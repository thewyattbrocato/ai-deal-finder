"""Coverage slice g8: nine more merchants (home, pet, beauty, tech, office, kitchen).

Offline: reads demo/evidence/*.json only. A merchant here means its product
pages were read (read-only GET plus the browser promo-text pass) and stored.
"""

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "demo"))

import catalog  # noqa: E402
import build as _unused  # noqa: E402,F401

NEW_MERCHANTS = {
    "hexclad": "hexclad.com", "greatjones": "greatjonesgoods.com",
    "openfarmpet": "openfarmpet.com", "tower28": "tower28beauty.com",
    "rarebeauty": "rarebeauty.com", "nativecos": "nativecos.com",
    "twelvesouth": "twelvesouth.com", "baronfig": "baronfig.com",
    "thesill": "thesill.com",
}
OBS, _EX = catalog.load_catalog()
KINDS = {o["kind"] for o in OBS if o["id"].split("-")[0] not in NEW_MERCHANTS}


def mine(prefix):
    return [o for o in OBS if o["id"].startswith(prefix + "-")]


def evidence(obs_id):
    with open(os.path.join(catalog.EVIDENCE_DIR, obs_id + ".json")) as f:
        return json.load(f)


class NewMerchantsTest(unittest.TestCase):
    def test_nine_new_merchants_and_thirty_six_products(self):
        for m in NEW_MERCHANTS:
            self.assertGreaterEqual(len(mine(m)), 4, m)
        total = sum(len(mine(m)) for m in NEW_MERCHANTS)
        self.assertGreaterEqual(total, 36)

    def test_each_product_has_stored_evidence_on_its_own_host(self):
        for m, host in NEW_MERCHANTS.items():
            for o in mine(m):
                ev = evidence(o["id"])
                self.assertEqual(ev["http_status"], 200, o["id"])
                self.assertTrue(ev["page_sha256"], o["id"])
                self.assertTrue(ev.get("rendered_checked"), o["id"])
                self.assertTrue(o["page_host"].endswith(host), o["id"])

    def test_price_is_traced_to_stored_page_data(self):
        for m in NEW_MERCHANTS:
            for o in mine(m):
                offers = catalog.offers_of(evidence(o["id"]))
                prices = {round(float(x.get("price") or
                                      x["priceSpecification"]["price"]), 2)
                          for x in offers}
                self.assertEqual(prices, {o["price"]}, o["id"])
                self.assertGreater(o["price"], 0)

    def test_kinds_come_from_existing_vocabulary(self):
        for m in NEW_MERCHANTS:
            for o in mine(m):
                self.assertIn(o["kind"], KINDS, o["id"])

    def test_no_coupon_without_page_text(self):
        for m in NEW_MERCHANTS:
            for o in mine(m):
                snippets = evidence(o["id"])["coupon_snippets"]
                if o["coupon"] is None:
                    for s in snippets:
                        c = catalog.CODE_RE.search(s)
                        self.assertTrue(not c or catalog.GATED_RE.search(s), o["id"])
                else:
                    self.assertTrue(any(o["coupon"]["text"] in s for s in snippets),
                                    o["id"])

    def test_the_only_coupons_are_open_farms_printed_autoship_code(self):
        coupons = {o["id"]: o["coupon"] for m in NEW_MERCHANTS for o in mine(m)
                   if o["coupon"]}
        self.assertTrue(coupons)
        for oid, c in coupons.items():
            self.assertTrue(oid.startswith("openfarmpet-"), oid)
            self.assertIn("Autoship", c["text"])

    def test_blocked_or_unusable_merchants_left_out(self):
        # fable.com prices in a non-USD currency, kosas.com pages carry no readable
        # product identity, ourplace/madeincookware/hydroflask/ridge refuse reads.
        shown = {o["id"].split("-")[0] for o in OBS}
        for skipped in ("fable", "kosas", "ourplace", "madeincookware",
                        "hydroflask", "ridge"):
            self.assertNotIn(skipped, shown)


if __name__ == "__main__":
    unittest.main()
