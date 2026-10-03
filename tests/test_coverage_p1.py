"""Coverage slice p1: nine more merchants for the thinnest kinds (Wellness, Tea,
Drinks, Grooming, Office), every product traced to stored evidence.

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
import build as _unused  # noqa: E402,F401

NEW_MERCHANTS = {
    "olly": "olly.com", "moonjuice": "moonjuice.com", "ritual": "ritual.com",
    "harrys": "harrys.com", "leuchtturm": "leuchtturm1917.us",
    "rishi": "rishi-tea.com", "ghia": "drinkghia.com",
    "spindrift": "drinkspindrift.com", "vahdam": "vahdam.com",
}
OBS, _EX = catalog.load_catalog()
KINDS = {o["kind"] for o in OBS if o["id"].split("-")[0] not in NEW_MERCHANTS}
PAGE = os.path.join(ROOT, "demo", "index.html")
DRIVER = os.path.join(ROOT, "tests", "coverage_names_driver.js")


def mine(prefix):
    return [o for o in OBS if o["id"].startswith(prefix + "-")]


def every():
    return [o for m in NEW_MERCHANTS for o in mine(m)]


def evidence(obs_id):
    with open(os.path.join(catalog.EVIDENCE_DIR, obs_id + ".json")) as f:
        return json.load(f)


class NewMerchantsTest(unittest.TestCase):
    def test_nine_new_merchants_and_thirty_seven_products(self):
        for m in NEW_MERCHANTS:
            self.assertGreaterEqual(len(mine(m)), 4, m)
        self.assertGreaterEqual(len(every()), 37)

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

    def test_kinds_come_from_existing_vocabulary_and_cover_the_thin_ones(self):
        for o in every():
            self.assertIn(o["kind"], KINDS, o["id"])
        got = {o["kind"] for o in every()}
        self.assertEqual(got, {"Wellness", "Tea", "Drinks", "Grooming", "Office"})

    def test_no_coupon_without_page_text(self):
        for o in every():
            snippets = evidence(o["id"])["coupon_snippets"]
            if o["coupon"] is None:
                for s in snippets:
                    c = catalog.CODE_RE.search(s)
                    self.assertTrue(not c or catalog.GATED_RE.search(s), o["id"])
            else:
                self.assertTrue(any(o["coupon"]["text"] in s for s in snippets), o["id"])

    def test_no_product_page_here_printed_a_public_code_so_none_is_shown(self):
        for o in every():
            self.assertIsNone(o["coupon"], o["id"])
            self.assertEqual(evidence(o["id"])["coupon_snippets"], [], o["id"])

    def test_blocked_or_unusable_merchants_left_out(self):
        # artoftea.com bundle pages carry no readable single price, harrys.com
        # "harrys-plus-blade-refills-tts" is a 404, mightyleaf.com lists $0.00 items.
        shown = {o["id"].split("-")[0] for o in OBS}
        self.assertNotIn("artoftea", shown)
        self.assertFalse(os.path.exists(os.path.join(
            catalog.EVIDENCE_DIR, "harrys-harrys-plus-blade-refills-tts.json")))


class ConditionsFromPagesTest(unittest.TestCase):
    def test_every_product_had_its_conditions_page_read_on_its_own_host(self):
        for m, host in NEW_MERCHANTS.items():
            for o in mine(m):
                c = evidence(o["id"]).get("conditions")
                self.assertTrue(c, o["id"])
                self.assertTrue(c["read_at"].startswith("2026-"), o["id"])
                self.assertIn(host.split(".")[0].replace("drink", ""), c["url"], o["id"])

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
        for o in mine("leuchtturm"):
            ev = evidence(o["id"])
            self.assertEqual(ev["conditions"]["sub"], [], o["id"])
            self.assertNotIn("sub", terms.from_evidence(ev, ev["kind"]), o["id"])

    def test_sizes_are_only_shoe_or_clothing_so_none_are_invented_here(self):
        for o in every():
            ev = evidence(o["id"])
            self.assertEqual(terms.from_evidence(ev, ev["kind"])["sizes"], [], o["id"])


class SearchFirstPageFindsThemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        arg = json.dumps({"names": [o["name"] for o in every()],
                          "kinds": sorted({o["kind"] for o in every()})})
        proc = subprocess.run(["node", DRIVER, PAGE, arg], capture_output=True,
                              text=True, check=False)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr or proc.stdout)
        cls.out = json.loads(proc.stdout)
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

    def test_a_store_plus_kind_search_lists_each_new_product(self):
        # Searching by what shoppers type (store and kind) reaches every new product,
        # even where the kind alone lists more products than one screen shows.
        queries = {o["name"]: o["brand"] or "" for o in every()}
        arg = json.dumps({"names": [f"{queries[o['name']]} {o['name']}".strip() for o in every()],
                          "kinds": []})
        proc = subprocess.run(["node", DRIVER, PAGE, arg], capture_output=True, text=True, check=True)
        got = json.loads(proc.stdout)["names"]
        for o in every():
            key = f"{queries[o['name']]} {o['name']}".strip()
            self.assertIn(o["name"], got[key], o["id"])


if __name__ == "__main__":
    unittest.main()
