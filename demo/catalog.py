"""Catalog collector and offline extractor for the checked-products page.

Two halves, kept apart so every observation is reproducible from stored
evidence without a network:

  collect  (network, read-only GET of public product pages, no login/cart/form)
           python3 demo/catalog.py collect <seeds.json>
           Writes demo/evidence/<id>.json (page facts as served) and the
           product's own photo (og:image from that same page) to demo/assets.
  extract  (offline) extract(evidence) -> observation dict, or an exclusion
           reason. A price needs one agreeing in-stock JSON-LD offer; identity
           needs a product name; a coupon needs literal code text on the page.
           Anything else is excluded, never guessed.
"""

import hashlib
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_DIR = os.path.join(HERE, "evidence")
ASSETS_DIR = os.path.join(HERE, "assets")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")

# "use code SAVE10", "code: WELCOME15", "promo code SPRING" — a code token
# directly after the word code. Offers without a code token are not coupons.
CODE_RE = re.compile(
    r"(?:\b(?:use|enter|with|apply)\s+)?(?:promo\s+|coupon\s+|discount\s+)?"
    r"\bcode\s*:?\s*[\"“']?([A-Z][A-Z0-9]{3,19})\b[\"”']?")
STOP_CODES = {"HTML", "NULL", "TRUE", "FALSE", "JSON"}
# Offers behind an email/signup/subscription step are not on-page coupons.
GATED_RE = re.compile(r"(?i)\b(e-?mail|address|sign[- ]?up|subscri\w+|resubscribe|newsletter|text)\b")


# "<Name> Sale:" opening a printed offer, e.g. "Wrinkle-Free Sale: Offer valid ...".
# Only the one word before "Sale" is taken: the words before it may be page navigation.
SALE_HEAD_RE = re.compile(r"(?<![\w-])[A-Z][\w-]* Sale:\s")
# A gift card or a membership is never a product with a shelf price to compare.
NON_DEAL_RE = re.compile(r"(?i)\bgift\s*cards?\b|\be-?gift\b|\bmemberships?\b")


def tight_offer(snip, m):
    """Verbatim substring of the snippet: the sentence holding the code.

    The snippet is a fixed-width window, so with no sentence break before the
    code its first word may be cut; that partial word is dropped.
    """
    before = [b.end() for b in re.finditer(r"[.!?]\s", snip[:m.start()])]
    if before:
        start = before[-1]
    else:
        start = snip.find(" ") + 1 if m.start() > 0 else 0
        start = min(start, m.start())
    if not before:
        offer = [o.start() for o in re.finditer(
            r"(?i)(?:\$\d+|\d+%)\s*off", snip[start:m.start()])]
        if offer:
            start += offer[-1]
    # Keep the sale the page names ("Wrinkle-Free Sale: ...") when it heads the
    # offer, so the quote carries the scope the page printed with the code.
    head = None
    for h in SALE_HEAD_RE.finditer(snip[:start]):
        head = h
    if head and start - head.start() <= 260:
        start = head.start()
    after = re.search(r"[.!?](?=\s|$)", snip[m.end():])
    end = m.end() + after.end() if after else len(snip)
    return snip[start:end].strip()


def visible_text(raw):
    raw = re.sub(r"(?is)<(script|style|noscript|template)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", htmllib.unescape(raw)).strip()


def coupon_snippets(text):
    out = []
    for m in CODE_RE.finditer(text):
        if m.group(1) in STOP_CODES:
            continue
        lo, hi = max(0, m.start() - 150), min(len(text), m.end() + 150)
        snip = text[lo:hi].strip()
        if snip not in out:
            out.append(snip)
        if len(out) >= 3:
            break
    return out


def json_ld_products(raw):
    found = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            t = node.get("@type")
            ts = t if isinstance(t, list) else [t]
            if "Product" in ts or "ProductGroup" in ts:
                found.append(node)
            for k in ("@graph", "hasVariant"):
                if k in node:
                    walk(node[k])

    for m in re.finditer(
            r'(?is)<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', raw):
        try:
            walk(json.loads(m.group(1)))
        except ValueError:
            continue
    return found


def meta_content(raw, prop):
    for m in re.finditer(r"(?is)<meta\b[^>]*>", raw):
        tag = m.group(0)
        if re.search(r'(?:property|name)=["\']' + re.escape(prop) + r'["\']', tag):
            c = re.search(r'content=["\']([^"\']*)["\']', tag)
            if c:
                return htmllib.unescape(c.group(1))
    return None


def fetch(url, binary=False, timeout=25):
    url = urllib.parse.quote(url, safe=":/?&=%#+,;@!$'()*~")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.geturl(), r.read()


def sized_image(url):
    """Same image from the same page; ask the CDN for a card-sized copy."""
    p = urllib.parse.urlparse(url)
    if "cdn.shopify.com" in p.netloc or "/cdn/shop/" in p.path:
        q = dict(urllib.parse.parse_qsl(p.query))
        q["width"] = "420"
        return urllib.parse.urlunparse(p._replace(query=urllib.parse.urlencode(q)))
    return url


def collect_one(seed, prior=None):
    """seed: {id, url, kind}. Returns the evidence record (saved).

    prior: the stored record being re-read; its saved photo is kept, not
    fetched again, so a re-read changes the page facts and nothing else.
    """
    status, final_url, body = fetch(seed["url"])
    raw = body.decode("utf-8", "replace")
    text = visible_text(raw)
    ev = {
        "id": seed["id"], "kind": seed["kind"], "url": seed["url"],
        "final_url": final_url, "http_status": status,
        "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "page_sha256": hashlib.sha256(body).hexdigest(),
        "title": (re.search(r"(?is)<title[^>]*>(.*?)</title>", raw) or [0, ""])[1].strip(),
        "json_ld": json_ld_products(raw),
        "og_image": meta_content(raw, "og:image"),
        "coupon_snippets": coupon_snippets(text),
        "image_file": None,
    }
    ev["title"] = htmllib.unescape(re.sub(r"\s+", " ", ev["title"]))
    imgs = ev["json_ld"][0].get("image") if ev["json_ld"] else None
    img = ev["og_image"] or (imgs[0] if isinstance(imgs, list) and imgs else imgs)
    if isinstance(img, dict):
        img = img.get("url")
    if img and img.startswith("//"):
        img = "https:" + img
    if prior and prior.get("image_file") and os.path.exists(
            os.path.join(ASSETS_DIR, prior["image_file"])):
        for k in ("image_file", "image_sha256", "image_source"):
            if k in prior:
                ev[k] = prior[k]
    elif img and offers_of(ev) is not None:
        try:
            _, _, data = fetch(sized_image(img))
            ext = ".png" if data[:4] == b"\x89PNG" else ".jpg"
            if data[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1",
                            b"\xff\xd8\xff\xdb", b"\xff\xd8\xff\xee") and len(data) > 2000:
                os.makedirs(ASSETS_DIR, exist_ok=True)
                name = seed["id"] + ext
                with open(os.path.join(ASSETS_DIR, name), "wb") as f:
                    f.write(data)
                ev["image_file"] = name
                ev["image_sha256"] = hashlib.sha256(data).hexdigest()
                ev["image_source"] = sized_image(img)
        except Exception as e:  # no photo is fine: the product shows without
            ev["image_error"] = str(e)[:120]
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    with open(os.path.join(EVIDENCE_DIR, seed["id"] + ".json"), "w") as f:
        json.dump(ev, f, indent=1, sort_keys=True)
    return ev


RENDER_JS = (
    "() => { const t = document.body.innerText.replace(/\\s+/g, ' ');"
    " const re = /\\b(?:use|enter|with|apply)?\\s*(?:promo |coupon |discount )?"
    "code\\s*:?\\s*[\"\u201c']?([A-Z][A-Z0-9]{3,19})\\b/g; const o = []; let m;"
    " while ((m = re.exec(t)) && o.length < 3) {"
    " o.push(t.slice(Math.max(0, m.index - 150), m.index + m[0].length + 150)); }"
    " return JSON.stringify(o); }")


def render_pass(ev_id, session="cat100"):
    """Open the product page in a real browser (read-only) and add any
    promo-code text that only appears once the page's scripts have run."""
    import subprocess
    env = dict(os.environ, CHROME_DEVTOOLS_AXI_SESSION=session)
    path = os.path.join(EVIDENCE_DIR, ev_id + ".json")
    ev = json.load(open(path))
    run = lambda *a: subprocess.run(["chrome-devtools-axi", *a], env=env,
                                    capture_output=True, text=True, timeout=90)
    run("open", ev["final_url"])
    run("wait", "2500")
    out = run("eval", RENDER_JS).stdout
    m = re.search(r'result: "(.*)"\n', out)
    snips = []
    if m:
        try:
            v = json.loads('"' + m.group(1) + '"')
            while isinstance(v, str):
                v = json.loads(v)
            snips = [x for x in v if isinstance(x, str)]
        except ValueError:
            snips = []
    ev["rendered_checked"] = True
    for sn in snips:
        if sn not in ev["coupon_snippets"]:
            ev["coupon_snippets"].append(sn)
    json.dump(ev, open(path, "w"), indent=1, sort_keys=True)
    return snips


# Second browser pass (read-only, nothing added to a cart, no code tried):
# keep the page's own lines that talk about shipping/delivery, subscribing,
# and the size picker, verbatim. terms.py turns only explicit statements in
# these lines into conditions; a page that is silent stays unknown.
CONDITIONS_JS = (
    "() => { const keep = (re, n) => { const o = [];"
    " for (const l of document.body.innerText.split(/\\n+/)) {"
    " const s = l.replace(/\\s+/g, ' ').trim();"
    " if (s.length > 2 && s.length <= 220 && re.test(s) && !o.includes(s)) o.push(s);"
    " if (o.length >= n) break; } return o; };"
    " return JSON.stringify({ at: [location.href],"
    " ship: keep(/shipping|delivery/i, 14),"
    " sub: keep(/subscri|auto-?ship|repeat order|recurring/i, 10),"
    " size: keep(/^(?:select |choose |pick )?(?:a |your )?size\\b|\\bsizes?:/i, 6)}); }")


def conditions_pass(ev_id, session="cond1"):
    """Re-read one stored product's page in a real browser and store the
    shipping / subscribe / size lines it prints, with the date read."""
    import subprocess
    env = dict(os.environ, CHROME_DEVTOOLS_AXI_SESSION=session)
    path = os.path.join(EVIDENCE_DIR, ev_id + ".json")
    ev = json.load(open(path))
    run = lambda *a: subprocess.run(["chrome-devtools-axi", *a], env=env,
                                    capture_output=True, text=True, timeout=90)
    run("open", ev["final_url"])
    pages = run("pages").stdout
    ids = re.findall(r"^\s+(\d+),(\S+),", pages, re.M)
    cur = [i for i, u in ids if u.startswith("http")]
    if cur:
        run("selectpage", cur[-1])
    run("wait", "3500")
    out = run("eval", CONDITIONS_JS).stdout
    m = re.search(r'result: "(.*)"\n', out)
    got = None
    if m:
        try:
            v = json.loads('"' + m.group(1) + '"')
            while isinstance(v, str):
                v = json.loads(v)
            got = {k: [x for x in v.get(k, []) if isinstance(x, str)]
                   for k in ("at", "ship", "sub", "size")}
        except ValueError:
            got = None
    if got is None or not got.get("at", [""])[0].startswith(
            "https://" + urllib.parse.urlparse(ev["final_url"]).netloc):
        return None
    got.pop("at")
    ev["conditions"] = dict(
        got, read_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        url=ev["final_url"])
    json.dump(ev, open(path, "w"), indent=1, sort_keys=True)
    return got


# The page facts one observation holds; a re-read moves these, as they were,
# into "history" (dated by their own observed_at) before the new ones are stored.
OBSERVED_KEYS = ("observed_at", "http_status", "final_url", "page_sha256", "title",
                 "json_ld", "og_image", "coupon_snippets", "rendered_checked",
                 "conditions", "excluded_reason")


def reread(ev_id, session="reread1"):
    """Observe a stored product's page again and keep the earlier observation.

    Same path as the first collection: read-only GET, then the real-browser
    promo-text pass and the shipping/subscribe/size pass. Returns
    ("read", None) when the page was read again, ("gone", reason) when the
    page answers 404/410 (stored as a new dated observation with the reason,
    the earlier one kept), or ("unread", reason) when it could not be read
    (the stored record is left exactly as it was).
    """
    import urllib.error
    path = os.path.join(EVIDENCE_DIR, ev_id + ".json")
    old = json.load(open(path))
    seed = {"id": ev_id, "url": old["url"], "kind": old["kind"]}
    snapshot = {k: old[k] for k in OBSERVED_KEYS if k in old}
    history = list(old.get("history", [])) + [snapshot]
    try:
        ev = collect_one(seed, prior=old)
    except urllib.error.HTTPError as e:
        if e.code not in (404, 410):
            return "unread", "HTTP %d" % e.code
        ev = dict(old)
        for k in OBSERVED_KEYS:
            ev.pop(k, None)
        ev.update(
            http_status=e.code, final_url=old["final_url"],
            observed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            json_ld=[], coupon_snippets=[], history=history,
            excluded_reason="page returned HTTP %d when read again" % e.code)
        json.dump(ev, open(path, "w"), indent=1, sort_keys=True)
        return "gone", ev["excluded_reason"]
    except Exception as e:
        return "unread", str(e)[:80]
    ev["history"] = history
    json.dump(ev, open(path, "w"), indent=1, sort_keys=True)
    if extract(ev)[0] == "ok":
        render_pass(ev_id, session)
        if conditions_pass(ev_id, session) is None:
            return "read", "conditions not read"
    return "read", None


def offers_of(ev):
    for p in ev.get("json_ld", []):
        o = p.get("offers")
        if o is not None:
            return o if isinstance(o, list) else [o]
        vs = p.get("hasVariant")
        if vs:
            out = []
            for v in vs:
                vo = v.get("offers")
                out.extend(vo if isinstance(vo, list) else [vo] if vo else [])
            return out or None
    return None


def extract(ev):
    """Evidence record -> ('ok', observation) or ('excluded', reason)."""
    if ev.get("excluded_reason"):
        return "excluded", ev["excluded_reason"]
    if ev.get("http_status") != 200:
        return "excluded", "page did not load"
    prods = ev.get("json_ld") or []
    if not prods:
        return "excluded", "no product data readable on the page"
    p = prods[0]
    name = (p.get("name") or "").strip()
    if not name:
        return "excluded", "product identity not readable"
    if NON_DEAL_RE.search(name):
        return "excluded", "gift card or membership, not a product with a shelf price"
    offers = offers_of(ev)
    if not offers:
        return "excluded", "no price on the page"
    prices, currencies, stock = set(), set(), []
    for o in offers:
        if not isinstance(o, dict):
            continue
        spec = o.get("priceSpecification")
        if isinstance(spec, list):
            spec = spec[0] if spec else None
        price = o.get("price")
        if price is None and isinstance(spec, dict):
            price = spec.get("price")
        try:
            prices.add(round(float(price), 2))
        except (TypeError, ValueError):
            return "excluded", "price not readable"
        currencies.add(o.get("priceCurrency") or (spec or {}).get("priceCurrency"))
        stock.append(str(o.get("availability", "")).endswith("InStock"))
    if len(prices) != 1:
        return "excluded", "price varies by option, not one shelf price"
    if currencies != {"USD"}:
        return "excluded", "not a USD price"
    price = prices.pop()
    if price <= 0:
        return "excluded", "price not readable"
    if not any(stock):
        return "excluded", "not in stock on the page"
    if re.search(r"(?i)\btest[- ]product\b", name + " " + ev["final_url"]):
        return "excluded", "internal test listing, not a product"
    coupon = None
    for snip in ev.get("coupon_snippets") or []:
        m = CODE_RE.search(snip)
        if m and not GATED_RE.search(snip):
            coupon = {"code": m.group(1), "text": tight_offer(snip, m)}
            break
    brand = p.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    host = urllib.parse.urlparse(ev["final_url"]).netloc.replace("www.", "")
    return "ok", {
        "id": ev["id"], "kind": ev["kind"], "name": htmllib.unescape(name),
        "brand": htmllib.unescape(brand) if isinstance(brand, str) else None,
        "price": price, "page_url": ev["final_url"], "page_host": host,
        "observed_at": ev["observed_at"], "coupon": coupon,
        "image": ev.get("image_file"), "title": ev.get("title") or "",
        "desc": str(p.get("description") or ""),
    }


def load_catalog(evidence_dir=EVIDENCE_DIR):
    """All stored evidence -> (observations, exclusions); deterministic order."""
    ok, ex = [], []
    for fn in sorted(os.listdir(evidence_dir)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(evidence_dir, fn)) as f:
            ev = json.load(f)
        state, val = extract(ev)
        (ok if state == "ok" else ex).append(val if state == "ok" else (ev["id"], val))
    return ok, ex


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "collect":
        seeds = json.load(open(sys.argv[2]))
        for s in seeds:
            if os.path.exists(os.path.join(EVIDENCE_DIR, s["id"] + ".json")):
                continue
            try:
                ev = collect_one(s)
                st, val = extract(ev)
                print(s["id"], st, val if st != "ok" else val["price"])
            except Exception as e:
                print(s["id"], "fetch-failed", str(e)[:80])
            time.sleep(1.0)
    elif len(sys.argv) >= 3 and sys.argv[1] == "reread":
        for ev_id in sys.argv[2:]:
            print(ev_id, *reread(ev_id), flush=True)
            time.sleep(1.0)
    elif len(sys.argv) == 2 and sys.argv[1] == "conditions-pass":
        for fn in sorted(os.listdir(EVIDENCE_DIR)):
            if not fn.endswith(".json"):
                continue
            ev_id = fn[:-5]
            ev = json.load(open(os.path.join(EVIDENCE_DIR, fn)))
            if ev.get("conditions") or extract(ev)[0] != "ok":
                continue
            got = conditions_pass(ev_id)
            print(ev_id, "unread" if got is None else
                  {k: len(v) for k, v in got.items()}, flush=True)
    elif len(sys.argv) == 2 and sys.argv[1] == "render-pass":
        for fn in sorted(os.listdir(EVIDENCE_DIR)):
            if not fn.endswith(".json"):
                continue
            ev_id = fn[:-5]
            ev = json.load(open(os.path.join(EVIDENCE_DIR, fn)))
            if ev.get("rendered_checked") or extract(ev)[0] != "ok":
                continue
            print(ev_id, render_pass(ev_id))
    else:
        print(__doc__)
