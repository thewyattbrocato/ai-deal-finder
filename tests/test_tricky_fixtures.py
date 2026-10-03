"""Tricky-deal fixtures TF-001 .. TF-008 in FIXTURES.json.

The judgment is a perfect 'buy', so only a deterministic rule can cause a
verify or an exclusion. Nothing is converted, inferred or assumed.
"""

import json
import unittest
from pathlib import Path

from deal_finder.runtime import evaluate
from tests.test_runtime import judgment, state

ROOT = Path(__file__).resolve().parent.parent


def run(value):
    return evaluate(value, judgment())


def kinds(result):
    return {(item["kind"], item["candidate"]) for item in result["labels"]}


class CatalogTest(unittest.TestCase):
    def test_every_tricky_case_is_in_the_fixture_corpus(self):
        cases = {c["case_id"] for c in json.loads((ROOT / "FIXTURES.json").read_text())["cases"]}
        self.assertEqual({f"TF-00{n}" for n in range(1, 9)} - cases, set())


class RegionAndCurrencyTest(unittest.TestCase):
    def test_other_region_is_left_out_and_labelled(self):  # TF-001
        value = state()
        value["candidates"][0]["region"] = "UK"
        result = run(value)
        self.assertEqual((result["verdict"], result["winner"]["id"]), ("buy", "C2"))
        self.assertIn(("not-comparable", "C1"), kinds(result))
        self.assertIn("region UK", result["labels"][0]["text"])

    def test_no_region_match_is_verify(self):  # TF-001
        value = state()
        for candidate in value["candidates"]:
            candidate["region"] = "UK"
        result = run(value)
        self.assertEqual(result["verdict"], "verify")
        self.assertIsNone(result["winner"])

    def test_other_currency_is_never_converted(self):  # TF-002
        value = state()
        value["candidates"][0]["currency"] = "GBP"
        result = run(value)
        self.assertEqual(result["winner"]["id"], "C2")
        self.assertIn("no conversion", result["labels"][0]["text"])

    def test_matching_currency_stays_in(self):  # TF-002
        value = state()
        value["candidates"][0]["currency"] = "usd"
        self.assertEqual(run(value)["winner"]["id"], "C1")


class ConditionTest(unittest.TestCase):
    def test_refurbished_left_out_when_only_new_accepted(self):  # TF-003
        value = state()
        value["request"]["acceptable_conditions"] = ["new"]
        value["candidates"][0]["condition"] = "refurbished"
        result = run(value)
        self.assertEqual(result["winner"]["id"], "C2")
        self.assertIn("refurbished", result["labels"][0]["text"])

    def test_condition_not_judged_when_shopper_stated_none(self):  # TF-003
        value = state()
        value["candidates"][0]["condition"] = "refurbished"
        result = run(value)
        self.assertEqual(result["winner"]["id"], "C1")
        self.assertEqual(result["labels"], [])

    def test_accepted_refurbished_can_win(self):  # TF-003
        value = state()
        value["request"]["acceptable_conditions"] = ["new", "Refurbished"]
        value["candidates"][0]["condition"] = "refurbished"
        self.assertEqual(run(value)["winner"]["id"], "C1")


class EligibilityTest(unittest.TestCase):
    def gated(self):
        value = state()
        value["candidates"][0]["eligibility_condition"] = "first order only"
        return value

    def test_unconfirmed_eligibility_is_refused(self):  # TF-004
        result = run(self.gated())
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("eligibility", result["reason"])
        self.assertIn("Ask the shopper", result["next_action"])
        self.assertIn(("eligibility", "C1"), kinds(result))

    def test_confirmed_eligibility_is_labelled_not_assumed(self):  # TF-004
        value = self.gated()
        value["candidates"][0]["eligibility_confirmed"] = True
        result = run(value)
        self.assertEqual(result["verdict"], "buy")
        self.assertIn("confirmed by the shopper", result["labels"][0]["text"])


class CouponTermsTest(unittest.TestCase):
    def coupon(self, counted):
        value = state()
        winner = value["candidates"][0]
        if counted:
            winner["immediate_discount"] = "5.00"
        winner["coupon"] = {
            "code": "SAVE5",
            "status": "applied-in-anonymous-cart" if counted else "retailer-stated",
            "terms_on_other_page": True,
        }
        return value

    def test_counted_discount_with_unread_terms_is_refused(self):  # TF-005
        result = run(self.coupon(True))
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("page that was not read", result["reason"])

    def test_uncounted_code_is_labelled_and_out_of_the_total(self):  # TF-005
        result = run(self.coupon(False))
        self.assertEqual(result["verdict"], "buy")
        self.assertIn(("coupon-terms-elsewhere", "C1"), kinds(result))
        self.assertEqual(result["winner"]["landed_cost_low"], "21.20")


class ArithmeticTest(unittest.TestCase):
    def test_shipping_fee_cancels_a_saving(self):  # TF-006
        value = state()
        value["candidates"][0]["shipping"] = "7"  # 20 + 7 + 1.20 = 28.20 > 26.50
        result = run(value)
        self.assertEqual(result["winner"]["id"], "C2")

    def test_pack_size_mismatch_is_excluded(self):  # TF-007
        value = state()
        value["candidates"][0].update(exact_match=False, variant="blue 4-pack", quantity_terms="4 units", item_price="1.00")
        self.assertEqual(run(value)["winner"]["id"], "C2")

    def test_subscription_only_price_is_excluded(self):  # TF-008
        value = state()
        value["candidates"][0]["subscription_only"] = True
        self.assertEqual(run(value)["winner"]["id"], "C2")

    def test_free_shipping_threshold_left_as_a_range_stays_unproven(self):  # TF-008
        value = state()
        value["candidates"][0]["shipping"] = {"min": 0, "max": 9}
        result = run(value)
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("overlap", result["reason"])


if __name__ == "__main__":
    unittest.main()
