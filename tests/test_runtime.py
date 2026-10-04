import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from deal_finder.runtime import (
    CART_DISABLED,
    DealFinderError,
    authorize_cart_test,
    build_jev_request,
    call_jev,
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


def granted(merchant="Example Merchant", attempt="attempt-1", session="session-1", at="2026-09-19T12:00:00Z"):
    """A consent record as the old CLI wrote it. No command writes one any more; the engine must ignore it."""
    return {
        "consent_id": "old-consent-record",
        "status": "granted",
        "scope": "logged-out anonymous-cart coupon testing; pre-payment totals only",
        "excludes": ["account mutation", "checkout", "inventory reservation", "login", "payment", "personal data"],
        "session_id": session,
        "merchant": merchant,
        "attempt": attempt,
        "granted_at": at,
        "last_changed_at": at,
    }


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

    def test_cart_applied_evidence_is_never_accepted(self):
        for consent in ({"status": "absent"}, {"status": "granted"}, granted()):
            with self.subTest(consent=consent.get("status"), complete="consent_id" in consent):
                value = state()
                value["candidates"][0]["evidence_state"] = "applied-in-anonymous-cart"
                value["consent"] = consent
                result = evaluate(value, judgment())
                self.assertEqual(result["verdict"], "verify")
                self.assertIn(CART_DISABLED, result["reason"])
                self.assertIn("yourself", result["next_action"])
                self.assertEqual(result["winner"]["landed_cost_low"], "21.20")  # shelf price, no discount
                self.assertIn(("cart-applied-not-accepted", "C1"), [(l["kind"], l["candidate"]) for l in result["labels"]])

    def test_cart_applied_evidence_cannot_reach_wait_either(self):
        value = state()
        value["candidates"][0]["evidence_state"] = "applied-in-anonymous-cart"
        value["history"] = {"provider": "T", "coverage": "c", "region": "US", "window": "90 days", "recheck_trigger": "later"}
        self.assertEqual(evaluate(value, judgment("wait"))["verdict"], "verify")

    def test_cart_applied_evidence_with_no_judgment_is_still_the_cart_refusal(self):
        value = state()
        value["candidates"][0]["evidence_state"] = "applied-in-anonymous-cart"
        self.assertIn(CART_DISABLED, evaluate(value)["reason"])

    def test_cart_applied_coupon_cannot_lower_the_price(self):
        value = state()
        value["candidates"][0]["immediate_discount"] = "5"
        value["candidates"][0]["coupon"] = {"code": "SAVE5", "status": "applied-in-anonymous-cart",
                                            "observed_at": "2026-09-19T12:00:00Z"}
        with self.assertRaisesRegex(DealFinderError, "lacks accepted proof"):
            evaluate(value, judgment())

    def test_cart_applied_candidate_cannot_carry_a_discount_even_with_no_coupon_object(self):
        value = state()
        value["candidates"][0]["evidence_state"] = "applied-in-anonymous-cart"
        value["candidates"][0]["immediate_discount"] = "5"
        with self.assertRaisesRegex(DealFinderError, "lacks accepted proof"):
            evaluate(value, judgment())

    def test_cart_applied_coupon_with_no_discount_is_labelled_and_the_shelf_price_stays(self):
        value = state()
        value["candidates"][1]["coupon"] = {"code": "SAVE5", "status": "applied-in-anonymous-cart"}
        result = evaluate(value, judgment())
        self.assertEqual(result["winner"]["id"], "C1")
        self.assertEqual(result["winner"]["landed_cost_low"], "21.20")
        self.assertIn(("cart-applied-not-accepted", "C2"), [(l["kind"], l["candidate"]) for l in result["labels"]])

    def test_a_coupon_the_shopper_confirmed_at_checkout_still_counts(self):
        value = state()
        value["candidates"][0]["immediate_discount"] = "5"
        value["candidates"][0]["coupon"] = {"code": "SAVE5", "status": "shopper-confirmed-at-checkout",
                                            "observed_at": "2026-09-19T12:00:00Z"}
        self.assertEqual(evaluate(value, judgment())["winner"]["landed_cost_low"], "16.20")

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
        with self.assertRaisesRegex(DealFinderError, "lacks accepted proof"):
            evaluate(value, judgment())

    def test_unproven_checkout_credit_does_not_beat_a_higher_cash_price(self):
        value = state()
        value["candidates"][0]["item_price"] = "30"
        value["candidates"][0]["immediate_discount"] = "0"
        value["candidates"][0]["checkout_credit"] = "20"
        value["candidates"][0]["tax"] = "0"
        value["candidates"][1]["item_price"] = "18"
        value["candidates"][1]["tax"] = "0"
        result = evaluate(value, judgment())
        self.assertEqual(result["verdict"], "buy")
        self.assertEqual(result["winner"]["id"], "C2")

    def test_unproven_checkout_credit_is_disclosed_with_delayed_value(self):
        value = state()
        value["candidates"][0]["checkout_credit"] = "5"
        value["candidates"][0]["delayed_value"] = "4% cash back"
        result = evaluate(value, judgment())
        self.assertEqual(result["verdict"], "buy")
        self.assertEqual(result["winner"]["id"], "C1")
        self.assertEqual(
            result["winner"]["delayed_value"],
            {"delayed_value": "4% cash back", "checkout_credit": "5"},
        )

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

    def test_private_data_aliases_are_rejected_before_jev_request(self):
        samples = {
            "credit_card": "4111111111111111",
            "credit_card_number": "4111111111111111",
            "ssn": "123-45-6789",
            "social_security_number": "123-45-6789",
            "payment_method": "visa",
            "shipping_address": "1 Main St",
        }
        for key, sample in samples.items():
            with self.subTest(key=key):
                value = state()
                value["request"][key] = sample
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

    def test_named_history_can_wait_without_extra_flag(self):
        value = state()
        value["history"] = {
            "provider": "Example Tracker",
            "coverage": "Example Widget 2-pack on Example Merchant",
            "region": "US",
            "window": "90 days",
            "recheck_trigger": "Recheck the merchant page before the restock window ends.",
        }
        result = evaluate(value, judgment("wait"))
        self.assertEqual(result["verdict"], "wait")
        self.assertIn("Recheck the merchant page", result["next_action"])

    def test_cart_applied_buy_with_matching_merchant_consent_no_longer_buys(self):
        # Was test_cart_applied_buy_with_matching_merchant_consent (asserted buy).
        value = state()
        value["candidates"][0]["evidence_state"] = "applied-in-anonymous-cart"
        value["consent"] = granted(merchant="Example Merchant")
        result = evaluate(value, judgment())
        self.assertEqual(result["verdict"], "verify")
        self.assertIn(CART_DISABLED, result["reason"])

    def test_malformed_coupon_shape_fails_closed(self):
        value = state()
        value["candidates"][0]["immediate_discount"] = "5"
        value["candidates"][0]["coupon"] = "SAVE10"
        with self.assertRaisesRegex(DealFinderError, "coupon must be an object"):
            evaluate(value, judgment())

    def test_malformed_verdict_answer_fails_closed_to_verify(self):
        response = judgment()
        response["answers"]["verdict"] = "buy"
        result = evaluate(state(), response)
        self.assertEqual(result["verdict"], "verify")

    def test_non_object_judgment_fails_closed_to_verify(self):
        result = evaluate(state(), ["buy"])
        self.assertEqual(result["verdict"], "verify")

    def test_non_object_jev_response_degrades_without_verdict(self):
        response = MagicMock()
        response.read.return_value = b"[1, 2]"
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}):
            with patch("deal_finder.runtime.urllib.request.urlopen", return_value=response):
                self.assertIsNone(call_jev(state()))

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


class CartRefusalTests(unittest.TestCase):
    """Replaces ConsentTests: grant, revoke and authorize all refuse (CONSENT.md keeps the design)."""

    def test_library_functions_refuse_with_the_stable_message(self):
        with self.assertRaisesRegex(DealFinderError, CART_DISABLED):
            authorize_cart_test(granted(), {"merchant": "Example Merchant"})
        with self.assertRaisesRegex(DealFinderError, CART_DISABLED):
            grant_consent(Path("never-written.json"), "s", True, merchant="m", attempt="a")
        with self.assertRaisesRegex(DealFinderError, CART_DISABLED):
            revoke_consent(Path("never-written.json"))
        self.assertFalse(Path("never-written.json").exists())

    def run_cli(self, *argv):
        output = StringIO()
        with redirect_stdout(output):
            code = main(list(argv))
        return code, output.getvalue()

    def test_consent_grant_refuses_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consent.json"
            code, out = self.run_cli(
                "consent", "grant", "--file", str(path), "--session", "s", "--merchant", "m",
                "--attempt", "a", "--confirmed",
            )
            self.assertFalse(path.exists())
        self.assertEqual(code, 1)
        self.assertIn(CART_DISABLED, out)

    def test_consent_revoke_and_bare_consent_refuse(self):
        for argv in (("consent", "revoke", "--file", "x.json"), ("consent",)):
            with self.subTest(argv=argv):
                code, out = self.run_cli(*argv)
                self.assertEqual(code, 1)
                self.assertIn(CART_DISABLED, out)

    def test_cart_check_refuses_even_with_a_perfect_old_record_and_run(self):
        run = {
            "merchant": "Example Merchant", "attempt": "attempt-1", "session_id": "session-1",
            "browser_tools": True, "merchant_rules": "allow", "logged_out": True,
            "cleanup_guaranteed": True, "scarce_inventory": False,
            "attempt_budget": 2, "attempts_planned": 1,
        }
        with tempfile.TemporaryDirectory() as directory:
            consent_path, run_path = Path(directory) / "consent.json", Path(directory) / "run.json"
            consent_path.write_text(json.dumps(granted()))
            run_path.write_text(json.dumps(run))
            code, out = self.run_cli("cart-check", "--consent", str(consent_path), "--run", str(run_path))
        self.assertEqual(code, 1)
        self.assertIn(CART_DISABLED, out)
        self.assertNotIn("allowed", out)

    def test_cart_check_refuses_before_reading_any_file(self):
        code, out = self.run_cli("cart-check", "--consent", "missing.json", "--run", "missing.json")
        self.assertEqual(code, 1)
        self.assertIn(CART_DISABLED, out)
        self.assertNotIn("file not found", out)


class CLITests(unittest.TestCase):
    def test_no_arguments_prints_agent_home_view(self):
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main([])
        self.assertEqual(exit_code, 0)
        self.assertIn("description:", output.getvalue())
        self.assertIn("commands[5]", output.getvalue())

    def test_unknown_flag_is_structured_usage_error(self):
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["evaluate", "input.json", "--unknown"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("error:", output.getvalue())
        self.assertIn("--help", output.getvalue())


if __name__ == "__main__":
    unittest.main()
