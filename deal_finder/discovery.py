"""Bounded discovery and substitute rules for ai-deal-finder V1.

At most 6 requested-item candidates and at most 4 substitute candidates per
decision. At most one additional option beyond the best requested-item offer
and the best qualifying substitute, and only when it changes the decision.

Authoritative rules: DISCOVERY.md, VISION.md ("Two Bounded Discovery Lanes"),
fixtures SUB-Q-001, SUB-A-001, SUB-A-002.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from .evidence import Candidate

MAX_REQUESTED_CANDIDATES = 6
MAX_SUBSTITUTE_CANDIDATES = 4


@dataclass
class DiscoveryBounds:
    must_have_attributes: List[str] = field(default_factory=list)
    may_vary_attributes: List[str] = field(default_factory=list)
    # Shopper-defined interpretations (e.g. what "local"/"similar" means).
    # Asked, never assumed; empty means "not yet asked".
    term_interpretations: dict = field(default_factory=dict)


@dataclass
class DiscoveryResult:
    requested: List[Candidate] = field(default_factory=list)
    substitutes: List[Candidate] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)  # id + why, per stopping rule
    extra_option: Optional[Candidate] = None


def substitute_eligible(candidate: Candidate, bounds: DiscoveryBounds) -> "tuple[bool, str]":
    """A substitute appears only when it satisfies every stated must-have
    with material differences stated beside its savings.

    SUB-A-001: a cheaper candidate violating a must-have is rejected, however
    large the saving. SUB-A-002: unknown manufacturer/durability/performance
    differences stay explicit and equivalence is never implied.
    """
    if not candidate.is_substitute:
        return True, "requested item; substitute rules do not apply"
    if candidate.must_haves_violated:
        return False, (
            "rejected as substitute: violates must-have attribute(s) "
            + ", ".join(candidate.must_haves_violated)
            + " (SUB-A-001: price must not win by changing the product)"
        )
    for attr in bounds.must_have_attributes:
        if attr not in candidate.must_haves_met:
            return False, (
                f"rejected as substitute: must-have '{attr}' not shown as met"
            )
    if not candidate.material_differences:
        return False, (
            "rejected as substitute: material differences undocumented; "
            "a substitute appears only with differences stated beside savings"
        )
    return True, "eligible substitute"


def check_bounds(result: DiscoveryResult) -> List[str]:
    """Fail-closed audit of candidate caps. Returns violations (empty=clean)."""
    violations = []
    if len(result.requested) > MAX_REQUESTED_CANDIDATES:
        violations.append(
            f"requested-item candidates exceed cap "
            f"({len(result.requested)} > {MAX_REQUESTED_CANDIDATES})"
        )
    if len(result.substitutes) > MAX_SUBSTITUTE_CANDIDATES:
        violations.append(
            f"substitute candidates exceed cap "
            f"({len(result.substitutes)} > {MAX_SUBSTITUTE_CANDIDATES})"
        )
    if result.extra_option is None and (
        len(result.requested) + len(result.substitutes) == 0
    ):
        violations.append("empty discovery set: nothing comparable to decide on")
    return violations


def stopping_rule_holds(
    leader_wins_robustly: bool,
    leader_evidence_meets_buy_minimum: bool,
    skipped_all_dominated: bool,
) -> bool:
    """Early stop only when ALL hold: robust range win, buy-minimum evidence,
    and every skipped candidate recorded as dominated (DISCOVERY.md)."""
    return (
        leader_wins_robustly
        and leader_evidence_meets_buy_minimum
        and skipped_all_dominated
    )
