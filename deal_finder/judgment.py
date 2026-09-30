"""Judgment-layer binding for ai-deal-finder V1 (rules-only).

JUDGMENT_ENGINE.md specifies Jev (TypeSafe System One, pinned model
`jev-1.13.0`) as the judgment engine for semantic decisions, with all
deterministic policy, arithmetic, provenance, consent, stops, and actions in
code. V1 ships the code side only:

- No live API calls, no SDK dependency, no credentials exist or are needed.
- The Jev question catalog (verdict Choice, substitute_fit/evidence_strength
  Scores, binary-condition Nouls) is mirrored here as deterministic heuristic
  gates so the composition order in code is fixed and testable.
- When the judgment service (or key) is unavailable, the fallback is always
  `verify`, never `buy`/`wait` (service-failure contract).

Live-Jev validation (threshold/weight tuning on the independently labeled
corpus, confidence-vs-accuracy plots, self-consistency repeats, pinned model
re-validation) is separately documented and requires a server-side
`TYPESAFE_API_KEY`; it is NOT part of V1 and must not gate V1 review.
See ASSUMPTIONS.md.
"""

from dataclasses import dataclass
from typing import List

from .decision import Decision, DecisionInput, Verdict, decide
from .evidence import VERIFIED_STATES


@dataclass
class JudgmentGates:
    """Deterministic mirrors of the Jev questions (code-owned thresholds)."""

    # substitute_fit_<id> minimum eligible level (proposed >= 2, code-owned).
    substitute_fit_minimum: int = 2


def substitute_fit_level(
    must_haves_met_count: int,
    must_haves_total: int,
    differences_stated: bool,
    quantity_normalized: bool,
    unknown_could_flip: bool,
) -> int:
    """0-3 substitute-fit level mirroring the Jev Score criteria."""
    if must_haves_total > 0 and must_haves_met_count < must_haves_total:
        return 0
    if not differences_stated:
        return 1
    if not quantity_normalized or unknown_could_flip:
        return 2
    return 3


def evidence_strength_level(state_name: str, conflict: bool = False) -> int:
    """0-3 evidence-strength level mirroring the Jev Score criteria."""
    if conflict:
        return 1
    return {
        "unverified": 0,
        "unknown": 0,
        "rejected": 0,
        "retailer-stated": 1,
        "user-provided": 1,
        "third-party-historical": 2,
        "observed-now": 3,
        "applied-in-anonymous-cart": 3,
    }.get(state_name, 0)


def judge(inp: DecisionInput, gates: JudgmentGates = JudgmentGates()) -> Decision:
    """Rules-only judgment path.

    Composition order (deterministic, in code):
    1. Service unavailable -> verify (V1 is always on this path for the
       semantic layer; the deterministic rules below still apply).
    2. Substitute eligibility via fit minimum; evidence minimums via
       strength levels; conflicts -> verify (handled in decide()).
    3. Verdict from decide(); V1 never upgrades evidence or authorizes
       action on a low-confidence judgment — the rules path has no
       confidence to spend, so buy requires every deterministic minimum.
    """
    for cand in inp.candidates:
        if not cand.is_substitute:
            continue
        total = len(cand.must_haves_met) + len(cand.must_haves_violated)
        level = substitute_fit_level(
            must_haves_met_count=len(cand.must_haves_met),
            must_haves_total=total,
            differences_stated=bool(cand.material_differences),
            quantity_normalized=True,  # V1 requires normalized quantity upstream
            unknown_could_flip=bool(cand.unknown_equivalence_gaps),
        )
        if level < gates.substitute_fit_minimum:
            cand.must_haves_violated = cand.must_haves_violated or [
                f"substitute fit level {level} below minimum {gates.substitute_fit_minimum}"
            ]
    decision = decide(inp)
    # A missing judgment never produces buy or wait: if no candidate carries
    # verified decisive evidence, force verify even if decide() passed.
    if decision.verdict in (Verdict.BUY, Verdict.WAIT):
        winner = next(
            (c for c in inp.candidates if c.id == decision.winner_id), None
        )
        states = (
            winner.price_determining_states or [winner.evidence_state]
            if winner
            else []
        )
        if winner is None or any(s not in VERIFIED_STATES for s in states):
            return Decision(
                verdict=Verdict.VERIFY,
                reasons=decision.reasons
                + ["judgment service unavailable: rules-only path cannot "
                     "upgrade unverified evidence to buy/wait"],
                manual_check=(
                    "Obtain an observed-now or applied-in-anonymous-cart "
                    "reading for the exact item and cart, then re-run."
                ),
                downgraded_from=decision.verdict.value,
            )
    return decision


def unavailable_fallback(reason: str) -> Decision:
    """Service-failure fallback: always verify with the named check."""
    return Decision(
        verdict=Verdict.VERIFY,
        reasons=[f"judgment unavailable: {reason}"],
        manual_check="Judgment service unavailable — manual check required.",
    )


def score_names(candidate_ids: List[str]) -> List[str]:
    """Canonical Jev question ids V1 mirrors (for review routing only)."""
    names = ["verdict"]
    for cid in candidate_ids:
        names.append(f"substitute_fit_{cid}")
        names.append(f"evidence_strength_{cid}")
    names.extend(
        [
            "identity_exact",
            "in_stock_win",
            "consent_covers_test",
            "history_supports_wait",
            "seller_flag_unresolved",
            "primary_page_blocked",
            "single_offer_only",
            "tamper_signs",
        ]
    )
    return names
