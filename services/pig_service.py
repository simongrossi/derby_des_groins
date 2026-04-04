from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math
import random

from flask import current_app, has_app_context

from data import (
    CHARCUTERIE, CHARCUTERIE_PREMIUM, DEFAULT_PIG_WEIGHT_KG, EPITAPHS, FRESHNESS_BONUS_HOURS,
    FRESHNESS_MORAL_BONUS, IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO,
    MAX_INJURY_RISK, MAX_PIG_SLOTS, MAX_PIG_WEIGHT_KG, MAX_WEIGHT_PERFORMANCE_MALUS,
    MIN_INJURY_RISK, MIN_PIG_WEIGHT_KG, PIG_EMOJIS, PIG_ORIGINS,
    PRELOADED_PIG_NAMES, RETIREMENT_HERITAGE_MIN_WINS, SCHOOL_XP_DECAY_FLOOR,
    SCHOOL_XP_DECAY_THRESHOLDS, VET_RESPONSE_MINUTES,
)
from exceptions import PigNotFoundError, PigTiredError


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
        weight_default_kg=_f('pig_weight_default_kg', DEFAULT_PIG_WEIGHT_KG),
        weight_min_kg=_f('pig_weight_min_kg', MIN_PIG_WEIGHT_KG),
        weight_max_kg=_f('pig_weight_max_kg', MAX_PIG_WEIGHT_KG),
        weight_malus_ratio=_f('pig_weight_malus_ratio', IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO),
        weight_malus_max=_f('pig_weight_malus_max', MAX_WEIGHT_PERFORMANCE_MALUS),
        injury_min_risk=_f('pig_injury_min_risk', MIN_INJURY_RISK),
        injury_max_risk=_f('pig_injury_max_risk', MAX_INJURY_RISK),
        vet_response_minutes=_i('pig_vet_response_minutes', VET_RESPONSE_MINUTES),
    )


from extensions import db
from models import Auction, Participant, Pig, Race, Trophy
from services.economy_service import (
    calculate_adoption_cost_for_counts,
    get_feeding_multiplier_for_count,
    get_level_happiness_bonus_value,
    get_progression_settings,
    scale_stat_gains,
    xp_for_level_value,
)

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
    months_alive = max(0, (datetime.utcnow() - pig.created_at).days // 30)
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
    if pig.created_at and (datetime.utcnow() - pig.created_at).days >= 30:
        Trophy.award(
            user_id=pig.owner.id,
            code='office_elder',
            label="L'Ancien du Bureau",
            emoji='🗄️',
            description='Un cochon a tenu plus de 30 jours reels avant son post-mortem.',
            pig_name=pig.name,
        )
    if pig.created_at and (datetime.utcnow() - pig.created_at).days >= 90:
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
    if (pig.school_sessions_completed or 0) > 20:
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
    if (pig.hunger or 0) >= 95:
        raise PigTiredError("Ton cochon n'a plus faim !")

    pig.hunger = min(100, float(pig.hunger or 0.0) + cereal['hunger_restore'])
    pig.energy = min(100, float(pig.energy or 0.0) + cereal.get('energy_restore', 0))
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
    pig.energy = max(0, min(100, float(pig.energy or 0.0) - training['energy_cost']))
    pig.hunger = max(0, float(pig.hunger or 0.0) - training.get('hunger_cost', 0))
    adjust_pig_weight(pig, training.get('weight_delta', 0.0))
    if 'happiness_bonus' in training:
        pig.happiness = min(
            100,
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

    pig.energy = max(0, float(pig.energy or 0.0) - lesson['energy_cost'])
    pig.hunger = max(0, float(pig.hunger or 0.0) - lesson['hunger_cost'])
    pig.last_school_at = datetime.utcnow()
    pig.school_sessions_completed = (pig.school_sessions_completed or 0) + 1

    if correct:
        pig.apply_stat_boosts(
            scale_stat_gains(lesson.get('stats', {}), progression.school_stat_gain_multiplier * decay)
        )
        pig.xp = int(pig.xp or 0) + int(round(lesson['xp'] * progression.school_xp_multiplier * decay))
        pig.happiness = min(
            100,
            float(pig.happiness or 0.0) + (lesson.get('happiness_bonus', 0) * progression.school_happiness_multiplier),
        )
        category = 'success'
    else:
        pig.xp = int(pig.xp or 0) + int(round(lesson.get('wrong_xp', 0) * progression.school_wrong_xp_multiplier * decay))
        pig.happiness = max(
            0,
            float(pig.happiness or 0.0) - (lesson.get('wrong_happiness_penalty', 0) * progression.school_wrong_happiness_multiplier),
        )
        category = 'warning'

    pig.register_positive_interaction(datetime.utcnow())
    pig.mark_bad_state_if_needed()
    check_level_up(pig)
    if commit:
        db.session.commit()
    return category


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
    min_commit_interval = 60
    if has_app_context():
        min_commit_interval = current_app.config.get('PIG_VITALS_COMMIT_INTERVAL_SECONDS', 60)

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
            pig.freshness = max(0.0, 100.0 - (elapsed_workdays * progression.freshness_decay_per_workday))
        else:
            pig.freshness = 100.0

    pig.hunger = max(0, pig.hunger - (hours * progression.hunger_decay_per_hour))
    if pig.hunger > progression.energy_regen_hunger_threshold:
        pig.energy = min(100, pig.energy + (hours * progression.energy_regen_per_hour))
    else:
        pig.energy = max(0, pig.energy - (hours * progression.energy_drain_per_hour))

    if pig.hunger < 15:
        pig.happiness = max(0, pig.happiness - (hours * progression.low_hunger_happiness_drain_per_hour))
    elif pig.hunger < 30:
        pig.happiness = max(0, pig.happiness - (hours * progression.mid_hunger_happiness_drain_per_hour))
    elif pig.happiness < progression.passive_happiness_regen_cap:
        pig.happiness = min(
            progression.passive_happiness_regen_cap,
            pig.happiness + (hours * progression.passive_happiness_regen_per_hour),
        )

    current_weight = pig.weight_kg or DEFAULT_PIG_WEIGHT_KG
    if pig.hunger < 25:
        pig.weight_kg = clamp_pig_weight(current_weight - hours * 0.25)
    elif pig.hunger > 75 and pig.energy < 45:
        pig.weight_kg = clamp_pig_weight(current_weight + hours * 0.18)
    elif pig.energy > 80 and pig.hunger < 60:
        pig.weight_kg = clamp_pig_weight(current_weight - hours * 0.08)

    pig.mark_bad_state_if_needed()
    pig.last_updated = now
    if force_commit or elapsed_seconds >= min_commit_interval:
        db.session.commit()
    return pig


def get_freshness_bonus(pig):
    freshness_value = max(0.0, min(100.0, float(getattr(pig, 'freshness', 100.0) or 100.0))) if pig else 100.0
    return {
        'active': freshness_value >= 95.0,
        'multiplier': 1.0,
        'bonus_percent': 0.0,
        'hours_remaining': 0.0,
        'value': round(freshness_value, 1),
    }


def clamp_pig_weight(weight):
    ps = get_pig_settings()
    return round(min(ps.weight_max_kg, max(ps.weight_min_kg, weight)), 1)


def get_weight_stat(source, stat_name, default=10.0):
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

    target = 108.0 + (force * 0.22) + (endurance * 0.16) - (agilite * 0.10) - (vitesse * 0.05) + ((level - 1) * 0.35)
    return round(min(140.0, max(95.0, target)), 1)


def generate_weight_kg_for_profile(source, level=None):
    ideal = calculate_target_weight_kg(source, level=level)
    return clamp_pig_weight(random.uniform(ideal - 7.0, ideal + 7.0))


def adjust_pig_weight(pig, delta):
    pig.weight_kg = clamp_pig_weight((pig.weight_kg or get_pig_settings().weight_default_kg) + delta)
    return pig.weight_kg


def get_weight_profile(pig):
    current_weight = clamp_pig_weight(pig.weight_kg or get_pig_settings().weight_default_kg)
    ideal_weight = calculate_target_weight_kg(pig)
    tolerance = round(10.0 + (pig.endurance * 0.08) + (pig.force * 0.04), 1)
    delta = round(current_weight - ideal_weight, 1)
    abs_delta = abs(delta)
    race_factor = max(0.82, min(1.06, 1.06 - ((abs_delta / max(tolerance * 2.2, 1.0)) * 0.24)))
    injury_factor = 1.0 + min(0.35, abs_delta / max(tolerance * 3.5, 1.0))

    force_mod = 1.0
    agilite_mod = 1.0
    if delta > 0:
        ratio = delta / max(tolerance, 1.0)
        force_mod = 1.0 + min(0.35, ratio * 0.12)
        agilite_mod = 1.0 - min(0.75, ratio * 0.25)
    elif delta < 0:
        ratio = abs(delta) / max(tolerance, 1.0)
        force_mod = 1.0 - min(0.25, ratio * 0.08)
        agilite_mod = 1.0 + min(0.15, ratio * 0.05)

    if abs_delta <= tolerance * 0.4:
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
        'score_pct': max(8, min(100, int((race_factor / 1.06) * 100))),
        'force_mod': round(force_mod, 2),
        'agilite_mod': round(agilite_mod, 2),
    }


def get_pig_performance_flags(pig):
    weight_profile = get_weight_profile(pig)
    ideal_weight = max(1.0, weight_profile['ideal_weight'])
    deviation_ratio = abs(weight_profile['current_weight'] - ideal_weight) / ideal_weight
    return {
        'hungry_penalty': (pig.hunger or 0) < 10,
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
    if (pig.hunger or 0) < 10:
        effective_force *= 0.7
        effective_endurance *= 0.7
    ps = get_pig_settings()
    ideal_weight = max(1.0, profile['ideal_weight'])
    deviation_ratio = abs(profile['current_weight'] - ideal_weight) / ideal_weight
    if deviation_ratio > ps.weight_malus_ratio:
        excess_ratio = deviation_ratio - ps.weight_malus_ratio
        penalty = min(ps.weight_malus_max, excess_ratio / ps.weight_malus_ratio * 0.2)
        modifier = 1.0 - penalty
        effective_vitesse *= modifier
        effective_agilite *= modifier
    effective_moral = pig.moral * freshness['multiplier']
    stats = [effective_vitesse, effective_endurance, effective_agilite, effective_force, pig.intelligence, effective_moral]
    stat_score = sum(math.sqrt(max(0.0, stat) / 100.0) * 100 for stat in stats) / len(stats)
    condition_factor = 0.8 + (((pig.energy + pig.hunger + pig.happiness) / 3.0) / 100.0) * 0.4
    return round(stat_score * condition_factor * profile['race_factor'], 2)


def xp_for_level(level):
    return xp_for_level_value(level)


def check_level_up(pig):
    while pig.xp >= xp_for_level(pig.level + 1):
        pig.level += 1
        pig.happiness = min(100, pig.happiness + get_level_happiness_bonus_value())


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
    rarity_bonus = {'commun': 0.0, 'rare': 0.5, 'epique': 1.0, 'legendaire': 2.0}.get(heritage.rarity, 0.0)
    return round((heritage.races_won * 0.6) + max(0, heritage.level - 1) * 0.08 + heritage.lineage_boost + rarity_bonus, 2)


def can_retire_into_heritage(pig):
    return bool(pig and pig.is_alive and not pig.retired_into_heritage and ((pig.races_won or 0) >= get_pig_settings().retirement_min_wins or (pig.rarity == 'legendaire')))


def retire_pig_into_heritage(user, pig):
    if not can_retire_into_heritage(pig):
        return 0.0
    bonus = max(1.0, round(get_pig_heritage_value(pig) * 0.35, 2))
    user.barn_heritage_bonus = round((user.barn_heritage_bonus or 0.0) + bonus, 2)
    pig.retired_into_heritage = True
    pig.lineage_boost = round((pig.lineage_boost or 0.0) + bonus, 2)
    lineage_name = get_lineage_label(pig)
    related_pigs = Pig.query.filter(Pig.user_id == user.id, Pig.is_alive == True, Pig.id != pig.id, Pig.lineage_name == lineage_name).all()
    for descendant in related_pigs:
        descendant.lineage_boost = round((descendant.lineage_boost or 0.0) + bonus, 2)
        descendant.moral = min(100, (descendant.moral or 0.0) + min(4.0, bonus * 0.4))
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
    base_value = getattr(pig, origin['bonus_stat']) or 10.0
    setattr(pig, origin['bonus_stat'], base_value + origin['bonus'])


def create_offspring(user, parent_a, parent_b, name=None):
    lineage_name = parent_a.lineage_name or parent_b.lineage_name or f"Maison {user.username}"
    barn_bonus = user.barn_heritage_bonus or 0.0
    child = Pig(
        user_id=user.id,
        name=build_unique_pig_name(name or f"Porcelet {lineage_name}", fallback_prefix='Porcelet'),
        emoji=random.choice(PIG_EMOJIS),
        rarity=parent_a.rarity if parent_a.rarity == parent_b.rarity else random.choice([parent_a.rarity, parent_b.rarity, 'commun']),
        origin_country=random.choice([parent_a.origin_country, parent_b.origin_country]),
        origin_flag=random.choice([parent_a.origin_flag, parent_b.origin_flag]),
        lineage_name=lineage_name,
        generation=max(parent_a.generation or 1, parent_b.generation or 1) + 1,
        sire_id=parent_a.id,
        dam_id=parent_b.id,
        lineage_boost=round(((parent_a.lineage_boost or 0.0) + (parent_b.lineage_boost or 0.0)) * 0.35 + (barn_bonus * 0.25), 2),
    )
    for stat in ['vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral']:
        base = (getattr(parent_a, stat, 10.0) + getattr(parent_b, stat, 10.0)) / 2
        inherited = base * 0.82 + random.uniform(-2.5, 2.5) + child.lineage_boost
        setattr(child, stat, round(min(100, max(8, inherited)), 1))
    child.energy = 78
    child.hunger = 70
    child.happiness = min(100, round(72 + (barn_bonus * 0.4), 1))
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
        pig = Pig(user_id=admin_user.id, name=pig_name, emoji=PIG_EMOJIS[index % len(PIG_EMOJIS)], origin_country=origin['country'], origin_flag=origin['flag'], lineage_name='Maison Admin')
        apply_origin_bonus(pig, origin)
        pig.weight_kg = generate_weight_kg_for_profile(pig)
        db.session.add(pig)
        created += 1
    return created
