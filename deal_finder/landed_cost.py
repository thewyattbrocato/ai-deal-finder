"""Landed-cost arithmetic and ranking for ai-deal-finder V1.

Known landed cost = item price - immediate discount + shipping + mandatory
fees + known tax + required membership/bundle cost - credit actually applied
at checkout. Nothing else enters the ranked number (LANDED_COST.md).

Unknowns control the ranking: when unknown spans overlap such that the
ranking could flip, output shows the range overlap and the verdict downgrades
to verify unless the ranking is robust to the unknown. No false precision.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class LandedCost:
    """One candidate's landed cost. Unknown components stay explicit."""

    item_price: float
    immediate_discount: float = 0.0
    shipping: Optional[float] = None  # None = Unknown (LC-002)
    shipping_range: Optional["tuple[float, float]"] = None
    mandatory_fees: float = 0.0
    known_tax: Optional[float] = None  # None = Unknown (LC-001)
    membership_or_bundle_cost: float = 0.0
    checkout_applied_credit: float = 0.0  # only credit applied at checkout
    # Delayed/conditional value (cash back, rebates, points, gift cards):
    # shown separately, NEVER subtracted from the ranked amount (LC-004).
    delayed_conditional_value: float = 0.0
    delayed_value_note: str = ""
    # Eligibility-gated price (member/student/first-order): retailer-stated
    # with the condition attached; eligibility never assumed (LC-003).
    eligibility_condition: str = ""
    # Subscription-only pricing is excluded from V1 even if lower.
    is_subscription_only: bool = False
    currency: str = "USD"

    def known_low(self) -> float:
        """Lowest amount due consistent with what is known."""
        ship = self._ship_low()
        tax = self.known_tax if self.known_tax is not None else 0.0
        return (
            self.item_price
            - self.immediate_discount
            + ship
            + self.mandatory_fees
            + tax
            + self.membership_or_bundle_cost
            - self.checkout_applied_credit
        )

    def known_high(self) -> float:
        """Highest amount due consistent with what is known.

        Unknown tax/shipping are unbounded above, so a cost with an Unknown
        component has no finite high bound: the range is open-ended.
        """
        if self.known_tax is None or (
            self.shipping is None and self.shipping_range is None
        ):
            return float("inf")
        return (
            self.item_price
            - self.immediate_discount
            + self._ship_high()
            + self.mandatory_fees
            + self.known_tax
            + self.membership_or_bundle_cost
            - self.checkout_applied_credit
        )

    def _ship_low(self) -> float:
        if self.shipping is not None:
            return self.shipping
        if self.shipping_range is not None:
            return self.shipping_range[0]
        return 0.0

    def _ship_high(self) -> float:
        if self.shipping is not None:
            return self.shipping
        if self.shipping_range is not None:
            return self.shipping_range[1]
        return 0.0  # open-ended; known_high() returns inf in this case

    def unknowns(self) -> List[str]:
        out = []
        if self.known_tax is None:
            out.append("tax")
        if self.shipping is None and self.shipping_range is None:
            out.append("shipping")
        if self.eligibility_condition:
            out.append(f"eligibility: {self.eligibility_condition}")
        return out

    def range_label(self) -> str:
        high = self.known_high()
        high_s = "open-ended (unknown unbounded above)" if high == float("inf") else f"{high:.2f}"
        return f"{self.currency} {self.known_low():.2f} .. {high_s}"


@dataclass
class RankedCandidate:
    candidate_id: str
    cost: LandedCost


def rank(costs: List[RankedCandidate]) -> List[RankedCandidate]:
    """Rank by known landed cost. Subscription-only offers are excluded.

    Ties/overlaps are NOT broken on headline discount percentage; callers
    must present overlapping candidates together with unknowns visible.
    """
    eligible = [c for c in costs if not c.cost.is_subscription_only]
    return sorted(eligible, key=lambda c: (c.cost.known_low(), c.cost.known_high()))


def ranking_is_robust(costs: List[RankedCandidate]) -> bool:
    """True when the cheapest candidate still wins under every stated unknown.

    The leader wins robustly iff its high bound is <= every rival's low bound.
    An open-ended (inf) high bound is never robust unless it is the only
    candidate.
    """
    eligible = [c for c in costs if not c.cost.is_subscription_only]
    if len(eligible) <= 1:
        return len(eligible) == 1
    ordered = rank(costs)
    leader_high = ordered[0].cost.known_high()
    return all(leader_high <= rival.cost.known_low() for rival in ordered[1:])


@dataclass
class QuantityNormalization:
    """Unit-cost normalization when quantity/size affects comparison."""

    unit: str  # e.g. "each", "oz", "ml", "count"
    unit_cost_low: float = 0.0
    unit_cost_high: float = field(default_factory=lambda: float("inf"))
