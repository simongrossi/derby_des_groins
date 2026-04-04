import unittest
from unittest.mock import patch

from app import create_app
from exceptions import ValidationError
from models import User
from services.market_service import list_pig_for_sale


class MarketServiceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')

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


if __name__ == '__main__':
    unittest.main()
