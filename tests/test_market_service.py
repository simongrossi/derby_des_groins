import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from extensions import db
from exceptions import ValidationError
from models import GrainFutureContract, GrainMarket, MarketEvent, MarketPositionHistory, User, UserCerealInventory
from services.market_service import (
    calculate_market_trend,
    create_grain_future_contract_for_user,
    get_grain_block_reason,
    list_pig_for_sale,
    resolve_due_grain_future_contracts,
    trigger_market_event,
)
from tests.support import build_test_app, reset_database


class MarketServiceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)

    @patch('helpers.market_helpers.get_market_unlock_progress', return_value=(True, 3, 24))
    @patch('services.market_service.is_market_open', return_value=False)
    def test_list_pig_for_sale_rejects_when_market_is_closed(
        self,
        _market_open_mock,
        _market_unlock_mock,
    ):
        with self.app.app_context():
            user = User(id=77, username='Seller')

            with self.assertRaises(ValidationError) as context:
                list_pig_for_sale(user, pig_id=12, starting_price=10.0)

        self.assertIn('marché est fermé', str(context.exception))

    def test_calculate_market_trend_reports_hausse_from_position_history(self):
        with self.app.app_context():
            db.session.add_all([
                MarketPositionHistory(cursor_x=1, cursor_y=1, average_surcharge=1.10),
                MarketPositionHistory(cursor_x=5, cursor_y=5, average_surcharge=1.42),
            ])
            db.session.add(GrainMarket(cursor_x=5, cursor_y=5))
            db.session.commit()

            trend = calculate_market_trend(days=7)

        self.assertEqual('hausse', trend['direction'])
        self.assertGreater(trend['delta_pct'], 0)

    @patch('services.pig_service.get_feeding_cost_multiplier', return_value=1.0)
    def test_create_grain_future_contract_locks_price_and_debits_user(self, _feeding_multiplier_mock):
        with self.app.app_context():
            user = User(username='Trader', password_hash='x', balance=500.0)
            db.session.add_all([user, GrainMarket(cursor_x=3, cursor_y=3)])
            db.session.commit()
            user_id = user.id

            contract = create_grain_future_contract_for_user(user.id, 'mais', quantity=2, delivery_days=3)
            contract_id = contract.id
            db.session.remove()
            refreshed_user = db.session.get(User, user_id)
            stored_contract = db.session.get(GrainFutureContract, contract_id)

        self.assertEqual('active', stored_contract.status)
        self.assertEqual('mais', stored_contract.cereal_key)
        self.assertEqual(2, stored_contract.quantity)
        self.assertLess(refreshed_user.balance, 500.0)

    @patch('services.market_service.push_user_notification')
    def test_resolve_due_grain_future_contracts_delivers_inventory(self, _notification_mock):
        with self.app.app_context():
            user = User(username='Holder', password_hash='x', balance=500.0)
            db.session.add(user)
            db.session.flush()
            contract = GrainFutureContract(
                user_id=user.id,
                cereal_key='mais',
                quantity=3,
                base_unit_price=10.0,
                locked_unit_price=11.0,
                surcharge_locked=1.0,
                feeding_multiplier_locked=1.0,
                premium_rate=0.10,
                total_price_paid=33.0,
                status='active',
                delivery_due_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
            )
            db.session.add(contract)
            db.session.commit()
            contract_id = contract.id
            user_id = user.id

            delivered = resolve_due_grain_future_contracts()
            db.session.remove()
            stored_contract = db.session.get(GrainFutureContract, contract_id)
            inventory = UserCerealInventory.query.filter_by(user_id=user_id, cereal_key='mais').first()

        self.assertEqual(1, delivered)
        self.assertEqual('delivered', stored_contract.status)
        self.assertEqual(3, inventory.quantity)

    def test_trigger_market_event_blocks_target_grain(self):
        with self.app.app_context():
            db.session.add(GrainMarket(cursor_x=3, cursor_y=3))
            db.session.commit()

            event = trigger_market_event(force_type='purchase_ban', target_cereal_key='mais')
            reason = get_grain_block_reason('mais', GrainMarket.query.first())

        self.assertIsInstance(event, MarketEvent)
        self.assertEqual('purchase_ban', event.event_type)
        self.assertIn('indisponible', reason)

    def test_trigger_market_event_can_move_market_cursor(self):
        with self.app.app_context():
            market = GrainMarket(cursor_x=3, cursor_y=3)
            db.session.add(market)
            db.session.commit()

            event = trigger_market_event(force_type='price_shock')
            event_id = event.id
            db.session.remove()
            stored_market = GrainMarket.query.first()
            stored_event = db.session.get(MarketEvent, event_id)

        self.assertIsInstance(stored_event, MarketEvent)
        self.assertEqual('price_shock', stored_event.event_type)
        self.assertNotEqual((3, 3), (stored_market.cursor_x, stored_market.cursor_y))


if __name__ == '__main__':
    unittest.main()
