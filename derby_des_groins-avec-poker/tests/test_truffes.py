import unittest

from app import create_app
from models import User
from routes.truffes import GRID_SIZE, MAX_CLICKS, TRUFFE_REWARD


class TruffesRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True

    def test_constants_match_expected_game_shape(self):
        self.assertEqual(GRID_SIZE, 20)
        self.assertEqual(MAX_CLICKS, 7)
        self.assertEqual(TRUFFE_REWARD, 20)

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
        self.assertEqual(payload['reward'], TRUFFE_REWARD)

        with self.app.app_context():
            refreshed = User.query.get(user_id)
            self.assertEqual(round(refreshed.balance or 0.0, 2), round(before + TRUFFE_REWARD, 2))
            refreshed.balance = before
            from extensions import db
            db.session.commit()


if __name__ == '__main__':
    unittest.main()
