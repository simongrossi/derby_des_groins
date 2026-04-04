import unittest

from app import create_app

from exceptions import ValidationError


class AdminSettingsServiceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')

    def test_save_race_engine_settings_json_rejects_invalid_json(self):
        from services.admin_settings_service import save_race_engine_settings_json

        with self.app.app_context():
            with self.assertRaises(ValidationError) as context:
                save_race_engine_settings_json('{bad json}')

        self.assertIn('JSON invalide', str(context.exception))


if __name__ == '__main__':
    unittest.main()
