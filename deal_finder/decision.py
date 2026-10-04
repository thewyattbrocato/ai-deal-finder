"""Recommendation verdicts for ai-deal-finder V1.

buy / wait / verify / abstain per DECISION_TABLE.md (semantic authority).
buy needs every minimum; any downgrade trigger forces verify; scope and
safety stops abstain with no ranking. Fail closed throughout.

JUDGMENT_ENGINE.md binding: this module is the deterministic composition
layer (abstain gate, hard stops, arithmetic rank, downgrade rules). The Jev
Choice/Score/Noul layer is specified but not called in V1 (no API key, no
live calls); see judgment.py for the rules-only fallback contract.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .consent import CART_DISABLED_MESSAGE, ConsentRecord, ConsentStatus
from .evidence import VERIFIED_STATES, Candidate, Coupon, EvidenceState
from .landed_cost import RankedCandidate, ranking_is_robust


class Verdict(str, Enum):
    BUY = "buy"
    WAIT = "wait"
    VERIFY = "verify"
    ABSTAIN = "abstain"


# Scope stops: excluded categories that abstain instead of ranking (VISION.md).
EXCLUDED_CATEGORIES = frozenset(
    {
        "subscription",
        "financial",
        "medical",
        "controlled",
        "resale-speculation",
        "negotiation",
    }
)

# Language bans without scope-matched evidence (DECISION_TABLE.md).
BANNED_PHRASES = (
    "safe",
    "guaranteed",
    "best ever",
    "works",  # for coupon claims: no code is ever cart-tested
    "ending soon",
    "lowest ever",
)


@dataclass
class PriceHistory:
    provider: str = ""
    coverage: str = ""  # item/marketplace covered
    region: str = ""
    window: str = ""  # time window
    favors_waiting: bool = False
    note: str = ""

    def is_grounded(self) -> bool:
        return bool(self.provider and self.coverage and self.region and self.window)


@dataclass
class DecisionInput:
    candidates: List[Candidate] = field(default_factory=list)
    ranked: List[RankedCandidate] = field(default_factory=list)
    coupons: List[Coupon] = field(default_factory=list)
    consent: ConsentRecord = field(default_factory=ConsentRecord)
    history: PriceHistory = field(default_factory=PriceHistory)
    mode: str = "browsing"  # browsing | non-browsing
    category: str = ""
    identity_resolvable: bool = True
    observation_stale: bool = False
    tamper_signs: bool = False
    sources_conflict: bool = False
    deadline_or_stock_pressure: bool = False
    recheck_trigger: str = ""


@dataclass
class Decision:
    verdict: Verdict
    winner_id: str = ""
    reasons: List[str] = field(default_factory=list)
    # verify carries exactly one manual check that would change the decision.
    manual_check: str = ""
    # buy names one next action; wait names an actionable recheck trigger.
    next_action: str = ""
    downgraded_from: str = ""


def _identity_matched(c: Candidate) -> bool:
    return bool(
        c.variant
        and c.seller
        and c.fulfilled_by
        and c.region
        and c.quantity_terms
        and c.condition
    )


def check_language(text: str) -> List[str]:
    """Flag banned phrases. Returns violations (empty = clean)."""
    lowered = text.lower()
    return [p for p in BANNED_PHRASES if p in lowered]


def decide(inp: DecisionInput) -> Decision:
    reasons: List[str] = []

    # 1. Abstain gate (scope/safety stop decided before any judgment).
    if inp.category.strip().lower() in EXCLUDED_CATEGORIES:
        return Decision(
            verdict=Verdict.ABSTAIN,
            reasons=[f"refused: out-of-scope category '{inp.category}' (no ranking)"],
        )
    if not inp.identity_resolvable:
        return Decision(
            verdict=Verdict.ABSTAIN,
            reasons=["refused: cannot establish what the item is (no ranking)"],
        )

    in_stock = [c for c in inp.candidates if c.in_stock]
    if not in_stock:
        return Decision(
            verdict=Verdict.VERIFY,
            manual_check="No in-stock candidate observed; recheck availability, then re-run.",
            reasons=["out-of-stock offers are excluded from recommendations"],
        )

    # Provisional winner: cheapest in-stock candidate by known landed cost.
    winner: Optional[Candidate] = None
    if inp.ranked:
        ranked_ids = [r.candidate_id for r in inp.ranked]
        for cid in ranked_ids:
            cand = next((c for c in in_stock if c.id == cid), None)
            if cand is not None:
                winner = cand
                break
    if winner is None:
        winner = in_stock[0]

    downgraded_from = ""

    def downgrade(manual_check: str, reason: str) -> Decision:
        return Decision(
            verdict=Verdict.VERIFY,
            winner_id="",
            reasons=reasons + [reason],
            manual_check=manual_check,
            downgraded_from=downgraded_from or "buy",
        )

    # 2. Hard stops first (each forces verify whatever the evidence says).
    if winner.primary_page_blocked:
        return downgrade(
            f"Manually open the merchant page for '{winner.variant}' from {winner.seller} "
            "and confirm the current price; only indexed text supports the claim.",
            "primary merchant page blocked: indexed text is unverified discovery only",
        )
    if winner.seller_flags_unresolved:
        return downgrade(
            f"Resolve the seller flag(s) for {winner.seller} "
            f"({', '.join(winner.seller_flags_unresolved)}) before buying.",
            "unresolved seller/fulfillment flag on the leading candidate",
        )
    if not winner.seller:
        return downgrade(
            "Identify the seller of record and fulfillment party before buying.",
            "seller cannot be identified",
        )
    if inp.tamper_signs:
        return downgrade(
            "Re-source the offer from the merchant page; pasted/indexed content "
            "shows tampering/injection signs.",
            "tamper/injection signs in pasted or indexed content",
        )
    if inp.sources_conflict:
        return downgrade(
            "Reconcile the conflicting sources on the merchant page (the shopper "
            "can check the total at checkout) and re-run.",
            "sources conflict and nothing observed resolves the conflict "
            "(cart-applied proof is not accepted)",
        )
    if inp.mode == "non-browsing" and len(inp.candidates) < 2:
        return downgrade(
            "Gather one comparable offer (same variant/quantity/condition) or run "
            "with browsing; three-minute checklist: match variant, seller, "
            "fulfillment, landed cost, stock.",
            "non-browsing mode with fewer than two comparable offers; "
            "live facts were not independently verified",
        )
    if inp.observation_stale:
        return downgrade(
            "Recheck the current price and stock, then re-run.",
            "observation is stale relative to price/stock volatility",
        )

    # 3. Winner depends on an untested code -> verify.
    for coupon in inp.coupons:
        if not coupon.may_count_in_landed_cost():
            reasons.append(
                f"code '{coupon.code}' is {coupon.status}; excluded from landed cost "
                "and must not decide the verdict"
            )
    # (If ranked totals already excluded untested codes, this is a no-op audit.)

    # 4. Landed-cost robustness: unknowns that could flip the ranking.
    robust = ranking_is_robust(inp.ranked) if inp.ranked else True
    unknowns_flip = bool(inp.ranked) and not robust
    if unknowns_flip:
        return downgrade(
            "Pin down the unknown cost component(s) (tax/shipping/eligibility) "
            "to a merchant-stated figure, then re-run.",
            "price-determining component Unknown and ranking not robust to it; "
            "range overlap could flip the winner",
        )

    # 5. buy minimums: exact identity, verified decisive claims, in stock,
    #    no unresolved flags (already checked), robust cost (checked).
    if not _identity_matched(winner):
        return downgrade(
            "Confirm the exact variant, quantity, condition, bundle, seller, "
            "fulfillment party, and region, then re-run.",
            "leading candidate identity not fully matched",
        )
    # Provenance gate: a verified state without source/region/timestamp is
    # pasted or indexed text, not an observation. Unverified evidence never
    # upgrades, so the winner cannot support buy/wait without provenance.
    if not (winner.source and winner.region and winner.observed_at):
        return downgrade(
            "Re-observe the offer at its source (merchant page URL) and record "
            "the source, region, and timestamp, then re-run.",
            "leading candidate claims verified evidence without provenance "
            "(source, region, timestamp missing)",
        )
    decisive = winner.price_determining_states or [winner.evidence_state]
    if any(s not in VERIFIED_STATES for s in decisive):
        states = ", ".join(sorted({s.value for s in decisive}))
        # Retailer-stated/user-provided/untested evidence cannot support buy.
        if EvidenceState.APPLIED_IN_ANONYMOUS_CART in decisive:
            return downgrade(
                "Cart-applied checks are disabled. Open the merchant page and check "
                "the code and the payable total at checkout yourself; the shelf "
                "price stays the price until you do. Then re-run with what you saw.",
                "cart-applied evidence is not accepted: " + CART_DISABLED_MESSAGE,
            )
        if winner.evidence_state == EvidenceState.RETAILER_STATED:
            check = (
                "Check the code at checkout yourself and supply the total you see "
                "(shopper-confirmed), then re-run; the skill tries no code in a cart."
            )
        elif winner.evidence_state == EvidenceState.USER_PROVIDED:
            check = (
                "Corroborate the user-provided price against a current merchant "
                "listing or a checkout result, then re-run."
            )
        else:
            check = (
                "Obtain an observed-now reading for the exact item from the "
                "merchant page, then re-run."
            )
        return downgrade(check, f"decisive claims not verified (states: {states})")

    # 6. wait: grounded history reason + actionable trigger, no pressure.
    if (
        inp.history.favors_waiting
        and inp.history.is_grounded()
        and not inp.deadline_or_stock_pressure
        and inp.recheck_trigger
    ):
        return Decision(
            verdict=Verdict.WAIT,
            winner_id=winner.id,
            reasons=reasons
            + [
                f"history ({inp.history.provider}, {inp.history.coverage}, "
                f"{inp.history.region}, {inp.history.window}) favors waiting"
            ],
            next_action=f"Recheck trigger: {inp.recheck_trigger}",
        )
    if inp.history.favors_waiting and not inp.history.is_grounded():
        reasons.append(
            "history reason ignored: provider, coverage, region, and window "
            "not all named"
        )

    # 7. buy: all minimums met.
    buy_reasons = reasons + [
        f"exact identity matched for '{winner.variant}' from {winner.seller}",
        "landed cost known or a still-winning range; decisive claims verified; in stock",
    ]
    # Substitute winner must carry its material differences visibly.
    if winner.is_substitute:
        if winner.unknown_equivalence_gaps:
            return downgrade(
                "Document or test the unknown differences "
                f"({', '.join(winner.unknown_equivalence_gaps)}) before buying; "
                "equivalence must never be implied.",
                "lookalike substitute with unknown manufacturer/durability/ "
                "performance differences; verify at best",
            )
        buy_reasons.append(
            "substitute differences stated beside savings: "
            + "; ".join(winner.material_differences)
        )
    return Decision(
        verdict=Verdict.BUY,
        winner_id=winner.id,
        reasons=buy_reasons,
        next_action=(
            f"Buy '{winner.variant}' from {winner.seller} at the verified landed "
            "cost; recheck price/stock at purchase time."
        ),
    )


def format_answer(decision: Decision, winner: Optional[Candidate] = None) -> str:
    """Concise text-first rendering: caveats beside the claims they qualify."""
    lines = [f"Verdict: {decision.verdict.value}"]
    if decision.winner_id:
        lines.append(f"Winner: {decision.winner_id}")
    for reason in decision.reasons:
        lines.append(f"- {reason}")
    if decision.verdict == Verdict.VERIFY:
        lines.append(f"Manual check: {decision.manual_check}")
    if decision.next_action:
        lines.append(f"Next action: {decision.next_action}")
    if decision.downgraded_from:
        lines.append(f"(downgraded from {decision.downgraded_from})")
    _ = winner  # caller may append candidate detail lines
    return "\n".join(lines)
