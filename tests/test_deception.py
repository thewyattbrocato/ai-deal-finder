"""Stale and deceptive-deal checks (fixtures DC-001 .. DC-009 in FIXTURES.json).

Every rule runs with a pinned `as_of` so no test depends on the clock. The
judgment is a perfect 'buy' so only the deterministic rule can cause a verify.
"""

import json
import unittest
from pathlib import Path

from deal_finder.runtime import DealFinderError, build_jev_request, evaluate
from tests.test_runtime import judgment, state

ROOT = Path(__file__).resolve().parent.parent
NOW = "2026-09-19T14:00:00Z"  # two hours after the fixture observations


def fresh():
    value = state()
    value["request"]["as_of"] = NOW
    return value


def run(value):
    return evaluate(value, judgment())


class FixtureCatalogTest(unittest.TestCase):
    def test_every_deception_case_is_in_the_fixture_corpus(self):
        cases = {c["case_id"] for c in json.loads((ROOT / "FIXTURES.json").read_text())["cases"]}
        self.assertEqual({f"DC-00{n}" for n in range(1, 10)} - cases, set())


class BaselineTest(unittest.TestCase):
    def test_clean_evidence_still_buys_with_no_labels(self):
        result = run(fresh())
        self.assertEqual(result["verdict"], "buy")
        self.assertEqual(result["labels"], [])


class StaleTest(unittest.TestCase):  # DC-001
    def test_price_older_than_window_is_refused(self):
        value = fresh()
        value["request"]["freshness_window_hours"] = 1
        result = run(value)
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("freshness window", result["reason"])
        self.assertIn("Recheck", result["next_action"])

    def test_price_inside_window_is_kept(self):
        value = fresh()
        value["request"]["freshness_window_hours"] = 24
        self.assertEqual(run(value)["verdict"], "buy")

    def test_no_window_means_age_is_not_judged(self):
        value = fresh()
        value["request"]["as_of"] = "2027-09-19T14:00:00Z"
        self.assertEqual(run(value)["verdict"], "buy")

    def test_future_dated_evidence_is_refused(self):
        value = fresh()
        value["request"]["freshness_window_hours"] = 24
        value["candidates"][0]["observed_at"] = "2026-09-20T12:00:00Z"
        self.assertIn("future", run(value)["reason"])

    def test_bad_window_is_rejected(self):
        for bad in (0, -1, "24", True, 1.5):
            with self.subTest(bad=bad):
                value = fresh()
                value["request"]["freshness_window_hours"] = bad
                with self.assertRaises(DealFinderError):
                    evaluate(value)

    def test_stale_coupon_discount_is_refused(self):  # DC-002
        value = fresh()
        value["request"]["freshness_window_hours"] = 6
        winner = value["candidates"][0]
        winner["observed_at"] = "2026-09-19T13:00:00Z"
        winner["immediate_discount"] = "5.00"
        winner["coupon"] = {"code": "SAVE5", "status": "shopper-confirmed-at-checkout", "observed_at": "2026-09-17T12:00:00Z"}
        result = run(value)
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("coupon evidence", result["reason"])

    def test_counted_coupon_without_time_is_refused(self):  # DC-002
        value = fresh()
        value["request"]["freshness_window_hours"] = 6
        winner = value["candidates"][0]
        winner["immediate_discount"] = "5.00"
        winner["coupon"] = {"code": "SAVE5", "status": "shopper-confirmed-at-checkout"}
        self.assertIn("observation time is missing", run(value)["reason"])


class UrgencyTest(unittest.TestCase):  # DC-003
    def test_urgency_alone_is_labelled_and_ignored(self):
        value = fresh()
        value["candidates"][0]["urgency_signals"] = [{"kind": "scarcity", "text": "Only 2 left"}]
        result = run(value)
        self.assertEqual(result["verdict"], "buy")
        self.assertEqual(result["labels"][0]["kind"], "urgency")
        self.assertIn("not evidence of stock or a deadline", result["labels"][0]["text"])

    def test_urgency_that_returns_on_reload_is_refused(self):
        value = fresh()
        value["candidates"][0]["urgency_signals"] = [
            {"kind": "ends-tonight", "text": "Ends tonight", "repeats_on_reload": True}
        ]
        result = run(value)
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("not a real deadline", result["reason"])

    def test_urgency_never_makes_wait_impossible_or_forces_buy(self):
        value = fresh()
        value["candidates"][0]["urgency_signals"] = [{"kind": "countdown", "text": "02:59:59"}]
        value["history"] = {
            "provider": "Tracker", "coverage": "item", "region": "US", "window": "90d", "recheck_trigger": "Friday",
        }
        answers = judgment("wait")
        self.assertEqual(evaluate(value, answers)["verdict"], "wait")


class ReferencePriceTest(unittest.TestCase):  # DC-004
    def test_undated_was_price_is_labelled_and_never_subtracted(self):
        value = fresh()
        value["candidates"][0]["reference_price"] = {"amount": "60.00", "dated_history": False}
        result = run(value)
        self.assertEqual(result["verdict"], "buy")
        self.assertEqual(result["winner"]["landed_cost_low"], "21.20")
        self.assertEqual(result["labels"][0]["kind"], "reference-price")
        self.assertIn("not treated as a saving", result["labels"][0]["text"])

    def test_dated_history_needs_no_label(self):
        value = fresh()
        value["candidates"][0]["reference_price"] = {"amount": "30.00", "dated_history": True}
        self.assertEqual(run(value)["labels"], [])


class CouponConditionTest(unittest.TestCase):  # DC-005
    def test_counted_coupon_with_unstated_condition_is_refused(self):
        value = fresh()
        winner = value["candidates"][0]
        winner["immediate_discount"] = "5.00"
        winner["coupon"] = {"code": "SAVE5", "status": "shopper-confirmed-at-checkout", "conditions_unstated": True}
        result = run(value)
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("condition the page did not state", result["reason"])

    def test_uncounted_code_with_unstated_condition_is_labelled_only(self):
        value = fresh()
        value["candidates"][0]["coupon"] = {"code": "SAVE5", "status": "retailer-stated", "conditions_unstated": True}
        result = run(value)
        self.assertEqual(result["verdict"], "buy")
        self.assertEqual(result["winner"]["landed_cost_low"], "21.20")
        self.assertEqual(result["labels"][0]["kind"], "coupon-conditions")


class SellerTest(unittest.TestCase):  # DC-006
    def test_explicitly_unverified_seller_is_refused(self):
        value = fresh()
        value["candidates"][0]["seller_verified"] = False
        self.assertIn("unverified", run(value)["reason"])

    def test_red_flags_are_refused(self):
        value = fresh()
        value["candidates"][0]["seller_red_flags"] = ["domain registered 9 days ago"]
        self.assertEqual(run(value)["verdict"], "verify")

    def test_unchecked_marketplace_seller_is_labelled_unknown(self):
        value = fresh()
        value["candidates"][0]["fulfilled_by"] = "Marketplace"
        result = run(value)
        self.assertEqual(result["verdict"], "buy")
        self.assertEqual(result["labels"][0]["kind"], "seller")
        self.assertNotIn("safe", result["labels"][0]["text"].lower())


class AffiliateTest(unittest.TestCase):  # DC-007, DC-008
    def test_affiliate_winner_is_refused_and_disclosed(self):
        value = fresh()
        value["candidates"][0]["affiliate_link"] = True
        result = run(value)
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("commission", result["reason"])
        self.assertIn("affiliate-linked or sponsored", result["affiliate_disclosure"])

    def test_sponsored_rival_that_loses_is_labelled_only(self):
        value = fresh()
        value["candidates"][1]["sponsored"] = True
        result = run(value)
        self.assertEqual(result["verdict"], "buy")
        self.assertEqual(result["winner"]["id"], "C1")
        self.assertEqual([item["kind"] for item in result["labels"]], ["affiliate"])

    def test_default_disclosure_unchanged(self):
        self.assertIn("independent of commission", run(fresh())["affiliate_disclosure"])


class PrivacyTest(unittest.TestCase):  # DC-009
    def test_private_values_never_reach_a_jev_request(self):
        samples = {
            "email": "buyer@example.com",
            "card": "pay with 4111 1111 1111 1111",
            "ssn": "id 123-45-6789",
            "url_secret": "https://merchant.example/p?token=abc",
            "url_login": "https://user:pw@merchant.example/p",
        }
        for name, sample in samples.items():
            with self.subTest(name=name):
                value = fresh()
                value["candidates"][0]["variant"] = sample
                with self.assertRaisesRegex(DealFinderError, "private value"):
                    build_jev_request(value)
                with self.assertRaises(DealFinderError):
                    evaluate(value)

    def test_new_private_keys_are_rejected(self):
        for key in ("email", "phone", "session_cookie", "auth_token"):
            with self.subTest(key=key):
                value = fresh()
                value["request"][key] = "x"
                with self.assertRaisesRegex(DealFinderError, "private field"):
                    evaluate(value)

    def test_ordinary_numbers_are_not_private(self):
        value = fresh()
        value["candidates"][0]["variant"] = "blue 2-pack, item 1234567890123"
        self.assertEqual(run(value)["verdict"], "buy")
