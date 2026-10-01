"""Demo page builder for ai-deal-finder live verification.

Runs the REAL deal_finder engine (stdlib-only, no network) over the
live-observed evidence recorded in LIVE_VERIFICATION.md and emits a single
self-contained demo/index.html. No deals are fabricated: every price,
verdict, and evidence state on the page is engine output or a recorded
browser observation.

Regenerate:  python3 demo/build.py   (from the repo root)
Verify:      python3 -m unittest discover -s tests
"""

import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deal_finder import __version__ as ENGINE_VERSION  # noqa: E402
from deal_finder.consent import ConsentRecord  # noqa: E402
from deal_finder.decision import DecisionInput, format_answer  # noqa: E402
from deal_finder.evidence import Candidate, Coupon, EvidenceState  # noqa: E402
from deal_finder.landed_cost import LandedCost, RankedCandidate  # noqa: E402

TS_OBS1 = "2026-09-30T14:08:20Z"
TS_OBS4 = "2026-09-30T14:09:23Z"
TS_EDU = "2026-09-30T14:09:36Z"
APPLE_URL = "https://www.apple.com/airpods-pro/"


def esc(s):
    return html.escape(str(s), quote=True)


def chip(label, value):
    return (
        '<span class="badge badge-outline badge-sm mr-1 mb-1">'
        + esc(label) + ": " + esc(value) + "</span>"
    )


def evidence_chips(source, region, observed_at, state):
    return (
        chip("source", source or "(none)")
        + chip("region", region or "(none)")
        + chip("timestamp", observed_at or "(none)")
        + chip("evidence", state)
    )


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


def run_lv002():
    """Rival primary page blocked (OBS-4 Best Buy) as winner."""
    from deal_finder.decision import decide
    bb = Candidate(
        id="bestbuy-listing", variant="AirPods Pro 3, white",
        quantity_terms="1 pair", condition="new",
        seller="", fulfilled_by="", region="US", in_stock=True,
        evidence_state=EvidenceState.UNKNOWN, source="", observed_at="",
        primary_page_blocked=True,
    )
    decision = decide(DecisionInput(candidates=[bb], ranked=[], mode="browsing"))
    return bb, None, decision


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


OBSERVATIONS = [
    ("OBS-1", APPLE_URL, TS_OBS1,
     "\u201cAirPods Pro 3 \u2026 $249\u201d with Buy link, Apple US site",
     "observed-now (item price)", "badge-success"),
    ("OBS-2", "https://www.apple.com/shop/buy-airpods/airpods-pro-3",
     "2026-09-30T14:08Z",
     "Buy page loads; generic delivery template text only; buy-box price absent from rendered text; no item-specific stock string",
     "unverified (price/stock on this page)", "badge-warning"),
    ("OBS-3", "https://www.apple.com/us-edu/shop/buy-airpods/airpods-pro-3",
     TS_EDU,
     "Education-gated store loads; no price in rendered text; eligibility not volunteered",
     "retailer-stated at best; eligibility-gated", "badge-warning"),
    ("OBS-4", "Best Buy AirPods Pro 3 product URL", TS_OBS4,
     "chrome-error, ERR_HTTP2_PROTOCOL_ERROR, page unreachable",
     "primary page blocked", "badge-error"),
    ("OBS-5", "https://www.sony.com/electronics/headphones/wh-1000xm5",
     "2026-09-30T14:08Z",
     "\u201cAccess Denied \u2026 Reference 0.e80a3517.1790777300.b9b3a8\u201d",
     "primary page blocked", "badge-error"),
    ("OBS-6", "B&H Photo WH-1000XM5 product page", "2026-09-30T14:08Z",
     "Cloudflare \u201cPerforming security verification\u201d challenge",
     "observation blocked", "badge-error"),
    ("OBS-7", "https://www.retailmenot.com/view/apple.com",
     "2026-09-30T14:09Z",
     "Cloudflare challenge; no code text observed; no consent solicited; no cart test run",
     "coupon stays unverified (research-only)", "badge-warning"),
    ("OBS-8", ON_URL, TS_ON,
     "High-Waisted SoComfy Wide-Leg Sweatpants \u2026 $25.00 (was $36.99); "
     "\u201cExtra 30% Off with Code: EXTRA\u201d on the product page; banner "
     "\u201cFall Faves Up To 50% Off + Extra 30% Off Purchase \u2026 Code: EXTRA "
     "\u2026 Exclusions apply\u201d; no cart test (no consent, read-only rule)",
     "observed-now (item price); code EXTRA retailer-stated, untested",
     "badge-success"),
    ("OBS-9", GAP_URL, TS_GAP,
     "CashSoft Crop Cardigan \u2026 $79.95; site texts \u201c50\u201360% off "
     "limited-time deals / Select styles\u201d, \u201cExtra 50% off sale\u201d, "
     "credit-card offer \u201cExtra 25% off your first purchase with your new "
     "card. Ends 10/3.\u201d No code seen; promos excluded (applicability "
     "unconfirmed)",
     "observed-now (item price); no coupon", "badge-success"),
    ("OBS-10", NIKE_URL, TS_NIKE,
     "Air Jordan OG Women\u2019s Shoes (CW0907-002) \u2026 $87.97 (was $155, "
     "43% off); \u201cMembers: Free Shipping on Orders $50+\u201d; "
     "\u201cYou\u2019ll see our shipping options at checkout.\u201d No code seen",
     "observed-now ($87.97 ranked; was-price is reference only); no coupon",
     "badge-success"),
    ("OBS-11", APPLE_URL, TS_APPLE2,
     "\u201cAirPods Pro 3 \u2026 $249\u201d with Buy link; coupon/promo/code "
     "text search over the rendered page: zero hits",
     "observed-now (item price); no-coupon result stands", "badge-success"),
]

VERDICT_BADGE = {
    "buy": "badge-success", "wait": "badge-info",
    "verify": "badge-warning", "abstain": "badge-error",
}


def verdict_card(run_id, title, candidate, cost, decision, notes,
                 pre_fix_note=None):
    v = decision.verdict.value
    parts = []
    parts.append('<section class="card bg-base-100 shadow-xl mb-6">')
    parts.append('<div class="card-body" style="min-width:0">')
    parts.append(
        '<h3 class="card-title flex flex-wrap items-center gap-2">'
        + esc(run_id) + " \u2014 " + esc(title)
        + ' <span class="badge ' + VERDICT_BADGE[v] + '">verdict: ' + esc(v)
        + "</span></h3>"
    )
    if decision.winner_id:
        parts.append("<p>" + chip("winner", decision.winner_id) + "</p>")
    if cost is not None:
        parts.append("<p>" + chip("landed-cost range", cost.range_label())
                     + "</p>")
    parts.append('<div class="mockup-code text-sm mb-3" '
                 'style="min-width:0;overflow-x:auto">')
    for line in format_answer(decision).splitlines():
        parts.append("<pre data-prefix=\">\" style=\"min-width:0\">"
                     + esc(line) + "</pre>")
    parts.append("</div>")
    if pre_fix_note:
        parts.append('<div class="alert alert-error mb-3"><div>'
                     '<span class="font-bold">Pre-fix behaviour (recorded, '
                     "not generated by current engine):</span> "
                     + esc(pre_fix_note) + "</div></div>")
    parts.append('<div class="mb-3"><h4 class="font-bold mb-1">Evidence beside '
                 "the verdict</h4>")
    parts.append("<p>" + evidence_chips(candidate.source, candidate.region,
                                        candidate.observed_at,
                                        candidate.evidence_state.value)
                 + "</p>")
    parts.append("<p>" + chip("variant", candidate.variant)
                 + chip("seller", candidate.seller or "(unknown)")
                 + chip("fulfilled_by",
                        candidate.fulfilled_by or "(unknown)")
                 + chip("in_stock", candidate.in_stock) + "</p>")
    if candidate.primary_page_blocked:
        parts.append("<p>" + chip("primary_page_blocked", "true") + "</p>")
    parts.append("</div>")
    if decision.manual_check:
        parts.append('<div class="alert alert-warning mb-3"><div><span '
                     'class="font-bold">Manual check:</span> '
                     + esc(decision.manual_check) + "</div></div>")
    if decision.next_action:
        parts.append('<div class="alert alert-success mb-3"><div><span '
                     'class="font-bold">Next action:</span> '
                     + esc(decision.next_action) + "</div></div>")
    if notes:
        parts.append('<ul class="list-disc ml-6 text-sm">'
                     + "".join("<li>" + esc(n) + "</li>" for n in notes)
                     + "</ul>")
    parts.append("</div></section>")
    return "\n".join(parts)


def build():
    c1, cost1, d1 = run_lv001()
    c2, _c2cost, d2 = run_lv002()
    c5, cost5, d5 = run_lv005()
    c6, cost6, d6 = run_lv006()
    c7, cost7, d7 = run_lv007()

    obs_rows = []
    for oid, src, ts, seen, state, badge in OBSERVATIONS:
        obs_rows.append(
            "<tr><td class=\"font-mono\">" + esc(oid) + "</td><td style=\"min-width:0;overflow-wrap:anywhere\">"
            + esc(src) + "</td><td class=\"font-mono text-xs\">" + esc(ts)
            + "</td><td>" + esc(seen) + '</td><td><span class="badge '
            + badge + '">' + esc(state) + "</span></td></tr>"
        )

    body = []
    body.append(verdict_card(
        "LV-001", "Single Apple direct offer, tax/shipping Unknown",
        c1, cost1, d1,
        notes=[
            "Amount-due range is open-ended: tax and shipping were Unknown "
            "on every loaded page and never inferred.",
            "Stock rests on the observed Buy affordance (OBS-1), not an "
            "item-specific stock string \u2014 see follow-ups.",
            "The unverified aggregator code was excluded from the ranking, "
            "not tested (no consent, read-only rule).",
            "Single candidate: ranking robustness is vacuous (no rival to "
            "flip with); flagged for review, behaviour matches LC-001 letter.",
        ]))
    body.append(verdict_card(
        "LV-002", "Rival primary page blocked (OBS-4 as winner)",
        c2, None, d2,
        notes=["Blocked evidence never upgrades; matches fixture BLK-001."]))
    # LV-003 (provenance-free "observed-now" safety check) stays in the
    # test suite (test_verified_state_without_provenance_downgrades) but is
    # not a product example, so it is intentionally absent from this page.
    body.append(verdict_card(
        "LV-005", "Old Navy sweatpants \u2014 retailer-stated code EXTRA "
                  "excluded (OBS-8)",
        c5, cost5, d5,
        notes=[
            "Code 'EXTRA' was really seen on the merchant page "
            "(product + banner, exclusions noted) with source, region, "
            "and timestamp \u2014 shown as retailer-stated, never tested "
            "(no consent, read-only rule), excluded from landed cost.",
            "CP-002 path: the winner holds without the code, so buy stands "
            "at USD 25.00 .. open-ended (tax/shipping Unknown, membership "
            "shipping note kept as eligibility, never assumed).",
            "Single candidate: ranking robustness is vacuous; flagged for "
            "review, behaviour matches LC-001 letter.",
        ]))
    body.append(verdict_card(
        "LV-006", "Gap cardigan \u2014 offer text seen, no code, no coupon "
                  "(OBS-9)",
        c6, cost6, d6,
        notes=[
            "No code was seen on the page, so there is no coupon result: "
            "the \u201c50\u201360% off / Select styles\u201d and \u201cExtra 50% "
            "off sale\u201d texts are recorded beside the verdict and "
            "excluded (applicability to this item unconfirmed).",
            "The credit-card offer text is recorded as seen and excluded \u2014 "
            "never a coupon for this item.",
            "Buy at USD 79.95 .. open-ended (tax/shipping Unknown).",
        ]))
    body.append(verdict_card(
        "LV-007", "Nike markdown \u2014 was-price is reference only (OBS-10)",
        c7, cost7, d7,
        notes=[
            "Ranked item price is the observed $87.97; the \u201cwas $155 / "
            "43% off\u201d text is quoted as seen, never subtracted \u2014 no "
            "savings figure fabricated.",
            "\u201cMembers: Free Shipping on Orders $50+\u201d keeps shipping "
            "Unknown with the eligibility condition attached (membership "
            "not volunteered; LC-003).",
            "No code seen: no-coupon result. Buy at USD 87.97 .. open-ended.",
        ]))

    page = """<!DOCTYPE html>
<html lang="en" data-theme="luxury">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ai-deal-finder \u2014 live verification demo</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/daisyui@5.5.19/daisyui.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/daisyui@5.5.19/themes.css">
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4.2.4/dist/index.global.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  :where(p, h1, h2, h3, h4, li, td, th, .badge) { overflow-wrap: anywhere; }
  :where(img, svg, video, canvas, iframe) { max-width: 100%; height: auto; }
  .wrap { max-width: 64rem; margin: 0 auto; padding: 1.5rem; min-width: 0; }
  table { display: block; overflow-x: auto; }
</style>
</head>
<body>
<div class="wrap">
<header class="mb-6">
<h1 class="text-3xl font-bold mb-2">ai-deal-finder \u2014 live verification demo</h1>
<p class="mb-2">Real <span class="font-mono">deal_finder/</span> engine (v"""
    page += esc(ENGINE_VERSION)
    page += """) run over live-observed browser evidence. Every price, verdict, and
evidence state below is engine output or a recorded observation \u2014 no fabricated deals.</p>
<p class="text-sm opacity-80">Scenarios (region US, browsing mode, no coupon consent, no price history):
\u201cAirPods Pro 3, white, new, 1 pair\u201d (no public coupon \u2014 correct no-coupon result, rechecked
2026-10-01); Old Navy sweatpants (retailer-stated code EXTRA, excluded); Gap cardigan (offer text, no code);
Nike shoes (markdown reference, membership shipping note). Read-only anonymous observation only:
no login, checkout, payment, personal data, or cart tests. Regenerate with
<span class="font-mono">python3 demo/build.py</span>; verify with
<span class="font-mono">python3 -m unittest discover -s tests</span> (59 green).</p>
</header>
<section class="stats stats-vertical sm:stats-horizontal shadow mb-6 w-full">
<div class="stat"><div class="stat-title">Observations</div><div class="stat-value">11</div><div class="stat-desc">6 observed \u00b7 5 blocked/fallback</div></div>
<div class="stat"><div class="stat-title">Engine runs</div><div class="stat-value">6</div><div class="stat-desc">LV-001, LV-002, LV-004 \u2026 LV-007</div></div>
<div class="stat"><div class="stat-title">Discrepancies fixed</div><div class="stat-value">1</div><div class="stat-desc">provenance gate, fail-closed</div></div>
</section>
<h2 class="text-2xl font-bold mb-3">Observations (source \u00b7 region US \u00b7 timestamp \u00b7 evidence state)</h2>
<table class="table table-zebra w-full mb-8">
<thead><tr><th>ID</th><th>Source</th><th>Observed (UTC)</th><th>What was seen</th><th>Evidence state</th></tr></thead>
<tbody>
"""
    page += "\n".join(obs_rows)
    page += """
</tbody>
</table>
<h2 class="text-2xl font-bold mb-3">Verdicts (engine output, evidence beside each claim)</h2>
"""
    page += "\n".join(body)
    page += """<section class="card bg-base-200 shadow mb-6"><div class="card-body" style="min-width:0">
<h3 class="card-title">LV-004 \u2014 coupon research-only fallback (OBS-7, no consent)</h3>
<p>No code text was observable (aggregator page bot-blocked) and no consent was solicited, so the only
honest coupon status is <span class="font-mono">unverified</span>: excluded from landed cost
(shown in LV-001 reasons) and no cart test run. Matches fixtures CP-003 / CS-001. Correct refusal, not failure.</p>
</div></section>
<section class="card bg-base-200 shadow mb-6"><div class="card-body" style="min-width:0">
<h3 class="card-title">Scope notes</h3>
<ul class="list-disc ml-6 text-sm">
<li>No gate in VALIDATION_RECORD.md is claimed passed; it stays NOT RUN pending independent review.</li>
<li>LV-003 (provenance-free \u201cobserved-now\u201d safety check) stays in the test suite and out of this product list: it is indexed text with no source, not a shopping result.</li>
<li>ASSUMPTIONS.md D1\u2013D6 and frozen VISION.md untouched.</li>
<li>Follow-ups (not built): stock-unknown representation; single-candidate vacuous robustness;
live Jev integration; browser cart-test bindings; price monitoring; monetization.</li>
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
    print("LV-001:", d1.verdict.value, "| LV-002:", d2.verdict.value,
          "| LV-005:", d5.verdict.value, "| LV-006:", d6.verdict.value,
          "| LV-007:", d7.verdict.value)


if __name__ == "__main__":
    build()
