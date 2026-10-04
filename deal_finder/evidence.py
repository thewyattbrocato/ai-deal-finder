"""Evidence states and claim provenance for ai-deal-finder V1.

Deterministic policy layer: every material price, coupon, availability, seller,
urgency, and history claim names its source, region, timestamp, and evidence
state. Nothing here calls a network, a model, or any credential.

Authoritative rules: VISION.md ("Evidence Before Confidence"), ACCEPTANCE.md
severity classes, JUDGMENT_ENGINE.md (code owns provenance and evidence-state
assignment; Jev only judges semantics over assembled evidence).
"""

from dataclasses import dataclass, field
from enum import Enum


class EvidenceState(str, Enum):
    OBSERVED_NOW = "observed-now"
    APPLIED_IN_ANONYMOUS_CART = "applied-in-anonymous-cart"
    RETAILER_STATED = "retailer-stated"
    THIRD_PARTY_HISTORICAL = "third-party-historical"
    USER_PROVIDED = "user-provided"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


# States that count as verification for a price-determining claim.
# buy minimums (DECISION_TABLE.md) require decisive claims to be one of these.
# applied-in-anonymous-cart stays a known state so old evidence parses, but it
# is never verification: cart-applied checks are disabled until the consent
# link is redesigned (CONSENT.md).
VERIFIED_STATES = frozenset({EvidenceState.OBSERVED_NOW})

# States that must never be silently treated as verification (ACCEPTANCE.md
# Evidence gate: zero upgrades without matching proof).
NEVER_VERIFIED_ALONE = frozenset(
    {
        EvidenceState.APPLIED_IN_ANONYMOUS_CART,
        EvidenceState.RETAILER_STATED,
        EvidenceState.THIRD_PARTY_HISTORICAL,
        EvidenceState.USER_PROVIDED,
        EvidenceState.UNVERIFIED,
        EvidenceState.REJECTED,
        EvidenceState.UNKNOWN,
    }
)


@dataclass(frozen=True)
class Claim:
    """One attributable claim. All four provenance fields are required."""

    text: str
    source: str
    region: str
    observed_at: str  # ISO-8601 timestamp string; stale checks compare recency
    state: EvidenceState = EvidenceState.UNKNOWN

    def has_provenance(self) -> bool:
        return bool(self.source and self.region and self.observed_at)

    def is_verified(self) -> bool:
        return self.state in VERIFIED_STATES and self.has_provenance()


@dataclass
class Coupon:
    """A coupon/coupon-code candidate with its verification state."""

    code: str
    merchant: str
    # One of: retailer-stated, unverified, rejected, shopper-confirmed (the
    # shopper safely supplied a checkout result). applied-in-anonymous-cart is
    # no longer accepted: the skill tries no code in a cart.
    status: str
    observed_at: str = ""
    reject_reason: str = ""
    terms_source: str = ""

    def may_count_in_landed_cost(self) -> bool:
        """A code counts only if the shopper confirmed it at checkout.

        retailer-stated or unverified codes must never decide a buy verdict
        (fixtures CP-002, CP-003); rejected codes are excluded (CP-004); a
        cart-applied status is not accepted (cart checks are disabled).
        """
        return self.status == "shopper-confirmed"


def check_no_upgrade(claims: "list[Claim]") -> "list[str]":
    """Fail-closed audit: flag any claim presented as verified without proof.

    Returns a list of violation messages (empty = clean). Callers must treat
    any violation as an S1 evidence error and downgrade to verify.
    """
    violations = []
    for claim in claims:
        if claim.state == EvidenceState.APPLIED_IN_ANONYMOUS_CART:
            violations.append(
                "cart-applied evidence is not accepted (cart checks are disabled "
                f"until the consent link is redesigned): {claim.text[:80]}"
            )
        if claim.state in NEVER_VERIFIED_ALONE and not claim.has_provenance():
            violations.append(
                f"claim lacks provenance and must stay {claim.state.value}: "
                f"{claim.text[:80]}"
            )
        if claim.state in VERIFIED_STATES and not claim.has_provenance():
            violations.append(
                f"claim presented as {claim.state.value} without provenance "
                f"(source, region, timestamp required): {claim.text[:80]}"
            )
    return violations


@dataclass
class Candidate:
    """One comparable offer for the requested item or a substitute."""

    id: str
    variant: str
    quantity_terms: str = ""
    condition: str = "new"
    bundle: str = ""
    seller: str = ""
    fulfilled_by: str = ""
    region: str = ""
    in_stock: bool = True
    is_substitute: bool = False
    # Substitute-only: shopper-stated must-haves this candidate satisfies.
    must_haves_met: "list[str]" = field(default_factory=list)
    must_haves_violated: "list[str]" = field(default_factory=list)
    # Material differences vs the requested item, stated beside savings.
    material_differences: "list[str]" = field(default_factory=list)
    # Unknown manufacturer/durability/performance differences (SUB-A-002).
    unknown_equivalence_gaps: "list[str]" = field(default_factory=list)
    seller_flags_unresolved: "list[str]" = field(default_factory=list)
    evidence_state: EvidenceState = EvidenceState.UNKNOWN
    source: str = ""
    observed_at: str = ""
    # Primary merchant page blocked; only indexed text supports the claim.
    primary_page_blocked: bool = False
    claims: "list[Claim]" = field(default_factory=list)
    price_determining_states: "list[EvidenceState]" = field(default_factory=list)
