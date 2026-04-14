import unittest
from datetime import datetime

from config.game_rules import PIG_DEFAULTS
from extensions import db
from models import BalanceTransaction, Duel, Pig, User
from services.octogroin_service import (
    FORFEIT_GRACE_SECONDS,
    OctogroinError,
    cancel_duel,
    create_duel,
    finish_duel,
    get_matchup_rating,
    get_player_hand,
    join_duel,
    list_open_duels,
    list_user_duels,
    get_visible_duel,
    maybe_auto_resolve_overdue,
    submit_actions,
)
from services.octogroin_cards import CARDS, HAND_SIZE
from tests.support import build_test_app, reset_database


def _make_pig(user_id, name, **overrides):
    attrs = dict(
        user_id=user_id,
        name=name,
        sex='M',
        force=60, endurance=60, agilite=60,
        intelligence=60, moral=60, vitesse=60,
        energy=80, hunger=80, happiness=80,
        weight_kg=112.0,
        is_alive=True,
        is_injured=False,
    )
    attrs.update(overrides)
    pig = Pig(**attrs)
    db.session.add(pig)
    return pig


def _make_user(username, balance=500.0):
    u = User(username=username, password_hash='x', balance=balance, created_at=datetime.utcnow())
    db.session.add(u)
    return u


class OctogroinServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)

    def _fixture(self):
        """Crée alice, bob, carol + un cochon chacun. Retourne les IDs."""
        with self.app.app_context():
            a = _make_user('alice', balance=500.0)
            b = _make_user('bob', balance=500.0)
            c = _make_user('carol', balance=500.0)
            db.session.flush()
            pa = _make_pig(a.id, 'AliceCochon')
            pb = _make_pig(b.id, 'BobCochon')
            pc = _make_pig(c.id, 'CarolCochon')
            db.session.commit()
            return {'a': a.id, 'b': b.id, 'c': c.id, 'pa': pa.id, 'pb': pb.id, 'pc': pc.id}

    def test_create_public_duel_debits_creator(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            duel = create_duel(a, pa, 25.0, 'public')
            self.assertEqual(duel.status, 'waiting')
            self.assertEqual(duel.visibility, 'public')
            self.assertAlmostEqual(duel.stake, 25.0)
            self.assertEqual(db.session.get(User, ids['a']).balance, 475.0)
            tx = BalanceTransaction.query.filter_by(
                user_id=ids['a'], reason_code='octogroin_stake', reference_id=duel.id
            ).first()
            self.assertIsNotNone(tx)
            self.assertAlmostEqual(tx.amount, -25.0)

    def test_create_direct_duel_requires_target(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            with self.assertRaises(OctogroinError):
                create_duel(a, pa, 25.0, 'direct')

    def test_stake_bounds_enforced(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            with self.assertRaises(OctogroinError):
                create_duel(a, pa, 1.0, 'public')  # below min
            with self.assertRaises(OctogroinError):
                create_duel(a, pa, 10_000.0, 'public')  # above max

    def test_insufficient_balance_rejected(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            a.balance = 5.0
            db.session.commit()
            with self.assertRaises(OctogroinError):
                create_duel(a, pa, 25.0, 'public')

    def test_pig_not_owned_rejected(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pb = db.session.get(Pig, ids['pb'])  # bob's pig
            with self.assertRaises(OctogroinError):
                create_duel(a, pb, 25.0, 'public')

    def test_pig_injured_rejected(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            pa.is_injured = True
            db.session.commit()
            with self.assertRaises(OctogroinError):
                create_duel(a, pa, 25.0, 'public')

    def test_cannot_engage_pig_twice(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            create_duel(a, pa, 25.0, 'public')
            with self.assertRaises(OctogroinError):
                create_duel(a, pa, 25.0, 'public')

    def test_join_duel_starts_match(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            duel = create_duel(a, pa, 25.0, 'public')
            b = db.session.get(User, ids['b'])
            pb = db.session.get(Pig, ids['pb'])
            duel = join_duel(duel, b, pb)
            self.assertEqual(duel.status, 'active')
            self.assertEqual(duel.current_round, 1)
            self.assertEqual(duel.player2_id, ids['b'])
            self.assertIsNotNone(duel.started_at)
            self.assertIsNotNone(duel.round_deadline_at)
            self.assertEqual(db.session.get(User, ids['b']).balance, 475.0)

    def test_cannot_join_own_duel(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            duel = create_duel(a, pa, 25.0, 'public')
            with self.assertRaises(OctogroinError):
                join_duel(duel, a, pa)

    def test_direct_challenge_limits_joiner(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            c = db.session.get(User, ids['c'])
            duel = create_duel(a, pa, 25.0, 'direct', challenged_user=c)
            b = db.session.get(User, ids['b'])
            pb = db.session.get(Pig, ids['pb'])
            with self.assertRaises(OctogroinError):
                join_duel(duel, b, pb)
            pc = db.session.get(Pig, ids['pc'])
            duel = join_duel(duel, c, pc)
            self.assertEqual(duel.status, 'active')

    def test_cancel_refunds_creator(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            duel = create_duel(a, pa, 25.0, 'public')
            self.assertEqual(db.session.get(User, ids['a']).balance, 475.0)
            cancel_duel(duel, a)
            self.assertEqual(duel.status, 'cancelled')
            self.assertAlmostEqual(db.session.get(User, ids['a']).balance, 500.0)
            refund = BalanceTransaction.query.filter_by(
                user_id=ids['a'], reason_code='octogroin_refund', reference_id=duel.id
            ).first()
            self.assertIsNotNone(refund)

    def test_cannot_cancel_active_duel(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            duel = create_duel(a, pa, 25.0, 'public')
            b = db.session.get(User, ids['b'])
            pb = db.session.get(Pig, ids['pb'])
            join_duel(duel, b, pb)
            with self.assertRaises(OctogroinError):
                cancel_duel(duel, a)

    def test_only_creator_can_cancel(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            duel = create_duel(a, pa, 25.0, 'public')
            b = db.session.get(User, ids['b'])
            with self.assertRaises(OctogroinError):
                cancel_duel(duel, b)

    def test_listings_filter_correctly(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            c = db.session.get(User, ids['c'])
            public_duel = create_duel(a, pa, 25.0, 'public')

            # create a second pig for alice so she can open another duel
            pa2 = _make_pig(ids['a'], 'AliceBis')
            db.session.commit()
            direct_duel = create_duel(a, pa2, 30.0, 'direct', challenged_user=c)

            open_duels = list_open_duels()
            self.assertIn(public_duel.id, [d.id for d in open_duels])
            self.assertNotIn(direct_duel.id, [d.id for d in open_duels])

            alice_duels = list_user_duels(a)
            self.assertEqual({d.id for d in alice_duels}, {public_duel.id, direct_duel.id})
            carol_duels = list_user_duels(c)
            self.assertEqual([d.id for d in carol_duels], [direct_duel.id])

    def _start_duel(self, stake=25.0, **pig_overrides):
        """Helper: create+join a duel, return the ids dict and the duel id."""
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            b = db.session.get(User, ids['b'])
            pa = db.session.get(Pig, ids['pa'])
            pb = db.session.get(Pig, ids['pb'])
            for pig in (pa, pb):
                for k, v in pig_overrides.items():
                    setattr(pig, k, v)
            db.session.commit()
            duel = create_duel(a, pa, stake, 'public')
            duel = join_duel(duel, b, pb)
            ids['duel'] = duel.id
        return ids

    def test_submit_actions_waits_for_both_then_resolves(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            b = db.session.get(User, ids['b'])
            result = submit_actions(duel, a, ['charge', 'repos', 'ancrage'])
            self.assertFalse(result['resolved'])
            duel = db.session.get(Duel, ids['duel'])
            self.assertIsNotNone(duel.round_actions_p1)
            self.assertIsNone(duel.round_actions_p2)
            self.assertEqual(duel.current_round, 1)

            result = submit_actions(duel, b, ['repos', 'charge', 'esquive'])
            self.assertTrue(result['resolved'])
            duel = db.session.get(Duel, ids['duel'])
            # After resolution either next round begins or duel finished.
            self.assertIn(duel.status, ('active', 'finished'))
            self.assertIsNotNone(duel.replay_json)

    def test_submit_rejects_bad_action_count(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            with self.assertRaises(OctogroinError):
                submit_actions(duel, a, ['charge', 'charge'])

    def test_submit_rejects_unknown_action(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            with self.assertRaises(OctogroinError):
                submit_actions(duel, a, ['charge', 'bazooka', 'repos'])

    def test_submit_rejects_non_participant(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            c = db.session.get(User, ids['c'])
            with self.assertRaises(OctogroinError):
                submit_actions(duel, c, ['charge', 'charge', 'charge'])

    def test_double_submit_same_round_rejected(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            submit_actions(duel, a, ['charge', 'repos', 'ancrage'])
            duel = db.session.get(Duel, ids['duel'])
            with self.assertRaises(OctogroinError):
                submit_actions(duel, a, ['esquive', 'esquive', 'esquive'])

    def test_finish_duel_pays_winner_with_house_tax(self):
        ids = self._start_duel(stake=100.0)
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            # Force the finish manually
            finish_duel(duel, ids['a'], reason='manual_test')
            db.session.commit()
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            self.assertEqual(duel.status, 'finished')
            self.assertEqual(duel.winner_id, ids['a'])
            # alice paid 100 at create, wins 180 (200 pot - 10% tax).
            self.assertAlmostEqual(a.balance, 500.0 - 100.0 + 180.0)
            prize = BalanceTransaction.query.filter_by(
                user_id=ids['a'], reason_code='octogroin_prize', reference_id=duel.id
            ).first()
            self.assertIsNotNone(prize)
            self.assertAlmostEqual(prize.amount, 180.0)

    def test_finish_duel_draw_refunds_both(self):
        ids = self._start_duel(stake=100.0)
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            finish_duel(duel, None, reason='draw')
            db.session.commit()
            a = db.session.get(User, ids['a'])
            b = db.session.get(User, ids['b'])
            self.assertEqual(a.balance, 500.0)
            self.assertEqual(b.balance, 500.0)

    def test_resolution_reaches_finish_in_at_most_5_rounds(self):
        """Sanity check: even with two stat-equal pigs constantly resting, the
        game eventually ends after round 5 by territorial advantage or draw."""
        ids = self._start_duel(stake=50.0)
        with self.app.app_context():
            for _ in range(5):
                duel = db.session.get(Duel, ids['duel'])
                if duel.status != 'active':
                    break
                a = db.session.get(User, ids['a'])
                b = db.session.get(User, ids['b'])
                submit_actions(duel, a, ['charge', 'charge', 'charge'])
                duel = db.session.get(Duel, ids['duel'])
                submit_actions(duel, b, ['charge', 'charge', 'charge'])
            duel = db.session.get(Duel, ids['duel'])
            self.assertEqual(duel.status, 'finished')
            self.assertIsNotNone(duel.replay_json)

    def test_get_matchup_rating_none_when_waiting(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            duel = create_duel(a, pa, 25.0, 'public')
            self.assertIsNone(get_matchup_rating(duel))

    def test_get_matchup_rating_populated_when_active(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            matchup = get_matchup_rating(duel)
            self.assertIsNotNone(matchup)
            for key in ('p1_pct', 'p2_pct', 'gap', 'level', 'favorite',
                        'p1_rating', 'p2_rating', 'stats', 'level_label'):
                self.assertIn(key, matchup)
            self.assertEqual(len(matchup['stats']), 6)

    def test_matchup_rating_independent_of_live_state(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            before = get_matchup_rating(duel)
            # Mess with live state — rating must stay the same.
            duel.pig1_position = 90.0
            duel.pig1_endurance = 5.0
            duel.pig2_position = 10.0
            duel.pig2_endurance = 95.0
            db.session.commit()
            after = get_matchup_rating(duel)
            self.assertEqual(before['p1_pct'], after['p1_pct'])
            self.assertEqual(before['p2_pct'], after['p2_pct'])
            self.assertEqual(before['favorite'], after['favorite'])

    def test_join_duel_deals_card_hands(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            b = db.session.get(User, ids['b'])
            hand_a = get_player_hand(duel, a)
            hand_b = get_player_hand(duel, b)
            self.assertEqual(len(hand_a), HAND_SIZE)
            self.assertEqual(len(hand_b), HAND_SIZE)
            for cid in hand_a + hand_b:
                self.assertIn(cid, CARDS)
            # Two distinct seeds => typically distinct hands.
            self.assertNotEqual(hand_a, hand_b)

    def test_submit_with_card_consumes_it(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            hand_before = get_player_hand(duel, a)
            chosen = hand_before[0]
            submit_actions(duel, a, ['charge', 'repos', 'ancrage'],
                           cards=[chosen, None, None])
            duel = db.session.get(Duel, ids['duel'])
            hand_after = get_player_hand(duel, a)
            self.assertNotIn(chosen, hand_after)
            self.assertEqual(len(hand_after), HAND_SIZE - 1)

    def test_submit_rejects_card_not_in_hand(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            hand = get_player_hand(duel, a)
            # Find a card NOT in the hand.
            all_ids = list(CARDS.keys())
            not_in_hand = [c for c in all_ids if c not in hand][0]
            with self.assertRaises(OctogroinError):
                submit_actions(duel, a, ['charge', 'repos', 'ancrage'],
                               cards=[not_in_hand, None, None])

    def test_submit_rejects_more_than_one_card(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            hand = get_player_hand(duel, a)
            if len(hand) < 2:
                self.skipTest("hand too small")
            with self.assertRaises(OctogroinError):
                submit_actions(duel, a, ['charge', 'repos', 'ancrage'],
                               cards=[hand[0], hand[1], None])

    def test_auto_resolve_noop_within_grace(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            # Deadline encore dans le futur → pas de résolution.
            self.assertFalse(maybe_auto_resolve_overdue(duel))
            duel = db.session.get(Duel, ids['duel'])
            self.assertEqual(duel.current_round, 1)

    def test_auto_resolve_when_both_absent_after_grace(self):
        from datetime import timedelta
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            # Force la deadline au passé + buffer + 1s
            duel.round_deadline_at = datetime.utcnow() - timedelta(seconds=FORFEIT_GRACE_SECONDS + 1)
            db.session.commit()
            duel = db.session.get(Duel, ids['duel'])
            self.assertTrue(maybe_auto_resolve_overdue(duel))
            duel = db.session.get(Duel, ids['duel'])
            # Deux Repos×3 simultanés = pas de contact, endurance max, round suivant.
            self.assertEqual(duel.current_round, 2)
            self.assertEqual(duel.pig1_endurance, 100.0)
            self.assertEqual(duel.pig2_endurance, 100.0)

    def test_auto_resolve_fills_absent_side_only(self):
        from datetime import timedelta
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            submit_actions(duel, a, ['charge', 'charge', 'charge'])
            duel = db.session.get(Duel, ids['duel'])
            duel.round_deadline_at = datetime.utcnow() - timedelta(seconds=FORFEIT_GRACE_SECONDS + 1)
            db.session.commit()
            duel = db.session.get(Duel, ids['duel'])
            self.assertTrue(maybe_auto_resolve_overdue(duel))
            duel = db.session.get(Duel, ids['duel'])
            # B a été forfaité avec Repos×3 → A a pu charger gratuitement.
            self.assertGreater(duel.pig2_position, 0.0)
            self.assertEqual(duel.current_round, 2)

    def test_auto_resolve_skips_when_both_submitted(self):
        ids = self._start_duel()
        with self.app.app_context():
            duel = db.session.get(Duel, ids['duel'])
            a = db.session.get(User, ids['a'])
            b = db.session.get(User, ids['b'])
            submit_actions(duel, a, ['repos', 'repos', 'repos'])
            duel = db.session.get(Duel, ids['duel'])
            submit_actions(duel, b, ['repos', 'repos', 'repos'])
            duel = db.session.get(Duel, ids['duel'])
            # Déjà résolu automatiquement par submit_actions ; auto-forfait est no-op.
            self.assertFalse(maybe_auto_resolve_overdue(duel))

    def test_direct_duel_hidden_from_uninvited_viewer(self):
        ids = self._fixture()
        with self.app.app_context():
            a = db.session.get(User, ids['a'])
            pa = db.session.get(Pig, ids['pa'])
            c = db.session.get(User, ids['c'])
            duel = create_duel(a, pa, 25.0, 'direct', challenged_user=c)
            b = db.session.get(User, ids['b'])
            self.assertIsNone(get_visible_duel(duel.id, b))
            self.assertIsNotNone(get_visible_duel(duel.id, c))
            self.assertIsNotNone(get_visible_duel(duel.id, a))


if __name__ == '__main__':
    unittest.main()
