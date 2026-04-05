from dataclasses import dataclass
import math
import random

from config.game_rules import (
    PIG_DEFAULTS,
    PIG_INTERACTION_RULES,
    PIG_LIMITS,
    PIG_POWER_RULES,
    PIG_WEIGHT_RULES,
)
from config.economy_defaults import MAX_PIG_SLOTS, RETIREMENT_HERITAGE_MIN_WINS
from config.gameplay_defaults import (
    IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO,
    MAX_INJURY_RISK,
    MAX_PIG_WEIGHT_KG,
    MAX_WEIGHT_PERFORMANCE_MALUS,
    MIN_INJURY_RISK,
    MIN_PIG_WEIGHT_KG,
    VET_RESPONSE_MINUTES,
)
from services.economy_service import get_level_happiness_bonus_value, xp_for_level_value


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


def get_freshness_bonus(pig):
    freshness_value = (
        max(
            PIG_LIMITS.min_value,
            min(
                PIG_LIMITS.max_value,
                float(getattr(pig, 'freshness', PIG_DEFAULTS.freshness) or PIG_DEFAULTS.freshness),
            ),
        )
        if pig
        else PIG_DEFAULTS.freshness
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
        penalty = min(
            ps.weight_malus_max,
            excess_ratio / ps.weight_malus_ratio * PIG_POWER_RULES.excess_weight_penalty_scale,
        )
        modifier = 1.0 - penalty
        effective_vitesse *= modifier
        effective_agilite *= modifier
    effective_moral = pig.moral * freshness['multiplier']
    stats = [
        effective_vitesse,
        effective_endurance,
        effective_agilite,
        effective_force,
        pig.intelligence,
        effective_moral,
    ]
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
