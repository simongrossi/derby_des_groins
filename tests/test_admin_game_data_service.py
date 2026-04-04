import unittest

from app import create_app
from exceptions import ValidationError
from models import CerealItem, HangmanWordItem, SchoolLessonItem, TrainingItem


class AdminGameDataServiceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')

    def test_save_cereal_item_rejects_invalid_available_from(self):
        from services.admin_game_data_service import save_cereal_item

        with self.app.app_context():
            with self.assertRaises(ValidationError) as context:
                save_cereal_item({
                    'key': 'mais',
                    'name': 'Mais',
                    'available_from': 'pas-une-date',
                }, CerealItem())

        self.assertIn('Date invalide', str(context.exception))

    def test_save_training_item_rejects_invalid_energy_cost(self):
        from services.admin_game_data_service import save_training_item

        with self.app.app_context():
            with self.assertRaises(ValidationError) as context:
                save_training_item({
                    'key': 'sprint',
                    'name': 'Sprint',
                    'energy_cost': 'abc',
                }, TrainingItem())

        self.assertIn('Valeur invalide', str(context.exception))

    def test_save_lesson_item_rejects_invalid_available_until(self):
        from services.admin_game_data_service import save_lesson_item

        with self.app.app_context():
            with self.assertRaises(ValidationError) as context:
                save_lesson_item({
                    'key': 'strategie',
                    'name': 'Strategie',
                    'question': 'Question',
                    'available_until': 'pas-une-date',
                }, SchoolLessonItem())

        self.assertIn('Date invalide', str(context.exception))

    def test_save_hangman_word_rejects_invalid_word(self):
        from services.admin_game_data_service import save_hangman_word

        with self.app.app_context():
            with self.assertRaises(ValidationError) as context:
                save_hangman_word({'word': '1234'}, HangmanWordItem())

        self.assertIn('lettres et des espaces', str(context.exception))


if __name__ == '__main__':
    unittest.main()
