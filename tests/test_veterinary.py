import unittest
from datetime import datetime, timedelta

from extensions import db
from helpers.time_helpers import format_duration_short
from models import Pig, User
from tests.support import build_test_app, ensure_user, reset_database


class VeterinaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)
        ensure_user(self.app, username='Simon')
        self.client = self.app.test_client()

    def test_format_duration_short_supports_longer_windows(self):
        self.assertEqual(format_duration_short(12 * 3600), '12h 00m')
        self.assertEqual(format_duration_short((24 + 3) * 3600), '1j 03h')

    def test_vet_solve_uses_base_cost_when_treated_immediately(self):
        with self.app.app_context():
            user = User.query.filter_by(username='Simon').first()
            pig = Pig(
                user_id=user.id,
                name='Rosette',
                is_injured=True,
                energy=80.0,
                happiness=70.0,
                vet_deadline=datetime.utcnow() + timedelta(hours=12),
            )
            db.session.add(pig)
            db.session.commit()
            pig_id = pig.id
            user_id = user.id

        with self.client.session_transaction() as session:
            session['user_id'] = user_id

        response = self.client.post('/api/vet/solve', json={'pig_id': pig_id})
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            pig = db.session.get(Pig, pig_id)
            self.assertFalse(pig.is_injured)
            self.assertEqual(round(pig.energy, 1), 70.0)
            self.assertEqual(round(pig.happiness, 1), 65.0)

    def test_vet_solve_costs_more_when_treated_late(self):
        with self.app.app_context():
            user = User.query.filter_by(username='Simon').first()
            pig = Pig(
                user_id=user.id,
                name='Rosette',
                is_injured=True,
                energy=80.0,
                happiness=70.0,
                vet_deadline=datetime.utcnow() + timedelta(hours=3),
            )
            db.session.add(pig)
            db.session.commit()
            pig_id = pig.id
            user_id = user.id

        with self.client.session_transaction() as session:
            session['user_id'] = user_id

        response = self.client.post('/api/vet/solve', json={'pig_id': pig_id})
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            pig = db.session.get(Pig, pig_id)
            self.assertFalse(pig.is_injured)
            self.assertEqual(round(pig.energy, 1), 62.5)
            self.assertEqual(round(pig.happiness, 1), 57.5)


if __name__ == '__main__':
    unittest.main()
