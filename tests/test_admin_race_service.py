import unittest

from werkzeug.datastructures import MultiDict

from app import create_app
from exceptions import ValidationError


class AdminRaceServiceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')

    def test_parse_race_npcs_csv_content_requires_name_column(self):
        from services.admin_race_service import parse_race_npcs_csv_content

        with self.assertRaises(ValidationError) as context:
            parse_race_npcs_csv_content("emoji\n🐷\n")

        self.assertIn("colonne obligatoire 'name'", str(context.exception))

    def test_save_admin_races_configuration_rejects_invalid_timezone(self):
        from services.admin_race_service import save_admin_races_configuration

        with self.app.app_context():
            with self.assertRaises(ValidationError) as context:
                save_admin_races_configuration(
                    MultiDict({
                        'timezone': 'Mars/Olympus',
                    })
                )

        self.assertIn('Fuseau horaire invalide', str(context.exception))


if __name__ == '__main__':
    unittest.main()
