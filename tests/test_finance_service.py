import unittest

from extensions import db
from models import BalanceTransaction, User
from services.finance_service import credit_user_balance
from tests.support import build_test_app, ensure_user, reset_database


class FinanceServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)

    def test_bet_payout_is_not_taxed_above_whale_threshold(self):
        ensure_user(self.app, username='Whale', balance=2500.0)

        with self.app.app_context():
            user = User.query.filter_by(username='Whale').first()
            before_balance = round(user.balance or 0.0, 2)

            credit_user_balance(
                user.id,
                100.0,
                reason_code='bet_payout',
                reason_label='Gain de pari',
                reference_type='bet',
                reference_id=42,
            )
            db.session.commit()

            refreshed_user = db.session.get(User, user.id)
            tx = (
                BalanceTransaction.query
                .filter_by(user_id=user.id, reason_code='bet_payout', reference_id=42)
                .order_by(BalanceTransaction.id.desc())
                .first()
            )

            self.assertIsNotNone(tx)
            self.assertEqual(round(refreshed_user.balance or 0.0, 2), before_balance + 100.0)
            self.assertEqual(round(tx.amount or 0.0, 2), 100.0)

    def test_bet_refund_is_not_taxed_above_whale_threshold(self):
        ensure_user(self.app, username='Refunded', balance=2500.0)

        with self.app.app_context():
            user = User.query.filter_by(username='Refunded').first()
            before_balance = round(user.balance or 0.0, 2)

            credit_user_balance(
                user.id,
                75.0,
                reason_code='bet_refund',
                reason_label='Remboursement pari',
                reference_type='race',
                reference_id=7,
            )
            db.session.commit()

            refreshed_user = db.session.get(User, user.id)
            tx = (
                BalanceTransaction.query
                .filter_by(user_id=user.id, reason_code='bet_refund', reference_id=7)
                .order_by(BalanceTransaction.id.desc())
                .first()
            )

            self.assertIsNotNone(tx)
            self.assertEqual(round(refreshed_user.balance or 0.0, 2), before_balance + 75.0)
            self.assertEqual(round(tx.amount or 0.0, 2), 75.0)

    def test_regular_credit_still_uses_progressive_tax(self):
        ensure_user(self.app, username='Taxed', balance=3500.0)

        with self.app.app_context():
            user = User.query.filter_by(username='Taxed').first()
            before_balance = round(user.balance or 0.0, 2)

            credit_user_balance(
                user.id,
                100.0,
                reason_code='auction_sale',
                reason_label='Vente',
                reference_type='auction',
                reference_id=9,
            )
            db.session.commit()

            refreshed_user = db.session.get(User, user.id)
            tx = (
                BalanceTransaction.query
                .filter_by(user_id=user.id, reason_code='auction_sale', reference_id=9)
                .order_by(BalanceTransaction.id.desc())
                .first()
            )

            self.assertIsNotNone(tx)
            self.assertEqual(round(refreshed_user.balance or 0.0, 2), before_balance + 80.0)
            self.assertEqual(round(tx.amount or 0.0, 2), 80.0)


if __name__ == '__main__':
    unittest.main()
