"""RaceEngineSettings — paramètres du moteur de course stockés en DB.

Toutes les constantes RACE_* de data.py sont regroupées dans un JSON blob
sous la clé 'race_engine_config'. Les valeurs de data.py servent de fallback
si la clé n'existe pas en base.
"""
import json
from dataclasses import dataclass, asdict

from data import (
    RACE_MAX_TURNS,
    RACE_ATTACK_THRESHOLD, RACE_NEUTRAL_MAX,
    RACE_STRATEGY_ECONOMY_MIN_MULT, RACE_STRATEGY_ATTACK_MAX_MULT,
    RACE_STRATEGY_ECONOMY_RECOVERY, RACE_STRATEGY_NEUTRAL_FATIGUE,
    RACE_ATTACK_FATIGUE_EXPONENT,
    RACE_BASE_SPEED_CONSTANT,
    RACE_MIN_FINAL_SPEED, RACE_SEGMENT_SPEED_CAP,
    RACE_VIRAGE_SPEED_CAP, RACE_BOUE_SPEED_CAP,
    RACE_FATIGUE_SPEED_PENALTY_FLOOR, RACE_FATIGUE_SPEED_PENALTY_DIVISOR,
    RACE_ENDURANCE_FATIGUE_DIVISOR, RACE_RECENT_RACE_PENALTY_FLOOR,
    RACE_MONTEE_SPEED_MULT, RACE_MONTEE_FORCE_MULT, RACE_MONTEE_TERRAIN_MOD,
    RACE_DESCENTE_SPEED_MULT, RACE_DESCENTE_TERRAIN_MOD,
    RACE_DESCENTE_AGI_RISK_REDUCTION,
    RACE_STUMBLE_BASE_CHANCE_DESCENTE, RACE_STUMBLE_SPEED_MULT,
    RACE_STUMBLE_BASE_CHANCE_VIRAGE,
    RACE_VIRAGE_AGI_MULT, RACE_VIRAGE_TERRAIN_MOD,
    RACE_BOUE_AGI_MULT, RACE_BOUE_TERRAIN_MOD,
    RACE_DRAFT_MIN_DIST, RACE_DRAFT_MAX_DIST,
    RACE_DRAFT_BONUS_MIN, RACE_DRAFT_BONUS_MAX,
    RACE_DRAFT_NO_FATIGUE_BONUS, RACE_FATIGUE_HEADWIND_PENALTY,
    RACE_VARIANCE_MIN, RACE_VARIANCE_MAX,
)


@dataclass(frozen=True)
class RaceEngineSettings:
    max_turns: int
    attack_threshold: int
    neutral_max: int
    strategy_economy_min_mult: float
    strategy_attack_max_mult: float
    strategy_economy_recovery: float
    strategy_neutral_fatigue: float
    attack_fatigue_exponent: float
    base_speed_constant: float
    min_final_speed: float
    segment_speed_cap: float
    virage_speed_cap: float
    boue_speed_cap: float
    fatigue_speed_penalty_floor: float
    fatigue_speed_penalty_divisor: float
    endurance_fatigue_divisor: float
    recent_race_penalty_floor: float
    montee_speed_mult: float
    montee_force_mult: float
    montee_terrain_mod: float
    descente_speed_mult: float
    descente_terrain_mod: float
    descente_agi_risk_reduction: float
    stumble_base_chance_descente: float
    stumble_speed_mult: float
    stumble_base_chance_virage: float
    virage_agi_mult: float
    virage_terrain_mod: float
    boue_agi_mult: float
    boue_terrain_mod: float
    draft_min_dist: float
    draft_max_dist: float
    draft_bonus_min: float
    draft_bonus_max: float
    draft_no_fatigue_bonus: float
    fatigue_headwind_penalty: float
    variance_min: float
    variance_max: float

    @classmethod
    def defaults(cls) -> 'RaceEngineSettings':
        return cls(
            max_turns=RACE_MAX_TURNS,
            attack_threshold=RACE_ATTACK_THRESHOLD,
            neutral_max=RACE_NEUTRAL_MAX,
            strategy_economy_min_mult=RACE_STRATEGY_ECONOMY_MIN_MULT,
            strategy_attack_max_mult=RACE_STRATEGY_ATTACK_MAX_MULT,
            strategy_economy_recovery=RACE_STRATEGY_ECONOMY_RECOVERY,
            strategy_neutral_fatigue=RACE_STRATEGY_NEUTRAL_FATIGUE,
            attack_fatigue_exponent=RACE_ATTACK_FATIGUE_EXPONENT,
            base_speed_constant=RACE_BASE_SPEED_CONSTANT,
            min_final_speed=RACE_MIN_FINAL_SPEED,
            segment_speed_cap=RACE_SEGMENT_SPEED_CAP,
            virage_speed_cap=RACE_VIRAGE_SPEED_CAP,
            boue_speed_cap=RACE_BOUE_SPEED_CAP,
            fatigue_speed_penalty_floor=RACE_FATIGUE_SPEED_PENALTY_FLOOR,
            fatigue_speed_penalty_divisor=RACE_FATIGUE_SPEED_PENALTY_DIVISOR,
            endurance_fatigue_divisor=RACE_ENDURANCE_FATIGUE_DIVISOR,
            recent_race_penalty_floor=RACE_RECENT_RACE_PENALTY_FLOOR,
            montee_speed_mult=RACE_MONTEE_SPEED_MULT,
            montee_force_mult=RACE_MONTEE_FORCE_MULT,
            montee_terrain_mod=RACE_MONTEE_TERRAIN_MOD,
            descente_speed_mult=RACE_DESCENTE_SPEED_MULT,
            descente_terrain_mod=RACE_DESCENTE_TERRAIN_MOD,
            descente_agi_risk_reduction=RACE_DESCENTE_AGI_RISK_REDUCTION,
            stumble_base_chance_descente=RACE_STUMBLE_BASE_CHANCE_DESCENTE,
            stumble_speed_mult=RACE_STUMBLE_SPEED_MULT,
            stumble_base_chance_virage=RACE_STUMBLE_BASE_CHANCE_VIRAGE,
            virage_agi_mult=RACE_VIRAGE_AGI_MULT,
            virage_terrain_mod=RACE_VIRAGE_TERRAIN_MOD,
            boue_agi_mult=RACE_BOUE_AGI_MULT,
            boue_terrain_mod=RACE_BOUE_TERRAIN_MOD,
            draft_min_dist=RACE_DRAFT_MIN_DIST,
            draft_max_dist=RACE_DRAFT_MAX_DIST,
            draft_bonus_min=RACE_DRAFT_BONUS_MIN,
            draft_bonus_max=RACE_DRAFT_BONUS_MAX,
            draft_no_fatigue_bonus=RACE_DRAFT_NO_FATIGUE_BONUS,
            fatigue_headwind_penalty=RACE_FATIGUE_HEADWIND_PENALTY,
            variance_min=RACE_VARIANCE_MIN,
            variance_max=RACE_VARIANCE_MAX,
        )

    @classmethod
    def load(cls) -> 'RaceEngineSettings':
        from helpers.config import get_config

        raw = get_config('race_engine_config', '')
        if not raw:
            return cls.defaults()
        try:
            d = json.loads(raw)
        except (TypeError, ValueError):
            return cls.defaults()
        if not isinstance(d, dict):
            return cls.defaults()
        defaults = cls.defaults()

        def _f(key, default):
            try:
                return float(d.get(key, default))
            except (TypeError, ValueError):
                return float(default)

        def _i(key, default):
            try:
                return int(float(d.get(key, default)))
            except (TypeError, ValueError):
                return int(default)

        return cls(
            max_turns=_i('max_turns', defaults.max_turns),
            attack_threshold=_i('attack_threshold', defaults.attack_threshold),
            neutral_max=_i('neutral_max', defaults.neutral_max),
            strategy_economy_min_mult=_f('strategy_economy_min_mult', defaults.strategy_economy_min_mult),
            strategy_attack_max_mult=_f('strategy_attack_max_mult', defaults.strategy_attack_max_mult),
            strategy_economy_recovery=_f('strategy_economy_recovery', defaults.strategy_economy_recovery),
            strategy_neutral_fatigue=_f('strategy_neutral_fatigue', defaults.strategy_neutral_fatigue),
            attack_fatigue_exponent=_f('attack_fatigue_exponent', defaults.attack_fatigue_exponent),
            base_speed_constant=_f('base_speed_constant', defaults.base_speed_constant),
            min_final_speed=_f('min_final_speed', defaults.min_final_speed),
            segment_speed_cap=_f('segment_speed_cap', defaults.segment_speed_cap),
            virage_speed_cap=_f('virage_speed_cap', defaults.virage_speed_cap),
            boue_speed_cap=_f('boue_speed_cap', defaults.boue_speed_cap),
            fatigue_speed_penalty_floor=_f('fatigue_speed_penalty_floor', defaults.fatigue_speed_penalty_floor),
            fatigue_speed_penalty_divisor=_f('fatigue_speed_penalty_divisor', defaults.fatigue_speed_penalty_divisor),
            endurance_fatigue_divisor=_f('endurance_fatigue_divisor', defaults.endurance_fatigue_divisor),
            recent_race_penalty_floor=_f('recent_race_penalty_floor', defaults.recent_race_penalty_floor),
            montee_speed_mult=_f('montee_speed_mult', defaults.montee_speed_mult),
            montee_force_mult=_f('montee_force_mult', defaults.montee_force_mult),
            montee_terrain_mod=_f('montee_terrain_mod', defaults.montee_terrain_mod),
            descente_speed_mult=_f('descente_speed_mult', defaults.descente_speed_mult),
            descente_terrain_mod=_f('descente_terrain_mod', defaults.descente_terrain_mod),
            descente_agi_risk_reduction=_f('descente_agi_risk_reduction', defaults.descente_agi_risk_reduction),
            stumble_base_chance_descente=_f('stumble_base_chance_descente', defaults.stumble_base_chance_descente),
            stumble_speed_mult=_f('stumble_speed_mult', defaults.stumble_speed_mult),
            stumble_base_chance_virage=_f('stumble_base_chance_virage', defaults.stumble_base_chance_virage),
            virage_agi_mult=_f('virage_agi_mult', defaults.virage_agi_mult),
            virage_terrain_mod=_f('virage_terrain_mod', defaults.virage_terrain_mod),
            boue_agi_mult=_f('boue_agi_mult', defaults.boue_agi_mult),
            boue_terrain_mod=_f('boue_terrain_mod', defaults.boue_terrain_mod),
            draft_min_dist=_f('draft_min_dist', defaults.draft_min_dist),
            draft_max_dist=_f('draft_max_dist', defaults.draft_max_dist),
            draft_bonus_min=_f('draft_bonus_min', defaults.draft_bonus_min),
            draft_bonus_max=_f('draft_bonus_max', defaults.draft_bonus_max),
            draft_no_fatigue_bonus=_f('draft_no_fatigue_bonus', defaults.draft_no_fatigue_bonus),
            fatigue_headwind_penalty=_f('fatigue_headwind_penalty', defaults.fatigue_headwind_penalty),
            variance_min=_f('variance_min', defaults.variance_min),
            variance_max=_f('variance_max', defaults.variance_max),
        )

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def get_race_engine_settings() -> RaceEngineSettings:
    return RaceEngineSettings.load()


def save_race_engine_settings(settings: RaceEngineSettings):
    from helpers.config import set_config
    set_config('race_engine_config', settings.to_json())


def reset_race_engine_settings():
    """Réinitialise le moteur aux valeurs par défaut de data.py."""
    save_race_engine_settings(RaceEngineSettings.defaults())
