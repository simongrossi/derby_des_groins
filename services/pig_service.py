from dataclasses import dataclass
from datetime import datetime
import math
import random

from data import (
    DEFAULT_PIG_WEIGHT_KG, FEEDING_PRESSURE_PER_PIG, FRESHNESS_BONUS_HOURS,
    FRESHNESS_MORAL_BONUS, IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO,
    MAX_INJURY_RISK, MAX_PIG_SLOTS, MAX_PIG_WEIGHT_KG, MAX_WEIGHT_PERFORMANCE_MALUS,
    MIN_INJURY_RISK, MIN_PIG_WEIGHT_KG, PIG_EMOJIS, PIG_ORIGINS,
    PRELOADED_PIG_NAMES, REPLACEMENT_PIG_COST, RETIREMENT_HERITAGE_MIN_WINS,
    SECOND_PIG_COST,
)
from extensions import db
from models import Auction, Pig

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
    return round(min(MAX_PIG_WEIGHT_KG, max(MIN_PIG_WEIGHT_KG, weight)), 1)


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
    pig.weight_kg = clamp_pig_weight((pig.weight_kg or DEFAULT_PIG_WEIGHT_KG) + delta)
    return pig.weight_kg


def get_weight_profile(pig):
    current_weight = clamp_pig_weight(pig.weight_kg or DEFAULT_PIG_WEIGHT_KG)
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
        'weight_penalty': deviation_ratio > IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO,
        'weight_status': weight_profile['status'],
    }


def update_pig_state(pig):
    now = datetime.utcnow()
    if not pig.last_updated:
        pig.last_updated = now
        return
    elapsed_hours = (now - pig.last_updated).total_seconds() / 3600
    if elapsed_hours < 0.01:
        return
    truce_hours = calculate_weekend_truce_hours(pig.last_updated, now)
    hours = max(0.0, elapsed_hours - truce_hours)
    hours = min(hours, 24)
    if hours < 0.01:
        pig.last_updated = now
        db.session.commit()
        return
    pig.hunger = max(0, pig.hunger - hours * 2)
    if pig.hunger > 30:
        pig.energy = min(100, pig.energy + hours * 5)
    else:
        pig.energy = max(0, pig.energy - hours * 1)
    if pig.hunger < 15:
        pig.happiness = max(0, pig.happiness - hours * 3)
    elif pig.hunger < 30:
        pig.happiness = max(0, pig.happiness - hours * 1)
    elif pig.happiness < 60:
        pig.happiness = min(60, pig.happiness + hours * 0.3)
    current_weight = pig.weight_kg or DEFAULT_PIG_WEIGHT_KG
    if pig.hunger < 25:
        pig.weight_kg = clamp_pig_weight(current_weight - hours * 0.25)
    elif pig.hunger > 75 and pig.energy < 45:
        pig.weight_kg = clamp_pig_weight(current_weight + hours * 0.18)
    elif pig.energy > 80 and pig.hunger < 60:
        pig.weight_kg = clamp_pig_weight(current_weight - hours * 0.08)
    pig.last_updated = now
    db.session.commit()


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
    ideal_weight = max(1.0, profile['ideal_weight'])
    deviation_ratio = abs(profile['current_weight'] - ideal_weight) / ideal_weight
    if deviation_ratio > IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO:
        excess_ratio = deviation_ratio - IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO
        penalty = min(MAX_WEIGHT_PERFORMANCE_MALUS, excess_ratio / IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO * 0.2)
        modifier = 1.0 - penalty
        effective_vitesse *= modifier
        effective_agilite *= modifier
    effective_moral = pig.moral * freshness['multiplier']
    stats = [effective_vitesse, effective_endurance, effective_agilite, effective_force, pig.intelligence, effective_moral]
    stat_score = sum(math.sqrt(max(0.0, stat) / 100.0) * 100 for stat in stats) / len(stats)
    condition_factor = 0.8 + (((pig.energy + pig.hunger + pig.happiness) / 3.0) / 100.0) * 0.4
    return round(stat_score * condition_factor * profile['race_factor'], 2)


def xp_for_level(level):
    return int(100 * (level ** 1.5))


def check_level_up(pig):
    while pig.xp >= xp_for_level(pig.level + 1):
        pig.level += 1
        pig.happiness = min(100, pig.happiness + 10)


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
    return MAX_PIG_SLOTS


def get_adoption_cost(user):
    slot_count = get_pig_slot_count(user)
    if slot_count >= get_max_pig_slots(user):
        return None
    active_count = Pig.query.filter_by(user_id=user.id, is_alive=True).count()
    if active_count == 0:
        return REPLACEMENT_PIG_COST
    return SECOND_PIG_COST + max(0, active_count - 1) * 15.0


def get_feeding_cost_multiplier(user):
    active_count = Pig.query.filter_by(user_id=user.id, is_alive=True).count()
    if active_count <= 1:
        return 1.0
    return round(1.0 + ((active_count - 1) * FEEDING_PRESSURE_PER_PIG), 2)


def get_lineage_label(pig):
    return pig.lineage_name or pig.name


def get_pig_heritage_value(pig):
    heritage = PigHeritageSnapshot.from_source(pig)
    rarity_bonus = {'commun': 0.0, 'rare': 0.5, 'epique': 1.0, 'legendaire': 2.0}.get(heritage.rarity, 0.0)
    return round((heritage.races_won * 0.6) + max(0, heritage.level - 1) * 0.08 + heritage.lineage_boost + rarity_bonus, 2)


def can_retire_into_heritage(pig):
    return bool(pig and pig.is_alive and not pig.retired_into_heritage and ((pig.races_won or 0) >= RETIREMENT_HERITAGE_MIN_WINS or (pig.rarity == 'legendaire')))


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
    pig.retire()
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
