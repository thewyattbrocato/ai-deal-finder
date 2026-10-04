"""Store labels, pre-orders, kinds and the Apple wording on the built page.

Offline: reads the generated demo/index.html and the stored evidence.
"""

import html
import importlib.util
import json
import os
import re
import sys
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "demo"))

import terms  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "demo_build", os.path.join(ROOT, "demo", "build.py"))
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

with open(os.path.join(ROOT, "demo", "index.html"), encoding="utf-8") as f:
    PAGE = f.read()
ROWS = json.loads(re.search(r'id="catalog"[^>]*>(.*?)</script>', PAGE, re.S)
                  .group(1))
CARDS = re.split(r'(?=<section class="card item")', PAGE)[1:]
MERCHANTS = build.merchants()


def host_of(url):
    return urllib.parse.urlparse(url).netloc.replace("www.", "")


def card(name):
    hit = [c for c in CARDS if 'data-name="' + html.escape(name) + '"' in c
           or 'data-name="' + name + '"' in c]
    assert len(hit) == 1, (name, len(hit))
    return hit[0]


def text(fragment):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)))


class StoreLabelTest(unittest.TestCase):
    def test_every_card_label_is_the_merchant_label_for_its_host(self):
        self.assertEqual(len(ROWS), 390)
        for r in ROWS:
            host = host_of(r["u"])
            self.assertIn(host, MERCHANTS, r["n"])
            self.assertEqual(r["m"], MERCHANTS[host], r["n"])

    def test_no_card_label_is_a_sku_like_code(self):
        for r in ROWS:
            self.assertIsNone(build.SKU_LIKE.fullmatch(r["m"]), (r["n"], r["m"]))
        for label in MERCHANTS.values():
            self.assertIsNone(build.SKU_LIKE.fullmatch(label), label)

    def test_one_host_has_one_label(self):
        self.assertEqual(len({r["m"] for r in ROWS}),
                         len({MERCHANTS[host_of(r["u"])] for r in ROWS}))
        # the header's store count is computed by the page script from these
        # labels, never written into the page (see demo/view.js)
        self.assertNotRegex(PAGE, r">\s*\d+ stores\b")

    def test_the_sixteen_audited_cards_name_their_real_store(self):
        want = {
            "Dynamic Folio for iPhone Duo": "MOFT",
            "Snap Fold for iPhone Duo": "MOFT",
            "Baratza Encore ESP Pro Grinder": "Counter Culture Coffee",
            "The Breville Bambino™": "Counter Culture Coffee",
            "Crossbones Klean Kanteen Mug": "Death Wish Coffee",
            "Cardamom Cloud": "Fellow",
            "Juan Puerta Mango": "Fellow",
            "Jewel Pro Sets": "GreenPan",
            "Reserve Pro 14pc Bundles": "GreenPan",
            "Valencia Pro Stainless Steel Uncoated 9-Piece Cookware Set": "GreenPan",
        }
        by_name = {r["n"]: r["m"] for r in ROWS}
        for name, label in want.items():
            self.assertEqual(by_name[name], label, name)
        for r in ROWS:
            if host_of(r["u"]) in ("moft.com", "cotopaxi.com"):
                self.assertIn(r["m"], ("MOFT", "Cotopaxi"), r["n"])
        for c in CARDS:
            self.assertNotRegex(text(c), r"See at (?:MS030|MD023|MD020|MB004|F24-Semiannual|"
                                         r"Cotopaxi-Amigos-24|Breville|BAMKO|Klean Kanteen|"
                                         r"Driftaway Coffee|Resident Coffee|Jewel Pro|"
                                         r"Reserve Pro|Valencia Pro)")

    def test_the_pages_own_brand_stays_searchable_but_a_sku_does_not(self):
        by_name = {r["n"]: r for r in ROWS}
        self.assertIn("breville", by_name["The Breville Bambino™"]["kw"])
        self.assertIn("baratza", by_name["Baratza Encore ESP Pro Grinder"]["kw"])
        for r in ROWS:
            for w in r["kw"]:
                self.assertNotIn(w, ("ms030", "md023", "md020", "mb004"), r["n"])


class PreOrderTest(unittest.TestCase):
    def test_a_stated_pre_order_line_is_quoted_with_its_date_wording(self):
        pre = terms._pre_from_lines(
            ["\U0001f69a International shipping off from Sep 30, resumes Oct 7.",
             "\U0001f69a Shipping: Pre-orders start shipping in Nov.", "Shipping"])
        self.assertEqual(pre["t"], "“Pre-orders start shipping in Nov.”")
        self.assertEqual(pre["when"], "“start shipping in Nov.”")

    def test_no_pre_order_text_means_no_pre_order(self):
        for lines in (None, [], ["Free shipping over USD$69", "Shipping"],
                      ["Pre-order our newsletter"],
                      ["Pre-orders start shipping in Nov.", "Preorders ship in Dec."]):
            self.assertIsNone(terms._pre_from_lines(lines), lines)

    def test_the_two_stated_moft_pre_orders_say_so_on_the_card(self):
        for name, when in (("Dynamic Folio for iPhone Duo", "Nov."),
                           ("Snap Fold for iPhone Duo", "Dec.")):
            t = text(card(name))
            self.assertIn("Shipping: pre-order, “start shipping in %s”" % when, t)
            self.assertIn("Pre-order — the page says "
                          "“Pre-orders start shipping in %s”" % when, t)
            self.assertNotIn("Shipping: not stated", t)
            self.assertNotIn("Shipping: not stated on the page", t)

    def test_the_other_moft_cards_are_not_called_pre_orders(self):
        for r in ROWS:
            if r["n"] in ("Dynamic Folio for iPhone Duo", "Snap Fold for iPhone Duo"):
                continue
            self.assertNotRegex(text(card(r["n"])).lower(), r"pre-?order", r["n"])

    def test_only_those_two_stored_pages_state_a_pre_order(self):
        found = []
        for fn in sorted(os.listdir(terms.EVIDENCE_DIR)):
            if fn.endswith(".json"):
                with open(os.path.join(terms.EVIDENCE_DIR, fn)) as f:
                    ev = json.load(f)
                if terms._pre_from_lines((ev.get("conditions") or {}).get("ship")):
                    found.append(fn)
        self.assertEqual(found, ["moft-dynamic-folio-for-iphone-duo.json",
                                 "moft-snap-fold-magsafe-compatible.json"])


MOVES = {  # product name on the card: (old kind, new kind); old kind = seeds.json before this change
    "Bath Strips": ("Tech", "Home"), "Bento Box": ("Tech", "Kitchen"),
    "Ironing Board Cover": ("Tech", "Home"), "Pizza Cutter": ("Tech", "Kitchen"),
    "Wall Hooks": ("Tech", "Home"),
    "Bomber Jacket | Cinnamon": ("Shoes", "Clothing"),
    "Mechanic Jacket | Army Green": ("Shoes", "Clothing"),
    "Racer Jacket | Java": ("Shoes", "Clothing"),
    "Highland Sweater | Driftwood": ("Shoes", "Clothing"),
    "Deco Bracelet 7.5-inch": ("Clothing", "Accessories"),
    "Deco Bracelet 7-inch": ("Clothing", "Accessories"),
    "Deco Mini Hoop Earrings": ("Clothing", "Accessories"),
    "Deco Pearl Earrings": ("Clothing", "Accessories"),
    "Cardamom Cloud": ("Kitchen", "Coffee"), "Juan Puerta Mango": ("Kitchen", "Coffee"),
    "Gift Wrap with Personalized Card": ("Pantry", "Home"),
    "Shoe Charm Black/White": ("Shoes", "Accessories"),
    "Shoe Charm Fish Blue": ("Shoes", "Accessories"),
    "Shoe Charm Terracotta/Gold": ("Shoes", "Accessories"),
    "Sodastream bubly drops® Tropical Original Variety Natural Flavor Essence 6 Pack 40ml - final sale": ("Kitchen", "Drinks"),
    "Sodastream bubly drops® Tropical Thrill Variety Natural Flavor Essence 3 Pack 40ml - final sale": ("Kitchen", "Drinks"),
    "Sodastream MTN DEW Diet Drink Mix 440ml": ("Kitchen", "Drinks"),
    "Cleaning Refill Set (3 Month Supply)": ("Personal care", "Home"),
    "Home Essentials Set": ("Personal care", "Home"),
}


class KindTest(unittest.TestCase):
    def test_each_moved_product_is_filed_by_what_its_own_page_title_says(self):
        by_name = {r["n"]: r["k"] for r in ROWS}
        for name, (_old, new) in MOVES.items():
            self.assertEqual(by_name[name], new, name)
            self.assertIn('data-kind="' + new + '"', card(name), name)

    def test_the_stored_evidence_keeps_the_kind_it_was_collected_under(self):
        # nothing is deleted or rewritten: the move lives in seeds.json only
        for fn in ("gorillagrip-bath-strips.json", "cuyana-deco-pearl-earrings.json",
                   "fellowproducts-colombia-juan-puerta-mango.json"):
            with open(os.path.join(terms.EVIDENCE_DIR, fn)) as f:
                self.assertEqual(json.load(f)["kind"],
                                 {"gorillagrip-bath-strips.json": "Tech",
                                  "cuyana-deco-pearl-earrings.json": "Clothing",
                                  "fellowproducts-colombia-juan-puerta-mango.json": "Kitchen"}[fn])

    def test_no_gorilla_grip_or_thursday_or_cuyana_card_is_in_a_wrong_kind(self):
        for r in ROWS:
            host = host_of(r["u"])
            if host == "gorillagrip.com":
                self.assertIn(r["k"], ("Home", "Kitchen"), r["n"])
            if host == "thursdayboots.com":
                self.assertEqual(r["k"], "Clothing", r["n"])
            if host == "cuyana.com":
                self.assertEqual(r["k"], "Accessories", r["n"])

    def test_every_kind_is_an_existing_kind(self):
        self.assertEqual(len({r["k"] for r in ROWS}), 18)


class AppleWordingTest(unittest.TestCase):
    def test_the_short_shipping_line_repeats_the_pages_word_delivery(self):
        t = text(card("AirPods Pro 3"))
        self.assertIn("Shipping: free delivery", t)
        self.assertNotIn("Shipping: free shipping", t)
        self.assertIn("“free delivery”", t)


if __name__ == "__main__":
    unittest.main()
