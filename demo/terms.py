"""Deal conditions a product's own page stated: size, shipping, subscribe.

Offline and read-only. A condition exists here only when the page said it;
anything else is simply absent and the page shows "unknown". Nothing is
computed from a stated condition (no savings, no subscribe price from a
percent), and a code seen on a page is not a condition at all.

Two sources, both stored in the repo:
  * from_evidence(ev, kind): the page's own structured product data already
    stored in demo/evidence/<id>.json (variant sizes with stock, and
    shippingDetails when the page published them).
  * HAND: the ten hand-checked products, re-read in a read-only browser on
    2026-10-02 (sizes, prices per size, shipping line, subscribe offer);
    what each page said is recorded in LIVE_VERIFICATION.md.

Terms shape (all keys optional except "group"/"sizes"):
  group: "coffee" | "shoe" | "clothing" | None
  sizes: [{"k": label, "c": shelf cents at that size | None,
           "s": subscribe cents the page printed | None,
           "sp": subscribe percent the page printed | None,
           "o": sort value, "ok": selectable when read | None, "d": default}]
  ship:  {"k": "free" | "threshold" | "cost", "over": cents, "rate": cents,
          "members": bool, "t": what the page said}
  sub:   {"t": what the page said}      (present only when offered)
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_DIR = os.path.join(HERE, "evidence")


def cents(v):
    return int(round(float(v) * 100))


def _offers(node):
    o = node.get("offers")
    if o is None:
        return []
    return [x for x in (o if isinstance(o, list) else [o]) if isinstance(x, dict)]


def _lead_number(label):
    m = re.match(r"\s*(?:[A-Za-z]+\s+)?(\d+(?:\.\d+)?)", label)
    return float(m.group(1)) if m else 1000.0


def _size_group(labels, kind):
    if not labels:
        return None
    if all(re.fullmatch(r"\d+(?:\.\d+)?", s) for s in labels) and kind == "Shoes":
        return "shoe"
    if all(re.match(r"(?:X{0,2}S|M|L|X{1,3}L)\b", s) for s in labels) \
            and kind == "Clothing":
        return "clothing"
    return None


def _shipping(node_list):
    for n in node_list:
        for of in _offers(n):
            sd = of.get("shippingDetails")
            for d in (sd if isinstance(sd, list) else [sd] if sd else []):
                if not isinstance(d, dict):
                    continue
                th = d.get("freeShippingThreshold")
                rate = d.get("shippingRate")
                if isinstance(th, dict) and th.get("value") not in (None, ""):
                    over = cents(th["value"])
                    us = " (US only)" if d.get("doesNotShip") else ""
                    return {"k": "threshold", "over": over, "members": False,
                            "t": "Free shipping over $%d%s, in the page's own "
                                 "shipping data" % (over // 100, us)}
                if isinstance(rate, dict) and rate.get("value") not in (None, ""):
                    r = cents(rate["value"])
                    if r == 0:
                        return {"k": "free",
                                "t": "Free shipping to the US, in the page's "
                                     "own shipping data"}
                    return {"k": "cost", "rate": r,
                            "t": "Shipping $%.2f, in the page's own shipping "
                                 "data" % (r / 100.0)}
    return None


def from_evidence(ev, kind):
    """Stored evidence record -> terms dict (sizes/shipping only if stated)."""
    prods = ev.get("json_ld") or []
    if not prods:
        return {"group": None, "sizes": []}
    p = prods[0]
    variants = p.get("hasVariant") or []
    sizes, seen = [], set()
    for v in variants:
        s = v.get("size")
        if not s or str(s) in seen:
            continue
        seen.add(str(s))
        stocks = [str(o.get("availability", "")).endswith("InStock")
                  for o in _offers(v)]
        sizes.append({"k": str(s), "c": None, "s": None, "sp": None,
                      "o": _lead_number(str(s)),
                      "ok": any(stocks) if stocks else None})
    if not sizes and p.get("size"):
        stocks = [str(o.get("availability", "")).endswith("InStock")
                  for o in _offers(p)]
        sizes.append({"k": str(p["size"]), "c": None, "s": None, "sp": None,
                      "o": _lead_number(str(p["size"])),
                      "ok": any(stocks) if stocks else None})
    group = _size_group([s["k"] for s in sizes], kind)
    if group is None:
        sizes = []
    out = {"group": group, "sizes": sizes}
    ship = _shipping([p] + variants)
    if ship:
        out["ship"] = ship
    return out


def for_id(ev_id, kind, evidence_dir=EVIDENCE_DIR):
    path = os.path.join(evidence_dir, ev_id + ".json")
    with open(path) as f:
        return from_evidence(json.load(f), kind)


def _size(k, c=None, s=None, sp=None, o=None, ok=None, d=False):
    return {"k": k, "c": c, "s": s, "sp": sp, "o": o, "ok": ok, "d": d}


# Re-read 2026-10-02 (UTC) in a read-only browser; nothing added to a cart,
# no code tried. "src" is the page the terms were read from.
HAND = {
    "cof3": {  # Lavazza Dolcevita Classico
        "src": ("https://www.lavazzausa.com/en/whole-bean-coffee/"
                "dolcevita-classico", "2026-10-02T22:09Z"),
        "group": "coffee",
        "sizes": [_size("12 oz", 1399, None, 25, 12, d=True)],
        "ship": {"k": "threshold", "over": 5000, "members": False,
                 "t": "“Free delivery on orders over $50”"},
        "sub": {"t": "“Subscribe and save 25%” (the subscribe "
                     "price itself is not shown)"},
    },
    "cof2": {  # Lavazza Qualita Rossa
        "src": ("https://www.lavazzausa.com/en/whole-bean-coffee/"
                "qualita-rossa", "2026-10-02T22:09Z"),
        "group": "coffee",
        "sizes": [_size("2.2 lb", 2499, None, 25, 35.2, d=True)],
        "ship": {"k": "threshold", "over": 5000, "members": False,
                 "t": "“Free delivery on orders over $50”"},
        "sub": {"t": "“Subscribe and save 25%” (the subscribe "
                     "price itself is not shown)"},
    },
    "cof1": {  # Lavazza Super Crema
        "src": ("https://www.lavazzausa.com/en/whole-bean-coffee/"
                "super-crema.4202", "2026-10-02T22:09:30Z"),
        "group": "coffee",
        "sizes": [_size("2.2 lb", 2699, None, 25, 35.2, d=True)],
        "ship": {"k": "threshold", "over": 5000, "members": False,
                 "t": "“Free delivery on orders over $50”"},
        "sub": {"t": "“Subscribe and save 25%” (the subscribe "
                     "price itself is not shown)"},
    },
    "hcr": {  # Honest Coffee Roasters Midnight Axes
        "src": ("https://www.honest.coffee/shop-3Ooj8/p/"
                "nguvu-bcntn-ksj2y-dy3ra-jzxhp-9wphr", "2026-10-02T22:10:43Z"),
        "group": "coffee",
        "sizes": [_size("12 oz", 1800, 1350, None, 12, d=True),
                  _size("2 lb", 3800, 2850, None, 32),
                  _size("5 lb", 9500, 7125, None, 80)],
        "sub": {"t": "“Subscribe” option with its own price per "
                     "size (delivery frequency not shown)"},
    },
    "wel": {  # The Well Coffee Roasters Watershed
        "src": ("https://wellcoffeeroasters.com/products/watershed",
                "2026-10-02T22:11Z"),
        "group": "coffee",
        "sizes": [_size("12 oz", 2050, 1845, None, 12, d=True),
                  _size("2 lb", 5150, 4635, None, 32),
                  _size("5 lb", 11900, 10710, None, 80)],
        "ship": {"k": "threshold", "over": 7500, "members": False,
                 "t": "“Free Shipping On All Orders $75+”; below "
                      "that “Shipping calculated at checkout”"},
        "sub": {"t": "“Subscribe & Save” (“Save up to 10%”) "
                     "with its own price per size"},
    },
    "ccc": {  # Counter Culture Big Trouble
        "src": ("https://counterculturecoffee.com/collections/coffee/"
                "products/big-trouble", "2026-10-02T22:13:21Z"),
        "group": "coffee",
        "sizes": [_size("12 oz", 1950, 1750, None, 12, d=True),
                  _size("24 oz", 3750, 3366, None, 24),
                  _size("5 lb", 10100, 9065, None, 80)],
        "ship": {"k": "threshold", "over": 3000, "members": False,
                 "t": "“Free shipping on $30 & up!”"},
        "sub": {"t": "“Subscribe + Save” with its own price per "
                     "size"},
    },
    "apple": {
        "src": ("https://www.apple.com/airpods-pro/", "2026-10-02T22:14:40Z"),
        "group": None, "sizes": [],
        "ship": {"k": "free", "t": "Page lists “free delivery” among "
                                   "its delivery options (no minimum shown)"},
    },
    "oldnavy": {
        "src": ("https://oldnavy.gap.com/browse/product.do?pid=777363182",
                "2026-10-02T22:14:17Z"),
        "group": "clothing",
        "sizes": [_size(k, ok=True, o=i) for i, k in enumerate(
            ["XS", "S", "M", "L", "XL", "XXL", "2X", "3X", "4X"])],
        "ship": {"k": "threshold", "over": 5000, "members": True,
                 "t": "“Free fast shipping on $50+ for Rewards "
                      "Members”"},
    },
    "gap": {
        "src": ("https://www.gap.com/browse/product.do?pid=800546212",
                "2026-10-02T22:16:01Z"),
        "group": "clothing",
        "sizes": [_size("XXS", ok=True, o=0), _size("XS", ok=True, o=1),
                  _size("S", ok=True, o=2), _size("M", ok=False, o=3),
                  _size("L", ok=False, o=4), _size("XL", ok=True, o=5),
                  _size("XXL", ok=False, o=6)],
        "ship": {"k": "threshold", "over": 5000, "members": True,
                 "t": "“Free fast shipping on $50+ for Rewards "
                      "Members”"},
    },
    "nike": {
        "src": ("https://www.nike.com/t/air-jordan-og-womens-shoes-6JW206/"
                "CW0907-002", "2026-10-02T22:13:55Z"),
        "group": "shoe",
        "sizes": [_size(k, ok=ok, o=_lead_number(k)) for k, ok in [
            ("W 5 / M 3.5", True), ("W 5.5 / M 4", True),
            ("W 6 / M 4.5", True), ("W 6.5 / M 5", True),
            ("W 7 / M 5.5", True), ("W 7.5 / M 6", True),
            ("W 8 / M 6.5", True), ("W 8.5 / M 7", True),
            ("W 9 / M 7.5", True), ("W 9.5 / M 8", True),
            ("W 10 / M 8.5", True), ("W 10.5 / M 9", False),
            ("W 11 / M 9.5", True), ("W 11.5 / M 10", False),
            ("W 12 / M 10.5", False), ("W 12.5 / M 11", False),
            ("W 13 / M 11.5", False), ("W 13.5 / M 12", False),
            ("W 14 / M 12.5", False), ("W 14.5 / M 13", False),
            ("W 15.5 / M 14", False)]],
        "ship": {"k": "threshold", "over": 5000, "members": True,
                 "t": "“Members: Free Shipping on Orders $50+”; "
                      "otherwise “You'll see our shipping options at "
                      "checkout”"},
    },
}

# What the live Lavazza pages print today. Kept as a dated observation only:
# the cards' CAFE20 observation is from 2026-10-01 and is not edited here.
LAVAZZA_BANNER_2026_10_02 = (
    "AUTUMN SAVINGS EVENT: 20% OFF Coffee* with code AS20 | Extra Savings "
    "on Orders $49+")
