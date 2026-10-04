"""Stored page shipping lines are quoted, never read; sizes span colours.

Offline: stored evidence, demo/terms.py and the built page. A quoted line is
what the page printed, not a known shipping fact; a size is in stock if the
page shows it in stock for any colour.
"""

import html as html_lib
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "demo"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import terms  # noqa: E402
from test_readiness import card_terms, cards, stored  # noqa: E402
from test_page import read  # noqa: E402

IN = "https://schema.org/InStock"
OUT = "https://schema.org/OutOfStock"


def ev_with(lines):
    return {"json_ld": [{"@type": "Product", "name": "x"}],
            "conditions": {"ship": lines, "url": "u", "read_at": "t"}}


def variant(color, size, avail):
    return {"@type": "Product", "color": color, "size": size,
            "offers": {"@type": "Offer", "availability": avail, "price": "10"}}


class QuotedShippingLines(unittest.TestCase):
    def test_a_plain_threshold_sentence_is_read(self):
        t = terms.from_evidence(ev_with(["FREE SHIPPING OVER $99. FREE RETURNS."]), None)
        self.assertEqual((t["ship"]["k"], t["ship"]["over"]), ("threshold", 9900))
        self.assertNotIn("ship_quoted", t)

    def test_qualified_wording_is_never_read_only_quoted(self):
        for line in (
            "Free shipping over USD$69 (except Stand Power Set/Smart Mat)",
            "FREE SHIPPING OVER $99 FOR VIP MEMBERS",
            "Free shipping over $50. Returns only by mail.",
            "Free shipping over $50. Members only.",
            "Free shipping over $50 in the contiguous US",
            "Free shipping over $50 excluding Hawaii and Alaska",
            "Free returns over $50",
            "FREE SHIPPING OVER $99. Free returns for members.",
            "Free ground shipping on orders over $75.",
            "FREE STANDARD SHIPPING W/ $50 ORDER.",
        ):
            self.assertIsNone(terms._plain_threshold(line), line)
            if "contiguous" not in line and "ground" not in line:  # the strict extractor reads those itself
                t = terms.from_evidence(ev_with([line]), None)
                self.assertNotIn("ship", t, line)

    def test_member_threshold_is_flagged_members_never_plain(self):
        t = terms.from_evidence(ev_with(["Members enjoy FREE SHIPPING over $49+."]), None)
        self.assertTrue(t["ship"]["members"])

    def test_a_threshold_conflicting_with_another_line_is_not_read(self):
        t = terms.from_evidence(ev_with(
            ["Free shipping over $175", "Members get free shipping over $49"]), None)
        self.assertNotIn("ship", t)
        self.assertEqual(t["ship_quoted"][0], "Free shipping over $175")

    def test_an_unread_statement_is_quoted_verbatim(self):
        t = terms.from_evidence(ev_with(["Shipping", "FREE SHIPPING OVER $99 FOR VIPS"]), None)
        self.assertEqual(t["ship_quoted"], ["FREE SHIPPING OVER $99 FOR VIPS"])
        self.assertNotIn("ship", t)

    def test_headings_and_policy_links_are_not_quoted(self):
        t = terms.from_evidence(ev_with(
            ["Shipping", "Shipping Policy", "Shipping & Returns",
             "Select your shipping state:"]), None)
        self.assertNotIn("ship_quoted", t)
        self.assertNotIn("ship", t)

    def test_a_cart_progress_message_is_quoted_not_read(self):
        t = terms.from_evidence(ev_with(
            ["Shipping", "You\u2019re $50.00 away from free shipping!"]), None)
        self.assertEqual(t["ship_quoted"], ["You\u2019re $50.00 away from free shipping!"])
        self.assertNotIn("ship", t)


class BuiltPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards = cards(read("demo", "index.html"))

    def card(self, name_part, nth=0):
        got = [c for n, _k, c in self.cards if name_part in n]
        return html_lib.unescape(got[nth])

    def test_not_stated_only_when_no_shipping_statement_was_stored(self):
        quoted = nothing = 0
        for n, _k, c in self.cards:
            text = html_lib.unescape(c)
            t = card_terms(c)
            if t.get("sh"):
                self.assertNotIn("The page prints:", text, n)
                continue
            if "Pre-order \u2014" in text:
                continue  # a stated pre-order has its own sentence
            if "The page prints:" in text:
                quoted += 1
                self.assertIn("Not read as a condition for this item; confirm at checkout.", text, n)
                self.assertNotIn("Shipping:</b> <span class=\"u\">not stated", text, n)
                self.assertIn("page prints a shipping line, not read", text, n)
            else:
                nothing += 1
                self.assertIn("Shipping:</span> not stated on the page", text, n)
        self.assertGreater(quoted, 60)
        self.assertGreater(nothing, 30)

    def test_quoted_line_is_not_a_known_shipping_fact_in_filters_or_counts(self):
        everett = self.card("Everett Jean")
        self.assertIn("The page prints: “Free & Fast 2-Day Shipping on All U.S. Orders!”", everett)
        self.assertIsNone(card_terms(self.card_raw("Everett Jean")).get("sh"))
        self.assertNotIn("Shipping:</b> free", everett)

    def card_raw(self, name_part):
        return [c for n, _k, c in self.cards if name_part in n][0]

    def test_threshold_sentence_cards_are_read_as_known(self):
        c = self.card_raw("Carter Table Lamp")
        self.assertEqual(card_terms(c)["sh"]["over"], 9900)

    def test_member_only_free_shipping_stays_member_flagged_or_quoted(self):
        for n, _k, c in self.cards:
            sh = card_terms(c).get("sh")
            if sh and sh["k"] == "threshold" and "VIP" in sh["t"].upper():
                self.assertTrue(sh["members"], n)


class SizesAcrossColours(unittest.TestCase):
    def test_xero_hfs_men_sizes_are_in_stock_if_any_colour_has_them(self):
        t = terms.from_evidence(stored("xeroshoes-hfs-men-original"), "Shoes")
        by = {s["k"]: s["ok"] for s in t["sizes"]}
        for k in ("6.5", "7", "15"):
            self.assertTrue(by[k], k)
        self.assertEqual(t["across"], ["colours"])

    def test_xero_hfs_women_sizes_are_in_stock_if_any_colour_has_them(self):
        t = terms.from_evidence(stored("xeroshoes-hfs-women-original"), "Shoes")
        by = {s["k"]: s["ok"] for s in t["sizes"]}
        for k in ("5", "6", "12"):
            self.assertTrue(by[k], k)

    def test_a_size_out_of_stock_in_every_colour_stays_out(self):
        ev = {"json_ld": [{"@type": "ProductGroup", "hasVariant": [
            variant("Red", "S", OUT), variant("Blue", "S", OUT),
            variant("Red", "M", OUT), variant("Blue", "M", IN)]}]}
        t = terms.from_evidence(ev, "Clothing")
        self.assertEqual({s["k"]: s["ok"] for s in t["sizes"]}, {"S": False, "M": True})
        self.assertEqual(t["across"], ["colours"])

    def test_single_colour_product_says_nothing_about_colours(self):
        ev = {"json_ld": [{"@type": "ProductGroup", "hasVariant": [
            variant("Red", "S", IN), variant("Red", "M", OUT)]}]}
        t = terms.from_evidence(ev, "Clothing")
        self.assertNotIn("across", t)

    def test_taylor_stitch_tee_is_read_across_colours_on_the_card(self):
        page = read("demo", "index.html")
        c = [c for n, _k, c in cards(page) if n == "The Long Sleeve Shop Tee"][0]
        text = html_lib.unescape(c)
        self.assertIn("read across the page's colours", text)

    def test_xero_cards_say_the_sizes_are_across_colours(self):
        page = read("demo", "index.html")
        for name in ("HFS Original - Men", "HFS Original - Women"):
            c = html_lib.unescape([c for n, _k, c in cards(page) if n == name][0])
            self.assertIn("read across the page's colours", c)
            self.assertNotRegex(c, r"not shown in stock when checked: 6\.5")


if __name__ == "__main__":
    unittest.main()
