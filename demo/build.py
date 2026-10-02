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


def product_card(item, decision, coupon_html):
    badge, label = DECISION_BADGE[decision.verdict.value]
    parts = []
    parts.append('<section class="card bg-base-100 shadow-lg mb-5" '
                 'data-keywords="' + esc(" ".join(item["keywords"]))
                 + '" data-kind="' + esc(item["kind"]) + '" data-coupon="'
                 + ("yes" if item["coupon"] else "no") + '" data-price="'
                 + str(item["price_cents"]) + '" data-quality="'
                 + esc(item["quality"]["tag"] if item["quality"] else "")
                 + '" data-form="' + esc(item["form"] or "") + '">')
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
    parts.append('<div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1" style="min-width:0">'
                 '<h2 class="card-title text-xl" style="min-width:0">'
                 + esc(item["name"]) + "</h2>"
                 '<div class="text-2xl font-extrabold whitespace-nowrap">'
                 + esc(item["price_label"]) + "</div></div>")
    parts.append('<p class="text-sm opacity-80 mb-1">' + esc(item["detail"]) + "</p>")
    if item["was_label"]:
        parts.append('<p class="text-sm opacity-70 mb-1">was '
                     + esc(item["was_label"])
                     + " (as marked on the page)</p>")
    if item["quality"]:
        parts.append('<p class="text-sm mt-1"><span class="font-semibold">'
                     + esc(item["quality"]["label"])
                     + '</span> <span class="opacity-70">\u2014 '
                     + esc(item["quality"]["basis"]) + "</span></p>")
    parts.append(
        '<div class="flex flex-wrap items-center gap-3 my-3 p-3 rounded-lg bg-base-200" style="min-width:0">'
        '<span class="text-lg font-bold text-success">\u2713 ' + esc(label) + "</span>"
        '<span class="text-sm opacity-80">Price verified on the page \u2014 recheck at checkout.</span>'
        '<a class="btn btn-primary" href="' + esc(item["page_url"])
        + '" target="_blank" rel="noopener">See at ' + esc(item["seller"])
        + " \u2192</a></div>"
    )
    parts.append(coupon_html)
    if decision.verdict.value == "verify" and decision.manual_check:
        parts.append('<div class="alert alert-warning mb-3"><div>'
                     + esc(decision.manual_check) + "</div></div>")
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


def card_for(item):
    if item["coupon"] is None:
        coupon_html = coupon_none_block(item["page_host"], item["region"],
                                        item["observed_at"])
    else:
        coupon_html = coupon_seen_block(
            item["coupon"]["code"], item["coupon"]["offer"],
            item["page_host"], item["region"], item["observed_at"],
            item["coupon"]["caveat"])
    return product_card(item, item["decision"], coupon_html)


def item_dict(key, name, detail, seller, kind, image, price_cents,
              price_label, was_label, decision, coupon, page_url, page_host,
              region, observed_at, fine_print, keywords, quality=None,
              form=None):
    return {
        "key": key, "name": name, "detail": detail, "seller": seller,
        "kind": kind, "image": image,
        "price_cents": price_cents, "price_label": price_label,
        "was_label": was_label, "decision": decision, "coupon": coupon,
        "page_url": page_url, "page_host": page_host, "region": region,
        "observed_at": observed_at, "fine_print": fine_print,
        "keywords": keywords, "quality": quality, "form": form,
    }


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

    tax_ship = ("Tax and shipping weren't shown for this item \u2014 check "
                "the total at checkout.")
    lavazza_coupon = {
        "code": CAFE20[0], "offer": CAFE20[1], "caveat": CAFE20_CAVEAT,
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
            ["airpods", "apple", "earbuds", "headphones"]),
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
            ["sweatpants", "old", "navy", "pants", "fleece"]),
        "gap": item_dict(
            "gap", "CashSoft Crop Cardigan",
            "Gap \u00b7 Brown and navy blue argyle \u00b7 new", "Gap",
            "Clothing", "assets/cardigan.jpg",
            7995, "$79.95", None, d6, None,
            GAP_URL, "gap.com", "US", TS_GAP,
            ["Store signs advertised select-style offers, but none named a "
             "code for this item \u2014 the $79.95 price stands on its own.",
             tax_ship],
            ["cardigan", "gap", "sweater"]),
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
            ["nike", "jordan", "shoes", "sneakers"]),
        "cof1": item_dict(
            "cof1", "Super Crema Whole Bean, 2.2 lb bag",
            "Lavazza \u00b7 medium roast \u00b7 honey, nutty", "Lavazza",
            "Coffee", "assets/super-crema.png",
            2699, "$26.99", None, dc1, lavazza_coupon,
            COF1_URL, "lavazzausa.com", "US", TS_COF1,
            [tax_ship],
            ["coffee", "beans", "lavazza", "super", "crema", "espresso",
             "whole", "bean"],
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
            quality={"tag": "independent-roastery",
                     "label": "Independent roastery",
                     "basis": "roastery in Franklin/Nashville AL + direct "
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
            quality={"tag": "independent-roastery",
                     "label": "Independent roastery",
                     "basis": "roastery with training centers and published "
                              "transparency reports, stated on "
                              "counterculturecoffee.com"},
            form="whole-bean"),
    }

    open_cards = "\n".join(card_for(items[k])
                            for k in ("cof3", "hcr", "ccc",
                                      "wel", "cof2", "cof1"))
    best_place = card_for(items["cof1"])
    all_cards = "\n".join(card_for(items[k]) for k in items)

    n_total = len(items)
    n_coupon = sum(1 for v in items.values() if v["coupon"])
    cheapest = min(items.values(), key=lambda v: v["price_cents"])

    page = """<!DOCTYPE html>
<html lang="en" data-theme="light">
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
  .mode-btn[aria-pressed="true"], .kind-btn[aria-pressed="true"] { outline: 2px solid currentColor; }
  body { font-size: 1.0625rem; line-height: 1.6; }
</style>
</head>
<body>
<div class="wrap">
<header class="mb-6">
<h1 class="text-4xl font-extrabold mb-2">Find a deal</h1>
<p class="mb-4 text-lg">Type what you want. Every result below was read straight off the store page \u2014
the item, the price, where to buy, the decision, and a coupon only when its text was really seen.
No login, no checkout, no cart test.</p>
<section class="stats stats-vertical sm:stats-horizontal shadow mb-4 w-full bg-base-100" aria-label="At a glance">
<div class="stat"><div class="stat-title">Products checked</div><div class="stat-value">"""
    page += str(n_total)
    page += """</div><div class="stat-desc">across coffee, clothing, shoes, tech</div></div>
<div class="stat"><div class="stat-title">With a coupon on the page</div><div class="stat-value">"""
    page += str(n_coupon)
    page += """</div><div class="stat-desc">codes really seen, never tested</div></div>
<div class="stat"><div class="stat-title">Cheapest checked price</div><div class="stat-value">"""
    page += esc(cheapest["price_label"])
    page += """</div><div class="stat-desc">"""
    page += esc(cheapest["name"])
    page += """</div></div>
</section>
<div class="flex flex-wrap gap-2 mb-3" role="group" aria-label="Search mode">
<button id="mode-open" class="btn mode-btn" aria-pressed="true">Kind of thing</button>
<button id="mode-exact" class="btn mode-btn" aria-pressed="false">Exact product</button>
</div>
<label class="input input-bordered input-lg flex items-center gap-2 w-full mb-2">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" width="18" height="18"><path fill-rule="evenodd" d="M9.965 11.026a5 5 0 1 1 1.06-1.06l2.755 2.754a.75.75 0 1 1-1.06 1.06l-2.755-2.754ZM10.5 7a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z" clip-rule="evenodd"/></svg>
<input id="q" type="search" class="grow" style="min-width:0" placeholder="Try &quot;coffee beans&quot; or &quot;super crema&quot;" value="coffee beans">
</label>
<div class="flex flex-wrap items-center gap-2 mb-2" role="group" aria-label="Narrow by kind">
<button class="btn btn-sm kind-btn" data-kind="" aria-pressed="true">Everything</button>
<button class="btn btn-sm kind-btn" data-kind="Coffee" aria-pressed="false">Coffee</button>
<button class="btn btn-sm kind-btn" data-kind="Clothing" aria-pressed="false">Clothing</button>
<button class="btn btn-sm kind-btn" data-kind="Shoes" aria-pressed="false">Shoes</button>
<button class="btn btn-sm kind-btn" data-kind="Tech" aria-pressed="false">Tech</button>
<label class="label cursor-pointer gap-2 ml-1"><input id="coupon-only" type="checkbox" class="checkbox checkbox-sm"> <span class="label-text">Coupon on the page</span></label>
<select id="sort" class="select select-sm select-bordered" aria-label="Sort results">
<option value="low">Price: low first</option>
<option value="high">Price: high first</option>
</select>
</div>
<p id="mode-hint" class="text-sm opacity-80 mb-2">Kind of thing: similar items that were actually seen, cheapest shelf price first.</p>
<details class="collapse collapse-arrow bg-base-100 border border-base-300 mb-2">
<summary class="collapse-title font-semibold">Guide me \u2014 three quick choices (optional, results stay visible)</summary>
<div class="collapse-content grid gap-3 sm:grid-cols-3" style="min-width:0">
<label class="form-control" style="min-width:0"><span class="label-text font-semibold mb-1">What matters most?</span>
<select id="prefer" class="select select-bordered w-full">
<option value="any">Just looking around</option>
<option value="price">Lowest price first</option>
<option value="roastery">Independent roasteries</option>
</select></label>
<label class="form-control" style="min-width:0"><span class="label-text font-semibold mb-1">Coffee form?</span>
<select id="formsel" class="select select-bordered w-full">
<option value="">Any form</option>
<option value="whole-bean">Whole bean only</option>
</select></label>
<label class="form-control" style="min-width:0"><span class="label-text font-semibold mb-1">Coupons?</span>
<select id="couponsel" class="select select-bordered w-full">
<option value="all">Show everything</option>
<option value="yes">Coupon on the page only</option>
</select></label>
</div>
</details>
<p class="text-xs opacity-70 mb-2">Quality is your call: \u201cIndependent roasteries\u201d shows only items whose pages say so. No brand is ruled out behind your back.</p>
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
const results = document.getElementById("results");
const cards = Array.from(results.querySelectorAll("[data-keywords]"));
const kindBtns = Array.from(document.querySelectorAll(".kind-btn"));
const couponOnly = document.getElementById("coupon-only");
const sortSel = document.getElementById("sort");
const preferSel = document.getElementById("prefer");
const formSel = document.getElementById("formsel");
const couponSel = document.getElementById("couponsel");
let kind = "";
let quality = "";
let form = "";
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
  const visible = [];
  for (const c of cards) {
    const hay = (c.getAttribute("data-keywords") + " " + c.innerText).toLowerCase();
    const hitText = terms.every(t => hay.includes(t));
    const hitKind = !kind || c.getAttribute("data-kind") === kind;
    const wantCoupon = couponOnly.checked || couponSel.value === "yes";
    const hitCoupon = !wantCoupon || c.getAttribute("data-coupon") === "yes";
    const hitQuality = !quality || c.getAttribute("data-quality") === quality;
    const hitForm = !form || c.getAttribute("data-form") === form;
    const hit = hitText && hitKind && hitCoupon && hitQuality && hitForm;
    c.style.display = hit ? "" : "none";
    if (hit) { shown++; visible.push(c); }
  }
  visible.sort((a, b) => {
    const pa = parseInt(a.getAttribute("data-price"), 10);
    const pb = parseInt(b.getAttribute("data-price"), 10);
    return sortSel.value === "high" ? pb - pa : pa - pb;
  });
  for (const c of visible) results.appendChild(c);
  noMatch.style.display = shown ? "none" : "";
}
openBtn.addEventListener("click", () => setMode(true));
exactBtn.addEventListener("click", () => setMode(false));
kindBtns.forEach(b => b.addEventListener("click", () => {
  kind = b.getAttribute("data-kind");
  kindBtns.forEach(x => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
  filter();
}));
couponOnly.addEventListener("change", filter);
sortSel.addEventListener("change", filter);
preferSel.addEventListener("change", () => {
  const v = preferSel.value;
  quality = v === "roastery" ? "independent-roastery" : "";
  if (v === "price") sortSel.value = "low";
  couponSel.value = "all";
  filter();
});
formSel.addEventListener("change", () => { form = formSel.value; filter(); });
couponSel.addEventListener("change", filter);
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
