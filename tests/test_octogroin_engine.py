import random
import unittest

from services.octogroin_engine import (
    ACTIONS,
    COMBAT_RATING_WEIGHTS,
    ENDURANCE_DELTA,
    PigState,
    compute_combat_rating,
    compute_matchup_odds,
    evaluate_end_of_duel,
    resolve_round,
)


def make_pig(**overrides):
    base = dict(
        force=60.0, weight_kg=112.0, agilite=60.0,
        intelligence=60.0, moral=60.0, vitesse=60.0,
        position=0.0, endurance=100.0,
    )
    base.update(overrides)
    return PigState(**base)


class EngineResolutionTests(unittest.TestCase):
    def test_all_actions_in_allowed_set(self):
        self.assertEqual(set(ACTIONS), {'charge', 'ancrage', 'esquive', 'repos'})
        self.assertTrue(all(a in ENDURANCE_DELTA for a in ACTIONS))

    def test_charge_costs_endurance_and_pushes_opponent(self):
        p1, p2, events = resolve_round(
            make_pig(), make_pig(agilite=0.0),
            ['charge', 'charge', 'charge'],
            ['repos', 'repos', 'repos'],
            round_number=1, rng=random.Random(0),
        )
        self.assertLess(p1.endurance, 100.0)
        self.assertGreater(p2.position, 0.0)
        self.assertEqual(len(events), 3)
        for ev in events:
            self.assertEqual(ev['outcome'], 'p1_crit_on_rest')

    def test_ancrage_counters_charge_and_punishes_attacker(self):
        p1, p2, events = resolve_round(
            make_pig(), make_pig(),
            ['charge', 'charge', 'charge'],
            ['ancrage', 'ancrage', 'ancrage'],
            round_number=1, rng=random.Random(0),
        )
        # Attacker pays charge cost (-20) + splat penalty (-30) per pair. After
        # the 2nd pair endurance hits the floor so the 3rd charge is essoufflé.
        self.assertLess(p1.endurance, p2.endurance)
        self.assertEqual(p2.position, 0.0)
        self.assertGreaterEqual(
            sum(1 for ev in events if ev['outcome'] == 'p1_splat_on_ancrage'), 1
        )

    def test_esquive_high_agility_sends_attacker_backwards(self):
        p1, p2, events = resolve_round(
            make_pig(force=80.0, agilite=0.0),
            make_pig(agilite=100.0),
            ['charge', 'charge', 'charge'],
            ['esquive', 'esquive', 'esquive'],
            round_number=1, rng=random.Random(0),
        )
        # Dodger has 95% chance ⇒ attacker slides toward own edge on most steps.
        self.assertGreater(p1.position, 0.0)
        self.assertEqual(p2.position, 0.0)
        self.assertTrue(
            any(ev['outcome'] == 'p1_whiffs_p2_dodges' for ev in events)
        )

    def test_clash_charge_vs_charge_stronger_wins(self):
        strong = make_pig(force=90.0, weight_kg=140.0, vitesse=70.0)
        weak = make_pig(force=40.0, weight_kg=90.0, vitesse=40.0)
        p1, p2, events = resolve_round(
            strong, weak,
            ['charge'] * 3, ['charge'] * 3,
            round_number=1, rng=random.Random(0),
        )
        self.assertGreater(p2.position, p1.position)
        self.assertTrue(all(ev['outcome'] == 'clash_p1_wins' for ev in events))

    def test_essouffle_pig_action_fails(self):
        tired = make_pig(endurance=0.0)
        p1, p2, events = resolve_round(
            tired, make_pig(),
            ['charge', 'charge', 'charge'],
            ['charge', 'repos', 'ancrage'],
            round_number=1, rng=random.Random(0),
        )
        # P1 should be marked essouffle on every step and take P2's pushes.
        for ev in events:
            self.assertTrue(ev['p1_essouffle'])
            self.assertEqual(ev['p1_action'], 'null')

    def test_repos_recovers_endurance(self):
        p = make_pig(endurance=30.0)
        p1, _p2, _ev = resolve_round(
            p, make_pig(),
            ['repos', 'repos', 'repos'],
            ['repos', 'repos', 'repos'],
            round_number=1, rng=random.Random(0),
        )
        # 3 x +25 capped at 100
        self.assertEqual(p1.endurance, 100.0)

    def test_invalid_action_raises(self):
        with self.assertRaises(ValueError):
            resolve_round(
                make_pig(), make_pig(),
                ['charge', 'charge', 'bogus'],
                ['repos', 'repos', 'repos'],
                round_number=1,
            )

    def test_wrong_action_count_raises(self):
        with self.assertRaises(ValueError):
            resolve_round(
                make_pig(), make_pig(),
                ['charge'], ['repos', 'repos', 'repos'],
                round_number=1,
            )

    def test_input_snapshots_not_mutated(self):
        p1 = make_pig()
        p2 = make_pig()
        p1_after, p2_after, _events = resolve_round(
            p1, p2,
            ['charge'] * 3, ['repos'] * 3,
            round_number=1, rng=random.Random(0),
        )
        self.assertEqual(p1.endurance, 100.0)
        self.assertEqual(p1.position, 0.0)
        self.assertNotEqual(p1_after.endurance, p1.endurance)

    def test_round_stops_on_knockout(self):
        # High-force crit on repos can push hard. Force the position near edge.
        p1 = make_pig(force=100.0)
        p2 = make_pig(position=99.5)
        p1_after, p2_after, events = resolve_round(
            p1, p2,
            ['charge', 'charge', 'charge'],
            ['repos', 'repos', 'repos'],
            round_number=3, rng=random.Random(0),
        )
        self.assertGreaterEqual(p2_after.position, 100.0)
        self.assertEqual(len(events), 1)

    def test_evaluate_knockout(self):
        p1 = make_pig(position=100.0)
        p2 = make_pig(position=20.0)
        v = evaluate_end_of_duel(p1, p2, 2)
        self.assertTrue(v['ended'])
        self.assertEqual(v['winner'], 'p2')
        self.assertEqual(v['reason'], 'knockout_p1')

    def test_evaluate_territorial_after_round_5(self):
        p1 = make_pig(position=30.0)
        p2 = make_pig(position=60.0)
        v = evaluate_end_of_duel(p1, p2, 5)
        self.assertTrue(v['ended'])
        self.assertEqual(v['winner'], 'p1')

    def test_evaluate_draw(self):
        p1 = make_pig(position=40.0)
        p2 = make_pig(position=40.0)
        v = evaluate_end_of_duel(p1, p2, 5)
        self.assertTrue(v['ended'])
        self.assertEqual(v['winner'], 'draw')

    def test_evaluate_mid_duel(self):
        v = evaluate_end_of_duel(make_pig(position=20.0), make_pig(position=30.0), 2)
        self.assertFalse(v['ended'])


class MatchupRatingTests(unittest.TestCase):
    def test_rating_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(COMBAT_RATING_WEIGHTS.values()), 1.0, places=6)

    def test_rating_in_bounds(self):
        # All stats at their cap → rating near 100
        max_pig = PigState(force=100, weight_kg=200, agilite=100,
                           intelligence=100, moral=100, vitesse=100,
                           position=0, endurance=100)
        self.assertAlmostEqual(compute_combat_rating(max_pig), 100.0, places=1)

        # All stats at 0 → rating 0
        min_pig = PigState(force=0, weight_kg=0, agilite=0,
                           intelligence=0, moral=0, vitesse=0,
                           position=0, endurance=0)
        self.assertEqual(compute_combat_rating(min_pig), 0.0)

    def test_rating_force_dominates(self):
        # Only force differs — the pig with more force has a higher rating.
        base = dict(weight_kg=112, agilite=60, intelligence=60, moral=60,
                    vitesse=60, position=0, endurance=100)
        low = PigState(force=60, **base)
        high = PigState(force=90, **base)
        self.assertGreater(compute_combat_rating(high), compute_combat_rating(low))

    def test_rating_clamps_above_cap(self):
        # Pathological: a stat overflow should not push rating past 100.
        overflow = PigState(force=9999, weight_kg=9999, agilite=9999,
                            intelligence=9999, moral=9999, vitesse=9999,
                            position=0, endurance=100)
        self.assertLessEqual(compute_combat_rating(overflow), 100.0)

    def test_odds_symmetric_for_identical_pigs(self):
        p = PigState(force=60, weight_kg=112, agilite=60,
                     intelligence=60, moral=60, vitesse=60,
                     position=0, endurance=100)
        odds = compute_matchup_odds(p, PigState(**p.to_dict()))
        self.assertEqual(odds['p1_pct'], 50.0)
        self.assertEqual(odds['p2_pct'], 50.0)
        self.assertEqual(odds['level'], 'even')
        self.assertIsNone(odds['favorite'])

    def test_odds_huge_gap_flags_huge_level(self):
        strong = PigState(force=100, weight_kg=200, agilite=100,
                          intelligence=100, moral=100, vitesse=100,
                          position=0, endurance=100)
        weak = PigState(force=10, weight_kg=75, agilite=10,
                        intelligence=10, moral=10, vitesse=10,
                        position=0, endurance=100)
        odds = compute_matchup_odds(strong, weak)
        self.assertEqual(odds['favorite'], 'p1')
        self.assertGreater(odds['p1_pct'], 65.0)
        self.assertEqual(odds['level'], 'huge')

    def test_odds_levels_cover_each_threshold(self):
        # Build synthetic pairs where only `force` varies so we can tune the gap.
        def mkpig(force):
            return PigState(force=force, weight_kg=112, agilite=60,
                            intelligence=60, moral=60, vitesse=60,
                            position=0, endurance=100)

        # Equal → even
        self.assertEqual(compute_matchup_odds(mkpig(60), mkpig(60))['level'], 'even')
        # Moderate force delta → slight (gap ~12 points)
        self.assertEqual(compute_matchup_odds(mkpig(40), mkpig(80))['level'], 'slight')
        # Big force delta → marked (gap ~24 points)
        self.assertEqual(compute_matchup_odds(mkpig(20), mkpig(100))['level'], 'marked')
        # Extreme: 'huge' is covered by test_odds_huge_gap_flags_huge_level.

    def test_stats_block_shape(self):
        p = PigState(force=60, weight_kg=112, agilite=60,
                     intelligence=60, moral=60, vitesse=60,
                     position=0, endurance=100)
        odds = compute_matchup_odds(p, p)
        self.assertEqual(len(odds['stats']), 6)
        for entry in odds['stats']:
            for key in ('key', 'label', 'p1', 'p2', 'max'):
                self.assertIn(key, entry)


if __name__ == '__main__':
    unittest.main()
