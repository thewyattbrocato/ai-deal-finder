"""Stale and deceptive-deal checks for the fail-closed runtime.

Pure functions over the evidence JSON; no network, no model, no credentials.
Each check returns either a refusal (the winner is not trusted, verdict
becomes verify) or a label (shown beside the claim, verdict unchanged).
Anything the evidence does not state stays unknown; nothing is inferred.

Authoritative rules: DECISION_TABLE.md downgrade triggers and language bans,
LANDED_COST.md (delayed value and reference prices never reduce the total).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

CLOCK_SKEW = timedelta(minutes=5)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
URL_SECRET = re.compile(
    r"://[^/\s:@]+:[^/\s@]*@|[?&](?:token|password|passwd|sessionid|session|api_?key|auth|email)=",
    re.IGNORECASE,
)


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    return parsed.astimezone(timezone.utc)


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = int(char)
        if index % 2:
            number = number * 2 - 9 if number > 4 else number * 2
        total += number
    return total % 10 == 0


def private_value(text: str) -> bool:
    """True when a string value looks like an email, SSN, card number or URL secret."""
    if EMAIL.search(text) or SSN.search(text) or URL_SECRET.search(text):
        return True
    return any(
        _luhn(digits)
        for digits in (re.sub(r"\D", "", match) for match in CARD.findall(text))
        if 13 <= len(digits) <= 19
    )


def _age_problem(observed_at: str, now: datetime, window: timedelta, what: str) -> str | None:
    observed = parse_time(observed_at)
    if observed - now > CLOCK_SKEW:
        return f"{what} is dated in the future ({observed_at}); its age cannot be trusted"
    if now - observed > window:
        hours = int(window.total_seconds() // 3600)
        return f"{what} was observed {observed_at}, older than the stated {hours}-hour freshness window"
    return None


def _refusals(candidate: dict[str, Any], now: datetime, window: timedelta | None) -> list[tuple[str, str]]:
    """Reasons the candidate must not be trusted, each with the one check that resolves it."""
    found: list[tuple[str, str]] = []
    if window is not None:
        problem = _age_problem(candidate["observed_at"], now, window, "price evidence")
        if problem:
            found.append((problem, "Recheck the price and stock on the merchant page now, then re-run."))
    coupon = candidate.get("coupon") if isinstance(candidate.get("coupon"), dict) else None
    counted = bool(coupon) and bool(candidate.get("immediate_discount")) and str(candidate["immediate_discount"]) != "0"
    if coupon and counted:
        if window is not None:
            if not coupon.get("observed_at"):
                found.append(
                    (
                        "coupon discount is counted but its observation time is missing",
                        "Re-test the code in a logged-out anonymous cart (with consent) and record the time.",
                    )
                )
            else:
                problem = _age_problem(coupon["observed_at"], now, window, "coupon evidence")
                if problem:
                    found.append((problem, "Re-test the code in a logged-out anonymous cart (with consent), then re-run."))
        if coupon.get("conditions_unstated"):
            found.append(
                (
                    "coupon discount depends on a condition the page did not state",
                    "Find the code's full terms on the merchant page, or treat the coupon as not counted.",
                )
            )
    for signal in candidate.get("urgency_signals") or []:
        if isinstance(signal, dict) and signal.get("repeats_on_reload"):
            found.append(
                (
                    f"urgency text '{signal.get('text', '')}' came back after a reload, so it is not a real deadline",
                    "Ignore the clock, reload once more, and confirm the price on the merchant page before buying.",
                )
            )
            break
    if candidate.get("seller_verified") is False or candidate.get("seller_red_flags"):
        found.append(
            (
                "seller is unverified or has recorded red flags",
                f"Check {candidate['seller']} on an independent source (seller rating, return policy) before buying.",
            )
        )
    if candidate.get("affiliate_link") or candidate.get("sponsored"):
        found.append(
            (
                "leading offer is affiliate-linked or sponsored, so its placement may follow commission",
                "Confirm the price on the merchant's own page and compare against an unsponsored offer.",
            )
        )
    return found


def _labels(candidate: dict[str, Any]) -> list[dict[str, str]]:
    """Notes shown beside the claim they qualify; they never change the verdict by themselves."""
    cid = candidate["id"]
    out: list[dict[str, str]] = []
    for signal in candidate.get("urgency_signals") or []:
        if isinstance(signal, dict):
            out.append(
                {
                    "kind": "urgency",
                    "candidate": cid,
                    "text": f"Urgency text '{signal.get('text', '')}' was seen; it is not evidence of stock or a deadline and was not used.",
                }
            )
    reference = candidate.get("reference_price")
    if isinstance(reference, dict) and not reference.get("dated_history"):
        out.append(
            {
                "kind": "reference-price",
                "candidate": cid,
                "text": "A 'was' price is shown with no dated price history; it is not treated as a saving and is never subtracted.",
            }
        )
    coupon = candidate.get("coupon") if isinstance(candidate.get("coupon"), dict) else None
    if coupon and coupon.get("conditions_unstated"):
        out.append(
            {
                "kind": "coupon-conditions",
                "candidate": cid,
                "text": "The code's conditions are not stated on the page; they stay unknown and the code is not counted.",
            }
        )
    if candidate.get("seller_verified") is None and candidate["seller"] != candidate["fulfilled_by"]:
        out.append(
            {
                "kind": "seller",
                "candidate": cid,
                "text": "Seller and fulfillment party differ and the seller was not checked; nothing is claimed about the seller.",
            }
        )
    if candidate.get("affiliate_link") or candidate.get("sponsored"):
        out.append(
            {
                "kind": "affiliate",
                "candidate": cid,
                "text": "This offer is affiliate-linked or sponsored; ranking uses landed cost only.",
            }
        )
    return out


def trust_review(
    winner: dict[str, Any],
    candidates: list[dict[str, Any]],
    now: datetime,
    window: timedelta | None,
) -> tuple[list[tuple[str, str]], list[dict[str, str]]]:
    """(refusals for the winner, labels for every candidate seen)."""
    labels = _labels(winner)
    for other in candidates:
        if other is not winner:
            labels.extend(item for item in _labels(other) if item["kind"] == "affiliate")
    return _refusals(winner, now, window), labels
