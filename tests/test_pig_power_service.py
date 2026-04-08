from types import SimpleNamespace
import unittest
from unittest.mock import patch

from config.game_rules import PIG_LIMITS, PIG_WEIGHT_RULES
from services.pig_power_service import (
    PigSettings,
    calculate_pig_power,
    calculate_target_weight_kg,
    check_level_up,
    get_weight_profile,
)


def build_pig_settings():
    return PigSettings(
        max_slots=6,
        retirement_min_wins=3,
        default_max_races=12,
        weight_default_kg=112.0,
        weight_min_kg=80.0,
        weight_max_kg=160.0,
        weight_malus_ratio=0.15,
        weight_malus_max=0.35,
        injury_min_risk=2.0,
        injury_max_risk=18.0,
        vet_response_minutes=90,
        weight_rules=PIG_WEIGHT_RULES,
    )


class PigPowerServiceTests(unittest.TestCase):
    @patch('services.pig_power_service.get_pig_settings', return_value=build_pig_settings())
    def test_calculate_target_weight_kg_uses_stats_profile(self, _settings_mock):
        pig = SimpleNamespace(force=15, endurance=14, agilite=8, vitesse=7, level=3)

        target_weight = calculate_target_weight_kg(pig)

        self.assertGreaterEqual(target_weight, PIG_WEIGHT_RULES.min_target_weight_kg)
        self.assertLessEqual(target_weight, PIG_WEIGHT_RULES.max_target_weight_kg)

    @patch('services.pig_power_service.get_pig_settings', return_value=build_pig_settings())
    def test_get_weight_profile_flags_heavy_pigs(self, _settings_mock):
        pig = SimpleNamespace(
            weight_kg=145.0,
            force=18.0,
            endurance=12.0,
            agilite=8.0,
            vitesse=7.0,
            level=2,
        )

        profile = get_weight_profile(pig)

        self.assertEqual('heavy', profile['status'])
        self.assertGreater(profile['force_mod'], 1.0)
        self.assertLess(profile['agilite_mod'], 1.0)

    @patch('services.pig_power_service.get_pig_settings', return_value=build_pig_settings())
    @patch('services.pig_power_service.get_freshness_bonus', return_value={'multiplier': 1.0})
    def test_calculate_pig_power_applies_condition_penalties(self, _freshness_mock, _settings_mock):
        balanced_profile = {
            'current_weight': 112.0,
            'ideal_weight': 112.0,
            'race_factor': 1.0,
            'force_mod': 1.0,
            'agilite_mod': 1.0,
        }
        heavy_profile = {
            'current_weight': 145.0,
            'ideal_weight': 112.0,
            'race_factor': 0.82,
            'force_mod': 1.1,
            'agilite_mod': 0.8,
        }
        fit_pig = SimpleNamespace(
            force=20.0,
            endurance=20.0,
            vitesse=20.0,
            agilite=20.0,
            intelligence=20.0,
            moral=20.0,
            energy=90.0,
            hunger=90.0,
            happiness=90.0,
        )
        tired_pig = SimpleNamespace(
            force=20.0,
            endurance=20.0,
            vitesse=20.0,
            agilite=20.0,
            intelligence=20.0,
            moral=20.0,
            energy=40.0,
            hunger=10.0,
            happiness=50.0,
        )

        with patch('services.pig_power_service.get_weight_profile', side_effect=[balanced_profile, heavy_profile]):
            fit_power = calculate_pig_power(fit_pig)
            tired_power = calculate_pig_power(tired_pig)

        self.assertGreater(fit_power, tired_power)
        self.assertGreater(fit_power, 0)

    @patch('services.pig_power_service.get_level_happiness_bonus_value', return_value=4.0)
    @patch('services.pig_power_service.xp_for_level_value', side_effect=lambda level: level * 10)
    def test_check_level_up_advances_multiple_levels(self, _xp_mock, _happiness_mock):
        pig = SimpleNamespace(level=1, xp=35, happiness=95.0)

        check_level_up(pig)

        self.assertEqual(3, pig.level)
        self.assertEqual(PIG_LIMITS.max_value, pig.happiness)


if __name__ == '__main__':
    unittest.main()
