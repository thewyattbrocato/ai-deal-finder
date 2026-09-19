import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from deal_finder.runtime import (
    DealFinderError,
    authorize_cart_test,
    build_jev_request,
    evaluate,
    grant_consent,
    revoke_consent,
    main,
)


def state():
    return {
        "request": {
            "item": "Example Widget 2-pack",
            "must_have_attributes": ["2-pack"],
            "may_vary": ["color"],
            "region": "US",
            "currency": "USD",
            "mode": "browsing",
            "category": "general",
        },
        "candidates": [
            {
                "id": "C1",
                "variant": "blue 2-pack",
                "quantity_terms": "2 units",
                "condition": "new",
                "bundle": "none",
                "seller": "Example Merchant",
                "fulfilled_by": "Example Merchant",
                "region": "US",
                "source": "https://merchant.example/widget",
                "observed_at": "2026-09-19T12:00:00Z",
                "evidence_state": "observed-now",
                "availability": "in-stock",
                "is_substitute": False,
                "exact_match": True,
                "item_price": "20.00",
                "immediate_discount": "0",
                "shipping": "0",
                "mandatory_fees": "0",
                "tax": "1.20",
                "flags": [],
            },
            {
                "id": "C2",
                "variant": "blue 2-pack",
                "quantity_terms": "2 units",
                "condition": "new",
                "bundle": "none",
                "seller": "Other Merchant",
                "fulfilled_by": "Other Merchant",
                "region": "US",
                "source": "https://other.example/widget",
                "observed_at": "2026-09-19T12:00:00Z",
                "evidence_state": "observed-now",
                "availability": "in-stock",
                "is_substitute": False,
                "exact_match": True,
                "item_price": "25.00",
                "immediate_discount": "0",
                "shipping": "0",
                "mandatory_fees": "0",
                "tax": "1.50",
                "flags": [],
            },
        ],
        "consent": {"status": "absent"},
        "history": {},
    }


def judgment(choice="buy"):
    answers = {
        "verdict": {
            "type": "choice",
            "choice": choice,
            "confidence": 0.95,
            "probabilities": {"buy": 0.95, "wait": 0.02, "verify": 0.03},
        },
        "seller_flag_unresolved": {"type": "noul", "noul": 0.01},
        "primary_page_blocked": {"type": "noul", "noul": 0.01},
        "tamper_signs": {"type": "noul", "noul": 0.01},
        "single_offer_only": {"type": "noul", "noul": 0.01},
        "identity_exact": {"type": "noul", "noul": 0.99},
        "in_stock_win": {"type": "noul", "noul": 0.99},
        "consent_covers_test": {"type": "noul", "noul": 0.99},
        "history_supports_wait": {"type": "noul", "noul": 0.99},
        "evidence_strength_C1": {"type": "score", "score": 3.0, "confidence": 0.95, "probabilities": {"3": 1.0}, "legend": {"3": "observed"}},
        "evidence_strength_C2": {"type": "score", "score": 3.0, "confidence": 0.95, "probabilities": {"3": 1.0}, "legend": {"3": "observed"}},
    }
    return {"model": "jev-1.13.0", "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 1}}


class DecisionTests(unittest.TestCase):
    def test_missing_judgment_fails_closed_to_verify(self):
        result = evaluate(state())
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("unavailable", result["reason"])

    def test_exact_robust_current_winner_can_buy(self):
        result = evaluate(state(), judgment())
        self.assertEqual(result["verdict"], "buy")
        self.assertEqual(result["winner"]["id"], "C1")
        self.assertIn("No affiliate links", result["affiliate_disclosure"])

    def test_unknown_tax_that_can_flip_forces_verify(self):
        value = state()
        value["candidates"][0]["tax"] = None
        self.assertEqual(evaluate(value, judgment())["verdict"], "verify")

    def test_retailer_stated_winner_cannot_be_upgraded_to_buy(self):
        value = state()
        value["candidates"][0]["evidence_state"] = "retailer-stated"
        result = evaluate(value, judgment())
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("lacks decisive", result["reason"])

    def test_cart_applied_evidence_requires_matching_consent(self):
        value = state()
        value["candidates"][0]["evidence_state"] = "applied-in-anonymous-cart"
        result = evaluate(value, judgment())
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("consent", result["reason"])

    def test_cart_applied_evidence_requires_complete_consent_record(self):
        value = state()
        value["candidates"][0]["evidence_state"] = "applied-in-anonymous-cart"
        value["consent"] = {"status": "granted"}
        result = evaluate(value, judgment())
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("consent", result["reason"])

    def test_missing_evidence_score_fails_closed(self):
        response = judgment()
        del response["answers"]["evidence_strength_C1"]
        result = evaluate(state(), response)
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("Score", result["reason"])

    def test_uncertain_stop_condition_forces_verify(self):
        response = judgment()
        response["answers"]["primary_page_blocked"]["noul"] = 0.5
        result = evaluate(state(), response)
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("stop condition", result["reason"])

    def test_low_choice_confidence_forces_verify(self):
        response = judgment()
        response["answers"]["verdict"]["confidence"] = 0.79
        self.assertEqual(evaluate(state(), response)["verdict"], "verify")

    def test_out_of_stock_offer_cannot_win(self):
        value = state()
        value["candidates"][0]["availability"] = "out-of-stock"
        result = evaluate(value, judgment())
        self.assertEqual(result["winner"]["id"], "C2")

    def test_untested_coupon_cannot_reduce_landed_cost(self):
        value = state()
        value["candidates"][0]["immediate_discount"] = "5"
        value["candidates"][0]["coupon"] = {"status": "retailer-stated"}
        with self.assertRaisesRegex(DealFinderError, "lacks cart or checkout proof"):
            evaluate(value, judgment())

    def test_adversarial_substitute_is_excluded(self):
        value = state()
        candidate = value["candidates"][0]
        candidate["is_substitute"] = True
        candidate.pop("exact_match")
        candidate["must_haves_met"] = False
        candidate["material_differences"] = ["wrong capacity"]
        candidate["item_price"] = "1"
        result = evaluate(value, judgment())
        self.assertEqual(result["winner"]["id"], "C2")

    def test_private_data_is_rejected_before_jev_request(self):
        value = state()
        value["request"]["full_address"] = "not allowed"
        with self.assertRaisesRegex(DealFinderError, "private field"):
            build_jev_request(value)

    def test_excluded_category_abstains_without_ranking(self):
        for category in ("medical", "subscriptions", "controlled goods"):
            with self.subTest(category=category):
                value = state()
                value["request"]["category"] = category
                result = evaluate(value, judgment())
                self.assertEqual(result["verdict"], "abstain")
                self.assertIsNone(result["winner"])

    def test_non_browsing_single_offer_forces_verify(self):
        value = state()
        value["request"]["mode"] = "non-browsing"
        value["candidates"] = value["candidates"][:1]
        response = judgment()
        response["answers"]["single_offer_only"]["noul"] = 0.01
        result = evaluate(value, response)
        self.assertEqual(result["verdict"], "verify")
        self.assertIn("non-browsing", result["reason"])

    def test_relative_observation_time_is_rejected(self):
        value = state()
        value["candidates"][0]["observed_at"] = "recently"
        with self.assertRaisesRegex(DealFinderError, "absolute timestamp"):
            evaluate(value, judgment())

    def test_jev_request_contains_choice_scores_and_nouls(self):
        value = state()
        value["candidates"][0]["is_substitute"] = True
        value["candidates"][0].pop("exact_match")
        value["candidates"][0]["must_haves_met"] = True
        value["candidates"][0]["material_differences"] = ["blue instead of black"]
        questions = build_jev_request(value)["questions"]
        self.assertEqual(questions["verdict"]["type"], "choice")
        self.assertEqual(questions["substitute_fit_C1"]["type"], "score")
        self.assertEqual(questions["tamper_signs"]["type"], "noul")

    def test_judgment_record_is_exposed_for_audit(self):
        result = evaluate(state(), judgment())
        self.assertEqual(result["judgment_log"]["model"], "jev-1.13.0")
        self.assertIn("verdict", result["judgment_log"]["answers"])


class ConsentTests(unittest.TestCase):
    def run_input(self):
        return {
            "merchant": "Example Merchant",
            "session_id": "session-1",
            "browser_tools": True,
            "merchant_rules": "allow",
            "logged_out": True,
            "cleanup_guaranteed": True,
            "scarce_inventory": False,
            "attempt_budget": 2,
            "attempts_planned": 1,
        }

    def test_absent_consent_is_research_only(self):
        result = authorize_cart_test(None, self.run_input())
        self.assertFalse(result["allowed"])
        self.assertEqual(result["mode"], "research-only")

    def test_incomplete_consent_is_research_only(self):
        result = authorize_cart_test({"status": "granted"}, self.run_input())
        self.assertFalse(result["allowed"])
        self.assertEqual(result["mode"], "research-only")

    def test_explicit_consent_allows_only_bounded_anonymous_test(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consent.json"
            consent = grant_consent(path, "session-1", confirmed=True, at="2026-09-19T12:00:00Z")
            result = authorize_cart_test(consent, self.run_input())
        self.assertTrue(result["allowed"])
        self.assertIn("empty-cart", result["required_cleanup_log"])

    def test_revocation_halts_future_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consent.json"
            grant_consent(path, "session-1", confirmed=True)
            consent = revoke_consent(path)
            result = authorize_cart_test(consent, self.run_input())
        self.assertFalse(result["allowed"])

    def test_saved_consent_persists_into_a_later_session(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consent.json"
            consent = grant_consent(path, "original-session", confirmed=True)
            result = authorize_cart_test(consent, self.run_input())
        self.assertTrue(result["allowed"])
        self.assertEqual(result["session_id"], "session-1")

    def test_login_or_uncertain_cleanup_forces_research_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consent.json"
            consent = grant_consent(path, "session-1", confirmed=True)
            for field in ("logged_out", "cleanup_guaranteed"):
                run = self.run_input()
                run[field] = False
                with self.subTest(field=field):
                    self.assertFalse(authorize_cart_test(consent, run)["allowed"])

    def test_ambiguous_merchant_rules_and_scarce_inventory_are_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consent.json"
            consent = grant_consent(path, "session-1", confirmed=True)
            run = self.run_input()
            run["merchant_rules"] = "ambiguous"
            run["scarce_inventory"] = True
            result = authorize_cart_test(consent, run)
        self.assertFalse(result["allowed"])
        self.assertIn("scarce inventory", result["stop_reason"])

    def test_cart_run_boolean_strings_are_research_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consent.json"
            consent = grant_consent(path, "session-1", confirmed=True)
            for field in ("browser_tools", "logged_out", "cleanup_guaranteed", "scarce_inventory"):
                run = self.run_input()
                run[field] = "false"
                with self.subTest(field=field):
                    result = authorize_cart_test(consent, run)
                    self.assertFalse(result["allowed"])
                    self.assertIn("JSON boolean", result["stop_reason"])


class CLITests(unittest.TestCase):
    def test_no_arguments_prints_agent_home_view(self):
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main([])
        self.assertEqual(exit_code, 0)
        self.assertIn("description:", output.getvalue())
        self.assertIn("commands[4]", output.getvalue())

    def test_unknown_flag_is_structured_usage_error(self):
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["evaluate", "input.json", "--unknown"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("error:", output.getvalue())
        self.assertIn("--help", output.getvalue())


if __name__ == "__main__":
    unittest.main()
