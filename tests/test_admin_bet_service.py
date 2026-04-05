import unittest
from datetime import datetime

from extensions import db
from models import BalanceTransaction, Bet, Participant, Race, User
from services.admin_bet_service import reconcile_bet_by_id
from services.finance_service import adjust_user_balance
from tests.support import build_test_app, ensure_user, reset_database


class AdminBetServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)

    def test_reconcile_bet_repairs_undercredited_winning_ticket(self):
        ensure_user(self.app, username='Parieur', balance=0.0)

        with self.app.app_context():
            user = User.query.filter_by(username='Parieur').first()
            race = Race(
                scheduled_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
                status='finished',
                winner_name='Alpha',
                winner_odds=10.0,
            )
            db.session.add(race)
            db.session.flush()

            winner = Participant(
                race_id=race.id,
                name='Alpha',
                emoji='🐷',
                odds=10.0,
                win_probability=0.7,
                finish_position=1,
            )
            loser = Participant(
                race_id=race.id,
                name='Beta',
                emoji='🐷',
                odds=2.0,
                win_probability=0.3,
                finish_position=2,
            )
            db.session.add_all([winner, loser])
            db.session.flush()

            bet = Bet(
                user_id=user.id,
                race_id=race.id,
                pig_name='Alpha',
                bet_type='win',
                selection_order=str(winner.id),
                amount=10.0,
                odds_at_bet=10.0,
                status='won',
                winnings=80.0,
            )
            db.session.add(bet)
            db.session.flush()

            adjust_user_balance(
                user.id,
                80.0,
                reason_code='bet_payout',
                reason_label='Gain de pari',
                reference_type='bet',
                reference_id=bet.id,
            )
            db.session.commit()

            before_balance = round(db.session.get(User, user.id).balance or 0.0, 2)

            reconciled_bet, did_update, result = reconcile_bet_by_id(bet.id)

            db.session.refresh(reconciled_bet)
            refreshed_user = db.session.get(User, user.id)
            payout_transactions = (
                BalanceTransaction.query
                .filter_by(user_id=user.id, reference_type='bet', reference_id=bet.id)
                .order_by(BalanceTransaction.id.asc())
                .all()
            )

            self.assertTrue(did_update)
            self.assertEqual(result, 'won')
            self.assertEqual(round(refreshed_user.balance or 0.0, 2), before_balance + 20.0)
            self.assertEqual(round(reconciled_bet.winnings or 0.0, 2), 100.0)
            self.assertEqual(round(sum(tx.amount for tx in payout_transactions), 2), 100.0)


if __name__ == '__main__':
    unittest.main()
