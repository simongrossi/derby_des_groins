import json
import unittest

from race_engine import CourseManager


class RaceEngineTests(unittest.TestCase):
    def test_replay_contains_expected_frontend_fields(self):
        manager = CourseManager(
            participants=[
                {'id': 1, 'name': 'Rillette', 'emoji': '🐷', 'vitesse': 18, 'endurance': 18, 'force': 15, 'agilite': 14, 'strategy_profile': {'phase_1': 40, 'phase_2': 55, 'phase_3': 90}},
                {'id': 2, 'name': 'Boudin', 'emoji': '🐽', 'vitesse': 17, 'endurance': 20, 'force': 16, 'agilite': 15, 'strategy_profile': {'phase_1': 35, 'phase_2': 50, 'phase_3': 85}},
            ],
            segments=[{'type': 'PLAT', 'length': 100}, {'type': 'VIRAGE', 'length': 80}, {'type': 'DESCENTE', 'length': 120}],
        )

        history = manager.run()
        replay = json.loads(manager.to_json())

        self.assertTrue(history)
        self.assertIn('track_profile', replay)
        self.assertIn('turns', replay)
        self.assertIn('segments', replay)
        pig_turn = replay['turns'][0]['pigs'][0]
        self.assertIn('distance', pig_turn)
        self.assertIn('vitesse_actuelle', pig_turn)
        self.assertIn('fatigue', pig_turn)
        self.assertIn('visual_event', pig_turn)

    def test_recent_race_penalty_slows_runner(self):
        segments = [{'type': 'PLAT', 'length': 120}]
        manager = CourseManager(
            participants=[
                {'id': 1, 'name': 'Frais', 'emoji': '🐷', 'vitesse': 20, 'endurance': 18, 'force': 15, 'agilite': 15, 'strategy_profile': {'phase_1': 60, 'phase_2': 60, 'phase_3': 60}, 'recent_race_penalty_multiplier': 1.0},
                {'id': 2, 'name': 'Use', 'emoji': '🐽', 'vitesse': 20, 'endurance': 18, 'force': 15, 'agilite': 15, 'strategy_profile': {'phase_1': 60, 'phase_2': 60, 'phase_3': 60}, 'recent_race_penalty_multiplier': 0.9},
            ],
            segments=segments,
        )

        manager.simulate_turn()
        fresh, tired = manager.participants
        self.assertGreater(fresh.distance, tired.distance)


if __name__ == '__main__':
    unittest.main()
