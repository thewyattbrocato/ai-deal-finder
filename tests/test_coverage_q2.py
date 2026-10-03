"""Coverage slice q2: nineteen more merchants for the searches the page had no answer
for (espresso and coffee makers, dog and cat food, perfume, sunglasses, candles,
plants, watches, books, stationery, travel, yoga mats, bottles), every product traced
to stored evidence.

Offline: reads demo/evidence/*.json and the generated page only. A merchant here
means its product pages were read (read-only GET, the browser promo-text pass and
the browser shipping/subscribe/size pass) and stored.
"""

import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "demo"))

import catalog  # noqa: E402
import terms  # noqa: E402
import build  # noqa: E402

NEW_MERCHANTS = {
    "miir": "miir.com", "manduka": "manduka.com", "moccamaster": "moccamaster.com",
    "aeropress": "aeropress.com", "flair": "flairespresso.com",
    "wacaco": "wacaco.com", "ember": "ember.com",
    "primalpetfoods": "primalpetfoods.com", "boysmells": "boysmells.com",
    "pfcandleco": "pfcandleco.com", "knockaround": "knockaround.com",
    "goodr": "goodr.com", "costafarms": "costafarms.com",
    "eaglecreek": "eaglecreek.com", "timex": "timex.com",
    "pioneerworks": "pioneerworks.org", "papersource": "papersource.com",
    "archerandolive": "archerandolive.com", "summerfridays": "summerfridays.com",
}
NEW_KINDS = {"Books"}
OBS, _EX = catalog.load_catalog()
OLD_KINDS = {o["kind"] for o in OBS if o["id"].split("-")[0] not in NEW_MERCHANTS}
PAGE = os.path.join(ROOT, "demo", "index.html")
DRIVER = os.path.join(ROOT, "tests", "coverage_names_driver.js")


def mine(prefix):
    return [o for o in OBS if o["id"].startswith(prefix + "-")]


def every():
    return [o for m in NEW_MERCHANTS for o in mine(m)]


def evidence(obs_id):
    with open(os.path.join(catalog.EVIDENCE_DIR, obs_id + ".json")) as f:
        return json.load(f)


def run_driver(names, kinds):
    proc = subprocess.run(["node", DRIVER, PAGE, json.dumps({"names": names, "kinds": kinds})],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


class NewMerchantsTest(unittest.TestCase):
    def test_nineteen_new_merchants_and_fifty_four_products(self):
        for m in NEW_MERCHANTS:
            self.assertGreaterEqual(len(mine(m)), 2, m)
        self.assertGreaterEqual(len(every()), 54)

    def test_each_product_has_stored_evidence_on_its_own_host(self):
        for m, host in NEW_MERCHANTS.items():
            for o in mine(m):
                ev = evidence(o["id"])
                self.assertEqual(ev["http_status"], 200, o["id"])
                self.assertTrue(ev["page_sha256"], o["id"])
                self.assertTrue(ev.get("rendered_checked"), o["id"])
                self.assertTrue(o["page_host"].endswith(host), o["id"])

    def test_price_is_traced_to_stored_page_data(self):
        for o in every():
            offers = catalog.offers_of(evidence(o["id"]))
            prices = {round(float(x.get("price") or x["priceSpecification"]["price"]), 2)
                      for x in offers}
            self.assertEqual(prices, {o["price"]}, o["id"])
            self.assertGreater(o["price"], 0)
            self.assertEqual({x.get("priceCurrency") for x in offers}, {"USD"}, o["id"])
            self.assertTrue(any(str(x.get("availability", "")).endswith("InStock") for x in offers),
                            o["id"])

    def test_kinds_are_old_or_the_one_new_kind_and_cover_the_empty_searches(self):
        for o in every():
            self.assertIn(o["kind"], OLD_KINDS | NEW_KINDS, o["id"])
        got = {o["kind"] for o in every()}
        self.assertTrue(NEW_KINDS <= got, NEW_KINDS - got)
        self.assertTrue({"Kitchen", "Pets", "Outdoors", "Personal care", "Office", "Home",
                         "Accessories"} <= got)

    def test_books_is_the_one_kind_added_and_each_book_page_prints_an_isbn_or_calls_itself_a_volume(self):
        # sunglasses, watches and travel gear are Accessories, candles and plants Home:
        # the existing 16 kinds fit them. Only the books had no kind.
        for o in mine("pioneerworks"):
            p = evidence(o["id"])["json_ld"][0]
            isbn = str(p.get("gtin13") or p.get("isbn") or "")
            self.assertTrue(isbn.startswith(("978", "979")) or "volume" in o["desc"].lower(), o["id"])

    def test_each_new_kind_has_its_search_words_and_the_seed_that_decided_it(self):
        with open(os.path.join(ROOT, "demo", "seeds.json")) as f:
            seeds = {s["id"]: s["kind"] for s in json.load(f)}
        for k in NEW_KINDS:
            self.assertIn(k.lower(), build.KIND_WORDS[k], k)
        for o in every():
            self.assertEqual(seeds[o["id"]], o["kind"], o["id"])

    def test_a_coupon_appears_only_as_page_text_and_none_was_printed_for_these(self):
        for o in every():
            snippets = evidence(o["id"])["coupon_snippets"]
            if o["coupon"] is None:
                for s in snippets:
                    c = catalog.CODE_RE.search(s)
                    self.assertTrue(not c or catalog.GATED_RE.search(s), o["id"])
            else:
                self.assertTrue(any(o["coupon"]["text"] in s for s in snippets), o["id"])
            self.assertIsNone(o["coupon"], o["id"])

    def test_a_code_printed_only_for_a_first_subscription_order_is_not_shown(self):
        # primalpetfoods.com prints "discount code: HELLO20" for "your first subscription
        # order": a subscription step, so not a code the shelf price can use or show.
        for o in mine("primalpetfoods"):
            snippets = evidence(o["id"])["coupon_snippets"]
            self.assertTrue(any("HELLO20" in s and "first subscription order" in s
                                for s in snippets), o["id"])
            self.assertIsNone(o["coupon"], o["id"])

    def test_skipped_merchants_were_not_stored(self):
        # chroniclebooks.com product pages carry no readable product data, so nothing
        # of theirs is stored; hydroflask.com, snowpeak.com, fieldnotesbrand.com and
        # jetpens.com refused the read.
        have = {f.split("-")[0] for f in os.listdir(catalog.EVIDENCE_DIR)}
        for m in ("chroniclebooks", "hydroflask", "snowpeak", "fieldnotesbrand", "jetpens",
                  "instantpot", "riflepaperco", "kosas"):
            self.assertNotIn(m, have)


class SearchWordsComeFromThePageTest(unittest.TestCase):
    def test_every_extra_search_word_is_printed_on_that_products_own_stored_page(self):
        ids = {o["id"] for o in every()}
        added = {i: w for i, w in terms.SEARCH_WORDS.items() if i in ids}
        self.assertTrue(added)
        for ev_id, words in added.items():
            ev = evidence(ev_id)
            said = " ".join([ev.get("title", ""), ev["json_ld"][0].get("name", ""),
                             str(ev["json_ld"][0].get("description", "")),
                             ev["final_url"]]).lower()
            for w in words:
                self.assertIn(w, said, (ev_id, w))


class StoreNamesTest(unittest.TestCase):
    def test_each_new_stores_label_is_the_name_its_own_stored_page_prints(self):
        # eaglecreek.com's JSON-LD brand says "Backpacks", papersource.com's names the
        # maker, goodr.com's says "goodr sunglasses": the label is the store.
        labels = build.merchants()
        for o in every():
            label = labels[o["page_host"]]
            title = evidence(o["id"])["title"].lower()
            self.assertTrue(label.lower() in title or label.lower().replace(" ", "") in title
                            or label.lower().replace(" ", "") in o["page_host"], (o["id"], label))

    def test_the_page_shows_that_store_and_a_store_search_finds_it(self):
        got = run_driver(["Eagle Creek", "Paper Source", "Primal Pet Foods", "Manduka"], [])["names"]
        self.assertIn("Global Travel Adapter Micro", got["Eagle Creek"])
        self.assertIn("Manuscript Fountain Pen Classic in Pillow Pack", got["Paper Source"])
        self.assertIn("Freeze-Dried Raw Nuggets Dog Food - Pork Recipe", got["Primal Pet Foods"])
        self.assertIn("Ratio Relaxation Mat", got["Manduka"])


class ConditionsFromPagesTest(unittest.TestCase):
    def test_every_product_had_its_conditions_page_read_on_its_own_host(self):
        for m, host in NEW_MERCHANTS.items():
            for o in mine(m):
                c = evidence(o["id"]).get("conditions")
                self.assertTrue(c, o["id"])
                self.assertTrue(c["read_at"].startswith("2026-"), o["id"])
                self.assertIn(host.split(".")[0], c["url"], o["id"])

    def test_a_shipping_or_subscribe_fact_exists_only_as_a_stored_page_line(self):
        for o in every():
            ev = evidence(o["id"])
            t = terms.from_evidence(ev, ev["kind"])
            if "ship" in t and not terms._shipping(ev["json_ld"]):
                quoted = t["ship"]["t"].strip("“”")
                self.assertTrue(any(quoted in l for l in ev["conditions"]["ship"]), o["id"])
            if "sub" in t:
                quoted = re.search("“(.*?)”", t["sub"]["t"]).group(1)
                self.assertTrue(any(quoted in l for l in ev["conditions"]["sub"]), o["id"])

    def test_a_page_with_no_stated_subscribe_line_stays_unknown(self):
        quiet = [o for o in every() if not evidence(o["id"])["conditions"]["sub"]]
        self.assertTrue(quiet)
        for o in quiet:
            ev = evidence(o["id"])
            self.assertNotIn("sub", terms.from_evidence(ev, ev["kind"]), o["id"])

    def test_sizes_are_only_shoe_or_clothing_so_none_are_invented_here(self):
        for o in every():
            ev = evidence(o["id"])
            self.assertEqual(terms.from_evidence(ev, ev["kind"])["sizes"], [], o["id"])


class SearchFirstPageFindsThemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = run_driver([o["name"] for o in every()],
                             sorted({o["kind"] for o in every()}))
        with open(PAGE, encoding="utf-8") as f:
            cat = re.search(r'<script type="application/json" id="catalog">([\s\S]*?)</script>',
                            f.read()).group(1)
        cls.cat = json.loads(cat)

    def test_each_new_product_is_listed_when_its_name_is_typed(self):
        for o in every():
            self.assertIn(o["name"], self.out["names"][o["name"]], o["id"])

    def test_each_new_product_is_in_the_page_catalog_with_its_own_kind_and_price(self):
        by_url = {c["u"]: c for c in self.cat}
        for o in every():
            c = by_url[o["page_url"]]
            self.assertEqual((c["k"], c["pc"]), (o["kind"], round(o["price"] * 100)), o["id"])

    def test_each_kind_search_lists_products_and_shows_new_ones(self):
        new_names = {o["name"] for o in every()}
        for kind, v in self.out["kinds"].items():
            self.assertTrue(v["typed"], kind)
            self.assertTrue(set(v["typed"]) & new_names, kind)
            self.assertTrue(set(v["opened"]) & new_names, kind)

    def test_a_store_plus_kind_search_lists_each_new_product(self):
        # Searching by what shoppers type (store and name) reaches every new product,
        # even where the kind alone lists more products than one screen shows.
        queries = [f"{build.merchants()[o['page_host']]} {o['name']}" for o in every()]
        got = run_driver(queries, [])["names"]
        for o, q in zip(every(), queries):
            self.assertIn(o["name"], got[q], o["id"])

    def test_the_searches_that_used_to_list_nothing_now_list_real_products(self):
        wanted = {
            "espresso machine": {"PICOPRESSO"},
            "espresso": {"Flair Classic", "MINIPRESSO GR2"},
            "coffee maker": {"AeroPress Coffee Maker - Premium Walnut"},
            "dog food": {"Freeze-Dried Raw Nuggets Dog Food - Pork Recipe"},
            "cat food": {"Freeze-Dried Raw Nuggets Cat Food - Rabbit Recipe"},
            "perfume": {"BIG APPLE", "LES"},
            "sunglasses": {"Bean There, Run That", "Dogfish Head Torrey Pines Sport"},
            "candle": {"HARD WOOD", "Celestial Smoky Cinnamon – Standard Candle"},
            "plants": {"Money Tree | large"},
            "plant": {"Brasil Philodendron | medium"},
            "watch": {"Timex Digital 33mm Resin Strap Watch"},
            "bottle": {"Shogo Ota Artist Series 20oz Wide Mouth Bottle"},
            "yoga mat": {"Ratio Relaxation Mat"},
            "books": {"Chelsea Girls by Eileen Myles"},
            "travel adapter": {"Global Travel Adapter Micro"},
            "fountain pen": {"Manuscript Fountain Pen Classic in Pillow Pack"},
        }
        got = run_driver(sorted(wanted), [])["names"]
        for q, names in wanted.items():
            self.assertTrue(names <= set(got[q]), (q, names - set(got[q])))

    def test_adding_these_products_left_every_other_product_findable_by_its_exact_name(self):
        # The page joins "12" + "oz" into a catalog word "12oz" when one exists, so a new
        # product named "12oz ..." made "Himalayan Green Tea, 12 oz" unfindable. Every
        # product on the page must still be listed when its own name is typed.
        names = [c["n"] for c in self.cat]
        got = run_driver(names, [])["names"]
        lost = [n for n in names if n not in got[n]]
        self.assertEqual(lost, [])

    def test_a_search_no_checked_page_answers_still_lists_nothing(self):
        # No laptop page read for this slice states one plain price (frame.work refused
        # the read, dell.com printed no product data), so "laptop" stays an honest zero.
        self.assertEqual(run_driver(["laptop"], [])["names"]["laptop"], [])


if __name__ == "__main__":
    unittest.main()
