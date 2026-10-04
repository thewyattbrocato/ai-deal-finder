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
            self.assertTrue(when.startswith(("2026-10-02T", "2026-10-03T", "2026-10-04T")), key)

    def test_hand_cards_carry_the_2026_10_03_observation_and_keep_history(self):
        import json
        with open(os.path.join(ROOT, "demo", "index.html"), encoding="utf-8") as f:
            page = f.read()
        first_seen = {"apple": "2026-10-01T19:50:52Z",
                      "oldnavy": "2026-10-01T19:50:21Z",
                      "gap": "2026-10-01T19:50:30Z",
                      "nike": "2026-10-01T19:50:41Z"}
        prices = {"apple": 249.0, "oldnavy": 25.0, "gap": 79.95, "nike": 87.97}
        for slug, first in first_seen.items():
            rec = terms.handcard_record(slug)
            obs = rec["observations"]
            # the earlier price read and the 2026-10-02 conditions read stay
            self.assertEqual(obs[0]["observed_at"], first, slug)
            self.assertEqual(obs[1]["observed_at"][:10], "2026-10-02", slug)
            latest = obs[-1]
            # Old Navy was read again 2026-10-04 (unchanged); the 2026-10-03 read stays
            if slug == "oldnavy":
                self.assertEqual(obs[2]["observed_at"], "2026-10-03T23:15:26Z")
                self.assertEqual(latest["observed_at"][:10], "2026-10-04", slug)
            else:
                self.assertEqual(latest["observed_at"][:10], "2026-10-03", slug)
            self.assertEqual(latest["shelf_price"], prices[slug], slug)
            self.assertFalse(latest.get("code_tried", False), slug)
            # the card's "Checked" stamp and the terms source are that read
            self.assertEqual(terms.HAND[slug]["src"][1], latest["observed_at"], slug)
            self.assertIn(rec["page_url"], page, slug)
            self.assertIn(latest["observed_at"], page, slug)
            self.assertNotIn(first, page, slug)
            # sizes and shipping on the card are what the latest read printed
            if latest["sizes"]:
                self.assertEqual(
                    [(s["k"], s["ok"]) for s in terms.HAND[slug]["sizes"]],
                    [(k, ok) for k, ok in latest["sizes"]], slug)
        # Gap: S and XL were selectable on 2026-10-02 and are not now
        gap = terms.handcard_record("gap")["observations"]
        self.assertEqual([k for k, ok in gap[1]["sizes"] if ok],
                         ["XXS", "XS", "S", "XL"])
        self.assertEqual([k for k, ok in gap[-1]["sizes"] if ok], ["XXS", "XS"])
        # a code seen is recorded as seen; no hand card has a code tried
        on = terms.handcard_record("oldnavy")["observations"][-1]
        self.assertTrue(any("Code: EXTRA" in x for x in on["offer_texts"]))
        self.assertFalse(on["code_tried"])

    def test_coffee_hand_cards_carry_the_2026_10_04_read_and_keep_history(self):
        with open(os.path.join(ROOT, "demo", "index.html"), encoding="utf-8") as f:
            page = f.read()
        first = {"hcr": "2026-10-02T15:00:17Z", "wel": "2026-10-02T15:01:25Z",
                 "ccc": "2026-10-02T15:03:57Z"}
        shelf = {"hcr": 18.0, "wel": 20.5, "ccc": 19.5}
        for slug, t0 in first.items():
            rec = terms.handcard_record(slug)
            obs = rec["observations"]
            self.assertEqual(len(obs), 3, slug)
            # the first price read and the 2026-10-02 conditions read stay
            self.assertEqual(obs[0]["observed_at"], t0, slug)
            self.assertEqual(obs[1]["observed_at"][:10], "2026-10-02", slug)
            latest = obs[-1]
            self.assertEqual(latest["observed_at"][:10], "2026-10-04", slug)
            self.assertEqual(latest["shelf_price"], shelf[slug], slug)
            self.assertFalse(latest["code_tried"], slug)
            # no coupon: the only offer text any read stored is an email-gated
            # signup (Well), which prints no code
            for o in obs:
                for text in o["offer_texts"]:
                    self.assertNotRegex(text, r"\b(?i:code)\s*:?\s*[A-Z][A-Z0-9]{3,}\b", slug)
            self.assertEqual(terms.HAND[slug]["src"][1], latest["observed_at"], slug)
            self.assertIn(rec["page_url"], page, slug)
            self.assertIn("Checked: " + rec["page_url"].split("/")[2].replace("www.", "")
                          + " · US · " + latest["observed_at"], page, slug)
            self.assertNotIn(t0, page, slug)
            # per-size one-time and subscribe prices on the card are what the read printed
            self.assertEqual(
                [(z["k"].replace(" ", ""), z["c"], z["s"]) for z in terms.HAND[slug]["sizes"]],
                [(k.replace(" ", ""), round(c * 100), round(s * 100)) for k, c, s in latest["size_prices"]], slug)
            # the card's terms are the earlier read's, unchanged
            self.assertEqual(latest["size_prices"], obs[1]["size_prices"], slug)
        self.assertNotIn("ship", terms.HAND["hcr"])  # still no shipping text on the page
        self.assertEqual(terms.handcard_record("hcr")["observations"][-1]["shipping"], [])
        self.assertIn("Free Shipping On All Orders $75+",
                      terms.handcard_record("wel")["observations"][-1]["shipping"])
        self.assertIn("Free shipping on $30 & up!",
                      terms.handcard_record("ccc")["observations"][-1]["shipping"])

    def test_lavazza_terms_are_the_2026_10_04_read(self):
        import glob
        for fn in glob.glob(os.path.join(ROOT, "demo", "evidence", "lavazza", "*.json")):
            with open(fn, encoding="utf-8") as f:
                rec = json.load(f)
            latest = rec["observations"][-1]
            self.assertEqual(latest["observed_at"][:10], "2026-10-04", fn)
            self.assertEqual(latest["code"], "AS20", fn)
            self.assertEqual(latest["shipping"],
                             ["Fast delivery on all orders. Free delivery on orders over $50"], fn)
            self.assertEqual(len(rec["observations"]), 3, fn)

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
