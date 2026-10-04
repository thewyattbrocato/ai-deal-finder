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
  ship_quoted: [lines] shipping lines the page printed that were not read
          as a condition (present only when "ship" is absent); shown as
          printed, never counted as a known shipping fact
  across: ["colours", ...] the sizes are read across these option groups
  sub:   {"t": what the page said}      (present only when offered)
"""

import json
import os
import re
import urllib.parse

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


_FREE_SHIP = re.compile(
    r"(?i)\bfree(?: (?:standard|ground|us|u\.s\.|fast|economy|domestic|"
    r"continental|usps|2-day|two-day|luxury))* (?:shipping|delivery)\b")
_NON_MEMBER = re.compile(r"(?i)\bnon[- ]?members?\b|\bvips?\b")
_THRESHOLD = re.compile(
    r"(?i)(?:\b(?:over|above|orders? of|orders? \$|spend|minimum|on)\s*"
    r"(?:orders? )?(?:over |of )?(?:US)?\$\s?(\d{2,4})(?:\.00)?(?!\d)"
    r"|(?:US)?\$\s?(\d{2,4})(?:\.00)?\s*(?:\+|and up|& up|or more|minimum))")
_SHIP_SKIP = re.compile(
    r"(?i)\b(?:international|canada|outside|worldwide|returns?|exchanges?|"
    r"more to (?:earn|get|qualify|unlock)|away from|to unlock|you.?re \$|"
    r"add \$|spend \$\d+ more|amount|only|exclud|except|select|some items|"
    r"hawaii|alaska|puerto)\b")
_MEMBERS = re.compile(
    r"(?i)\b(?:members?|membership|rewards?|loyalty|sign(?:ed)? in|log ?in|"
    r"join|insider|vip|club)\b")
_FREE_ALL = re.compile(
    r"(?i)\bfree(?: [a-z.]+){0,2} (?:shipping|delivery) (?:on |for )?"
    r"(?:all|every|any) (?:us |u\.s\. )?orders?\b(?! over| of| \$)")
_SUB_OFFER = re.compile(
    r"(?i)subscribe\s*(?:&|and|\+|n)\s*(?:save|get|enjoy)|auto-?ship|"
    r"subscription (?:discount|price|option|available)|"
    r"(?:save|get) (?:up to )?\d{1,2}% (?:when you|with a|on a|on your|by) "
    r"(?:subscri|auto)|deliver(?:ed|y)? every \d|"
    r"(?:subscribe|subscription) (?:for|to) (?:this|the) (?:product|item|coffee)")
_SUB_SKIP = re.compile(
    r"(?i)\b(?:newsletter|e-?mails?|text|sms|updates|notify|restock|"
    r"back in stock|sign ?up|join our|waitlist|offers? and|promotions?)\b")
_PCT = re.compile(r"(?i)\bsave (?:up to )?(\d{1,2})\s?%")


_PLAIN_THRESHOLD = re.compile(
    r"(?i)\W*free (?:shipping|delivery) (?:on orders )?(?:over|above) "
    r"\$\s?(\d{2,4})(?:\.00)?[.!]?")
_RETURNS_ONLY = re.compile(r"(?i)\W*(?:and )?free (?:returns?|exchanges?)[.!]?")


def _plain_threshold(line):
    """Cents of a plain "free shipping over $N" sentence, else None.

    Only a line made of that one sentence (optionally followed by a bare
    "free returns" sentence) counts. Anything else in the line (a member,
    region, exception or returns condition) leaves it to the quote.
    """
    parts = [x for x in re.split(r"(?<=[.!])\s+", line.strip()) if x]
    if not parts or not _PLAIN_THRESHOLD.fullmatch(parts[0]):
        return None
    if any(not _RETURNS_ONLY.fullmatch(x) for x in parts[1:]):
        return None
    return int(_PLAIN_THRESHOLD.fullmatch(parts[0]).group(1)) * 100


def _ship_from_lines(lines):
    """Explicit shipping statements in the page's own stored lines.

    Fail closed: lines that talk about returns, other countries, cart
    progress or exceptions are ignored, two different thresholds mean
    unknown, and a bare "free shipping" tag with no minimum is not a
    condition.
    """
    found = []
    segs = [g.strip() for l in lines or [] for g in re.split(r"\s[|\u2022]\s", l)]
    for line in segs:
        if _NON_MEMBER.search(line):
            continue
        if not _FREE_SHIP.search(line) or _SHIP_SKIP.search(line):
            plain = _plain_threshold(line)
            if plain:
                found.append(("threshold", plain, False, line))
            continue
        mem = bool(_MEMBERS.search(line))
        m = _THRESHOLD.search(line)
        if m:
            over = int(m.group(1) or m.group(2)) * 100
            found.append(("threshold", over, mem, line))
        elif _FREE_ALL.search(line) and not mem:
            found.append(("free", None, False, line))
    if not found:
        return None
    kinds = {(k, o) for k, o, _, _ in found}
    if len(kinds) != 1:
        return None
    k, over, _, line = found[0]
    mem = any(f[2] for f in found)
    quote = "\u201c" + line + "\u201d"
    if k == "free":
        return {"k": "free", "t": quote}
    return {"k": "threshold", "over": over, "members": mem, "t": quote}


_SHIP_STATEMENT = re.compile(
    r"(?i)\bfree\b[^|]{0,40}\b(?:shipping|delivery)\b|\bships? free\b|"
    r"\bflat[- ]rate\b|\bshipping\b[^|]{0,30}(?:\$\s?\d|at checkout|"
    r"calculated)|\$\s?\d[^|]{0,30}\bshipping\b")


def quoted_ship_lines(lines, limit=3):
    """Stored shipping statements shown as printed, never read as a condition.

    Used only when the extractor read nothing: a line that says something
    about shipping cost (not a bare heading, a policy link or long legal
    text) is kept word for word, so the card can say what the page printed
    instead of that it stated nothing.
    """
    out, seen = [], set()
    for l in lines or []:
        for g in (x.strip() for x in re.split(r"\s[|\u2022]\s", l)):
            key = g.lower()
            if (not g or len(g) > 160 or key in seen
                    or not _SHIP_STATEMENT.search(g)):
                continue
            seen.add(key)
            out.append(g)
    return out[:limit]


_PRE_ORDER = re.compile(r"(?i)\bpre-?orders?\b")
_PRE_SHIP = re.compile(r"(?i)\b(?:start|begin|will)?\s*ship(?:s|ping)?\b")


def _pre_from_lines(lines):
    """A stated pre-order shipping line, quoted as the page wrote it.

    Only a line that says "pre-order" and talks about shipping counts; the
    emoji or "Shipping:" label in front of it is dropped, the rest is the
    page's own words. Two different pre-order lines mean unknown.
    """
    found = []
    for g in [g.strip() for l in lines or [] for g in re.split(r"\s[|•]\s", l)]:
        if not (_PRE_ORDER.search(g) and _PRE_SHIP.search(g)):
            continue
        q = re.sub(r"^[^A-Za-z0-9]+", "", g)
        q = re.sub(r"(?i)^shipping:\s*", "", q).strip()
        if q and q not in found:
            found.append(q)
    if len(found) != 1:
        return None
    q = found[0]
    m = re.search(r"(?i)\bstart\w* shipping\b.*$", q)
    return {"t": "“" + q + "”",
            "when": "“" + (m.group(0) if m else q) + "”"}


def _sub_from_lines(lines):
    hits = [l for l in (lines or [])
            if _SUB_OFFER.search(l) and not _SUB_SKIP.search(l)]
    if not hits:
        return None
    out = {"t": "\u201c" + hits[0] + "\u201d (the subscribe price itself is "
                                    "not shown)"}
    pct = _PCT.search(hits[0])
    if pct:
        out["pct"] = int(pct.group(1))
    return out


def conditions_from_evidence(ev):
    """(ship, sub, src) the page's stored lines state, else (None, None, None)."""
    c = ev.get("conditions")
    if not c:
        return None, None, None
    return (_ship_from_lines(c.get("ship")), _sub_from_lines(c.get("sub")),
            (c.get("url"), c.get("read_at")))


def _offer_size(o):
    """The size an offer's own url names (?Size=M), else None."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(str(o.get("url") or "")).query)
    vals = [v for k, vs in q.items() if k.lower() == "size" for v in vs if v]
    return vals[0] if len(vals) == 1 else None


def _sizes_from_offers(p):
    """Sizes a product with no variants lists in its offers.

    One offer: the product's own size. Several offers: every offer must name
    its size, else the parse is partial and no size is shown at all (the
    top-level size alone would understate what the page lists).
    """
    offers = _offers(p)
    if len(offers) <= 1:
        return [{"k": str(p["size"]), "c": None, "s": None, "sp": None,
                 "o": _lead_number(str(p["size"])),
                 "ok": str(offers[0].get("availability", "")).endswith("InStock")
                 if offers else None}]
    out, seen = [], set()
    for o in offers:
        k = _offer_size(o)
        if k is None:
            return []
        if k in seen:
            continue
        seen.add(k)
        n = _lead_number(k)
        out.append({"k": k, "c": None, "s": None, "sp": None,
                    # letter sizes keep the page's own order (XS, S, M ...)
                    "o": n if n != 1000.0 else float(len(out)),
                    "ok": str(o.get("availability", "")).endswith("InStock")})
    return out


_AXIS_WORDS = {"color": "colours", "colour": "colours", "height": "heights",
               "material": "materials", "pattern": "patterns",
               "style": "styles"}


def _size_axes(variants):
    """Option groups besides size that vary across the variants a size spans.

    A size listed for several variants (say several colours) is read across
    all of them; the axis names say what the size reading is across.
    """
    by = {}
    for v in variants:
        if v.get("size"):
            by.setdefault(str(v["size"]), []).append(v)
    if not any(len(l) > 1 for l in by.values()):
        return []
    axes = []
    for key, word in _AXIS_WORDS.items():
        if len({str(v.get(key)) for l in by.values() for v in l
                if v.get(key)}) > 1 and word not in axes:
            axes.append(word)
    return axes


def from_evidence(ev, kind):
    """Stored evidence record -> terms dict (sizes/shipping only if stated)."""
    prods = ev.get("json_ld") or []
    if not prods:
        return {"group": None, "sizes": []}
    p = prods[0]
    variants = p.get("hasVariant") or []
    sizes, at = [], {}
    for v in variants:
        s = v.get("size")
        if not s:
            continue
        stocks = [str(o.get("availability", "")).endswith("InStock")
                  for o in _offers(v)]
        k = str(s)
        if k not in at:
            at[k] = len(sizes)
            sizes.append({"k": k, "c": None, "s": None, "sp": None,
                          "o": _lead_number(k), "ok": None})
        # A size is in stock if the page shows it in stock for any variant
        # (colour); out of stock only when every variant that states stock
        # shows it out; unknown when none states it.
        cur = sizes[at[k]]
        if stocks:
            cur["ok"] = True if (cur["ok"] or any(stocks)) else False
    if not sizes and p.get("size"):
        sizes = _sizes_from_offers(p)
    group = _size_group([s["k"] for s in sizes], kind)
    if group is None:
        sizes = []
    out = {"group": group, "sizes": sizes}
    across = _size_axes(variants) if sizes else []
    if across:
        out["across"] = across
    ship = _shipping([p] + variants)
    r_ship, r_sub, src = conditions_from_evidence(ev)
    ship = ship or r_ship
    if ship:
        out["ship"] = ship
    if r_sub:
        out["sub"] = r_sub
    ship_lines = (ev.get("conditions") or {}).get("ship")
    pre = _pre_from_lines(ship_lines)
    if pre:
        out["pre"] = pre
    quoted = [] if ship else quoted_ship_lines(ship_lines)
    if quoted:
        out["ship_quoted"] = quoted
    if src and (ship or r_sub or pre or quoted):
        out["src"] = src
    return out


def for_id(ev_id, kind, evidence_dir=EVIDENCE_DIR):
    path = os.path.join(evidence_dir, ev_id + ".json")
    with open(path) as f:
        return from_evidence(json.load(f), kind)


# Search words a product's own name does not carry, so the search finds it by
# what it is. Added here, at build time, never by hand in the page; each is a
# plain description of a real catalog product, not a claim about its page.
SEARCH_WORDS = {
    # "The Breville Bambino": an espresso machine (kind Kitchen, Counter Culture)
    "counterculturecoffee-the-bambino": ["espresso"],
    # Each word below is printed in that product's own stored page title,
    # description or address (tests/test_coverage_q2.py checks it is).
    "flair-the-flair-classic": ["espresso", "maker"],
    "flair-the-royal-grinder": ["espresso"],
    "wacaco-picopresso": ["espresso", "machine"],
    "wacaco-minipresso-gr2": ["espresso", "maker"],
    "moccamaster-kb": ["coffee", "brewer"],
    "moccamaster-moccamaster-kbgt-midnight": ["coffee", "maker"],
    "moccamaster-moccamaster-kbgv-coffee-maker-sorbet": ["coffee", "maker"],
    "aeropress-aeropress-manual-coffee-grinder": ["coffee", "grinder"],
    "goodr-what-lurks-in-the-shadows": ["sunglasses"],
    "goodr-bean-there-run-that": ["sunglasses"],
    "knockaround-sunburst-stratocaster-fort-knocks": ["sunglasses"],
    "knockaround-dogfish-head-torrey-pines": ["sunglasses"],
    "knockaround-wm-phoenix-fast-lanes-sport": ["sunglasses"],
    "boysmells-hard-wood-classic-candle-9oz": ["candle"],
    "boysmells-herbaceous-classic-candle-9oz": ["candle"],
    "costafarms-anthurium-hookeri-dark-medium": ["plant"],
    "costafarms-brasil-philodendron-medium": ["plant"],
    "costafarms-large-pachira-parent": ["plant"],
    "eaglecreek-pack-it-dry-cube-m": ["travel"],
    "eaglecreek-cargo-hauler-tote-65l": ["travel"],
    "manduka-ratio-relaxation-mat": ["yoga"],
    "boysmells-big-apple-perfume-50ml": ["perfume", "fragrance"],
    "boysmells-les-perfume-50ml": ["perfume", "fragrance"],
    # Slice t1: each word below is printed in that product's own stored page
    # title, description or address (tests/test_coverage_t1.py checks it is).
    "topodesigns-daypack-classic-navy": ["backpack"],
    "xeroshoes-hfs-men-original": ["running"],
    "xeroshoes-hfs-women-original": ["running"],
    "cocokind-electrolyte-water-cream": ["moisturizer"],
    "cocokind-retinol-body-cream": ["moisturizer"],
    "supergoop-city-sunscreen-serum": ["moisturizer"],
    "burstoralcare-pro-brush-replacement-head-3-pack": ["toothbrush"],
    "skullcandy-crusher-720-headphones": ["headphones"],
    "skullcandy-icon-180-wired": ["headphones"],
    "skullcandy-session-540": ["speaker"],
    "transparentlabs-multivitamin": ["vitamins", "supplement"],
    "perfectsnacks-oaties-brownie-batter": ["snacks", "protein"],
    "perfectsnacks-pumpkin-pie": ["snacks", "protein"],
    "epicprovisions-maple-bacon-pork-cracklings": ["snack"],
    "epicprovisions-sea-salt-vinegar-pork-rinds": ["snack"],
    "cuddleandkind-tiny-baby-mouse": ["dolls"],
    "cuddleandkind-tiny-baby-puppy": ["dolls"],
    "cuddleandkind-tiny-baby-skeleton": ["dolls"],
    "cuddleandkind-tiny-honey-bear": ["dolls"],
}


def handcard_record(slug):
    """Stored dated observations of a hand-checked card (the earlier ones are
    history, the last one is what the card shows)."""
    with open(os.path.join(EVIDENCE_DIR, "handcards", slug + ".json"),
              encoding="utf-8") as f:
        return json.load(f)


def _latest(slug):
    return handcard_record(slug)["observations"][-1]


def _lavazza_latest(slug):
    with open(os.path.join(EVIDENCE_DIR, "lavazza", slug + ".json"),
              encoding="utf-8") as f:
        return json.load(f)["observations"][-1]


def _size(k, c=None, s=None, sp=None, o=None, ok=None, d=False):
    return {"k": k, "c": c, "s": s, "sp": sp, "o": o, "ok": ok, "d": d}


# Read in a read-only browser; nothing added to a cart, no code tried. "src" is
# the page and the time of the latest read of it. Hand cards were read again
# 2026-10-03 and 2026-10-04 (demo/evidence/handcards/, demo/evidence/lavazza/;
# earlier reads kept there as dated history); the sizes below are that latest read.
HAND = {
    "cof3": {  # Lavazza Dolcevita Classico
        "src": ("https://www.lavazzausa.com/en/whole-bean-coffee/"
                "dolcevita-classico", _lavazza_latest("dolcevita-classico")["observed_at"]),
        "group": "coffee",
        "sizes": [_size("12 oz", 1399, None, 25, 12, d=True)],
        "ship": {"k": "threshold", "over": 5000, "members": False,
                 "t": "“Free delivery on orders over $50”"},
        "sub": {"t": "“Subscribe and save 25%” (the subscribe "
                     "price itself is not shown)"},
    },
    "cof2": {  # Lavazza Qualita Rossa
        "src": ("https://www.lavazzausa.com/en/whole-bean-coffee/"
                "qualita-rossa", _lavazza_latest("qualita-rossa")["observed_at"]),
        "group": "coffee",
        "sizes": [_size("2.2 lb", 2499, None, 25, 35.2, d=True)],
        "ship": {"k": "threshold", "over": 5000, "members": False,
                 "t": "“Free delivery on orders over $50”"},
        "sub": {"t": "“Subscribe and save 25%” (the subscribe "
                     "price itself is not shown)"},
    },
    "cof1": {  # Lavazza Super Crema
        "src": ("https://www.lavazzausa.com/en/whole-bean-coffee/"
                "super-crema.4202", _lavazza_latest("super-crema")["observed_at"]),
        "group": "coffee",
        "sizes": [_size("2.2 lb", 2699, None, 25, 35.2, d=True)],
        "ship": {"k": "threshold", "over": 5000, "members": False,
                 "t": "“Free delivery on orders over $50”"},
        "sub": {"t": "“Subscribe and save 25%” (the subscribe "
                     "price itself is not shown)"},
    },
    "hcr": {  # Honest Coffee Roasters Midnight Axes
        "src": ("https://www.honest.coffee/shop-3Ooj8/p/"
                "nguvu-bcntn-ksj2y-dy3ra-jzxhp-9wphr", _latest("hcr")["observed_at"]),
        "group": "coffee",
        "sizes": [_size("12 oz", 1800, 1350, None, 12, d=True),
                  _size("2 lb", 3800, 2850, None, 32),
                  _size("5 lb", 9500, 7125, None, 80)],
        "sub": {"t": "“Subscribe” option with its own price per "
                     "size (delivery frequency not shown)"},
    },
    "wel": {  # The Well Coffee Roasters Watershed
        "src": ("https://wellcoffeeroasters.com/products/watershed",
                _latest("wel")["observed_at"]),
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
                "products/big-trouble", _latest("ccc")["observed_at"]),
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
        "src": ("https://www.apple.com/airpods-pro/", _latest("apple")["observed_at"]),
        "group": None, "sizes": [],
        "ship": {"k": "free", "t": "Page lists “free delivery” among "
                                   "its delivery options (no minimum shown)"},
    },
    "oldnavy": {
        "src": ("https://oldnavy.gap.com/browse/product.do?pid=777363182",
                _latest("oldnavy")["observed_at"]),
        "group": "clothing",
        "sizes": [_size(k, ok=True, o=i) for i, k in enumerate(
            ["XS", "S", "M", "L", "XL", "XXL", "2X", "3X", "4X"])],
        "ship": {"k": "threshold", "over": 5000, "members": True,
                 "t": "“Free fast shipping on $50+ for Rewards "
                      "Members”"},
    },
    "gap": {
        "src": ("https://www.gap.com/browse/product.do?pid=800546212",
                _latest("gap")["observed_at"]),
        "group": "clothing",
        "sizes": [_size("XXS", ok=True, o=0), _size("XS", ok=True, o=1),
                  _size("S", ok=False, o=2), _size("M", ok=False, o=3),
                  _size("L", ok=False, o=4), _size("XL", ok=False, o=5),
                  _size("XXL", ok=False, o=6)],
        "ship": {"k": "threshold", "over": 5000, "members": True,
                 "t": "“Free fast shipping on $50+ for Rewards "
                      "Members”"},
    },
    "nike": {
        "src": ("https://www.nike.com/t/air-jordan-og-womens-shoes-6JW206/"
                "CW0907-002", _latest("nike")["observed_at"]),
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
# the cards now carry the 2026-10-03 re-observation (demo/evidence/lavazza/);
# the earlier CAFE20 read stays there as dated history.
LAVAZZA_BANNER_2026_10_02 = (
    "AUTUMN SAVINGS EVENT: 20% OFF Coffee* with code AS20 | Extra Savings "
    "on Orders $49+")
