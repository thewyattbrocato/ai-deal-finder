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
            c = ev.get("conditions") or {}
            if "sub" in t:  # only from a subscribe offer line the page printed
                self.assertTrue(any(terms._SUB_OFFER.search(l)
                                    for l in c.get("sub", [])), fn)
            for s in t["sizes"]:
                self.assertIsNone(s["c"], fn)
                self.assertIsNone(s["s"], fn)
            checked += 1
        self.assertGreater(checked, 100)


class ReadConditionsTest(unittest.TestCase):
    def lines(self, ship=(), sub=()):
        return {"conditions": {"ship": list(ship), "sub": list(sub),
                               "url": "https://x.test/p", "read_at": "2026-10-03T14:00:00Z"},
                "json_ld": [{"name": "P"}]}

    def ship(self, *lines):
        return terms.conditions_from_evidence(self.lines(ship=lines))[0]

    def test_threshold_read_from_the_pages_own_line(self):
        s = self.ship("Free ground shipping on orders over $100")
        self.assertEqual((s["k"], s["over"], s["members"]), ("threshold", 10000, False))
        self.assertIn("orders over $100", s["t"])

    def test_members_only_threshold_is_marked_members(self):
        s = self.ship("FREE SHIPPING ON ORDERS $50+ FOR COLLECTIVE MEMBERS")
        self.assertTrue(s["members"])

    def test_silent_or_ambiguous_lines_stay_unknown(self):
        self.assertIsNone(self.ship("Shipping", "Shipping calculated at checkout"))
        self.assertIsNone(self.ship("Free shipping"))                  # no minimum stated
        self.assertIsNone(self.ship("Free returns on orders over $50"))
        self.assertIsNone(self.ship("Spend $100 more to earn free shipping!"))
        self.assertIsNone(self.ship("Free international shipping over $200"))
        self.assertIsNone(self.ship("FREE SHIPPING FOR VIPS | $150+ FOR NON MEMBERS"))
        self.assertIsNone(self.ship("Free shipping over $50", "Free shipping over $75"))

    def test_every_order_free_shipping(self):
        self.assertEqual(self.ship("FREE SHIPPING ON EVERY ORDER | 60 DAYS RETURN")["k"], "free")

    def test_subscribe_needs_an_offer_not_a_newsletter(self):
        sub = lambda *l: terms.conditions_from_evidence(self.lines(sub=l))[1]
        self.assertIsNone(sub("SUBSCRIBE TO OUR EMAILS", "Subscribe", "Manage Subscription"))
        self.assertIsNone(sub("Subscribe to our newsletter and save & subscribe"))
        got = sub("Subscribe & Save")
        self.assertIn("price itself is not shown", got["t"])

    def test_source_and_date_travel_with_the_condition(self):
        ev = self.lines(ship=["Free Shipping Over $50"])
        t = terms.from_evidence(ev, "Pantry")
        self.assertEqual(t["src"], ("https://x.test/p", "2026-10-03T14:00:00Z"))
        self.assertEqual(t["ship"]["over"], 5000)
        self.assertNotIn("src", terms.from_evidence({"json_ld": [{"name": "P"}]}, "Pantry"))

    def test_page_json_ld_shipping_wins_over_text(self):
        ev = self.lines(ship=["Free shipping over $99"])
        ev["json_ld"] = [{"offers": {"price": "5", "shippingDetails": {
            "shippingRate": {"value": "0", "currency": "USD"}}}}]
        self.assertEqual(terms.from_evidence(ev, "Pantry")["ship"]["k"], "free")

    def test_stored_reread_covers_at_least_sixty_products_across_merchants(self):
        evidence = os.path.join(ROOT, "demo", "evidence")
        got, merchants = 0, set()
        for fn in sorted(os.listdir(evidence)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(evidence, fn)) as f:
                ev = json.load(f)
            t = terms.from_evidence(ev, ev.get("kind", ""))
            if "ship" in t or "sub" in t:
                got += 1
                merchants.add(fn.split("-")[0])
                self.assertTrue(ev.get("conditions") or ev.get("json_ld"), fn)
            if ev.get("conditions") and ("ship" in t) and not terms._shipping(ev["json_ld"]):
                # the quoted line must be literally in the stored page text
                quoted = t["ship"]["t"].strip("\u201c\u201d")
                self.assertTrue(any(quoted in l for l in ev["conditions"]["ship"]), fn)
        self.assertGreaterEqual(got, 60)
        self.assertGreaterEqual(len(merchants), 15)


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
