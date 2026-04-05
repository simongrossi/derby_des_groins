import unittest
import uuid

from extensions import db
from helpers.config import set_config
from models import User
from services.gameplay_settings_service import get_minigame_settings
from tests.support import build_test_app, ensure_user, reset_database


class TruffesRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)
        ensure_user(self.app, username='Simon')

    def test_constants_match_expected_game_shape(self):
        with self.app.app_context():
            settings = get_minigame_settings()
            self.assertEqual(settings.truffe_grid_size, 20)
            self.assertEqual(settings.truffe_max_clicks, 7)
            self.assertEqual(settings.truffe_reward, 20)

    def test_win_route_requires_authentication(self):
        client = self.app.test_client()
        response = client.post('/truffes/win', json={'clicks': 3})

        self.assertEqual(response.status_code, 401)

    def test_win_route_credits_reward(self):
        client = self.app.test_client()
        with self.app.app_context():
            user = User.query.filter_by(username='Simon').first()
            before = round(user.balance or 0.0, 2)
            user_id = user.id

        with client.session_transaction() as session:
            session['user_id'] = user_id

        response = client.post('/truffes/win', json={'clicks': 4})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        with self.app.app_context():
            reward = get_minigame_settings().truffe_reward

        self.assertEqual(payload['reward'], reward)

        with self.app.app_context():
            refreshed = db.session.get(User, user_id)
            self.assertEqual(round(refreshed.balance or 0.0, 2), round(before + reward, 2))
            refreshed.balance = before
            db.session.commit()

    def test_play_route_decrements_remaining_free_plays_for_regular_user(self):
        client = self.app.test_client()
        username = f"truffes-player-{uuid.uuid4().hex[:8]}"

        with self.app.app_context():
            set_config('truffe_daily_limit', '5')
            user = User(username=username, password_hash='x', is_admin=False, truffe_plays_today=0)
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        with client.session_transaction() as session:
            session['user_id'] = user_id

        response = client.post('/truffes/play', json={'is_replay': False})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['remaining_free_plays'], 4)

        with self.app.app_context():
            refreshed = db.session.get(User, user_id)
            self.assertEqual(refreshed.truffe_plays_today, 1)
            db.session.delete(refreshed)
            db.session.commit()

    def test_play_route_decrements_remaining_free_plays_for_admin_too(self):
        client = self.app.test_client()
        username = f"truffes-admin-{uuid.uuid4().hex[:8]}"

        with self.app.app_context():
            set_config('truffe_daily_limit', '5')
            admin = User(username=username, password_hash='x', is_admin=True, truffe_plays_today=0)
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id

        with client.session_transaction() as session:
            session['user_id'] = admin_id

        response = client.post('/truffes/play', json={'is_replay': False})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['remaining_free_plays'], 4)

        with self.app.app_context():
            refreshed = db.session.get(User, admin_id)
            self.assertEqual(refreshed.truffe_plays_today, 1)
            db.session.delete(refreshed)
            db.session.commit()


if __name__ == '__main__':
    unittest.main()
