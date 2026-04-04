from dataclasses import dataclass, field


@dataclass(frozen=True)
class PigLimitRules:
    """Shared caps for pig stats and Tamagotchi gauges."""

    min_value: float = 0.0
    max_value: float = 100.0


@dataclass(frozen=True)
class PigDefaults:
    """Default values used when a new pig is created."""

    stat: float = 10.0
    energy: float = 80.0
    hunger: float = 60.0
    happiness: float = 70.0
    weight_kg: float = 112.0
    freshness: float = 100.0
    max_races: int = 80
    injury_risk: float = 4.0


@dataclass(frozen=True)
class PigInteractionRules:
    """Thresholds used by simple pig state transitions."""

    comeback_bonus_idle_hours: int = 12
    bad_state_hunger_threshold: float = 20.0
    bad_state_energy_threshold: float = 20.0
    feed_block_hunger_threshold: float = 95.0
    freshness_bonus_threshold: float = 95.0
    race_ready_energy_threshold: float = 20.0
    race_ready_hunger_threshold: float = 20.0


@dataclass(frozen=True)
class PigVitalsRules:
    """Rules controlling passive Tamagotchi decay over time."""

    min_commit_interval_seconds: int = 60
    low_hunger_threshold: float = 15.0
    mid_hunger_threshold: float = 30.0
    weight_loss_hunger_threshold: float = 25.0
    weight_gain_hunger_threshold: float = 75.0
    weight_gain_low_energy_threshold: float = 45.0
    weight_loss_high_energy_threshold: float = 80.0
    weight_loss_balanced_hunger_threshold: float = 60.0
    starving_weight_loss_per_hour: float = 0.25
    resting_weight_gain_per_hour: float = 0.18
    active_weight_loss_per_hour: float = 0.08


@dataclass(frozen=True)
class PigWeightRules:
    """Rules documenting target-weight and deviation formulas.

    Target-weight formula:
    `base + force*w_force + endurance*w_endurance - agilite*w_agilite - vitesse*w_vitesse + (level - 1)*w_level`

    Weight-profile formula:
    - tolerance = `base_tolerance + endurance*tolerance_endurance + force*tolerance_force`
    - race_factor penalizes large deviations from the tolerance window
    - injury_factor increases when the deviation grows
    - force/agility modifiers depend on whether the pig is too heavy or too light
    """

    base_target_weight_kg: float = 108.0
    target_force_factor: float = 0.22
    target_endurance_factor: float = 0.16
    target_agilite_factor: float = 0.10
    target_vitesse_factor: float = 0.05
    target_level_factor: float = 0.35
    min_target_weight_kg: float = 95.0
    max_target_weight_kg: float = 140.0
    spawn_variation_kg: float = 7.0
    base_tolerance_kg: float = 10.0
    tolerance_endurance_factor: float = 0.08
    tolerance_force_factor: float = 0.04
    race_factor_floor: float = 0.82
    race_factor_cap: float = 1.06
    race_factor_base: float = 1.06
    race_factor_window_multiplier: float = 2.2
    race_factor_penalty_factor: float = 0.24
    injury_factor_cap: float = 0.35
    injury_factor_window_multiplier: float = 3.5
    ideal_zone_ratio: float = 0.4
    heavy_force_bonus_cap: float = 0.35
    heavy_force_bonus_factor: float = 0.12
    heavy_agilite_penalty_cap: float = 0.75
    heavy_agilite_penalty_factor: float = 0.25
    light_force_penalty_cap: float = 0.25
    light_force_penalty_factor: float = 0.08
    light_agilite_bonus_cap: float = 0.15
    light_agilite_bonus_factor: float = 0.05
    minimum_ratio_denominator: float = 1.0
    score_floor_percent: int = 8


@dataclass(frozen=True)
class PigPowerRules:
    """Rules documenting the race-power calculation.

    Power formula:
    - each stat is transformed through `sqrt(stat / max_value) * max_value`
    - hunger below the threshold reduces force and endurance
    - the final score is scaled by a condition factor based on average vitals
    """

    hungry_penalty_threshold: float = 10.0
    hungry_penalty_multiplier: float = 0.7
    excess_weight_penalty_scale: float = 0.2
    condition_base: float = 0.8
    condition_range: float = 0.4
    vitals_average_divisor: float = 3.0


@dataclass(frozen=True)
class PigTrophyRules:
    """Thresholds for pig lifetime and memorial trophies."""

    longevity_days_per_trophy_step: int = 30
    elder_days_threshold: int = 30
    pillar_days_threshold: int = 90
    school_sessions_memorial_threshold: int = 20


@dataclass(frozen=True)
class PigHeritageRules:
    """Multipliers used by retirement and lineage inheritance."""

    heritage_races_won_factor: float = 0.6
    heritage_level_factor: float = 0.08
    minimum_retirement_bonus: float = 1.0
    retirement_bonus_factor: float = 0.35
    descendant_lineage_factor: float = 0.4
    descendant_moral_cap: float = 4.0
    rarity_bonus_by_key: dict[str, float] = field(
        default_factory=lambda: {
            'commun': 0.0,
            'rare': 0.5,
            'epique': 1.0,
            'legendaire': 2.0,
        }
    )


@dataclass(frozen=True)
class PigOffspringRules:
    """Formulas used when generating a child from two parents."""

    parent_lineage_factor: float = 0.35
    barn_bonus_factor: float = 0.25
    inherited_stats_parent_average_factor: float = 0.82
    inherited_stats_random_min: float = -2.5
    inherited_stats_random_max: float = 2.5
    inherited_stat_floor: float = 8.0
    initial_energy: float = 78.0
    initial_hunger: float = 70.0
    initial_happiness_base: float = 72.0
    initial_happiness_barn_bonus_factor: float = 0.4


PIG_LIMITS = PigLimitRules()
PIG_DEFAULTS = PigDefaults()
PIG_INTERACTION_RULES = PigInteractionRules()
PIG_VITALS_RULES = PigVitalsRules()
PIG_WEIGHT_RULES = PigWeightRules()
PIG_POWER_RULES = PigPowerRules()
PIG_TROPHY_RULES = PigTrophyRules()
PIG_HERITAGE_RULES = PigHeritageRules()
PIG_OFFSPRING_RULES = PigOffspringRules()
