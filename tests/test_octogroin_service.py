import unittest
from datetime import datetime

from config.game_rules import PIG_DEFAULTS
from extensions import db
from models import BalanceTransaction, Duel, Pig, User
from services.octogroin_service import (
    OctogroinError,
    cancel_duel,
    create_duel,
    finish_duel,
    join_duel,
    list_open_duels,
    list_user_duels,
    get_visible_duel,
    submit_actions,
)
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
