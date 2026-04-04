from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math
import random

from flask import current_app, has_app_context

from config.game_rules import (
    PIG_DEFAULTS,
    PIG_HERITAGE_RULES,
    PIG_INTERACTION_RULES,
    PIG_LIMITS,
    PIG_OFFSPRING_RULES,
    PIG_POWER_RULES,
    PIG_TROPHY_RULES,
    PIG_VITALS_RULES,
    PIG_WEIGHT_RULES,
)
from data import (
    BOURSE_GRAIN_LAYOUT,
    CHARCUTERIE, CHARCUTERIE_PREMIUM, EPITAPHS, IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO,
    MAX_INJURY_RISK, MAX_PIG_SLOTS, MAX_PIG_WEIGHT_KG, MAX_WEIGHT_PERFORMANCE_MALUS,
    MIN_INJURY_RISK, MIN_PIG_WEIGHT_KG, PIG_EMOJIS, PIG_ORIGINS,
    PRELOADED_PIG_NAMES, RETIREMENT_HERITAGE_MIN_WINS, SCHOOL_XP_DECAY_FLOOR,
    SCHOOL_XP_DECAY_THRESHOLDS, SCHOOL_COOLDOWN_MINUTES, TRAIN_DAILY_CAP, VET_RESPONSE_MINUTES,
)
from exceptions import InsufficientFundsError, PigNotFoundError, PigTiredError, ValidationError


@dataclass(frozen=True)
class PigSettings:
    max_slots: int
    retirement_min_wins: int
    weight_default_kg: float
    weight_min_kg: float
    weight_max_kg: float
    weight_malus_ratio: float
    weight_malus_max: float
    injury_min_risk: float
    injury_max_risk: float
    vet_response_minutes: int


def get_pig_settings():
    from helpers.config import get_config

    def _f(key, default):
        try:
            return float(get_config(key, str(default)))
        except (TypeError, ValueError):
            return float(default)

    def _i(key, default):
        try:
            return int(float(get_config(key, str(default))))
        except (TypeError, ValueError):
            return int(default)

    return PigSettings(
        max_slots=_i('pig_max_slots', MAX_PIG_SLOTS),
        retirement_min_wins=_i('pig_retirement_min_wins', RETIREMENT_HERITAGE_MIN_WINS),
        weight_default_kg=_f('pig_weight_default_kg', PIG_DEFAULTS.weight_kg),
        weight_min_kg=_f('pig_weight_min_kg', MIN_PIG_WEIGHT_KG),
        weight_max_kg=_f('pig_weight_max_kg', MAX_PIG_WEIGHT_KG),
        weight_malus_ratio=_f('pig_weight_malus_ratio', IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO),
        weight_malus_max=_f('pig_weight_malus_max', MAX_WEIGHT_PERFORMANCE_MALUS),
        injury_min_risk=_f('pig_injury_min_risk', MIN_INJURY_RISK),
        injury_max_risk=_f('pig_injury_max_risk', MAX_INJURY_RISK),
        vet_response_minutes=_i('pig_vet_response_minutes', VET_RESPONSE_MINUTES),
    )


from extensions import db
from models import Auction, Participant, Pig, Race, Trophy, User, UserCerealInventory
from services.economy_service import (
    calculate_adoption_cost_for_counts,
    get_feeding_multiplier_for_count,
    get_level_happiness_bonus_value,
    get_progression_settings,
    scale_stat_gains,
    xp_for_level_value,
)
from services.finance_service import debit_user, reserve_pig_challenge_slot

from utils.time_utils import calculate_weekend_truce_hours


@dataclass(frozen=True)
class PigHeritageSnapshot:
    races_won: int
    level: int
    rarity: str
    lineage_boost: float

    @classmethod
    def from_source(cls, pig):
        if isinstance(pig, dict):
            return cls(
                races_won=int(pig.get('races_won') or 0),
                level=max(1, int(pig.get('level') or 1)),
                rarity=str(pig.get('rarity') or 'commun'),
                lineage_boost=float(pig.get('lineage_boost') or 0.0),
            )
        return cls(
            races_won=int(getattr(pig, 'races_won', 0) or 0),
            level=max(1, int(getattr(pig, 'level', 1) or 1)),
            rarity=str(getattr(pig, 'rarity', 'commun') or 'commun'),
            lineage_boost=float(getattr(pig, 'lineage_boost', 0.0) or 0.0),
        )


def get_pig_record(pig_or_id):
    if isinstance(pig_or_id, Pig):
        return pig_or_id
    pig = Pig.query.get(pig_or_id)
    if not pig:
        raise PigNotFoundError("Cochon introuvable.")
    return pig


def get_user_record(user_or_id):
    if isinstance(user_or_id, User):
        return user_or_id
    user = User.query.get(user_or_id)
    if not user:
        raise ValidationError("Utilisateur introuvable.")
    return user


def random_pig_sex():
    return random.choice(['M', 'F'])


def get_user_cereal_inventory_entry(user_id, cereal_key):
    return UserCerealInventory.query.filter_by(user_id=user_id, cereal_key=cereal_key).first()


def get_user_cereal_inventory_dict(user_or_id):
    from helpers.game_data import get_cereals_dict

    user = get_user_record(user_or_id)
    cereals = get_cereals_dict()
    inventory = {key: 0 for key in cereals.keys()}
    rows = UserCerealInventory.query.filter_by(user_id=user.id).all()
    for row in rows:
        inventory[row.cereal_key] = max(0, int(row.quantity or 0))
    return inventory


def add_cereal_to_inventory(user_or_id, cereal_key, quantity=1, commit=True):
    user = get_user_record(user_or_id)
    if quantity <= 0:
        raise ValidationError("Quantite invalide.")

    entry = get_user_cereal_inventory_entry(user.id, cereal_key)
    if entry is None:
        entry = UserCerealInventory(user_id=user.id, cereal_key=cereal_key, quantity=0)
        db.session.add(entry)
    entry.quantity = int(entry.quantity or 0) + int(quantity)
    if commit:
        db.session.commit()
    return entry


def consume_cereal_from_inventory(user_or_id, cereal_key, quantity=1, commit=True):
    user = get_user_record(user_or_id)
    if quantity <= 0:
        raise ValidationError("Quantite invalide.")

    entry = get_user_cereal_inventory_entry(user.id, cereal_key)
    if not entry or (entry.quantity or 0) < quantity:
        raise ValidationError("Tu n'as plus cette céréale en stock ! Va à la Bourse.")

    entry.quantity = max(0, int(entry.quantity or 0) - int(quantity))
    if commit:
        db.session.commit()
    return entry


def get_owned_alive_pig(user_id, pig_id):
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user_id or not pig.is_alive:
        raise PigNotFoundError("Cochon introuvable !")
    return pig


def get_winning_track_profiles(pig) -> set[str]:
    if not pig or not pig.id:
        return set()
    winning_rows = (
        db.session.query(Race.replay_json)
        .join(Participant, Participant.race_id == Race.id)
        .filter(
            Participant.pig_id == pig.id,
            Participant.finish_position == 1,
            Race.status == 'finished',
        )
        .all()
    )
    profiles = set()
    for (replay_json,) in winning_rows:
        if not replay_json:
            continue
        try:
            replay = json.loads(replay_json)
        except (TypeError, ValueError):
            continue
        if isinstance(replay, dict) and replay.get('track_profile'):
            profiles.add(replay['track_profile'])
    return profiles


def award_longevity_trophies(pig):
    if not pig or not pig.owner or not pig.created_at:
        return
    months_alive = max(0, (datetime.utcnow() - pig.created_at).days // PIG_TROPHY_RULES.longevity_days_per_trophy_step)
    for month_index in range(1, months_alive + 1):
        Trophy.award(
            user_id=pig.owner.id,
            code=f'ancient_one_month_{month_index}',
            label="L'Ancien",
            emoji='🕰️',
            description=f"{pig.name} a traverse {month_index} mois reel(s) de bureau sans quitter la porcherie.",
            pig_name=pig.name,
        )


def maybe_award_memorial_trophies(pig):
    if not pig or not pig.owner:
        return
    if pig.created_at and (datetime.utcnow() - pig.created_at).days >= PIG_TROPHY_RULES.elder_days_threshold:
        Trophy.award(
            user_id=pig.owner.id,
            code='office_elder',
            label="L'Ancien du Bureau",
            emoji='🗄️',
            description='Un cochon a tenu plus de 30 jours reels avant son post-mortem.',
            pig_name=pig.name,
        )
    if pig.created_at and (datetime.utcnow() - pig.created_at).days >= PIG_TROPHY_RULES.pillar_days_threshold:
        Trophy.award(
            user_id=pig.owner.id,
            code='office_pillar',
            label='Le Pilier de Bureau',
            emoji='🪑',
            description='Un cochon a tenu plus de 3 mois reels avant de quitter la piste.',
            pig_name=pig.name,
        )
    if pig.max_races and pig.races_entered >= pig.max_races and not pig.ever_bad_state:
        Trophy.award(
            user_id=pig.owner.id,
            code='golden_retirement',
            label='Retraite Doree',
            emoji='☕',
            description="Atteindre la limite de courses sans jamais tomber en mauvais etat.",
            pig_name=pig.name,
        )
    if len(get_winning_track_profiles(pig)) >= 3:
        Trophy.award(
            user_id=pig.owner.id,
            code='segment_expert',
            label='Expert des Segments',
            emoji='🧭',
            description='Ce cochon a gagne sur 3 profils de piste differents.',
            pig_name=pig.name,
        )
    if (pig.school_sessions_completed or 0) > PIG_TROPHY_RULES.school_sessions_memorial_threshold:
        Trophy.award(
            user_id=pig.owner.id,
            code='iron_memory',
            label='Memoire de Fer',
            emoji='🧠',
            description="Plus de 20 passages a l'ecole porcine avant la fin de carriere.",
            pig_name=pig.name,
        )


def get_school_decay_multiplier(pig) -> float:
    pig = get_pig_record(pig)
    today = datetime.utcnow().date()
    sessions = 0 if pig.last_school_date != today else (pig.daily_school_sessions or 0)
    for threshold, multiplier in SCHOOL_XP_DECAY_THRESHOLDS:
        if sessions < threshold:
            return multiplier
    return SCHOOL_XP_DECAY_FLOOR


def feed_pig(pig_or_id, cereal, commit=True):
    pig = get_pig_record(pig_or_id)
    if not pig.is_alive:
        raise PigTiredError("Ce cochon ne peut plus etre nourri.")
    if (pig.hunger or 0) >= PIG_INTERACTION_RULES.feed_block_hunger_threshold:
        raise PigTiredError("Ton cochon n'a plus faim !")

    pig.hunger = min(PIG_LIMITS.max_value, float(pig.hunger or 0.0) + cereal['hunger_restore'])
    pig.energy = min(PIG_LIMITS.max_value, float(pig.energy or 0.0) + cereal.get('energy_restore', 0))
    adjust_pig_weight(pig, cereal.get('weight_delta', 0.0))
    pig.apply_stat_boosts(cereal.get('stats', {}))
    pig.last_fed_at = datetime.utcnow()
    pig.register_positive_interaction(pig.last_fed_at)
    pig.mark_bad_state_if_needed()
    if commit:
        db.session.commit()
    return pig


def train_pig(pig_or_id, training, commit=True):
    pig = get_pig_record(pig_or_id)
    if not pig.is_alive or pig.is_injured:
        raise PigTiredError("Ton cochon est blesse. Passe d'abord par le veterinaire.")
    if training['energy_cost'] > 0 and (pig.energy or 0) < training['energy_cost']:
        raise PigTiredError("Ton cochon est trop fatigue !")
    if (pig.hunger or 0) < training.get('hunger_cost', 0):
        raise PigTiredError("Ton cochon a trop faim pour s'entrainer !")
    if (pig.happiness or 0) < training.get('min_happiness', 0):
        raise PigTiredError("Ton cochon n'est pas assez heureux !")

    progression = get_progression_settings()
    pig.energy = max(PIG_LIMITS.min_value, min(PIG_LIMITS.max_value, float(pig.energy or 0.0) - training['energy_cost']))
    pig.hunger = max(PIG_LIMITS.min_value, float(pig.hunger or 0.0) - training.get('hunger_cost', 0))
    adjust_pig_weight(pig, training.get('weight_delta', 0.0))
    if 'happiness_bonus' in training:
        pig.happiness = min(
            PIG_LIMITS.max_value,
            float(pig.happiness or 0.0) + (training['happiness_bonus'] * progression.training_happiness_multiplier),
        )
    pig.apply_stat_boosts(
        scale_stat_gains(training.get('stats', {}), progression.training_stat_gain_multiplier)
    )
    pig.register_positive_interaction(datetime.utcnow())
    pig.mark_bad_state_if_needed()
    if commit:
        db.session.commit()
    return pig


def study_pig(pig_or_id, lesson, correct, commit=True) -> str:
    pig = get_pig_record(pig_or_id)
    if not pig.is_alive or pig.is_injured:
        raise PigTiredError("L'ecole attendra. Ton cochon doit d'abord passer au veterinaire.")
    if (pig.energy or 0) < lesson['energy_cost']:
        raise PigTiredError("Ton cochon est trop fatigue pour suivre ce cours.")
    if (pig.hunger or 0) < lesson['hunger_cost']:
        raise PigTiredError("Ton cochon a trop faim pour se concentrer.")
    if (pig.happiness or 0) < lesson['min_happiness']:
        raise PigTiredError("Ton cochon boude l'ecole aujourd'hui. Remonte-lui le moral d'abord.")

    progression = get_progression_settings()
    decay = get_school_decay_multiplier(pig)
    today = datetime.utcnow().date()
    if pig.last_school_date != today:
        pig.daily_school_sessions = 0
        pig.last_school_date = today
    pig.daily_school_sessions = (pig.daily_school_sessions or 0) + 1

    pig.energy = max(PIG_LIMITS.min_value, float(pig.energy or 0.0) - lesson['energy_cost'])
    pig.hunger = max(PIG_LIMITS.min_value, float(pig.hunger or 0.0) - lesson['hunger_cost'])
    pig.last_school_at = datetime.utcnow()
    pig.school_sessions_completed = (pig.school_sessions_completed or 0) + 1

    if correct:
        pig.apply_stat_boosts(
            scale_stat_gains(lesson.get('stats', {}), progression.school_stat_gain_multiplier * decay)
        )
        pig.xp = int(pig.xp or 0) + int(round(lesson['xp'] * progression.school_xp_multiplier * decay))
        pig.happiness = min(
            PIG_LIMITS.max_value,
            float(pig.happiness or 0.0) + (lesson.get('happiness_bonus', 0) * progression.school_happiness_multiplier),
        )
        category = 'success'
    else:
        pig.xp = int(pig.xp or 0) + int(round(lesson.get('wrong_xp', 0) * progression.school_wrong_xp_multiplier * decay))
        pig.happiness = max(
            PIG_LIMITS.min_value,
            float(pig.happiness or 0.0) - (lesson.get('wrong_happiness_penalty', 0) * progression.school_wrong_happiness_multiplier),
        )
        category = 'warning'

    pig.register_positive_interaction(datetime.utcnow())
    pig.mark_bad_state_if_needed()
    check_level_up(pig)
    if commit:
        db.session.commit()
    return category


def buy_cereal_from_bourse_for_user(user_or_id, cereal_key):
    from helpers.game_data import get_cereals_dict
    from services.market_service import get_all_grain_surcharges, get_grain_market, is_grain_blocked, update_vitrine

    user = get_user_record(user_or_id)
    if cereal_key not in [key for key in BOURSE_GRAIN_LAYOUT.values() if key]:
        raise ValidationError("Cereale inconnue ou pas dans le bloc.")

    cereals = get_cereals_dict()
    cereal = cereals.get(cereal_key)
    if not cereal:
        raise ValidationError("Cereale introuvable !")

    market = get_grain_market()
    if is_grain_blocked(cereal_key, market):
        raise ValidationError(f"{cereal['name']} est en vitrine ! Achete autre chose pour debloquer.")

    surcharges = get_all_grain_surcharges(market)
    surcharge = surcharges.get(cereal_key, 1.0)
    feeding_multiplier = get_feeding_cost_multiplier(user)
    effective_cost = round(cereal['cost'] * surcharge * feeding_multiplier, 2)

    try:
        debit_user(
            user,
            effective_cost,
            reason_code='feed_purchase',
            reason_label='Achat Bourse aux Grains',
            details=(
                f"{cereal['name']} ajoute au stock. "
                f"Surcout Bourse x{surcharge:.2f}, "
                f"Pression x{feeding_multiplier:.2f}."
            ),
            reference_type='user',
            reference_id=user.id,
            commit=False,
        )
    except InsufficientFundsError:
        raise InsufficientFundsError("Pas assez de BitGroins !") from None

    add_cereal_to_inventory(user.id, cereal_key, quantity=1, commit=False)
    update_vitrine(market, cereal_key, user.id)
    db.session.commit()

    return {
        'category': 'success',
        'message': (
            f"{cereal['emoji']} x1 {cereal['name']} ajouté à l'inventaire ! "
            f"Prix: {effective_cost:.1f} 🪙"
        ),
    }


def feed_pig_for_user(user_or_id, pig_id, cereal_key):
    from helpers.game_data import get_cereals_dict

    user = get_user_record(user_or_id)
    pig = get_owned_alive_pig(user.id, pig_id)
    update_pig_vitals(pig)

    cereals = get_cereals_dict()
    cereal = cereals.get(cereal_key)
    if not cereal:
        raise ValidationError("Cereale introuvable !")

    try:
        consume_cereal_from_inventory(user.id, cereal_key, quantity=1, commit=False)
        feed_pig(pig, cereal, commit=False)
    except (ValidationError, PigTiredError):
        db.session.rollback()
        raise

    db.session.commit()
    return {
        'category': 'success',
        'message': f"{cereal['emoji']} {cereal['name']} donné ! Miam !",
    }


def train_pig_for_user(user_or_id, pig_id, training_key):
    from datetime import date as date_type
    from helpers.game_data import get_trainings_dict

    user = get_user_record(user_or_id)
    pig = get_owned_alive_pig(user.id, pig_id)
    update_pig_vitals(pig)

    trainings = get_trainings_dict()
    training = trainings.get(training_key)
    if not training:
        raise ValidationError("Entrainement introuvable !")

    today = date_type.today()
    if pig.last_train_date != today:
        pig.daily_train_count = 0
        pig.last_train_date = today
    if (pig.daily_train_count or 0) >= TRAIN_DAILY_CAP:
        raise ValidationError(
            f"Ton cochon a atteint sa limite d'entrainement pour aujourd'hui ({TRAIN_DAILY_CAP} sessions). Reviens demain !"
        )

    train_pig(pig, training, commit=False)
    pig.daily_train_count = (pig.daily_train_count or 0) + 1
    pig.last_train_date = today
    db.session.commit()

    remaining = max(0, TRAIN_DAILY_CAP - pig.daily_train_count)
    suffix = (
        f" ({remaining} session{'s' if remaining != 1 else ''} restante{'s' if remaining != 1 else ''} aujourd'hui)"
        if remaining < 3 else ""
    )
    return {
        'category': 'success',
        'message': f"{training['emoji']} {training['name']} termine !{suffix}",
    }


def study_pig_for_user(user_or_id, pig_id, lesson_key, answer_idx, cooldown_minutes=SCHOOL_COOLDOWN_MINUTES):
    from helpers.game_data import get_school_lessons_dict
    from helpers.time_helpers import format_duration_short, get_cooldown_remaining

    user = get_user_record(user_or_id)
    pig = get_owned_alive_pig(user.id, pig_id)
    update_pig_vitals(pig)

    lessons = get_school_lessons_dict()
    lesson = lessons.get(lesson_key)
    if not lesson:
        raise ValidationError("Cours introuvable !")

    cooldown = get_cooldown_remaining(pig.last_school_at, cooldown_minutes)
    if cooldown > 0:
        raise ValidationError(
            f"La salle de classe est fermee pour l'instant. Reviens dans {format_duration_short(cooldown)}."
        )

    answers = lesson.get('answers', [])
    if answer_idx is None or answer_idx < 0 or answer_idx >= len(answers):
        raise ValidationError("Reponse invalide !")

    selected_answer = answers[answer_idx]
    decay_before = get_school_decay_multiplier(pig)
    category = study_pig(pig, lesson, correct=selected_answer['correct'], commit=False)
    db.session.commit()

    feedback_prefix = (
        "Cours valide avec mention groin-tres-bien."
        if category == 'success'
        else "Le cours etait plus complique que prevu."
    )
    decay_suffix = ""
    if decay_before < 1.0:
        decay_suffix = f" (rendement ecole reduit a {int(decay_before * 100)}% aujourd'hui)"
    return {
        'category': category,
        'message': f"{lesson['emoji']} {lesson['name']} - {feedback_prefix} {selected_answer['feedback']}{decay_suffix}",
    }


def enter_pig_death_challenge(user_or_id, pig_id, wager):
    user = get_user_record(user_or_id)
    pig = get_owned_alive_pig(user.id, pig_id)
    update_pig_vitals(pig)

    if pig.is_injured:
        raise ValidationError("Impossible d'inscrire un cochon blesse au Challenge de la Mort.")
    if not wager or wager < 10:
        raise ValidationError("Mise minimum : 10 🪙 pour le Challenge de la Mort !")
    if pig.challenge_mort_wager > 0:
        raise ValidationError("Tu es deja inscrit au Challenge de la Mort !")
    if pig.energy <= PIG_INTERACTION_RULES.race_ready_energy_threshold or pig.hunger <= PIG_INTERACTION_RULES.race_ready_hunger_threshold:
        raise PigTiredError("Ton cochon est trop faible pour le Challenge !")

    try:
        debit_user(
            user,
            wager,
            reason_code='challenge_entry',
            reason_label='Inscription Challenge de la Mort',
            details=f"{pig.name} engage pour {wager:.0f} 🪙.",
            reference_type='pig',
            reference_id=pig.id,
            commit=False,
        )
    except InsufficientFundsError:
        raise InsufficientFundsError("T'as pas les moyens de jouer avec la vie de ton cochon !") from None

    if not reserve_pig_challenge_slot(pig.id, wager):
        db.session.rollback()
        raise ValidationError("Tu es deja inscrit au Challenge de la Mort !")

    db.session.commit()
    return {
        'category': 'success',
        'message': f"💀 {pig.name} inscrit au Challenge de la Mort ({wager:.0f} 🪙) ! Bonne chance...",
    }


def kill_pig(pig_or_id, cause='abattoir', commit=True):
    pig = get_pig_record(pig_or_id)
    charcuterie = random.choice(CHARCUTERIE)
    epitaph_template = random.choice(EPITAPHS)
    pig.is_alive = False
    pig.is_injured = False
    pig.vet_deadline = None
    pig.death_date = datetime.utcnow()
    pig.death_cause = cause
    pig.charcuterie_type = charcuterie['name']
    pig.charcuterie_emoji = charcuterie['emoji']
    pig.epitaph = epitaph_template.format(name=pig.name, wins=pig.races_won)
    pig.challenge_mort_wager = 0
    maybe_award_memorial_trophies(pig)
    if commit:
        db.session.commit()
    return pig


def retire_pig(pig_or_id, commit=True):
    pig = get_pig_record(pig_or_id)
    charcuterie = random.choice(CHARCUTERIE_PREMIUM)
    pig.is_alive = False
    pig.is_injured = False
    pig.vet_deadline = None
    pig.death_date = datetime.utcnow()
    pig.death_cause = 'vieillesse'
    pig.charcuterie_type = charcuterie['name']
    pig.charcuterie_emoji = charcuterie['emoji']
    pig.epitaph = (
        f"{pig.name} a pris sa retraite après {pig.races_entered} courses glorieuses. "
        f"Un cochon bien vieilli fait le meilleur jambon."
    )
    pig.challenge_mort_wager = 0
    maybe_award_memorial_trophies(pig)
    if commit:
        db.session.commit()
    return pig


def update_pig_vitals(pig_or_id, force_commit=False):
    pig = get_pig_record(pig_or_id)
    now = datetime.utcnow()
    progression = get_progression_settings()
    min_commit_interval = PIG_VITALS_RULES.min_commit_interval_seconds
    if has_app_context():
        min_commit_interval = current_app.config.get(
            'PIG_VITALS_COMMIT_INTERVAL_SECONDS',
            PIG_VITALS_RULES.min_commit_interval_seconds,
        )

    award_longevity_trophies(pig)
    if not pig.last_updated:
        pig.last_updated = now
        return pig

    elapsed_seconds = (now - pig.last_updated).total_seconds()
    elapsed_hours = elapsed_seconds / 3600
    if elapsed_hours < 0.01:
        return pig

    truce_hours = calculate_weekend_truce_hours(pig.last_updated, now)
    effective_hours = max(0.0, elapsed_hours - truce_hours)
    hours = min(effective_hours, 24)
    if effective_hours < 0.01:
        pig.last_updated = now
        if force_commit or elapsed_seconds >= min_commit_interval:
            db.session.commit()
        return pig

    reference_interaction = pig.last_interaction_at or pig.last_updated
    if reference_interaction:
        grace_deadline = reference_interaction + timedelta(hours=progression.freshness_grace_hours)
        if now > grace_deadline:
            elapsed_workdays = 0
            cursor = grace_deadline.date()
            while cursor <= now.date():
                if cursor.weekday() < 5:
                    elapsed_workdays += 1
                cursor += timedelta(days=1)
            pig.freshness = max(
                PIG_LIMITS.min_value,
                PIG_DEFAULTS.freshness - (elapsed_workdays * progression.freshness_decay_per_workday),
            )
        else:
            pig.freshness = PIG_DEFAULTS.freshness

    pig.hunger = max(PIG_LIMITS.min_value, pig.hunger - (hours * progression.hunger_decay_per_hour))
    if pig.hunger > progression.energy_regen_hunger_threshold:
        pig.energy = min(PIG_LIMITS.max_value, pig.energy + (hours * progression.energy_regen_per_hour))
    else:
        pig.energy = max(PIG_LIMITS.min_value, pig.energy - (hours * progression.energy_drain_per_hour))

    if pig.hunger < PIG_VITALS_RULES.low_hunger_threshold:
        pig.happiness = max(PIG_LIMITS.min_value, pig.happiness - (hours * progression.low_hunger_happiness_drain_per_hour))
    elif pig.hunger < PIG_VITALS_RULES.mid_hunger_threshold:
        pig.happiness = max(PIG_LIMITS.min_value, pig.happiness - (hours * progression.mid_hunger_happiness_drain_per_hour))
    elif pig.happiness < progression.passive_happiness_regen_cap:
        pig.happiness = min(
            progression.passive_happiness_regen_cap,
            pig.happiness + (hours * progression.passive_happiness_regen_per_hour),
        )

    current_weight = pig.weight_kg or PIG_DEFAULTS.weight_kg
    if pig.hunger < PIG_VITALS_RULES.weight_loss_hunger_threshold:
        pig.weight_kg = clamp_pig_weight(current_weight - hours * PIG_VITALS_RULES.starving_weight_loss_per_hour)
    elif (
        pig.hunger > PIG_VITALS_RULES.weight_gain_hunger_threshold
        and pig.energy < PIG_VITALS_RULES.weight_gain_low_energy_threshold
    ):
        pig.weight_kg = clamp_pig_weight(current_weight + hours * PIG_VITALS_RULES.resting_weight_gain_per_hour)
    elif (
        pig.energy > PIG_VITALS_RULES.weight_loss_high_energy_threshold
        and pig.hunger < PIG_VITALS_RULES.weight_loss_balanced_hunger_threshold
    ):
        pig.weight_kg = clamp_pig_weight(current_weight - hours * PIG_VITALS_RULES.active_weight_loss_per_hour)

    pig.mark_bad_state_if_needed()
    pig.last_updated = now
    if force_commit or elapsed_seconds >= min_commit_interval:
        db.session.commit()
    return pig


def get_freshness_bonus(pig):
    freshness_value = (
        max(
            PIG_LIMITS.min_value,
            min(PIG_LIMITS.max_value, float(getattr(pig, 'freshness', PIG_DEFAULTS.freshness) or PIG_DEFAULTS.freshness)),
        )
        if pig else PIG_DEFAULTS.freshness
    )
    return {
        'active': freshness_value >= PIG_INTERACTION_RULES.freshness_bonus_threshold,
        'multiplier': 1.0,
        'bonus_percent': 0.0,
        'hours_remaining': 0.0,
        'value': round(freshness_value, 1),
    }


def clamp_pig_weight(weight):
    ps = get_pig_settings()
    return round(min(ps.weight_max_kg, max(ps.weight_min_kg, weight)), 1)


def get_weight_stat(source, stat_name, default=PIG_DEFAULTS.stat):
    if isinstance(source, dict):
        value = source.get(stat_name, default)
    else:
        value = getattr(source, stat_name, default)
    return float(default if value is None else value)


def calculate_target_weight_kg(source, level=None):
    force = get_weight_stat(source, 'force')
    endurance = get_weight_stat(source, 'endurance')
    agilite = get_weight_stat(source, 'agilite')
    vitesse = get_weight_stat(source, 'vitesse')
    if level is None:
        level = source.get('level', 1) if isinstance(source, dict) else getattr(source, 'level', 1)
    level = max(1, int(level or 1))

    target = (
        PIG_WEIGHT_RULES.base_target_weight_kg
        + (force * PIG_WEIGHT_RULES.target_force_factor)
        + (endurance * PIG_WEIGHT_RULES.target_endurance_factor)
        - (agilite * PIG_WEIGHT_RULES.target_agilite_factor)
        - (vitesse * PIG_WEIGHT_RULES.target_vitesse_factor)
        + ((level - 1) * PIG_WEIGHT_RULES.target_level_factor)
    )
    return round(
        min(PIG_WEIGHT_RULES.max_target_weight_kg, max(PIG_WEIGHT_RULES.min_target_weight_kg, target)),
        1,
    )


def generate_weight_kg_for_profile(source, level=None):
    ideal = calculate_target_weight_kg(source, level=level)
    return clamp_pig_weight(
        random.uniform(
            ideal - PIG_WEIGHT_RULES.spawn_variation_kg,
            ideal + PIG_WEIGHT_RULES.spawn_variation_kg,
        )
    )


def adjust_pig_weight(pig, delta):
    pig.weight_kg = clamp_pig_weight((pig.weight_kg or get_pig_settings().weight_default_kg) + delta)
    return pig.weight_kg


def get_weight_profile(pig):
    current_weight = clamp_pig_weight(pig.weight_kg or get_pig_settings().weight_default_kg)
    ideal_weight = calculate_target_weight_kg(pig)
    tolerance = round(
        PIG_WEIGHT_RULES.base_tolerance_kg
        + (pig.endurance * PIG_WEIGHT_RULES.tolerance_endurance_factor)
        + (pig.force * PIG_WEIGHT_RULES.tolerance_force_factor),
        1,
    )
    delta = round(current_weight - ideal_weight, 1)
    abs_delta = abs(delta)
    race_factor = max(
        PIG_WEIGHT_RULES.race_factor_floor,
        min(
            PIG_WEIGHT_RULES.race_factor_cap,
            PIG_WEIGHT_RULES.race_factor_base
            - (
                (
                    abs_delta
                    / max(
                        tolerance * PIG_WEIGHT_RULES.race_factor_window_multiplier,
                        PIG_WEIGHT_RULES.minimum_ratio_denominator,
                    )
                )
                * PIG_WEIGHT_RULES.race_factor_penalty_factor
            ),
        ),
    )
    injury_factor = 1.0 + min(
        PIG_WEIGHT_RULES.injury_factor_cap,
        abs_delta / max(
            tolerance * PIG_WEIGHT_RULES.injury_factor_window_multiplier,
            PIG_WEIGHT_RULES.minimum_ratio_denominator,
        ),
    )

    force_mod = 1.0
    agilite_mod = 1.0
    if delta > 0:
        ratio = delta / max(tolerance, PIG_WEIGHT_RULES.minimum_ratio_denominator)
        force_mod = 1.0 + min(PIG_WEIGHT_RULES.heavy_force_bonus_cap, ratio * PIG_WEIGHT_RULES.heavy_force_bonus_factor)
        agilite_mod = 1.0 - min(PIG_WEIGHT_RULES.heavy_agilite_penalty_cap, ratio * PIG_WEIGHT_RULES.heavy_agilite_penalty_factor)
    elif delta < 0:
        ratio = abs(delta) / max(tolerance, PIG_WEIGHT_RULES.minimum_ratio_denominator)
        force_mod = 1.0 - min(PIG_WEIGHT_RULES.light_force_penalty_cap, ratio * PIG_WEIGHT_RULES.light_force_penalty_factor)
        agilite_mod = 1.0 + min(PIG_WEIGHT_RULES.light_agilite_bonus_cap, ratio * PIG_WEIGHT_RULES.light_agilite_bonus_factor)

    if abs_delta <= tolerance * PIG_WEIGHT_RULES.ideal_zone_ratio:
        status = 'ideal'
        status_label = 'Zone ideale'
        note = "Ton cochon est dans son poids de forme. Il transforme mieux ses stats en vitesse utile."
    elif delta > tolerance:
        status = 'heavy'
        status_label = 'Trop lourd'
        note = "Impact strategique : Il devient un bulldozer (Force+) mais perd toute souplesse (Agilite-)."
    elif delta < -tolerance:
        status = 'light'
        status_label = 'Trop leger'
        note = "Impact strategique : Il est tres vif (Agilite+) mais manque d'impact face aux autres (Force-)."
    else:
        status = 'warning'
        status_label = 'A surveiller'
        note = "Le poids reste jouable, mais un petit ajustement peut encore aider en course."

    return {
        'current_weight': current_weight,
        'ideal_weight': ideal_weight,
        'min_weight': round(ideal_weight - tolerance, 1),
        'max_weight': round(ideal_weight + tolerance, 1),
        'delta': delta,
        'status': status,
        'status_label': status_label,
        'note': note,
        'race_factor': round(race_factor, 3),
        'race_percent': round((race_factor - 1.0) * 100, 1),
        'injury_factor': round(injury_factor, 3),
        'score_pct': max(
            PIG_WEIGHT_RULES.score_floor_percent,
            min(PIG_LIMITS.max_value, int((race_factor / PIG_WEIGHT_RULES.race_factor_cap) * 100)),
        ),
        'force_mod': round(force_mod, 2),
        'agilite_mod': round(agilite_mod, 2),
    }


def get_pig_performance_flags(pig):
    weight_profile = get_weight_profile(pig)
    ideal_weight = max(PIG_WEIGHT_RULES.minimum_ratio_denominator, weight_profile['ideal_weight'])
    deviation_ratio = abs(weight_profile['current_weight'] - ideal_weight) / ideal_weight
    return {
        'hungry_penalty': (pig.hunger or 0) < PIG_POWER_RULES.hungry_penalty_threshold,
        'weight_penalty': deviation_ratio > get_pig_settings().weight_malus_ratio,
        'weight_status': weight_profile['status'],
    }


def update_pig_state(pig):
    update_pig_vitals(pig)


def calculate_pig_power(pig):
    profile = get_weight_profile(pig)
    freshness = get_freshness_bonus(pig)
    effective_force = pig.force * profile['force_mod']
    effective_endurance = pig.endurance
    effective_vitesse = pig.vitesse
    effective_agilite = pig.agilite * profile['agilite_mod']
    if (pig.hunger or 0) < PIG_POWER_RULES.hungry_penalty_threshold:
        effective_force *= PIG_POWER_RULES.hungry_penalty_multiplier
        effective_endurance *= PIG_POWER_RULES.hungry_penalty_multiplier
    ps = get_pig_settings()
    ideal_weight = max(PIG_WEIGHT_RULES.minimum_ratio_denominator, profile['ideal_weight'])
    deviation_ratio = abs(profile['current_weight'] - ideal_weight) / ideal_weight
    if deviation_ratio > ps.weight_malus_ratio:
        excess_ratio = deviation_ratio - ps.weight_malus_ratio
        penalty = min(ps.weight_malus_max, excess_ratio / ps.weight_malus_ratio * PIG_POWER_RULES.excess_weight_penalty_scale)
        modifier = 1.0 - penalty
        effective_vitesse *= modifier
        effective_agilite *= modifier
    effective_moral = pig.moral * freshness['multiplier']
    stats = [effective_vitesse, effective_endurance, effective_agilite, effective_force, pig.intelligence, effective_moral]
    stat_score = sum(
        math.sqrt(max(PIG_LIMITS.min_value, stat) / PIG_LIMITS.max_value) * PIG_LIMITS.max_value
        for stat in stats
    ) / len(stats)
    condition_factor = (
        PIG_POWER_RULES.condition_base
        + (
            ((pig.energy + pig.hunger + pig.happiness) / PIG_POWER_RULES.vitals_average_divisor)
            / PIG_LIMITS.max_value
        ) * PIG_POWER_RULES.condition_range
    )
    return round(stat_score * condition_factor * profile['race_factor'], 2)


def xp_for_level(level):
    return xp_for_level_value(level)


def check_level_up(pig):
    while pig.xp >= xp_for_level(pig.level + 1):
        pig.level += 1
        pig.happiness = min(PIG_LIMITS.max_value, pig.happiness + get_level_happiness_bonus_value())


def reset_snack_share_limit_if_needed(user, now=None):
    if not user:
        return
    current_time = now or datetime.utcnow()
    if not user.snack_share_reset_at or user.snack_share_reset_at.date() != current_time.date():
        user.snack_shares_today = 0
        user.snack_share_reset_at = current_time


def get_active_listing_count(user):
    return Auction.query.filter_by(seller_id=user.id, status='active').count()


def get_pig_slot_count(user):
    active_pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).count()
    return active_pigs + get_active_listing_count(user)


def get_max_pig_slots(user=None):
    return get_pig_settings().max_slots


def get_adoption_cost(user):
    slot_count = get_pig_slot_count(user)
    if slot_count >= get_max_pig_slots(user):
        return None
    active_count = Pig.query.filter_by(user_id=user.id, is_alive=True).count()
    return calculate_adoption_cost_for_counts(active_count, slot_count, get_max_pig_slots(user))


def get_feeding_cost_multiplier(user):
    active_count = Pig.query.filter_by(user_id=user.id, is_alive=True).count()
    return get_feeding_multiplier_for_count(active_count)


def get_lineage_label(pig):
    return pig.lineage_name or pig.name


def get_pig_heritage_value(pig):
    heritage = PigHeritageSnapshot.from_source(pig)
    rarity_bonus = PIG_HERITAGE_RULES.rarity_bonus_by_key.get(heritage.rarity, 0.0)
    return round(
        (heritage.races_won * PIG_HERITAGE_RULES.heritage_races_won_factor)
        + max(0, heritage.level - 1) * PIG_HERITAGE_RULES.heritage_level_factor
        + heritage.lineage_boost
        + rarity_bonus,
        2,
    )


def can_retire_into_heritage(pig):
    return bool(pig and pig.is_alive and not pig.retired_into_heritage and ((pig.races_won or 0) >= get_pig_settings().retirement_min_wins or (pig.rarity == 'legendaire')))


def retire_pig_into_heritage(user, pig):
    if not can_retire_into_heritage(pig):
        return 0.0
    bonus = max(
        PIG_HERITAGE_RULES.minimum_retirement_bonus,
        round(get_pig_heritage_value(pig) * PIG_HERITAGE_RULES.retirement_bonus_factor, 2),
    )
    user.barn_heritage_bonus = round((user.barn_heritage_bonus or 0.0) + bonus, 2)
    pig.retired_into_heritage = True
    pig.lineage_boost = round((pig.lineage_boost or 0.0) + bonus, 2)
    lineage_name = get_lineage_label(pig)
    related_pigs = Pig.query.filter(Pig.user_id == user.id, Pig.is_alive == True, Pig.id != pig.id, Pig.lineage_name == lineage_name).all()
    for descendant in related_pigs:
        descendant.lineage_boost = round((descendant.lineage_boost or 0.0) + bonus, 2)
        descendant.moral = min(
            PIG_LIMITS.max_value,
            (descendant.moral or 0.0) + min(PIG_HERITAGE_RULES.descendant_moral_cap, bonus * PIG_HERITAGE_RULES.descendant_lineage_factor),
        )
    retire_pig(pig, commit=False)
    pig.death_cause = 'retraite_honoree'
    pig.epitaph = f"{pig.name} entre au haras des legends. Sa lignee inspire toute la porcherie (+{bonus:.1f} heritage)."
    db.session.commit()
    return bonus


def normalize_pig_name(name):
    return ' '.join((name or '').split()).casefold()


def is_pig_name_taken(name, exclude_pig_id=None):
    normalized = normalize_pig_name(name)
    if not normalized:
        return False
    pigs = Pig.query
    if exclude_pig_id is not None:
        pigs = pigs.filter(Pig.id != exclude_pig_id)
    return any(normalize_pig_name(pig.name) == normalized for pig in pigs.all())


def build_unique_pig_name(base_name, fallback_prefix='Cochon'):
    candidate = ' '.join((base_name or '').split())[:80]
    if not candidate:
        candidate = fallback_prefix
    if not is_pig_name_taken(candidate):
        return candidate
    suffix = 2
    while True:
        suffix_label = f' {suffix}'
        trimmed = candidate[:max(1, 80 - len(suffix_label))].rstrip()
        unique_name = f'{trimmed}{suffix_label}'
        if not is_pig_name_taken(unique_name):
            return unique_name
        suffix += 1


def apply_origin_bonus(pig, origin):
    base_value = getattr(pig, origin['bonus_stat']) or PIG_DEFAULTS.stat
    setattr(pig, origin['bonus_stat'], base_value + origin['bonus'])


def create_offspring(user, parent_a, parent_b, name=None):
    if parent_a.sex == parent_b.sex:
        raise ValidationError("La reproduction nécessite un mâle et une femelle !")

    sire = parent_a if parent_a.sex == 'M' else parent_b
    dam = parent_a if parent_a.sex == 'F' else parent_b
    lineage_name = parent_a.lineage_name or parent_b.lineage_name or f"Maison {user.username}"
    barn_bonus = user.barn_heritage_bonus or 0.0
    child = Pig(
        user_id=user.id,
        name=build_unique_pig_name(name or f"Porcelet {lineage_name}", fallback_prefix='Porcelet'),
        emoji=random.choice(PIG_EMOJIS),
        sex=random_pig_sex(),
        rarity=parent_a.rarity if parent_a.rarity == parent_b.rarity else random.choice([parent_a.rarity, parent_b.rarity, 'commun']),
        origin_country=random.choice([parent_a.origin_country, parent_b.origin_country]),
        origin_flag=random.choice([parent_a.origin_flag, parent_b.origin_flag]),
        lineage_name=lineage_name,
        generation=max(parent_a.generation or 1, parent_b.generation or 1) + 1,
        sire_id=sire.id,
        dam_id=dam.id,
        lineage_boost=round(
            ((parent_a.lineage_boost or 0.0) + (parent_b.lineage_boost or 0.0)) * PIG_OFFSPRING_RULES.parent_lineage_factor
            + (barn_bonus * PIG_OFFSPRING_RULES.barn_bonus_factor),
            2,
        ),
    )
    for stat in ['vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral']:
        base = (getattr(parent_a, stat, PIG_DEFAULTS.stat) + getattr(parent_b, stat, PIG_DEFAULTS.stat)) / 2
        inherited = (
            base * PIG_OFFSPRING_RULES.inherited_stats_parent_average_factor
            + random.uniform(
                PIG_OFFSPRING_RULES.inherited_stats_random_min,
                PIG_OFFSPRING_RULES.inherited_stats_random_max,
            )
            + child.lineage_boost
        )
        setattr(
            child,
            stat,
            round(min(PIG_LIMITS.max_value, max(PIG_OFFSPRING_RULES.inherited_stat_floor, inherited)), 1),
        )
    child.energy = PIG_OFFSPRING_RULES.initial_energy
    child.hunger = PIG_OFFSPRING_RULES.initial_hunger
    child.happiness = min(
        PIG_LIMITS.max_value,
        round(
            PIG_OFFSPRING_RULES.initial_happiness_base
            + (barn_bonus * PIG_OFFSPRING_RULES.initial_happiness_barn_bonus_factor),
            1,
        ),
    )
    child.weight_kg = generate_weight_kg_for_profile(child, level=child.level)
    return child


def create_preloaded_admin_pigs(admin_user):
    if not admin_user:
        return 0
    created = 0
    for index, pig_name in enumerate(PRELOADED_PIG_NAMES):
        if is_pig_name_taken(pig_name):
            continue
        origin = PIG_ORIGINS[index % len(PIG_ORIGINS)]
        pig = Pig(
            user_id=admin_user.id,
            name=pig_name,
            emoji=PIG_EMOJIS[index % len(PIG_EMOJIS)],
            sex=random_pig_sex(),
            origin_country=origin['country'],
            origin_flag=origin['flag'],
            lineage_name='Maison Admin',
        )
        apply_origin_bonus(pig, origin)
        pig.weight_kg = generate_weight_kg_for_profile(pig)
        db.session.add(pig)
        created += 1
    return created
