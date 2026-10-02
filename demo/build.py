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
    parts.append('<section class="card bg-base-100 shadow mb-5 border border-base-200" '
                 'data-keywords="' + esc(" ".join(item["keywords"]))
                 + '" data-name="' + esc(item["name"]) + '" data-kind="' + esc(item["kind"]) + '" data-coupon="'
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
    parts.append('<p class="text-xs font-semibold tracking-wide opacity-60 mb-1">'
                 + esc(item["kind"]) + " \u00b7 " + esc(item["seller"]) + "</p>")
    parts.append('<div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1" style="min-width:0">'
                 '<h3 class="card-title text-xl" style="min-width:0">'
                 + esc(item["name"]) + "</h3>"
                 '<div class="text-2xl font-extrabold whitespace-nowrap">'
                 + esc(item["price_label"]) + "</div></div>")
    parts.append('<p class="text-sm opacity-80 mb-1">' + esc(item["detail"]) + "</p>")
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
              form=None, band=None):
    return {
        "key": key, "name": name, "detail": detail, "seller": seller,
        "kind": kind, "image": image,
        "price_cents": price_cents, "price_label": price_label,
        "was_label": was_label, "decision": decision, "coupon": coupon,
        "page_url": page_url, "page_host": page_host, "region": region,
        "observed_at": observed_at, "fine_print": fine_print,
        "keywords": keywords, "quality": quality, "form": form,
        "band": band,
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

    all_cards = "\n".join(card_for(items[k]) for k in items)
    coffee = [items[k] for k in ("cof3", "cof2", "cof1", "hcr", "wel", "ccc")]
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
<p class="text-sm font-semibold mb-1">Guide (optional) — <span id="guide-step"></span></p>
<p id="guide-q" class="mb-2"></p>
<div id="guide-opts" class="flex flex-wrap gap-2"></div>
</section>
<p class="text-sm opacity-80 mb-2">""" + coffee_note + """</p>
<p id="no-match" class="alert mb-4" style="display:none">Nothing here matches — only the checked pages below exist, and nothing is invented.</p>
</header>
<section id="all-checked" class="mb-8">
<hr class="section-rule">
<div id="results">
"""
    page += all_cards
    page += """</div>
<p id="exact-note" class="text-sm opacity-80" style="display:none">Other stores for the exact bag (Target, Walmart, Kroger) were blocked or unreachable at check time, so no price from them is shown.</p>
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
const exactNote = document.getElementById("exact-note");
const openBtn = document.getElementById("mode-open");
const exactBtn = document.getElementById("mode-exact");
const results = document.getElementById("results");
const cards = Array.from(results.querySelectorAll("[data-keywords]"));
const OPEN_TEXT = "Kind of thing shows similar checked products. A coupon appears only when that product's own page printed it, and it is never tried out \\u2014 the price shown is the shelf price.";
const EXACT_TEXT = "Exact product is one named item: the closest name match, with its own page's price and any coupon that page printed.";
let exact = false;
const pick = { prefer: "any", form: "", coupon: "all" };
const STEPS = [
  { key: "prefer", q: "What matters most?", opts: [
    ["price", "Lowest price"], ["specialty", "Specialty-roaster quality"]] },
  { key: "form", q: "Whole bean or any coffee?", opts: [
    ["whole-bean", "Whole bean"], ["", "Any coffee"]] },
  { key: "coupon", q: "Only products whose page printed a coupon?", opts: [
    ["yes", "Only with a printed coupon"], ["all", "Show all"]] },
];
let step = 0;
function renderGuide() {
  const stepEl = document.getElementById("guide-step");
  const qEl = document.getElementById("guide-q");
  const box = document.getElementById("guide-opts");
  box.innerHTML = "";
  if (step >= STEPS.length) {
    stepEl.textContent = "done";
    qEl.textContent = "The list below already reflects your answers.";
    box.appendChild(guideBtn("Start over", () => { step = 0; pick.prefer = "any"; pick.form = ""; pick.coupon = "all"; renderGuide(); filter(); }));
    return;
  }
  const s = STEPS[step];
  stepEl.textContent = "question " + (step + 1) + " of " + STEPS.length;
  qEl.textContent = s.q;
  for (const [val, label] of s.opts) {
    box.appendChild(guideBtn(label, () => { pick[s.key] = val; step++; renderGuide(); filter(); }));
  }
  box.appendChild(guideBtn("Skip", () => { step++; renderGuide(); }));
}
function guideBtn(label, fn) {
  const b = document.createElement("button");
  b.className = "btn btn-sm guide-btn";
  b.textContent = label;
  b.addEventListener("click", fn);
  return b;
}
function setMode(open) {
  exact = !open;
  openBtn.setAttribute("aria-pressed", open ? "true" : "false");
  exactBtn.setAttribute("aria-pressed", open ? "false" : "true");
  modeText.textContent = open ? OPEN_TEXT : EXACT_TEXT;
  q.value = open ? "coffee beans" : "super crema";
  filter();
}
function byPrice(a, b) {
  return parseInt(a.getAttribute("data-price"), 10) - parseInt(b.getAttribute("data-price"), 10);
}
function filter() {
  const terms = q.value.toLowerCase().split(/\\s+/).filter(Boolean);
  const visible = [];
  for (const c of cards) {
    const hay = (c.getAttribute("data-keywords") + " " + c.innerText).toLowerCase();
    const hit = terms.every(t => hay.includes(t))
      && (pick.coupon !== "yes" || c.getAttribute("data-coupon") === "yes")
      && (!pick.form || c.getAttribute("data-form") === pick.form);
    c.style.display = "none";
    if (hit) visible.push(c);
  }
  visible.sort(byPrice);
  let shownSet = visible;
  if (exact) {
    // One named item: every term in its name, closest (shortest) name wins.
    const named = visible.filter(c => {
      const nm = c.getAttribute("data-name").toLowerCase();
      return terms.length && terms.every(t => nm.includes(t));
    });
    named.sort((a, b) => a.getAttribute("data-name").length - b.getAttribute("data-name").length);
    shownSet = named.slice(0, 1);
  } else if (pick.prefer === "specialty") {
    const lead = visible.filter(c => c.getAttribute("data-quality") === "independent-roastery");
    shownSet = lead.concat(visible.filter(c => !lead.includes(c)));
  }
  for (const c of shownSet) { c.style.display = ""; results.appendChild(c); }
  noMatch.style.display = shownSet.length ? "none" : "";
  exactNote.style.display = exact && shownSet.length ? "" : "none";
  document.getElementById("result-count").textContent = shownSet.length + " shown.";
}
openBtn.addEventListener("click", () => setMode(true));
exactBtn.addEventListener("click", () => setMode(false));
q.addEventListener("input", filter);
document.getElementById("search-go").addEventListener("click", filter);
renderGuide();
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
