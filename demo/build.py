"""Demo page builder: a product screen for the ai-deal-finder coupon slice.

Runs the REAL deal_finder engine (stdlib-only, no network) over the
live-observed evidence recorded in LIVE_VERIFICATION.md and emits a single
self-contained demo/index.html. The page shows the product, the price, the
decision, and any coupon really seen — no lab labels. No deals are
fabricated: every price, decision, and coupon on the page is engine output
or a recorded browser observation.

Regenerate:  python3 demo/build.py   (from the repo root)
Verify:      python3 -m unittest discover -s tests
"""

import datetime
import html
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from deal_finder.consent import ConsentRecord  # noqa: E402
from deal_finder.decision import DecisionInput  # noqa: E402
from deal_finder.evidence import Candidate, Coupon, EvidenceState  # noqa: E402
from deal_finder.landed_cost import LandedCost, RankedCandidate  # noqa: E402
import catalog  # noqa: E402  (demo/catalog.py: stored evidence -> observations)
import terms  # noqa: E402  (demo/terms.py: size/shipping/subscribe pages stated)

TS_OBS1 = "2026-09-30T14:08:20Z"
APPLE_URL = "https://www.apple.com/airpods-pro/"


def esc(s):
    return html.escape(str(s), quote=True)


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
     "nov", "dec"], 1)}
_TIME = r"(?: at \d{1,2}:\d\d [AP]M(?: [A-Z]{2,3})?)?"
_DATE_RE = re.compile(
    r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b" + _TIME
    + r"|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? "
    r"(\d{1,2}),? (\d{4})\b" + _TIME)
_CONDITION_RE = re.compile(
    r"(?i)cannot be combined|can't be combined|not valid|no cash value|"
    r"excludes?\b|excluded|one per|limit \d|limited to|minimum|while supplies")


def printed_window(text):
    """The date window a coupon's own page text prints, or None.

    Only explicit full dates (m/d/yyyy read as US month/day/year, the stored
    pages being US, or "Oct 4, 2026") count, and only exactly two of them in
    order. One date (start or end unclear), a date without a year, an
    impossible date or an out-of-order pair is ambiguous: no window.
    """
    found = []
    for m in _DATE_RE.finditer(text or ""):
        try:
            if m.group(1):
                d = datetime.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            else:
                d = datetime.date(int(m.group(6)), _MONTHS[m.group(4).lower()],
                                  int(m.group(5)))
        except ValueError:
            return None
        found.append((d, m))
    if len(found) != 2 or found[0][0] > found[1][0]:
        return None
    first, last = found[0][1], found[1][1]
    return {"start": found[0][0].isoformat(), "end": found[1][0].isoformat(),
            "quote": text[first.start():last.end()]}


def printed_conditions(text):
    """Whole sentences of the page text that state a condition, verbatim."""
    out = []
    for s in re.split(r"(?<=[.!?])\s+", text or ""):
        s = s.strip()
        if s and s[-1] in ".!?" and _CONDITION_RE.search(s):
            out.append(s)
    return out


def coupon_page_text(obs):
    """The stored page text around the code (evidence file), or the shown offer."""
    cp = obs["coupon"]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence",
                        obs["id"] + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            for sn in json.load(f).get("coupon_snippets") or []:
                if cp["code"] in sn:
                    return sn
    except (OSError, ValueError):
        pass
    return cp["text"]


def run_lv001():
    """Single Apple direct offer, full provenance, tax/shipping Unknown."""
    apple = Candidate(
        id="apple-direct", variant="AirPods Pro 3, white",
        quantity_terms="1 pair", condition="new", bundle="single",
        seller="Apple", fulfilled_by="Apple", region="US", in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source=APPLE_URL, observed_at=TS_OBS1,
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(item_price=249.0, shipping=None, known_tax=None)
    from deal_finder.decision import decide
    decision = decide(DecisionInput(
        candidates=[apple],
        ranked=[RankedCandidate("apple-direct", cost)],
        coupons=[Coupon(code="AGG20", merchant="Apple", status="unverified")],
        consent=ConsentRecord(), mode="browsing",
    ))
    return apple, cost, decision


TS_ON = "2026-10-01T19:50:21Z"
TS_GAP = "2026-10-01T19:50:30Z"
TS_NIKE = "2026-10-01T19:50:41Z"
TS_APPLE2 = "2026-10-01T19:50:52Z"
ON_URL = "https://oldnavy.gap.com/browse/product.do?pid=777363182"
GAP_URL = "https://www.gap.com/browse/product.do?pid=800546212"
NIKE_URL = "https://www.nike.com/t/air-jordan-og-womens-shoes-6JW206/CW0907-002"


def run_lv005():
    """Old Navy sweatpants, retailer-stated code EXTRA excluded."""
    from deal_finder.decision import decide
    on = Candidate(
        id="oldnavy-sweatpants",
        variant="High-Waisted SoComfy Wide-Leg Sweatpants",
        quantity_terms="1 pair", condition="new", bundle="single",
        seller="Old Navy", fulfilled_by="Old Navy", region="US",
        in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source=ON_URL, observed_at=TS_ON,
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(
        item_price=25.0, shipping=None, known_tax=None,
        eligibility_condition="free shipping on $50+ for Rewards Members; "
                              "membership not volunteered",
    )
    decision = decide(DecisionInput(
        candidates=[on],
        ranked=[RankedCandidate("oldnavy-sweatpants", cost)],
        coupons=[Coupon(code="EXTRA", merchant="Old Navy",
                        status="retailer-stated")],
        consent=ConsentRecord(), mode="browsing",
    ))
    return on, cost, decision


def run_lv006():
    """Gap cardigan, offer text seen but no code — no coupon."""
    from deal_finder.decision import decide
    gap = Candidate(
        id="gap-cardigan",
        variant="CashSoft Crop Cardigan, Brown and navy blue argyle",
        quantity_terms="1 cardigan", condition="new", bundle="single",
        seller="Gap", fulfilled_by="Gap", region="US", in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source=GAP_URL, observed_at=TS_GAP,
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(
        item_price=79.95, shipping=None, known_tax=None,
        eligibility_condition="free shipping on $50+ for Rewards Members; "
                              "membership not volunteered",
    )
    decision = decide(DecisionInput(
        candidates=[gap],
        ranked=[RankedCandidate("gap-cardigan", cost)],
        coupons=[], consent=ConsentRecord(), mode="browsing",
    ))
    return gap, cost, decision


def run_lv007():
    """Nike markdown price; was-price is reference text, never subtracted."""
    from deal_finder.decision import decide
    nike = Candidate(
        id="nike-jordan-og",
        variant="Air Jordan OG Women's Shoes, Black/White/University Red "
                "(CW0907-002)",
        quantity_terms="1 pair", condition="new", bundle="single",
        seller="Nike", fulfilled_by="Nike", region="US", in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source=NIKE_URL, observed_at=TS_NIKE,
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(
        item_price=87.97, shipping=None, known_tax=None,
        eligibility_condition="members free shipping on orders $50+; "
                              "membership not volunteered",
    )
    decision = decide(DecisionInput(
        candidates=[nike],
        ranked=[RankedCandidate("nike-jordan-og", cost)],
        coupons=[], consent=ConsentRecord(), mode="browsing",
    ))
    return nike, cost, decision


def lavazza_record(slug):
    """Stored Lavazza evidence (demo/evidence/lavazza/<slug>.json)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "evidence", "lavazza", slug + ".json")
    with open(path) as f:
        rec = json.load(f)
    return rec, rec["observations"][-1]


_L1, _O1 = lavazza_record("super-crema")
_L2, _O2 = lavazza_record("qualita-rossa")
_L3, _O3 = lavazza_record("dolcevita-classico")
TS_COF1, TS_COF2, TS_COF3 = _O1["observed_at"], _O2["observed_at"], _O3["observed_at"]
COF1_URL, COF2_URL, COF3_URL = _L1["page_url"], _L2["page_url"], _L3["page_url"]
# The code the pages print now (latest dated observation); the earlier
# CAFE20 observation stays in the stored record as history.
LAVAZZA_CODE = _O1["code"]
assert {_O1["code"], _O2["code"], _O3["code"]} == {LAVAZZA_CODE}
LAVAZZA_OFFER = (LAVAZZA_CODE, "\u201c" + _O1["banner"] + "\u201d")
LAVAZZA_CAVEAT = ("Seen in the store banner but never tried out, so the price "
                 "shown does not include it.")


def run_cof1():
    """Super Crema Whole Bean 2.2 lb, $26.99, code seen not tested."""
    from deal_finder.decision import decide
    cof = Candidate(
        id="lavazza-super-crema",
        variant="Super Crema Whole Bean, 2.2 lb",
        quantity_terms="1x 2.2 lb bag", condition="new", bundle="single",
        seller="Lavazza", fulfilled_by="Lavazza", region="US", in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source=COF1_URL, observed_at=TS_COF1,
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(item_price=26.99, shipping=None, known_tax=None)
    decision = decide(DecisionInput(
        candidates=[cof],
        ranked=[RankedCandidate("lavazza-super-crema", cost)],
        coupons=[Coupon(code=LAVAZZA_CODE, merchant="Lavazza",
                        status="retailer-stated")],
        consent=ConsentRecord(), mode="browsing",
    ))
    return cof, cost, decision


def run_cof2():
    """Qualita Rossa Whole Bean 2.2 lb, $24.99, code seen not tested."""
    from deal_finder.decision import decide
    cof = Candidate(
        id="lavazza-rossa",
        variant="Qualita Rossa Whole Bean, 2.2 lb",
        quantity_terms="1x 2.2 lb bag", condition="new", bundle="single",
        seller="Lavazza", fulfilled_by="Lavazza", region="US", in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source=COF2_URL, observed_at=TS_COF2,
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(item_price=24.99, shipping=None, known_tax=None)
    decision = decide(DecisionInput(
        candidates=[cof],
        ranked=[RankedCandidate("lavazza-rossa", cost)],
        coupons=[Coupon(code=LAVAZZA_CODE, merchant="Lavazza",
                        status="retailer-stated")],
        consent=ConsentRecord(), mode="browsing",
    ))
    return cof, cost, decision


def run_cof3():
    """Dolcevita Classico Whole Bean 12 oz, $13.99, code seen not tested."""
    from deal_finder.decision import decide
    cof = Candidate(
        id="lavazza-classico",
        variant="Dolcevita Classico Whole Bean, 12 oz",
        quantity_terms="1x 12 oz bag", condition="new", bundle="single",
        seller="Lavazza", fulfilled_by="Lavazza", region="US", in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source=COF3_URL, observed_at=TS_COF3,
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(item_price=13.99, shipping=None, known_tax=None)
    decision = decide(DecisionInput(
        candidates=[cof],
        ranked=[RankedCandidate("lavazza-classico", cost)],
        coupons=[Coupon(code=LAVAZZA_CODE, merchant="Lavazza",
                        status="retailer-stated")],
        consent=ConsentRecord(), mode="browsing",
    ))
    return cof, cost, decision


def run_specific_super_crema():
    """Named-product search: Super Crema 2.2 lb.

    Lavazza direct is the only seller whose page loads (Target, Walmart,
    and Kroger checks were blocked or unreachable, so those sellers stay
    unverified and are not counted). One verified candidate: buy.
    """
    return run_cof1()


TS_HCR = "2026-10-02T15:00:17Z"
TS_WEL = "2026-10-02T15:01:25Z"
TS_CCC = "2026-10-02T15:03:57Z"
HCR_URL = ("https://www.honest.coffee/shop-3Ooj8/p/"
           "nguvu-bcntn-ksj2y-dy3ra-jzxhp-9wphr")
WEL_URL = "https://wellcoffeeroasters.com/products/watershed"
CCC_URL = ("https://counterculturecoffee.com/collections/coffee/products/"
           "big-trouble")


def run_hcr():
    """Honest Midnight Axes 12oz, $18.00 one-time, no coupon seen."""
    from deal_finder.decision import decide
    hcr = Candidate(
        id="honest-midnight-axes",
        variant="Midnight Axes dark roast, 12 oz bag (whole bean on bag)",
        quantity_terms="1x 12 oz bag", condition="new", bundle="single",
        seller="Honest Coffee Roasters",
        fulfilled_by="Honest Coffee Roasters", region="US", in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source=HCR_URL, observed_at=TS_HCR,
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(item_price=18.0, shipping=None, known_tax=None)
    decision = decide(DecisionInput(
        candidates=[hcr],
        ranked=[RankedCandidate("honest-midnight-axes", cost)],
        coupons=[], consent=ConsentRecord(), mode="browsing",
    ))
    return hcr, cost, decision


def run_wel():
    """Well Watershed 12oz Whole Bean, $20.50, email offer is not a coupon."""
    from deal_finder.decision import decide
    wel = Candidate(
        id="well-watershed",
        variant="Watershed light roast, 12 oz bag, Whole Bean",
        quantity_terms="1x 12 oz bag", condition="new", bundle="single",
        seller="The Well Coffee Roasters",
        fulfilled_by="The Well Coffee Roasters", region="US", in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source=WEL_URL, observed_at=TS_WEL,
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(item_price=20.5, shipping=None, known_tax=None)
    decision = decide(DecisionInput(
        candidates=[wel],
        ranked=[RankedCandidate("well-watershed", cost)],
        coupons=[], consent=ConsentRecord(), mode="browsing",
    ))
    return wel, cost, decision


def run_ccc():
    """Counter Culture Big Trouble 12oz, $19.50 one-time, no coupon seen."""
    from deal_finder.decision import decide
    ccc = Candidate(
        id="ccc-big-trouble",
        variant="Big Trouble medium-dark roast, 12 oz bag "
                "(whole bean on bag)",
        quantity_terms="1x 12 oz bag", condition="new", bundle="single",
        seller="Counter Culture Coffee",
        fulfilled_by="Counter Culture Coffee", region="US", in_stock=True,
        evidence_state=EvidenceState.OBSERVED_NOW,
        source=CCC_URL, observed_at=TS_CCC,
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(item_price=19.5, shipping=None, known_tax=None)
    decision = decide(DecisionInput(
        candidates=[ccc],
        ranked=[RankedCandidate("ccc-big-trouble", cost)],
        coupons=[], consent=ConsentRecord(), mode="browsing",
    ))
    return ccc, cost, decision


DECISION_BADGE = {
    "buy": ("badge-success", "Good to buy"),
    "wait": ("badge-info", "Worth a wait"),
    "verify": ("badge-warning", "Check first"),
    "abstain": ("badge-error", "Skipped"),
}


PAGE_READ_LABEL = "Price read from the store page"


def savings_block(item):
    """Shelf price, the page-printed coupon (never applied), and what is unknown.

    Every fact is read from the stored page evidence; the coupon is quoted in
    the page's own words and never turned into a lower price.
    """
    t = item.get("terms") or {}
    cp = item["coupon"]
    rows = []
    confirm_html = []
    if cp is None:
        status = "No coupon printed on the page"
        rows.append(
            "<li>No coupon code was visible when this page was checked ("
            + esc(item["page_host"]) + ", " + esc(item["region"]) + ", "
            + esc(item["observed_at"]) + ").</li>")
    else:
        status = "Coupon printed, not applied"
        offer = cp["offer"].rstrip(".")
        if not offer.startswith("\u201c"):
            offer = "\u201c" + offer + "\u201d"
        rows.append(
            '<li data-coupon-row><span class="fs" data-coupon-label>'
            "Coupon on this page:</span> "
            '<span class="mono">' + esc(cp["code"])
            + "</span> \u2014 the page says " + esc(offer)
            + ". Conditions: only as that wording states them. Seen on "
            + esc(item["page_host"]) + ", " + esc(item["region"]) + ", "
            + esc(item["observed_at"]) + ". <strong>Not applied:</strong> "
            + esc(cp["caveat"]) + "</li>")
        w = cp.get("window")
        if w:
            rows.append(
                '<li data-window-row data-window-start="' + w["start"]
                + '" data-window-end="' + w["end"]
                + '"><span class="fs">Window the page prints:</span> '
                "\u201c" + esc(w["quote"]) + "\u201d (read as " + w["start"]
                + " to " + w["end"] + "). "
                '<strong data-window-status>Compare it with today\'s date.</strong></li>')
        else:
            rows.append(
                '<li data-window-row><span class="fs">Window the page prints:</span> '
                "<strong data-window-status>the coupon text states no date window "
                "(or only one that is not a clear start and end), so no window is shown."
                "</strong></li>")
        if cp.get("conditions"):
            rows.append(
                '<li data-conditions-row><span class="fs">Conditions the page prints:</span> '
                + " ".join("\u201c" + esc(c) + "\u201d" for c in cp["conditions"])
                + "</li>")
        confirm_html.append('<span data-confirm-code>whether the code works and what it would take off</span>')
    parts = ["tax"]
    if not t.get("ship"):
        parts.append("shipping cost (the page did not state it)")
    confirm_text = esc("; ".join(parts))
    if confirm_html:
        confirm_text += "; " + "; ".join(confirm_html)
    rows.append('<li><span class="fs">Confirm at checkout:</span> '
                + confirm_text + ".</li>")
    return (
        '<div class="savings-box" data-savings>'
        '<p class="fs" data-saving-lead>'
        '<span data-shelf-line>' + esc(item["price_label"])
        + ' as printed on the page</span>. '
        '<span data-saving-status>' + status + "</span>.</p>"
        "<ul>" + "".join(rows) + "</ul></div>")


def _offer_quote(cp):
    offer = cp["offer"].rstrip(".")
    return offer if offer.startswith("“") else "“" + offer + "”"


def _short_money(c):
    return "$%d" % (c // 100) if c % 100 == 0 else _money(c)


def facts_strip(item):
    """Size, shipping and subscribe in a few words, from what the page stated.

    Anything the page did not say reads "not stated — unknown", never "no"
    and never a guess. The full wording is in the card's details.
    """
    t = item.get("terms") or {"group": None, "sizes": []}
    unknown = '<span class="u">not stated — unknown</span>'
    sizes = t.get("sizes") or []
    if sizes:
        size = "%d size%s listed" % (len(sizes), "" if len(sizes) == 1 else "s")
        if all(s["ok"] is False for s in sizes):
            size += ", none shown in stock"
        size = esc(size)
    else:
        size = unknown
    ship = t.get("ship")
    if not ship:
        shipping = unknown
    elif ship["k"] == "free":
        shipping = "free shipping"
    elif ship["k"] == "threshold":
        shipping = esc("free over " + _short_money(ship["over"]) + (
            " (members only)" if ship.get("members") else ""))
    else:
        shipping = esc("shipping " + _short_money(ship["rate"]))
    sub = "offered" if t.get("sub") else unknown
    return ('<p class="facts" data-facts>' + "".join(
        "<span><b>" + k + ":</b> " + v + "</span>"
        for k, v in (("Size", size), ("Shipping", shipping),
                     ("Subscribe", sub))) + "</p>")


def coupon_line(item):
    """The printed coupon in the page's own words, and that it is not applied."""
    cp = item["coupon"]
    if cp is None:
        return ""
    return (
        '<p class="coupon" data-coupon-line><b data-coupon-lead>Printed coupon '
        '<span class="code">' + esc(cp["code"]) + "</span></b> — the page says "
        '<span class="quote">' + esc(_offer_quote(cp)) + "</span>"
        '<span data-coupon-ended></span> '
        "<b>Not applied:</b> the price above is the shelf price and does not "
        "include it.</p>")


def product_card(item, decision, coupon_html, index=0):
    """One product: a compact card (name, store, shelf price, check age, printed
    coupon status, unknowns, one tap to the store) with the full detail behind
    a native disclosure on the same card."""
    badge, label = DECISION_BADGE[decision.verdict.value]
    parts = []
    parts.append('<section class="card item" data-i="' + str(index)
                 + '" data-keywords="' + esc(" ".join(item["keywords"]))
                 + '" data-name="' + esc(item["name"]) + '" data-kind="' + esc(item["kind"]) + '" data-coupon="'
                 + ("yes" if item["coupon"] else "no") + '" data-price="'
                 + str(item["price_cents"])
                 + '" data-price-label="' + esc(item["price_label"])
                 + '" data-coupon-code="'
                 + esc(item["coupon"]["code"] if item["coupon"] else "")
                 + '"' + (' data-coffee-note="yes"' if item.get("coffee_note") else "")
                 + ' data-terms="' + esc(terms_json(item.get("terms")))
                 + '">')
    parts.append('<div class="card-main">')
    if item["image"]:
        parts.append(
            '<img src="' + esc(item["image"]) + '" alt="Photo of '
            + esc(item["name"]) + ' as shown on the store page" '
            'loading="lazy" decoding="async" width="96" height="96">')
    else:
        parts.append('<div class="nophoto" role="img" aria-label="No photo was '
                     'captured for this product">No photo captured</div>')
    parts.append('<div class="card-head">')
    parts.append('<p class="meta">' + esc(item["kind"]) + " · " + esc(item["seller"]) + "</p>")
    parts.append('<h3 data-heading>' + esc(item["name"]) + "</h3>")
    parts.append('<p class="var">' + esc(item["detail"]) + "</p>")
    parts.append('<div class="priceline"><span class="price" data-price-text>'
                 + esc(item["price_label"]) + "</span><small>shelf price</small></div>")
    if item["was_label"]:
        parts.append('<p class="was">was ' + esc(item["was_label"])
                     + " (as marked on the page)</p>")
    parts.append('<p class="size-line" data-size-line style="display:none"></p>')
    parts.append("</div></div>")
    if item.get("page_read"):
        # One page read, nothing compared: say what was established, no verdict.
        parts.append('<p class="readline"><span class="fs" data-page-read>'
                     + PAGE_READ_LABEL + '</span> · <span>Not compared with other stores.</span></p>')
    parts.append('<p class="line sm" data-age data-observed="' + esc(item["observed_at"])
                 + '">Checked ' + esc(item["observed_at"][:10]) + "</p>")
    if item["coupon"]:
        parts.append(coupon_line(item))
    parts.append(facts_strip(item))
    parts.append('<div class="cardfoot"><a class="go" href="' + esc(item["page_url"])
                 + '" target="_blank" rel="noopener">See at ' + esc(item["seller"])
                 + " →</a></div>")
    parts.append('<details class="more"><summary>Full details: savings, coupon '
                 "window, what to confirm, terms</summary>"
                 '<div class="more-body">')
    if not item.get("page_read"):
        parts.append(
            '<div class="status"><span class="big">✓ ' + esc(label) + "</span>"
            '<span class="sm">Price as read from the page.</span></div>')
    if item["quality"] and not item.get("band"):
        parts.append('<p class="line"><span class="fs">'
                     + esc(item["quality"]["label"])
                     + '</span> <span>— '
                     + esc(item["quality"]["basis"]) + "</span></p>")
    if item.get("band"):
        parts.append('<p class="line"><span class="fs">Specialty band: </span>'
                     + esc(item["band"]) + "</p>")
    parts.append(coupon_html)
    if decision.verdict.value == "verify" and decision.manual_check:
        parts.append('<div class="banner">' + esc(decision.manual_check) + "</div>")
    parts.append(terms_block(item))
    parts.append('<ul class="fine">'
                 + "".join("<li>" + esc(n) + "</li>" for n in item["fine_print"])
                 + "</ul>")
    parts.append(
        '<p class="src">Checked: ' + esc(item["page_host"]) + " · " + esc(item["region"])
        + " · " + esc(item["observed_at"]) + "</p>"
    )
    parts.append("</div></details></section>")
    return "\n".join(parts)


def terms_json(t):
    """The terms the page stated, as the page script reads them."""
    t = t or {"group": None, "sizes": []}
    return json.dumps({
        "g": t.get("group"), "z": t.get("sizes") or [],
        "sh": t.get("ship"), "sb": t.get("sub"),
    }, separators=(",", ":"), ensure_ascii=False)


def _money(c):
    return "$%.2f" % (c / 100.0)


def terms_block(item):
    """What the product's own page stated about size, shipping, subscribe.

    Silent pages say unknown; nothing is filled in or computed.
    """
    t = item.get("terms") or {"group": None, "sizes": []}
    sizes = t.get("sizes") or []
    unknown = "not stated on the page \u2014 unknown"
    if t.get("group") == "coffee":
        size_txt = " \u00b7 ".join(
            s["k"] + " " + _money(s["c"]) for s in sizes) + " (shelf prices)"
    elif sizes:
        have = [s["k"] for s in sizes if s["ok"] is not False]
        out = [s["k"] for s in sizes if s["ok"] is False]
        size_txt = "listed: " + ", ".join(s["k"] for s in sizes)
        if out:
            size_txt += " \u2014 not shown in stock when checked: " + ", ".join(out)
        elif not have:
            size_txt += " \u2014 stock not stated"
    else:
        size_txt = unknown
    ship = t.get("ship")
    ship_txt = ship["t"] if ship else unknown
    sub = t.get("sub")
    if sub:
        priced = [s for s in sizes if s.get("s") is not None]
        sub_txt = sub["t"]
        if priced:
            sub_txt += ": " + " \u00b7 ".join(
                s["k"] + " " + _money(s["s"]) for s in priced)
    else:
        sub_txt = unknown
    rows = [("Size", size_txt), ("Shipping", ship_txt), ("Subscribe", sub_txt)]
    src = ""
    if t.get("src"):
        src = ('<p class="src">Read ' + esc(t["src"][1])
               + " from " + esc(t["src"][0]) + "</p>")
    return (
        '<div class="terms-box" data-terms-block>'
        '<p class="t">What the page states about this purchase</p>'
        "<ul>"
        + "".join('<li><span class="fs">' + esc(k) + ":</span> "
                  + esc(v) + "</li>" for k, v in rows)
        + "</ul>" + src + "</div>")


def card_for(item, index=0):
    return product_card(item, item["decision"], savings_block(item), index)


def item_dict(key, name, detail, seller, kind, image, price_cents,
              price_label, was_label, decision, coupon, page_url, page_host,
              region, observed_at, fine_print, keywords, quality=None,
              form=None, band=None, base_name=None, terms=None,
              page_read=False):
    return {
        "key": key, "name": name, "detail": detail, "seller": seller,
        "kind": kind, "image": image,
        "price_cents": price_cents, "price_label": price_label,
        "was_label": was_label, "decision": decision, "coupon": coupon,
        "page_url": page_url, "page_host": page_host, "region": region,
        "observed_at": observed_at, "fine_print": fine_print,
        "keywords": keywords, "quality": quality, "form": form,
        "band": band, "base_name": base_name, "terms": terms,
        "page_read": page_read, "coffee_note": False,
    }


KIND_WORDS = {
    "Shoes": ["shoes", "footwear"],
    "Clothing": ["clothing", "clothes", "apparel", "wear"],
    "Home": ["home"],
    "Pets": ["pets", "pet"],
    "Kitchen": ["kitchen", "cooking"],
    "Outdoors": ["outdoors", "outdoor", "camping", "hiking"],
    "Tea": ["tea", "drink"],
    "Pantry": ["pantry", "food", "cooking"],
    "Drinks": ["drinks", "drink", "beverage"],
    "Coffee": ["coffee", "beans"],
    "Tech": ["tech", "gadget", "electronics"],
    "Accessories": ["accessories", "wallet", "bag"],
    "Grooming": ["grooming", "beard", "care"],
    "Personal care": ["personal", "care", "bath"],
    "Wellness": ["wellness", "scent"],
    "Office": ["office", "desk"],
}
# A plain product-type word a kind must not hand to every product in it: it is
# added to a product only when that product's own stored page (title and name; for dog and cat also its description) says so.
TITLE_WORDS = (
    ("sneakers", r"\bsneakers?\b", False), ("dog", r"\bdogs?\b", True),
    ("cat", r"\bcats?\b", True), ("phone", r"\b(?:iphone|pixel|phone)\b", False),
    ("bedding", r"\b(?:blanket|pillow|throw|comforter)\b", False),
)
PAGE_CAVEAT = ("Seen on the page but never tried out, so the price shown "
               "does not include it.")
TAX_SHIP_UNKNOWN = ("Tax and shipping weren't shown for this item \u2014 check "
                    "the total at checkout.")
TAX_UNKNOWN = ("Tax wasn't shown for this item \u2014 check the total at "
               "checkout.")
RECHECK = "Recheck the price before paying; store pages change."


def tax_ship_line(t):
    """Only what the stored evidence leaves unknown: tax always (no page
    shows it before checkout), shipping only when no shipping line is stored."""
    return TAX_UNKNOWN if (t or {}).get("ship") else TAX_SHIP_UNKNOWN


def run_catalog_observation(obs):
    """One stored observation -> engine decision (same fail-closed path)."""
    from deal_finder.decision import decide
    cand = Candidate(
        id=obs["id"], variant=obs["name"], quantity_terms="1 item",
        condition="new", bundle="single",
        seller=obs["brand"] or obs["page_host"],
        fulfilled_by=obs["brand"] or obs["page_host"], region="US",
        in_stock=True, evidence_state=EvidenceState.OBSERVED_NOW,
        source=obs["page_url"], observed_at=obs["observed_at"],
        price_determining_states=[EvidenceState.OBSERVED_NOW],
    )
    cost = LandedCost(item_price=obs["price"], shipping=None, known_tax=None)
    coupons = []
    if obs["coupon"]:
        coupons.append(Coupon(code=obs["coupon"]["code"],
                              merchant=obs["brand"] or obs["page_host"],
                              status="retailer-stated"))
    return decide(DecisionInput(
        candidates=[cand], ranked=[RankedCandidate(obs["id"], cost)],
        coupons=coupons, consent=ConsentRecord(), mode="browsing"))


def catalog_item(obs):
    seller = obs["brand"] or obs["page_host"]
    words = set(re.findall(r"[a-z0-9]+", (obs["name"] + " " + seller).lower()))
    words.update(KIND_WORDS.get(obs["kind"], [obs["kind"].lower()]))
    words.add(obs["kind"].lower())
    words.update(terms.SEARCH_WORDS.get(obs["id"], []))
    said = obs.get("title", "") + " " + obs["name"]
    for word, pattern, in_desc in TITLE_WORDS:
        if re.search(pattern, said + (" " + obs.get("desc", "") if in_desc else ""), re.I):
            words.add(word)
    cents = int(round(obs["price"] * 100))
    label = "$%d" % obs["price"] if cents % 100 == 0 else "$%.2f" % obs["price"]
    coupon = None
    if obs["coupon"]:
        page_text = coupon_page_text(obs)
        coupon = {"code": obs["coupon"]["code"],
                  "offer": "\u201c" + obs["coupon"]["text"] + "\u201d",
                  "caveat": PAGE_CAVEAT,
                  "window": printed_window(page_text),
                  "conditions": printed_conditions(page_text)}
    item_terms = terms.for_id(obs["id"], obs["kind"])
    return item_dict(
        obs["id"], obs["name"], seller + " \u00b7 new", seller, obs["kind"],
        ("assets/" + obs["image"]) if obs["image"] else None,
        cents, label, None, run_catalog_observation(obs), coupon,
        obs["page_url"], obs["page_host"], "US", obs["observed_at"],
        [tax_ship_line(item_terms), RECHECK], sorted(words), page_read=True,
        terms=item_terms)


def seed_kinds():
    """seeds.json is where a product's kind is decided; stored evidence keeps
    the kind it was collected under, so a corrected kind is applied here."""
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "seeds.json"),
              encoding="utf-8") as f:
        return {s["id"]: s["kind"] for s in json.load(f)}


def catalog_items(hand_items):
    """Stored evidence -> items, minus products already shown by hand."""
    seen = {(i["page_host"], i["page_url"].rstrip("/").rsplit("/", 1)[-1])
            for i in hand_items.values()}
    obs_ok, _excluded = catalog.load_catalog()
    kinds = seed_kinds()
    obs_ok = [dict(o, kind=kinds.get(o["id"], o["kind"])) for o in obs_ok]
    names = {i["name"] for i in hand_items.values()}
    out = {}
    for o in obs_ok:
        key = (o["page_host"], o["page_url"].rstrip("/").rsplit("/", 1)[-1])
        if key in seen:
            continue
        if o["name"] in names:
            continue  # exact search needs one card per name
        seen.add(key)
        names.add(o["name"])
        out[o["id"]] = catalog_item(o)
    return out


HERE = os.path.dirname(os.path.abspath(__file__))


def catalog_entry(item):
    """The search index row for one card: only what the stored evidence states."""
    t = item.get("terms") or {}
    ship = t.get("ship")
    return {
        "n": item["name"], "m": item["seller"], "k": item["kind"],
        "kw": item["keywords"], "pc": item["price_cents"],
        "pl": item["price_label"], "u": item["page_url"],
        "c": item["observed_at"][:10],
        "cp": item["coupon"]["code"] if item["coupon"] else "",
        "z": [{"k": z["k"], "c": z["c"], "ok": z["ok"]}
              for z in (t.get("sizes") or [])],
        "sh": {"k": ship["k"], "members": bool(ship.get("members"))} if ship else None,
        "sb": 1 if t.get("sub") else 0,
    }


def catalog_json(items):
    """The index as JSON that is safe inside a script element."""
    raw = json.dumps([catalog_entry(i) for i in items], separators=(",", ":"))
    return raw.replace("<", "\\u003c")


def _read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


PAGE_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Find a deal — what the store page actually shows</title>
<style>
{css}</style>
</head>
<body>
<div class="wrap">
<header class="top">
<p class="brand">Deal Finder</p>
<p class="lede">Only products whose store pages were actually read. <span id="range"></span></p>
</header>
<main>
<label class="search-label" for="q">Search products, stores or kinds</label>
<div class="searchbox">
<div class="field">
<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
<input id="q" type="search" autocomplete="off" autocapitalize="off" spellcheck="false" role="combobox" aria-expanded="false" aria-controls="sugg" aria-autocomplete="list" enterkeyhint="done" placeholder="Try “coffee”, “Old Navy” or “sneaker”">
<button type="button" id="clearq" class="clear-x" aria-label="Clear search" style="display:none">×</button>
</div>
<div id="sugg" role="listbox" aria-label="Suggestions" style="display:none"></div>
</div>
<p class="hint" id="hint">Results update as you type. Partial words and small typos are fine.</p>
<noscript><p>Searching needs JavaScript. Nothing is hidden from you otherwise: every checked store page is linked from its product.</p></noscript>

<section id="start" class="start" aria-label="Start with a kind">
<h2>Or start with a kind</h2>
<ul class="tiles" id="tiles"></ul>
<div class="more-kinds">
<button type="button" class="linkbtn" id="morebtn" aria-expanded="false" aria-controls="morekinds">More kinds</button>
<button type="button" class="linkbtn" id="browseall" style="margin-left:16px">Browse all <span id="allcount"></span> checked products</button>
<ul class="kindrow" id="morekinds" style="display:none"></ul>
</div>
<div class="read">
<p><b>How to read this page.</b> The price is the shelf price printed on the store page on the day it was checked. A printed coupon is shown in quotes and is never subtracted. “Unknown” means the page did not say; it is never guessed.</p>
</div>
</section>

<section id="resultsArea" aria-label="Results" style="display:none">
<div id="active"></div>
<details id="refine" class="refine"><summary>Refine results<span id="refine-count"></span></summary><div id="bar"></div></details>
<div class="statusline">
<h2 id="count" aria-live="polite" role="status" tabindex="-1"></h2>
<div class="sortbox" id="sortbox"><label for="sort">Sort</label>
<select id="sort"><option value="rel">Best word match</option><option value="lo">Price, low to high</option><option value="hi">Price, high to low</option></select>
</div>
</div>
<div id="notes"></div>
<p id="coffee-note" class="note" style="display:none">{coffee_note}</p>
<div id="unk" style="display:none"></div>
<div id="empty" class="empty" role="status" style="display:none"></div>
<div id="results">
<h2 id="unk-head" style="display:none">The page doesn’t say — listed separately</h2>
{cards}
</div>
<button type="button" id="show-more" class="showmore" style="display:none">Show more</button>
</section>
</main>
<section class="how"><h3>How these were checked</h3>
<ul>
<li>Pages opened anonymously — nothing added to a bag, no code tried out.</li>
<li>Tax and shipping shown only when the page shows them.</li>
<li>Coupon shown only when its text was seen, with page and time.</li>
</ul>
</section>
</div>
<script type="application/json" id="catalog">{catalog}</script>
<script>
{engine}</script>
<script>
{view}</script>
</body>
</html>
"""


def page_html(cards, catalog, coffee_note):
    """The page: search first, every card written from stored evidence."""
    vals = {"css": _read("page.css"), "cards": cards, "catalog": catalog,
            "coffee_note": coffee_note, "engine": _read("engine.js"),
            "view": _read("view.js")}
    return re.sub(r"\{(css|cards|catalog|coffee_note|engine|view)\}",
                  lambda m: vals[m.group(1)], PAGE_SHELL)


def build():
    _c1, _cost1, d1 = run_lv001()
    _c5, _cost5, d5 = run_lv005()
    _c6, _cost6, d6 = run_lv006()
    _c7, _cost7, d7 = run_lv007()
    _cc1, _ccost1, dc1 = run_cof1()
    _cc2, _ccost2, dc2 = run_cof2()
    _cc3, _ccost3, dc3 = run_cof3()
    _hcr, _hcost, dhcr = run_hcr()
    _wel, _wcost, dwel = run_wel()
    _ccc, _cccost, dccc = run_ccc()
    _sp, _spcost, dsp = run_specific_super_crema()

    tax_ship = TAX_SHIP_UNKNOWN
    lavazza_coupon = {
        "code": LAVAZZA_OFFER[0], "offer": LAVAZZA_OFFER[1], "caveat": LAVAZZA_CAVEAT,
    }
    items = {
        "apple": item_dict(
            "apple", "AirPods Pro 3",
            "White \u00b7 new \u00b7 1 pair \u00b7 sold by Apple", "Apple",
            "Tech", "assets/airpods-pro.jpg",
            24900, "$249", None, d1, None,
            APPLE_URL, "apple.com", "US", TS_APPLE2,
            [tax_ship,
             "Recheck the price before paying; store pages change."],
            ["airpods", "apple", "earbuds", "headphones"],
            band="not checked for other products yet."),
        "oldnavy": item_dict(
            "oldnavy", "High-Waisted SoComfy Wide-Leg Sweatpants",
            "Old Navy \u00b7 new \u00b7 Product #777363", "Old Navy",
            "Clothing", "assets/sweatpants.jpg",
            2500, "$25.00", "$36.99", d5,
            {"code": "EXTRA", "offer": "Extra 30% off (exclusions apply).",
             "caveat": "The code was seen but never tested, so the $25.00 "
                       "price above does not include it."},
            ON_URL, "oldnavy.gap.com", "US", TS_ON,
            [tax_ship,
             "Free shipping over $50 needs a Rewards membership, which was "
             "not signed into during this check."],
            ["sweatpants", "old", "navy", "pants", "fleece"],
            band="not checked for other products yet."),
        "gap": item_dict(
            "gap", "CashSoft Crop Cardigan",
            "Gap \u00b7 Brown and navy blue argyle \u00b7 new", "Gap",
            "Clothing", "assets/cardigan.jpg",
            7995, "$79.95", None, d6, None,
            GAP_URL, "gap.com", "US", TS_GAP,
            ["Store signs advertised select-style offers, but none named a "
             "code for this item \u2014 the $79.95 price stands on its own.",
             tax_ship],
            ["cardigan", "gap", "sweater"],
            band="not checked for other products yet."),
        "nike": item_dict(
            "nike", "Air Jordan OG Women's Shoes",
            "Nike \u00b7 Black/White/University Red \u00b7 new \u00b7 1 pair",
            "Nike", "Shoes", "assets/jordan.jpg", 8797, "$87.97", "$155", d7, None,
            NIKE_URL, "nike.com", "US", TS_NIKE,
            ["The marked-down price is the price checked; no extra savings "
             "math was added.",
             "Members get free shipping over $50, but no membership was "
             "signed into during this check \u2014 shipping wasn't shown.",
             "Tax wasn't shown for this item \u2014 check the total at "
             "checkout."],
            ["nike", "jordan", "shoes", "sneakers"],
            band="not checked for other products yet."),
        "cof1": item_dict(
            "cof1", "Super Crema Whole Bean, 2.2 lb bag",
            "Lavazza \u00b7 medium roast \u00b7 honey, nutty", "Lavazza",
            "Coffee", "assets/super-crema.png",
            2699, "$26.99", None, dc1, lavazza_coupon,
            COF1_URL, "lavazzausa.com", "US", TS_COF1,
            [tax_ship],
            ["coffee", "beans", "lavazza", "super", "crema", "espresso",
             "whole", "bean"],
            band="Not in this band: no small-batch or direct-trade statement seen on the checked pages.",
            form="whole-bean"),
        "cof2": item_dict(
            "cof2", "Qualit\u00e0 Rossa Whole Bean, 2.2 lb bag",
            "Lavazza \u00b7 medium roast \u00b7 chocolate", "Lavazza",
            "Coffee", "assets/rossa.png",
            2499, "$24.99", None, dc2, lavazza_coupon,
            COF2_URL, "lavazzausa.com", "US", TS_COF2,
            [tax_ship],
            ["coffee", "beans", "lavazza", "rossa", "qualita", "espresso",
             "whole", "bean"],
            band="Not in this band: no small-batch or direct-trade statement seen on the checked pages.",
            form="whole-bean"),
        "cof3": item_dict(
            "cof3", "Dolcevita Classico Whole Bean, 12 oz bag",
            "Lavazza \u00b7 filter roast \u00b7 roasted nuts", "Lavazza",
            "Coffee", "assets/classico.png",
            1399, "$13.99", None, dc3, lavazza_coupon,
            COF3_URL, "lavazzausa.com", "US", TS_COF3,
            [tax_ship],
            ["coffee", "beans", "lavazza", "classico", "dolcevita", "filter",
             "whole", "bean"],
            band="Not in this band: no small-batch or direct-trade statement seen on the checked pages.",
            form="whole-bean"),
        "hcr": item_dict(
            "hcr", "Midnight Axes dark roast, 12 oz bag",
            "Honest Coffee Roasters \u00b7 Nicaragua single origin \u00b7 "
            "dark chocolate, bourbon", "Honest Coffee Roasters",
            "Coffee", "assets/midnight-axes.jpg",
            1800, "$18.00", None, dhcr, None,
            HCR_URL, "honest.coffee", "US", TS_HCR,
            [tax_ship,
             "No coupon code was visible on this page.",
             "The bag reads whole-bean coffee; 12 oz one-time purchase."],
            ["coffee", "beans", "honest", "midnight", "axes", "dark",
             "roast", "nashville", "franklin", "whole", "bean"],
            band="In this band: roastery locations plus direct sourcing, stated on honest.coffee; single-origin bag.",
            quality={"tag": "independent-roastery",
                     "label": "Independent roastery",
                     "basis": "roastery in Franklin/Nashville TN plus Alabama + direct "
                              "sourcing, stated on honest.coffee"},
            form="whole-bean"),
        "wel": item_dict(
            "wel", "Watershed light roast, 12 oz bag, Whole Bean",
            "The Well Coffee Roasters \u00b7 Guatemala single origin \u00b7 "
            "orange, almond, chocolate", "The Well Coffee Roasters",
            "Coffee", "assets/watershed.png",
            2050, "$20.50", None, dwel, None,
            WEL_URL, "wellcoffeeroasters.com", "US", TS_WEL,
            [tax_ship,
             "No coupon code was visible; the 10%-off signup needs an email "
             "address, so it stays uncounted.",
             "Free shipping starts at $75; this bag is below that, and the "
             "exact shipping wasn't shown."],
            ["coffee", "beans", "well", "watershed", "light", "nashville",
             "whole", "bean"],
            band="In this band: 'Small Batch Roasted in Nashville' plus direct trade, stated on the page.",
            quality={"tag": "independent-roastery",
                     "label": "Independent roastery",
                     "basis": "\u201cSmall Batch Roasted in Nashville\u201d "
                              "and direct trade, stated on the page"},
            form="whole-bean"),
        "ccc": item_dict(
            "ccc", "Big Trouble medium-dark roast, 12 oz bag",
            "Counter Culture Coffee \u00b7 caramel, nutty, round \u00b7 "
            "roasted in Durham, NC", "Counter Culture Coffee",
            "Coffee", "assets/big-trouble.jpg",
            1950, "$19.50", None, dccc, None,
            CCC_URL, "counterculturecoffee.com", "US", TS_CCC,
            [tax_ship,
             "No coupon code was visible on this page.",
             "The bag reads whole-bean coffee; 12 oz one-time purchase. "
             "Free shipping starts at $30."],
            ["coffee", "beans", "counter", "culture", "big", "trouble",
             "durham", "whole", "bean"],
            band="In this band: roastery training centers plus published transparency reports, stated on counterculturecoffee.com.",
            quality={"tag": "independent-roastery",
                     "label": "Independent roastery",
                     "basis": "roastery with training centers and published "
                              "transparency reports, stated on "
                              "counterculturecoffee.com"},
            form="whole-bean"),
    }

    coffee = [items[k] for k in ("cof3", "cof2", "cof1", "hcr", "wel", "ccc")]
    base_names = {"cof3": "Dolcevita Classico Whole Bean",
                  "cof2": "Qualit\u00e0 Rossa Whole Bean",
                  "cof1": "Super Crema Whole Bean",
                  "hcr": "Midnight Axes dark roast",
                  "wel": "Watershed light roast",
                  "ccc": "Big Trouble medium-dark roast"}
    for k, item in items.items():
        t = terms.HAND[k]
        item["terms"] = dict(t, src=t["src"])
        item["base_name"] = base_names.get(k)
        item["fine_print"] = [tax_ship_line(item["terms"]) if n == tax_ship else n
                              for n in item["fine_print"]]
        item["coffee_note"] = any(item is c for c in coffee)
        # the default size's price is the card's shelf price, never different
        for s in t["sizes"]:
            if s.get("d"):
                assert s["c"] == item["price_cents"], k
    items.update(catalog_items(items))
    all_cards = "\n".join(card_for(items[k], i) for i, k in enumerate(items))
    with_c = [v for v in coffee if v["coupon"]]
    without_c = [v for v in coffee if not v["coupon"]]

    def short(v):
        return v["name"].split(" Whole Bean")[0].split(" dark roast")[0] \
            .split(" light roast")[0].split(" medium-dark")[0]

    def join(names):
        return ", ".join(names[:-1]) + " and " + names[-1]

    coffee_note = (
        "Coffee note: " + join([short(v) for v in with_c])
        + " showed the code " + esc(with_c[0]["coupon"]["code"])
        + " on their own pages; " + join([v["seller"] for v in without_c])
        + " did not. No code was tried, so every price here is the shelf price."
    )

    page = page_html(all_cards, catalog_json(items.values()), coffee_note)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    docs = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "docs", "index.html")
    os.makedirs(os.path.dirname(docs), exist_ok=True)
    src_assets = os.path.join(os.path.dirname(out), "assets")
    dst_assets = os.path.join(os.path.dirname(docs), "assets")
    os.makedirs(dst_assets, exist_ok=True)
    for fn in os.listdir(src_assets):
        shutil.copy2(os.path.join(src_assets, fn), os.path.join(dst_assets, fn))
    with open(docs, "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote " + out)
    print("wrote " + docs)
    print("apple:", d1.verdict.value,
          "| oldnavy:", d5.verdict.value, "| gap:", d6.verdict.value,
          "| nike:", d7.verdict.value,
          "| cof1:", dc1.verdict.value, "| cof2:", dc2.verdict.value,
          "| cof3:", dc3.verdict.value, "| specific:", dsp.verdict.value)


if __name__ == "__main__":
    build()
