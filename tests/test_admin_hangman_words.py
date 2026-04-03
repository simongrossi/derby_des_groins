import unittest
import uuid

from app import create_app
from extensions import db
from helpers.game_data import get_hangman_words, invalidate_game_data_cache
from models import HangmanWordItem, User


class AdminHangmanWordsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        with cls.app.app_context():
            HangmanWordItem.__table__.create(bind=db.engine, checkfirst=True)

    def setUp(self):
        self.client = self.app.test_client()

    def test_admin_can_create_hangman_word_from_admin_form(self):
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
            data={'word': 'vétérinaire', 'sort_order': '12', 'is_active': 'on'},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Mots du Cochon Pendu', response.get_data(as_text=True))

        with self.app.app_context():
            created = HangmanWordItem.query.filter_by(word='VETERINAIRE').first()
            self.assertIsNotNone(created)
            self.assertEqual(created.sort_order, 12)
            self.assertTrue(created.is_active)
            db.session.delete(created)
            admin = User.query.get(admin_id)
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
