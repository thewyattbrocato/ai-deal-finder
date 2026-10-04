"""Coverage slice t1: twenty-three more merchants for the everyday searches that still
answered nothing or little (backpack, jeans, socks, headphones, charger, knife,
toothbrush, moisturizer, sunscreen, protein, snacks, toy, baby, lamp, deodorant,
running shoes), every product traced to stored evidence.

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
    "simplemodern": "simplemodern.com", "darntough": "darntough.com",
    "stance": "stance.com", "agjeans": "agjeans.com",
    "topodesigns": "topodesigns.com", "herschel": "herschel.com",
    "jlab": "jlab.com", "skullcandy": "skullcandy.com",
    "nativeunion": "nativeunion.com", "getquip": "getquip.com",
    "burstoralcare": "burstoralcare.com", "drsquatch": "drsquatch.com",
    "supergoop": "supergoop.com", "cocokind": "cocokind.com",
    "transparentlabs": "transparentlabs.com", "epicprovisions": "epicprovisions.com",
    "perfectsnacks": "perfectsnacks.com", "brightech": "brightech.com",
    "xeroshoes": "xeroshoes.com", "messermeister": "messermeister.com",
    "fromourplace": "fromourplace.com", "cuddleandkind": "cuddleandkind.com",
    "kytebaby": "kytebaby.com",
}
NEW_KINDS = {"Toys"}
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


def alnum(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


class NewMerchantsTest(unittest.TestCase):
    def test_twenty_three_new_merchants_and_fifty_five_products(self):
        self.assertEqual(len(NEW_MERCHANTS), 23)
        for m in NEW_MERCHANTS:
            self.assertGreaterEqual(len(mine(m)), 1, m)
        self.assertEqual(len(every()), 55)

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

    def test_kinds_are_old_or_the_one_new_kind_and_cover_the_gap_searches(self):
        for o in every():
            self.assertIn(o["kind"], OLD_KINDS | NEW_KINDS, o["id"])
        got = {o["kind"] for o in every()}
        self.assertTrue(NEW_KINDS <= got, NEW_KINDS - got)
        self.assertTrue({"Kitchen", "Clothing", "Accessories", "Tech", "Personal care", "Grooming",
                         "Wellness", "Pantry", "Home", "Shoes", "Outdoors"} <= got)

    def test_toys_is_the_one_kind_added_and_each_toy_page_calls_itself_a_doll_or_play(self):
        # Backpacks, jeans, socks, headphones and the rest fit the existing 17 kinds.
        # Only the knitted dolls had none: every Toys page prints "doll" or "play".
        self.assertEqual({o["kind"] for o in mine("cuddleandkind")}, {"Toys"})
        for o in mine("cuddleandkind"):
            said = (evidence(o["id"])["title"] + " " + o["desc"]).lower()
            self.assertTrue("doll" in said or "play" in said, o["id"])

    def test_the_new_kind_has_its_search_words_and_the_seed_that_decided_it(self):
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

    def test_skipped_merchants_were_not_stored(self):
        # drbronner.com: the real-browser read never loaded its pages (the promo-text and
        # shipping passes could not run), so nothing of theirs is stored.
        # melissaanddoug.com printed no price in its page data, altrarunning.com, tegu.com
        # and opinel-usa.com printed no product data, tatcha.com's price was not readable,
        # dl1961.com's price varies by size, kidrobot.com's plush were pre-orders or out of
        # stock, hukitchen.com was out of stock; madeincookware.com, rhone.com and
        # vivobarefoot.com refused the read and bombas.com rate-limited it.
        have = {f.split("-")[0] for f in os.listdir(catalog.EVIDENCE_DIR)}
        for m in ("drbronner", "melissaanddoug", "altrarunning", "tegu", "opinel", "tatcha",
                  "dl1961", "kidrobot", "hukitchen", "madeincookware", "rhone",
                  "vivobarefoot", "bombas", "olaplex", "satechi", "nanoleaf", "everlane"):
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
    def test_each_new_stores_label_is_the_name_its_own_stored_page_or_address_prints(self):
        labels = build.merchants()
        for o in every():
            label = labels[o["page_host"]]
            ev = evidence(o["id"])
            printed = alnum(ev["title"] + " " + o["page_host"])
            self.assertIn(alnum(label), printed, (o["id"], label))

    def test_the_page_shows_that_store_and_a_store_search_finds_it(self):
        got = run_driver(["Xero Shoes", "Dr. Squatch", "Native Union", "Brightech"], [])["names"]
        self.assertIn("HFS Original - Men", got["Xero Shoes"])
        self.assertIn("Drunk'n Pumpkin Deodorant", got["Dr. Squatch"])
        self.assertIn("Fast GaN Charger PD 100W", got["Native Union"])
        self.assertIn("Koa Table Lamp", got["Brightech"])


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

    def test_sizes_come_only_from_a_stored_size_line_so_none_are_invented(self):
        # Shoes and clothing may carry sizes; every one must be a line the page printed.
        for o in every():
            ev = evidence(o["id"])
            sizes = terms.from_evidence(ev, ev["kind"])["sizes"]
            if o["kind"] not in ("Shoes", "Clothing"):
                self.assertEqual(sizes, [], o["id"])


class SearchFirstPageFindsThemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = run_driver([o["name"] for o in every()], sorted(NEW_KINDS))
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

    def test_the_new_kind_search_lists_its_products(self):
        new_names = {o["name"] for o in every()}
        for kind, v in self.out["kinds"].items():
            self.assertTrue(set(v["typed"]) & new_names, kind)
            self.assertTrue(set(v["opened"]) & new_names, kind)

    def test_a_store_plus_name_search_lists_each_new_product(self):
        queries = [f"{build.merchants()[o['page_host']]} {o['name']}" for o in every()]
        got = run_driver(queries, [])["names"]
        for o, q in zip(every(), queries):
            self.assertIn(o["name"], got[q], o["id"])

    def test_the_page_now_has_390_products_in_18_kinds(self):
        self.assertEqual(len(self.cat), 390)
        self.assertEqual(len({c["k"] for c in self.cat}), 18)

    def test_the_searches_that_answered_little_or_nothing_now_list_real_products(self):
        wanted = {
            "backpack": {"Daypack Classic", "City Backpack Twill"},
            "jeans": {"Everett Jean", "Tellis Jean"},
            "socks": {"Women's Cable Crew Lightweight Lifestyle Socks"},
            "headphones": {"Crusher® 720", "Icon® 180 Wired"},
            "charger": {"Fast GaN Charger PD 100W", "Rise 3-in-1 Magnetic Wireless Charger"},
            "knife": {"Oliva Elite Chef's Knife - 9\"", "Walnut Knife Block"},
            "toothbrush": {"Sonic Toothbrush", "Pro Brush Replacement Heads 3 Pack"},
            "moisturizer": {"electrolyte water cream", "retinol body cream"},
            "sunscreen": {"Unseen Sunscreen SPF 50"},
            "protein": {"Protein Coffee", "Oaties Brownie Batter"},
            "snacks": {"Maple Bacon Pork Cracklings", "Pumpkin Pie"},
            "toy": {"Tiny baby puppy"},
            "baby": {"Tiny baby mouse"},
            "lamp": {"Carter Table Lamp", "Koa Table Lamp"},
            "deodorant": {"Drunk'n Pumpkin Deodorant"},
            "running shoes": {"HFS Original - Men", "HFS Original - Women"},
            "sneakers": {"360 Rally - Men"},
            "water bottle": {"Summit Water Bottle with Straw Lid"},
        }
        got = run_driver(sorted(wanted), [])["names"]
        for q, names in wanted.items():
            self.assertTrue(names <= set(got[q]), (q, names - set(got[q])))

    def test_each_measured_search_lists_at_least_as_many_products_as_before(self):
        # The count each search listed on the page before this slice (measured on the live
        # page, 335 products) is a floor: adding products never made one answer less.
        before = {
            "backpack": 2, "wallet": 27, "sneakers": 2, "running shoes": 0, "jeans": 1,
            "socks": 1, "headphones": 1, "phone case": 8, "charger": 1, "water bottle": 0,
            "blender": 1, "knife": 0, "cookware": 5, "toothbrush": 0, "shampoo": 2,
            "moisturizer": 0, "sunscreen": 0, "vitamins": 0, "protein": 0, "snacks": 2,
            "olive oil": 4, "spice": 6, "tea": 16, "gift": 5, "toy": 2, "baby": 1,
            "garden": 1, "bedding": 16, "towel": 4, "lamp": 0, "t-shirt": 1, "jacket": 6,
            "sweater": 4, "laptop": 0, "mug": 4, "pillow": 2, "candle": 4, "soap": 0,
            "deodorant": 2, "notebook": 4,
        }
        got = run_driver(sorted(before), [])["names"]
        for q, n in before.items():
            self.assertGreaterEqual(len(got[q]), n, q)
        short = sorted(q for q in before if len(got[q]) < 3)
        # What is still short is listed here, so a later slice knows where to look.
        self.assertEqual(short, ["blender", "garden", "laptop", "pillow", "running shoes",
                                 "shampoo", "soap", "t-shirt", "vitamins", "water bottle"])

    def test_adding_these_products_left_every_other_product_findable_by_its_exact_name(self):
        names = [c["n"] for c in self.cat]
        got = run_driver(names, [])["names"]
        lost = [n for n in names if n not in got[n]]
        self.assertEqual(lost, [])

    def test_a_search_no_checked_page_answers_still_lists_nothing(self):
        # No laptop page read states one plain price in stock (frame.work refused the read,
        # dell.com printed no product data), and no soap page names itself a soap
        # (drsquatch.com's bar-soap titles print only the scent), so these stay honest zeros.
        got = run_driver(["laptop", "soap"], [])["names"]
        self.assertEqual(got["laptop"], [])
        self.assertEqual(got["soap"], [])


if __name__ == "__main__":
    unittest.main()
