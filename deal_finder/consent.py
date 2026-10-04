"""Consent records and cart-action accountability for ai-deal-finder V1.

One stored approval must never become blanket permission. Every cart mutation
must trace to a visible consent record, and every run must end in a recorded
stop. Anonymous-cart coupon testing only; logged-out; pre-payment totals only.

Authoritative rules: CONSENT.md, VISION.md ("Verification Stops Before
Identity Or Purchase"), ACCEPTANCE.md S0 class, fixture CS-001.

DISABLED: the skill never performs or authorizes a cart action. The record
format below is kept as the design for the redesign (a consent record that
binds merchant, attempt and action); nothing here can open a cart test.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class ConsentStatus(str, Enum):
    GRANTED = "granted"
    REVOKED = "revoked"
    ABSENT = "absent"


CONSENT_SCOPE = "anonymous-cart coupon test only"

CART_DISABLED_MESSAGE = "cart-applied checks are disabled until the consent link is redesigned"


@dataclass
class ConsentRecord:
    """All fields required before any cart action (CONSENT.md)."""

    status: ConsentStatus = ConsentStatus.ABSENT
    granted_at: str = ""  # absolute timestamp of when consent was given
    session: str = ""  # session the consent covers
    merchant: str = ""  # merchant each attempt is traceable to
    last_changed_at: str = ""

    def revoke(self, at: str) -> None:
        """Revocation takes effect immediately and is recorded."""
        self.status = ConsentStatus.REVOKED
        self.last_changed_at = at

    def covers(self, merchant: str) -> bool:
        """A missing, expired, or revoked record behaves exactly like absent."""
        return (
            self.status == ConsentStatus.GRANTED
            and bool(self.granted_at)
            and bool(self.session)
            and self.merchant == merchant
        )


@dataclass
class AttemptBudget:
    """Small declared attempt budget; terms-supported combos first."""

    declared_max: int = 3
    used: int = 0

    def remaining(self) -> int:
        return max(0, self.declared_max - self.used)

    def spend(self) -> bool:
        """Consume one attempt. Returns False when the budget is exhausted."""
        if self.remaining() <= 0:
            return False
        self.used += 1
        return True


class StopReason(str, Enum):
    CART_DISABLED = CART_DISABLED_MESSAGE
    COMPLETED = "completed"
    NO_CONSENT = "no consent on record; research-only verification used"
    REVOKED = "consent revoked mid-run; further actions halted"
    BUDGET_EXCEEDED = "attempt budget would be exceeded; research-only fallback"
    LOGIN_REQUIRED = "page requires login; stop before identity"
    CHECKOUT_OR_PAYMENT = "flow reached checkout/payment; stop before purchase"
    PERSONAL_DATA = "flow requests personal data; stop"
    ACCOUNT_MUTATION = "action would mutate account; stop"
    SCARCE_INVENTORY = "action would reserve scarce inventory; stop"
    NO_BROWSER_TOOLS = "browser tools absent; research-only verification used"
    MERCHANT_RULES_PROHIBIT = "merchant rules prohibit testing; no test"
    CLEANUP_BOUNDARY = "cleanup boundary would be exceeded; research-only fallback"


@dataclass
class ActionLog:
    """Per-run log: merchant, actions, budget used vs declared, stop, cleanup."""

    merchant: str
    declared_budget: int = 3
    actions: List[str] = field(default_factory=list)
    budget_used: int = 0
    stop_reason: StopReason = StopReason.COMPLETED
    cleanup_ok: bool = False  # visible empty-cart restoration + session cleanup
    consent_reference: str = ""

    def record(self, action: str) -> None:
        self.actions.append(action)


@dataclass
class CartTestGate:
    """Fail-closed gate for one coupon-test run."""

    consent: ConsentRecord
    budget: AttemptBudget
    merchant: str
    browser_tools_available: bool = True
    merchant_rules_prohibit: bool = False
    merchant_terms_ambiguous: bool = False

    def authorize(self) -> "tuple[bool, StopReason]":
        """Always refuses: cart-applied checks are disabled until the consent
        link is redesigned. The caller falls back to research-only claims.
        CONSENT.md keeps the record format as the design for the redesign.
        """
        return False, StopReason.CART_DISABLED

    def check_revoked(self) -> "tuple[bool, StopReason]":
        """Mid-run revocation check: revocation halts further actions."""
        if self.consent.status != ConsentStatus.GRANTED:
            return False, StopReason.REVOKED
        return True, StopReason.COMPLETED
