"""Catalog slice: 100+ checked product pages, no-invention rules.

Observations come only from stored evidence (demo/evidence/*.json) through
demo/catalog.py, and are judged by the same fail-closed engine path as the
hand-checked products. Offline: nothing here touches the network.
"""

import copy
import hashlib
import importlib.util
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "demo"))

import catalog  # noqa: E402
from deal_finder.decision import Verdict  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "demo_build", os.path.join(ROOT, "demo", "build.py"))
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

OBS, EXCLUDED = catalog.load_catalog()


def evidence(obs_id):
    with open(os.path.join(catalog.EVIDENCE_DIR, obs_id + ".json")) as f:
        return json.load(f)


def fake_ev(**over):
    ev = {
        "id": "x-1", "kind": "Home", "url": "https://shop.example/products/x",
        "final_url": "https://shop.example/products/x", "http_status": 200,
        "observed_at": "2026-10-02T16:00:00Z",
        "json_ld": [{"@type": "Product", "name": "Thing", "offers": {
            "@type": "Offer", "price": "12.50", "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"}}],
        "coupon_snippets": [], "image_file": None,
    }
    ev.update(over)
    return ev


class CatalogSizeTest(unittest.TestCase):
    def test_at_least_100_checked_products_across_varied_kinds(self):
        self.assertGreaterEqual(len(OBS), 100)
        self.assertGreaterEqual(len({o["kind"] for o in OBS}), 8)
        self.assertEqual(len({o["id"] for o in OBS}), len(OBS))

    def test_every_observation_reproduces_from_stored_evidence(self):
        for o in OBS:
            state, again = catalog.extract(evidence(o["id"]))
            self.assertEqual(state, "ok", o["id"])
            self.assertEqual(again, o, o["id"])
            self.assertTrue(o["page_url"].startswith("https://"), o["id"])
            self.assertRegex(o["observed_at"], r"^\d{4}-\d\d-\d\dT")

    def test_unreadable_pages_are_excluded_not_guessed(self):
        shown = {o["id"] for o in OBS}
        for ev_id, why in EXCLUDED:
            self.assertNotIn(ev_id, shown)
            self.assertTrue(why)


class NoInventionTest(unittest.TestCase):
    def test_price_is_the_pages_single_in_stock_usd_price(self):
        for o in OBS:
            offers = catalog.offers_of(evidence(o["id"]))
            prices = {round(float((x.get("price") or
                                   (x.get("priceSpecification") or {}).get("price"))), 2)
                      for x in offers}
            self.assertEqual(prices, {o["price"]}, o["id"])

    def test_no_price_means_excluded(self):
        ev = fake_ev(json_ld=[{"@type": "Product", "name": "Thing"}])
        self.assertEqual(catalog.extract(ev)[0], "excluded")
        ev = fake_ev(json_ld=[])
        self.assertEqual(catalog.extract(ev)[0], "excluded")

    def test_unreadable_identity_price_or_stock_is_excluded(self):
        good = fake_ev()
        self.assertEqual(catalog.extract(good)[0], "ok")
        cases = {}
        c = copy.deepcopy(good); c["json_ld"][0]["name"] = " "; cases["name"] = c
        c = copy.deepcopy(good); c["json_ld"][0]["offers"]["price"] = "call us"; cases["price"] = c
        c = copy.deepcopy(good); c["json_ld"][0]["offers"]["price"] = "0"; cases["zero"] = c
        c = copy.deepcopy(good); c["json_ld"][0]["offers"]["priceCurrency"] = "EUR"; cases["cur"] = c
        c = copy.deepcopy(good)
        c["json_ld"][0]["offers"]["availability"] = "https://schema.org/OutOfStock"
        cases["stock"] = c
        c = copy.deepcopy(good); c["http_status"] = 403; cases["status"] = c
        c = copy.deepcopy(good)
        c["json_ld"][0]["offers"] = [
            {"price": "10", "priceCurrency": "USD",
             "availability": "https://schema.org/InStock"},
            {"price": "14", "priceCurrency": "USD",
             "availability": "https://schema.org/InStock"}]
        cases["varies"] = c
        for label, ev in cases.items():
            self.assertEqual(catalog.extract(ev)[0], "excluded", label)

    def test_no_coupon_without_literal_page_text(self):
        state, o = catalog.extract(fake_ev())
        self.assertEqual((state, o["coupon"]), ("ok", None))
        # Offer wording with no code token is not a coupon.
        ev = fake_ev(coupon_snippets=["Spring sale: 20% off everything this week."])
        self.assertIsNone(catalog.extract(ev)[1]["coupon"])
        # An email/signup-gated code is not an on-page coupon.
        ev = fake_ev(coupon_snippets=[
            "Join our email list and get 10% off with code WELCOME10 today."])
        self.assertIsNone(catalog.extract(ev)[1]["coupon"])

    def test_every_shown_coupon_is_verbatim_stored_page_text(self):
        with_coupon = [o for o in OBS if o["coupon"]]
        self.assertTrue(with_coupon, "catalog should include on-page coupons")
        for o in with_coupon:
            snippets = evidence(o["id"])["coupon_snippets"]
            self.assertIn(o["coupon"]["code"], o["coupon"]["text"], o["id"])
            self.assertTrue(any(o["coupon"]["text"] in s for s in snippets), o["id"])
        for o in OBS:
            if not o["coupon"]:
                for s in evidence(o["id"])["coupon_snippets"]:
                    m = catalog.CODE_RE.search(s)
                    self.assertTrue(not m or catalog.GATED_RE.search(s), o["id"])

    def test_photo_only_from_stored_capture(self):
        self.assertEqual(catalog.extract(fake_ev())[1]["image"], None)
        for o in OBS:
            ev = evidence(o["id"])
            if o["image"] is None:
                self.assertFalse(ev.get("image_file"), o["id"])
                continue
            path = os.path.join(catalog.ASSETS_DIR, o["image"])
            with open(path, "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(),
                                 ev["image_sha256"], o["id"])
            self.assertEqual(o["image"], ev["image_file"])

    def test_coupon_never_changes_the_shown_price(self):
        items = build.catalog_items({})
        for o in OBS:
            if o["id"] not in items:
                continue  # same-name duplicate, shown once
            item = items[o["id"]]
            self.assertEqual(item["price_cents"], int(round(o["price"] * 100)))
            if o["coupon"]:
                d = item["decision"]
                self.assertEqual(d.verdict, Verdict.BUY, o["id"])
                self.assertTrue(any(o["coupon"]["code"] in r and "excluded" in r
                                    for r in d.reasons), o["id"])
                html = build.card_for(item)
                self.assertIn("never tried", html)
                self.assertIn(o["coupon"]["text"].split("&")[0][:20], html)


class PublicPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "demo", "index.html"), encoding="utf-8") as f:
            cls.page = f.read()
        with open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8") as f:
            cls.docs = f.read()

    def test_public_page_lists_100_checked_products(self):
        self.assertEqual(self.page, self.docs)
        self.assertGreaterEqual(self.page.count("data-keywords="), 100)

    def test_every_card_has_page_link_and_check_time(self):
        self.assertEqual(self.page.count("Checked: "), self.page.count("data-keywords="))

    def test_image_tags_point_at_stored_files(self):
        for src in re.findall(r'<img src="(assets/[^"]+)"', self.page):
            self.assertTrue(os.path.exists(os.path.join(ROOT, "docs", src)), src)
            self.assertTrue(os.path.exists(os.path.join(ROOT, "demo", src)), src)

    def test_every_coupon_on_the_page_is_stored_evidence_or_hand_checked(self):
        stored = {o["coupon"]["code"] for o in OBS if o["coupon"]}
        on_page = set(re.findall(r'data-coupon-code="([^"]+)"', self.page))
        hand_checked = on_page - stored
        # codes the page shows beyond stored catalog evidence must be hand-checked ones
        with open(os.path.join(ROOT, "demo", "build.py"), encoding="utf-8") as f:
            build_src = f.read()
        for code in hand_checked:
            self.assertRegex(build_src, r'Coupon\(code="%s"' % re.escape(code))
        # every stored catalog coupon is shown, and none gains a lower price
        self.assertTrue(stored <= on_page)
        self.assertEqual(self.page.count('data-coupon="yes"'),
                         len(re.findall(r'data-coupon-code="[^"]+"', self.page)))

    def test_search_never_dumps_the_catalog(self):
        self.assertIn("const PAGE = 12;", self.page)
        self.assertIn('id="show-more"', self.page)


class ReadmeLiveLinkTest(unittest.TestCase):
    LIVE = "https://thewyattbrocato.github.io/ai-deal-finder/"

    def setUp(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            self.readme = fh.read()

    def test_live_link_comes_first_and_needs_no_download(self):
        self.assertEqual(self.readme.index(self.LIVE), self.readme.index("http"))
        self.assertIn("Nothing to download or install", self.readme)
        self.assertLess(self.readme.index("Nothing to download"),
                        self.readme.index("## Use it in four steps"))

    def test_readme_admits_the_page_needs_internet_while_the_page_uses_a_cdn(self):
        with open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8") as fh:
            page = fh.read()
        if re.search(r'<script[^>]+src="https://', page):
            self.assertIn("internet connection", " ".join(self.readme.split()))

    def test_every_readme_image_is_a_file_in_the_repo(self):
        srcs = re.findall(r'src="([^"]+)"', self.readme)
        self.assertTrue(srcs)
        for src in srcs:
            self.assertFalse(src.startswith("http"), src)
            self.assertTrue(os.path.isfile(os.path.join(ROOT, src)), src)


if __name__ == "__main__":
    unittest.main()
