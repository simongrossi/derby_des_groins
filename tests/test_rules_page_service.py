import unittest

from services.rules_page_service import _fmt_number, _format_stat_changes, build_rules_page_context
from tests.support import build_test_app, reset_database


class RulesPageServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)

    def test_fmt_number_formats_ints_and_decimals(self):
        self.assertEqual('12', _fmt_number(12))
        self.assertEqual('12.5', _fmt_number(12.5))
        self.assertEqual('abc', _fmt_number('abc'))

    def test_format_stat_changes_ignores_zeroish_values(self):
        result = _format_stat_changes({'vitesse': 2, 'force': -1, 'moral': 0.0001})

        self.assertIn('+2 VIT', result)
        self.assertIn('-1 FOR', result)
        self.assertNotIn('MOR', result)

    def test_build_rules_page_context_returns_render_ready_sections(self):
        with self.app.app_context():
            context = build_rules_page_context()

        self.assertGreater(len(context['hero_cards']), 0)
        self.assertGreater(len(context['bet_rows']), 0)
        self.assertGreater(len(context['sections']), 0)
        self.assertIn('Fenêtre vétérinaire', {card['label'] for card in context['hero_cards']})


if __name__ == '__main__':
    unittest.main()
