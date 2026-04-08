from datetime import datetime, timedelta
import unittest

from extensions import db
from models import BalanceTransaction, Bet, Pig, Trophy, User
from services.classement_page_service import (
    build_classement_page_context,
    build_empty_classement_page_context,
)
from tests.support import build_test_app, reset_database


class ClassementPageServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)

    def test_build_empty_classement_page_context_returns_empty_payload(self):
        context = build_empty_classement_page_context()

        self.assertEqual([], context['rankings'])
        self.assertEqual([], context['awards'])
        self.assertEqual([], context['chart_data']['labels'])

    def test_build_classement_page_context_uses_refactored_queries_and_trophies(self):
        with self.app.app_context():
            alice = User(username='Alice', password_hash='x', balance=650)
            bob = User(username='Bob', password_hash='x', balance=80)
            db.session.add_all([alice, bob])
            db.session.flush()

            db.session.add_all([
                Pig(
                    user_id=alice.id,
                    name='Atlas',
                    races_won=6,
                    races_entered=10,
                    level=4,
                    xp=120,
                    school_sessions_completed=21,
                    rarity='legendaire',
                    is_alive=True,
                ),
                Pig(
                    user_id=alice.id,
                    name='Brutus',
                    races_won=3,
                    races_entered=4,
                    is_alive=False,
                    death_cause='challenge',
                ),
                Pig(
                    user_id=bob.id,
                    name='Chou',
                    races_won=1,
                    races_entered=8,
                    is_alive=True,
                    level=2,
                ),
                Pig(
                    user_id=bob.id,
                    name='Dodu',
                    is_alive=False,
                    death_cause='blessure',
                ),
                Pig(
                    user_id=bob.id,
                    name='Eclair',
                    is_alive=False,
                    death_cause='sacrifice',
                ),
            ])

            db.session.add_all([
                Bet(
                    user_id=alice.id,
                    race_id=1,
                    pig_name='Atlas',
                    amount=10,
                    winnings=35,
                    odds_at_bet=3.5,
                    status='won',
                ),
                Bet(
                    user_id=alice.id,
                    race_id=2,
                    pig_name='Atlas',
                    amount=5,
                    winnings=0,
                    odds_at_bet=2.0,
                    status='lost',
                ),
                Bet(
                    user_id=bob.id,
                    race_id=3,
                    pig_name='Chou',
                    amount=20,
                    winnings=0,
                    odds_at_bet=4.0,
                    status='lost',
                ),
            ])

            now = datetime.now()
            db.session.add_all([
                BalanceTransaction(
                    user_id=alice.id,
                    amount=-25,
                    balance_before=675,
                    balance_after=650,
                    reason_code='feed_purchase',
                    reason_label='Nourriture',
                    created_at=now,
                ),
                BalanceTransaction(
                    user_id=alice.id,
                    amount=120,
                    balance_before=530,
                    balance_after=650,
                    reason_code='race_reward',
                    reason_label='Victoire',
                    created_at=now + timedelta(minutes=1),
                ),
                BalanceTransaction(
                    user_id=alice.id,
                    amount=999,
                    balance_before=650,
                    balance_after=650,
                    reason_code='snapshot',
                    reason_label='Snapshot',
                    created_at=now + timedelta(minutes=2),
                ),
            ])

            db.session.add(
                Trophy(
                    user_id=alice.id,
                    code='hall_of_fame',
                    label='Hall of Fame',
                    emoji='🌟',
                    description='Trophee persistant',
                    earned_at=now - timedelta(days=1),
                )
            )
            db.session.commit()

            context = build_classement_page_context()

        rankings = context['rankings']
        self.assertEqual(['Alice', 'Bob'], [entry['user'].username for entry in rankings])
        self.assertEqual(9, rankings[0]['total_wins'])
        self.assertEqual(14, rankings[0]['total_races'])
        self.assertEqual(1, rankings[0]['dead_count'])
        self.assertEqual(1, rankings[0]['deaths_challenge'])
        self.assertEqual(20.0, rankings[0]['bet_profit'])
        self.assertEqual(25.0, rankings[0]['total_spent_on_food'])
        self.assertEqual(120.0, rankings[0]['total_earned'])
        self.assertEqual('Atlas', rankings[0]['best_pig'].name)
        self.assertIn('Cresus', [trophy['n'] for trophy in rankings[0]['trophies']])
        self.assertIn('Collectionneur', [trophy['n'] for trophy in rankings[0]['trophies']])
        self.assertIn('Hall of Fame', [trophy['n'] for trophy in rankings[0]['trophies']])

        self.assertEqual(['Alice', 'Bob'], context['chart_data']['labels'])
        award_titles = {award['title']: award for award in context['awards']}
        self.assertEqual('Alice', award_titles['Roi du Derby']['user'])
        self.assertEqual('Alice', award_titles['Le Bookmaker']['user'])
        self.assertEqual('Bob', award_titles['Le Pigeon']['user'])


if __name__ == '__main__':
    unittest.main()
