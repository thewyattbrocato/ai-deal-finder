"""Readiness fixes D1-D8: the page says only what its stored evidence supports.

Offline: the static page, the page script driven under node, and the stored
evidence. Nothing here invents a product, price, size, coupon or shipping fact.
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

import catalog  # noqa: E402
import terms  # noqa: E402
from test_page import drive, read  # noqa: E402

PAGE = os.path.join(ROOT, "demo", "index.html")
HAND = {"apple", "oldnavy", "gap", "nike", "cof1", "cof2", "cof3", "hcr", "wel", "ccc"}


def stored(ev_id):
    with open(os.path.join(ROOT, "demo", "evidence", ev_id + ".json"), encoding="utf-8") as f:
        return json.load(f)


def stored_seeds():
    with open(os.path.join(ROOT, "demo", "seeds.json"), encoding="utf-8") as f:
        return json.load(f)


def card_terms(card):
    return json.loads(html_lib.unescape(re.search(r'data-terms="([^"]*)"', card).group(1)))


def cards(page):
    out = []
    for c in re.findall(r'<section class="card item".*?</section>', page, re.S):
        m = re.search(r'data-name="([^"]*)"', c)
        if "data-keywords=" in c and m:
            out.append((html_lib.unescape(m.group(1)),
                        re.search(r'data-kind="([^"]*)"', c).group(1),
                        c))
    return out


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = read("demo", "index.html")
        cls.cards = cards(cls.page)


class D1PageReadNotVerdict(Base):
    def test_catalog_cards_state_what_was_read_with_no_endorsement(self):
        neutral = [c for _n, _k, c in self.cards if "data-page-read" in c]
        self.assertGreater(len(neutral), 200)
        for c in neutral:
            self.assertIn("Price read from the store page", c)
            self.assertIn("Not compared with other stores.", c)
            for word in ("Good to buy", "Worth a wait", "Check first", "✓"):
                self.assertNotIn(word, c)
            self.assertNotIn("text-success", c)

    def test_engine_verdict_wording_stays_only_on_the_hand_checked_cards(self):
        verdict = [n for n, _k, c in self.cards if "Good to buy" in c]
        self.assertEqual(len(verdict), 10)
        self.assertEqual(len(self.cards), len(verdict) + len(
            [1 for _n, _k, c in self.cards if "data-page-read" in c]))
        self.assertEqual(self.page.count("Good to buy"), len(verdict))


class D2CoffeeIsBeans(Base):
    NOT_BEANS = {
        "WILDWOOD Sticker Crow", "Crow's Call Patch", "Wilderness Field Notes",
        "Ghost Bridge Tote", "Into the WILDWOOD Mug", "WILDWOOD Trail Pack",
        "The Breville Bambino™", "Baratza Encore ESP Pro Grinder",
        "After Hours Decaf — 8ct", "Decaf Placer De La Tarde — 8ct",
        "The Big Chlebowski Bundle — Mixed Roast",
        "White Chocolate Pistachio Ground Bundle",
    }

    def test_coffee_beans_search_lists_only_the_nine_bean_bags(self):
        load = drive(PAGE, only_load=True, hash="#q=coffee%20beans")["load"]
        names = [c["name"] for c in load["main"]]
        self.assertEqual(len(names), 9)
        for c in load["main"]:
            self.assertEqual(c["kind"], "Coffee", c)
            self.assertNotIn(c["name"], self.NOT_BEANS)

    def test_the_coffee_kind_holds_no_merch_gear_pods_or_bundles(self):
        coffee = {n for n, k, _c in self.cards if k == "Coffee"}
        self.assertFalse(coffee & self.NOT_BEANS)

    def test_reclassified_products_stay_on_the_page_under_their_own_kind(self):
        kinds = {n: k for n, k, _c in self.cards}
        for n in self.NOT_BEANS:
            self.assertIn(n, kinds)
            self.assertNotEqual(kinds[n], "Coffee", n)
        self.assertEqual(kinds["Crow's Call Patch"], "Accessories")
        self.assertEqual(kinds["The Breville Bambino™"], "Kitchen")

    def test_a_non_bean_item_is_found_by_its_own_name(self):
        shown = drive(PAGE, only_load=True, hash="#q=bambino")["load"]["main"]
        self.assertEqual([c["name"] for c in shown], ["The Breville Bambino\u2122"])

    def test_seeds_are_where_the_kind_is_decided_and_evidence_is_kept(self):
        seeds = {s["id"]: s["kind"] for s in stored_seeds()}
        self.assertEqual(seeds["stumptowncoffee-crows-call-patch"], "Accessories")
        for i in ("stumptowncoffee-crows-call-patch", "cometeer-first-person-after-hours-decaf"):
            ev = stored(i)
            self.assertEqual(ev["kind"], "Coffee")  # collected label, untouched
            self.assertTrue(ev["json_ld"])


class D3TaxShipLineIsConditional(Base):
    def test_shipping_unknown_is_said_only_when_no_shipping_line_is_stored(self):
        stated = unknown = 0
        for n, _k, c in self.cards:
            says_both = "Tax and shipping weren&#x27;t shown" in c
            if card_terms(c).get("sh"):
                stated += 1
                self.assertFalse(says_both, n)
            elif "Members get free shipping over $50" in c:
                continue  # Nike's own two sentences already say what is unknown
            else:
                unknown += 1
                self.assertTrue(says_both, n)
        self.assertGreater(stated, 100)
        self.assertGreater(unknown, 10)

    def test_lavazza_super_crema_shows_a_shipping_line_and_only_tax_unknown(self):
        c = [c for n, _k, c in self.cards if n.startswith("Super Crema Whole Bean")][0]
        self.assertIn("Tax wasn&#x27;t shown for this item", c)
        self.assertNotIn("shipping weren", c)
        self.assertIn("Free delivery on orders over $50", html_lib.unescape(c))


class D4SizesFromOffers(unittest.TestCase):
    def test_chubbies_lists_every_size_its_offers_list_with_stock(self):
        t = terms.for_id("chubbiesshorts-the-groovy-with-it-eagles-polo", "Clothing")
        self.assertEqual([s["k"] for s in t["sizes"]],
                         ["XS", "S", "M", "L", "XL", "XXL", "XXXL"])
        self.assertEqual([s["ok"] for s in t["sizes"]],
                         [False, True, True, True, True, True, True])  # XS out of stock
        t = terms.for_id("chubbiesshorts-the-prowls-boys-lined-swim-trunk-pink", "Clothing")
        self.assertEqual([s["k"] for s in t["sizes"]], ["XS", "S", "M", "L", "XL"])
        self.assertEqual(t["group"], "clothing")

    def _ev(self, offers, size="XS"):
        return {"json_ld": [{"name": "x", "size": size, "offers": offers}]}

    def _o(self, suffix):
        return {"availability": "https://schema.org/InStock", "price": 1,
                "url": "https://s.example/p" + suffix}

    def test_partial_parse_shows_no_size_rather_than_one(self):
        ev = self._ev([self._o("?Size=XS"), self._o("?Size=S"), self._o("")])
        self.assertEqual(terms.from_evidence(ev, "Clothing")["sizes"], [])

    def test_a_single_offer_keeps_the_products_own_size(self):
        t = terms.from_evidence(self._ev([self._o("")], size="M"), "Clothing")
        self.assertEqual([s["k"] for s in t["sizes"]], ["M"])

    def test_no_chubbies_card_reads_listed_xs_alone(self):
        page = read("demo", "index.html")
        for c in re.findall(r'<section class="card item".*?</section>', page, re.S):
            if "chubbies" in c.lower() and "data-terms=" in c:
                self.assertGreater(len(card_terms(c)["z"]), 1)


class D5SaleNameKept(unittest.TestCase):
    def test_untuckit_quote_keeps_the_sale_the_page_printed(self):
        ok, _ = catalog.load_catalog()
        rows = [o for o in ok if o["coupon"] and o["coupon"]["code"] == "NOIRON"]
        self.assertEqual(len(rows), 6)
        for o in rows:
            text = o["coupon"]["text"]
            self.assertTrue(text.startswith("Wrinkle-Free Sale:"), text)
            self.assertIn("enter code NOIRON at checkout.", text)
            stored_ev = stored(o["id"])
            self.assertTrue(any(text in sn for sn in stored_ev["coupon_snippets"]))
        page = html_lib.unescape(read("demo", "index.html"))
        self.assertIn("“Wrinkle-Free Sale: Offer valid 10/1/2026", page)

    def test_offers_with_no_sale_heading_are_quoted_as_before(self):
        ok, _ = catalog.load_catalog()
        moft = [o for o in ok if o["coupon"] and o["coupon"]["code"] == "DYNAMIC10"][0]
        self.assertEqual(moft["coupon"]["text"], "$10 OFF Early Bird Offer: Use code DYNAMIC10 at checkout.")


class D6CoffeeNoteOnlyWithCoffee(Base):
    def test_note_shows_for_a_coffee_search(self):
        load = drive(PAGE, only_load=True, hash="#q=coffee%20beans")["load"]
        self.assertEqual(load["coffeeNote"], "")

    def test_note_is_hidden_when_results_have_no_coffee(self):
        for q in ("tea", "airpods", "shoes"):
            self.assertEqual(drive(PAGE, only_load=True, hash="#q=" + q)["load"]["coffeeNote"], "none", q)


class D7NoGiftCardsOrMemberships(unittest.TestCase):
    IDS = ("nisolo-nisolo-gift-card-100", "publicgoods-better-together-membership")

    def test_both_are_excluded_with_a_stated_reason_and_evidence_is_kept(self):
        ok, ex = catalog.load_catalog()
        reasons = dict(ex)
        for i in self.IDS:
            self.assertNotIn(i, {o["id"] for o in ok})
            self.assertIn("not a product with a shelf price", reasons[i])
            ev = stored(i)
            self.assertTrue(ev["json_ld"] and ev["excluded_reason"])

    def test_the_rule_also_catches_a_new_gift_card_without_a_stored_reason(self):
        ev = stored(self.IDS[0])
        del ev["excluded_reason"]
        state, reason = catalog.extract(ev)
        self.assertEqual(state, "excluded")
        self.assertIn("gift card or membership", reason)

    def test_gift_sets_of_real_coffee_are_not_gift_cards(self):
        ok, _ = catalog.load_catalog()
        self.assertTrue([o for o in ok if "Gift Set" in o["name"]])

    def test_the_page_no_longer_shows_them(self):
        page = read("demo", "index.html")
        self.assertNotIn("Nisolo Gift Card", page)
        self.assertNotIn("Public Goods Membership", page)


class D8EasternDate(unittest.TestCase):
    def state(self, now, tz):
        rows = drive(PAGE, now=now, only_load=True, tz=tz)["load"]["windows"]
        return {w["state"] for w in rows if w["code"] == "NOIRON"}

    def test_window_ending_10_4_11_59_pm_et_is_not_ended_early(self):
        # 02:00Z on 10/5 is 10 PM ET on 10/4: still inside, whatever the browser zone.
        for tz in ("UTC", "Pacific/Auckland", "Asia/Tokyo", "America/Los_Angeles"):
            self.assertEqual(self.state("2026-10-05T02:00:00Z", tz), {"inside"}, tz)
            self.assertEqual(self.state("2026-10-04T15:00:00Z", tz), {"inside"}, tz)

    def test_it_ends_at_the_eastern_date_change_not_the_viewers(self):
        for tz in ("UTC", "Pacific/Auckland", "America/Los_Angeles"):
            self.assertEqual(self.state("2026-10-05T04:30:00Z", tz), {"ended"}, tz)  # 12:30 AM ET 10/5
            self.assertEqual(self.state("2026-10-01T03:00:00Z", tz), {"before"}, tz)  # 11 PM ET 9/30

    def test_status_says_which_zone_the_date_is_in(self):
        rows = drive(PAGE, now="2026-10-05T02:00:00Z", only_load=True)["load"]["windows"]
        self.assertTrue(all("US Eastern time (2026-10-04)" in w["status"]
                            for w in rows if w["code"] == "NOIRON"))


if __name__ == "__main__":
    unittest.main()
