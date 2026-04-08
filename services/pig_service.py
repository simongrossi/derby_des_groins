from datetime import UTC, datetime, timedelta
import json
import random

from config.game_rules import (
    PIG_DEFAULTS,
    PIG_HERITAGE_RULES,
    PIG_INTERACTION_RULES,
    PIG_LIMITS,
    PIG_TROPHY_RULES,
    PIG_VITALS_RULES,
)
from config.grain_market_defaults import BOURSE_GRAIN_LAYOUT
from content.flavor_texts import CHARCUTERIE, CHARCUTERIE_PREMIUM, EPITAPHS
from exceptions import InsufficientFundsError, PigNotFoundError, PigTiredError, ValidationError


from extensions import db
from models import Auction, Participant, Pig, Race, Trophy, User, UserCerealInventory
from services.economy_service import (
    calculate_adoption_cost_for_counts,
    get_feeding_multiplier_for_count,
    get_progression_settings,
    scale_stat_gains,
)
from services.finance_service import debit_user, reserve_pig_challenge_slot
from services.gameplay_settings_service import get_gameplay_settings
from services.pig_lineage_service import (
    PigHeritageSnapshot,
    apply_origin_bonus,
    build_unique_pig_name,
    create_offspring,
    create_preloaded_admin_pigs,
    get_lineage_label,
    get_pig_heritage_value,
    is_pig_name_taken,
    normalize_pig_name,
    random_pig_sex,
)
from services.pig_power_service import (
    PigSettings,
    adjust_pig_weight,
    calculate_pig_power,
    calculate_target_weight_kg,
    check_level_up,
    clamp_pig_weight,
    generate_weight_kg_for_profile,
    get_freshness_bonus,
    get_pig_performance_flags,
    get_pig_settings,
    get_weight_profile,
    get_weight_stat,
    xp_for_level,
)
from services.pig_vitals_buffer_service import (
    apply_buffered_vitals_to_pig,
    discard_buffered_pig_vitals,
    flush_buffered_pig_vitals,
    queue_buffered_pig_vitals,
)

from utils.time_utils import calculate_weekend_truce_hours


def _utcnow_naive():
    return datetime.now(UTC).replace(tzinfo=None)


def get_pig_record(pig_or_id):
    if isinstance(pig_or_id, Pig):
        return apply_buffered_vitals_to_pig(pig_or_id)
    pig = db.session.get(Pig, pig_or_id)
    if not pig:
        raise PigNotFoundError("Cochon introuvable.")
    return apply_buffered_vitals_to_pig(pig)


def get_user_record(user_or_id):
    if isinstance(user_or_id, User):
        return user_or_id
    user = db.session.get(User, user_or_id)
    if not user:
        raise ValidationError("Utilisateur introuvable.")
    return user


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
    pig = get_pig_record(pig_id)
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
    months_alive = max(0, (_utcnow_naive() - pig.created_at).days // PIG_TROPHY_RULES.longevity_days_per_trophy_step)
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
    if pig.created_at and (_utcnow_naive() - pig.created_at).days >= PIG_TROPHY_RULES.elder_days_threshold:
        Trophy.award(
            user_id=pig.owner.id,
            code='office_elder',
            label="L'Ancien du Bureau",
            emoji='🗄️',
            description='Un cochon a tenu plus de 30 jours reels avant son post-mortem.',
            pig_name=pig.name,
        )
    if pig.created_at and (_utcnow_naive() - pig.created_at).days >= PIG_TROPHY_RULES.pillar_days_threshold:
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


def get_learning_decay_multiplier(pig) -> float:
    pig = get_pig_record(pig)
    today = datetime.utcnow().date()
    sessions = 0 if pig.last_school_date != today else (pig.daily_school_sessions or 0)
    gameplay = get_gameplay_settings()
    for threshold, multiplier in gameplay.school_xp_decay_thresholds:
        if sessions < threshold:
            return multiplier
    return gameplay.school_xp_decay_floor


def get_school_decay_multiplier(pig) -> float:
    return get_learning_decay_multiplier(pig)


def register_learning_session(pig_or_id, session_time=None):
    pig = get_pig_record(pig_or_id)
    session_time = session_time or datetime.utcnow()
    today = session_time.date()
    if pig.last_school_date != today:
        pig.daily_school_sessions = 0
        pig.last_school_date = today
    pig.daily_school_sessions = (pig.daily_school_sessions or 0) + 1
    pig.last_school_at = session_time
    pig.last_updated = session_time
    return pig.daily_school_sessions


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
    decay = get_learning_decay_multiplier(pig)
    register_learning_session(pig)

    pig.energy = max(PIG_LIMITS.min_value, float(pig.energy or 0.0) - lesson['energy_cost'])
    pig.hunger = max(PIG_LIMITS.min_value, float(pig.hunger or 0.0) - lesson['hunger_cost'])
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
    from services.market_service import get_all_grain_surcharges, get_grain_block_reason, get_grain_market, update_vitrine

    user = get_user_record(user_or_id)
    if cereal_key not in [key for key in BOURSE_GRAIN_LAYOUT.values() if key]:
        raise ValidationError("Cereale inconnue ou pas dans le bloc.")

    cereals = get_cereals_dict()
    cereal = cereals.get(cereal_key)
    if not cereal:
        raise ValidationError("Cereale introuvable !")

    market = get_grain_market()
    block_reason = get_grain_block_reason(cereal_key, market)
    if block_reason:
        raise ValidationError(block_reason)

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
    gameplay = get_gameplay_settings()
    if (pig.daily_train_count or 0) >= gameplay.train_daily_cap:
        raise ValidationError(
            f"Ton cochon a atteint sa limite d'entrainement pour aujourd'hui ({gameplay.train_daily_cap} sessions). Reviens demain !"
        )

    train_pig(pig, training, commit=False)
    pig.daily_train_count = (pig.daily_train_count or 0) + 1
    pig.last_train_date = today
    db.session.commit()

    remaining = max(0, gameplay.train_daily_cap - pig.daily_train_count)
    suffix = (
        f" ({remaining} session{'s' if remaining != 1 else ''} restante{'s' if remaining != 1 else ''} aujourd'hui)"
        if remaining < 3 else ""
    )
    return {
        'category': 'success',
        'message': f"{training['emoji']} {training['name']} termine !{suffix}",
    }


def study_pig_for_user(user_or_id, pig_id, lesson_key, answer_idx, cooldown_minutes=None):
    from helpers.game_data import get_school_lessons_dict
    from helpers.time_helpers import format_duration_short, get_cooldown_remaining

    user = get_user_record(user_or_id)
    pig = get_owned_alive_pig(user.id, pig_id)
    update_pig_vitals(pig)

    lessons = get_school_lessons_dict()
    lesson = lessons.get(lesson_key)
    if not lesson:
        raise ValidationError("Cours introuvable !")

    applied_cooldown = get_gameplay_settings().school_cooldown_minutes if cooldown_minutes is None else cooldown_minutes
    cooldown = get_cooldown_remaining(pig.last_school_at, applied_cooldown)
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
    pig.death_date = _utcnow_naive()
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
    now = _utcnow_naive()
    progression = get_progression_settings()

    award_longevity_trophies(pig)
    created_trophies = any(isinstance(obj, Trophy) for obj in db.session.new)
    if not pig.last_updated:
        pig.last_updated = now
        queue_buffered_pig_vitals(pig, queued_at=now)
        if force_commit:
            flush_buffered_pig_vitals(pig_ids=[pig.id])
        elif created_trophies:
            db.session.commit()
            discard_buffered_pig_vitals(pig.id)
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
        queue_buffered_pig_vitals(pig, queued_at=now)
        if force_commit:
            flush_buffered_pig_vitals(pig_ids=[pig.id])
        elif created_trophies:
            db.session.commit()
            discard_buffered_pig_vitals(pig.id)
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
    queue_buffered_pig_vitals(pig, queued_at=now)
    if force_commit:
        flush_buffered_pig_vitals(pig_ids=[pig.id])
    elif created_trophies:
        db.session.commit()
        discard_buffered_pig_vitals(pig.id)
    return pig


def update_pig_state(pig):
    update_pig_vitals(pig)


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


def recommend_best_cereal(pig, inventory_dict):
    """
    Choisit la meilleure céréale du stock pour ce cochon.
    Priorité :
    1. Si faim < 40 : céréale à fort hunger_restore.
    2. Si énergie < 40 : céréale à fort energy_restore.
    3. Sinon : céréale boostant les statistiques les plus faibles du cochon (équilibrage).
    """
    from helpers.game_data import get_cereals_dict
    cereals = get_cereals_dict()

    available_keys = [k for k, q in inventory_dict.items() if q > 0]
    if not available_keys:
        return None

    # On calcule un score pour chaque céréale dispo
    scores = {}
    for key in available_keys:
        cereal = cereals.get(key)
        if not cereal:
            continue
        score = 0

        # -- Besoin de nourriture (Poids fort) --
        if pig.hunger < 40:
            score += cereal.get('hunger_restore', 0) * 1.5
        elif pig.hunger < 70:
            score += cereal.get('hunger_restore', 0) * 0.5

        # -- Besoin d'énergie --
        if pig.energy < 40:
            score += cereal.get('energy_restore', 0) * 2.0
        elif pig.energy < 70:
            score += cereal.get('energy_restore', 0) * 0.8

        # -- Boosts de statistiques (Cœur de la logique demandée) --
        # On valorise plus les boosts sur les stats où le cochon est faible.
        c_stats = cereal.get('stats', {})
        for s_key, s_boost in c_stats.items():
            if s_boost <= 0:
                continue
            
            p_val = getattr(pig, s_key, 50.0)
            # Poids multiplicateur : plus la stat est faible, plus le boost vaut de points.
            # Base 100, on divise pour avoir un multiplicateur entre ~1 et ~10
            stat_weight = max(1, (100 - p_val) / 10.0)
            
            # Bonus spécifique pour le moral car c'est une stat de "forme"
            if s_key == 'moral':
                stat_weight *= 1.2
            
            score += (s_boost * stat_weight * 8)

        scores[key] = score

    if not scores:
        best_key = available_keys[0] # Fallback simple
    else:
        best_key = max(scores, key=scores.get)
        
    res = cereals[best_key].copy()
    res['key'] = best_key
    return res
