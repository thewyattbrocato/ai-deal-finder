"""Output contract for the skill's "similar products and their offers" mode.

`validate(answer)` checks one answer JSON against SIMILAR_OUTPUT.md and returns
violation messages (empty = the answer follows the contract). `render(answer)`
prints the markdown answer in the template's fixed order. Pure functions: no
network, no model, no credentials. Unit prices are recomputed with
deal_finder/unit_price.py, never here.

Authoritative rules: SIMILAR_OUTPUT.md, SKILL.md ("Similar products and their
offers"), VISION.md (evidence states, no affiliate links), README.md ("What the
evidence rules mean": a seen code is never a lower price).
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from . import unit_price as units
from .decision import BANNED_PHRASES
from .deception import parse_time
from .evidence import EvidenceState

CONTRACT = "similar-v1"
CODE_LABEL = "not tried, may not work"
SIZE_NOT_STATED = "not comparable: size not stated"
MAX_PAGES = 10
STATES = {state.value for state in EvidenceState}
OFFER_STATES = {"retailer-stated", "unverified", "rejected"}
OFFER_KINDS = {"code", "sale", "subscribe", "signup", "shipping-threshold", "other"}
OFFER_WHERE = {"product page", "site banner", "store page"}
GATES = {"none", "email", "sms", "first-order", "subscription", "member", "store-card", "app", "other"}
STATUSES = {"compared", "flagged", "excluded"}
CHECKS = {"same", "differs", "unknown"}
ATTRIBUTE_SOURCES = {"page", "shopper", "assumed"}
TRACKING_PARAM = re.compile(
    r"^(utm_.*|_gsid|gclid|gbraid|wbraid|fbclid|msclkid|mc_[a-z]+|_ga|ref|ref_|tag|aff.*|affiliate.*|irclickid|clickid|srsltid)$",
    re.IGNORECASE,
)
EXTRA_BANS = ("best deal", "great deal", "hurry", "act now", "don't miss", "lowest price guaranteed")
WORDING = re.compile(r"\b(" + "|".join(re.escape(p) for p in BANNED_PHRASES + EXTRA_BANS) + r")\b", re.IGNORECASE)
# Page text and page-copied identities may contain any words; only the
# agent's own wording is held to the language bans.
NOT_AGENT_WORDS = {"quote", "url", "code", "name", "store", "said"}


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


def url_problem(url: Any) -> str:
    """Empty when the URL is a plain http(s) link with no tracking or affiliate parameter."""
    if not _text(url) or urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).hostname:
        return "is not an http(s) link"
    dirty = [key for key, _ in parse_qsl(urlsplit(url).query) if TRACKING_PARAM.match(key)]
    return f"keeps tracking or affiliate parameters ({', '.join(dirty)})" if dirty else ""


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
    """Codes that may form the 'if a printed code applies' line: printed by the store, ungated."""
    return [
        offer
        for offer in item.get("offers") or []
        if isinstance(offer, dict)
        and offer.get("kind") == "code"
        and offer.get("state") == "retailer-stated"
        and offer.get("gate") == "none"
    ]


def _shelf(item: dict[str, Any]) -> Decimal | None:
    price = item.get("shelf_price")
    return _money(price.get("amount")) if isinstance(price, dict) else None


def _eligible(answer: dict[str, Any]) -> list[dict[str, Any]]:
    """Items the two lowest lines may name: compared, read on their own page now, in the asked currency."""
    reference = dict(answer.get("reference") or {}, status="compared")
    currency = (answer.get("request") or {}).get("currency")
    return [
        item
        for item in [reference] + [c for c in answer.get("candidates") or [] if isinstance(c, dict)]
        if item.get("status") == "compared"
        and _shelf(item) is not None
        and item["shelf_price"].get("state") == "observed-now"
        and item["shelf_price"].get("currency") == currency
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


def _check_offer(where: str, offer: Any) -> list[str]:
    if not isinstance(offer, dict):
        return [f"{where} must be an object"]
    problems = []
    if offer.get("kind") not in OFFER_KINDS:
        problems.append(f"{where}.kind must be one of {sorted(OFFER_KINDS)}")
    if not _text(offer.get("quote")):
        problems.append(f"{where} needs the page's own words in quote")
    if offer.get("where") not in OFFER_WHERE:
        problems.append(f"{where}.where must be one of {sorted(OFFER_WHERE)}; codes from coupon sites are not listed")
    if offer.get("state") not in OFFER_STATES:
        problems.append(f"{where}.state must be one of {sorted(OFFER_STATES)}; nothing was tried in a cart")
    if offer.get("gate") not in GATES:
        problems.append(f"{where}.gate must be one of {sorted(GATES)}")
    if not _time(offer.get("seen_at")):
        problems.append(f"{where}.seen_at must be an absolute timestamp")
    if offer.get("kind") == "code":
        code = offer.get("code")
        if not _text(code) or code.lower() not in (offer.get("quote") or "").lower():
            problems.append(f"{where} code must appear in the page's own words (quote)")
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
            problems.append(f"{where} is unsourced: checked_at must be an absolute timestamp")
    if not reference and not _text(item.get("found_via")):
        problems.append(f"{where}.found_via must say how it was found")

    price = item.get("shelf_price")
    if price is None and not described:
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

    size = item.get("size")
    if size is not None and not _printed(size):
        problems.append(f"{where}.size must quote the page's own words; never guess a size (use null)")

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
    status = item.get("status")
    if status not in STATUSES:
        problems.append(f"{where}.status must be one of {sorted(STATUSES)}")
    if status in ("flagged", "excluded") and not _text(item.get("status_reason")):
        problems.append(f"{where}.status_reason must say why it is {status}")
    checks = item.get("checks") if isinstance(item.get("checks"), dict) else {}
    for name in names:
        if checks.get(name) not in CHECKS:
            problems.append(f"{where}.checks['{name}'] must be one of {sorted(CHECKS)}")
    if any(checks.get(name) == "differs" for name in musts) and status != "excluded":
        problems.append(f"{where} fails a must-have attribute and must be excluded")
    elif any(checks.get(name) == "unknown" for name in musts) and status == "compared":
        problems.append(f"{where} has a must-have its page does not show; flag it, do not compare it")
    if status == "compared" and isinstance(price, dict) and price.get("state") != "observed-now":
        problems.append(f"{where} is compared but its shelf price was not read on its own page now")
    if status != "excluded" and isinstance(price, dict) and price.get("currency") != currency:
        problems.append(f"{where} is in another currency; exclude it (prices are never converted)")
    for field, label in (("similar_because", "similar-because reason"), ("not_comparable", "not-comparable reason")):
        reasons = item.get(field)
        if not isinstance(reasons, list) or not reasons or not all(_text(r) for r in reasons):
            problems.append(f"{where} is missing a {label} ({field} must be a non-empty list)")
    return problems


def _printed(size: Any) -> bool:
    return isinstance(size, dict) and _text(size.get("text")) and _text(size.get("quote"))


def _printed_size(size: dict[str, Any]) -> units.Size | str:
    """The one size in the size text, checked against the page's words; or why it cannot be used."""
    parsed, quoted = units.parse_size_checked(size["text"]), units.parse_size_checked(size["quote"])
    if not isinstance(parsed, units.Size):
        return f"'{size['text']}' is not one printed size" + (f" ({parsed.reason})" if parsed else "")
    if isinstance(quoted, units.SizeRefusal):
        return f"the page's words '{size['quote']}' give no single size ({quoted.reason})"
    if quoted is None or abs(quoted.base_total() - parsed.base_total()) > (
        parsed.base_total() * units.CONSISTENT_WITHIN
    ):
        return f"size '{size['text']}' is not the size in the page's words '{size['quote']}'; never guess a size"
    return parsed


def _unit_problem(item: dict[str, Any], reference: dict[str, Any], unit: dict[str, Any]) -> str:
    """Empty when the unit price is shelf price / printed size as deal_finder/unit_price.py computes it."""
    sizes = [_printed_size(owner["size"]) for owner in (item, reference)]
    reasons = [size for size in sizes if isinstance(size, str)]
    if reasons:
        return reasons[0] + "; write 'not comparable: <reason>'"
    if sizes[0].family != sizes[1].family:
        return f"different units ({sizes[0].family} vs {sizes[1].family}); write 'not comparable: different units'"
    try:
        price = units.Price.of(item["shelf_price"]["amount"], item["shelf_price"]["currency"])
        value = units.unit_price(price, sizes[0], units.normalize_unit(unit["per"]))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return f"per must be a unit deal_finder/unit_price.py uses ({', '.join(units.FAMILY)}) beside a shelf price"
    if isinstance(value, units.NotComparable):
        return value.reason
    expected = value.display().split()[0]
    if _money(unit.get("amount")) != Decimal(expected):
        return f"unit price must be shelf price / printed size, {expected} per {value.unit} (deal_finder/unit_price.py)"
    return ""


def _check_unit_prices(items: list[dict[str, Any]], reference: dict[str, Any]) -> list[str]:
    problems, per = [], set()
    for item in items:
        unit = item.get("unit_price")
        both_printed = _printed(item.get("size")) and _printed(reference.get("size"))
        if isinstance(unit, dict):
            if not both_printed:
                problems.append(
                    f"{item.get('id')}: a unit price needs both sizes printed on their pages; "
                    f"write '{SIZE_NOT_STATED}'"
                )
            elif _unit_problem(item, reference, unit):
                problems.append(f"{item.get('id')}.unit_price: {_unit_problem(item, reference, unit)}")
            per.add(unit.get("per"))
        elif not both_printed and unit != SIZE_NOT_STATED:
            problems.append(f"{item.get('id')}.unit_price must be exactly '{SIZE_NOT_STATED}'")
        elif both_printed and not (isinstance(unit, str) and unit.startswith("not comparable: ")):
            problems.append(f"{item.get('id')}.unit_price must be an object or 'not comparable: <reason>'")
    if len(per) > 1:
        problems.append(f"unit prices must use one stated unit, not {sorted(map(str, per))}")
    return problems


def _check_lowest(answer: dict[str, Any], items: list[dict[str, Any]]) -> list[str]:
    lowest = answer.get("lowest")
    if not isinstance(lowest, dict):
        return ["lowest is required (shelf, unit, if_code)"]
    problems = []
    eligible = _eligible(answer)
    by_id = {item.get("id"): item for item in eligible}
    shelf = lowest.get("shelf")
    if not eligible:
        if shelf is not None:
            problems.append("lowest.shelf must be null: no compared item has a shelf price read on its page")
    elif not isinstance(shelf, dict) or shelf.get("id") not in by_id:
        problems.append("lowest.shelf must name a compared item with a shelf price read on its page")
    else:
        floor = min(_shelf(item) for item in eligible)
        if _money(shelf.get("amount")) != _shelf(by_id[shelf["id"]]) or _shelf(by_id[shelf["id"]]) != floor:
            problems.append(
                f"lowest.shelf must be the lowest compared shelf price ({floor}) exactly as its page printed it; "
                "a printed code never lowers a price"
            )
        listed = {
            entry.get("id")
            for entry in shelf.get("also_lower_not_counted") or []
            if isinstance(entry, dict) and _text(entry.get("why"))
        }
        hidden = [
            item.get("id")
            for item in items
            if item.get("status") == "flagged" and _shelf(item) is not None and _shelf(item) < floor
            and item["shelf_price"].get("currency") == (answer.get("request") or {}).get("currency")
            and item.get("id") not in listed
        ]
        if hidden:
            problems.append(f"lowest.shelf.also_lower_not_counted must name each cheaper flagged item and why: {hidden}")

    unit = lowest.get("unit")
    unit_prices = {
        item.get("id"): _money(item["unit_price"].get("amount"))
        for item in eligible
        if isinstance(item.get("unit_price"), dict) and _money(item["unit_price"].get("amount")) is not None
    }
    if unit is not None and (
        not isinstance(unit, dict)
        or unit_prices.get(unit.get("id")) != _money(unit.get("amount"))
        or _money(unit.get("amount")) != min(unit_prices.values(), default=None)
    ):
        problems.append("lowest.unit must be the lowest unit price among compared items with both sizes printed")

    if_code = lowest.get("if_code")
    priced_codes = [(code_price(_shelf(item), offer), item, offer) for item in eligible for offer in _code_offers(item)]
    options = [option for option in priced_codes if option[0] is not None]
    if if_code is None:
        if options:
            problems.append("lowest.if_code is missing although a compared item prints an ungated code")
        if not _text(lowest.get("if_code_none")):
            problems.append("lowest.if_code_none must say why there is no code line")
        return problems
    if not isinstance(if_code, dict) or if_code.get("label") != CODE_LABEL:
        problems.append(f"lowest.if_code must carry the label '{CODE_LABEL}'")
        return problems
    match = [o for o in options if o[1].get("id") == if_code.get("id") and o[2].get("code") == if_code.get("code")]
    item = next((i for i in items + [answer.get("reference") or {}] if i.get("id") == if_code.get("id")), {})
    used = next((o for o in item.get("offers") or [] if isinstance(o, dict) and o.get("code") == if_code.get("code")), {})
    if used and used.get("gate") != "none":
        problems.append(
            "lowest.if_code uses a gated code; a code behind email, SMS, first order, subscription "
            "or membership is labelled gated and never forms this line"
        )
    elif not match:
        problems.append(
            "lowest.if_code must use an ungated code printed by the store on a compared item, with its discount stated"
        )
    elif _money(if_code.get("amount")) != match[0][0] or match[0][0] != min(o[0] for o in options):
        problems.append(
            f"lowest.if_code.amount must be the lowest shelf price with one printed code applied "
            f"({min(o[0] for o in options)}); codes never stack"
        )
    return problems


def validate(answer: Any) -> list[str]:
    """Return every way this answer breaks SIMILAR_OUTPUT.md (empty list = it follows the contract)."""
    if not isinstance(answer, dict):
        return ["answer must be a JSON object"]
    if answer.get("contract") != CONTRACT:
        return [f"contract must be '{CONTRACT}'"]
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
    problems.extend(_check_item("reference", reference, names, musts, currency, reference=True))
    candidates = answer.get("candidates")
    if not isinstance(candidates, list):
        problems.append("candidates must be a list")
        candidates = []
    for index, candidate in enumerate(candidates):
        problems.extend(_check_item(f"candidates[{index}]", candidate, names, musts, currency, reference=False))
    items = [c for c in candidates if isinstance(c, dict)]
    ids = [reference.get("id")] + [c.get("id") for c in items]
    if len(set(ids)) != len(ids):
        problems.append("ids must be unique")
    problems.extend(_check_unit_prices(([reference] if reference.get("from") == "page" else []) + items, reference))

    order = [(c.get("status") == "excluded", -sum(1 for v in (c.get("checks") or {}).values() if v == "same")) for c in items]
    if order != sorted(order):
        problems.append("candidates must be ranked most similar first (count of 'same' checks), excluded ones last")
    problems.extend(_check_lowest(answer, items))

    blocked = answer.get("blocked")
    if not isinstance(blocked, list):
        problems.append("blocked must be a list (empty when every page was read)")
        blocked = []
    for index, page in enumerate(blocked):
        if not isinstance(page, dict) or not _text(page.get("store")) or not _text(page.get("what_happened")):
            problems.append(f"blocked[{index}] needs store and what_happened")
        elif url_problem(page.get("url")):
            problems.append(f"blocked[{index}].url {url_problem(page.get('url'))}")

    run = answer.get("run") if isinstance(answer.get("run"), dict) else {}
    budget, read = run.get("page_budget"), run.get("pages_read")
    urls = {i.get("url") for i in [reference] + items + [b for b in blocked if isinstance(b, dict)] if _text(i.get("url"))}
    if not (isinstance(budget, int) and 0 < budget <= MAX_PAGES):
        problems.append(f"run.page_budget must be a whole number from 1 to {MAX_PAGES}")
    elif not isinstance(read, int) or read > budget:
        problems.append(f"run.pages_read must be a whole number no larger than the budget ({budget})")
    elif read < len(urls):
        problems.append(f"run.pages_read ({read}) is fewer than the distinct pages named ({len(urls)})")
    if not isinstance(run.get("searches"), list) or not run.get("searches"):
        problems.append("run.searches must list the searches made")
    if not (_time(run.get("started_at")) and _time(run.get("finished_at"))) or (
        parse_time(run["finished_at"]) < parse_time(run["started_at"])
    ):
        problems.append("run.started_at and run.finished_at must be absolute timestamps in order")
    for field in ("took", "cost", "stopped_because"):
        if not _text(run.get(field)):
            problems.append(f"run.{field} is required ('not reported' when the runtime does not say)")
    hosts = {urlsplit(u).hostname for u in urls if u != reference.get("url")}
    if len(hosts) < 2:
        problems.append("candidates and blocked pages must span at least two stores; never search one store only")
    if not isinstance(answer.get("unknowns"), list) or not answer.get("unknowns"):
        problems.append("unknowns must name what stayed unknown (tax at least)")

    for text in _walk_words(answer):
        for match in WORDING.finditer(text):
            problems.append(f"no endorsement or urgency wording: '{match.group(0)}' in \"{text[:60]}\"")
    return problems


def _price(amount: Any, currency: str) -> str:
    return f"${amount}" if currency == "USD" else f"{amount} {currency}"


def _unit(item: dict[str, Any]) -> str:
    unit = item.get("unit_price")
    if isinstance(unit, dict):
        return f"{_price(unit['amount'], unit.get('currency', 'USD'))} per {unit['per']}"
    return str(unit)


def _size(item: dict[str, Any]) -> str:
    return item["size"]["text"] if isinstance(item.get("size"), dict) else "size not stated"


def _offer(offer: dict[str, Any]) -> str:
    gate = "no sign-up needed" if offer["gate"] == "none" else f"gated: {offer['gate']}"
    return f"{offer['kind']} \"{offer['quote']}\" ({offer['state']}, {gate}, {offer['where']})"


def render(answer: dict[str, Any]) -> str:
    """The markdown answer, in SIMILAR_OUTPUT.md's template order. Call validate() first."""
    currency = answer["request"]["currency"]
    run, ref, lowest = answer["run"], answer["reference"], answer["lowest"]
    items = {i["id"]: i for i in [ref] + answer["candidates"]}
    lines = [
        f"## Similar products and their offers: {ref['name']} ({ref['store']})",
        "",
        f"Checked {run['started_at']} to {run['finished_at']} · {run['pages_read']} of {run['page_budget']} pages read"
        f" · {len(run['searches'])} search{'es' if len(run['searches']) != 1 else ''} · took {run['took']}"
        f" · cost {run['cost']}",
        f"Stopped because: {run['stopped_because']}",
        "",
    ]
    shelf = lowest.get("shelf")
    if shelf:
        item = items[shelf["id"]]
        lines.append(
            f"**Lowest shelf price:** {_price(shelf['amount'], currency)} at {item['store']}, {item['name']}, "
            f"{_size(item)} ({_unit(item)}), read on its page at {item['checked_at']}. This is the price."
        )
        for entry in shelf.get("also_lower_not_counted") or []:
            other = items[entry["id"]]
            lines.append(f"- Lower but not counted: {other['name']} at {other['store']}, "
                         f"{_price(other['shelf_price']['amount'], currency)}: {entry['why']}")
        lines.append("")
    else:
        lines += ["**Lowest shelf price:** none; no compared product had a shelf price read on its page.", ""]
    if lowest.get("unit"):
        unit, item = lowest["unit"], items[lowest["unit"]["id"]]
        lines.append(f"**Lowest price per {item['unit_price']['per']} (both sizes printed):** "
                     f"{_price(unit['amount'], currency)} at {item['store']}, {item['name']}, {_size(item)}.")
        lines.append("")
    code = lowest.get("if_code")
    if code:
        item = items[code["id"]]
        quote = next(o["quote"] for o in item["offers"] if o.get("code") == code["code"])
        lines.append(f"**If a printed code applies ({CODE_LABEL}):** {_price(code['amount'], currency)} at "
                     f"{item['store']} with code {code['code']}: \"{quote}\". This is not the price.")
    else:
        lines.append(f"**If a printed code applies ({CODE_LABEL}):** none. {lowest['if_code_none']}")

    lines += ["", "### What it was compared with", ""]
    where = ref.get("url") or "described by you, no page"
    ref_price = _price(ref["shelf_price"]["amount"], currency) if ref.get("shelf_price") else "no price"
    lines.append(f"{ref['name']} at {ref['store']}: {ref_price} for {_size(ref)}. {where}")
    lines.append("")
    for attribute in answer["attributes_used"]:
        need = "must have" if attribute["must_have"] else "may vary"
        source = {"page": f"from the page: \"{attribute.get('quote', '')}\"", "shopper": "from you",
                  "assumed": f"assumed: {attribute.get('why', 'not stated')}"}[attribute["from"]]
        lines.append(f"- {attribute['name']}: {attribute['value']} ({need}; {source})")

    lines += ["", "### Similar products, most similar first", ""]
    for rank, item in enumerate(answer["candidates"], 1):
        status = "Compared" if item["status"] == "compared" else f"{item['status'].capitalize()}: {item['status_reason']}"
        lines.append(f"{rank}. **{item['name']}** at {item['store']}: "
                     f"{_price(item['shelf_price']['amount'], item['shelf_price']['currency'])} for {_size(item)} "
                     f"({_unit(item)}). {status}.")
        lines.append(f"   - Similar because: {'; '.join(item['similar_because'])}")
        lines.append(f"   - Not comparable: {'; '.join(item['not_comparable'])}")
        offers = "; ".join(_offer(o) for o in item["offers"]) or "none printed on the pages read"
        lines.append(f"   - Offers seen: {offers}")
        lines.append(f"   - Checked {item['checked_at']}: {item['url']} (found via {item['found_via']})")

    lines += ["", "### Pages that could not be read", ""]
    lines += [f"- {b['store']}: {b['what_happened']}. Check it yourself: {b['url']}" for b in answer["blocked"]] or ["- none"]
    lines += ["", "### Unknowns", ""] + [f"- {u}" for u in answer["unknowns"]]
    lines += [
        "",
        "No code was tried and nothing was added to a cart. A shelf price is the price; codes, subscribe prices "
        "and sign-up offers never lower it. No affiliate links; the order is by similarity, not by commission.",
    ]
    return "\n".join(lines) + "\n"
