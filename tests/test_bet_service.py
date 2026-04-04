import unittest
from unittest.mock import patch

from exceptions import ValidationError
from models import User
from services.bet_service import place_bet_for_user


class BetServiceUnitTests(unittest.TestCase):
    @patch(
        'services.bet_service.get_bet_limits',
        return_value={'min_bet_race': 1.0, 'max_bet_race': 100.0},
    )
    @patch(
        'services.bet_service.get_configured_bet_types',
        return_value={'win': {'selection_count': 1, 'label': 'Gagnant', 'icon': '🎟️'}},
    )
    @patch('services.bet_service.get_weekly_bacon_tickets_value', return_value=3)
    @patch('services.bet_service.get_user_weekly_bet_count', return_value=3)
    def test_place_bet_rejects_when_weekly_ticket_quota_is_reached(
        self,
        _weekly_count_mock,
        _weekly_tickets_mock,
        _bet_types_mock,
        _bet_limits_mock,
    ):
        user = User(id=123, username='UnitTester')

        with self.assertRaises(ValidationError) as context:
            place_bet_for_user(user, 99, 'win', '1', 5.0)

        self.assertIn('Tickets Bacon', str(context.exception))


if __name__ == '__main__':
    unittest.main()
