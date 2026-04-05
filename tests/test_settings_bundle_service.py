import json
import unittest

from services.game_settings_bundle_service import (
    build_game_settings_bundle,
    build_game_settings_bundle_json,
    import_game_settings_bundle,
)
from services.gameplay_settings_service import (
    get_gameplay_settings,
    get_minigame_settings,
)
from services.pig_power_service import get_pig_settings
from tests.support import build_test_app, reset_database


class SettingsBundleServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)

    def test_bundle_export_contains_new_domains(self):
        with self.app.app_context():
            bundle = build_game_settings_bundle()
            self.assertIn('gameplay', bundle)
            self.assertIn('minigames', bundle)
            self.assertIn('race_engine', bundle)
            self.assertEqual(bundle['schema_version'], 1)

    def test_bundle_import_applies_gameplay_and_minigames(self):
        with self.app.app_context():
            bundle = build_game_settings_bundle()
            bundle['gameplay']['school_cooldown_minutes'] = 45
            bundle['minigames']['agenda_reward'] = 77
            bundle['minigames']['pendu_free_plays_per_day'] = 4
            bundle['pigs']['default_max_races'] = 36
            bundle['pigs']['weight_rules']['target_force_factor'] = 0.3

            import_game_settings_bundle(json.dumps(bundle))

            gameplay = get_gameplay_settings()
            minigames = get_minigame_settings()
            pigs = get_pig_settings()

            self.assertEqual(gameplay.school_cooldown_minutes, 45)
            self.assertEqual(minigames.agenda_reward, 77.0)
            self.assertEqual(minigames.pendu_free_plays_per_day, 4)
            self.assertEqual(pigs.default_max_races, 36)
            self.assertEqual(pigs.weight_rules.target_force_factor, 0.3)

    def test_bundle_json_is_valid_json(self):
        with self.app.app_context():
            payload = json.loads(build_game_settings_bundle_json())
            self.assertEqual(payload['schema_version'], 1)


if __name__ == '__main__':
    unittest.main()
