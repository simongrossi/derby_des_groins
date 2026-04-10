from dataclasses import dataclass
import json
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
    INJURY_RISK_DECAY_PER_HOUR,
    INJURY_RISK_GOOD_CARE_MULTIPLIER,
    INJURY_RISK_VET_REDUCTION,
    MAX_INJURY_RISK,
    MAX_PIG_WEIGHT_KG,
    MAX_WEIGHT_PERFORMANCE_MALUS,
    MIN_INJURY_RISK,
    MIN_PIG_WEIGHT_KG,
    VET_GRACE_MINUTES,
    VET_RESPONSE_MINUTES,
)
from services.economy_service import get_level_happiness_bonus_value, xp_for_level_value


@dataclass(frozen=True)
class PigSettings:
    max_slots: int
    retirement_min_wins: int
    default_max_races: int
    weight_default_kg: float
    weight_min_kg: float
    weight_max_kg: float
    weight_malus_ratio: float
    weight_malus_max: float
    injury_min_risk: float
    injury_max_risk: float
    injury_risk_decay_per_hour: float
    injury_risk_good_care_multiplier: float
    injury_risk_vet_reduction: float
    vet_response_minutes: int
    vet_grace_minutes: int
    weight_rules: 'PigWeightSettings'


@dataclass(frozen=True)
class PigWeightSettings:
    base_target_weight_kg: float
    target_force_factor: float
    target_endurance_factor: float
    target_agilite_factor: float
    target_vitesse_factor: float
    target_level_factor: float
    min_target_weight_kg: float
    max_target_weight_kg: float
    spawn_variation_kg: float
    base_tolerance_kg: float
    tolerance_endurance_factor: float
    tolerance_force_factor: float
    race_factor_floor: float
    race_factor_cap: float
    race_factor_base: float
    race_factor_window_multiplier: float
    race_factor_penalty_factor: float
    injury_factor_cap: float
    injury_factor_window_multiplier: float
    ideal_zone_ratio: float
    heavy_force_bonus_cap: float
    heavy_force_bonus_factor: float
    heavy_agilite_penalty_cap: float
    heavy_agilite_penalty_factor: float
    light_force_penalty_cap: float
    light_force_penalty_factor: float
    light_agilite_bonus_cap: float
    light_agilite_bonus_factor: float
    minimum_ratio_denominator: float
    score_floor_percent: int


def _coerce_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _coerce_int(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _load_weight_rules():
    from helpers.config import get_config

    raw = get_config('settings_pig_weight_rules', '')
    payload = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            parsed = {}
        if isinstance(parsed, dict):
            payload = parsed

    return PigWeightSettings(
        base_target_weight_kg=_coerce_float(payload.get('base_target_weight_kg'), PIG_WEIGHT_RULES.base_target_weight_kg),
        target_force_factor=_coerce_float(payload.get('target_force_factor'), PIG_WEIGHT_RULES.target_force_factor),
        target_endurance_factor=_coerce_float(payload.get('target_endurance_factor'), PIG_WEIGHT_RULES.target_endurance_factor),
        target_agilite_factor=_coerce_float(payload.get('target_agilite_factor'), PIG_WEIGHT_RULES.target_agilite_factor),
        target_vitesse_factor=_coerce_float(payload.get('target_vitesse_factor'), PIG_WEIGHT_RULES.target_vitesse_factor),
        target_level_factor=_coerce_float(payload.get('target_level_factor'), PIG_WEIGHT_RULES.target_level_factor),
        min_target_weight_kg=_coerce_float(payload.get('min_target_weight_kg'), PIG_WEIGHT_RULES.min_target_weight_kg),
        max_target_weight_kg=_coerce_float(payload.get('max_target_weight_kg'), PIG_WEIGHT_RULES.max_target_weight_kg),
        spawn_variation_kg=_coerce_float(payload.get('spawn_variation_kg'), PIG_WEIGHT_RULES.spawn_variation_kg),
        base_tolerance_kg=_coerce_float(payload.get('base_tolerance_kg'), PIG_WEIGHT_RULES.base_tolerance_kg),
        tolerance_endurance_factor=_coerce_float(payload.get('tolerance_endurance_factor'), PIG_WEIGHT_RULES.tolerance_endurance_factor),
        tolerance_force_factor=_coerce_float(payload.get('tolerance_force_factor'), PIG_WEIGHT_RULES.tolerance_force_factor),
        race_factor_floor=_coerce_float(payload.get('race_factor_floor'), PIG_WEIGHT_RULES.race_factor_floor),
        race_factor_cap=_coerce_float(payload.get('race_factor_cap'), PIG_WEIGHT_RULES.race_factor_cap),
        race_factor_base=_coerce_float(payload.get('race_factor_base'), PIG_WEIGHT_RULES.race_factor_base),
        race_factor_window_multiplier=_coerce_float(payload.get('race_factor_window_multiplier'), PIG_WEIGHT_RULES.race_factor_window_multiplier),
        race_factor_penalty_factor=_coerce_float(payload.get('race_factor_penalty_factor'), PIG_WEIGHT_RULES.race_factor_penalty_factor),
        injury_factor_cap=_coerce_float(payload.get('injury_factor_cap'), PIG_WEIGHT_RULES.injury_factor_cap),
        injury_factor_window_multiplier=_coerce_float(payload.get('injury_factor_window_multiplier'), PIG_WEIGHT_RULES.injury_factor_window_multiplier),
        ideal_zone_ratio=_coerce_float(payload.get('ideal_zone_ratio'), PIG_WEIGHT_RULES.ideal_zone_ratio),
        heavy_force_bonus_cap=_coerce_float(payload.get('heavy_force_bonus_cap'), PIG_WEIGHT_RULES.heavy_force_bonus_cap),
        heavy_force_bonus_factor=_coerce_float(payload.get('heavy_force_bonus_factor'), PIG_WEIGHT_RULES.heavy_force_bonus_factor),
        heavy_agilite_penalty_cap=_coerce_float(payload.get('heavy_agilite_penalty_cap'), PIG_WEIGHT_RULES.heavy_agilite_penalty_cap),
        heavy_agilite_penalty_factor=_coerce_float(payload.get('heavy_agilite_penalty_factor'), PIG_WEIGHT_RULES.heavy_agilite_penalty_factor),
        light_force_penalty_cap=_coerce_float(payload.get('light_force_penalty_cap'), PIG_WEIGHT_RULES.light_force_penalty_cap),
        light_force_penalty_factor=_coerce_float(payload.get('light_force_penalty_factor'), PIG_WEIGHT_RULES.light_force_penalty_factor),
        light_agilite_bonus_cap=_coerce_float(payload.get('light_agilite_bonus_cap'), PIG_WEIGHT_RULES.light_agilite_bonus_cap),
        light_agilite_bonus_factor=_coerce_float(payload.get('light_agilite_bonus_factor'), PIG_WEIGHT_RULES.light_agilite_bonus_factor),
        minimum_ratio_denominator=_coerce_float(payload.get('minimum_ratio_denominator'), PIG_WEIGHT_RULES.minimum_ratio_denominator),
        score_floor_percent=_coerce_int(payload.get('score_floor_percent'), PIG_WEIGHT_RULES.score_floor_percent),
    )


def get_pig_settings():
    from helpers.config import get_config

    return PigSettings(
        max_slots=_coerce_int(get_config('pig_max_slots', str(MAX_PIG_SLOTS)), MAX_PIG_SLOTS),
        retirement_min_wins=_coerce_int(get_config('pig_retirement_min_wins', str(RETIREMENT_HERITAGE_MIN_WINS)), RETIREMENT_HERITAGE_MIN_WINS),
        default_max_races=_coerce_int(get_config('pig_default_max_races', str(PIG_DEFAULTS.max_races)), PIG_DEFAULTS.max_races),
        weight_default_kg=_coerce_float(get_config('pig_weight_default_kg', PIG_DEFAULTS.weight_kg), PIG_DEFAULTS.weight_kg),
        weight_min_kg=_coerce_float(get_config('pig_weight_min_kg', MIN_PIG_WEIGHT_KG), MIN_PIG_WEIGHT_KG),
        weight_max_kg=_coerce_float(get_config('pig_weight_max_kg', MAX_PIG_WEIGHT_KG), MAX_PIG_WEIGHT_KG),
        weight_malus_ratio=_coerce_float(get_config('pig_weight_malus_ratio', IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO), IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO),
        weight_malus_max=_coerce_float(get_config('pig_weight_malus_max', MAX_WEIGHT_PERFORMANCE_MALUS), MAX_WEIGHT_PERFORMANCE_MALUS),
        injury_min_risk=_coerce_float(get_config('pig_injury_min_risk', MIN_INJURY_RISK), MIN_INJURY_RISK),
        injury_max_risk=_coerce_float(get_config('pig_injury_max_risk', MAX_INJURY_RISK), MAX_INJURY_RISK),
        injury_risk_decay_per_hour=_coerce_float(get_config('pig_injury_risk_decay_per_hour', INJURY_RISK_DECAY_PER_HOUR), INJURY_RISK_DECAY_PER_HOUR),
        injury_risk_good_care_multiplier=_coerce_float(get_config('pig_injury_risk_good_care_multiplier', INJURY_RISK_GOOD_CARE_MULTIPLIER), INJURY_RISK_GOOD_CARE_MULTIPLIER),
        injury_risk_vet_reduction=_coerce_float(get_config('pig_injury_risk_vet_reduction', INJURY_RISK_VET_REDUCTION), INJURY_RISK_VET_REDUCTION),
        vet_response_minutes=_coerce_int(get_config('pig_vet_response_minutes', str(VET_RESPONSE_MINUTES)), VET_RESPONSE_MINUTES),
        vet_grace_minutes=_coerce_int(get_config('pig_vet_grace_minutes', str(VET_GRACE_MINUTES)), VET_GRACE_MINUTES),
        weight_rules=_load_weight_rules(),
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
    wr = get_pig_settings().weight_rules
    force = get_weight_stat(source, 'force')
    endurance = get_weight_stat(source, 'endurance')
    agilite = get_weight_stat(source, 'agilite')
    vitesse = get_weight_stat(source, 'vitesse')
    if level is None:
        level = source.get('level', 1) if isinstance(source, dict) else getattr(source, 'level', 1)
    level = max(1, int(level or 1))

    target = (
        wr.base_target_weight_kg
        + (force * wr.target_force_factor)
        + (endurance * wr.target_endurance_factor)
        - (agilite * wr.target_agilite_factor)
        - (vitesse * wr.target_vitesse_factor)
        + ((level - 1) * wr.target_level_factor)
    )
    return round(
        min(wr.max_target_weight_kg, max(wr.min_target_weight_kg, target)),
        1,
    )


def generate_weight_kg_for_profile(source, level=None):
    wr = get_pig_settings().weight_rules
    ideal = calculate_target_weight_kg(source, level=level)
    return clamp_pig_weight(
        random.uniform(
            ideal - wr.spawn_variation_kg,
            ideal + wr.spawn_variation_kg,
        )
    )


def adjust_pig_weight(pig, delta):
    pig.weight_kg = clamp_pig_weight((pig.weight_kg or get_pig_settings().weight_default_kg) + delta)
    return pig.weight_kg


def get_weight_profile(pig):
    wr = get_pig_settings().weight_rules
    current_weight = clamp_pig_weight(pig.weight_kg or get_pig_settings().weight_default_kg)
    ideal_weight = calculate_target_weight_kg(pig)
    tolerance = round(
        wr.base_tolerance_kg
        + (pig.endurance * wr.tolerance_endurance_factor)
        + (pig.force * wr.tolerance_force_factor),
        1,
    )
    delta = round(current_weight - ideal_weight, 1)
    abs_delta = abs(delta)
    race_factor = max(
        wr.race_factor_floor,
        min(
            wr.race_factor_cap,
            wr.race_factor_base
            - (
                (
                    abs_delta
                    / max(
                        tolerance * wr.race_factor_window_multiplier,
                        wr.minimum_ratio_denominator,
                    )
                )
                * wr.race_factor_penalty_factor
            ),
        ),
    )
    injury_factor = 1.0 + min(
        wr.injury_factor_cap,
        abs_delta / max(
            tolerance * wr.injury_factor_window_multiplier,
            wr.minimum_ratio_denominator,
        ),
    )

    force_mod = 1.0
    agilite_mod = 1.0
    if delta > 0:
        ratio = delta / max(tolerance, wr.minimum_ratio_denominator)
        force_mod = 1.0 + min(wr.heavy_force_bonus_cap, ratio * wr.heavy_force_bonus_factor)
        agilite_mod = 1.0 - min(wr.heavy_agilite_penalty_cap, ratio * wr.heavy_agilite_penalty_factor)
    elif delta < 0:
        ratio = abs(delta) / max(tolerance, wr.minimum_ratio_denominator)
        force_mod = 1.0 - min(wr.light_force_penalty_cap, ratio * wr.light_force_penalty_factor)
        agilite_mod = 1.0 + min(wr.light_agilite_bonus_cap, ratio * wr.light_agilite_bonus_factor)

    if abs_delta <= tolerance * wr.ideal_zone_ratio:
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
            wr.score_floor_percent,
            min(PIG_LIMITS.max_value, int((race_factor / wr.race_factor_cap) * 100)),
        ),
        'force_mod': round(force_mod, 2),
        'agilite_mod': round(agilite_mod, 2),
    }


def get_pig_performance_flags(pig):
    weight_profile = get_weight_profile(pig)
    ideal_weight = max(get_pig_settings().weight_rules.minimum_ratio_denominator, weight_profile['ideal_weight'])
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
    ideal_weight = max(ps.weight_rules.minimum_ratio_denominator, profile['ideal_weight'])
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
