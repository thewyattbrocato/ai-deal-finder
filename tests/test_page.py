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
import subprocess
import unittest

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
        self.assertEqual(load["focus"], {"id": "q", "chip": None, "isQ": True})
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
        self.assertIn("Kitchen30 products", start)
        self.assertIn("Browse all 244 checked products", start)
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
        self.assertEqual(t["cof"]["count"], "20 checked products for “cof”")
        self.assertEqual(t["coffee"]["count"], "20 checked products for “coffee”")
        self.assertEqual(t["old nav"]["count"], "1 checked product for “old nav”")

    def test_whole_words_only_bean_does_not_find_beanie(self):
        q = self.eng["queries"]
        self.assertEqual(len(q["bean"]["rows"]), 9)
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
        self.assertEqual(len(t["espreso"]["main"]), 3)
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
        self.assertEqual(len(rows), 3)
        self.assertEqual(names(self.d["typed"]["espresso"]["main"]), rows)
        self.assertIn("The Breville Bambino™", names(self.d["typed"]["bambino"]["main"]))

    def test_ranking_is_relevance_not_cheapest_first(self):
        main = self.d["typed"]["coffee"]["main"]
        self.assertEqual(main[0]["name"], "Coffee Tin + PSL")      # the word is in its name
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
        self.assertEqual(s[0], ["kind", "Coffee", "kind · 9 products"])
        self.assertTrue([x for x in s if x[0] == "store"])
        products = [x for x in s if x[0] == "product"]
        self.assertTrue(products)
        for _t, label, sub in products:
            self.assertRegex(sub, r"^\$\d+(\.\d\d)? · ")
        self.assertIn(["product", "The Breville Bambino™", "$299.95 · Breville"],
                      self.eng["suggest"]["bambino"])

    # ---- 3. a result: compact card, one tap to the store, details on the card --

    def test_every_shown_card_names_the_store_shelf_price_age_and_unknowns(self):
        seen = 0
        for q in ("coffee", "shoes", "clothing", "old navy", "airpods", "dog"):
            for c in self.d["typed"][q]["main"]:
                seen += 1
                self.assertEqual(c["price"], c["priceLabel"], c["name"])
                self.assertRegex(c["age"], r"^Checked (today|\d+ days?) ?(ago)?,? ?\d{4}-\d\d-\d\d$")
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
        self.assertEqual(len(cards), 244)
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
        for q in ("zzyzx", "espresso machine"):
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
        self.assertIn("11 more products don’t state a subscribe option on the page, so they aren’t counted above.", s["unk"])
        self.assertEqual(len(s["main"]), 9)
        self.assertEqual(s["unkCards"], [])
        shown = self.d["coffeeSubShown"]
        self.assertTrue(shown["unkOpen"])
        self.assertEqual(len(shown["unkCards"]), 11)
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
        self.assertIn("14 more products don’t state size on the page", two["unk"])
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
        self.assertEqual(self.d["browseAll"]["count"], "244 checked products")
        self.assertEqual(len(self.d["browseAll"]["main"]), 24)
        self.assertEqual(self.d["browseAll"]["showMore"], "Show 24 more (220 left)")
        self.assertEqual(self.d["afterKind"]["count"], "9 checked products for “coffee”")
        self.assertEqual(self.d["removeKind"]["count"], "20 checked products for “coffee”")

    # ---- 5. empty state, URL state ---------------------------------------------

    def test_empty_state_says_what_was_searched_and_offers_real_closest_products(self):
        e = self.d["typed"]["espresso machine"]["empty"]
        self.assertIn("No checked product matches “espresso machine”", e["text"])
        self.assertIn("for all of: “espresso”, “machine”", e["text"])
        self.assertIn("Nothing is shown that doesn’t match, and nothing is guessed.", e["text"])
        near = e["near"]
        self.assertEqual(len(near), 3)
        self.assertIn("The Breville Bambino™", [n["name"] for n in near])
        for n in near:
            self.assertIn("Matches “espresso” · doesn’t match “machine”", n["text"])
            self.assertTrue(n["href"].startswith("https://"))
        for b in ("Kitchen 30", "Browse all 244", "Clear search"):
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
        self.assertIn("No checked product fits these choices", n["empty"]["text"])
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
        self.assertEqual(h["back2"]["count"], "20 checked products for “coffee”")
        self.assertEqual(h["back2"]["q"], "coffee")
        self.assertTrue(h["back3"]["startShown"])
        self.assertEqual(h["back3"]["q"], "")
        refreshed = self.d["loadWithHash"]
        self.assertEqual(refreshed["q"], "cofee")
        self.assertEqual([a["key"] for a in refreshed["active"]], ["ship"])
        self.assertEqual(refreshed["count"].split(" ")[0], str(len(refreshed["main"])) if len(refreshed["main"]) < 24 else "24")
        r = self.d["hashRestore"]
        self.assertEqual(r["#kind=Shoes"]["count"], "14 checked products")
        self.assertEqual(r["#all=1"]["count"], "244 checked products")
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

    def test_the_page_reads_the_date_once_for_the_age_line_only(self):
        script = self.page[self.page.index("<script>"):]
        self.assertEqual(script.count("new Date()"), 1)

    def test_each_card_says_how_old_its_stored_check_is_in_plain_days(self):
        # the page script runs with "today" pinned to 2026-10-05
        for c in page_cards(self.page):
            iso = re.search(r'data-observed="([^"]*)"', c).group(1)
            self.assertIn("Checked " + iso[:10] + "</p>", c)  # no-script fallback: date only
            self.assertEqual(iso, re.search(r"Checked: [^<]*· (\d{4}[^<]*)</p>", c).group(1))
        seen = set()
        for c in self.d["load"]["all"]:
            seen.add(c["age"])
            self.assertRegex(c["age"], r"^Checked (today|\d+ days?) ?(ago)?,? ?\d{4}-\d\d-\d\d$")
            for word in ("fresh", "stale", "old", "expired", "recent", "outdated", "valid"):
                self.assertNotIn(word, c["age"].lower())
        self.assertIn("Checked 3 days ago, 2026-10-02", seen)
        self.assertIn("Checked 2 days ago, 2026-10-03", seen)

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
                self.assertIn("shipping cost (the page did not state it)", line)
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

    def test_lavazza_records_carry_the_2026_10_03_observation(self):
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
            self.assertEqual((latest["code"], latest["observed_at"][:10]), ("AS20", "2026-10-03"), fn)
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


if __name__ == "__main__":
    unittest.main()
