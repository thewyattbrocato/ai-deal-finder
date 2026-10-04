"""The public page: search first, instant results, honest cards.

Checks the generated demo/index.html and its GitHub Pages copy docs/index.html.
Offline; no invented products, prices, or coupons. The page's own scripts run
under node (tests/page_driver.js drives the page against its markup,
tests/engine_driver.js runs the search engine on the page's embedded catalog);
nothing here is a source search.
"""

import html as html_lib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

AGE_RE = r"^Checked (less than 1 hour ago, \d{4}-\d\d-\d\dT[\d:]+Z|\d+ hours? ago, \d{4}-\d\d-\d\dT[\d:]+Z|\d+ days ago, \d{4}-\d\d-\d\d|\d{4}-\d\d-\d\d)$"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, "tests", "page_driver.js")
ENGINE = os.path.join(ROOT, "tests", "engine_driver.js")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def _node(script, page_path, env):
    proc = subprocess.run(["node", script, page_path], check=False,
                          capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


def drive(page_path, now=None, only_load=False, tz="UTC", hash=None):
    env = dict(os.environ, TZ=tz)  # the browser's own zone must not decide a printed window
    if now:
        env["PAGE_NOW"] = now
    if hash:
        env["PAGE_HASH"] = hash
    if only_load:
        env["ONLY_LOAD"] = "1"
    return _node(DRIVER, page_path, env)


def engine(page_path):
    return _node(ENGINE, page_path, dict(os.environ))


def names(cards):
    return [c["name"] for c in cards]


def page_cards(page):
    return re.findall(r'<section class="card item".*?</section>', page, re.S)


class ShopperWordsTest(unittest.TestCase):
    """Defects found walking the live page: words a shopper types that found
    nothing, or found products that are not what the word names."""

    @classmethod
    def setUpClass(cls):
        cls.eng = engine(os.path.join(ROOT, "demo", "index.html"))
        cls.q = cls.eng["queries"]

    def rows(self, q):
        return self.q[q]["rows"]

    def test_plural_of_a_word_ending_ie_finds_it(self):
        self.assertEqual(self.rows("hoodies"), self.rows("hoodie"))
        self.assertTrue(self.rows("hoodies"))

    def test_t_shirt_in_any_spelling_finds_the_tee_not_button_shirts(self):
        tee = self.rows("tee")
        self.assertEqual(tee, ["The Long Sleeve Shop Tee"])
        for q in ("t-shirt", "t shirt", "tshirts"):
            self.assertEqual(self.rows(q), tee, q)

    def test_two_word_and_one_word_spellings_of_a_catalog_word_find_the_same_product(self):
        one = self.rows("sweatpants")
        self.assertEqual(one, ["High-Waisted SoComfy Wide-Leg Sweatpants"])
        for q in ("sweat pants", "sweat-pants", "sweat pant", "sweatpant"):
            self.assertEqual(self.rows(q), one, q)
        # a split spelling of a word the catalog has, never a made-up join: unrelated words stay unmatched
        self.assertEqual(self.rows("pan cake"), [])
        self.assertEqual(self.rows("olive oil"), self.rows("oliveoil"))
        self.assertEqual(len(self.rows("olive oil")), 4)

    def test_dog_never_lists_cat_products(self):
        dogs, cats = self.rows("dog"), self.rows("cat")
        self.assertTrue(dogs and cats)
        self.assertFalse(set(dogs) & set(cats))
        self.assertEqual(self.rows("dogs"), dogs)

    def test_a_kind_synonym_is_not_handed_to_every_product_of_the_kind(self):
        # every product a word finds prints it in its own name, stored page title or description,
        # unless the whole search is the kind's own name or a word that names the kind
        sys.path.insert(0, os.path.join(ROOT, "demo"))
        import catalog
        obs, _ = catalog.load_catalog()
        said = {o["name"]: (o["name"] + " " + o.get("title", "") + " " + o.get("desc", "")).lower() for o in obs}
        for word in ("wallet", "bag", "camping", "hiking", "bath", "scent", "cooking", "beard"):
            rows = self.rows(word)
            for n in rows:
                if n in said:   # the ten hand-checked cards carry their own words
                    self.assertRegex(said[n], r"\b" + word + r"(?:s|es)?\b", (word, n))
        self.assertLess(len(self.rows("wallet")), 10)
        self.assertEqual([n for n in self.rows("wallet") if "Wallet" in n or "Cardholder" in n][:1], ["Ekster Wallet Pro"])
        for n in ("Deco Bracelet", "Death Grip Bottle Opener"):
            self.assertFalse([r for r in self.rows("wallet") if r.startswith(n)], n)
        # a bare kind name or a word that names the kind still returns the kind
        kinds = self.eng["kinds"]
        for word, kind in (("shoes", "Shoes"), ("footwear", "Shoes"), ("coffee", "Coffee"), ("tea", "Tea"),
                           ("kitchen", "Kitchen"), ("apparel", "Clothing"), ("electronics", "Tech"),
                           ("accessories", "Accessories"), ("grooming", "Grooming"), ("toys", "Toys")):
            self.assertGreaterEqual(len(self.rows(word)), kinds[kind], word)
        # but not as a word of a longer search: "coffee beans" is not every coffee product
        self.assertLess(len(self.rows("coffee beans")), len(self.rows("coffee")))
        self.assertTrue(self.rows("nike shoes"))

    def test_a_kind_word_is_not_handed_to_every_product_of_the_kind(self):
        # phone: only products whose own page names a phone, never bath strips
        self.assertTrue(self.rows("phone"))
        for n in ("Bath Strips", "Bento Box", "Pizza Cutter"):
            self.assertNotIn(n, self.rows("phone"))
        # sneakers: not shoe charms, flip flops or jackets filed under Shoes
        for n in self.rows("sneakers"):
            self.assertNotRegex(n, r"(?i)charm|flip flop|jacket|sweater")
        # bedding: not plants or detergent sheets filed under Home
        for n in self.rows("bedding"):
            self.assertNotRegex(n, r"(?i)camellia|detergent|dryer")


class SearchFirstTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = read("demo", "index.html")
        cls.d = drive(os.path.join(ROOT, "demo", "index.html"))
        cls.eng = engine(os.path.join(ROOT, "demo", "index.html"))

    def test_pages_copy_matches_demo(self):
        self.assertEqual(self.page, read("docs", "index.html"))

    # ---- 1. nothing in front of the search box --------------------------------

    def test_the_box_is_first_and_empty_with_focus_on_desktop(self):
        load = self.d["load"]
        self.assertEqual(load["q"], "")
        self.assertEqual(load["focus"], {"id": "q", "chip": None, "remove": None, "isQ": True})
        self.assertTrue(load["startShown"])
        self.assertFalse(load["areaShown"])
        self.assertNotIn("coffee beans", load["pageText"])
        self.assertEqual(load["count"], "")
        self.assertEqual(load["chips"], [])
        # the first control in the page is the search box, with a visible label
        first = re.search(r"<(input|button|select|a|summary)\b[^>]*>", self.page[self.page.index("<body>"):])
        self.assertEqual(first.group(1), "input")
        self.assertIn('id="q"', first.group(0))
        self.assertIn('<label class="search-label" for="q">', self.page)

    def test_no_focus_stolen_on_a_phone_where_the_keyboard_would_cover_the_page(self):
        self.assertIsNone(self.d["loadPhone"]["focus"])

    def test_no_guide_mode_switch_or_search_button(self):
        for gone in ('id="guide', 'id="mode-', 'id="search-go"', "Guide (optional)",
                     "Exact product", "Kind of thing", ">Search</button>", "guide-"):
            self.assertNotIn(gone, self.page)
        buttons = re.findall(r"<button[^>]*>([^<]*)<", self.page)
        self.assertNotIn("Search", [b.strip() for b in buttons])

    def test_the_first_screen_offers_kinds_and_how_to_read_it(self):
        start = self.d["load"]["startText"]
        self.assertIn("Or start with a kind", start)
        self.assertIn("Kitchen46 products", start)
        self.assertIn("Browse all 390 checked products", start)
        self.assertIn("never guessed", start)

    # ---- 2. results as the first characters are typed -------------------------

    def test_results_follow_the_characters_with_no_submit(self):
        t = self.d["typed"]
        self.assertFalse(t["c"]["areaShown"])           # one letter is not a word yet
        self.assertTrue(t["c"]["startShown"])
        self.assertEqual(len(self.d["sweatpantsLetters"]), 10)
        counts = [int(re.match(r"\d+", s["count"]).group(0)) if re.match(r"\d+", s["count"]) else 0
                  for s in self.d["sweatpantsLetters"]]
        self.assertEqual(counts[-1], 1)                 # "sweatpants" finds the Old Navy pair
        for s in self.d["sweatpantsLetters"][1:]:
            self.assertTrue(s["areaShown"])
        self.assertEqual(t["cof"]["count"], "33 checked products for “cof”")
        self.assertEqual(t["coffee"]["count"], "33 checked products for “coffee”")
        self.assertEqual(t["old nav"]["count"], "1 checked product for “old nav”")

    def test_whole_words_only_bean_does_not_find_beanie(self):
        q = self.eng["queries"]
        self.assertEqual(len(q["bean"]["rows"]), 12)   # incl. goodr "Bean There, Run That"
        self.assertFalse([n for n in q["bean"]["rows"] if "Beanie" in n])
        self.assertEqual(q["beanie"]["rows"], ["Wild at Heart Beanie"])
        # a word still being typed may be the start of a word, until it is a whole word
        self.assertEqual(q["beani"]["rows"], ["Wild at Heart Beanie"])
        self.assertEqual(q["beani"]["modes"][0][1], "prefix")
        self.assertEqual(q["bean"]["modes"][0][1], "exact")
        self.assertEqual(sorted(q["dogs"]["rows"]), sorted(q["dog"]["rows"]))  # plurals are the same word
        self.assertEqual(sorted(q["sneakers"]["rows"]), sorted(q["sneaker"]["rows"]))

    def test_the_page_view_agrees_bean_never_lists_a_beanie(self):
        t = self.d["typed"]
        self.assertFalse([c for c in t["bean"]["main"] if "Beanie" in c["name"]])
        self.assertEqual(names(t["beanie"]["main"]), ["Wild at Heart Beanie"])

    def test_a_typo_is_corrected_and_the_page_says_so_plainly(self):
        t = self.d["typed"]
        self.assertEqual(t["cofee"]["notes"], [
            "No exact word “cofee” in the catalog — showing close spellings: coffee."])
        self.assertEqual(names(t["cofee"]["main"]), names(t["coffee"]["main"]))
        self.assertEqual(t["coffee"]["notes"], [])
        self.assertEqual(t["cof"]["notes"], [])          # a start of a word is not a typo
        self.assertEqual(len(t["espreso"]["main"]), 8)
        self.assertIn("espresso", t["espreso"]["notes"][0])

    def test_a_word_nothing_is_near_is_not_corrected_to_something_else(self):
        self.assertEqual(self.eng["queries"]["zzyzx"]["rows"], [])
        self.assertEqual(self.eng["queries"]["zzyzx"]["notes"], [])

    def test_espresso_finds_the_bambino_through_the_catalog_build(self):
        sys_path = os.path.join(ROOT, "demo")
        import sys
        sys.path.insert(0, sys_path)
        import terms
        self.assertEqual(terms.SEARCH_WORDS["counterculturecoffee-the-bambino"], ["espresso"])
        self.assertTrue(os.path.exists(os.path.join(ROOT, "demo", "evidence",
                                                    "counterculturecoffee-the-bambino.json")))
        rows = self.eng["queries"]["espresso"]["rows"]
        self.assertIn("The Breville Bambino™", rows)
        self.assertEqual(len(rows), 8)       # the Bambino, two roasts, Flair, Wacaco (see test_coverage_q2)
        self.assertEqual(names(self.d["typed"]["espresso"]["main"]), rows)
        self.assertIn("The Breville Bambino™", names(self.d["typed"]["bambino"]["main"]))

    def test_ranking_is_relevance_not_cheapest_first(self):
        main = self.d["typed"]["coffee"]["main"]
        self.assertIn("coffee", main[0]["name"].lower())           # the word is in its name
        prices = [int(self.cents(c["priceLabel"])) for c in main]
        self.assertNotEqual(prices, sorted(prices))
        lo = [self.cents(c["priceLabel"]) for c in self.d["sortLo"]["main"]]
        hi = [self.cents(c["priceLabel"]) for c in self.d["sortHi"]["main"]]
        self.assertEqual(lo, sorted(lo))
        self.assertEqual(hi, sorted(hi, reverse=True))

    @staticmethod
    def cents(label):
        return round(float(label.replace("$", "").replace(",", "")) * 100)

    def test_order_is_stable_while_typing(self):
        for q, o in self.eng["order"].items():
            self.assertTrue(o["same"], q)
            self.assertTrue(o["tiesInOrder"], q)  # ties keep the fixed catalog order
        steps = self.eng["typing"]
        for a, b in zip(steps, steps[1:]):
            self.assertEqual([n for n in a if n in b], [n for n in b if n in a])

    def test_suggestions_offer_kinds_stores_and_products_with_shelf_price(self):
        s = self.eng["suggest"]["cof"]
        self.assertEqual(s[0], ["kind", "Coffee", "kind · 11 products"])
        self.assertTrue([x for x in s if x[0] == "store"])
        products = [x for x in s if x[0] == "product"]
        self.assertTrue(products)
        for _t, label, sub in products:
            self.assertRegex(sub, r"^\$\d+(\.\d\d)? · ")
        self.assertIn(["product", "The Breville Bambino™", "$299.95 · Counter Culture Coffee"],
                      self.eng["suggest"]["bambino"])

    # ---- 3. a result: compact card, one tap to the store, details on the card --

    def test_every_shown_card_names_the_store_shelf_price_age_and_unknowns(self):
        seen = 0
        for q in ("coffee", "shoes", "clothing", "old navy", "airpods", "dog"):
            for c in self.d["typed"][q]["main"]:
                seen += 1
                self.assertEqual(c["price"], c["priceLabel"], c["name"])
                self.assertRegex(c["age"], AGE_RE)
                self.assertRegex(c["facts"], r"^Size: .*Shipping: .*Subscribe: ")
                self.assertTrue(c["href"].startswith("https://"), c["name"])
                self.assertTrue(c["link"].startswith("See at "), c["name"])
                self.assertEqual(c["heading"], c["name"].replace("™", "™"))
        self.assertGreater(seen, 40)

    def test_one_tap_reaches_the_store_page_from_the_compact_card(self):
        for card in page_cards(self.page):
            m = re.search(r'<div class="cardfoot"><a class="go" href="([^"]+)" target="_blank" rel="noopener">See at ', card)
            self.assertIsNotNone(m, card[:200])
            self.assertLess(card.index('class="go"'), card.index('<details class="more">'))

    def test_the_compact_card_quotes_a_printed_coupon_and_says_not_applied(self):
        coupons = [c for c in self.d["load"]["all"] if c["coupon"] == "yes"]
        self.assertEqual(len(coupons), 19)
        for c in coupons:
            line = c["couponLine"]
            self.assertTrue(line.startswith("Printed coupon " + c["code"]), line)
            self.assertIn("the page says", line)
            self.assertIn("Not applied: the price above is the shelf price and does not include it.", line)
        for c in self.d["load"]["all"]:
            if c["coupon"] != "yes":
                self.assertIsNone(c["couponLine"])

    def test_unknowns_read_not_stated_never_no(self):
        unknown = "not stated — unknown"
        facts = [c["facts"] for c in self.d["load"]["all"]]
        self.assertTrue([f for f in facts if unknown in f])
        for f in facts:
            self.assertNotRegex(f, r"(?i)(size|shipping|subscribe): no\b")
        sparse = [c for c in self.d["load"]["all"] if c["name"] == "AirPods Pro 3"][0]
        self.assertIn("Size: " + unknown, sparse["facts"])
        self.assertIn("Subscribe: " + unknown, sparse["facts"])

    def test_the_compact_shipping_never_counts_members_only_as_free(self):
        old = [c for c in self.d["load"]["all"] if c["name"].startswith("High-Waisted SoComfy")][0]
        self.assertIn("Shipping: free over $50 (members only)", old["facts"])
        for q, snap in (("free", self.d["clothingShipFree"]), ("min", self.d["clothingShipMin"])):
            for c in snap["main"]:
                self.assertNotIn("members only", c["facts"], q)
        self.assertGreater(self.eng["membersExist"], 0)
        self.assertEqual(self.eng["members"]["free"], 0)
        self.assertEqual(self.eng["members"]["min"], 0)

    def test_full_detail_stays_on_the_same_card_one_tap_away(self):
        cards = page_cards(self.page)
        self.assertEqual(len(cards), 390)
        for c in cards:
            body = c[c.index('<details class="more">'):]
            self.assertIn("<summary>Full details: savings, coupon window, what to confirm, terms</summary>", body)
            for need in ("data-savings", "Confirm at checkout:", "data-terms-block",
                         "What the page states about this purchase", "Checked: "):
                self.assertIn(need, body)
            if 'data-coupon="yes"' in c:
                self.assertIn("data-window-row", body)
                self.assertIn("Window the page prints:", body)
                self.assertIn("Not applied:", body)

    def test_price_read_wording_stays_and_no_endorsement_is_on_the_first_view(self):
        neutral = [c for c in page_cards(self.page) if "data-page-read" in c]
        self.assertGreater(len(neutral), 200)
        for c in neutral:
            head = c[:c.index('<details class="more">')]
            self.assertIn("Price read from the store page", head)
            self.assertIn("Not compared with other stores.", head)
        for c in page_cards(self.page):
            head = c[:c.index('<details class="more">')]
            for word in ("Good to buy", "Worth a wait", "Check first", "✓", "best deal", "recommended"):
                self.assertNotIn(word, head)

    def test_card_names_are_unique_and_index_matches_the_catalog(self):
        cat = json.loads(re.search(r'id="catalog">(.*?)</script>', self.page, re.S).group(1))
        cards = page_cards(self.page)
        self.assertEqual(len(cat), len(cards))
        for c in cards:
            i = int(re.search(r'data-i="(\d+)"', c).group(1))
            self.assertEqual(html_lib.unescape(re.search(r'data-name="([^"]*)"', c).group(1)), cat[i]["n"])
            self.assertIn("data-price=\"%d\"" % cat[i]["pc"], c)
            self.assertEqual(cat[i]["cp"], html_lib.unescape(re.search(r'data-coupon-code="([^"]*)"', c).group(1)))
        found = [c["n"] for c in cat]
        self.assertEqual(len(found), len(set(found)))
        self.assertNotIn("</script", json.dumps(cat))

    def test_the_catalog_index_adds_nothing_the_cards_do_not_state(self):
        cat = json.loads(re.search(r'id="catalog">(.*?)</script>', self.page, re.S).group(1))
        for i, c in enumerate(page_cards(self.page)):
            terms = json.loads(html_lib.unescape(re.search(r'data-terms="([^"]*)"', c).group(1)))
            self.assertEqual(bool(cat[i]["sb"]), bool(terms["sb"]))
            self.assertEqual(bool(cat[i]["sh"]), bool(terms["sh"]))
            if terms["sh"]:
                self.assertEqual(cat[i]["sh"]["k"], terms["sh"]["k"])
                self.assertEqual(cat[i]["sh"]["members"], bool(terms["sh"].get("members")))
            self.assertEqual([z["k"] for z in cat[i]["z"]], [z["k"] for z in terms["z"]])

    # ---- 4. filters: optional, after results, counts equal the list -----------

    def test_chips_appear_only_after_there_are_results(self):
        self.assertEqual(self.d["load"]["chips"], [])
        self.assertFalse(self.d["load"]["refineShown"])
        for q in ("zzyzx", "espresso laptop"):
            self.assertFalse(self.d["typed"][q]["refineShown"], q)
        coffee = self.d["coffee"]
        self.assertTrue(coffee["refineShown"])
        keys = [c["key"] for c in coffee["chips"]]
        for k in ("size", "ship:min", "sub:true", "coupon:true"):
            self.assertTrue(any(x == k for x in keys), k)

    def test_filters_are_collapsed_on_a_phone_and_open_on_a_desktop(self):
        self.assertTrue(self.d["load"]["refineOpen"])
        self.assertFalse(self.d["loadPhone"]["refineOpen"])
        self.assertFalse(self.d["phoneCoffee"]["refineOpen"])
        self.assertTrue(self.d["phoneCoffee"]["refineShown"])      # there, one tap away
        self.assertTrue(self.d["phoneCoffee"]["main"])             # and never blocking the results
        self.assertIn("<details id=\"refine\"", self.page)

    def test_every_chip_count_is_the_length_of_the_list_it_gives(self):
        total = 0
        for q, rows in self.d["chipCounts"].items():
            for r in rows:
                total += 1
                self.assertEqual(r["said"], r["listed"], (q, r))
        self.assertGreater(total, 150)

    def test_chip_counts_match_an_independent_count_from_the_catalog(self):
        self.assertGreater(len(self.eng["chips"]), 150)
        for c in self.eng["chips"]:
            self.assertEqual((c["said"], c["listed"]), (c["oracle"], c["oracle"]), c)

    def test_a_page_that_says_nothing_is_never_counted_as_no(self):
        for u in self.eng["unknown"]:
            self.assertTrue(u["unkAllSilent"], u)
            self.assertTrue(u["noSilentListed"], u)
            self.assertTrue(u["disjoint"], u)
        s = self.d["coffeeSub"]
        self.assertIn("20 more products don’t state a subscribe option on the page, so they aren’t counted above.", s["unk"])
        self.assertEqual(len(s["main"]), 13)
        self.assertEqual(s["unkCards"], [])
        shown = self.d["coffeeSubShown"]
        self.assertTrue(shown["unkOpen"])
        self.assertEqual(len(shown["unkCards"]), 20)
        for c in shown["unkCards"]:
            self.assertIn("Subscribe: not stated — unknown", c["facts"])
        self.assertIn("Hide them", shown["unk"])
        self.assertFalse(self.d["coffeeSubHidden"]["unkOpen"])
        self.assertIn("listed separately", self.page)

    def test_size_filter_lists_only_pages_that_list_the_size_and_shows_that_size_price(self):
        two = self.d["coffeeSize2lb"]
        self.assertEqual([c["name"][:8] for c in two["main"]], ["Midnight", "Watershe"])
        self.assertEqual([c["price"] for c in two["main"]], ["$38.00", "$51.50"])
        for c in two["main"]:
            self.assertIn("2 lb bag", c["sizeLine"])
            self.assertEqual(c["shelf"], c["price"] + " for the 2 lb bag, as printed on the page")
            self.assertNotRegex(c["shelf"], r"(?i)code|coupon|off\b|save")
        self.assertIn("27 more products don’t state size on the page", two["unk"])
        back = self.d["coffeeSizeBack"]
        for c in back["main"]:
            self.assertEqual(c["price"], c["priceLabel"])
            self.assertEqual(c["sizeLine"], "")
        self.assertEqual(self.d["midnight5lb"]["main"][0]["price"], "$95.00")
        self.assertEqual(self.eng["sizePrice"]["midnight"], [["Midnight Axes dark roast, 12 oz bag", 3800, 1800]])
        self.assertTrue(self.eng["sizePrice"]["clothingMUnchanged"])

    def test_an_out_of_stock_size_is_not_listed(self):
        gap = [c for c in self.d["clothingSizeM"]["main"] if c["name"].startswith("CashSoft")]
        self.assertEqual(gap, [])  # Gap's page shows M out of stock
        old = [c for c in self.d["clothingSizeM"]["main"] if c["name"].startswith("High-Waisted")]
        self.assertEqual(len(old), 1)

    def test_a_chosen_chip_keeps_the_query_and_the_other_chips(self):
        s = self.d["queryKept"]
        self.assertEqual(s["q"], "coffee")
        self.assertEqual([a["key"] for a in s["active"]], ["sub", "coupon"])
        self.assertEqual(s["hash"], "#q=coffee&sub=1&coupon=1")
        self.assertTrue(s["clearAll"])

    def test_opening_a_kind_or_everything_keeps_nothing_blocking(self):
        self.assertEqual(self.d["tile"]["active"][0]["label"][:12], "Remove: Kind")
        self.assertEqual(self.d["browseAll"]["count"], "390 checked products")
        self.assertEqual(len(self.d["browseAll"]["main"]), 24)
        self.assertEqual(self.d["browseAll"]["showMore"], "Show 24 more (366 left)")
        self.assertEqual(self.d["afterKind"]["count"], "11 checked products for “coffee”")
        self.assertEqual(self.d["removeKind"]["count"], "33 checked products for “coffee”")

    # ---- 5. empty state, URL state ---------------------------------------------

    def test_empty_state_says_what_was_searched_and_offers_real_closest_products(self):
        e = self.d["typed"]["espresso laptop"]["empty"]
        self.assertIn("No checked product matches “espresso laptop”", e["text"])
        self.assertIn("for all of: “espresso”, “laptop”", e["text"])
        self.assertIn("Nothing is shown that doesn’t match, and nothing is guessed.", e["text"])
        near = e["near"]
        self.assertEqual(len(near), 3)
        self.assertIn("Flair Classic", [n["name"] for n in near])    # a real espresso maker, closest first
        for n in near:
            self.assertIn("Matches “espresso” · doesn’t match “laptop”", n["text"])
            self.assertTrue(n["href"].startswith("https://"))
        for b in ("Kitchen 46", "Browse all 390", "Clear search"):
            self.assertTrue([x for x in e["buttons"] if x.startswith(b)], b)
        z = self.d["typed"]["zzyzx"]["empty"]
        self.assertEqual(z["near"], [])
        self.assertIn("no close match to offer", z["text"])

    def test_empty_state_shortcuts_work(self):
        self.assertEqual(self.d["emptySearchKind"]["hash"], "#kind=Kitchen")
        self.assertEqual(self.d["emptySearchBrowse"]["hash"], "#all=1")
        self.assertEqual(self.d["emptySearchClear"]["hash"], "")
        self.assertTrue(self.d["emptySearchClear"]["startShown"])

    def test_empty_state_offers_to_drop_a_filter_with_what_would_show(self):
        e = self.d["emptyFilters"]
        self.assertEqual(e["q"], "airpods")
        self.assertIn("“airpods” matches 1 checked product, but none also fit your choices", e["empty"]["text"])
        self.assertIn("Drop Printed coupon 1 would show", e["empty"]["buttons"])
        d = self.d["emptyFiltersDrop"]
        self.assertEqual(names(d["main"]), ["AirPods Pro 3"])
        self.assertEqual(d["q"], "airpods")
        c = self.d["emptyFiltersClearAll"]
        self.assertEqual(c["q"], "airpods")
        self.assertEqual(c["active"], [])
        self.assertEqual(names(c["main"]), ["AirPods Pro 3"])
        n = self.d["emptyNoQuery"]
        self.assertIn("None of the checked products state a match for these choices", n["empty"]["text"])
        self.assertEqual(self.d["emptyNoQueryClear"]["active"], [])

    def test_state_lives_in_the_address_bar_so_back_and_refresh_work(self):
        h = self.d["history"]
        fwd = h["forward"]
        # typing replaces the entry; each chosen chip is a new entry
        kinds = [x[0] for x in fwd["history"]]
        self.assertEqual(kinds, ["replace", "replace", "push", "push"])
        self.assertEqual(fwd["hash"], "#q=coffee&sub=1&coupon=1")
        self.assertEqual(h["back1"]["hash"], "#q=coffee&sub=1")
        self.assertEqual([a["key"] for a in h["back1"]["active"]], ["sub"])
        self.assertEqual(h["back2"]["count"], "33 checked products for “coffee”")
        self.assertEqual(h["back2"]["q"], "coffee")
        self.assertTrue(h["back3"]["startShown"])
        self.assertEqual(h["back3"]["q"], "")
        refreshed = self.d["loadWithHash"]
        self.assertEqual(refreshed["q"], "cofee")
        self.assertEqual([a["key"] for a in refreshed["active"]], ["ship"])
        self.assertEqual(refreshed["count"].split(" ")[0], str(len(refreshed["main"])) if len(refreshed["main"]) < 24 else "24")
        r = self.d["hashRestore"]
        self.assertEqual(r["#kind=Shoes"]["count"], "11 checked products")
        self.assertEqual(r["#all=1"]["count"], "390 checked products")
        lo = [self.cents(c["priceLabel"]) for c in r["#q=coffee&sort=lo"]["main"]]
        self.assertEqual(lo, sorted(lo))
        self.assertEqual(r["#q=coffee&size=2%20lb"]["count"], "2 checked products for “coffee”")
        self.assertEqual(r["#store=Lavazza"]["count"], "3 checked products")
        bad = r["#kind=Nope&ship=weird&q=tea"]            # unknown values are dropped, not trusted
        self.assertEqual(bad["active"], [])
        self.assertEqual(bad["q"], "tea")
        self.assertEqual(r["#q=%E0%A4%A"]["startShown"], True)
        for h_, o in self.eng["hash"].items():
            self.assertTrue(o["again"], h_)
        self.assertEqual(self.eng["hash"]["kind=Nope&ship=weird&q=tea&sort=zzz"]["encoded"], "q=tea")

    # ---- keyboard and accessibility ---------------------------------------------

    def test_arrow_keys_move_through_suggestions_and_enter_chooses(self):
        d = self.d
        self.assertTrue(d["kbOpen"]["sugg"]["shown"])
        self.assertEqual(d["kbOpen"]["sugg"]["expanded"], "true")
        self.assertEqual([i["selected"] for i in d["kbOpen"]["sugg"]["items"]][:2], [False, False])
        down = d["kbDown"]["sugg"]
        self.assertTrue(down["items"][0]["selected"])
        self.assertEqual(down["active"], "sg0")
        self.assertTrue(d["kbDown2"]["sugg"]["items"][1]["selected"])
        self.assertEqual(d["kbDown2"]["sugg"]["active"], "sg1")
        up = d["kbUp"]["sugg"]
        self.assertTrue(up["items"][-1]["selected"])          # wraps to the last
        k = d["kbEnterKind"]
        self.assertEqual(k["hash"], "#kind=Coffee")
        self.assertFalse(k["sugg"]["shown"])
        self.assertEqual(k["q"], "")
        none = d["kbEnterNone"]
        self.assertFalse(none["sugg"]["shown"])
        self.assertEqual(none["q"], "cof")
        p = d["kbProduct"]
        self.assertEqual(p["q"], "The Breville Bambino™")
        self.assertEqual(names(p["main"]), ["The Breville Bambino™"])
        s = d["clickSugg"]
        self.assertEqual(s["hash"], "#store=Old%20Navy")
        self.assertTrue(d["kbOpen"]["sugg"]["items"][0]["text"].startswith("Coffee"))

    def test_scrolling_the_page_closes_the_list_that_covers_the_results(self):
        d = self.d
        self.assertTrue(d["kbOpen"]["sugg"]["shown"])
        self.assertTrue(d["scrollSmall"]["sugg"]["shown"])           # a nudge keeps it
        self.assertFalse(d["scrollFar"]["sugg"]["shown"])
        self.assertEqual(d["scrollFar"]["q"], "coffee")              # the words and results stay
        self.assertEqual(names(d["scrollFar"]["main"]), names(d["kbOpen"]["main"]))
        down = d["scrollThenArrow"]["sugg"]                          # arrows bring it back, no extra key
        self.assertTrue(down["shown"])
        self.assertTrue(down["items"][0]["selected"])
        self.assertTrue(d["scrollThenType"]["sugg"]["shown"])        # typing opens it again

    def test_escape_closes_suggestions_then_clears_the_box_then_the_size_list(self):
        d = self.d
        self.assertFalse(d["kbEscape1"]["sugg"]["shown"])
        self.assertEqual(d["kbEscape1"]["q"], "cof")
        self.assertEqual(d["kbEscape2"]["q"], "")
        self.assertTrue(d["kbEscape2"]["startShown"])
        self.assertEqual(d["coffeeSizeOpen"]["sizeButton"]["expanded"], "true")
        self.assertEqual(d["kbEscapePop"]["sizeButton"]["expanded"], "false")
        self.assertEqual(d["kbEscapePop"]["focus"]["chip"], "size")
        self.assertEqual(d["clearButton"]["q"], "")
        self.assertTrue(d["clearButton"]["focus"]["isQ"])

    def test_controls_are_labelled_and_reachable_by_keyboard(self):
        page = self.page
        self.assertIn('role="combobox" aria-expanded="false" aria-controls="sugg" aria-autocomplete="list"', page)
        self.assertIn('role="listbox" aria-label="Suggestions"', page)
        self.assertIn('aria-label="Clear search"', page)
        self.assertIn('<label for="sort">Sort</label>', page)
        self.assertIn('id="count" aria-live="polite"', page)
        self.assertIn(":focus-visible{outline:3px solid", page)
        self.assertIn('name="viewport"', page)
        self.assertIn('<html lang="en">', page)
        for c in self.d["coffee"]["chips"]:
            self.assertRegex(c["label"], r"\S")
        self.assertTrue([c for c in self.d["coffee"]["chips"] if re.search(r", \d+ results?$", c["label"])])
        for a in self.d["coffeeSub"]["active"]:
            self.assertTrue(a["label"].startswith("Remove: "))

    def test_every_tap_target_is_at_least_44_px(self):
        css = read("demo", "page.css")
        for sel in (".clear-x", ".linkbtn", ".chip", ".go", ".sortbox select", "details.more>summary",
                    ".refine>summary", ".showmore", ".nearitem a", ".sg"):
            m = re.search(re.escape(sel) + r"\{[^}]*min-(?:height|width):(\d+)px", css) \
                or re.search(re.escape(sel) + r"\{[^}]*min-height:(\d+)px", css)
            self.assertIsNotNone(m, sel)
            self.assertGreaterEqual(int(m.group(1)), 44, sel)
        self.assertIn(".tile{width:100%;min-height:76px", css)
        self.assertIn("@media (max-width:640px)", css)
        self.assertNotIn("min-width:390", css)

    def test_a_quoted_coupon_is_never_cut_short_on_screen(self):
        css = read("demo", "page.css")
        self.assertNotIn("line-clamp", css)

    def test_page_is_self_contained_no_cdn_script_or_stylesheet(self):
        self.assertNotRegex(self.page, r'<script[^>]+src=')
        self.assertNotRegex(self.page, r'<link[^>]+rel="stylesheet"')

    # ---- evidence rules the page must keep --------------------------------------

    def test_every_card_states_shelf_price_coupon_and_what_is_unknown(self):
        cards = page_cards(self.page)
        self.assertGreaterEqual(len(cards), 100)
        with_coupon = 0
        for c in cards:
            box = re.search(r'data-savings>(.*?)</ul></div>', c, re.S).group(1)
            text = re.sub(r"<[^>]+>", " ", box)
            text = re.sub(r"\s+", " ", text)
            label = re.search(r'data-price-label="([^"]*)"', c).group(1)
            self.assertTrue(re.sub(r"\s+([.])", r"\1", text).strip().startswith(
                label + " as printed on the page. "), text)
            self.assertIn("Confirm at checkout:", text)
            self.assertIn("tax", text.split("Confirm at checkout:")[1])
            if 'data-coupon="yes"' in c:
                with_coupon += 1
                code = re.search(r'data-coupon-code="([^"]*)"', c).group(1)
                self.assertIn("Coupon on this page: " + code, text)
                self.assertIn("the page says", text)
                self.assertIn("Conditions: only as that wording states them", text)
                self.assertIn("Not applied:", text)
                self.assertIn("does not include it", text)
                self.assertIn("whether the code works", text.split("Confirm at checkout:")[1])
            else:
                self.assertIn("No coupon printed on the page .", text)
                self.assertNotIn("Not applied", text)
                self.assertNotIn("whether the code works", text)
        self.assertEqual(with_coupon, 19)  # 9 + 6 Untuckit (NOIRON) + 4 Open Farm first-Autoship code

    def test_a_seen_code_is_never_shown_as_a_lower_price(self):
        for c in page_cards(self.page):
            if 'data-coupon="yes"' not in c:
                continue
            label = re.search(r'data-price-label="([^"]*)"', c).group(1)
            price = re.search(r'data-price-text>([^<]*)<', c).group(1)
            self.assertEqual(price, label)
            line = re.search(r'<span data-shelf-line>([^<]*)</span>', c).group(1)
            self.assertEqual(line, label + " as printed on the page")
            self.assertNotRegex(line, r"(?i)code|coupon|off|save")
        for key in ("coffeeCoupon", "queryKept", "coffeeSize2lb"):
            for c in self.d[key]["main"]:
                self.assertEqual(c["price"] if not c["sizeLine"] else c["price"], c["price"])
                self.assertNotRegex(c["shelf"], r"(?i)code|coupon|off\b|save", key)
        for c in self.d["coffeeCoupon"]["main"]:
            self.assertEqual(c["price"], c["priceLabel"])

    def test_the_page_keeps_quiet_no_urgency_or_scarcity(self):
        banned = ("hurry", "limited time", "ends soon", "last chance", "act now",
                  "don't miss", "countdown", "running out", "selling fast",
                  "only a few left", "expires", "deal of the day", "best deal", "recommend")
        for key in ("load", "coffee", "emptyFilters", "typed"):
            snaps = list(self.d[key].values()) if key == "typed" else [self.d[key]]
            for s in snaps:
                low = (s["pageText"] + " " + " ".join(s["empty"]["buttons"] if s["empty"] else [])).lower()
                for word in banned:
                    self.assertNotIn(word, low, (key, word))
        low = self.page.lower()
        script = low[low.index("<script>"):]
        for word in ("setinterval", "settimeout", "date.now"):
            self.assertNotIn(word, script)

    def test_the_page_reads_the_date_once_for_the_age_line_and_once_for_a_live_read_time(self):
        script = self.page[self.page.index("<script>"):]
        self.assertEqual(script.count("new Date()"), 2)
        live_time = script[script.index("function liveTime"):]
        self.assertEqual(live_time[:live_time.index("}\n")].count("new Date()"), 1)

    def test_each_card_says_how_old_its_stored_check_is_in_plain_days(self):
        # the page script runs with "today" pinned to 2026-10-05
        for c in page_cards(self.page):
            iso = re.search(r'data-observed="([^"]*)"', c).group(1)
            self.assertIn("Checked " + iso[:10] + "</p>", c)  # no-script fallback: date only
            self.assertEqual(iso, re.search(r"Checked: [^<]*· (\d{4}[^<]*)</p>", c).group(1))
        seen = set()
        for c in self.d["load"]["all"]:
            seen.add(c["age"])
            self.assertRegex(c["age"], AGE_RE)
            for word in ("fresh", "stale", "old", "expired", "recent", "outdated", "valid"):
                self.assertNotIn(word, c["age"].lower())
        # the three coffee hand cards were re-read 2026-10-04: no card reads days old
        self.assertIn("Checked 38 hours ago, 2026-10-04T00:56:40Z", seen)
        self.assertIn("Checked 39 hours ago, 2026-10-03T23:15:06Z", seen)
        self.assertFalse([a for a in seen if "days ago" in a], seen)

    def test_the_age_line_counts_hours_under_48_and_whole_days_after_from_the_stored_time(self):
        # AirPods Pro 3 was stored at 2026-10-03T23:15:06Z; the clock is pinned for each run
        stamp = "2026-10-03T23:15:06Z"
        cases = {
            "2026-10-03T22:00:00Z": "Checked 2026-10-03",                       # before the check: no age
            "2026-10-03T23:45:00Z": "Checked less than 1 hour ago, " + stamp,
            # an hour after the check, just past 00:00 UTC: not "1 day ago"
            "2026-10-04T00:16:00Z": "Checked 1 hour ago, " + stamp,
            "2026-10-04T05:15:06Z": "Checked 6 hours ago, " + stamp,
            "2026-10-05T23:15:05Z": "Checked 47 hours ago, " + stamp,
            "2026-10-05T23:15:06Z": "Checked 2 days ago, 2026-10-03",
            "2026-10-07T23:15:05Z": "Checked 3 days ago, 2026-10-03",
        }
        for now, want in cases.items():
            card = [c for c in drive(os.path.join(ROOT, "demo", "index.html"), now=now, only_load=True)["load"]["all"]
                    if c["name"] == "AirPods Pro 3"][0]
            self.assertEqual(card["age"], want, now)

    def test_confirm_at_checkout_lists_only_what_the_stored_evidence_leaves_unknown(self):
        known = unknown = 0
        for c in page_cards(self.page):
            box = re.search(r'data-savings>(.*?)</ul></div>', c, re.S).group(1)
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", box))
            line = re.search(r"Confirm at checkout: (.*?)\.(?: |$)", text).group(1)
            self.assertEqual(text.count("Confirm at checkout:"), 1)
            terms = json.loads(html_lib.unescape(re.search(r'data-terms="([^"]*)"', c).group(1)))
            self.assertIn("tax", line)
            if terms["sh"]:
                known += 1
                self.assertNotIn("shipping", line)
            else:
                unknown += 1
                self.assertRegex(
                    line, r"shipping cost \(the page(?:&#x27;s printed shipping "
                          r"line was not read as a condition for this item|"
                          r" did not state it)\)")
            if 'data-coupon="yes"' in c:
                self.assertIn("whether the code works and what it would take off", line)
            else:
                self.assertNotIn("code", line)
        self.assertGreater(known, 0)
        self.assertGreater(unknown, 0)

    def test_savings_box_opens_with_shelf_price_and_plain_saving_status(self):
        for c in page_cards(self.page):
            label = re.search(r'data-price-label="([^"]*)"', c).group(1)
            lead = re.sub(r"<[^>]+>", "", re.search(r"data-saving-lead>(.*?)</p>", c, re.S).group(1))
            status = "Coupon printed, not applied" if 'data-coupon="yes"' in c \
                else "No coupon printed on the page"
            self.assertEqual(lead, label + " as printed on the page. " + status + ".")
            self.assertLess(c.index("data-saving-lead"), c.index("Confirm at checkout:"))
        for c in self.d["load"]["all"]:
            status = "Coupon printed, not applied" if c["coupon"] == "yes" else "No coupon printed on the page"
            if c["windowState"] == "ended":
                status = "The page's printed window has ended"
            self.assertEqual(c["lead"], c["shelf"] + ". " + status + ".")

    def test_coffee_note_matches_evidence_and_shows_only_with_coffee(self):
        m = re.search(r"Coffee note: ([^<]*)", self.page)
        self.assertIsNotNone(m)
        note = m.group(1)
        self.assertIn("Dolcevita Classico, Qualità Rossa and Super Crema "
                      "showed the code AS20", note)
        for seller in ("Honest Coffee Roasters", "The Well Coffee Roasters",
                       "Counter Culture Coffee"):
            self.assertIn(seller, note)
        self.assertIn("shelf price", note)
        self.assertEqual(self.d["coffee"]["coffeeNote"], "")
        for q in ("tea", "airpods", "shoes", "clothing"):
            self.assertEqual(self.d["typed"][q]["coffeeNote"], "none", q)

    def test_coupon_cards_match_note(self):
        cards = page_cards(self.page)
        with_code = {re.search(r'data-name="([^"]*)"', c).group(1)
                     for c in cards if 'data-coupon="yes"' in c and "AS20" in c}
        self.assertEqual(len(with_code), 3)
        for c in cards:
            if "Midnight Axes" in c or "Watershed" in c or "Big Trouble" in c:
                self.assertIn('data-coupon="no"', c)

    def test_lavazza_records_carry_the_2026_10_04_observation_and_keep_history(self):
        import glob
        files = sorted(glob.glob(os.path.join(ROOT, "demo", "evidence", "lavazza", "*.json")))
        self.assertEqual(len(files), 3)
        cards = page_cards(self.page)
        for fn in files:
            with open(fn, encoding="utf-8") as f:
                rec = json.load(f)
            first, latest = rec["observations"][0], rec["observations"][-1]
            # the earlier CAFE20 read stays as dated history, never deleted
            self.assertEqual((first["code"], first["observed_at"][:10]), ("CAFE20", "2026-10-01"), fn)
            # the 2026-10-03 AS20 read stays as history; the card shows 2026-10-04
            self.assertEqual((rec["observations"][1]["code"], rec["observations"][1]["observed_at"][:10]),
                             ("AS20", "2026-10-03"), fn)
            self.assertEqual((latest["code"], latest["observed_at"][:10]), ("AS20", "2026-10-04"), fn)
            self.assertIn("AS20", latest["banner"])
            self.assertFalse(latest["code_tried"])
            self.assertEqual(latest["shelf_price"], first["shelf_price"])
            card = [c for c in cards if rec["page_url"] in c]
            self.assertEqual(len(card), 1, fn)
            card = card[0]
            self.assertIn("Checked: lavazzausa.com · US · " + latest["observed_at"], card)
            self.assertIn(">AS20</span>", card)
            self.assertNotIn("CAFE20", card)
            self.assertIn("never tried out", card)
            self.assertIn("price shown does not include it", card)
            self.assertIn('data-price="%d"' % round(latest["shelf_price"] * 100), card)
        self.assertNotIn("CAFE20", self.page)

    def test_vague_recheck_wording_is_gone(self):
        self.assertNotIn("recheck at checkout", self.page)
        self.assertNotIn("Not known:", self.page)


class PrintedWindowTest(unittest.TestCase):
    """A coupon page's own printed date window against the browser's date."""

    PAGE = os.path.join(ROOT, "demo", "index.html")
    UNTUCKIT = "NOIRON"
    CASES = {  # pinned browser time -> (state, status text)
        "2026-09-30T15:00:00Z": ("before", "Today in US Eastern time (2026-09-30) is before the page's printed window."),
        "2026-10-01T15:00:00Z": ("inside", "Today in US Eastern time (2026-10-01) is inside the page's printed window."),
        "2026-10-04T15:00:00Z": ("inside", "Today in US Eastern time (2026-10-04) is inside the page's printed window."),
        "2026-10-05T15:00:00Z": ("ended", "The page's printed window has ended (today in US Eastern time is 2026-10-05)."),
    }

    @classmethod
    def setUpClass(cls):
        cls.page = read("demo", "index.html")
        cls.runs = {now: drive(cls.PAGE, now=now, only_load=True)["load"]["windows"]
                    for now in cls.CASES}

    def untuckit(self, now):
        return [w for w in self.runs[now] if w["code"] == self.UNTUCKIT]

    def test_window_is_stated_before_inside_and_after_the_printed_dates(self):
        for now, (state, text) in self.CASES.items():
            rows = self.untuckit(now)
            self.assertEqual(len(rows), 6, now)
            for w in rows:
                self.assertEqual(w["state"], state, now)
                self.assertTrue(w["status"].startswith(text), (now, w["status"]))
                self.assertEqual(w["windowStart"], "2026-10-01")
                # never a lower price, in any state
                self.assertEqual(w["price"], w["priceLabel"])

    def test_an_ended_window_is_information_not_an_offer(self):
        for w in self.untuckit("2026-10-05T15:00:00Z"):
            self.assertEqual(w["lead"], w["priceLabel"] + " as printed on the page. "
                             "The page's printed window has ended.")
            self.assertTrue(w["label"].startswith("The page's printed window has ended"))
            self.assertIn("information only", w["label"])
            self.assertIn("not as an available offer", w["status"])
            self.assertIn("whether any offer is still available", w["confirm"])
            self.assertNotIn("Coupon printed, not applied", w["lead"])
            # the compact card says so too, and still says not applied
            self.assertIn("Its printed window has ended: information only, not an available offer.", w["couponLine"])
            self.assertIn("Not applied:", w["couponLine"])
        for now in ("2026-09-30T15:00:00Z", "2026-10-04T15:00:00Z"):
            for w in self.untuckit(now):
                self.assertNotIn("has ended", w["lead"])
                self.assertNotIn("has ended", w["couponLine"])

    def test_before_and_inside_still_say_seen_never_tried(self):
        for now in ("2026-09-30T15:00:00Z", "2026-10-04T15:00:00Z"):
            for w in self.untuckit(now):
                self.assertEqual(w["lead"], w["priceLabel"] + " as printed on the page. "
                                 "Coupon printed, not applied.")
                self.assertEqual(w["label"], "Coupon on this page:")
                self.assertEqual(w["confirm"], "whether the code works and what it would take off")
        self.assertIn("The code is still never tried", self.untuckit("2026-10-04T15:00:00Z")[0]["status"])

    def test_coupons_with_no_printed_window_say_so_on_any_date(self):
        for now, rows in self.runs.items():
            others = [w for w in rows if w["code"] != self.UNTUCKIT]
            self.assertEqual(len(others), 13, now)  # 9 + 4 Open Farm pages
            for w in others:
                self.assertEqual(w["state"], "none", now)
                self.assertTrue(w["status"].startswith("the coupon text states no date window"), w["status"])
                self.assertIsNone(w["windowStart"])
                self.assertNotIn("has ended", w["lead"])
                self.assertEqual(w["lead"], w["priceLabel"] + " as printed on the page. "
                                 "Coupon printed, not applied.")

    def test_printed_conditions_are_quoted_word_for_word_from_the_stored_text(self):
        stored = json.loads(read("demo", "evidence", "untuckit-normand.json"))["coupon_snippets"][0]
        quote = "Cannot be combined with any offers or promotions."
        self.assertIn(quote, stored)
        for w in self.untuckit("2026-10-05T15:00:00Z"):
            self.assertEqual(len(w["conditions"]), 1)
            self.assertIn("“" + quote + "”", w["conditions"][0])
            for sentence in re.findall("“([^”]*)”", w["conditions"][0]):
                self.assertIn(sentence, stored)
        # the window quote is a verbatim piece of the stored page text too
        for m in re.finditer(r"Window the page prints:</span> “([^”]*)”",
                             html_lib.unescape(self.page)):
            self.assertEqual(m.group(1), "10/1/2026 at 12:00 AM ET through 10/4/2026 at 11:59 PM ET")
            self.assertIn(m.group(1), stored)

    def test_the_page_adds_no_countdown_or_urgency(self):
        for word in ("hurry", "last chance", "ends soon", "countdown", "only today"):
            self.assertNotIn(word, self.page.lower())


class PrintedWindowParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, os.path.join(ROOT, "demo"))
        sys.path.insert(0, ROOT)
        import build
        cls.window = staticmethod(build.printed_window)
        cls.conditions = staticmethod(build.printed_conditions)

    def test_two_explicit_dates_make_a_window(self):
        w = self.window("Offer valid 10/1/2026 at 12:00 AM ET through 10/4/2026 at 11:59 PM ET, online.")
        self.assertEqual((w["start"], w["end"]), ("2026-10-01", "2026-10-04"))
        self.assertEqual(w["quote"], "10/1/2026 at 12:00 AM ET through 10/4/2026 at 11:59 PM ET")
        w = self.window("Use code X from Oct 1, 2026 to October 4, 2026.")
        self.assertEqual((w["start"], w["end"]), ("2026-10-01", "2026-10-04"))

    def test_ambiguous_or_absent_dates_make_no_window(self):
        for text in (
            "Use code X at checkout.",
            "Ends 10/4/2026.",                       # one date: start or end unclear
            "Valid 10/1 to 10/4.",                   # no year
            "Valid 10/1/26 through 10/4/26.",        # two-digit year
            "Valid 10/4/2026 through 10/1/2026.",    # out of order
            "Valid 13/45/2026 through 14/45/2026.",  # impossible dates
            "Valid 10/1/2026, 10/4/2026 and 10/9/2026.",  # three dates
            "Valid through the end of the month.",
            "", None,
        ):
            self.assertIsNone(self.window(text), text)

    def test_conditions_are_whole_sentences_quoted_as_printed(self):
        text = ("Offer valid 10/1/2026 through 10/4/2026. Enter code X. Cannot be combined "
                "with any offers or promotions. Offer has no cash value and is not valid on gift c")
        self.assertEqual(self.conditions(text),
                         ["Cannot be combined with any offers or promotions."])  # truncated tail is not quoted
        self.assertEqual(self.conditions("Use code X."), [])



LIVE_FIXTURE = os.path.join(ROOT, "tests", "live_search_fixture.json")
SAVING_WORDS = re.compile(r"sav(e|es|ed|ing|ings)\b|discount|\bdeal\b|\bcode\b|promo|coupon|\boff\b|\bwas\b|\bbest\b|\bonly \d|hurry|limited|endorse|recommend", re.I)


def live(scenarios):
    env = dict(os.environ, TZ="UTC", LIVE_FIXTURE=LIVE_FIXTURE, LIVE_SCENARIOS=json.dumps(scenarios))
    proc = subprocess.run(["node", DRIVER, os.path.join(ROOT, "demo", "index.html")], check=False,
                          capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


class LiveSearchTest(unittest.TestCase):
    """'Search stores live': Shopify's keyless catalog, called from the page, nothing stored.
    The fixture is a real recorded reply (tests/live_search_fixture.json); a scripted fetch returns it."""

    @classmethod
    def setUpClass(cls):
        with open(LIVE_FIXTURE, encoding="utf-8") as f:
            cls.fx = json.load(f)
        cls.products = cls.fx["response"]["result"]["structuredContent"]["products"]
        cls.d = live({
            "ok": {}, "noavail": {"mutate": "dropAvailability"}, "inject": {"mutate": "injectDiscountFields"},
            "reject": {"fail": "reject"}, "status": {"fail": "status"}, "rpc": {"fail": "rpcError"},
            "nofetch": {"noFetch": True}, "empty": {"empty": True}, "noprice": {"mutate": "dropPrice"},
            "eur": {"mutate": "foreignCurrency"}, "moveon": {"thenType": "coffee"},
        })

    def test_the_fixture_is_a_real_recording_with_tracking_parameters_in_it(self):
        self.assertEqual(len(self.products), 10)
        self.assertRegex(self.fx["recorded_at"], r"^2026-10-04T")
        urls = [p["variants"][0]["url"] for p in self.products]
        self.assertTrue(all("_gsid=" in u or "utm_source=" in u for u in urls[:3]))

    def test_the_call_is_the_one_the_design_specifies(self):
        calls = self.d["ok"]["calls"]
        self.assertEqual(len(calls), 1)
        c = calls[0]
        self.assertEqual(c["url"], "https://catalog.shopify.com/api/ucp/mcp")
        self.assertEqual(c["init"]["method"], "POST")
        self.assertEqual(c["init"]["headers"], {"Content-Type": "text/plain"})  # application/json fails the preflight
        body = json.loads(c["init"]["body"])
        self.assertEqual(body["method"], "tools/call")
        self.assertEqual(body["params"]["name"], "search_catalog")
        a = body["params"]["arguments"]
        self.assertEqual(a["meta"]["ucp-agent"]["profile"], "https://thewyattbrocato.github.io/ai-deal-finder/ucp-agent.json")
        self.assertEqual(a["catalog"]["query"], "waffle knit hoodie men")
        self.assertEqual(a["catalog"]["context"], {"address_country": "US", "currency": "USD"})
        self.assertEqual(a["catalog"]["pagination"], {"limit": 10})

    def test_nothing_is_sent_until_the_shopper_asks_and_the_words_going_out_are_said(self):
        b = self.d["ok"]["before"]
        self.assertEqual(b["calls"], 0)
        self.assertTrue(b["btnShown"])
        self.assertIn("Live search sends your search words to Shopify", b["privacy"])

    def test_each_card_shows_exactly_the_fixture_price_seller_and_title(self):
        cards = self.d["ok"]["cards"]
        self.assertEqual(len(cards), 10)
        for card, p in zip(cards, self.products):
            v = p["variants"][0]
            self.assertEqual(card["price"], "$%d.%02d" % divmod(v["price"]["amount"], 100))
            self.assertEqual(card["title"], p["title"].strip())
            self.assertEqual(card["seller"], "Seller: " + v["seller"]["name"])
        self.assertEqual(cards[0]["price"], "$105.00")
        self.assertEqual(cards[3]["price"], "$85.00")
        self.assertEqual(cards[4]["price"], "$34.00")

    def test_stock_follows_the_catalog_and_missing_availability_says_not_stated(self):
        got = [c["stock"] for c in self.d["ok"]["cards"]]
        want = ["In stock" if p["variants"][0]["availability"]["available"] else "Out of stock" for p in self.products]
        self.assertEqual(got, want)
        self.assertIn("Out of stock", got)
        self.assertIn("In stock", got)
        self.assertEqual({c["stock"] for c in self.d["noavail"]["cards"]}, {"Stock not stated"})

    def test_links_lose_the_tracking_parameters_and_keep_the_variant(self):
        for card, p in zip(self.d["ok"]["cards"], self.products):
            raw = p["variants"][0]["url"]
            self.assertNotIn("_gsid", card["href"])
            self.assertNotIn("utm_", card["href"])
            self.assertTrue(raw.startswith(card["href"]), (raw, card["href"]))
            if "variant=" in raw:
                self.assertIn("variant=", card["href"])

    def test_every_card_carries_its_four_plain_labels(self):
        for c in self.d["ok"]["cards"]:
            self.assertRegex(c["source"], r"^Price from the store.s Shopify catalog, read at .+ today$")
            self.assertEqual(c["scope"], "Not compared with stores outside Shopify")
            self.assertEqual(c["coupon"], "Coupon: not checked")
            self.assertEqual(c["tax"], "Tax and shipping not shown")

    def test_no_coupon_saving_or_endorsement_wording_appears(self):
        allowed = ("Coupon: not checked",)
        for name in ("ok", "noavail", "inject"):
            for c in self.d[name]["cards"]:
                text = c["text"]
                for a in allowed:
                    text = text.replace(a, "")
                self.assertIsNone(SAVING_WORDS.search(text), (name, text))
        panel = self.d["ok"]["liveText"]
        for a in allowed:
            panel = panel.replace(a, "")
        self.assertIsNone(SAVING_WORDS.search(panel), panel)

    def test_a_checkout_link_a_was_price_a_discount_or_a_description_is_never_shown(self):
        injected = self.d["inject"]
        self.assertEqual([c["price"] for c in injected["cards"]], [c["price"] for c in self.d["ok"]["cards"]])
        for c in injected["cards"]:
            self.assertNotIn("example.test", c["href"] or "")
        for bad in ("example.test", "999.99", "50% off", "SAVE BIG"):
            self.assertNotIn(bad, injected["liveText"])

    def test_live_results_are_in_the_catalogs_order_with_no_sort_offered(self):
        self.assertEqual([c["title"] for c in self.d["ok"]["cards"]], [p["title"].strip() for p in self.products])
        page = read("demo", "index.html")
        live_part = page[page.index('id="live"'):page.index('id="stored-head"')]
        self.assertNotIn("<select", live_part)

    def test_stored_results_are_labelled_observed_examples_beside_live_ones(self):
        ok = self.d["ok"]
        self.assertFalse(ok["before"]["storedHead"])
        self.assertTrue(ok["storedHeadShown"])
        self.assertEqual(ok["storedHeadText"], "Observed examples, read earlier")
        # the stored list itself is the same as before the live search was asked for
        self.assertEqual(ok["storedCount"], ok["before"]["stored"])

    def test_the_stored_path_gains_no_click_or_key(self):
        before = self.d["ok"]["before"]
        self.assertEqual(before["calls"], 0)
        page = drive(os.path.join(ROOT, "demo", "index.html"))
        self.assertEqual(page["typed"]["coffee"]["areaShown"], True)
        self.assertTrue(page["typed"]["coffee"]["main"])
        self.assertEqual(self.d["moveon"]["before"]["calls"], 0)

    def test_a_failed_call_says_so_and_the_stored_examples_stay(self):
        for name in ("reject", "status", "rpc", "nofetch"):
            d = self.d[name]
            self.assertIn("Live search is unavailable right now", d["liveText"], name)
            self.assertEqual(d["cards"], [], name)
            self.assertTrue(d["storedHeadShown"], name)
        # a reply that is not a product list is a failure, not an empty result
        self.assertNotIn("returned no products", self.d["rpc"]["liveText"])

    def test_an_empty_reply_says_nothing_was_returned_and_guesses_nothing(self):
        t = self.d["empty"]["liveText"]
        self.assertIn("returned no products", t)
        self.assertIn("Nothing is guessed", t)
        self.assertEqual(self.d["empty"]["cards"], [])

    def test_a_result_without_a_usd_price_is_left_out_and_counted_not_priced(self):
        for name in ("noprice", "eur"):
            d = self.d[name]
            self.assertEqual(len(d["cards"]), 9, name)
            self.assertIn("1 result was left out because the catalog gave no USD price for it", d["liveText"], name)
        self.assertNotIn(self.products[0]["title"], self.d["noprice"]["liveText"])

    def test_live_results_do_not_outlive_the_words_they_were_fetched_for(self):
        a = self.d["moveon"]["afterType"]
        self.assertFalse(a["storedHead"])
        self.assertNotIn("Live from Shopify", a["live"])
        self.assertNotIn("Seller:", a["live"])

    def test_nothing_is_stored_and_the_address_bar_does_not_carry_the_live_results(self):
        self.assertNotIn("live", self.d["ok"]["hash"])
        view = read("demo", "view.js")
        for banned in ("localStorage", "sessionStorage", "indexedDB", "document.cookie"):
            self.assertNotIn(banned, view)

    def test_the_view_never_reads_checkout_or_inferred_fields(self):
        eng = read("demo", "engine.js")
        live_src = eng[eng.index("var LIVE_ENDPOINT"):]
        parse_src = live_src[live_src.index("function liveParse"):live_src.index("return { create:")]
        for banned in ("checkout_url", ".description", ".options", ".metadata", ".rating", ".condition", ".eligible"):
            self.assertNotIn(banned, parse_src, banned)

    def test_the_agent_profile_is_published_with_the_page_and_asks_for_search_and_lookup_only(self):
        a = json.loads(read("docs", "ucp-agent.json"))
        self.assertEqual(a, json.loads(read("demo", "ucp-agent.json")))
        self.assertEqual(sorted(a["ucp"]["capabilities"]),
                         ["dev.ucp.shopping.catalog.lookup", "dev.ucp.shopping.catalog.search"])
        self.assertEqual(a["ucp"]["version"], "2026-08-25")
        for banned in ("checkout", "cart", "order", "discount", "buyer_consent"):
            self.assertNotIn(banned, " ".join(a["ucp"]["capabilities"]))

if __name__ == "__main__":
    unittest.main()


class FocusWalkTest(unittest.TestCase):
    """Defects found walking the live page in a real browser: a NodeList has no
    filter(), so every chip click threw after drawing, and focus fell to the
    page body; a phone's keyboard was raised over the list by taps."""

    @classmethod
    def setUpClass(cls):
        cls.d = drive(os.path.join(ROOT, "demo", "index.html"))

    def focus(self, key):
        return self.d[key]["focus"]

    def test_picking_a_kind_chip_moves_focus_to_its_remove_chip_not_the_body(self):
        self.assertEqual(self.focus("focusAfterKind")["remove"], "kind")

    def test_picking_a_size_returns_focus_to_the_size_button(self):
        self.assertEqual(self.focus("focusAfterSize")["chip"], "size")

    def test_escape_in_the_size_list_returns_focus_to_the_size_button(self):
        self.assertEqual(self.focus("focusAfterEscape")["chip"], "size")

    def test_desktop_tile_and_remove_keep_focus_in_the_box_for_typing(self):
        self.assertTrue(self.focus("focusTileDesktop")["isQ"])
        self.assertTrue(self.focus("focusRemoveDesktop")["isQ"])

    def test_phone_tile_and_remove_do_not_raise_the_keyboard(self):
        for k in ("focusTilePhone", "focusRemovePhone"):
            self.assertFalse(self.focus(k)["isQ"], k)
            self.assertEqual(self.focus(k)["id"], "count", k)

    def test_buttons_that_disappear_hand_focus_to_the_count_line(self):
        self.assertEqual(self.focus("focusEmptyKind")["id"], "count")
        self.assertEqual(self.focus("focusShowMore")["id"], "count")
        self.assertIn('id="count" aria-live="polite" role="status" tabindex="-1"', read("demo", "index.html"))

    def test_refine_summary_keeps_a_gap_before_the_number_of_choices_on(self):
        self.assertRegex(read("demo", "page.css"), r"\.refine>summary\{[^}]*gap:")


CHROME = next((p for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                           shutil.which("google-chrome") or "", shutil.which("chromium") or "")
               if p and os.path.exists(p)), None)


class PageFixesR2Test(unittest.TestCase):
    """Audit defects: one neutral price line on every card, a phone Size list
    that fits, an empty box whenever nothing fits, coffee-only coffee lines,
    a favicon, and exact-price search."""

    @classmethod
    def setUpClass(cls):
        cls.path = os.path.join(ROOT, "demo", "index.html")
        cls.page = read("demo", "index.html")
        cls.d = drive(cls.path)
        cls.cards = page_cards(cls.page)

    # 1. no endorsement badge, the same neutral wording on every card
    def test_every_card_carries_the_same_neutral_price_wording_and_no_badge(self):
        self.assertEqual(len(self.cards), 390)
        for c in self.cards:
            self.assertIn("Price read from the store page", c)
            self.assertIn("Not compared with other stores.", c)
        for word in ("Good to buy", "Worth a wait", "Check first", "Skipped", "✓"):
            self.assertNotIn(word, self.page)

    # 2. phone Size list
    def test_phone_size_list_fills_the_bar_width_not_a_fixed_offset_box(self):
        css = read("demo", "page.css")
        phone = css[css.index("@media (max-width:640px)"):]
        self.assertRegex(phone, r"\.pop\{position:static\}")
        self.assertRegex(phone, r"\.popbody\{[^}]*left:0;right:0;width:auto")

    @unittest.skipUnless(CHROME, "no Chrome to lay the page out")
    def test_size_list_open_at_390_px_does_not_scroll_the_page_sideways(self):
        wrapper = (
            "<!doctype html><body style='margin:0'><iframe id=f width=390 height=800 "
            "style='border:0' src='file://%s#q=hoodie'></iframe><pre id=out></pre><script>"
            "f.onload=function(){setTimeout(function(){var d=f.contentDocument;"
            "d.querySelector('#refine>summary').click();"
            "d.querySelector('[data-chip=size]').click();"
            "var r=d.querySelector('.popbody').getBoundingClientRect();"
            "out.textContent=JSON.stringify({iw:f.contentWindow.innerWidth,"
            "sw:d.documentElement.scrollWidth,l:r.left,r:r.right});},300)}</script>" % self.path)
        with tempfile.TemporaryDirectory() as tmp:
            w = os.path.join(tmp, "w.html")
            with open(w, "w", encoding="utf-8") as f:
                f.write(wrapper)
            dump = os.path.join(tmp, "dom.html")
            with open(dump, "w", encoding="utf-8") as sink:
                proc = subprocess.Popen(
                    [CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                     "--user-data-dir=" + os.path.join(tmp, "profile"), "--virtual-time-budget=3000",
                     "--dump-dom", "file://" + w], stdout=sink, stderr=subprocess.DEVNULL)
            try:   # Chrome can linger after printing the page: wait for the dump, not the exit
                for _ in range(120):
                    with open(dump, encoding="utf-8") as f:
                        out = f.read()
                    if "</html>" in out or proc.poll() is not None:
                        break
                    time.sleep(0.5)
            finally:
                proc.kill()
                proc.wait()
            with open(dump, encoding="utf-8") as f:
                out = f.read()
        m = re.search(r'<pre id="out">(\{.*?\})</pre>', out)
        self.assertIsNotNone(m, out[-500:])
        got = json.loads(html_lib.unescape(m.group(1)))
        self.assertEqual(got["iw"], 390)
        self.assertEqual(got["sw"], 390, got)
        self.assertGreaterEqual(got["l"], 0, got)
        self.assertLessEqual(got["r"], 390, got)

    # 3. a choice that fits nothing still gets the empty box with its Drop buttons
    def test_deep_link_to_a_choice_that_fits_nothing_shows_the_box_and_drop_buttons(self):
        d = self.d["deepNoFit"]
        self.assertEqual(d["main"], [])
        self.assertIn("“hoodie” matches 3 checked products, but none also fit your choices", d["empty"]["text"])
        self.assertIn("Drop Size: ZZ 3 would show", d["empty"]["buttons"])
        self.assertNotIn("No checked product matches", d["count"])
        self.assertIn("None of the checked products state a match for these choices", d["count"])
        # the pages that don't say stay listed, apart and labelled, below the box
        self.assertEqual(len(d["unkCards"]), 2)
        # the sentence above them must be literally true: they are not "shown as fitting"
        self.assertNotIn("Nothing is shown that doesn’t fit", d["empty"]["text"])
        self.assertIn("The pages that don’t say are listed below", d["empty"]["text"])
        self.assertIn("can’t be ruled in or out", d["empty"]["text"])
        self.assertIn("These pages don’t say, so they can’t be ruled in or out", self.page)
        self.assertIn("Not matches", d["unk"])
        self.assertIn("listed below", d["unk"])
        self.assertNotIn("Hide them", d["unk"])

    def test_a_choice_alone_that_fits_nothing_does_not_claim_nothing_is_shown(self):
        n = self.d["deepNoFitNoQuery"]
        self.assertEqual(n["main"], [])
        self.assertEqual(n["count"], "None of the checked products state a match for these choices")
        self.assertIn("None of the checked products state a match for these choices", n["empty"]["text"])
        self.assertNotIn("Nothing is shown that doesn’t fit", n["empty"]["text"])
        self.assertIn("The pages that don’t say are listed below", n["empty"]["text"])
        self.assertTrue(n["unkCards"])
        self.assertIn("Not matches", n["unk"])

    def test_dropping_the_choice_lists_the_matches(self):
        d = self.d["deepNoFitDrop"]
        self.assertEqual(len(d["main"]), 3)
        self.assertIsNone(d["empty"])

    def test_a_query_that_fits_nothing_with_nothing_unknown_still_has_its_box(self):
        d = self.d["deepNoFitUnk"]
        self.assertIsNotNone(d["empty"])
        self.assertTrue([b for b in d["empty"]["buttons"] if b.startswith("Drop Kind: Tea")])

    # 4. console noise
    def test_page_has_an_inline_favicon_so_no_404(self):
        self.assertRegex(self.page, r'<link rel="icon" href="data:image/svg\+xml,')

    def test_no_card_text_shows_a_literal_amp_entity(self):
        # the Read ... from URL: escaped once in the markup, so a reader sees "&"
        self.assertIn("Phone=Pixel+8&amp;Case+Style=SlimLink+Case", self.page)
        self.assertNotIn("&amp;amp;", self.page)
        s = drive(self.path, hash="#q=slimlink")
        self.assertNotIn("&amp;", s["load"]["pageText"])
        self.assertIn("Phone=Pixel+8&Case+Style=SlimLink+Case", s["load"]["pageText"] + " ".join(
            c for c in re.findall(r"Read [^<]*", html_lib.unescape(self.page))))

    # 5. the specialty band is a coffee line
    def test_specialty_band_shows_only_on_coffee_cards(self):
        with_band = [c for c in self.cards if "Specialty band" in c]
        self.assertEqual(len(with_band), 6)
        for c in with_band:
            self.assertIn('data-kind="Coffee"', c)
            self.assertIn('data-coffee-note="yes"', c)
        self.assertNotIn("not checked for other products yet", self.page)

    # 6. exact price
    def test_a_typed_price_finds_products_priced_exactly_that(self):
        for q in ("$25", "$25.00", "25 dollars"):
            d = self.d["price"][q]
            self.assertTrue(d["main"], q)
            self.assertEqual(d["count"].split(" ")[0], "14", q)
            for c in d["main"]:
                self.assertIn(c["priceLabel"], ("$25", "$25.00"), c)
        self.assertNotIn("PowerBug", " ".join(names(self.d["price"]["$25"]["main"])))

    def test_a_price_with_nothing_at_that_price_says_what_search_matches(self):
        for q in ("under $20", "$0.07"):
            e = self.d["price"][q]["empty"]
            self.assertIn("Search matches words and an exact shelf price", e["text"])
            self.assertIn("sort by price", e["text"])
            self.assertTrue([b for b in e["buttons"] if b.startswith("Browse all 390, lowest price first")])
        self.assertEqual(self.d["priceSort"]["hash"], "#sort=lo&all=1")
        self.assertEqual(self.d["priceSort"]["count"], "390 checked products")
        # an ordinary word query gets no price note
        self.assertNotIn("exact shelf price", self.d["typed"]["zzyzx"]["empty"]["text"])
