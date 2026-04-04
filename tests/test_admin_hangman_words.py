import unittest
import uuid

from extensions import db
from helpers.game_data import get_hangman_words, invalidate_game_data_cache
from models import HangmanWordItem, User
from tests.support import build_test_app, reset_database


class AdminHangmanWordsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)
        self.client = self.app.test_client()

    def test_admin_can_create_hangman_phrase_from_admin_form(self):
        username = f"hangman-admin-{uuid.uuid4().hex[:8]}"

        with self.app.app_context():
            admin = User(username=username, password_hash='x', is_admin=True)
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id

        with self.client.session_transaction() as session:
            session['user_id'] = admin_id

        response = self.client.post(
            '/admin/data/hangman-word/save',
            data={'word': 'gros vétérinaire', 'sort_order': '12', 'is_active': 'on'},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Mots du Cochon Pendu', response.get_data(as_text=True))

        with self.app.app_context():
            created = HangmanWordItem.query.filter_by(word='GROS VETERINAIRE').first()
            self.assertIsNotNone(created)
            self.assertEqual(created.sort_order, 12)
            self.assertTrue(created.is_active)
            db.session.delete(created)
            admin = db.session.get(User, admin_id)
            db.session.delete(admin)
            db.session.commit()

    def test_admin_can_replace_hangman_list_from_textarea(self):
        username = f"hangman-admin-{uuid.uuid4().hex[:8]}"
        previous_words = []

        with self.app.app_context():
            previous_words = [
                {
                    'word': item.word,
                    'is_active': item.is_active,
                    'sort_order': item.sort_order,
                }
                for item in HangmanWordItem.query.order_by(HangmanWordItem.sort_order, HangmanWordItem.id).all()
            ]
            admin = User(username=username, password_hash='x', is_admin=True)
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id

        with self.client.session_transaction() as session:
            session['user_id'] = admin_id

        response = self.client.post(
            '/admin/data/hangman-words/bulk-save',
            data={'words_text': 'gros groin\n\nvétérinaire de course\nGROS GROIN'},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Liste du Cochon Pendu remplacee', response.get_data(as_text=True))

        with self.app.app_context():
            words = HangmanWordItem.query.order_by(HangmanWordItem.sort_order, HangmanWordItem.id).all()
            self.assertEqual([word.word for word in words[:2]], ['GROS GROIN', 'VETERINAIRE DE COURSE'])
            HangmanWordItem.query.delete()
            for item in previous_words:
                db.session.add(HangmanWordItem(**item))
            admin = db.session.get(User, admin_id)
            db.session.delete(admin)
            db.session.commit()

    def test_hangman_helper_returns_only_active_admin_words(self):
        active_word = f"GROIN{uuid.uuid4().hex[:4].upper()}"
        inactive_word = f"LARD{uuid.uuid4().hex[:4].upper()}"

        with self.app.app_context():
            active_item = HangmanWordItem(word=active_word, is_active=True, sort_order=9998)
            inactive_item = HangmanWordItem(word=inactive_word, is_active=False, sort_order=9999)
            db.session.add(active_item)
            db.session.add(inactive_item)
            db.session.commit()

            invalidate_game_data_cache()
            words = get_hangman_words()
            self.assertIn(active_word, words)
            self.assertNotIn(inactive_word, words)

            db.session.delete(inactive_item)
            db.session.delete(active_item)
            db.session.commit()
            invalidate_game_data_cache()


if __name__ == '__main__':
    unittest.main()
