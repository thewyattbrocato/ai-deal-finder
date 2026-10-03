"""No product on the search-first page can become unfindable by its own words.

tests/findability_driver.js types, through the page's own engine, every product's exact name, each
distinct word of its name and each adjacent word pair. tests/union_driver.js checks the compound-word
rule on a small made-up catalog: a joined or split reading adds products and never takes one away.
"""
import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "demo", "index.html")


def run(script):
    proc = subprocess.run(["node", os.path.join(ROOT, "tests", script), PAGE],
                          check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


class EveryProductFindableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = run("findability_driver.js")

    def test_every_product_is_found_by_its_exact_name_each_word_and_each_adjacent_pair(self):
        self.assertGreater(self.d["products"], 300)
        self.assertEqual(self.d["misses"], [])

    def test_no_query_is_empty_when_the_same_words_in_another_spacing_find_products(self):
        self.assertEqual(self.d["zeroDespiteOtherSpacing"], [])


class CompoundRuleIsAUnionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run("union_driver.js")

    def test_12_oz_finds_the_split_product_and_the_joined_product(self):
        self.assertEqual(self.r["12 oz"], ["Himalayan Green Tea, 12 oz", "Sparkling Water 12oz Can"])
        self.assertEqual(self.r["12oz"], self.r["12 oz"])

    def test_the_literal_words_always_work_beside_a_joined_word(self):
        self.assertEqual(self.r["green tea 12 oz"], ["Himalayan Green Tea, 12 oz"])
        self.assertEqual(self.r["tea 12 oz"], ["Himalayan Green Tea, 12 oz"])
        self.assertEqual(self.r["tea 12oz"], ["Himalayan Green Tea, 12 oz"])

    def test_sweat_pants_still_finds_sweatpants_and_oliveoil_still_finds_olive_oil(self):
        self.assertIn("Sweatpants Fleece", self.r["sweat pants"])
        self.assertIn("Sweat Band Pants Set", self.r["sweat pants"])  # the words as typed still count
        self.assertIn("Extra Virgin Olive Oil", self.r["oliveoil"])
        self.assertEqual(self.r["oliveoil"], self.r["olive oil"])


if __name__ == "__main__":
    unittest.main()
