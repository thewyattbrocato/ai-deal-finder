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
            '<li data-coupon-row><span class="font-semibold" data-coupon-label>'
            "Coupon on this page:</span> "
            '<span class="font-mono font-bold">' + esc(cp["code"])
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
                + '"><span class="font-semibold">Window the page prints:</span> '
                "\u201c" + esc(w["quote"]) + "\u201d (read as " + w["start"]
                + " to " + w["end"] + "). "
                '<strong data-window-status>Compare it with today\'s date.</strong></li>')
        else:
            rows.append(
                '<li data-window-row><span class="font-semibold">Window the page prints:</span> '
                "<strong data-window-status>the coupon text states no date window "
                "(or only one that is not a clear start and end), so no window is shown."
                "</strong></li>")
        if cp.get("conditions"):
            rows.append(
                '<li data-conditions-row><span class="font-semibold">Conditions the page prints:</span> '
                + " ".join("\u201c" + esc(c) + "\u201d" for c in cp["conditions"])
                + "</li>")
        confirm_html.append('<span data-confirm-code>whether the code works and what it would take off</span>')
    parts = ["tax"]
    if not t.get("ship"):
        parts.append("shipping cost (the page did not state it)")
    confirm_text = esc("; ".join(parts))
    if confirm_html:
        confirm_text += "; " + "; ".join(confirm_html)
    rows.append('<li><span class="font-semibold">Confirm at checkout:</span> '
                + confirm_text + ".</li>")
    return (
        '<div class="savings-box" data-savings>'
        '<p class="text-sm font-semibold mb-1" data-saving-lead>'
        '<span data-shelf-line>' + esc(item["price_label"])
        + ' as printed on the page</span>. '
        '<span data-saving-status>' + status + "</span>.</p>"
        '<ul class="text-sm" style="list-style:none;margin:0;padding:0">'
        + "".join(rows) + "</ul></div>")


def product_card(item, decision, coupon_html):
    badge, label = DECISION_BADGE[decision.verdict.value]
    parts = []
    parts.append('<section class="card bg-base-100 shadow mb-5 border border-base-200" '
                 'data-keywords="' + esc(" ".join(item["keywords"]))
                 + '" data-name="' + esc(item["name"]) + '" data-kind="' + esc(item["kind"]) + '" data-coupon="'
                 + ("yes" if item["coupon"] else "no") + '" data-price="'
                 + str(item["price_cents"]) + '" data-quality="'
                 + esc(item["quality"]["tag"] if item["quality"] else "")
                 + '" data-form="' + esc(item["form"] or "")
                 + '" data-price-label="' + esc(item["price_label"])
                 + '" data-coupon-code="'
                 + esc(item["coupon"]["code"] if item["coupon"] else "")
                 + '" data-quality-basis="'
                 + esc(item["quality"]["basis"] if item["quality"] else "")
                 + '" data-base-name="' + esc(item.get("base_name") or "")
                 + '"' + (' data-coffee-note="yes"' if item.get("coffee_note") else "")
                 + ' data-terms="' + esc(terms_json(item.get("terms")))
                 + '">')
    parts.append('<div class="card-body" style="min-width:0">')
    parts.append('<div class="flex flex-wrap gap-4" style="min-width:0">')
    if item["image"]:
        parts.append(
            '<img src="' + esc(item["image"]) + '" alt="Photo of '
            + esc(item["name"]) + ' as shown on the store page" '
            'loading="eager" width="140" height="140" '
            'style="width:140px;height:140px;object-fit:cover;border-radius:0.75rem;flex:none;background:#f3f4f6">'
        )
    parts.append('<div style="min-width:0;flex:1 1 16rem">')
    parts.append('<p class="text-xs font-semibold tracking-wide opacity-60 mb-1">'
                 + esc(item["kind"]) + " \u00b7 " + esc(item["seller"]) + "</p>")
    parts.append('<div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1" style="min-width:0">'
                 '<h3 class="card-title text-xl" style="min-width:0" data-heading>'
                 + esc(item["name"]) + "</h3>"
                 '<div class="text-2xl font-extrabold whitespace-nowrap" data-price-text>'
                 + esc(item["price_label"]) + "</div></div>")
    parts.append('<p class="text-sm opacity-80 mb-1">' + esc(item["detail"]) + "</p>")
    parts.append('<p class="guide-why text-sm mb-1" data-why style="display:none"></p>')
    parts.append('<p class="text-sm font-semibold mb-1" data-sub-note style="display:none"></p>')
    if item["was_label"]:
        parts.append('<p class="text-sm opacity-70 mb-1">was '
                     + esc(item["was_label"])
                     + " (as marked on the page)</p>")
    if item["quality"] and not item.get("band"):
        parts.append('<p class="text-sm mt-1"><span class="font-semibold">'
                     + esc(item["quality"]["label"])
                     + '</span> <span class="opacity-70">\u2014 '
                     + esc(item["quality"]["basis"]) + "</span></p>")
    if item.get("band"):
        parts.append('<p class="text-sm mt-1"><span class="font-semibold">'
                     "Specialty band: "
                     + "</span>" + esc(item["band"]) + "</p>")
    if item.get("page_read"):
        # One page read, nothing compared: say what was established, no verdict.
        status = ('<span class="text-lg font-bold" data-page-read>'
                  + PAGE_READ_LABEL + "</span>"
                  '<span class="text-sm opacity-80">Not compared with other stores.</span>')
    else:
        status = ('<span class="text-lg font-bold text-success">\u2713 ' + esc(label) + "</span>"
                  '<span class="text-sm opacity-80">Price as read from the page.</span>')
    parts.append(
        '<div class="flex flex-wrap items-center gap-3 my-3 p-3 rounded-lg bg-base-200" style="min-width:0">'
        + status +
        '<a class="btn btn-primary" href="' + esc(item["page_url"])
        + '" target="_blank" rel="noopener">See at ' + esc(item["seller"])
        + " \u2192</a></div>"
    )
    parts.append('<p class="text-sm mb-1" data-age data-observed="' + esc(item["observed_at"])
                 + '">Checked ' + esc(item["observed_at"][:10]) + "</p>")
    parts.append(coupon_html)
    if decision.verdict.value == "verify" and decision.manual_check:
        parts.append('<div class="alert alert-warning mb-3"><div>'
                     + esc(decision.manual_check) + "</div></div>")
    parts.append(terms_block(item))
    parts.append('<ul class="list-disc ml-6 text-sm mb-2">'
                 + "".join("<li>" + esc(n) + "</li>" for n in item["fine_print"])
                 + "</ul>")
    parts.append(
        '<p class="text-xs opacity-70" style="min-width:0;overflow-wrap:anywhere">'
        "Checked: " + esc(item["page_host"]) + " \u00b7 " + esc(item["region"])
        + " \u00b7 " + esc(item["observed_at"]) + "</p>"
    )
    parts.append("</div></div></div></section>")
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
        src = ('<p class="text-xs opacity-70 mt-1">Read ' + esc(t["src"][1])
               + " from " + esc(t["src"][0]) + "</p>")
    return (
        '<div class="terms-box" data-terms-block>'
        '<p class="text-sm font-semibold mb-1">What the page states about this purchase</p>'
        '<ul class="text-sm" style="list-style:none;margin:0;padding:0">'
        + "".join('<li><span class="font-semibold">' + esc(k) + ":</span> "
                  + esc(v) + "</li>" for k, v in rows)
        + "</ul>" + src + "</div>")


def card_for(item):
    return product_card(item, item["decision"], savings_block(item))


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
    "Shoes": ["shoes", "sneakers", "footwear"],
    "Clothing": ["clothing", "clothes", "apparel", "wear"],
    "Home": ["home", "bedding"],
    "Pets": ["pets", "pet", "dog"],
    "Kitchen": ["kitchen", "cooking"],
    "Outdoors": ["outdoors", "outdoor", "camping", "hiking"],
    "Tea": ["tea", "drink"],
    "Pantry": ["pantry", "food", "cooking"],
    "Drinks": ["drinks", "drink", "beverage"],
    "Coffee": ["coffee", "beans"],
    "Tech": ["tech", "phone", "gadget", "electronics"],
    "Accessories": ["accessories", "wallet", "bag"],
    "Grooming": ["grooming", "beard", "care"],
    "Personal care": ["personal", "care", "bath"],
    "Wellness": ["wellness", "scent"],
    "Office": ["office", "desk"],
}
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
    all_cards = "\n".join(card_for(items[k]) for k in items)
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

    page = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Find a deal — what the store page actually shows</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/daisyui@5.5.19/daisyui.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/daisyui@5.5.19/themes.css">
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4.2.4/dist/index.global.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  :where(p, h1, h2, h3, h4, li, td, th, .badge) { overflow-wrap: anywhere; }
  :where(img, svg, video, canvas, iframe) { max-width: 100%; height: auto; }
  .wrap { max-width: 64rem; margin: 0 auto; padding: 1.5rem; min-width: 0; }
  .mode-btn[aria-pressed="true"], .guide-btn[aria-pressed="true"] { outline: 2px solid currentColor; }
  body { font-size: 1.0625rem; line-height: 1.6; }
  .eyebrow { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; opacity: 0.6; }
  .section-rule { border: 0; border-top: 2px solid currentColor; opacity: 0.15; margin: 0 0 1rem; }
  .mode-btn, .guide-btn { min-height: 2.5rem; }
  .guide-opt { cursor: pointer; display: inline-flex; align-items: center; min-height: 2.5rem; padding: 0 0.9rem; border: 1px solid currentColor; border-radius: 0.5rem; font-size: 0.9rem; opacity: 0.85; }
  .guide-opt input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .guide-opt:has(input:checked) { outline: 2px solid currentColor; font-weight: 700; opacity: 1; }
  .guide-opt:has(input:focus-visible) { outline: 3px solid #1d4ed8; outline-offset: 2px; }
  .guide-sec { margin-bottom: 0.9rem; }
  .guide-sec-title { font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; opacity: 0.6; margin-bottom: 0.4rem; }
  .guide-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 0.9rem 1.25rem; }
  .guide-q { border: 0; padding: 0; margin: 0; min-width: 0; }
  .guide-best { border-left: 4px solid currentColor; background: rgba(127,127,127,0.1); padding: 0.6rem 0.8rem; border-radius: 0.5rem; margin: 0.5rem 0; }
  .terms-box { border-top: 1px solid rgba(127,127,127,0.3); margin: 0.5rem 0; padding-top: 0.5rem; }
  .savings-box { border: 1px solid rgba(127,127,127,0.35); border-radius: 0.5rem; margin: 0.5rem 0 0.75rem; padding: 0.6rem 0.8rem; }
  .savings-box li { margin-bottom: 0.25rem; }
  [data-window-state="ended"] [data-coupon-row], [data-window-state="ended"] [data-window-row] { opacity: 0.65; }
  [data-window-state="ended"] [data-coupon-label], [data-window-state="ended"] [data-window-status] { color: #b45309; }
  .guide-why { border-left: 3px solid currentColor; padding-left: 0.6rem; }
  a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible { outline: 3px solid #1d4ed8; outline-offset: 2px; }
</style>
</head>
<body>
<div class="wrap">
<header class="mb-6">
<p class="eyebrow mb-1">Deal Finder · checked pages only</p>
<h1 class="text-4xl font-extrabold mb-2">Find a deal</h1>
<p class="mb-4 text-lg">Search checked store pages. Price, decision, and coupon only when really seen.</p>
<div class="flex flex-wrap gap-2 mb-2" role="group" aria-label="Search mode">
<button id="mode-open" class="btn mode-btn" aria-pressed="true">Kind of thing</button>
<button id="mode-exact" class="btn mode-btn" aria-pressed="false">Exact product</button>
</div>
<p id="mode-hint" class="text-sm opacity-80 mb-3"><span id="mode-text">Kind of thing shows similar checked products. A coupon appears only when that product's own page printed it, and it is never tried out — the price shown is the shelf price.</span> <span id="result-count" class="font-semibold"></span></p>
<div class="flex gap-2 mb-3" style="min-width:0">
<label class="input input-bordered input-lg flex items-center gap-2 w-full" style="min-width:0">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" width="18" height="18" aria-hidden="true"><path fill-rule="evenodd" d="M9.965 11.026a5 5 0 1 1 1.06-1.06l2.755 2.754a.75.75 0 1 1-1.06 1.06l-2.755-2.754ZM10.5 7a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z" clip-rule="evenodd"/></svg>
<input id="q" type="search" class="grow" style="min-width:0" placeholder="Try &quot;coffee beans&quot; or &quot;super crema&quot;" value="coffee beans" aria-label="Search checked products">
</label>
<button id="search-go" class="btn btn-primary btn-lg flex-none">Search</button>
</div>
<section id="guide" class="border border-base-300 rounded-lg bg-base-100 p-3 mb-3" aria-label="Optional guide" style="min-width:0">
<div class="flex flex-wrap items-baseline justify-between gap-2 mb-3"><p class="text-sm font-semibold">Guide (optional) \u2014 it asks only what would change these results, biggest narrowing first. The number beside an answer is how many results it would leave; an answer that would leave nothing is not offered. Answer any, in any order, and change them anytime.</p><button id="guide-reset" class="btn btn-sm guide-btn" type="button">Reset \u2014 show everything</button></div>
<div id="guide-dyn"></div>
<div id="guide-best" class="guide-best" style="display:none"><p class="eyebrow mb-1">Best under your answers</p><p id="guide-best-text" class="text-sm"></p></div>
<p id="guide-status" class="text-sm font-semibold" role="status" aria-live="polite"></p>
<details id="hidden-by" class="text-sm mt-1" style="display:none"><summary class="cursor-pointer">Hidden by your answers</summary><ul id="hidden-list" class="list-disc ml-6 mt-1"></ul></details>
</section>
<p id="coffee-note" class="text-sm opacity-80 mb-2" style="display:none">""" + coffee_note + """</p>
<div id="no-match" class="alert mb-4" style="display:none" role="status"><div style="min-width:0"><p id="no-match-text" class="font-semibold"></p><div id="no-match-actions" class="flex flex-wrap gap-2 mt-2"></div></div></div>
</header>
<section id="all-checked" class="mb-8">
<hr class="section-rule">
<div id="results">
"""
    page += all_cards
    page += """</div>
<div class="text-center mt-2"><button id="show-more" class="btn" style="display:none">Show more matches</button></div>
</section>
<section class="card bg-base-200 shadow mb-6"><div class="card-body" style="min-width:0">
<h3 class="card-title text-base">How these were checked</h3>
<ul class="list-disc ml-6 text-sm">
<li>Pages opened anonymously — nothing added to a bag, no code tried out.</li>
<li>Tax and shipping shown only when the page shows them.</li>
<li>Coupon shown only when its text was seen, with page and time.</li>
</ul>
</div></section>
</div>
<script>
const q = document.getElementById("q");
const modeText = document.getElementById("mode-text");
const noMatch = document.getElementById("no-match");
const openBtn = document.getElementById("mode-open");
const exactBtn = document.getElementById("mode-exact");
const results = document.getElementById("results");
const cards = Array.from(results.querySelectorAll("[data-keywords]"));
const OPEN_TEXT = "Kind of thing shows similar checked products. A coupon appears only when that product's own page printed it, and it is never tried out — the price shown is the shelf price.";
const EXACT_TEXT = "Exact product is one named item: the closest name match, with its own page's price and any coupon that page printed.";
const PAGE = 12;
let limit = PAGE;
const moreBtn = document.getElementById("show-more");
let exact = false;

// ---- what each product's own page stated (build-time evidence, never filled in)
const NO_TERMS = { g: null, z: [], sh: null, sb: null };
const T = new Map(cards.map(c => {
  const raw = c.getAttribute("data-terms");
  return [c, raw ? JSON.parse(raw) : NO_TERMS];
}));
function fold(s) {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}
// Search text is read once, without the terms block and before any "why" line.
const hays = new Map(cards.map(c => {
  const tb = c.querySelectorAll("[data-terms-block]")[0];
  if (tb) tb.style.display = "none";
  const h = fold(c.getAttribute("data-keywords") + " " + c.innerText);
  if (tb) tb.style.display = "";
  return [c, h];
}));
const shownPrice = new Map(cards.map(c => [c, c.querySelectorAll("[data-price-text]")[0].textContent]));
const shownName = new Map(cards.map(c => [c, c.querySelectorAll("[data-heading]")[0].textContent]));
function fmt(cents) { return "$" + (cents / 100).toFixed(2); }

// ---- answers
const DEFAULTS = { prefer: "price", form: "", coffee_size: "", shoe_size: "", clothing_size: "",
  purchase: "any", shipping: "any", coupon: "all" };
const pick = Object.assign({}, DEFAULTS);
const guideDyn = document.getElementById("guide-dyn");
const guideStatus = document.getElementById("guide-status");
const hiddenBy = document.getElementById("hidden-by");
const hiddenList = document.getElementById("hidden-list");
const bestBox = document.getElementById("guide-best");
const bestText = document.getElementById("guide-best-text");
let spec = [];
let specSig = "";
let renderSig = "";
let controls = [];
const coffeeNote = document.getElementById("coffee-note");
const noMatchText = document.getElementById("no-match-text");
const noMatchActions = document.getElementById("no-match-actions");
const shelfLine = new Map(cards.map(c => [c, c.querySelectorAll("[data-shelf-line]")[0].textContent]));
// How old each stored check is, from its stored time only: whole days, no verdict, no threshold.
const NOW = new Date();  // the one read of "today", for the age line and the printed windows
function checkedAge(iso) {
  const d = iso.slice(0, 10);
  const then = Date.parse(d + "T00:00:00Z");
  const today = Date.UTC(NOW.getUTCFullYear(), NOW.getUTCMonth(), NOW.getUTCDate());
  const days = Math.round((today - then) / 86400000);
  if (isNaN(days) || days < 0) return "Checked " + d;
  if (days === 0) return "Checked today, " + d;
  return "Checked " + days + (days === 1 ? " day" : " days") + " ago, " + d;
}
for (const c of cards) {
  const el = c.querySelectorAll("[data-age]")[0];
  el.textContent = checkedAge(el.getAttribute("data-observed"));
}
// A coupon page's own printed date window against the browser's date (calendar days, ISO strings compare).
// Ended means information only: never an available offer, never a lower price.
function two(n) { return (n < 10 ? "0" : "") + n; }
// Printed ends are US Eastern ("11:59 PM ET"), so "today" is the Eastern calendar date, not the viewer's.
const TODAY = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit" }).format(NOW);
function windowState(start, end) {
  if (!start || !end) return "none";
  if (TODAY < start) return "before";
  if (TODAY > end) return "ended";
  return "inside";
}
const WINDOW_TEXT = {
  before: "Today in US Eastern time (" + TODAY + ") is before the page's printed window.",
  inside: "Today in US Eastern time (" + TODAY + ") is inside the page's printed window. The code is still never tried: confirm it at checkout.",
  ended: "The page's printed window has ended (today in US Eastern time is " + TODAY + "). Shown as information only, not as an available offer.",
};
for (const c of cards) {
  const row = c.querySelectorAll("[data-window-row]")[0];
  if (!row) continue;
  const state = windowState(row.getAttribute("data-window-start"), row.getAttribute("data-window-end"));
  c.setAttribute("data-window-state", state);
  if (state === "none") continue;
  row.querySelectorAll("[data-window-status]")[0].textContent = WINDOW_TEXT[state];
  if (state !== "ended") continue;
  c.querySelectorAll("[data-saving-status]")[0].textContent = "The page's printed window has ended";
  c.querySelectorAll("[data-coupon-label]")[0].textContent = "The page's printed window has ended \u2014 code the page printed, information only:";
  c.querySelectorAll("[data-confirm-code]")[0].textContent = "whether any offer is still available (the page's printed window has ended)";
}

function mk(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function sizeOptions(searched, group) {
  const seen = new Map();
  for (const c of searched) {
    const t = T.get(c);
    if (t.g !== group) continue;
    for (const s of t.z) {
      const e = seen.get(s.k) || { k: s.k, o: s.o, n: 0 };
      e.n += 1;
      seen.set(s.k, e);
    }
  }
  return Array.from(seen.values()).sort((a, b) => (a.o - b.o) || (a.k < b.k ? -1 : 1));
}
function buildSpec(searched) {
  const out = [];
  const has = f => searched.some(f);
  const coffeeCards = searched.filter(c => T.get(c).g === "coffee");
  if (has(c => c.getAttribute("data-form"))) {
    const o = [["", "Anything"]];
    if (has(c => c.getAttribute("data-kind") !== "Coffee")) o.push(["any-coffee", "Any coffee"]);
    o.push(["whole-bean", "Whole bean"]);
    out.push({ id: "form", legend: "What kind?", type: "radio", opts: o });
  }
  if (coffeeCards.length) {
    const o = [["", "Any size"]].concat(sizeOptions(searched, "coffee").map(s => [s.k, s.k]));
    out.push({ id: "coffee_size", reprices: true, legend: "Coffee bag size", type: "radio", opts: o,
      help: "A cheaper 12 oz bag is not the same purchase as a 2 lb or 5 lb bag. Sizes and their prices come only from each product's own page; counts show how many results that size leaves." });
  }
  for (const [g, id, legend] of [["shoe", "shoe_size", "Shoe size"], ["clothing", "clothing_size", "Clothing size"]]) {
    const opts = sizeOptions(searched, g);
    if (opts.length) {
      out.push({ id: id, legend: legend, type: "select",
        opts: [["", "Any size"]].concat(opts.map(s => [s.k, s.k])),
        help: "Only sizes a product's own page listed. A product that does not list your size is hidden, not guessed." });
    }
  }
  if (has(c => T.get(c).sb)) {
    out.push({ id: "purchase", reprices: true, legend: "How you would buy", type: "radio",
      opts: [["any", "Either way"], ["subscribe", "Subscribe (price the page printed)"]],
      help: "Subscribe only counts where the page stated a subscribe option; a printed percent without a price is listed but not ranked." });
  }
  if (has(c => T.get(c).sh)) {
    out.push({ id: "shipping", legend: "Shipping", type: "radio",
      opts: [["any", "Any"], ["free", "Free shipping stated for this purchase"]],
      help: "Counts only where the page stated free shipping and this price qualifies; membership-only offers do not count. Silent pages are unknown." });
  }
  if (has(c => c.getAttribute("data-quality"))) {
    out.push({ id: "prefer", reorder: true, legend: "What matters most?", type: "radio",
      opts: [["price", "Lowest price first"], ["specialty", "Specialty-roaster quality first"]],
      help: "Only changes the order, never removes anything. Specialty roasters lead only where the page states small-batch, direct-trade or similar; the other items follow in the same list, still ordered by shelf price." });
  }
  if (has(c => c.getAttribute("data-coupon") === "yes")) {
    out.push({ id: "coupon", legend: "Which coupons?", type: "radio",
      opts: [["all", "Show all"], ["yes", "Only with a printed coupon"]],
      help: "A printed coupon is a code that product's own page showed. It is never tried and never a lower price — prices stay shelf prices." });
  }
  return out;
}
function countUnder(searched, over) {
  const p = Object.assign({}, pick, over || {});
  let n = 0;
  for (const c of searched) if (!view(c, p).reasons.length) n += 1;
  return exact ? Math.min(n, 1) : n;
}
function orderFor(visible, prefer) {
  if (exact) return visible.slice(0, 1);
  if (prefer === "specialty") {
    const lead = visible.filter(c => c.getAttribute("data-quality") === "independent-roastery");
    return lead.concat(visible.filter(c => !lead.includes(c)));
  }
  return visible;
}
// Which questions are worth asking now, and how much each answer would leave.
function guideModel(searched, visible) {
  const out = [];
  spec.forEach((s, idx) => {
    const m = { s: s, idx: idx, counts: null, show: false, score: 0 };
    if (s.reorder) {
      const a = orderFor(visible, "price").slice(0, PAGE);
      const b = orderFor(visible, "specialty").slice(0, PAGE);
      m.show = pick[s.id] !== DEFAULTS[s.id] || a.some((c, i) => c !== b[i]);
    } else {
      const dflt = DEFAULTS[s.id];
      m.counts = s.opts.map(o => countUnder(searched, { [s.id]: o[0] }));
      const base = m.counts[s.opts.findIndex(o => o[0] === dflt)];
      let least = null;
      s.opts.forEach((o, i) => {
        const n = m.counts[i];
        if (o[0] !== dflt && n > 0 && (n < base || s.reprices)) least = least === null ? n : Math.min(least, n);
      });
      m.show = pick[s.id] !== dflt || least !== null;
      m.score = least === null ? 0 : Math.max(0, base - least);
    }
    out.push(m);
  });
  return out.filter(m => m.show).sort((a, b) => (b.score - a.score) || (a.idx - b.idx));
}
function renderGuide(model) {
  const sig = JSON.stringify(model.map(m => [m.s.id, m.counts, pick[m.s.id], m.s.opts]));
  if (sig === renderSig) return;
  renderSig = sig;
  const ae = document.activeElement;
  const had = ae && ae.getAttribute && ae.getAttribute("data-guide-key")
    ? [ae.getAttribute("data-guide-key"), ae.getAttribute("value")] : null;
  guideDyn.innerHTML = "";
  controls = [];
  if (!model.length) {
    guideDyn.appendChild(mk("p", "text-sm opacity-70", "Nothing to narrow for these results — no answer would change the list. The guide only asks what their pages state."));
    return;
  }
  const grid = mk("div", "guide-grid");
  for (const m of model) {
    const s = m.s;
    const fs = mk("fieldset", "guide-q");
    fs.appendChild(mk("legend", "text-sm font-semibold mb-1", s.legend));
    const text = (o, i) => m.counts ? o[1] + " (" + m.counts[i] + ")" : o[1];
    // an answer that would leave nothing is not offered (unless it is the current one)
    const gone = (o, i) => m.counts && m.counts[i] === 0 && pick[s.id] !== o[0];
    if (s.type === "select") {
      const sel = mk("select", "select select-bordered select-sm w-full");
      sel.setAttribute("aria-label", s.legend);
      sel.setAttribute("data-guide-key", s.id);
      s.opts.forEach((o, i) => {
        if (gone(o, i)) return;
        const opt = mk("option", "", text(o, i));
        opt.setAttribute("value", o[0]);
        sel.appendChild(opt);
      });
      sel.addEventListener("change", () => { pick[s.id] = sel.value; limit = PAGE; filter(); });
      fs.appendChild(sel);
      controls.push({ id: s.id, sel: sel });
    } else {
      const row = mk("div", "flex flex-wrap gap-2");
      s.opts.forEach((o, i) => {
        if (gone(o, i)) return;
        const lab = mk("label", "guide-opt");
        const inp = mk("input");
        inp.setAttribute("type", "radio");
        inp.setAttribute("name", "guide-" + s.id);
        inp.setAttribute("value", o[0]);
        inp.setAttribute("data-guide-key", s.id);
        inp.addEventListener("change", () => {
          if (!inp.checked) return;
          pick[s.id] = o[0];
          limit = PAGE;
          filter();
        });
        lab.appendChild(inp);
        lab.appendChild(mk("span", "", text(o, i)));
        row.appendChild(lab);
        controls.push({ id: s.id, inp: inp, v: o[0] });
      });
      fs.appendChild(row);
    }
    if (s.help) fs.appendChild(mk("p", "text-xs opacity-70 mt-1", s.help));
    grid.appendChild(fs);
  }
  guideDyn.appendChild(grid);
  syncControls();
  if (had) {
    const back = controls.find(c => c.id === had[0] && (c.sel || c.v === had[1]));
    const el = back && (back.sel || back.inp);
    if (el && el.focus) el.focus();
  }
}
function syncControls() {
  for (const c of controls) {
    if (c.sel) c.sel.value = pick[c.id];
    else c.inp.checked = pick[c.id] === c.v;
  }
}
function labelOf(id, v) {
  const s = spec.find(x => x.id === id);
  const o = s && s.opts.find(x => x[0] === v);
  return o ? o[1] : v;
}
function updateSpec(searched) {
  const next = buildSpec(searched);
  const sig = JSON.stringify(next);
  if (sig !== specSig) {
    spec = next;
    specSig = sig;
    for (const key of Object.keys(DEFAULTS)) {
      const s = spec.find(x => x.id === key);
      if (!s || !s.opts.some(o => o[0] === pick[key])) pick[key] = DEFAULTS[key];
    }
  }
}
// Nothing matches: say why and offer the way back, with what each step would restore.
function renderEmpty(searched) {
  noMatchActions.innerHTML = "";
  const add = (label, fn) => {
    const b = mk("button", "btn btn-sm", label);
    b.setAttribute("type", "button");
    b.addEventListener("click", fn);
    noMatchActions.appendChild(b);
  };
  const active = spec.filter(s => !s.reorder && pick[s.id] !== DEFAULTS[s.id]);
  if (active.length) {
    noMatchText.textContent = "No checked page fits all of your answers. Take one back to see more:";
    for (const s of active) {
      const n = countUnder(searched, { [s.id]: DEFAULTS[s.id] });
      if (n > 0) add("Drop “" + s.legend.replace("?", "") + ": " + labelOf(s.id, pick[s.id]) + "” — " + n + " would match", () => {
        pick[s.id] = DEFAULTS[s.id];
        limit = PAGE;
        filter();
      });
    }
    const all = {};
    for (const s of active) all[s.id] = DEFAULTS[s.id];
    const total = countUnder(searched, all);
    if (active.length > 1 || total === 0) {
      add("Reset all answers — " + total + " would match", () => {
        Object.assign(pick, DEFAULTS);
        limit = PAGE;
        filter();
      });
    }
    return;
  }
  const words = q.value.trim();
  noMatchText.textContent = "No checked page matches “" + words + "”" + (exact ? " as one named product" : "")
    + ". Only the checked pages exist and nothing is invented — try fewer or different words.";
  if (words) add("Clear the search — show all " + cards.length + " checked products", () => {
    q.value = "";
    limit = PAGE;
    filter();
  });
  if (exact) add("Switch to Kind of thing — similar checked products", () => setMode(true, true));
}
document.getElementById("guide-reset").addEventListener("click", () => {
  Object.assign(pick, DEFAULTS);
  limit = PAGE;
  syncControls();
  filter();
});

// ---- one product under the current answers: only page-stated facts
function view(c, p) {
  const t = T.get(c);
  const price = parseInt(c.getAttribute("data-price"), 10);
  const v = { shelf: price, size: null, sub: null, subPct: null, reasons: [], resized: false, rank: null, subNote: "" };
  let sz = null;
  if (t.g === "coffee") {
    sz = p.coffee_size ? t.z.find(s => s.k === p.coffee_size) : (t.z.find(s => s.d) || t.z[0]);
    if (sz) { v.size = sz.k; v.shelf = sz.c; v.sub = sz.s; v.subPct = sz.sp; v.resized = !!p.coffee_size; }
  }
  if (p.coffee_size && !sz) v.reasons.push("its page does not list a " + p.coffee_size + " bag (answer: Coffee bag size)");
  for (const [id, g, nm] of [["shoe_size", "shoe", "Shoe size"], ["clothing_size", "clothing", "Clothing size"]]) {
    if (!p[id]) continue;
    const s = t.g === g ? t.z.find(x => x.k === p[id]) : null;
    if (!s) v.reasons.push("its page does not list size " + p[id] + " (answer: " + nm + ")");
    else if (s.ok === false) v.reasons.push("its page lists size " + p[id] + " but it was not shown in stock when checked (answer: " + nm + ")");
    else v.size = s.k;
  }
  if (p.purchase === "subscribe") {
    if (!t.sb) v.reasons.push("its page did not state a subscribe option (answer: Subscribe)");
    else if (v.sub === null) v.subNote = "Subscribe offered, but the page printed no subscribe price" + (v.subPct ? " (" + v.subPct + "% stated)" : "");
  }
  const paid = p.purchase === "subscribe" && v.sub !== null ? v.sub : v.shelf;
  if (p.shipping === "free") {
    const sh = t.sh;
    if (!sh) v.reasons.push("its page did not state shipping, so free shipping is unknown (answer: Shipping)");
    else if (sh.k === "free") { /* stated free */ }
    else if (sh.k === "threshold" && sh.members) v.reasons.push("free shipping is stated only for members (answer: Shipping)");
    else if (sh.k === "threshold") {
      if (paid < sh.over) v.reasons.push("free shipping starts at " + fmt(sh.over) + " and this price is " + fmt(paid) + "; what it costs below that is not stated (answer: Shipping)");
    } else v.reasons.push("its page states a shipping charge, not free shipping (answer: Shipping)");
  }
  if (p.coupon === "yes" && c.getAttribute("data-coupon") !== "yes") v.reasons.push("no coupon code was printed on its own page (answer: Only with a printed coupon)");
  const f = p.form;
  if (f === "any-coffee" && c.getAttribute("data-kind") !== "Coffee") v.reasons.push("it is not coffee (answer: Any coffee)");
  if (f === "whole-bean" && c.getAttribute("data-form") !== "whole-bean") v.reasons.push("its page does not mark it whole bean (answer: Whole bean)");
  v.rank = p.purchase === "subscribe" ? v.sub : v.shelf;
  return v;
}
function shipFact(c) {
  const sh = T.get(c).sh;
  return sh ? sh.t : "shipping not stated on the page (unknown)";
}
function whyShown(c, v, rank, total, terms) {
  const out = [];
  if (exact) out.push("closest name match to “" + q.value.trim() + "”");
  else if (terms.length) out.push("matches “" + q.value.trim() + "”");
  if (pick.form === "whole-bean") out.push("its page marks it whole bean");
  if (pick.form === "any-coffee") out.push("it is coffee");
  if (v.resized) out.push("its page lists the " + v.size + " bag at " + fmt(v.shelf));
  if (pick.shoe_size || pick.clothing_size) out.push("its page lists size " + v.size);
  if (pick.purchase === "subscribe" && v.sub !== null) out.push("its page printed a subscribe price of " + fmt(v.sub) + " (shelf price " + fmt(v.shelf) + ")");
  if (pick.shipping === "free") out.push("its page states its shipping as " + shipFact(c));
  if (pick.coupon === "yes") {
    out.push("its own page printed " + c.getAttribute("data-coupon-code")
      + (c.getAttribute("data-window-state") === "ended" ? " (its printed window has ended: information only, never tried, never a lower price)" : " (seen, never tried")
      + (c.getAttribute("data-window-state") === "ended" ? "" : " — the price is still the shelf price)"));
  }
  const basis = c.getAttribute("data-quality-basis");
  if (pick.prefer === "specialty" && !exact) {
    out.push(basis ? "listed first: " + basis : "listed after the roasters whose pages state a specialty basis");
  }
  if (!exact && total > 1 && pick.prefer === "price" && v.rank !== null) {
    out.push((T.get(c).g === "coffee" && v.size && !v.resized ? v.size + " bag, " : "") + (pick.purchase === "subscribe" ? "subscribe price " : "shelf price ") + fmt(v.rank) + ", " + (rank === 1 ? "lowest" : "#" + rank + " by price") + " of " + total + " shown");
  }
  return out.length ? out.join("; ") : "it is one of the checked product pages";
}
function setMode(open, keepQuery) {
  exact = !open;
  limit = PAGE;
  openBtn.setAttribute("aria-pressed", open ? "true" : "false");
  exactBtn.setAttribute("aria-pressed", open ? "false" : "true");
  modeText.textContent = open ? OPEN_TEXT : EXACT_TEXT;
  if (!keepQuery) q.value = open ? "coffee beans" : "super crema";
  filter();
}
function filter() {
  const terms = fold(q.value).split(/\\s+/).filter(Boolean);
  const searched = [];
  for (const c of cards) {
    const hay = hays.get(c);
    const hit = terms.every(t => hay.includes(t))
      && (!exact || (terms.length && terms.every(t => fold(c.getAttribute("data-name")).includes(t))));
    c.style.display = "none";
    if (hit) searched.push(c);
  }
  updateSpec(searched);
  const views = new Map();
  const visible = [];
  const hidden = [];
  for (const c of searched) {
    const v = view(c, pick);
    views.set(c, v);
    if (v.reasons.length) hidden.push(c);
    else visible.push(c);
  }
  // Lowest effective price first; a product with no printed price for the chosen terms goes last.
  visible.sort((a, b) => {
    const x = views.get(a).rank, y = views.get(b).rank;
    if (x === null || y === null) return (x === null) - (y === null);
    return x - y;
  });
  // One named item: every term in its name, closest (shortest) name wins.
  if (exact) visible.sort((a, b) => a.getAttribute("data-name").length - b.getAttribute("data-name").length);
  let shownSet = orderFor(visible, pick.prefer);
  renderGuide(guideModel(searched, visible));
  syncControls();
  for (const c of cards) {
    c.querySelectorAll("[data-why]")[0].style.display = "none";
    c.querySelectorAll("[data-sub-note]")[0].style.display = "none";
  }
  const total = shownSet.length;
  if (!exact) shownSet = shownSet.slice(0, limit);
  shownSet.forEach((c, i) => {
    const v = views.get(c);
    c.style.display = "";
    results.appendChild(c);
    c.querySelectorAll("[data-price-text]")[0].textContent = v.resized ? fmt(v.shelf) : shownPrice.get(c);
    const base = c.getAttribute("data-base-name");
    c.querySelectorAll("[data-heading]")[0].textContent = v.resized && base ? base + " — " + v.size : shownName.get(c);
    const sn = c.querySelectorAll("[data-sub-note]")[0];
    if (pick.purchase === "subscribe") {
      sn.textContent = v.sub !== null
        ? "Subscribe price the page printed: " + fmt(v.sub) + (v.size ? " for " + v.size : "") + ". Shelf price above is unchanged."
        : v.subNote;
      sn.style.display = "";
    }
    const why = c.querySelectorAll("[data-why]")[0];
    why.textContent = "Shown because " + whyShown(c, v, i + 1, shownSet.length, terms) + ".";
    why.style.display = "";
    c.querySelectorAll("[data-shelf-line]")[0].textContent = v.resized
      ? fmt(v.shelf) + " for the " + v.size + " bag, as printed on the page" : shelfLine.get(c);
  });
  coffeeNote.style.display = shownSet.some(c => c.getAttribute("data-coffee-note") === "yes") ? "" : "none";
  noMatch.style.display = shownSet.length ? "none" : "";
  if (!shownSet.length) renderEmpty(searched);
  else { noMatchText.textContent = ""; noMatchActions.innerHTML = ""; }
  moreBtn.style.display = total > shownSet.length ? "" : "none";
  document.getElementById("result-count").textContent = shownSet.length + " of " + total + " matches shown (" + cards.length + " products checked).";

  // ---- best under the conditions the shopper set (page-stated prices only)
  const conds = ["coffee_size", "shoe_size", "clothing_size", "purchase", "shipping"].filter(k => pick[k] !== DEFAULTS[k]);
  const ranked = visible.filter(c => views.get(c).rank !== null);
  const bagSizes = new Set(ranked.filter(c => T.get(c).g === "coffee").map(c => views.get(c).size));
  bestText.textContent = "";
  if (!exact && conds.length && ranked.length && !pick.coffee_size && bagSizes.size > 1) {
    // Different bag sizes are different purchases; do not call one "best".
    bestText.textContent = "These results come in different bag sizes (" + Array.from(bagSizes).join(", ")
      + "), so a lowest price would compare unlike purchases. Choose a bag size above to see the best price for that size.";
    bestBox.style.display = "";
  } else if (!exact && conds.length && ranked.length) {
    const b = ranked[0], bv = views.get(b);
    const unranked = visible.length - ranked.length;
    bestText.textContent = "Best under your answers: " + shownName.get(b).split(",")[0] + (bv.size ? " — " + bv.size : "")
      + " at " + fmt(bv.rank) + (pick.purchase === "subscribe" ? " (subscribe price the page printed; shelf price " + fmt(bv.shelf) + ")" : " (shelf price)")
      + ". Shipping: " + shipFact(b) + "."
      + (unranked ? " " + unranked + " more match but their pages print no price for these terms, so they are not ranked." : "")
      + " A code seen on a page is never part of this ranking.";
    bestBox.style.display = "";
  } else {
    bestBox.style.display = "none";
  }

  const active = [];
  for (const s of spec) {
    if (pick[s.id] !== DEFAULTS[s.id]) active.push(s.legend.replace("?", "") + ": " + labelOf(s.id, pick[s.id]));
  }
  guideStatus.textContent = (active.length ? "Your answers: " + active.join(" · ") + ". " : "No answers set. ")
    + total + " match, " + hidden.length + " hidden by your answers.";
  hiddenList.innerHTML = "";
  for (const c of hidden.slice(0, PAGE)) {
    const li = document.createElement("li");
    li.textContent = c.getAttribute("data-name") + " — " + views.get(c).reasons.join("; ");
    hiddenList.appendChild(li);
  }
  if (hidden.length > PAGE) {
    const more = document.createElement("li");
    more.textContent = "and " + (hidden.length - PAGE) + " more";
    hiddenList.appendChild(more);
  }
  hiddenBy.style.display = hidden.length ? "" : "none";
}
openBtn.addEventListener("click", () => setMode(true));
exactBtn.addEventListener("click", () => setMode(false));
q.addEventListener("input", () => { limit = PAGE; filter(); });
moreBtn.addEventListener("click", () => { limit += PAGE; filter(); });
document.getElementById("search-go").addEventListener("click", filter);
filter();
</script>
</body>
</html>
"""
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
