"""V1 unit tests: deterministic rules mapped to the FIXTURES.json draft corpus.

Run: python3 -m unittest discover -s tests -v  (stdlib only, no dependencies)

These tests pin the fail-closed behavior of the V1 rules engine. They do NOT
pass any acceptance gate: gates require independent relabeling and real-user
evidence per VALIDATION_RECORD.md.
"""

import unittest

from deal_finder import consent, decision, discovery, evidence, judgment, landed_cost
from deal_finder.consent import (
    ActionLog,
    AttemptBudget,
    CartTestGate,
    ConsentRecord,
    ConsentStatus,
    StopReason,
)
from deal_finder.decision import (
    DecisionInput,
    PriceHistory,
    Verdict,
    check_language,
    decide,
    format_answer,
)
from deal_finder.discovery import (
    DiscoveryBounds,
    DiscoveryResult,
    check_bounds,
    stopping_rule_holds,
    substitute_eligible,
)
from deal_finder.evidence import (
    Candidate,
    Claim,
    Coupon,
    EvidenceState,
    check_no_upgrade,
)
from deal_finder.landed_cost import LandedCost, RankedCandidate, rank, ranking_is_robust


def full_candidate(cid="C1", **kw):
    args = dict(
        id=cid,
        variant="Acme Widget 5000, 12oz box",
        quantity_terms="1x 12oz box",
        condition="new",
        bundle="single",
        seller="Acme Store",
        fulfilled_by="Acme Store",
        region="US",
        in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source="acme.example.com",
        observed_at="2026-09-30T12:00:00Z",
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    args.update(kw)
    return Candidate(**args)


def cost(price, **kw):
    args = dict(item_price=price, shipping=5.0, known_tax=2.0)
    args.update(kw)
    return LandedCost(**args)


class EvidenceTest(unittest.TestCase):
    def test_provenance_required(self):
        c = Claim(text="price $10", source="", region="US",
                  observed_at="2026-09-30T12:00:00Z",
                  state=EvidenceState.RETAILER_STATED)
        self.assertFalse(c.is_verified())
        self.assertEqual(len(check_no_upgrade([c])), 1)

    def test_observed_now_with_provenance_verifies(self):
        c = Claim(text="price $10", source="s", region="US",
                  observed_at="2026-09-30T12:00:00Z",
                  state=EvidenceState.OBSERVED_NOW)
        self.assertTrue(c.is_verified())
        self.assertEqual(check_no_upgrade([c]), [])

    def test_verified_state_without_provenance_flagged(self):
        # Live-verification regression (LV-003): indexed/pasted text labeled
        # observed-now with no source or timestamp must not pass the audit.
        c = Claim(text="price $249", source="", region="",
                  observed_at="",
                  state=EvidenceState.OBSERVED_NOW)
        self.assertFalse(c.is_verified())
        violations = check_no_upgrade([c])
        self.assertEqual(len(violations), 1)
        self.assertIn("without provenance", violations[0])

    def test_coupon_counting(self):
        self.assertTrue(Coupon(code="X", merchant="m",
                              status="applied-in-anonymous-cart").may_count_in_landed_cost())
        self.assertTrue(Coupon(code="X", merchant="m",
                              status="shopper-confirmed").may_count_in_landed_cost())
        for s in ("retailer-stated", "unverified", "rejected"):
            self.assertFalse(Coupon(code="X", merchant="m", status=s).may_count_in_landed_cost(),
                             s)


class LandedCostTest(unittest.TestCase):
    def test_rank_by_landed_not_headline(self):
        # Higher headline discount but higher landed cost must lose.
        a = RankedCandidate("A", cost(100, immediate_discount=40))  # 100-40+5+2=67
        b = RankedCandidate("B", cost(70, immediate_discount=5))    # 70-5+5+2=72
        c = RankedCandidate("C", cost(60, immediate_discount=0))    # 60+5+2=67 tie-ish
        ordered = rank([a, b, c])
        self.assertEqual([x.candidate_id for x in ordered], ["A", "C", "B"])

    def test_tax_unknown_open_ended_not_robust(self):
        a = RankedCandidate("A", cost(50, known_tax=None))  # low 55, high inf
        b = RankedCandidate("B", cost(60))                   # 67..67
        self.assertFalse(ranking_is_robust([a, b]))

    def test_robust_range_still_wins(self):
        # Leader unknown tax but rivals far above: still not robust (inf high).
        a = RankedCandidate("A", cost(10, known_tax=None))
        b = RankedCandidate("B", cost(1000))
        self.assertFalse(ranking_is_robust([a, b]))

    def test_known_costs_robust(self):
        a = RankedCandidate("A", cost(50))
        b = RankedCandidate("B", cost(80))
        self.assertTrue(ranking_is_robust([a, b]))

    def test_delayed_value_never_ranked(self):
        a = RankedCandidate("A", cost(70, delayed_conditional_value=30,
                                     delayed_value_note="$30 cash back later"))
        b = RankedCandidate("B", cost(65))
        self.assertEqual(rank([a, b])[0].candidate_id, "B")

    def test_subscription_excluded(self):
        a = RankedCandidate("A", cost(10, is_subscription_only=True))
        b = RankedCandidate("B", cost(90))
        ordered = rank([a, b])
        self.assertEqual([x.candidate_id for x in ordered], ["B"])
        self.assertTrue(ranking_is_robust([a, b]))

    def test_unknowns_listed(self):
        c = cost(50, known_tax=None, shipping=None,
                 eligibility_condition="student ID")
        self.assertIn("tax", c.unknowns())
        self.assertIn("shipping", c.unknowns())
        self.assertTrue(any("eligibility" in u for u in c.unknowns()))

    def test_full_address_never_needed(self):
        fields = set(LandedCost.__dataclass_fields__)
        self.assertNotIn("full_address", fields)
        self.assertNotIn("postal_code", fields)


class ConsentTest(unittest.TestCase):
    def granted(self):
        return ConsentRecord(status=ConsentStatus.GRANTED,
                             granted_at="2026-09-30T11:00:00Z",
                             session="s1", merchant="Acme",
                             last_changed_at="2026-09-30T11:00:00Z")

    def test_absent_consent_refuses_cart_test(self):
        gate = CartTestGate(consent=ConsentRecord(), budget=AttemptBudget(),
                            merchant="Acme")
        ok, reason = gate.authorize()
        self.assertFalse(ok)
        self.assertEqual(reason, StopReason.NO_CONSENT)

    def test_granted_consent_authorizes(self):
        gate = CartTestGate(consent=self.granted(), budget=AttemptBudget(),
                            merchant="Acme")
        ok, _ = gate.authorize()
        self.assertTrue(ok)

    def test_wrong_merchant_refused(self):
        gate = CartTestGate(consent=self.granted(), budget=AttemptBudget(),
                            merchant="Other")
        ok, reason = gate.authorize()
        self.assertFalse(ok)
        self.assertEqual(reason, StopReason.NO_CONSENT)

    def test_revocation_halts_mid_run(self):
        rec = self.granted()
        gate = CartTestGate(consent=rec, budget=AttemptBudget(), merchant="Acme")
        rec.revoke("2026-09-30T11:30:00Z")
        ok, reason = gate.check_revoked()
        self.assertFalse(ok)
        self.assertEqual(reason, StopReason.REVOKED)

    def test_ambiguous_terms_means_no_test(self):
        gate = CartTestGate(consent=self.granted(), budget=AttemptBudget(),
                            merchant="Acme", merchant_terms_ambiguous=True)
        ok, reason = gate.authorize()
        self.assertFalse(ok)
        self.assertEqual(reason, StopReason.MERCHANT_RULES_PROHIBIT)

    def test_no_browser_tools_means_research_only(self):
        gate = CartTestGate(consent=self.granted(), budget=AttemptBudget(),
                            merchant="Acme", browser_tools_available=False)
        ok, reason = gate.authorize()
        self.assertFalse(ok)
        self.assertEqual(reason, StopReason.NO_BROWSER_TOOLS)

    def test_budget_exhaustion_falls_back(self):
        budget = AttemptBudget(declared_max=1)
        self.assertTrue(budget.spend())
        self.assertFalse(budget.spend())
        gate = CartTestGate(consent=self.granted(), budget=budget, merchant="Acme")
        ok, reason = gate.authorize()
        self.assertFalse(ok)
        self.assertEqual(reason, StopReason.BUDGET_EXCEEDED)

    def test_action_log_records_budget_and_stop(self):
        log = ActionLog(merchant="Acme", declared_budget=3)
        log.record("applied SAVE10 in anonymous cart")
        log.budget_used = 1
        log.stop_reason = StopReason.COMPLETED
        log.cleanup_ok = True
        self.assertEqual(log.budget_used, 1)
        self.assertTrue(log.cleanup_ok)


class DiscoveryTest(unittest.TestCase):
    def test_caps(self):
        res = DiscoveryResult(
            requested=[full_candidate(f"R{i}") for i in range(7)],
            substitutes=[],
        )
        self.assertEqual(len(check_bounds(res)), 1)
        res2 = DiscoveryResult(
            requested=[],
            substitutes=[full_candidate(f"S{i}", is_substitute=True) for i in range(5)],
        )
        self.assertTrue(any("substitute" in v for v in check_bounds(res2)))

    def test_adversarial_must_have_violation_rejected(self):
        bounds = DiscoveryBounds(must_have_attributes=["12oz box"])
        sub = full_candidate("S1", is_substitute=True,
                             must_haves_met=[],
                             must_haves_violated=["12oz box"],
                             material_differences=["8oz box instead"])
        ok, _ = substitute_eligible(sub, bounds)
        self.assertFalse(ok)

    def test_adversarial_lookalike_needs_explicit_gaps(self):
        bounds = DiscoveryBounds(must_have_attributes=["widget"])
        sub = full_candidate("S1", is_substitute=True,
                             must_haves_met=["widget"],
                             material_differences=["private-label version"],
                             unknown_equivalence_gaps=["durability", "performance"])
        ok, _ = substitute_eligible(sub, bounds)
        self.assertTrue(ok)  # eligible for compare, but decide() caps at verify

    def test_substitute_without_differences_rejected(self):
        bounds = DiscoveryBounds(must_have_attributes=["widget"])
        sub = full_candidate("S1", is_substitute=True,
                             must_haves_met=["widget"],
                             material_differences=[])
        ok, _ = substitute_eligible(sub, bounds)
        self.assertFalse(ok)

    def test_qualifying_substitute_eligible(self):
        bounds = DiscoveryBounds(must_have_attributes=["widget"],
                                 may_vary_attributes=["color"])
        sub = full_candidate("S1", is_substitute=True,
                             must_haves_met=["widget"],
                             material_differences=["red instead of blue"])
        ok, _ = substitute_eligible(sub, bounds)
        self.assertTrue(ok)

    def test_stopping_rule_requires_all_three(self):
        self.assertTrue(stopping_rule_holds(True, True, True))
        self.assertFalse(stopping_rule_holds(True, True, False))
        self.assertFalse(stopping_rule_holds(True, False, True))
        self.assertFalse(stopping_rule_holds(False, True, True))


class DecisionTest(unittest.TestCase):
    def buy_input(self, **kw):
        c = full_candidate()
        args = dict(candidates=[c], ranked=[RankedCandidate("C1", cost(50))])
        args.update(kw)
        return DecisionInput(**args)

    def test_buy_when_all_minimums_met(self):
        d = decide(self.buy_input())
        self.assertEqual(d.verdict, Verdict.BUY)
        self.assertEqual(d.winner_id, "C1")
        self.assertTrue(d.next_action)

    def test_out_of_stock_excluded(self):
        c = full_candidate(in_stock=False)
        d = decide(DecisionInput(candidates=[c],
                                ranked=[RankedCandidate("C1", cost(50))]))
        self.assertEqual(d.verdict, Verdict.VERIFY)
        self.assertEqual(d.winner_id, "")

    def test_variant_mismatch_downgrades(self):
        c = full_candidate(variant="")  # identity not established
        d = decide(DecisionInput(candidates=[c],
                                ranked=[RankedCandidate("C1", cost(50))]))
        self.assertEqual(d.verdict, Verdict.VERIFY)

    def test_retailer_stated_cannot_buy(self):
        c = full_candidate(evidence_state=EvidenceState.RETAILER_STATED,
                           price_determining_states=[EvidenceState.RETAILER_STATED])
        d = decide(DecisionInput(candidates=[c],
                                ranked=[RankedCandidate("C1", cost(50))]))
        self.assertEqual(d.verdict, Verdict.VERIFY)
        self.assertTrue(d.manual_check)

    def test_verified_state_without_provenance_downgrades(self):
        # Live-verification regression (LV-003): observed-now with no
        # source/region/timestamp is unverified evidence and never upgrades.
        c = full_candidate(source="", region="", observed_at="")
        d = decide(DecisionInput(candidates=[c],
                                ranked=[RankedCandidate("C1", cost(50))]))
        self.assertEqual(d.verdict, Verdict.VERIFY)
        self.assertEqual(d.winner_id, "")
        self.assertTrue(d.manual_check)

    def test_untested_code_forces_verify(self):
        c = full_candidate()
        d = decide(DecisionInput(
            candidates=[c], ranked=[RankedCandidate("C1", cost(50))],
            coupons=[Coupon(code="SAVE20", merchant="Acme", status="unverified")]))
        # Winner evidence verified but ranking robustness unaffected here;
        # the untested code must be recorded as excluded.
        self.assertTrue(any("SAVE20" in r for r in d.reasons))

    def test_unknown_tax_overlap_downgrades(self):
        c1, c2 = full_candidate("C1"), full_candidate("C2")
        ranked = [RankedCandidate("C1", cost(50, known_tax=None)),
                  RankedCandidate("C2", cost(60))]
        d = decide(DecisionInput(candidates=[c1, c2], ranked=ranked))
        self.assertEqual(d.verdict, Verdict.VERIFY)

    def test_blocked_page_downgrades(self):
        c = full_candidate(primary_page_blocked=True)
        d = decide(DecisionInput(candidates=[c],
                                ranked=[RankedCandidate("C1", cost(50))]))
        self.assertEqual(d.verdict, Verdict.VERIFY)

    def test_unresolved_seller_flag_downgrades(self):
        c = full_candidate(seller_flags_unresolved=["returns unclear"])
        d = decide(DecisionInput(candidates=[c],
                                ranked=[RankedCandidate("C1", cost(50))]))
        self.assertEqual(d.verdict, Verdict.VERIFY)

    def test_conflict_without_cart_proof_downgrades(self):
        d = decide(self.buy_input(sources_conflict=True,
                                  conflict_resolved_by_cart_proof=False))
        self.assertEqual(d.verdict, Verdict.VERIFY)

    def test_conflict_resolved_by_cart_proof_buys(self):
        d = decide(self.buy_input(sources_conflict=True,
                                  conflict_resolved_by_cart_proof=True))
        self.assertEqual(d.verdict, Verdict.BUY)

    def test_single_pasted_offer_is_verify(self):
        c = full_candidate(evidence_state=EvidenceState.USER_PROVIDED,
                           price_determining_states=[EvidenceState.USER_PROVIDED])
        d = decide(DecisionInput(candidates=[c],
                                ranked=[RankedCandidate("C1", cost(50))],
                                mode="non-browsing"))
        self.assertEqual(d.verdict, Verdict.VERIFY)
        self.assertTrue(d.manual_check)

    def test_wait_needs_grounded_history_and_trigger(self):
        hist = PriceHistory(provider="Tracker", coverage="Acme Widget marketplace",
                            region="US", window="90d", favors_waiting=True)
        d = decide(self.buy_input(history=hist, recheck_trigger="recheck Friday"))
        self.assertEqual(d.verdict, Verdict.WAIT)
        # No target price from history alone.
        self.assertNotIn("$", d.next_action.replace("Recheck trigger:", ""))

    def test_history_only_target_refused(self):
        hist = PriceHistory(favors_waiting=True)  # ungrounded
        d = decide(self.buy_input(history=hist))
        self.assertEqual(d.verdict, Verdict.BUY)  # history ignored, evidence buys
        hist2 = PriceHistory(provider="T", coverage="c", region="r",
                             window="w", favors_waiting=True)
        d2 = decide(self.buy_input(history=hist2))  # no trigger, no pressure
        self.assertEqual(d2.verdict, Verdict.BUY)

    def test_abstain_subscription(self):
        d = decide(self.buy_input(category="subscription"))
        self.assertEqual(d.verdict, Verdict.ABSTAIN)

    def test_abstain_unresolvable_identity(self):
        d = decide(self.buy_input(identity_resolvable=False))
        self.assertEqual(d.verdict, Verdict.ABSTAIN)

    def test_stale_observation_downgrades(self):
        d = decide(self.buy_input(observation_stale=True))
        self.assertEqual(d.verdict, Verdict.VERIFY)

    def test_tamper_signs_downgrade(self):
        d = decide(self.buy_input(tamper_signs=True))
        self.assertEqual(d.verdict, Verdict.VERIFY)

    def test_lookalike_substitute_capped_at_verify(self):
        sub = full_candidate("S1", is_substitute=True,
                             must_haves_met=["widget"],
                             material_differences=["private-label version"],
                             unknown_equivalence_gaps=["durability"])
        d = decide(DecisionInput(candidates=[sub],
                                ranked=[RankedCandidate("S1", cost(40))]))
        self.assertEqual(d.verdict, Verdict.VERIFY)

    def test_qualifying_substitute_can_win(self):
        sub = full_candidate("S1", is_substitute=True,
                             must_haves_met=["widget"],
                             material_differences=["red instead of blue"])
        d = decide(DecisionInput(candidates=[sub],
                                ranked=[RankedCandidate("S1", cost(40))]))
        self.assertEqual(d.verdict, Verdict.BUY)
        self.assertTrue(any("differences stated" in r for r in d.reasons))

    def test_language_bans(self):
        self.assertIn("safe", check_language("this seller is safe"))
        self.assertIn("guaranteed", check_language("guaranteed savings"))
        self.assertIn("ending soon", check_language("sale ending soon!"))
        self.assertEqual(check_language("verified price $40 at stated timestamp"), [])

    def test_verify_never_smuggles_buy(self):
        d = decide(self.buy_input(observation_stale=True))
        text = format_answer(d).lower()
        self.assertNotIn("looks good", text)

    def test_format_answer_places_caveats(self):
        d = decide(self.buy_input(observation_stale=True))
        text = format_answer(d)
        self.assertIn("Verdict: verify", text)
        self.assertIn("Manual check:", text)


class JudgmentTest(unittest.TestCase):
    def test_rules_path_buys_on_verified_evidence(self):
        c = full_candidate()
        d = judgment.judge(DecisionInput(
            candidates=[c], ranked=[RankedCandidate("C1", cost(50))]))
        self.assertEqual(d.verdict, Verdict.BUY)

    def test_rules_path_never_upgrades_unverified(self):
        c = full_candidate(evidence_state=EvidenceState.UNVERIFIED,
                           price_determining_states=[EvidenceState.UNVERIFIED])
        d = judgment.judge(DecisionInput(
            candidates=[c], ranked=[RankedCandidate("C1", cost(50))]))
        self.assertEqual(d.verdict, Verdict.VERIFY)

    def test_unavailable_fallback_is_verify(self):
        d = judgment.unavailable_fallback("timeout")
        self.assertEqual(d.verdict, Verdict.VERIFY)
        self.assertTrue(d.manual_check)

    def test_fit_levels(self):
        self.assertEqual(judgment.substitute_fit_level(0, 1, True, True, False), 0)
        self.assertEqual(judgment.substitute_fit_level(1, 1, False, True, False), 1)
        self.assertEqual(judgment.substitute_fit_level(1, 1, True, True, True), 2)
        self.assertEqual(judgment.substitute_fit_level(1, 1, True, True, False), 3)

    def test_evidence_strength_levels(self):
        self.assertEqual(judgment.evidence_strength_level("observed-now"), 3)
        self.assertEqual(judgment.evidence_strength_level("retailer-stated"), 1)
        self.assertEqual(judgment.evidence_strength_level("unverified"), 0)
        self.assertEqual(judgment.evidence_strength_level("observed-now", conflict=True), 1)

    def test_score_names_cover_catalog(self):
        names = judgment.score_names(["C1"])
        for expected in ("verdict", "substitute_fit_C1", "evidence_strength_C1",
                         "consent_covers_test", "primary_page_blocked"):
            self.assertIn(expected, names)


class CouponSliceTest(unittest.TestCase):
    """Live coupon-slice regression (2026-10-01, OBS-8 … OBS-11).

    Real merchant-page observations: a retailer-stated code must be excluded
    while the winner can still hold without it (CP-002); offer text without
    a code never becomes a coupon; membership-gated shipping notes keep
    shipping Unknown (LC-003); markdown was-prices never enter arithmetic.
    """

    def test_retailer_stated_code_excluded_while_winner_holds(self):
        c = full_candidate(
            cid="oldnavy-sweatpants",
            variant="High-Waisted SoComfy Wide-Leg Sweatpants",
            quantity_terms="1 pair",
            seller="Old Navy", fulfilled_by="Old Navy",
            source="oldnavy.gap.com/browse/product.do?pid=777363182",
            observed_at="2026-10-01T19:50:21Z",
        )
        d = decide(DecisionInput(
            candidates=[c],
            ranked=[RankedCandidate("oldnavy-sweatpants", cost(25.0))],
            coupons=[Coupon(code="EXTRA", merchant="Old Navy",
                            status="retailer-stated")]))
        self.assertEqual(d.verdict, Verdict.BUY)
        self.assertEqual(d.winner_id, "oldnavy-sweatpants")
        self.assertTrue(any("EXTRA" in r and "excluded" in r
                            for r in d.reasons))

    def test_offer_text_without_code_stays_coupon_free(self):
        c = full_candidate(
            cid="gap-cardigan",
            variant="CashSoft Crop Cardigan",
            quantity_terms="1 cardigan",
            seller="Gap", fulfilled_by="Gap",
            source="www.gap.com/browse/product.do?pid=800546212",
            observed_at="2026-10-01T19:50:30Z",
        )
        d = decide(DecisionInput(
            candidates=[c],
            ranked=[RankedCandidate("gap-cardigan", cost(79.95))],
            coupons=[]))
        self.assertEqual(d.verdict, Verdict.BUY)
        self.assertFalse(any("code" in r for r in d.reasons))
        self.assertNotIn("code", format_answer(d).lower())

    def test_membership_shipping_note_stays_unknown(self):
        c = cost(87.97, shipping=None, known_tax=None,
                 eligibility_condition="members free shipping on orders "
                                       "$50+; membership not volunteered")
        self.assertIn("shipping", c.unknowns())
        self.assertTrue(any("eligibility" in u for u in c.unknowns()))
        self.assertEqual(c.known_high(), float("inf"))

    def test_markdown_reference_price_never_subtracted(self):
        # OBS-10: the ranked item price is the observed $87.97; the
        # "$155 / 43% off" reference lives outside LandedCost arithmetic.
        c = cost(87.97, shipping=None, known_tax=None)
        self.assertEqual(c.known_low(), 87.97)
        self.assertNotIn("67", c.range_label().replace("87.97", ""))


if __name__ == "__main__":
    unittest.main()
