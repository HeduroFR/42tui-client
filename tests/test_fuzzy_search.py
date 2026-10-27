import json
import unittest
from pathlib import Path
from ft_tui.shared.fuzzy_search import fuzzy_score


class FuzzySearchTests(unittest.TestCase):
    def test_shared_matching_and_scoring_contract(self):
        cases = json.loads((Path(__file__).parent / 'fixtures/fuzzy_search.json').read_text())
        for case in cases:
            with self.subTest(query=case['query'], fields=case['fields']):
                self.assertEqual(fuzzy_score(case['query'], *case['fields']), case['score'])

    def test_exact_prefix_substring_abbreviation_and_typo_order(self):
        self.assertLess(fuzzy_score('alice', 'alice'), fuzzy_score('alice', 'alicex'))
        self.assertLess(fuzzy_score('alice', 'alicex'), fuzzy_score('alice', 'xalicex'))
        self.assertLess(fuzzy_score('alice', 'xalicex'), fuzzy_score('alice', 'axlxixcxe'))
        self.assertLess(fuzzy_score('alice', 'axlxixcxe'), fuzzy_score('alice', 'ailce'))

    def test_long_queries_skip_expensive_typo_matching(self):
        self.assertEqual(fuzzy_score('a' * 512, 'a' * 512), 0)
        self.assertIsNone(fuzzy_score('a' * 512, 'b' * 512))
