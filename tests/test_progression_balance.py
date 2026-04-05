import unittest
from datetime import datetime, timedelta

from extensions import db
from models import Pig, User
from services.economy_service import (
    get_economy_settings,
    get_feeding_cost_multiplier_for_count,
    get_progression_settings,
)
from tests.support import build_test_app, ensure_user, reset_database


class ProgressionBalanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)
        ensure_user(self.app, username='Simon')
        self.client = self.app.test_client()

    def test_default_balance_settings_reduce_passive_pressure(self):
        with self.app.app_context():
            economy = get_economy_settings()
            progression = get_progression_settings()

            self.assertEqual(economy.weekly_race_quota, 5)
            self.assertEqual(economy.race_appearance_reward, 12.0)
            self.assertEqual(economy.race_position_rewards[1], 100.0)
            self.assertEqual(economy.race_position_rewards[2], 60.0)
            self.assertEqual(economy.race_position_rewards[3], 35.0)
            self.assertEqual(get_feeding_cost_multiplier_for_count(4), 1.3)
            self.assertEqual(round(progression.hunger_decay_per_hour, 1), 1.2)
            self.assertEqual(round(progression.typing_xp_reward, 1), 12.0)
            self.assertEqual(progression.race_position_xp[1], 140)

    def test_typing_derby_shares_learning_decay_with_school(self):
        with self.app.app_context():
            user = User.query.filter_by(username='Simon').first()
            pig = Pig(
                user_id=user.id,
                name='Dactylo',
                xp=0,
                vitesse=10.0,
                agilite=10.0,
                daily_school_sessions=2,
                last_school_date=datetime.utcnow().date(),
                last_school_at=datetime.utcnow() - timedelta(minutes=40),
            )
            db.session.add(pig)
            db.session.commit()
            pig_id = pig.id
            user_id = user.id

        with self.client.session_transaction() as session:
            session['user_id'] = user_id

        response = self.client.post(
            '/typing-complete',
            data={'pig_id': pig_id, 'time_taken': 18, 'errors': 1},
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            pig = db.session.get(Pig, pig_id)
            self.assertEqual(pig.xp, 6)
            self.assertEqual(round(pig.vitesse, 2), 10.75)
            self.assertEqual(round(pig.agilite, 2), 10.5)
            self.assertEqual(pig.daily_school_sessions, 3)


if __name__ == '__main__':
    unittest.main()
