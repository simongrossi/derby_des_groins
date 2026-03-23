import unittest

from routes.blackjack import build_deck, hand_value


class BlackjackTests(unittest.TestCase):
    def test_build_deck_contains_54_cards_and_two_jokers(self):
        deck = build_deck()

        self.assertEqual(len(deck), 54)
        self.assertEqual(sum(1 for card in deck if card['is_joker']), 2)

    def test_hand_value_uses_soft_aces(self):
        hand = [
            {'rank': 'A', 'suit': '♠', 'value': [1, 11], 'is_joker': False},
            {'rank': '9', 'suit': '♦', 'value': 9, 'is_joker': False},
            {'rank': 'A', 'suit': '♥', 'value': [1, 11], 'is_joker': False},
        ]

        self.assertEqual(hand_value(hand), 21)

    def test_hand_value_ignores_jokers(self):
        hand = [
            {'rank': 'JOKER', 'suit': '🃏', 'value': 0, 'is_joker': True},
            {'rank': 'K', 'suit': '♣', 'value': 10, 'is_joker': False},
            {'rank': 'Q', 'suit': '♠', 'value': 10, 'is_joker': False},
        ]

        self.assertEqual(hand_value(hand), 20)


if __name__ == '__main__':
    unittest.main()
