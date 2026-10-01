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

import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deal_finder.consent import ConsentRecord  # noqa: E402
from deal_finder.decision import DecisionInput  # noqa: E402
from deal_finder.evidence import Candidate, Coupon, EvidenceState  # noqa: E402
from deal_finder.landed_cost import LandedCost, RankedCandidate  # noqa: E402

TS_OBS1 = "2026-09-30T14:08:20Z"
APPLE_URL = "https://www.apple.com/airpods-pro/"


def esc(s):
    return html.escape(str(s), quote=True)


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


DECISION_BADGE = {
    "buy": ("badge-success", "Good to buy"),
    "wait": ("badge-info", "Worth a wait"),
    "verify": ("badge-warning", "Check first"),
    "abstain": ("badge-error", "Skipped"),
}


def coupon_seen_block(code, offer, page_host, region, observed_at, caveat):
    return (
        '<div class="alert alert-success mb-3" style="min-width:0"><div style="min-width:0">'
        '<div class="font-bold mb-1">Coupon on this page</div>'
        '<p class="mb-1"><span class="font-mono font-bold text-lg">'
        + esc(code) + "</span> \u2014 " + esc(offer) + "</p>"
        '<p class="text-sm opacity-80">Seen on ' + esc(page_host)
        + ", " + esc(region) + ", " + esc(observed_at) + ". " + esc(caveat)
        + "</p></div></div>"
    )


def coupon_none_block(page_host, region, observed_at):
    return (
        '<div class="alert mb-3" style="min-width:0"><div style="min-width:0">'
        '<div class="font-bold mb-1">No coupon on this page</div>'
        '<p class="text-sm opacity-80">No coupon code was visible when this '
        "page was checked (" + esc(page_host) + ", " + esc(region) + ", "
        + esc(observed_at) + ").</p></div></div>"
    )


def product_card(name, detail, price, was_price, decision, coupon_html,
                 page_url, page_host, region, observed_at, fine_print):
    badge, label = DECISION_BADGE[decision.verdict.value]
    parts = []
    parts.append('<section class="card bg-base-100 shadow-xl mb-6">')
    parts.append('<div class="card-body" style="min-width:0">')
    parts.append(
        '<div class="flex flex-wrap items-start justify-between gap-3 mb-1" '
        'style="min-width:0">'
        "<div style=\"min-width:0\">"
        '<h2 class="card-title text-2xl">' + esc(name) + "</h2>"
        '<p class="text-sm opacity-80">' + esc(detail) + "</p>"
        "</div>"
        '<div class="text-right" style="min-width:0">'
        '<div class="text-3xl font-bold">' + esc(price) + "</div>"
    )
    if was_price:
        parts.append('<div class="text-sm opacity-70">was ' + esc(was_price)
                     + " (as marked on the page)</div>")
    parts.append(
        '</div></div>'
        '<p class="mb-3"><span class="badge ' + badge + '">'
        + esc(label) + "</span></p>"
    )
    parts.append(coupon_html)
    if decision.verdict.value == "verify" and decision.manual_check:
        parts.append('<div class="alert alert-warning mb-3"><div>'
                     + esc(decision.manual_check) + "</div></div>")
    parts.append('<ul class="list-disc ml-6 text-sm mb-3">'
                 + "".join("<li>" + esc(n) + "</li>" for n in fine_print)
                 + "</ul>")
    parts.append(
        '<p class="text-xs opacity-70" style="min-width:0;overflow-wrap:anywhere">'
        "Checked: <a class=\"link\" href=\"" + esc(page_url) + "\">"
        + esc(page_host) + "</a> \u00b7 " + esc(region) + " \u00b7 "
        + esc(observed_at) + "</p>"
    )
    parts.append("</div></section>")
    return "\n".join(parts)


def build():
    c1, cost1, d1 = run_lv001()
    c5, cost5, d5 = run_lv005()
    c6, cost6, d6 = run_lv006()
    c7, cost7, d7 = run_lv007()

    body = []
    body.append(product_card(
        "AirPods Pro 3", "White \u00b7 new \u00b7 1 pair \u00b7 sold by Apple",
        "$249", None, d1,
        coupon_none_block("apple.com", "US", TS_APPLE2),
        APPLE_URL, "apple.com", "US", TS_APPLE2,
        fine_print=[
            "Tax and shipping weren't shown for this item \u2014 check the "
            "total at checkout.",
            "Recheck the price before paying; store pages change.",
        ]))
    body.append(product_card(
        "High-Waisted SoComfy Wide-Leg Sweatpants",
        "Old Navy \u00b7 new \u00b7 Product #777363",
        "$25.00", "$36.99", d5,
        coupon_seen_block(
            "EXTRA", "Extra 30% off (exclusions apply).",
            "oldnavy.gap.com", "US", TS_ON,
            "The code was seen but never tested, so the $25.00 price "
            "above does not include it."),
        ON_URL, "oldnavy.gap.com", "US", TS_ON,
        fine_print=[
            "Tax and shipping weren't shown for this item \u2014 check the "
            "total at checkout.",
            "Free shipping over $50 needs a Rewards membership, which was "
            "not signed into during this check.",
        ]))
    body.append(product_card(
        "CashSoft Crop Cardigan",
        "Gap \u00b7 Brown and navy blue argyle \u00b7 new \u00b7 Product #800546",
        "$79.95", None, d6,
        coupon_none_block("gap.com", "US", TS_GAP),
        GAP_URL, "gap.com", "US", TS_GAP,
        fine_print=[
            "Store signs advertised select-style offers, but none named a "
            "code for this item \u2014 the $79.95 price stands on its own.",
            "Tax and shipping weren't shown for this item \u2014 check the "
            "total at checkout.",
        ]))
    body.append(product_card(
        "Air Jordan OG Women's Shoes",
        "Nike \u00b7 Black/White/University Red \u00b7 new \u00b7 1 pair",
        "$87.97", "$155", d7,
        coupon_none_block("nike.com", "US", TS_NIKE),
        NIKE_URL, "nike.com", "US", TS_NIKE,
        fine_print=[
            "The marked-down price is the price checked; no extra savings "
            "math was added.",
            "Members get free shipping over $50, but no membership was "
            "signed into during this check \u2014 shipping wasn't shown.",
            "Tax wasn't shown for this item \u2014 check the total at "
            "checkout.",
        ]))

    page = """<!DOCTYPE html>
<html lang="en" data-theme="luxury">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Deal check \u2014 what the store page actually shows</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/daisyui@5.5.19/daisyui.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/daisyui@5.5.19/themes.css">
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4.2.4/dist/index.global.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  :where(p, h1, h2, h3, h4, li, td, th, .badge) { overflow-wrap: anywhere; }
  :where(img, svg, video, canvas, iframe) { max-width: 100%; height: auto; }
  .wrap { max-width: 64rem; margin: 0 auto; padding: 1.5rem; min-width: 0; }
</style>
</head>
<body>
<div class="wrap">
<header class="mb-6">
<h1 class="text-3xl font-bold mb-2">Deal check</h1>
<p class="mb-2">Four products, checked read-only on the store page: the product, the price,
the decision, and any coupon actually printed on the page. No login, no checkout, no cart test.</p>
<p class="text-sm opacity-80">Prices change \u2014 recheck at checkout. A coupon appears here only
when its text was really seen, with the page and time it was seen.</p>
</header>
"""
    page += "\n".join(body)
    page += """<section class="card bg-base-200 shadow mb-6"><div class="card-body" style="min-width:0">
<h3 class="card-title text-base">How these were checked</h3>
<ul class="list-disc ml-6 text-sm">
<li>Each page was opened anonymously and read \u2014 nothing was added to a bag and no code was tried out.</li>
<li>Tax and shipping are left out whenever the page doesn't show them for the exact item.</li>
<li>Apple shows no public coupon: that is the correct result, not a missing one.</li>
</ul>
</div></section>
</div>
</body>
</html>
"""
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote " + out)
    print("apple:", d1.verdict.value,
          "| oldnavy:", d5.verdict.value, "| gap:", d6.verdict.value,
          "| nike:", d7.verdict.value)


if __name__ == "__main__":
    build()
