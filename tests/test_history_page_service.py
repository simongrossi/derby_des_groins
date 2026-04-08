from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest

from services.history_page_service import (
    _build_bet_curve_context,
    _build_bitgroins_curve_context,
    _get_bet_net_delta,
    _normalize_selected_user_ids,
)


class HistoryPageServiceTests(unittest.TestCase):
    def test_get_bet_net_delta_handles_settled_and_pending_bets(self):
        self.assertEqual(15.0, _get_bet_net_delta(SimpleNamespace(status='won', winnings=25.0, amount=10.0)))
        self.assertEqual(-10.0, _get_bet_net_delta(SimpleNamespace(status='lost', winnings=0.0, amount=10.0)))
        self.assertEqual(0.0, _get_bet_net_delta(SimpleNamespace(status='refunded', winnings=0.0, amount=10.0)))
        self.assertIsNone(_get_bet_net_delta(SimpleNamespace(status='pending', winnings=0.0, amount=10.0)))

    def test_normalize_selected_user_ids_deduplicates_and_supports_all(self):
        self.assertEqual([], _normalize_selected_user_ids(['all', '12']))
        self.assertEqual([2, 5], _normalize_selected_user_ids(['5', '2', 'oops', '5']))

    def test_build_bitgroins_curve_context_sorts_transactions_and_computes_swings(self):
        alice = SimpleNamespace(id=1, username='Alice')
        bob = SimpleNamespace(id=2, username='Bob')
        base = datetime(2026, 1, 1, 12, 0)
        transactions = [
            SimpleNamespace(id=2, user_id=1, user=alice, amount=-20, balance_after=80, reason_label='Achat', reason_code='feed', created_at=base + timedelta(minutes=1)),
            SimpleNamespace(id=1, user_id=1, user=alice, amount=100, balance_after=100, reason_label='Prime', reason_code='reward', created_at=base),
            SimpleNamespace(id=3, user_id=2, user=bob, amount=10, balance_after=40, reason_label='Gain', reason_code='reward', created_at=base + timedelta(minutes=2)),
            SimpleNamespace(id=4, user_id=999, user=None, amount=999, balance_after=999, reason_label='Ignore', reason_code='snapshot', created_at=base),
        ]

        context = _build_bitgroins_curve_context(transactions)

        self.assertEqual(3, context['total_points'])
        self.assertEqual(['Alice', 'Bob'], [row['label'] for row in context['rows']])
        self.assertEqual(2, context['rows'][0]['tx_count'])
        self.assertEqual(100.0, context['biggest_jump']['largest_jump'])
        self.assertEqual(-20.0, context['biggest_drop']['largest_drop'])
        self.assertEqual(100.0, context['datasets'][0]['data'][0]['y'])

    def test_build_bet_curve_context_marks_suspicious_large_swings(self):
        alice = SimpleNamespace(id=1, username='Alice')
        bob = SimpleNamespace(id=2, username='Bob')
        base = datetime(2026, 1, 1, 9, 0)
        bets = [
            SimpleNamespace(id=1, user_id=1, user=alice, amount=10.0, winnings=15.0, status='won', placed_at=base, bet_type='win', pig_name='Atlas', outcome_snapshot=None),
            SimpleNamespace(id=2, user_id=1, user=alice, amount=10.0, winnings=20.0, status='won', placed_at=base + timedelta(minutes=1), bet_type='win', pig_name='Atlas', outcome_snapshot=None),
            SimpleNamespace(id=3, user_id=1, user=alice, amount=10.0, winnings=25.0, status='won', placed_at=base + timedelta(minutes=2), bet_type='win', pig_name='Atlas', outcome_snapshot=None),
            SimpleNamespace(id=4, user_id=1, user=alice, amount=10.0, winnings=170.0, status='won', placed_at=base + timedelta(minutes=3), bet_type='win', pig_name='Atlas', outcome_snapshot=SimpleNamespace(bet_label='Jackpot')),
            SimpleNamespace(id=5, user_id=2, user=bob, amount=20.0, winnings=0.0, status='lost', placed_at=base + timedelta(minutes=4), bet_type='place', pig_name='Bolt', outcome_snapshot=None),
            SimpleNamespace(id=6, user_id=2, user=bob, amount=5.0, winnings=0.0, status='pending', placed_at=base + timedelta(minutes=5), bet_type='place', pig_name='Bolt', outcome_snapshot=None),
        ]

        context = _build_bet_curve_context(bets)

        self.assertEqual(150.0, context['suspicious_threshold'])
        self.assertEqual(1, context['suspicious_count'])
        self.assertEqual('Alice', context['biggest_jump']['label'])
        self.assertTrue(context['rows'][0]['is_suspicious'])
        self.assertEqual('Jackpot', context['datasets'][0]['data'][-1]['bet_label'])


if __name__ == '__main__':
    unittest.main()
