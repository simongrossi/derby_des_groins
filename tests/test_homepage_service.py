from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from extensions import db
from models import BalanceTransaction, Bet, Participant, Pig, Race, User, UserCerealInventory
from services.homepage_service import build_homepage_context
from tests.support import build_test_app, reset_database


class HomepageServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)

    @patch('services.homepage_service.recommend_best_cereal', return_value='mais')
    @patch('services.homepage_service.get_course_theme', return_value='Boue Party')
    @patch('services.homepage_service.get_next_market_time', return_value='demain 09:00')
    @patch('services.homepage_service.is_market_open', return_value=True)
    @patch('services.homepage_service.get_prix_moyen_groin', return_value=12.5)
    @patch('services.homepage_service.get_user_weekly_bet_count', return_value=1)
    @patch('services.homepage_service.build_course_schedule', return_value=['slot-1', 'slot-2', 'slot-3'])
    @patch('services.homepage_service.get_pig_dashboard_status', return_value={'rest_label': 'En forme', 'rest_note': 'Pret pour la suite'})
    @patch('services.homepage_service.get_weight_profile', return_value={'status': 'ideal'})
    @patch('services.homepage_service.calculate_pig_power', return_value=42.5)
    @patch('services.homepage_service.update_pig_vitals')
    @patch('services.homepage_service.get_user_active_pigs')
    @patch('services.homepage_service.claim_daily_reward', return_value=25.0)
    @patch('services.homepage_service.get_configured_bet_types', return_value={'win': {'label': 'Gagnant'}})
    @patch('services.homepage_service.get_weekly_bacon_tickets_value', return_value=3)
    def test_build_homepage_context_for_logged_user_builds_dashboard_payload(
        self,
        _weekly_tickets_mock,
        _bet_types_mock,
        _daily_reward_mock,
        get_user_active_pigs_mock,
        _update_vitals_mock,
        _power_mock,
        _weight_mock,
        _dashboard_mock,
        _schedule_mock,
        _weekly_count_mock,
        _price_mock,
        _market_open_mock,
        _next_market_mock,
        _theme_mock,
        _recommend_mock,
    ):
        with self.app.app_context():
            user = User(username='Alice', password_hash='x')
            db.session.add(user)
            db.session.flush()

            now = datetime.now()
            next_race = Race(scheduled_at=now + timedelta(hours=1), status='open')
            latest_race = Race(
                scheduled_at=now - timedelta(days=1),
                finished_at=now - timedelta(days=1, minutes=-5),
                status='finished',
            )
            pig = Pig(user_id=user.id, name='Atlas', is_alive=True, is_injured=False)
            injured_pig = Pig(user_id=user.id, name='Bobo', is_alive=True, is_injured=True, vet_deadline=now + timedelta(hours=2))
            db.session.add_all([next_race, latest_race, pig, injured_pig])
            db.session.flush()

            db.session.add_all([
                Participant(race_id=next_race.id, pig_id=pig.id, name=pig.name, odds=2.4, win_probability=0.4, owner_name=user.username),
                Participant(race_id=latest_race.id, pig_id=pig.id, name=pig.name, odds=2.0, win_probability=0.5, finish_position=1, owner_name=user.username),
                Bet(user_id=user.id, race_id=next_race.id, pig_name=pig.name, amount=10, winnings=0, odds_at_bet=2.4, status='pending'),
                BalanceTransaction(user_id=user.id, amount=75, balance_before=0, balance_after=75, reason_code='bet_payout', reason_label='Jackpot', created_at=now),
                UserCerealInventory(user_id=user.id, cereal_key='mais', quantity=3),
            ])
            db.session.commit()

            get_user_active_pigs_mock.return_value = [pig]
            context = build_homepage_context(user.id)

        self.assertEqual(user.id, context['user'].id)
        self.assertEqual(next_race.id, context['next_race'].id)
        self.assertEqual('Atlas', context['featured_pig']['pig'].name)
        self.assertTrue(context['headline_status']['participates'])
        self.assertEqual(2, context['bacon_tickets_remaining'])
        self.assertEqual('mais', context['recommended_cereal'])
        self.assertEqual({'mais': 3}, context['inventory'])
        self.assertEqual(25.0, context['daily_reward'])
        self.assertEqual('Boue Party', context['next_race_theme'])
        self.assertGreater(len(context['news_items']), 0)
        self.assertEqual('Alice', context['latest_race_participants'][0].owner_name)


if __name__ == '__main__':
    unittest.main()
