"""Output contract for the skill's "similar products and their offers" mode.

`validate(answer, now=None)` checks one answer JSON against SIMILAR_OUTPUT.md and
returns violation messages (empty = the answer follows the contract); `now`, when
given, is the checker's clock, so a finish time ahead of it is caught.
`render(answer)` prints the markdown answer in the template's fixed order. Pure
functions: no network, no model, no credentials. Unit prices are computed with
deal_finder/unit_price.py, never here.

Authoritative rules: SIMILAR_OUTPUT.md, SKILL.md ("Similar products and their
offers"), VISION.md (evidence states, no affiliate links), README.md ("What the
evidence rules mean": a seen code is never a lower price).
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from . import unit_price as units
from .decision import BANNED_PHRASES
from .deception import parse_time
from .evidence import EvidenceState

CONTRACT = "similar-v3"
CODE_LABEL = "not tried, may not work"
SIZE_NOT_STATED = "not comparable: size not stated"
NO_UNIT = "none"  # the kind is sold one item at a time (shoes, earbuds): no size, no unit price
MATERIAL = Decimal("0.02")  # a gap under 2% of the shopper's price is no meaningful saving
MAX_PAGES = 10
STATES = {state.value for state in EvidenceState}
OFFER_STATES = {"retailer-stated", "unverified", "rejected"}
OFFER_KINDS = {"code", "sale", "subscribe", "autoship", "signup", "shipping-threshold", "bundle", "bulk", "other"}
OFFER_WHERE = {"product page", "site banner", "store page", "pop-up"}
GATES = {"none", "email", "sms", "first-order", "subscription", "member", "store-card", "app", "other"}
STATUSES = {"compared", "flagged", "excluded"}
CHECKS = {"same", "inherited", "differs", "unknown", "not-read"}
SAME = {"same", "inherited"}  # inherited: the same product's page does not print it, so the shopper's value carries
ATTRIBUTE_SOURCES = {"page", "shopper", "assumed"}
PAGE_TEXT = "page-text"
READS = {PAGE_TEXT, "raw-html", "reader-summary", "listing-page", "search-snippet"}
READ_WORDS = {
    PAGE_TEXT: "the page's own text",
    "raw-html": "the page's raw HTML, not the text a browser shows",
    "reader-summary": "a page reader's summary",
    "listing-page": "a store listing, not the product's own page",
    "search-snippet": "a search result's text",
    "shopper": "you",
}
AVAILABILITY = {"in-stock", "out-of-stock", "not-stated"}
CURRENCY_NOT_STATED = "not stated"  # the page prints a price with no currency: flagged, never converted
STATUS_ORDER = {"compared": 0, "flagged": 1, "excluded": 2}
# Stores SKILL.md names as refusing an agent's reader: they may be listed unopened, without spending a page.
KNOWN_BLOCKED = ("amazon.com", "walmart.com", "bestbuy.com")
UNITS = set(units.FAMILY) | {NO_UNIT}
CODED = re.compile(r"\b(?:with|use|using|enter|apply)\s+(?:the\s+)?code\b|\bcode\s+applied\b", re.IGNORECASE)
FROM_OR_RANGE = re.compile(r"\bfrom\s*:?\s*\$?\s*\d|\d\s*(?:-|–|—|\bto\b)\s*\$\s*\d", re.IGNORECASE)
TRACKING_PARAM = re.compile(
    r"^(utm_.*|_gsid|gclid|gbraid|wbraid|fbclid|msclkid|mc_[a-z]+|_ga|ref|ref_|tag|aff.*|affiliate.*|irclickid|clickid|srsltid)$",
    re.IGNORECASE,
)
EXTRA_BANS = ("best deal", "great deal", "hurry", "act now", "don't miss", "lowest price guaranteed")
WORDING = re.compile(r"\b(" + "|".join(re.escape(p) for p in BANNED_PHRASES + EXTRA_BANS) + r")\b", re.IGNORECASE)
# Page text and page-copied identities may contain any words; only the
# agent's own wording is held to the language bans, outside the page words it quotes.
NOT_AGENT_WORDS = {"quote", "url", "code", "name", "store", "said", "expires"}
QUOTED = re.compile(r"(?<![A-Za-z])'(?:[^']|'(?=[A-Za-z]))*?'(?![A-Za-z])|\"[^\"]*\"|“[^”]*”|‘[^’]*’")


def _money(value: Any) -> Decimal | None:
    """A non-negative decimal written as a string, as in "19.50"; anything else is None."""
    if not isinstance(value, str):
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None


def _numbers(text: str) -> set[Decimal]:
    return {Decimal(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text or "")}


def _time(value: Any) -> bool:
    if not isinstance(value, str) or not re.search(r"(Z|[+-]\d\d:\d\d)$", value):
        return False
    try:
        parse_time(value)
    except ValueError:
        return False
    return True


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _label(item: dict[str, Any], fallback: str) -> str:
    """Name an item by its id in messages, so each problem points at the item that is wrong."""
    return item["id"] if _text(item.get("id")) else fallback


def url_problem(url: Any) -> str:
    """Empty when the URL is a plain http(s) link with no tracking or affiliate parameter."""
    if not _text(url) or urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).hostname:
        return "is not an http(s) link"
    dirty = [key for key, _ in parse_qsl(urlsplit(url).query) if TRACKING_PARAM.match(key)]
    return f"keeps tracking or affiliate parameters ({', '.join(dirty)})" if dirty else ""


def _page(url: str) -> str:
    """One page per product: a store's own `?variant=` link for an option is the page it belongs to."""
    parts = urlsplit(url)
    query = "&".join(f"{k}={v}" for k, v in parse_qsl(parts.query) if k != "variant")
    return parts._replace(query=query, fragment="").geturl()


def _host(url: Any) -> str:
    host = (urlsplit(url).hostname or "") if _text(url) else ""
    return host[4:] if host.startswith("www.") else host


def _known_blocked(url: Any) -> bool:
    host = _host(url)
    return any(host == store or host.endswith("." + store) for store in KNOWN_BLOCKED)


def code_price(shelf: Decimal, offer: dict[str, Any]) -> Decimal | None:
    """Shelf price if this printed code applied, or None when the page did not state it in numbers."""
    discount = offer.get("discount") if isinstance(offer.get("discount"), dict) else {}
    minimum = _money(offer.get("min_spend")) if offer.get("min_spend") is not None else Decimal(0)
    if minimum is None or shelf < minimum:
        return None
    if _money(discount.get("percent")) is not None:
        cut = shelf * _money(discount["percent"]) / 100
    elif _money(discount.get("amount")) is not None:
        cut = _money(discount["amount"])
    else:
        return None
    return max(shelf - cut, Decimal(0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _code_offers(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Codes that may form the 'if a printed code applies' line: printed by the store, read in its text, ungated."""
    return [
        offer
        for offer in item.get("offers") or []
        if isinstance(offer, dict)
        and offer.get("kind") == "code"
        and offer.get("state") == "retailer-stated"
        and offer.get("read") == PAGE_TEXT
        and offer.get("gate") == "none"
    ]


def _shelf(item: dict[str, Any]) -> Decimal | None:
    price = item.get("shelf_price")
    return _money(price.get("amount")) if isinstance(price, dict) else None


def _size(item: dict[str, Any]) -> units.Size | str | None:
    """The item's one printed size; a string saying why it cannot be used; None when no size is given."""
    size = item.get("size")
    if size is None:
        return None
    if not (isinstance(size, dict) and _text(size.get("text")) and _text(size.get("quote"))):
        return "must quote the page's own words (quote) and state one size (text); never guess a size (use null)"
    parsed, quoted = units.parse_size_checked(size["text"]), units.parse_size_checked(size["quote"])
    if not isinstance(parsed, units.Size):
        reason = f" ({parsed.reason})" if parsed else ""
        return f"'{size['text']}' is not one size{reason}; write it with {units.ACCEPTED_UNITS}"
    if isinstance(quoted, units.SizeRefusal):
        return f"the page's words '{size['quote']}' give no single size ({quoted.reason}); never guess a size"
    if quoted is None or abs(quoted.base_total() - parsed.base_total()) > parsed.base_total() * units.CONSISTENT_WITHIN:
        return f"size '{size['text']}' is not the size in the page's words '{size['quote']}'; never guess a size"
    return parsed


def _confirmed_size(item: dict[str, Any]) -> units.Size | None:
    """A size that may decide a comparison: read in the page's own text (or given by the shopper)."""
    size = _size(item)
    read = (item.get("size") or {}).get("read") if isinstance(item.get("size"), dict) else None
    return size if isinstance(size, units.Size) and read in (PAGE_TEXT, "shopper") else None


def _why_not_counted(item: dict[str, Any], currency: str) -> list[tuple[str, str]]:
    """Why this item's price cannot enter a lowest line, as (code, the shopper's words); empty = it can."""
    reasons = []
    price = item.get("shelf_price") if isinstance(item.get("shelf_price"), dict) else {}
    if _shelf(item) is None:
        return [("price", "no price could be read on its page")]
    if price.get("currency") == CURRENCY_NOT_STATED:
        reasons.append(("currency-unstated", "its page prints no currency; prices are never converted"))
    elif price.get("currency") != currency:
        reasons.append(("currency", f"priced in {price.get('currency')}; prices are never converted"))
    if price.get("state") != "observed-now":
        reasons.append(("state", "its price was not read on its own page during this run"))
    if price.get("read") != PAGE_TEXT:
        words = READ_WORDS.get(price.get("read"), "a read it does not state")
        reasons.append(("read", f"its price comes from {words}, not confirmed in the page's own text"))
    if FROM_OR_RANGE.search(price.get("quote") or ""):
        reasons.append(("range", "its page prints a 'from' price or a range, not one price for one size"))
    if CODED.search(price.get("quote") or ""):
        reasons.append(("coded", "its quoted price is shown with a code applied, which is not a shelf price"))
    stock = item.get("availability") if isinstance(item.get("availability"), dict) else {}
    if stock.get("state") == "out-of-stock" and stock.get("read") == PAGE_TEXT:
        reasons.append(("out", f"out of stock on its page: \"{stock.get('quote', '')}\""))
    elif stock.get("state") == "out-of-stock":
        words = READ_WORDS.get(stock.get("read"), "a read it does not state")
        reasons.append(("out", f"out of stock according to {words} (\"{stock.get('quote', '')}\"), "
                               "not confirmed in the page's own text"))
    elif stock.get("state") == "not-stated":
        reasons.append(("stock-unstated", "stock not stated on its page"))
    elif stock.get("read") != PAGE_TEXT:
        words = READ_WORDS.get(stock.get("read"), "a read it does not state")
        reasons.append(("stock-read", f"its stock comes from {words}, not confirmed in the page's own text"))
    return reasons


def reference_reason(answer: dict[str, Any]) -> str:
    """Why the shopper's own product is not counted in the lowest lines; empty when it is."""
    reference = answer.get("reference") or {}
    if reference.get("from") == "description":
        return "described by you; no page was read"
    reasons = _why_not_counted(reference, (answer.get("request") or {}).get("currency"))
    return reasons[0][1] if reasons else ""


def _counted(answer: dict[str, Any]) -> list[dict[str, Any]]:
    """Items the lowest lines may name: compared, priced and in stock in the page's own text, in the asked currency."""
    currency = (answer.get("request") or {}).get("currency")
    reference = answer.get("reference") or {}
    pool = [] if reference.get("from") == "description" else [reference]
    pool += [c for c in answer.get("candidates") or [] if isinstance(c, dict) and c.get("status") == "compared"]
    return [item for item in pool if not _why_not_counted(item, currency)]


def _equal(mine: units.Size, theirs: units.Size) -> bool:
    return mine.family == theirs.family and (
        abs(mine.base_total() - theirs.base_total()) <= mine.base_total() * units.CONSISTENT_WITHIN
    )


def _same_quantity(item: dict[str, Any], answer: dict[str, Any]) -> bool | None:
    """True when the item is the same size as the shopper's; None when either size is unknown."""
    if answer.get("unit") == NO_UNIT:
        return True
    mine, theirs = _confirmed_size(answer.get("reference") or {}), _confirmed_size(item)
    if mine is None or theirs is None:
        return None
    return _equal(mine, theirs)


def _unit_amount(item: dict[str, Any], answer: dict[str, Any]) -> Decimal | None:
    unit = item.get("unit_price")
    if not isinstance(unit, dict) or unit.get("currency") != (answer.get("request") or {}).get("currency"):
        return None
    try:
        if units.normalize_unit(str(unit.get("per"))) != answer.get("unit"):
            return None
    except ValueError:
        return None
    return _money(unit.get("amount"))


def _unit_counted(answer: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in _counted(answer)
        if _unit_amount(item, answer) is not None and _confirmed_size(item) is not None
    ]


def _lower_not_counted(answer: dict[str, Any], bar: Decimal | None, amount, keep) -> list[str]:
    """Ids of candidates not counted whose amount is under the bar: each must be named with why."""
    if bar is None:
        return []
    counted = {id(item) for item in _counted(answer)}
    return [
        c.get("id")
        for c in answer.get("candidates") or []
        if isinstance(c, dict) and id(c) not in counted and amount(c) is not None and amount(c) < bar and keep(c)
    ]


def _walk_words(value: Any, key: str = "") -> list[str]:
    if key in NOT_AGENT_WORDS:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in _walk_words(v, k)]
    if isinstance(value, list):
        return [s for v in value for s in _walk_words(v, key)]
    return []


def _check_read(where: str, value: Any, extra: tuple[str, ...] = ()) -> list[str]:
    allowed = sorted(READS | set(extra))
    return [] if value in allowed else [f"{where}.read must say how it was read, one of {allowed}"]


def _check_offer(where: str, offer: Any) -> list[str]:
    if not isinstance(offer, dict):
        return [f"{where} must be an object"]
    problems = []
    if offer.get("kind") not in OFFER_KINDS:
        problems.append(f"{where}.kind must be one of {sorted(OFFER_KINDS)}; anything else is 'other' with the page's words")
    if not _text(offer.get("quote")):
        problems.append(f"{where} needs the page's own words in quote")
    if offer.get("where") not in OFFER_WHERE:
        problems.append(f"{where}.where must be one of {sorted(OFFER_WHERE)}; codes from coupon sites are not listed")
    if offer.get("state") not in OFFER_STATES:
        problems.append(f"{where}.state must be one of {sorted(OFFER_STATES)}; nothing was tried in a cart")
    if offer.get("gate") not in GATES:
        problems.append(f"{where}.gate must be one of {sorted(GATES)}")
    problems.extend(_check_read(where, offer.get("read")))
    if offer.get("read") == "search-snippet" and offer.get("state") != "unverified":
        problems.append(f"{where} comes from a search result's text, so its state is 'unverified'")
    if not _time(offer.get("seen_at")):
        problems.append(f"{where}.seen_at must be an absolute timestamp from date -u")
    if "expires" in offer and not _text(offer["expires"]):
        problems.append(f"{where}.expires must quote the page's words for when it ends, or be left out")
    if offer.get("kind") == "code":
        code = offer.get("code")
        if not _text(code) or code.lower() not in (offer.get("quote") or "").lower():
            problems.append(f"{where} code must appear in the page's own words (quote)")
    if "discount" in offer and not (
        isinstance(offer["discount"], dict)
        and (_money(offer["discount"].get("percent")) is not None or _money(offer["discount"].get("amount")) is not None)
    ):
        problems.append(f"{where}.discount must be {{\"percent\": \"20\"}} or {{\"amount\": \"5.00\"}} as printed")
    return problems


def _check_item(where: str, item: Any, names: list[str], musts: set[str], currency: str, reference: bool) -> list[str]:
    if not isinstance(item, dict):
        return [f"{where} must be an object"]
    problems = []
    described = reference and item.get("from") == "description"
    for field in ("id", "name", "store"):
        if not _text(item.get(field)):
            problems.append(f"{where}.{field} is required")
    if not described:
        problem = url_problem(item.get("url"))
        if problem:
            problems.append(f"{where} is unsourced: url {problem}")
        if not _time(item.get("checked_at")):
            problems.append(f"{where} is unsourced: checked_at must be an absolute timestamp from date -u")
        stock = item.get("availability")
        if not isinstance(stock, dict) or stock.get("state") not in AVAILABILITY:
            problems.append(f"{where}.availability.state must be one of {sorted(AVAILABILITY)}, as its page prints it")
        else:
            if stock["state"] != "not-stated" and not _text(stock.get("quote")):
                problems.append(f"{where}.availability needs the page's own words in quote")
            problems.extend(_check_read(f"{where}.availability", stock.get("read")))
    if not reference and not _text(item.get("found_via")):
        problems.append(f"{where}.found_via must say how it was found")

    price = item.get("shelf_price")
    if price is None and not reference:
        problems.append(f"{where} is unsourced: shelf_price is required")
    elif not isinstance(price, dict) and price is not None:
        problems.append(f"{where}.shelf_price must be an object")
    elif isinstance(price, dict):
        amount = _money(price.get("amount"))
        if amount is None:
            problems.append(f"{where}.shelf_price.amount must be a decimal string")
        elif amount not in _numbers(price.get("quote") or ""):
            problems.append(
                f"{where}.shelf_price.amount must be the price the page printed (quote); "
                "a code, subscribe or sign-up price never lowers it"
            )
        if price.get("state") not in STATES:
            problems.append(f"{where}.shelf_price.state must be an evidence state")
        if not _text(price.get("currency")):
            problems.append(f"{where}.shelf_price.currency is required")
        problems.extend(_check_read(f"{where}.shelf_price", price.get("read")))
        if price.get("read") == "search-snippet":
            problems.append(f"{where}.shelf_price comes from a search result: a snippet price never enters the answer")

    size = item.get("size")
    if size is not None:
        found = _size(item)
        if isinstance(found, str):
            problems.append(f"{where}.size: {found}")
        if isinstance(size, dict):
            problems.extend(_check_read(f"{where}.size", size.get("read"), ("shopper",) if reference else ()))

    offers = item.get("offers")
    if not isinstance(offers, list):
        problems.append(f"{where}.offers must be a list (empty when the page printed none)")
    else:
        for index, offer in enumerate(offers):
            problems.extend(_check_offer(f"{where}.offers[{index}]", offer))

    if reference:
        if item.get("from") not in ("page", "description"):
            problems.append(f"{where}.from must be 'page' or 'description'")
        return problems
    if "same_product" in item and not isinstance(item["same_product"], bool):
        problems.append(f"{where}.same_product must be true or false")
    status = item.get("status")
    if status not in STATUSES:
        problems.append(f"{where}.status must be one of {sorted(STATUSES)}")
    if status in ("flagged", "excluded") and not _text(item.get("status_reason")):
        problems.append(f"{where}.status_reason must say why it is {status}")
    checks = item.get("checks") if isinstance(item.get("checks"), dict) else {}
    for name in names:
        if checks.get(name) not in CHECKS:
            problems.append(f"{where}.checks['{name}'] must be one of {sorted(CHECKS)}")
    inherited = [name for name in names if checks.get(name) == "inherited"]
    if inherited and item.get("same_product") is not True:
        problems.append(f"{where}.checks {inherited} are 'inherited', which only the same product at another store "
                        "may use; a different product's page must show it (or it is 'unknown')")
    fails_must = any(checks.get(name) == "differs" for name in musts)
    if fails_must and status != "excluded":
        problems.append(f"{where} fails a must-have attribute and must be excluded")
    elif any(checks.get(name) in ("unknown", "not-read") for name in musts) and status == "compared":
        problems.append(f"{where} has a must-have its page does not show (or you did not read); flag it, do not compare it")
    reasons = dict(_why_not_counted(item, currency)) if isinstance(price, dict) else {}
    stock = item.get("availability") if isinstance(item.get("availability"), dict) else {}
    other_currency = "currency" in reasons
    if other_currency and status != "excluded":
        problems.append(f"{where} is in another currency; exclude it (prices are never converted)")
    if stock.get("state") == "out-of-stock":
        if stock.get("read") == PAGE_TEXT and status != "excluded":
            problems.append(f"{where} is out of stock on its page (\"{stock.get('quote', '')}\"); exclude it")
        elif stock.get("read") != PAGE_TEXT and status != "flagged" and not (fails_must or other_currency):
            problems.append(
                f"{where}'s out-of-stock state comes from {READ_WORDS.get(stock.get('read'), 'an unstated read')}; "
                "confirm it in the page's text in a browser or flag it"
            )
    if status == "compared":
        if "state" in reasons:
            problems.append(f"{where} is compared but its shelf price was not read on its own page now")
        if "read" in reasons:
            problems.append(f"{where} is compared but {reasons['read']}; confirm the price in the page's text in "
                            "a browser or flag it")
        if "range" in reasons:
            problems.append(f"{where} is compared but {reasons['range']}; open the size you compare and quote "
                            "that price, or flag it")
        if "stock-read" in reasons:
            problems.append(f"{where} is compared but {reasons['stock-read']}; confirm it or flag it")
        if "stock-unstated" in reasons:
            problems.append(f"{where} is compared but its page states no stock (no stock words and no buy button "
                            "for the option priced); flag it: stock not stated never names a lowest line")
        if "currency-unstated" in reasons:
            problems.append(f"{where} is compared but {reasons['currency-unstated']}; flag it")
        if "coded" in reasons:
            problems.append(f"{where} is compared but {reasons['coded']}; quote the price without the code, "
                            "or flag it")
    for field, label in (("similar_because", "similar-because reason"), ("not_comparable", "not-comparable reason")):
        reasons_given = item.get(field)
        if not isinstance(reasons_given, list) or not reasons_given or not all(_text(r) for r in reasons_given):
            problems.append(f"{where} is missing a {label} ({field} must be a non-empty list)")
    return problems


def _check_unit_prices(answer: dict[str, Any], items: list[tuple[str, dict[str, Any]]]) -> list[str]:
    unit = answer.get("unit")
    if unit not in UNITS:
        return [
            f"unit must be one of {sorted(UNITS)}: the one unit for the whole answer (US coffee: oz), "
            "or 'none' when the kind is sold one item at a time (shoes, earbuds)"
        ]
    problems = []
    for label, item in items:
        given, size = item.get("unit_price"), _size(item)
        if unit == NO_UNIT:
            if item.get("size") is not None:
                problems.append(f"{label}.size must be null when unit is 'none'; if its page prints a size or a "
                                "count, the answer has a unit: use it")
            if given is not None:
                problems.append(f"{label}.unit_price must be left out when unit is 'none' (no unit applies)")
            continue
        words = isinstance(given, str) and given.startswith("not comparable: ") and len(given) > 16
        if isinstance(size, str):
            continue  # the size itself is reported broken
        if size is None:
            if isinstance(given, dict):
                problems.append(f"{label}.unit_price needs a size printed on its page; leave it out or write "
                                f"'{SIZE_NOT_STATED}'")
            elif given is not None and not words:
                problems.append(f"{label}.unit_price must be left out or 'not comparable: <reason>'")
            continue
        if units.FAMILY[size.unit] != units.FAMILY[unit]:
            if not words:
                problems.append(f"{label}.unit_price: its size is a {size.family} and the answer's unit is "
                                f"'{unit}'; write 'not comparable: different units'")
            continue
        price = item.get("shelf_price") if isinstance(item.get("shelf_price"), dict) else {}
        if price.get("currency") == CURRENCY_NOT_STATED:
            if not words:
                problems.append(f"{label}.unit_price: its page prints no currency; write 'not comparable: "
                                "currency not stated'")
            continue
        try:
            value = units.unit_price(units.Price.of(price["amount"], price["currency"]), size, unit)
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue  # the shelf price itself is reported broken
        expected = value.display().split()[0]
        if isinstance(given, dict):
            per = given.get("per")
            try:
                same_unit = units.normalize_unit(str(per)) == unit
            except ValueError:
                same_unit = False
            if not same_unit:
                problems.append(f"{label}.unit_price.per must be the answer's unit '{unit}', not {per!r}")
            elif _money(given.get("amount")) != Decimal(expected) or given.get("currency") != price.get("currency"):
                problems.append(
                    f"{label}.unit_price must be shelf price / printed size: {expected} {price.get('currency')} "
                    f"per {unit} (2 decimals, 3 decimals under 1.00, half up; deal_finder/unit_price.py)"
                )
        elif price.get("currency") == (answer.get("request") or {}).get("currency"):
            problems.append(
                f"{label}.unit_price must be {{\"amount\": \"{expected}\", \"currency\": \"{price.get('currency')}\", "
                f"\"per\": \"{unit}\"}}: its size is printed, so its unit price is shown"
            )
        elif not words:
            problems.append(f"{label}.unit_price must be an object or 'not comparable: <reason>'")
    return problems


def _check_lower(answer: dict[str, Any], key: str, required: list[str], ids: dict[str, Any]) -> list[str]:
    entries = (answer.get("lowest") or {}).get(key)
    if not isinstance(entries, list):
        return [f"lowest.{key} must be a list (empty when nothing cheaper was left out)"]
    counted = {id(item) for item in _counted(answer)}
    problems, listed = [], set()
    for index, entry in enumerate(entries):
        item = ids.get(entry.get("id")) if isinstance(entry, dict) else None
        if item is None or not _text(entry.get("why")):
            problems.append(f"lowest.{key}[{index}] needs the id of an item in this answer and why it is not counted")
        elif id(item) in counted:
            problems.append(f"lowest.{key}[{index}] names {entry['id']}, which is counted; list only items not counted")
        elif key == "shelf_lower_not_counted" and _same_quantity(item, answer) is False:
            problems.append(f"lowest.{key}[{index}] names {entry['id']}, which is {item['size']['text']}, not your "
                            "size; a different size is named on the per-unit line only")
        else:
            listed.add(entry["id"])
    missing = [item_id for item_id in required if item_id not in listed]
    if missing:
        problems.append(f"lowest.{key} must name each cheaper item that is not counted (flagged or excluded), "
                        f"with why: {missing}")
    return problems


def _check_if_size(answer: dict[str, Any], if_size: Any, ids: dict[str, Any]) -> list[str]:
    """The shelf answer for one printed size, when your page prints none and no shopper could be asked."""
    if if_size is None:
        return []
    unit = answer.get("unit")
    if unit == NO_UNIT or _confirmed_size(answer.get("reference") or {}) is not None:
        return ["lowest.if_size is only for a product whose page prints no size (leave it out)"]
    size = units.parse_size_checked(if_size.get("size")) if isinstance(if_size, dict) else None
    if not isinstance(size, units.Size) or size.family != units.FAMILY.get(unit) or not _text(if_size.get("why")):
        return [f"lowest.if_size needs size (one size, in the answer's unit '{unit}') and why (where that size is "
                "printed, such as the store's other bags)"]
    pool = [i for i in _counted(answer) if _confirmed_size(i) is not None and _equal(size, _confirmed_size(i))]
    if not pool:
        return [f"lowest.if_size: no counted item is {if_size['size']}; leave it out"]
    floor = min(_shelf(i) for i in pool)
    chosen = ids.get(if_size.get("id"))
    if chosen is None or not any(chosen is i for i in pool) or _money(if_size.get("amount")) != floor \
            or _shelf(chosen) != floor:
        return [f"lowest.if_size must be the lowest counted shelf price for {if_size['size']} ({floor}), with its id"]
    return []


def _check_lowest(answer: dict[str, Any]) -> list[str]:
    lowest = answer.get("lowest")
    if not isinstance(lowest, dict):
        return ["lowest is required (shelf, shelf_lower_not_counted, unit, unit_lower_not_counted, if_code)"]
    problems = []
    currency = (answer.get("request") or {}).get("currency")
    reference = answer.get("reference") or {}
    ids = {item.get("id"): item for item in [reference] + list(answer.get("candidates") or []) if isinstance(item, dict)}
    counted = _counted(answer)
    unit = answer.get("unit")

    mine = _confirmed_size(reference)
    pool = [item for item in counted if _same_quantity(item, answer) is True]
    shelf = lowest.get("shelf")
    if pool:
        floor = min(_shelf(item) for item in pool)
        chosen = ids.get(shelf.get("id")) if isinstance(shelf, dict) else None
        if chosen is not None and any(chosen is item for item in counted) and _same_quantity(chosen, answer) is False:
            problems.append(
                f"lowest.shelf compares only items the same size as yours ({reference['size']['text']}); "
                f"{shelf['id']} is {chosen['size']['text']}: it is compared per {unit} on the unit line"
            )
        elif chosen is None or not any(chosen is item for item in pool) or _money(shelf.get("amount")) != _shelf(chosen) \
                or _shelf(chosen) != floor:
            problems.append(
                f"lowest.shelf must be the lowest counted shelf price at your size ({floor}), exactly as its page "
                "printed it; a printed code never lowers a price"
            )
    elif shelf is not None:
        if unit != NO_UNIT and mine is None:
            why = "your product's size is not printed in its page's text: ask the shopper for it"
        elif not counted:
            why = "no item's price could be counted"
        else:
            why = f"no counted item is the same size as yours; compare them per {unit}"
        problems.append(f"lowest.shelf must be null: {why}")
    problems.extend(_check_if_size(answer, lowest.get("if_size"), ids))
    in_currency = lambda c: _shelf(c) if isinstance(c.get("shelf_price"), dict) and \
        c["shelf_price"].get("currency") == currency else None
    bar = min((_shelf(item) for item in pool), default=None)
    if bar is None and reference.get("from") == "page" and (unit == NO_UNIT or mine is not None):
        bar = in_currency(reference)  # nothing counted at your size: cheaper than yours is still named
    required = _lower_not_counted(answer, bar, in_currency, lambda c: _same_quantity(c, answer) is not False)
    problems.extend(_check_lower(answer, "shelf_lower_not_counted", required, ids))

    by_unit = _unit_counted(answer)
    floor_u = min((_unit_amount(item, answer) for item in by_unit), default=None)
    unit_amount = lambda c: _unit_amount(c, answer)
    lower_u = _lower_not_counted(answer, floor_u, unit_amount, lambda c: not any(c is item for item in by_unit))
    needed = bool(by_unit) and (len(by_unit) > 1 or by_unit[0] is not reference or bool(lower_u))
    line = lowest.get("unit")
    if needed:
        chosen = ids.get(line.get("id")) if isinstance(line, dict) else None
        if chosen is None or not any(chosen is item for item in by_unit) or _money(line.get("amount")) != floor_u \
                or unit_amount(chosen) != floor_u:
            problems.append(
                f"lowest.unit must be the lowest unit price among counted items with a printed size ({floor_u} per "
                f"{unit})"
            )
    elif line is not None:
        problems.append("lowest.unit must be null: no counted item other than yours has a unit price from a "
                        "printed size, and nothing cheaper per unit was left out")
    problems.extend(_check_lower(answer, "unit_lower_not_counted", lower_u if needed else [], ids))

    if_code = lowest.get("if_code")
    priced_codes = [(code_price(_shelf(item), offer), item, offer) for item in counted for offer in _code_offers(item)]
    options = [option for option in priced_codes if option[0] is not None]
    if if_code is None:
        if options:
            problems.append("lowest.if_code is missing although a counted item prints an ungated code with its "
                            "discount in numbers")
        if not _text(lowest.get("if_code_none")):
            problems.append("lowest.if_code_none must say why there is no code line")
        return problems
    if not isinstance(if_code, dict) or if_code.get("label") != CODE_LABEL:
        problems.append(f"lowest.if_code must carry \"label\": \"{CODE_LABEL}\"")
        return problems
    match = [o for o in options if o[1].get("id") == if_code.get("id") and o[2].get("code") == if_code.get("code")]
    item = ids.get(if_code.get("id")) or {}
    used = next((o for o in item.get("offers") or [] if isinstance(o, dict) and o.get("code") == if_code.get("code")), {})
    if used and used.get("gate") != "none":
        problems.append(
            "lowest.if_code uses a gated code; a code behind email, SMS, first order, subscription "
            "or membership is labelled gated and never forms this line"
        )
    elif not match:
        problems.append(
            "lowest.if_code must use an ungated code the store printed on a counted item, read in the page's own "
            "text, with its discount stated in numbers (offer.discount)"
        )
    elif _money(if_code.get("amount")) != match[0][0] or match[0][0] != min(o[0] for o in options):
        problems.append(
            f"lowest.if_code.amount must be the lowest shelf price with one printed code applied "
            f"({min(o[0] for o in options)}); codes never stack"
        )
    return problems


def _check_times(answer: dict[str, Any], items: list[tuple[str, dict[str, Any]]], now: datetime | None) -> list[str]:
    run = answer.get("run") if isinstance(answer.get("run"), dict) else {}
    if not (_time(run.get("started_at")) and _time(run.get("finished_at"))):
        return ["run.started_at and run.finished_at must be absolute timestamps from date -u"]
    start, end = parse_time(run["started_at"]), parse_time(run["finished_at"])
    if end < start:
        return ["run.finished_at is before run.started_at"]
    problems = []
    if now is not None and end > now:
        problems.append(f"run.finished_at ({run['finished_at']}) is later than now; copy times from date -u, "
                        "never estimate them")
    stamps = []
    for label, item in items:
        stamps.append((f"{label}.checked_at", item.get("checked_at")))
        for index, offer in enumerate(item.get("offers") or []):
            if isinstance(offer, dict):
                stamps.append((f"{label}.offers[{index}].seen_at", offer.get("seen_at")))
    for where, stamp in stamps:
        if _time(stamp) and not start <= parse_time(stamp) <= end:
            problems.append(f"{where} ({stamp}) is outside the run ({run['started_at']} to {run['finished_at']}); "
                            "run date -u right after each read and copy it")
    return problems


def _rank(item: dict[str, Any]) -> tuple[bool, int, int]:
    same = sum(1 for v in (item.get("checks") or {}).values() if v in SAME)
    return (item.get("same_product") is not True, STATUS_ORDER.get(item.get("status"), 3), -same)


def _describe_rank(item: dict[str, Any]) -> str:
    other, _, count = _rank(item)
    return f"{item.get('id')}: {'similar' if other else 'same product'}, {item.get('status')}, {-count} same"


def validate(answer: Any, now: datetime | None = None) -> list[str]:
    """Return every way this answer breaks SIMILAR_OUTPUT.md (empty list = it follows the contract)."""
    if not isinstance(answer, dict):
        return ["answer must be a JSON object"]
    if answer.get("contract") != CONTRACT:
        return [f"contract must be '{CONTRACT}' (SIMILAR_OUTPUT.md)"]
    problems = []
    request = answer.get("request") if isinstance(answer.get("request"), dict) else {}
    currency = request.get("currency", "")
    if not _text(currency) or not _text(request.get("region")):
        problems.append("request.region and request.currency are required")

    attributes = answer.get("attributes_used")
    if not isinstance(attributes, list) or not attributes:
        problems.append("attributes_used must list the quality attributes used")
        attributes = []
    names, musts = [], set()
    for index, attribute in enumerate(attributes):
        where = f"attributes_used[{index}]"
        if not isinstance(attribute, dict) or not _text(attribute.get("name")) or not _text(attribute.get("value")):
            problems.append(f"{where} needs name and value")
            continue
        names.append(attribute["name"])
        if attribute.get("must_have") is True:
            musts.add(attribute["name"])
        elif attribute.get("must_have") is not False:
            problems.append(f"{where}.must_have must be true or false")
        if attribute.get("from") not in ATTRIBUTE_SOURCES:
            problems.append(f"{where}.from must be one of {sorted(ATTRIBUTE_SOURCES)}")
        elif attribute["from"] == "page" and not _text(attribute.get("quote")):
            problems.append(f"{where} comes from the page and must quote it")

    reference = answer.get("reference") if isinstance(answer.get("reference"), dict) else {}
    problems.extend(_check_item(_label(reference, "reference"), reference, names, musts, currency, reference=True))
    candidates = answer.get("candidates")
    if not isinstance(candidates, list):
        problems.append("candidates must be a list")
        candidates = []
    labelled = []
    for index, candidate in enumerate(candidates):
        label = _label(candidate, f"candidates[{index}]") if isinstance(candidate, dict) else f"candidates[{index}]"
        problems.extend(_check_item(label, candidate, names, musts, currency, reference=False))
        if isinstance(candidate, dict):
            labelled.append((label, candidate))
    items = [c for _, c in labelled]
    ids = [reference.get("id")] + [c.get("id") for c in items]
    if len(set(ids)) != len(ids):
        problems.append("ids must be unique")
    paged = ([(_label(reference, "reference"), reference)] if reference.get("from") == "page" else []) + labelled
    problems.extend(_check_unit_prices(answer, ([(_label(reference, "reference"), reference)]) + labelled))

    for before, after in zip(items, items[1:]):
        if _rank(before) > _rank(after):
            problems.append(
                "candidates must be ranked: the same product at another store first; then compared, flagged, "
                f"excluded; most 'same' checks first within each; {_describe_rank(after)} belongs before "
                f"{_describe_rank(before)}"
            )
            break
    if answer.get("unit") in UNITS:
        problems.extend(_check_lowest(answer))

    blocked = answer.get("blocked")
    if not isinstance(blocked, list):
        problems.append("blocked must be a list (empty when every page was read)")
        blocked = []
    for index, page in enumerate(blocked):
        if not isinstance(page, dict) or not _text(page.get("store")) or not _text(page.get("what_happened")):
            problems.append(f"blocked[{index}] needs store and what_happened")
        elif url_problem(page.get("url")):
            problems.append(f"blocked[{index}].url {url_problem(page.get('url'))}")
        elif "opened" in page and not isinstance(page["opened"], bool):
            problems.append(f"blocked[{index}].opened must be true or false")
        elif page.get("opened") is False and not _known_blocked(page["url"]):
            problems.append(f"blocked[{index}] is listed unopened, which only a known-blocked store "
                            f"({', '.join(KNOWN_BLOCKED)}) may be; open it (it counts as a page) or leave it out")
    opened = [b for b in blocked if isinstance(b, dict) and b.get("opened") is not False]

    run = answer.get("run") if isinstance(answer.get("run"), dict) else {}
    budget, read = run.get("page_budget"), run.get("pages_read")
    urls = {_page(i["url"]) for i in [reference] + items + opened if _text(i.get("url"))}
    if not (isinstance(budget, int) and 0 < budget <= MAX_PAGES):
        problems.append(f"run.page_budget must be a whole number from 1 to {MAX_PAGES}")
    elif not isinstance(read, int) or read > budget:
        problems.append(f"run.pages_read must be a whole number no larger than the budget ({budget})")
    elif read < len(urls):
        problems.append(f"run.pages_read ({read}) is fewer than the distinct pages named ({len(urls)})")
    if not isinstance(run.get("searches"), list) or not run.get("searches"):
        problems.append("run.searches must list the searches made")
    problems.extend(_check_times(answer, paged, now))
    for field in ("took", "cost", "stopped_because"):
        if not _text(run.get(field)):
            problems.append(f"run.{field} is required ('not reported' when the runtime does not say)")
    hosts = {_host(u) for u in urls if not _text(reference.get("url")) or u != _page(reference["url"])}
    if len(hosts) < 2:
        problems.append("candidates and blocked pages must span at least two stores; never search one store only")
    if not isinstance(answer.get("unknowns"), list) or not answer.get("unknowns"):
        problems.append("unknowns must name what stayed unknown (tax at least)")

    for text in _walk_words(answer):
        for match in WORDING.finditer(QUOTED.sub(" ", text)):
            problems.append(f"no endorsement or urgency wording: '{match.group(0)}' in \"{text[:60]}\"")
    return problems


def _clean(text: Any) -> str:
    """Words as one line: newlines and runs of spaces copied from a page collapse to one space."""
    return " ".join(str(text).split())


def _sentence(text: Any) -> str:
    """Words that follow a full stop: a capital letter first and a full stop last."""
    text = _clean(text)
    return text[:1].upper() + text[1:] + ("" if text.endswith((".", "!", "?")) else ".")


def _price(amount: Any, currency: str) -> str:
    if currency == CURRENCY_NOT_STATED:
        return f"{amount} (currency not stated)"
    return f"${amount}" if currency == "USD" else f"{amount} {currency}"


def _unit_text(item: dict[str, Any]) -> str:
    unit = item.get("unit_price")
    if isinstance(unit, dict):
        return f"{_price(unit['amount'], unit.get('currency', 'USD'))} per {unit['per']}"
    return str(unit) if unit else ""


def _size_text(item: dict[str, Any], answer: dict[str, Any]) -> str:
    """' for 12 oz ($1.63 per oz)', ', size not stated', or '' when no unit applies."""
    if answer["unit"] == NO_UNIT:
        return ""
    if not isinstance(item.get("size"), dict):
        return ", size not stated"
    unit = _unit_text(item)
    return f" for {item['size']['text']}" + (f" ({unit})" if unit else "")


def _price_text(item: dict[str, Any]) -> str:
    price = item.get("shelf_price")
    if not isinstance(price, dict):
        return "no price read"
    text = _price(price["amount"], price["currency"])
    if price.get("read") != PAGE_TEXT:
        text += f" (from {READ_WORDS.get(price.get('read'), 'an unstated read')}, not confirmed in the page's own text)"
    return text


def _stock_text(item: dict[str, Any]) -> str:
    stock = item.get("availability") or {}
    quote = _clean(stock.get("quote", ""))
    text = {"in-stock": f"in stock (\"{quote}\")",
            "out-of-stock": f"out of stock (\"{quote}\")"}.get(stock.get("state"), "stock not stated")
    if stock.get("read") not in (PAGE_TEXT, None) and stock.get("state") != "not-stated":
        text += f", from {READ_WORDS.get(stock['read'], 'an unstated read')}"
    return text


def _offer(offer: dict[str, Any]) -> str:
    gate = "no sign-up needed" if offer["gate"] == "none" else f"gated: {offer['gate']}"
    ends = f"expires \"{_clean(offer['expires'])}\"" if _text(offer.get("expires")) else "no expiry printed"
    read = "" if offer.get("read") == PAGE_TEXT else f", from {READ_WORDS.get(offer.get('read'), 'an unstated read')}"
    return f"{offer['kind']} \"{_clean(offer['quote'])}\" ({offer['state']}, {gate}, {offer['where']}, {ends}{read})"


def _offers(item: dict[str, Any]) -> str:
    return "; ".join(_offer(o) for o in item.get("offers") or []) or "none printed on the pages read"


def _who(item: dict[str, Any], reference: dict[str, Any]) -> str:
    """How a lowest line names an item: yours, the same product, a similar product or a different product."""
    if item is reference:
        return "yours"
    checks = item.get("checks") or {}
    if item.get("same_product"):
        carried = [name for name, value in checks.items() if value == "inherited"]
        return "the same product" + (f"; its page does not print {', '.join(carried)}, taken from yours" if carried else "")
    differs = [name for name, value in checks.items() if value == "differs"]
    unseen = [name for name, value in checks.items() if value in ("unknown", "not-read")]
    if not differs and not unseen:
        return "a similar product"
    parts = ([f"differs: {', '.join(differs)}"] if differs else []) + \
        ([f"not shown on its page: {', '.join(unseen)}"] if unseen else [])
    return "a different product, not yours; " + "; ".join(parts)


def _gap(lower: Decimal, mine: Decimal) -> tuple[Decimal, str, bool]:
    """How far under the shopper's price, as (amount, percent text, meaningful)."""
    gap = mine - lower
    percent = (gap * 100 / mine).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if mine else Decimal(0)
    return gap, f"{percent}%", gap >= mine * MATERIAL


def _my_price(answer: dict[str, Any]) -> Decimal | None:
    """The shopper's own price when it can be compared: read in its page's text, in the asked currency."""
    reasons = {code for code, _ in _why_not_counted(answer["reference"], answer["request"]["currency"])}
    stock_only = {"out", "stock-read", "stock-unstated"}
    return None if answer["reference"].get("from") != "page" or reasons - stock_only else _shelf(answer["reference"])


def _sample(answer: dict[str, Any]) -> str:
    """' Based on N stores ...' when the counted items are a thin sample; '' otherwise."""
    counted, reference = _counted(answer), answer["reference"]
    stores: dict[str, str] = {}
    for item in counted:
        stores.setdefault(_host(item["url"]), item["store"])
    others = [item for item in counted if item is not reference and _host(item["url"]) != _host(reference.get("url"))]
    if len(stores) == 1:
        return (f" Based on 1 store: only prices at {next(iter(stores.values()))} could be counted, so they are not "
                "shown to be lower than at other stores.")
    if stores and (len(others) < 2 or len(stores) < 3):
        return (f" Based on {len(stores)} stores ({', '.join(stores.values())}): a thin sample, so a lower price may "
                "exist that this pass did not count.")
    return ""


def _if_size_text(answer: dict[str, Any], items: dict[str, dict[str, Any]]) -> str:
    if_size, currency = answer["lowest"].get("if_size"), answer["request"]["currency"]
    if not if_size:
        return ""
    item = items[if_size["id"]]
    text = (f" If yours is {if_size['size']} ({_clean(if_size['why'])}): {_price(if_size['amount'], currency)} at "
            f"{item['store']}, {item['name']} ({_who(item, answer['reference'])}), read on its page at "
            f"{item['checked_at']}")
    my_price = _my_price(answer)
    if my_price is not None:
        gap, percent, meaningful = _gap(_shelf(item), my_price)
        text += (f", {_price(gap, currency)} ({percent}) below yours at {_price(my_price, currency)}" if meaningful
                 else f"; no meaningful saving against yours at {_price(my_price, currency)}")
    return text + "."


def _shelf_line(answer: dict[str, Any], items: dict[str, dict[str, Any]]) -> list[str]:
    ref, lowest, currency, unit = answer["reference"], answer["lowest"], answer["request"]["currency"], answer["unit"]
    mine = _confirmed_size(ref)
    label = "**Lowest shelf price" + (f" for {ref['size']['text']}" if unit != NO_UNIT and mine else "") + ":**"
    shelf = lowest.get("shelf")
    if shelf:
        item = items[shelf["id"]]
        price = _price(shelf["amount"], currency)
        unit_part = f", {_unit_text(item)}" if isinstance(item.get("unit_price"), dict) else ""
        said = f"{price} at {item['store']}, {item['name']} ({_who(item, ref)}){unit_part}, read on its page at " \
               f"{item['checked_at']}"
        my_price = _my_price(answer)
        if item is not ref and my_price is not None:
            gap, percent, meaningful = _gap(_shelf(item), my_price)
            if meaningful:
                line = f"{label} {said}. This is the price: {_price(gap, currency)} ({percent}) below yours at " \
                       f"{_price(my_price, currency)}."
            else:
                line = f"{label} no meaningful saving found. {said}, is {_price(gap, currency)} ({percent}) below " \
                       f"yours at {_price(my_price, currency)}; a gap under 2% of your price is not counted as a saving."
        else:
            line = f"{label} {said}. This is the price."
    elif unit != NO_UNIT and mine is None:
        line = (f"{label} not compared: your product's page prints no size. What size is yours? It is printed on "
                "the bag or box; tell me and I will compare it." + _if_size_text(answer, items)
                + (f" Until then, compare per {unit} below." if lowest.get("unit") else ""))
    elif _counted(answer):
        line = f"{label} none counted at your size." + (f" Compare per {unit} below." if lowest.get("unit") else "")
    else:
        line = f"{label} none; no product had a price that could be counted."
    lines = [line + _sample(answer)]
    for entry in lowest.get("shelf_lower_not_counted") or []:
        other = items[entry["id"]]
        lines.append(f"- Lower but not counted: {other['name']} at {other['store']}, "
                     f"{_price(other['shelf_price']['amount'], other['shelf_price']['currency'])}: {_clean(entry['why'])}")
    return lines + [""]


def _unit_line(answer: dict[str, Any], items: dict[str, dict[str, Any]]) -> list[str]:
    ref, lowest, currency, unit = answer["reference"], answer["lowest"], answer["request"]["currency"], answer["unit"]
    if not lowest.get("unit"):
        return []
    line, item = lowest["unit"], items[lowest["unit"]["id"]]
    amount = _price(line["amount"], currency)
    said = f"{amount} at {item['store']}, {item['name']} ({_who(item, ref)}), {item['size']['text']} " \
           f"({_price(item['shelf_price']['amount'], currency)})"
    mine = _unit_amount(ref, answer) if _my_price(answer) is not None and _confirmed_size(ref) else None
    if item is not ref and mine is not None:
        _, percent, meaningful = _gap(_money(line["amount"]), mine)
        if meaningful:
            text = f"**Lowest price per {unit}:** {said}; yours is {_price(mine, currency)} per {unit}."
        else:
            text = (f"**Lowest price per {unit}:** no meaningful saving found. {said}, is {percent} below yours "
                    f"({_price(mine, currency)} per {unit}); a gap under 2% is not counted as a saving.")
    else:
        text = f"**Lowest price per {unit}:** {said}."
    lines = [text]
    for entry in lowest.get("unit_lower_not_counted") or []:
        other = items[entry["id"]]
        lines.append(f"- Lower per {unit} but not counted: {other['name']} at {other['store']}, "
                     f"{_unit_text(other)}: {_clean(entry['why'])}")
    return lines + [""]


def _code_line(answer: dict[str, Any], items: dict[str, dict[str, Any]]) -> str:
    lowest, currency = answer["lowest"], answer["request"]["currency"]
    code = lowest.get("if_code")
    if not code:
        return f"**If a printed code applies ({CODE_LABEL}):** none. {_sentence(lowest['if_code_none'])}"
    item = items[code["id"]]
    offer = next(o for o in item["offers"] if o.get("code") == code["code"])
    line = (f"**If a printed code applies ({CODE_LABEL}):** {_price(code['amount'], currency)} at {item['store']} "
            f"with code {code['code']}: \"{_clean(offer['quote'])}\".")
    if _text(offer.get("conditions")):
        line += f" Conditions: {_clean(offer['conditions']).rstrip('.')}."
    if "*" in offer["quote"]:
        line += " The asterisk means terms apply: it may not apply to this item."
    line += f" Expires \"{_clean(offer['expires'])}\"." if _text(offer.get("expires")) else " No expiry printed."
    return line + " This is not the price."


def render(answer: dict[str, Any]) -> str:
    """The markdown answer, in SIMILAR_OUTPUT.md's template order. Call validate() first."""
    run, ref = answer["run"], answer["reference"]
    items = {i["id"]: i for i in [ref] + answer["candidates"]}
    lines = [
        f"## Similar products and their offers: {ref['name']} ({ref['store']})",
        "",
        f"Checked {run['started_at']} to {run['finished_at']} · {run['pages_read']} of {run['page_budget']} pages read"
        f" · {len(run['searches'])} search{'es' if len(run['searches']) != 1 else ''} · took {run['took']}"
        f" · cost {run['cost']}",
        f"Stopped because: {_clean(run['stopped_because'])}",
        "This is one pass: results vary between runs because search results vary.",
        "",
    ]
    why = reference_reason(answer)
    if why:
        lines += [f"**Your product:** {why}; it is not counted below.", ""]
    qualified = [c for c in answer["candidates"] if c["status"] in ("compared", "flagged")]
    if answer["candidates"] and not qualified:
        lines += ["**Similar products:** none qualified; every product found was excluded, each listed below "
                  "with why.", ""]
    lines += _shelf_line(answer, items)
    lines += _unit_line(answer, items)
    lines.append(_code_line(answer, items))

    lines += ["", "### What it was compared with", ""]
    where = ref.get("url") or "described by you, no page"
    stock = _stock_text(ref)
    stock = f" {stock[0].upper()}{stock[1:]} on its page." if ref.get("from") == "page" else ""
    lines.append(f"{ref['name']} at {ref['store']}: {_price_text(ref)}{_size_text(ref, answer)}.{stock} {where}")
    lines.append("")
    offers = _offers(ref) if ref.get("from") == "page" else "none; no page was read"
    lines.append(f"- Offers seen on its page: {offers}")
    for attribute in answer["attributes_used"]:
        need = "must have" if attribute["must_have"] else "may vary"
        source = {"page": f"from the page: \"{_clean(attribute.get('quote', ''))}\"", "shopper": "from you",
                  "assumed": f"assumed: {_clean(attribute.get('why', 'not stated'))}"}[attribute["from"]]
        lines.append(f"- {attribute['name']}: {attribute['value']} ({need}; {source})")

    heading = "Similar products, most similar first" if qualified or not answer["candidates"] else \
        "Products looked at, none qualified"
    lines += ["", f"### {heading}", ""]
    for rank, item in enumerate(answer["candidates"], 1):
        status = "Compared" if item["status"] == "compared" else \
            f"{item['status'].capitalize()}: {_clean(item['status_reason'])}"
        same = "Same product at another store. " if item.get("same_product") else ""
        lines.append(f"{rank}. **{item['name']}** at {item['store']}: {_price_text(item)}{_size_text(item, answer)}. "
                     f"{same}{status}.")
        lines.append(f"   - Similar because: {'; '.join(_clean(r) for r in item['similar_because'])}")
        lines.append(f"   - Not comparable: {'; '.join(_clean(r) for r in item['not_comparable'])}")
        carried = [name for name, value in (item.get("checks") or {}).items() if value == "inherited"]
        if carried:
            lines.append(f"   - Taken from yours, not printed on its page: {', '.join(carried)} (the same product)")
        lines.append(f"   - Offers seen: {_offers(item)}")
        lines.append(f"   - Checked {item['checked_at']}, {_stock_text(item)}: {item['url']}; found via "
                     f"{_clean(item['found_via'])}")

    lines += ["", "### Pages that could not be read or priced", ""]
    lines += [f"- {b['store']}: {'not opened, known blocked: ' if b.get('opened') is False else ''}"
              f"{_clean(b['what_happened']).rstrip('.')}. Check it yourself: {b['url']}" for b in answer["blocked"]] \
        or ["- none"]
    lines += ["", "### Unknowns", ""] + [f"- {_clean(u)}" for u in answer["unknowns"]]
    lines += [
        "",
        "No code was tried and nothing was added to a cart. A shelf price is the price; codes, subscribe prices "
        "and sign-up offers never lower it. Pop-ups and delayed offers do not show on every load, so a page may "
        "print an offer this pass did not see. No affiliate links; the order is by similarity, not by commission.",
    ]
    return "\n".join(lines) + "\n"
