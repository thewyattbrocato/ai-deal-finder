"""Quiet public page: guide, two-search explanation, coffee note.

Checks the generated demo/index.html and its GitHub Pages copy
docs/index.html. Offline; no invented products, prices, or coupons.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class QuietPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = read("demo", "index.html")

    def test_pages_copy_matches_demo(self):
        self.assertEqual(self.page, read("docs", "index.html"))

    def test_quiet_default_has_no_extras(self):
        for gone in ("stats", "Compare at a glance", "kind-btn",
                     'id="coupon-only"', 'id="sort"', "Everything checked"):
            self.assertNotIn(gone, self.page, gone)

    def test_single_copy_of_each_product(self):
        names = re.findall(r'data-name="([^"]*)"', self.page)
        self.assertTrue(names)
        self.assertEqual(len(names), len(set(names)))

    def test_guide_is_optional_one_question_at_a_time(self):
        for text in ("What matters most?", "Whole bean or any coffee?",
                     "Only products whose page printed a coupon?",
                     '"Skip"', "Specialty-roaster quality"):
            self.assertIn(text, self.page, text)
        # The list is outside the guide and never hidden by it.
        self.assertLess(self.page.index('id="guide"'),
                        self.page.index('id="results"'))

    def test_two_search_explanation(self):
        self.assertIn("similar checked products", self.page)
        self.assertIn("only when that product's own page printed it", self.page)
        self.assertIn("one named item", self.page)
        self.assertIn("the price shown is the shelf price", self.page)

    def test_coffee_note_matches_evidence(self):
        m = re.search(r"Coffee note: ([^<]*)", self.page)
        self.assertIsNotNone(m)
        note = m.group(1)
        self.assertIn("Dolcevita Classico, Qualità Rossa and Super Crema "
                      "showed the code CAFE20", note)
        for seller in ("Honest Coffee Roasters", "The Well Coffee Roasters",
                       "Counter Culture Coffee"):
            self.assertIn(seller, note)
        self.assertIn("shelf price", note)

    def test_coupon_cards_match_note(self):
        cards = re.split(r'(?=<section class="card)', self.page)
        with_code = {re.search(r'data-name="([^"]*)"', c).group(1)
                     for c in cards if 'data-coupon="yes"' in c
                     and "CAFE20" in c}
        self.assertEqual(len(with_code), 3)
        for c in cards:
            if "Midnight Axes" in c or "Watershed" in c or "Big Trouble" in c:
                self.assertIn('data-coupon="no"', c)

    def test_exact_search_resolves_to_one_named_item(self):
        self.assertIn("named.slice(0, 1)", self.page)


if __name__ == "__main__":
    unittest.main()
