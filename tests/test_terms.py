"""Deal conditions (size, shipping, subscribe) come only from what a page said.

Offline. Covers the stored-evidence extractor and the hand-read terms: a
silent page has no condition, nothing is computed from a percent, and a seen
code is never a condition.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "demo"))

import terms  # noqa: E402


def variant(size, in_stock=True):
    return {"@type": "Product", "size": size, "offers": {
        "price": "100.00", "priceCurrency": "USD",
        "availability": "https://schema.org/" + ("InStock" if in_stock else "OutOfStock")}}


class FromEvidenceTest(unittest.TestCase):
    def test_shoe_sizes_and_stock_come_from_variants(self):
        ev = {"json_ld": [{"name": "Runner", "hasVariant": [
            variant("8"), variant("8.5", False), variant("9")]}]}
        t = terms.from_evidence(ev, "Shoes")
        self.assertEqual(t["group"], "shoe")
        self.assertEqual([(s["k"], s["ok"]) for s in t["sizes"]],
                         [("8", True), ("8.5", False), ("9", True)])
        self.assertNotIn("ship", t)

    def test_no_stated_size_means_no_size_group(self):
        t = terms.from_evidence({"json_ld": [{"name": "Charm"}]}, "Shoes")
        self.assertEqual(t, {"group": None, "sizes": []})
        t = terms.from_evidence({"json_ld": []}, "Shoes")
        self.assertEqual(t, {"group": None, "sizes": []})

    def test_numbers_on_a_non_shoe_are_not_shoe_sizes(self):
        ev = {"json_ld": [{"hasVariant": [variant("8"), variant("9")]}]}
        self.assertIsNone(terms.from_evidence(ev, "Kitchen")["group"])
        self.assertEqual(terms.from_evidence(ev, "Kitchen")["sizes"], [])

    def test_clothing_letters(self):
        ev = {"json_ld": [{"hasVariant": [variant("XS"), variant("M - 40")]}]}
        self.assertEqual(terms.from_evidence(ev, "Clothing")["group"], "clothing")

    def test_shipping_only_when_the_page_published_it(self):
        def offer(sd):
            return {"json_ld": [{"offers": {"price": "5", "shippingDetails": sd}}]}
        free = terms.from_evidence(
            offer({"shippingRate": {"value": "0", "currency": "USD"}}), "Pantry")
        self.assertEqual(free["ship"]["k"], "free")
        cost = terms.from_evidence(
            offer({"shippingRate": {"value": "6.5", "currency": "USD"}}), "Pantry")
        self.assertEqual((cost["ship"]["k"], cost["ship"]["rate"]), ("cost", 650))
        thr = terms.from_evidence(offer({
            "freeShippingThreshold": {"value": "100.00", "currency": "USD"},
            "doesNotShip": [{"name": "Non-US"}]}), "Grooming")
        self.assertEqual((thr["ship"]["k"], thr["ship"]["over"]), ("threshold", 10000))
        self.assertFalse(thr["ship"]["members"])
        silent = terms.from_evidence({"json_ld": [{"offers": {"price": "5"}}]}, "Pantry")
        self.assertNotIn("ship", silent)

    def test_stored_catalog_has_no_invented_subscribe_terms(self):
        evidence = os.path.join(ROOT, "demo", "evidence")
        checked = 0
        for fn in sorted(os.listdir(evidence)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(evidence, fn)) as f:
                ev = json.load(f)
            t = terms.from_evidence(ev, ev.get("kind", ""))
            self.assertNotIn("sub", t, fn)
            for s in t["sizes"]:
                self.assertIsNone(s["c"], fn)
                self.assertIsNone(s["s"], fn)
            checked += 1
        self.assertGreater(checked, 100)


class HandTermsTest(unittest.TestCase):
    def test_every_hand_product_is_covered_with_its_source(self):
        self.assertEqual(sorted(terms.HAND), sorted(
            ["cof1", "cof2", "cof3", "hcr", "wel", "ccc",
             "apple", "oldnavy", "gap", "nike"]))
        for key, t in terms.HAND.items():
            url, when = t["src"]
            self.assertTrue(url.startswith("https://"), key)
            self.assertTrue(when.startswith("2026-10-02T"), key)

    def test_subscribe_prices_are_printed_ones_never_computed(self):
        for key, t in terms.HAND.items():
            for s in t["sizes"]:
                if s["s"] is not None:
                    self.assertLess(s["s"], s["c"], key)
                    self.assertIsNone(s["sp"], key)
                    self.assertIn("sub", t, key)
        # Lavazza prints only a percent, so there is no subscribe price at all.
        for key in ("cof1", "cof2", "cof3"):
            for s in terms.HAND[key]["sizes"]:
                self.assertIsNone(s["s"])
                self.assertEqual(s["sp"], 25)

    def test_stated_sizes_prices_and_shipping_lines(self):
        by = {s["k"]: s for s in terms.HAND["ccc"]["sizes"]}
        self.assertEqual((by["12 oz"]["c"], by["12 oz"]["s"]), (1950, 1750))
        self.assertEqual((by["24 oz"]["c"], by["24 oz"]["s"]), (3750, 3366))
        self.assertEqual((by["5 lb"]["c"], by["5 lb"]["s"]), (10100, 9065))
        self.assertEqual(terms.HAND["ccc"]["ship"]["over"], 3000)
        self.assertEqual(terms.HAND["wel"]["ship"]["over"], 7500)
        self.assertNotIn("ship", terms.HAND["hcr"])  # the page said nothing
        for key in ("oldnavy", "gap", "nike"):
            self.assertTrue(terms.HAND[key]["ship"]["members"], key)
        self.assertNotIn("sub", terms.HAND["apple"])
        self.assertNotIn("sub", terms.HAND["nike"])


if __name__ == "__main__":
    unittest.main()
