import unittest

from app import create_app
from extensions import db
from helpers import ensure_next_race
from models import Bet, Participant, Race, User


class BettingRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True

    def setUp(self):
        self.client = self.app.test_client()

    def test_place_bet_creates_ticket_and_debits_balance(self):
        with self.app.app_context():
            user = User.query.filter_by(username='Simon').first()
            race = ensure_next_race()
            participant = Participant.query.filter_by(race_id=race.id).order_by(Participant.odds.asc()).first()
            self.assertIsNotNone(participant)

            Bet.query.filter_by(user_id=user.id, race_id=race.id).delete(synchronize_session=False)
            db.session.commit()

            before_balance = round(user.balance or 0.0, 2)
            user_id = user.id
            race_id = race.id
            participant_id = participant.id

        with self.client.session_transaction() as session:
            session['user_id'] = user_id

        response = self.client.post('/bet', data={
            'race_id': race_id,
            'bet_type': 'win',
            'selection_order': str(participant_id),
            'amount': '5',
        }, follow_redirects=False)

        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            bet = Bet.query.filter_by(user_id=user_id, race_id=race_id).first()
            refreshed_user = User.query.get(user_id)

            self.assertIsNotNone(bet)
            self.assertEqual(bet.bet_type, 'win')
            self.assertEqual(bet.selection_order, str(participant_id))
            self.assertEqual(round(refreshed_user.balance or 0.0, 2), round(before_balance - 5.0, 2))

            db.session.delete(bet)
            refreshed_user.balance = before_balance
            db.session.commit()


if __name__ == '__main__':
    unittest.main()
