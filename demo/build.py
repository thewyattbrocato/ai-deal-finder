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


TS_COF1 = "2026-10-01T23:52:52Z"
TS_COF2 = "2026-10-01T23:54:08Z"
TS_COF3 = "2026-10-01T23:55:04Z"
COF1_URL = "https://www.lavazzausa.com/en/whole-bean-coffee/super-crema.4202"
COF2_URL = "https://www.lavazzausa.com/en/whole-bean-coffee/qualita-rossa"
COF3_URL = "https://www.lavazzausa.com/en/whole-bean-coffee/dolcevita-classico"
CAFE20 = ("CAFE20", "20% off coffee (free mug on orders $150+)")
CAFE20_CAVEAT = ("Seen in the store banner but never tried out, so the price "
                 "shown does not include it.")


def run_cof1():
    """Super Crema Whole Bean 2.2 lb, $26.99, code CAFE20 seen not tested."""
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
        coupons=[Coupon(code="CAFE20", merchant="Lavazza",
                        status="retailer-stated")],
        consent=ConsentRecord(), mode="browsing",
    ))
    return cof, cost, decision


def run_cof2():
    """Qualita Rossa Whole Bean 2.2 lb, $24.99, code CAFE20 seen not tested."""
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
        coupons=[Coupon(code="CAFE20", merchant="Lavazza",
                        status="retailer-stated")],
        consent=ConsentRecord(), mode="browsing",
    ))
    return cof, cost, decision


def run_cof3():
    """Dolcevita Classico Whole Bean 12 oz, $13.99, CAFE20 seen not tested."""
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
        coupons=[Coupon(code="CAFE20", merchant="Lavazza",
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


def item_dict(key, name, detail, seller, price_cents, price_label,
              was_label, decision, coupon, page_url, page_host, region,
              observed_at, fine_print, keywords):
    return {
        "key": key, "name": name, "detail": detail, "seller": seller,
        "price_cents": price_cents, "price_label": price_label,
        "was_label": was_label, "decision": decision, "coupon": coupon,
        "page_url": page_url, "page_host": page_host, "region": region,
        "observed_at": observed_at, "fine_print": fine_print,
        "keywords": keywords,
    }


def card_for(item):
    if item["coupon"] is None:
        coupon_html = coupon_none_block(item["page_host"], item["region"],
                                        item["observed_at"])
    else:
        coupon_html = coupon_seen_block(
            item["coupon"]["code"], item["coupon"]["offer"],
            item["page_host"], item["region"], item["observed_at"],
            item["coupon"]["caveat"])
    html_card = product_card(
        item["name"], item["detail"], item["price_label"],
        item["was_label"], item["decision"], coupon_html,
        item["page_url"], item["page_host"], item["region"],
        item["observed_at"], item["fine_print"])
    return html_card.replace(
        '<section class="card',
        '<section data-keywords="' + esc(" ".join(item["keywords"]))
        + '" class="card', 1)


def build():
    _c1, _cost1, d1 = run_lv001()
    _c5, _cost5, d5 = run_lv005()
    _c6, _cost6, d6 = run_lv006()
    _c7, _cost7, d7 = run_lv007()
    _cc1, _ccost1, dc1 = run_cof1()
    _cc2, _ccost2, dc2 = run_cof2()
    _cc3, _ccost3, dc3 = run_cof3()
    _sp, _spcost, dsp = run_specific_super_crema()

    tax_ship = ("Tax and shipping weren't shown for this item \u2014 check "
                "the total at checkout.")
    lavazza_coupon = {
        "code": CAFE20[0], "offer": CAFE20[1], "caveat": CAFE20_CAVEAT,
    }
    items = {
        "apple": item_dict(
            "apple", "AirPods Pro 3",
            "White \u00b7 new \u00b7 1 pair \u00b7 sold by Apple", "Apple",
            24900, "$249", None, d1, None,
            APPLE_URL, "apple.com", "US", TS_APPLE2,
            [tax_ship,
             "Recheck the price before paying; store pages change."],
            ["airpods", "apple", "earbuds", "headphones"]),
        "oldnavy": item_dict(
            "oldnavy", "High-Waisted SoComfy Wide-Leg Sweatpants",
            "Old Navy \u00b7 new \u00b7 Product #777363", "Old Navy",
            2500, "$25.00", "$36.99", d5,
            {"code": "EXTRA", "offer": "Extra 30% off (exclusions apply).",
             "caveat": "The code was seen but never tested, so the $25.00 "
                       "price above does not include it."},
            ON_URL, "oldnavy.gap.com", "US", TS_ON,
            [tax_ship,
             "Free shipping over $50 needs a Rewards membership, which was "
             "not signed into during this check."],
            ["sweatpants", "old", "navy", "pants", "fleece"]),
        "gap": item_dict(
            "gap", "CashSoft Crop Cardigan",
            "Gap \u00b7 Brown and navy blue argyle \u00b7 new", "Gap",
            7995, "$79.95", None, d6, None,
            GAP_URL, "gap.com", "US", TS_GAP,
            ["Store signs advertised select-style offers, but none named a "
             "code for this item \u2014 the $79.95 price stands on its own.",
             tax_ship],
            ["cardigan", "gap", "sweater"]),
        "nike": item_dict(
            "nike", "Air Jordan OG Women's Shoes",
            "Nike \u00b7 Black/White/University Red \u00b7 new \u00b7 1 pair",
            "Nike", 8797, "$87.97", "$155", d7, None,
            NIKE_URL, "nike.com", "US", TS_NIKE,
            ["The marked-down price is the price checked; no extra savings "
             "math was added.",
             "Members get free shipping over $50, but no membership was "
             "signed into during this check \u2014 shipping wasn't shown.",
             "Tax wasn't shown for this item \u2014 check the total at "
             "checkout."],
            ["nike", "jordan", "shoes", "sneakers"]),
        "cof1": item_dict(
            "cof1", "Super Crema Whole Bean, 2.2 lb bag",
            "Lavazza \u00b7 medium roast \u00b7 honey, nutty", "Lavazza",
            2699, "$26.99", None, dc1, lavazza_coupon,
            COF1_URL, "lavazzausa.com", "US", TS_COF1,
            [tax_ship],
            ["coffee", "beans", "lavazza", "super", "crema", "espresso",
             "whole", "bean"]),
        "cof2": item_dict(
            "cof2", "Qualit\u00e0 Rossa Whole Bean, 2.2 lb bag",
            "Lavazza \u00b7 medium roast \u00b7 chocolate", "Lavazza",
            2499, "$24.99", None, dc2, lavazza_coupon,
            COF2_URL, "lavazzausa.com", "US", TS_COF2,
            [tax_ship],
            ["coffee", "beans", "lavazza", "rossa", "qualita", "espresso",
             "whole", "bean"]),
        "cof3": item_dict(
            "cof3", "Dolcevita Classico Whole Bean, 12 oz bag",
            "Lavazza \u00b7 filter roast \u00b7 roasted nuts", "Lavazza",
            1399, "$13.99", None, dc3, lavazza_coupon,
            COF3_URL, "lavazzausa.com", "US", TS_COF3,
            [tax_ship],
            ["coffee", "beans", "lavazza", "classico", "dolcevita", "filter",
             "whole", "bean"]),
    }

    open_cards = "\n".join(card_for(items[k])
                            for k in ("cof3", "cof2", "cof1"))
    best_place = card_for(items["cof1"])
    all_cards = "\n".join(card_for(items[k]) for k in items)

    page = """<!DOCTYPE html>
<html lang="en" data-theme="luxury">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Find a deal \u2014 what the store page actually shows</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/daisyui@5.5.19/daisyui.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/daisyui@5.5.19/themes.css">
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4.2.4/dist/index.global.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  :where(p, h1, h2, h3, h4, li, td, th, .badge) { overflow-wrap: anywhere; }
  :where(img, svg, video, canvas, iframe) { max-width: 100%; height: auto; }
  .wrap { max-width: 64rem; margin: 0 auto; padding: 1.5rem; min-width: 0; }
  .mode-btn[aria-pressed="true"] { outline: 2px solid currentColor; }
</style>
</head>
<body>
<div class="wrap">
<header class="mb-6">
<h1 class="text-3xl font-bold mb-2">Find a deal</h1>
<p class="mb-4">Type what you want. Every result below was read straight off the store page \u2014
the item, the price, where to buy, the decision, and a coupon only when its text was really seen.
No login, no checkout, no cart test.</p>
<div class="flex flex-wrap gap-2 mb-3" role="group" aria-label="Search mode">
<button id="mode-open" class="btn mode-btn" aria-pressed="true">Kind of thing</button>
<button id="mode-exact" class="btn mode-btn" aria-pressed="false">Exact product</button>
</div>
<label class="input input-bordered flex items-center gap-2 w-full mb-2">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" width="16" height="16"><path fill-rule="evenodd" d="M9.965 11.026a5 5 0 1 1 1.06-1.06l2.755 2.754a.75.75 0 1 1-1.06 1.06l-2.755-2.754ZM10.5 7a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z" clip-rule="evenodd"/></svg>
<input id="q" type="search" class="grow" style="min-width:0" placeholder="Try &quot;coffee beans&quot; or &quot;super crema&quot;" value="coffee beans">
</label>
<p id="mode-hint" class="text-sm opacity-80 mb-2">Kind of thing: similar items that were actually seen, cheapest shelf price first.</p>
<p id="no-match" class="alert mb-4" style="display:none">Nothing here matches \u2014 only the checked pages below exist, and nothing is invented.</p>
</header>
<section id="open-example" class="mb-8">
<h2 class="text-2xl font-bold mb-1">Kind of thing \u2014 \u201ccoffee beans\u201d</h2>
<p class="text-sm opacity-80 mb-4">Different blends, not interchangeable: each was checked on its own page with its own decision. Ordered by shelf price.</p>
"""
    page += open_cards
    page += """</section>
<section id="exact-example" class="mb-8">
<h2 class="text-2xl font-bold mb-1">Exact product \u2014 \u201cLavazza Super Crema Whole Bean, 2.2 lb\u201d</h2>
<p class="text-sm opacity-80 mb-4">Best place found: Lavazza direct. The same bag at three other stores
wouldn't load when checked, so those stores aren't counted \u2014 only the page that loaded decides.</p>
"""
    page += best_place
    page += """<div class="alert mb-6"><div><span class="font-bold">Not counted:</span>
Target, Walmart, and Kroger pages were blocked or unreachable at check time, so no price from them is shown.</div></div>
</section>
<section id="all-checked" class="mb-8">
<h2 class="text-2xl font-bold mb-4">Everything checked</h2>
<div id="results">
"""
    page += all_cards
    page += """</div>
</section>
<section class="card bg-base-200 shadow mb-6"><div class="card-body" style="min-width:0">
<h3 class="card-title text-base">How these were checked</h3>
<ul class="list-disc ml-6 text-sm">
<li>Each page was opened anonymously and read \u2014 nothing was added to a bag and no code was tried out.</li>
<li>Tax and shipping are left out whenever the page doesn't show them for the exact item.</li>
<li>A coupon appears only when its text was really seen, with the page and time.</li>
</ul>
</div></section>
</div>
<script>
const q = document.getElementById("q");
const hint = document.getElementById("mode-hint");
const noMatch = document.getElementById("no-match");
const openBtn = document.getElementById("mode-open");
const exactBtn = document.getElementById("mode-exact");
const cards = Array.from(document.querySelectorAll("#results [data-keywords]"));
function setMode(open) {
  openBtn.setAttribute("aria-pressed", open ? "true" : "false");
  exactBtn.setAttribute("aria-pressed", open ? "false" : "true");
  hint.textContent = open
    ? "Kind of thing: similar items that were actually seen, cheapest shelf price first."
    : "Exact product: one named item, best place to buy with coupons seen on the page.";
  q.value = open ? "coffee beans" : "super crema";
  filter();
  document.getElementById(open ? "open-example" : "exact-example").scrollIntoView();
}
function filter() {
  const terms = q.value.toLowerCase().split(/\\s+/).filter(Boolean);
  let shown = 0;
  for (const c of cards) {
    const hay = (c.getAttribute("data-keywords") + " " + c.innerText).toLowerCase();
    const hit = terms.every(t => hay.includes(t));
    c.style.display = hit ? "" : "none";
    if (hit) shown++;
  }
  noMatch.style.display = shown ? "none" : "";
}
openBtn.addEventListener("click", () => setMode(true));
exactBtn.addEventListener("click", () => setMode(false));
q.addEventListener("input", filter);
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
