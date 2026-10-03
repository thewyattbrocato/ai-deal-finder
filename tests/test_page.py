"""Quiet public page: interactive guide, two-search explanation, coffee note.

Checks the generated demo/index.html and its GitHub Pages copy
docs/index.html. Offline; no invented products, prices, or coupons.

The coffee note and card attributes are the generated page contract.
Search, guide, and exact-product behavior are executed in the page script.
"""

import html as html_lib
import json
import os
import re
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Executes the generated page's own script against its markup and returns
# what a reader would see after each action. Not a source search.
DRIVER = r"""
const fs = require("fs");
const vm = require("vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const VOID = new Set(["area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"]);

function decode(s) {
  return s.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+);/g, function (all, ent) {
    const named = { quot: '"', amp: "&", lt: "<", gt: ">", apos: "'" };
    if (named[ent]) return named[ent];
    if (ent[0] === "#") {
      const hex = ent[1] === "x" || ent[1] === "X";
      return String.fromCodePoint(parseInt(ent.slice(hex ? 2 : 1), hex ? 16 : 10));
    }
    return all;
  });
}

function El(tag) {
  this.tag = tag;
  this.children = [];
  this.parent = null;
  this.attrs = {};
  this.listeners = {};
  this.style = { display: "" };
  this.className = "";
  this._text = "";
}
El.prototype.getAttribute = function (name) {
  return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
};
El.prototype.setAttribute = function (name, value) { this.attrs[name] = String(value); };
El.prototype.addEventListener = function (type, fn) {
  (this.listeners[type] = this.listeners[type] || []).push(fn);
};
let ACTIVE = null;
El.prototype.focus = function () { ACTIVE = this; };
El.prototype.dispatch = function (type) {
  for (const fn of this.listeners[type] || []) fn();
};
El.prototype.appendChild = function (child) {
  if (child.parent) child.parent.children = child.parent.children.filter(n => n !== child);
  child.parent = this;
  this.children.push(child);
  return child;
};
El.prototype.querySelectorAll = function (sel) {
  const m = /^\[([^\]]+)\]$/.exec(sel);
  if (!m) throw new Error("unsupported selector " + sel);
  const out = [];
  walk(this, el => {
    if (el !== this && Object.prototype.hasOwnProperty.call(el.attrs, m[1])) out.push(el);
  });
  return out;
};
function collect(el) {
  let s = "";
  if (el._text && el.children.length === 0) return el._text;
  s += el._text || "";
  for (const c of el.children) s += collect(c);
  return s;
}
Object.defineProperty(El.prototype, "textContent", {
  get() { return collect(this); },
  set(v) { this._text = String(v); this.children = []; },
});
Object.defineProperty(El.prototype, "innerText", { get() { return visibleText(this); } });
Object.defineProperty(El.prototype, "innerHTML", {
  set(v) {
    if (v !== "") throw new Error("unsupported innerHTML");
    this._text = "";
    this.children = [];
  },
});
Object.defineProperty(El.prototype, "value", {
  get() { return this.attrs.value || ""; },
  set(v) { this.attrs.value = String(v); },
});

function walk(el, fn) {
  fn(el);
  for (const c of el.children) walk(c, fn);
}

function parse(src) {
  const root = new El("#document");
  const stack = [root];
  const re = /<!--[\s\S]*?-->|<!DOCTYPE[^>]*>|<\s*(\/)?\s*([a-zA-Z0-9]+)\s*([^>]*?)(\/?)>|([^<]+)/g;
  let m;
  while ((m = re.exec(src))) {
    if (m[0].startsWith("<!") || m[0].startsWith("<!--")) continue;
    if (m[5] != null) {
      const text = decode(m[5]);
      if (!text) continue;
      const t = new El("#text");
      t._text = text;
      stack[stack.length - 1].appendChild(t);
      continue;
    }
    const closing = !!m[1];
    const tag = m[2].toLowerCase();
    if (closing) {
      for (let i = stack.length - 1; i > 0; i--) {
        if (stack[i].tag === tag) { stack.length = i; break; }
      }
      continue;
    }
    const el = new El(tag);
    const attrRe = /([:@\w-]+)\s*=\s*"([^"]*)"|([:@\w-]+)\s*=\s*'([^']*)'|([:@\w-]+)/g;
    let a;
    while ((a = attrRe.exec(m[3]))) {
      const key = (a[1] || a[3] || a[5]).toLowerCase();
      el.attrs[key] = decode(a[2] != null ? a[2] : (a[4] != null ? a[4] : ""));
    }
    stack[stack.length - 1].appendChild(el);
    if ((tag === "script" || tag === "style") && m[4] !== "/") {
      const end = src.indexOf("</" + tag, re.lastIndex);
      const t = new El("#text");
      t._text = src.slice(re.lastIndex, end);
      el.appendChild(t);
      re.lastIndex = src.indexOf(">", end) + 1;
      continue;
    }
    if (m[4] !== "/" && !VOID.has(tag)) stack.push(el);
  }
  return root;
}

function makeDocument(root) {
  return {
    getElementById(id) {
      let found = null;
      walk(root, el => { if (!found && el.attrs && el.attrs.id === id) found = el; });
      return found;
    },
    createElement(tag) { return new El(tag); },
    get activeElement() { return ACTIVE; },
    _root: root,
  };
}

function visibleText(el) {
  if (!el || el.tag === "script" || el.tag === "style" || el.tag === "#document") {
    if (!el || el.tag === "script" || el.tag === "style") return "";
  }
  if (el.style && el.style.display === "none") return "";
  if (el.tag === "#text") return el._text;
  if (el.tag === "script" || el.tag === "style") return "";
  let s = el.tag === "#document" ? "" : (el._text || "");
  for (const c of el.children) s += visibleText(c);
  return s;
}

function contained(node, anc) {
  let p = node;
  while (p) { if (p === anc) return true; p = p.parent; }
  return false;
}

// The page reads "today" once to say how old each stored check is; pin it.
const NOW = process.env.PAGE_NOW ? Date.parse(process.env.PAGE_NOW) : Date.UTC(2026, 9, 5, 15, 0, 0);
class FixedDate extends Date {
  constructor(...a) { if (a.length) super(...a); else super(NOW); }
}

function boot() {
  ACTIVE = null;
  const root = parse(html);
  const document = makeDocument(root);
  const scripts = [];
  walk(root, el => {
    if (el.tag === "script" && !el.attrs.src) scripts.push(el.textContent);
  });
  const context = vm.createContext({
    document: document,
    console: console,
    Array: Array,
    parseInt: parseInt,
    Date: FixedDate,
  });
  for (const code of scripts) vm.runInContext(code, context);
  return document;
}

function snap(document) {
  const results = document.getElementById("results");
  const cards = results.querySelectorAll("[data-keywords]");
  const buttons = [];
  let tables = 0;
  walk(document._root, el => {
    if (el.tag === "button") buttons.push(collect(el).trim());
    if (el.tag === "table") tables += 1;
  });
  const controls = [];
  const legends = [];
  walk(document.getElementById("guide-dyn"), el => {
    if (el.tag === "legend") legends.push(collect(el).trim());
    if ((el.tag === "input" || el.tag === "select") && el.attrs["data-guide-key"]) {
      controls.push({
        key: el.attrs["data-guide-key"], tag: el.tag,
        value: el.tag === "select" ? el.value : el.attrs.value,
        checked: el.tag === "input" ? !!el.checked : null,
        disabled: Object.prototype.hasOwnProperty.call(el.attrs, "disabled"),
        label: el.tag === "input" ? collect(el.parent).trim() : null,
        options: el.tag === "select" ? el.children.map(o => collect(o).trim()) : null,
        offDisabled: el.tag === "select" ? el.children.filter(o => Object.prototype.hasOwnProperty.call(o.attrs, "disabled")).map(o => collect(o).trim()) : null,
      });
    }
  });
  const shown = cards.filter(c => c.style.display !== "none");
  const first = (c, a) => c.querySelectorAll(a)[0];
  return {
    status: collect(document.getElementById("guide-status")).trim(),
    guideText: visibleText(document.getElementById("guide")),
    legends: legends,
    controls: controls,
    hiddenItems: document.getElementById("hidden-list").children.map(li => collect(li).trim()),
    hiddenShown: document.getElementById("hidden-by").style.display !== "none",
    bestShown: document.getElementById("guide-best").style.display !== "none",
    best: collect(document.getElementById("guide-best-text")).trim(),
    whys: shown.map(c => collect(first(c, "[data-why]")).trim()),
    prices: shown.map(c => collect(first(c, "[data-price-text]")).trim()),
    headings: shown.map(c => collect(first(c, "[data-heading]")).trim()),
    subNotes: shown.map(c => first(c, "[data-sub-note]").style.display === "none" ? "" : collect(first(c, "[data-sub-note]")).trim()),
    terms: shown.map(c => collect(first(c, "[data-terms-block]")).trim()),
    visible: shown.map(card),
    all: cards.map(card),
    mode: collect(document.getElementById("mode-text")).trim(),
    count: collect(document.getElementById("result-count")).trim(),
    resultsInGuide: contained(results, document.getElementById("guide")),
    tables: tables,
    buttons: buttons,
    exactNote: document.getElementById("exact-note") !== null,
    blockedClaim: visibleText(document._root).indexOf("Target, Walmart, Kroger") !== -1,
    noMatch: document.getElementById("no-match").style.display,
    focus: ACTIVE ? { key: ACTIVE.attrs["data-guide-key"] || null, value: ACTIVE.attrs.value || null,
      inGuide: contained(ACTIVE, document.getElementById("guide-dyn")) } : null,
    emptyText: collect(document.getElementById("no-match-text")).trim(),
    emptyActions: document.getElementById("no-match-actions").children.map(b => collect(b).trim()),
    savings: shown.map(c => collect(first(c, "[data-savings]")).trim()),
    ages: shown.map(c => collect(first(c, "[data-age]")).trim()),
    leads: shown.map(c => collect(first(c, "[data-saving-lead]")).trim()),
    shelfLines: shown.map(c => collect(first(c, "[data-shelf-line]")).trim()),
    windows: cards.filter(c => c.getAttribute("data-coupon") === "yes").map(c => ({
      id: c.getAttribute("data-name"),
      code: c.getAttribute("data-coupon-code"),
      state: c.getAttribute("data-window-state"),
      status: collect(first(c, "[data-window-status]")).trim(),
      lead: collect(first(c, "[data-saving-lead]")).trim(),
      label: collect(first(c, "[data-coupon-label]")).trim(),
      confirm: collect(first(c, "[data-confirm-code]")).trim(),
      price: collect(first(c, "[data-price-text]")).trim(),
      priceLabel: c.getAttribute("data-price-label"),
      conditions: c.querySelectorAll("[data-conditions-row]").map(r => collect(r).trim()),
      windowStart: c.querySelectorAll("[data-window-row]")[0].getAttribute("data-window-start"),
    })),
  };
}
function card(c) {
  return {
    name: c.getAttribute("data-name"),
    kind: c.getAttribute("data-kind"),
    form: c.getAttribute("data-form"),
    coupon: c.getAttribute("data-coupon"),
    quality: c.getAttribute("data-quality"),
    windowState: c.getAttribute("data-window-state"),
  };
}
function setQuery(document, value) {
  const q = document.getElementById("q");
  q.value = value;
  q.dispatch("input");
}
function answer(document, key, value) {
  let found = null;
  walk(document._root, el => {
    if ((el.tag === "input" || el.tag === "select") && el.attrs["data-guide-key"] === key
        && (el.tag === "select" || el.attrs.value === value)) found = el;
  });
  if (!found) throw new Error("missing answer " + key + "=" + value);
  if (found.tag === "input" && Object.prototype.hasOwnProperty.call(found.attrs, "disabled")) throw new Error("disabled answer " + key + "=" + value);
  if (found.tag === "select") {
    found.value = value;
  } else {
    found.checked = true;
  }
  found.dispatch("change");
}
function answerFocused(document, key, value) {
  walk(document._root, el => {
    if ((el.tag === "input" || el.tag === "select") && el.attrs["data-guide-key"] === key
        && (el.tag === "select" || el.attrs.value === value)) el.focus();
  });
  answer(document, key, value);
}
function clickAction(document, text) {
  let found = null;
  walk(document.getElementById("no-match-actions"), el => {
    if (el.tag === "button" && collect(el).trim().indexOf(text) === 0) found = el;
  });
  if (!found) throw new Error("missing action " + text);
  found.dispatch("click");
}
function clickId(document, id) {
  const el = document.getElementById(id);
  if (!el) throw new Error("missing #" + id);
  el.dispatch("click");
}

const out = {};
function fresh(fn) { const document = boot(); fn(document); return snap(document); }
out.load = fresh(() => {});
if (process.env.ONLY_LOAD) { process.stdout.write(JSON.stringify(out)); process.exit(0); }
out.allProducts = fresh(d => { setQuery(d, ""); });
out.anyCoffee = fresh(d => { setQuery(d, ""); answer(d, "form", "any-coffee"); });
out.wholeBean = fresh(d => { setQuery(d, ""); answer(d, "form", "whole-bean"); });
out.wholeBeanThenAnything = fresh(d => {
  setQuery(d, ""); answer(d, "form", "whole-bean"); answer(d, "form", "");
});
out.specialty = fresh(d => { setQuery(d, ""); answer(d, "prefer", "specialty"); });
out.specialtyThenPrice = fresh(d => {
  setQuery(d, ""); answer(d, "prefer", "specialty"); answer(d, "prefer", "price");
});
out.couponOnly = fresh(d => { setQuery(d, ""); answer(d, "coupon", "yes"); });
out.combined = fresh(d => {
  setQuery(d, "");
  answer(d, "prefer", "specialty"); answer(d, "form", "whole-bean"); answer(d, "coupon", "yes");
});
out.combinedChanged = fresh(d => {
  setQuery(d, "");
  answer(d, "prefer", "specialty"); answer(d, "form", "whole-bean"); answer(d, "coupon", "yes");
  answer(d, "coupon", "all");
});
out.resetAfterCombined = fresh(d => {
  setQuery(d, "");
  answer(d, "prefer", "specialty"); answer(d, "form", "whole-bean"); answer(d, "coupon", "yes");
  clickId(d, "guide-reset");
});
out.exactQualita = fresh(d => { clickId(d, "mode-exact"); setQuery(d, "qualita rossa"); });
out.exactAccent = fresh(d => { clickId(d, "mode-exact"); setQuery(d, "qualità rossa"); });
out.exactSuper = fresh(d => { clickId(d, "mode-exact"); setQuery(d, "super crema"); });
out.exactMidnight = fresh(d => { clickId(d, "mode-exact"); setQuery(d, "midnight axes"); });
out.exactAirpods = fresh(d => { clickId(d, "mode-exact"); setQuery(d, "airpods pro"); });
// bag size: just the 2 lb bags, just the 5 lb bags, and back
out.size12 = fresh(d => { answer(d, "coffee_size", "12 oz"); });
out.size2lb = fresh(d => { setQuery(d, "midnight"); answer(d, "coffee_size", "2 lb"); });
out.coffee2lb = fresh(d => { answer(d, "coffee_size", "2 lb"); });
out.coffee5lb = fresh(d => { answer(d, "coffee_size", "5 lb"); });
out.coffee22 = fresh(d => { answer(d, "coffee_size", "2.2 lb"); });
out.coffee5lbBack = fresh(d => { answer(d, "coffee_size", "5 lb"); answer(d, "coffee_size", ""); });
// subscribe / shipping: stated vs unknown
out.subscribe = fresh(d => { answer(d, "purchase", "subscribe"); });
out.subFree5lb = fresh(d => {
  answer(d, "coffee_size", "5 lb"); answer(d, "purchase", "subscribe"); answer(d, "shipping", "free");
});
out.clothingFree = fresh(d => { setQuery(d, "clothing"); answer(d, "shipping", "free"); });
out.sub2lb = fresh(d => { answer(d, "coffee_size", "2 lb"); answer(d, "purchase", "subscribe"); });
out.subFree5lbReset = fresh(d => {
  answer(d, "coffee_size", "5 lb"); answer(d, "purchase", "subscribe"); answer(d, "shipping", "free");
  clickId(d, "guide-reset");
});
// kinds that grow their own questions
out.shoes = fresh(d => { setQuery(d, "shoes"); });
out.shoe8 = fresh(d => { setQuery(d, "shoes"); answer(d, "shoe_size", "8"); });
out.shoeNikeW8 = fresh(d => { setQuery(d, "shoes"); answer(d, "shoe_size", "W 8 / M 6.5"); });
out.shoeNikeOut = fresh(d => { setQuery(d, "shoes"); answer(d, "shoe_size", "W 11.5 / M 10"); });
out.clothing = fresh(d => { setQuery(d, "clothing"); });
out.clothingXs = fresh(d => { setQuery(d, "clothing"); answer(d, "clothing_size", "XS"); });
out.clothingM = fresh(d => { setQuery(d, "clothing"); answer(d, "clothing_size", "M"); });
out.airpods = fresh(d => { setQuery(d, "airpods"); });
out.tea = fresh(d => { setQuery(d, "tea"); });
// what each offered answer says it would leave, against what choosing it leaves
function optionCounts(query) {
  const rows = [];
  const base = boot();
  if (query != null) setQuery(base, query);
  const found = snap(base).controls.filter(c => c.key !== "prefer");
  for (const c of found) {
    const value = c.tag === "select" ? null : c.value;
    const options = c.tag === "select" ? c.options : [c.label];
    options.forEach((label, i) => {
      const d = boot();
      if (query != null) setQuery(d, query);
      let v = value;
      if (c.tag === "select") {
        const sel = [];
        walk(d._root, el => { if (el.tag === "select" && el.attrs["data-guide-key"] === c.key) sel.push(el); });
        v = sel[0].children[i].attrs.value;
      }
      answer(d, c.key, v);
      const m = /^(?:Your answers: .*\. )?(\d+) match/.exec(snap(d).status) || /(\d+) match, \d+ hidden/.exec(snap(d).status);
      rows.push({ key: c.key, label: label, said: parseInt(/\((\d+)\)$/.exec(label)[1], 10), left: parseInt(m[1], 10) });
    });
  }
  return rows;
}
out.counts = { coffee: optionCounts(null), shoes: optionCounts("shoes"), clothing: optionCounts("clothing"), all: optionCounts("") };
out.focusKept = fresh(d => { answerFocused(d, "coupon", "yes"); });
out.focusKeptSize = fresh(d => { answerFocused(d, "coffee_size", "5 lb"); });
// nothing matches: a way back, with what each step restores
const emptyAnswers = d => {
  answer(d, "coffee_size", "12 oz"); answer(d, "coupon", "yes"); setQuery(d, "medium");
};
out.emptyAnswers = fresh(emptyAnswers);
out.emptyAnswersDrop = fresh(d => { emptyAnswers(d); clickAction(d, "Drop “Which coupons"); });
out.emptyAnswersReset = fresh(d => { emptyAnswers(d); clickAction(d, "Reset all answers"); });
out.emptySearch = fresh(d => { setQuery(d, "blend"); });
out.emptySearchClear = fresh(d => { setQuery(d, "blend"); clickAction(d, "Clear the search"); });
out.emptyExact = fresh(d => { clickId(d, "mode-exact"); setQuery(d, "honest"); });
out.emptyExactSwitch = fresh(d => {
  clickId(d, "mode-exact"); setQuery(d, "honest"); clickAction(d, "Switch to Kind of thing");
});
// an answer that no longer fits the search is dropped, not left filtering
out.sizeThenKind = fresh(d => { answer(d, "coffee_size", "5 lb"); setQuery(d, "airpods"); });
out.exactMidnight5lb = fresh(d => {
  clickId(d, "mode-exact"); setQuery(d, "midnight axes"); answer(d, "coffee_size", "5 lb");
});
{
  const document = boot();
  clickId(document, "mode-exact");
  setQuery(document, "airpods pro");
  out.exactAirpods2 = snap(document);
  clickId(document, "mode-open");
  out.backToKind = snap(document);
}
process.stdout.write(JSON.stringify(out));
"""


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def drive(page_path, now=None, only_load=False):
    env = dict(os.environ, TZ="UTC")  # the page reads the browser's local date
    if now:
        env["PAGE_NOW"] = now
    if only_load:
        env["ONLY_LOAD"] = "1"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(DRIVER)
        script = handle.name
    try:
        proc = subprocess.run(
            ["node", script, page_path],
            check=False, capture_output=True, text=True, env=env,
        )
    finally:
        os.remove(script)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


def names(snap):
    return [card["name"] for card in snap["visible"]]


class QuietPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = read("demo", "index.html")
        cls.driven = drive(os.path.join(ROOT, "demo", "index.html"))
        cls.counts = cls.driven.pop("counts")

    def test_pages_copy_matches_demo(self):
        self.assertEqual(self.page, read("docs", "index.html"))

    def test_coffee_note_matches_evidence(self):
        m = re.search(r"Coffee note: ([^<]*)", self.page)
        self.assertIsNotNone(m)
        note = m.group(1)
        self.assertIn("Dolcevita Classico, Qualità Rossa and Super Crema "
                      "showed the code AS20", note)
        for seller in ("Honest Coffee Roasters", "The Well Coffee Roasters",
                       "Counter Culture Coffee"):
            self.assertIn(seller, note)
        self.assertIn("shelf price", note)

    def test_coupon_cards_match_note(self):
        cards = re.split(r'(?=<section class="card)', self.page)
        with_code = {re.search(r'data-name="([^"]*)"', c).group(1)
                     for c in cards if 'data-coupon="yes"' in c
                     and "AS20" in c}
        self.assertEqual(len(with_code), 3)
        for c in cards:
            if "Midnight Axes" in c or "Watershed" in c or "Big Trouble" in c:
                self.assertIn('data-coupon="no"', c)

    def test_lavazza_records_carry_the_2026_10_03_observation(self):
        import glob
        import json
        files = sorted(glob.glob(os.path.join(ROOT, "demo", "evidence",
                                              "lavazza", "*.json")))
        self.assertEqual(len(files), 3)
        cards = re.split(r'(?=<section class="card)', self.page)
        for fn in files:
            with open(fn, encoding="utf-8") as f:
                rec = json.load(f)
            first, latest = rec["observations"][0], rec["observations"][-1]
            # the earlier CAFE20 read stays as dated history, never deleted
            self.assertEqual((first["code"], first["observed_at"][:10]),
                             ("CAFE20", "2026-10-01"), fn)
            self.assertEqual((latest["code"], latest["observed_at"][:10]),
                             ("AS20", "2026-10-03"), fn)
            self.assertIn("AS20", latest["banner"])
            self.assertFalse(latest["code_tried"])
            self.assertEqual(latest["shelf_price"], first["shelf_price"])
            card = [c for c in cards if rec["page_url"] in c]
            self.assertEqual(len(card), 1, fn)
            card = card[0]
            self.assertIn("Checked: lavazzausa.com \u00b7 US \u00b7 "
                          + latest["observed_at"], card)
            self.assertIn(">AS20</span>", card)
            self.assertNotIn("CAFE20", card)
            self.assertIn("never tried out", card)
            self.assertIn("price shown does not include it", card)
            self.assertIn('data-price="%d"' % round(latest["shelf_price"] * 100), card)
        self.assertNotIn("CAFE20", self.page)

    def test_card_names_are_unique(self):
        names_found = [card["name"] for card in self.driven["load"]["all"]]
        self.assertTrue(names_found)
        self.assertEqual(len(names_found), len(set(names_found)))

    def test_guide_asks_only_what_the_results_fit(self):
        d = self.driven
        self.assertEqual(d["load"]["legends"], [
            "Coffee bag size", "Which coupons?", "What kind?", "How you would buy",
            "What matters most?"])
        self.assertEqual(d["shoes"]["legends"], ["Shoe size"])
        self.assertEqual(d["clothing"]["legends"],
                         ["Clothing size", "Shipping", "Which coupons?"])
        self.assertEqual(d["airpods"]["legends"], [])
        self.assertEqual(d["tea"]["legends"], [])
        self.assertIn("Nothing to narrow", d["tea"]["guideText"])
        shoe = [c for c in d["shoes"]["controls"] if c["key"] == "shoe_size"][0]
        self.assertEqual(shoe["tag"], "select")
        self.assertEqual(shoe["options"][0], "Any size (15)")
        self.assertIn("W 8 / M 6.5 (1)", shoe["options"])
        self.assertIn("8 (2)", shoe["options"])
        for key in ("load", "tea", "airpods"):
            self.assertFalse([c for c in d[key]["controls"] if c["key"].endswith("_size")
                              and c["key"] != "coffee_size"], key)
        self.assertEqual(
            [c["label"] for c in d["load"]["controls"] if c["key"] == "coffee_size"],
            ["Any size (21)", "12 oz (4)", "24 oz (1)", "2 lb (2)", "2.2 lb (2)", "5 lb (3)"])
        self.assertEqual(d["load"]["buttons"], [
            "Kind of thing", "Exact product", "Search",
            "Reset — show everything", "Show more matches"])
        self.assertFalse(d["load"]["resultsInGuide"])
        self.assertEqual(d["load"]["tables"], 0)
        self.assertIn("similar checked products", d["load"]["mode"])
        self.assertIn("the price shown is the shelf price", d["load"]["mode"])
        self.assertRegex(d["load"]["status"],
                         r"^No answers set\. \d+ match, 0 hidden by your answers\.$")
        self.assertGreaterEqual(len(d["load"]["all"]), 100)
        self.assertLessEqual(len(d["load"]["visible"]), 12)

    def test_an_answer_that_no_longer_fits_the_search_is_dropped(self):
        dropped = self.driven["sizeThenKind"]
        self.assertTrue(dropped["status"].startswith("No answers set."))
        self.assertEqual(names(dropped), ["AirPods Pro 3"])

    def test_coffee_bag_size_shows_just_that_size_and_its_prices(self):
        d = self.driven
        two = d["coffee2lb"]
        self.assertEqual(two["prices"], ["$38.00", "$51.50"])
        self.assertEqual([n.split(",")[0] for n in names(two)],
                         ["Midnight Axes dark roast", "Watershed light roast"])
        self.assertEqual(two["headings"], ["Midnight Axes dark roast — 2 lb",
                                           "Watershed light roast — 2 lb"])
        self.assertTrue(any("Big Trouble" in h and "does not list a 2 lb bag" in h
                            for h in two["hiddenItems"]))
        five = d["coffee5lb"]
        self.assertEqual(five["prices"], ["$95.00", "$101.00", "$119.00"])
        self.assertEqual(len(five["visible"]), 3)
        lavazza = d["coffee22"]
        self.assertEqual(lavazza["prices"], ["$24.99", "$26.99"])
        self.assertTrue(all("Whole Bean, 2.2 lb" in n for n in names(lavazza)))
        twelve = d["size12"]
        self.assertEqual(twelve["prices"][:4], ["$13.99", "$18.00", "$19.50", "$20.50"])
        back = d["coffee5lbBack"]
        self.assertEqual(names(back), names(d["load"]))
        self.assertEqual(back["prices"], d["load"]["prices"])
        self.assertIn("Best under your answers: Midnight Axes dark roast — 5 lb at $95.00",
                      five["best"])
        self.assertIn("(shelf price)", five["best"])
        self.assertFalse(back["bestShown"])
        # a 2 lb bag is a different purchase from a 12 oz one: no cross-size "best"
        self.assertEqual(d["exactMidnight5lb"]["prices"], ["$95.00"])

    def test_subscribe_and_shipping_count_only_where_the_page_stated_them(self):
        d = self.driven
        sub = d["subscribe"]
        self.assertEqual(sub["prices"][:3], ["$18.00", "$19.50", "$20.50"])  # shelf stays
        self.assertIn("Subscribe price the page printed: $13.50 for 12 oz. Shelf price above is unchanged.",
                      sub["subNotes"][0])
        self.assertIn("Subscribe price the page printed: $17.50 for 12 oz", sub["subNotes"][1])
        self.assertIn("Subscribe price the page printed: $18.45 for 12 oz", sub["subNotes"][2])
        lav = [n for nm, n in zip(names(sub), sub["subNotes"]) if "Whole Bean" in nm
               and ("Qualit" in nm or "Super" in nm or "Classico" in nm)]
        self.assertEqual(len(lav), 3)
        for n in lav:
            self.assertIn("printed no subscribe price (25% stated)", n)
        self.assertIn("not ranked", sub["best"])
        self.assertTrue(any("Midnight Axes" not in nm for nm in names(sub)))
        clothes = d["clothingFree"]
        self.assertEqual(len(clothes["visible"]), 3)
        joined = " | ".join(clothes["hiddenItems"])
        self.assertIn("free shipping is stated only for members", joined)
        self.assertIn("did not state shipping", joined)
        for why in clothes["whys"]:
            self.assertIn("its page states its shipping as", why)
        five = d["subFree5lb"]
        self.assertEqual(five["prices"], ["$101.00", "$119.00"])
        self.assertEqual(five["subNotes"][0],
                         "Subscribe price the page printed: $90.65 for 5 lb. Shelf price above is unchanged.")
        self.assertEqual(five["subNotes"][1][:48],
                         "Subscribe price the page printed: $107.10 for 5 ")
        self.assertIn("Best under your answers: Big Trouble medium-dark roast — 5 lb at $90.65",
                      five["best"])
        self.assertIn("(subscribe price the page printed; shelf price $101.00)", five["best"])
        self.assertIn("“Free shipping on $30 & up!”", five["best"])
        self.assertIn("never part of this ranking", five["best"])
        self.assertTrue(any("Midnight Axes" in h and "did not state shipping" in h
                            for h in five["hiddenItems"]))
        self.assertTrue(any("free shipping starts at" in h and "what it costs below that is not stated" in h
                            for h in five["hiddenItems"]))
        two = d["sub2lb"]  # no 2 lb page states free shipping, so that answer is not offered
        self.assertTrue(two["visible"])
        self.assertEqual([c["label"] for c in two["controls"] if c["key"] == "shipping"], [])
        reset = d["subFree5lbReset"]
        self.assertEqual(names(reset), names(d["load"]))
        self.assertFalse(reset["bestShown"])
        for key, snap in d.items():
            for text in snap["whys"] + [snap["best"]]:
                self.assertNotIn("CAFE20", text, key)
                self.assertNotIn("AS20", text if "printed AS20" not in text else "", key)

    def test_shoe_and_clothing_sizes_use_only_sizes_the_page_listed(self):
        d = self.driven
        eight = d["shoe8"]
        self.assertEqual(sorted(names(eight)),
                         ["Men's Cruiser Slip On", "Women's Canvas Runner NZ"])
        joined = " | ".join(eight["hiddenItems"])
        self.assertIn("Air Jordan OG Women's Shoes — its page does not list size 8", joined)
        self.assertIn("Men's Canvas Runner NZ — its page lists size 8 but it was not shown in stock", joined)
        nike = d["shoeNikeW8"]
        self.assertEqual(names(nike), ["Air Jordan OG Women's Shoes"])
        self.assertEqual(nike["prices"], ["$87.97"])
        out = d["shoeNikeOut"]
        self.assertEqual(out["visible"], [])
        self.assertTrue(any("Air Jordan" in h and "not shown in stock when checked" in h
                            for h in out["hiddenItems"]))
        xs = d["clothingXs"]
        self.assertTrue(all(c["kind"] == "Clothing" for c in xs["visible"]))
        m = d["clothingM"]
        self.assertIn("High-Waisted SoComfy Wide-Leg Sweatpants", names(m))
        self.assertTrue(any("CashSoft Crop Cardigan" in h and "not shown in stock" in h
                            for h in m["hiddenItems"]))

    def test_silent_pages_say_unknown_and_nothing_is_filled_in(self):
        unknown = "not stated on the page — unknown"
        cards = [c for c in re.split(r'(?=<section class="card)', self.page)
                 if c.startswith('<section class="card bg-base-100')]
        self.assertGreaterEqual(len(cards), 100)
        silent = 0
        for c in cards:
            block = re.search(r'data-terms-block>(.*?)</div>', c, re.S).group(1)
            text = re.sub(r"<[^>]+>", " ", block)
            for label in ("Size:", "Shipping:", "Subscribe:"):
                self.assertIn(label, text)
            if unknown in text:
                silent += 1
        self.assertGreater(silent, 100)
        nike = [c for c in cards if "Air Jordan OG Women" in c][0]
        self.assertIn("Subscribe:</span> " + unknown, nike)
        honest = [c for c in cards if "Midnight Axes" in c][0]
        self.assertIn("Shipping:</span> " + unknown, honest)
        self.assertIn("12 oz $13.50", honest)
        lavazza = [c for c in cards if "Super Crema" in c][0]
        self.assertIn("the subscribe price itself is not shown", lavazza)
        self.assertNotIn("$20.24", lavazza)  # never 75% of the shelf price

    def test_kind_with_no_questions_and_airpods_shipping(self):
        air = self.driven["airpods"]
        self.assertEqual(names(air), ["AirPods Pro 3"])
        self.assertEqual(air["controls"], [])  # one result: no question could narrow it
        self.assertEqual(self.driven["tea"]["controls"], [])
        self.assertEqual(len(self.driven["tea"]["visible"]), 6)

    def test_form_answers_narrow_and_can_be_changed_back(self):
        any_coffee = self.driven["anyCoffee"]
        coffee = [card for card in any_coffee["all"] if card["kind"] == "Coffee"]
        self.assertEqual(len(any_coffee["visible"]), min(12, len(coffee)))
        self.assertTrue(set(names(any_coffee)) <= {c["name"] for c in coffee})
        self.assertNotIn("AirPods Pro 3", names(any_coffee))
        self.assertEqual(any_coffee["noMatch"], "none")
        whole = self.driven["wholeBean"]
        beans = [card for card in whole["all"] if card["form"] == "whole-bean"]
        self.assertEqual(len(whole["visible"]), min(12, len(beans)))
        self.assertTrue(set(names(whole)) <= {c["name"] for c in beans})
        self.assertNotIn("AirPods Pro 3", names(whole))
        self.assertTrue(whole["hiddenShown"])
        self.assertTrue(any("Whole bean" in h for h in whole["hiddenItems"]))
        self.assertLessEqual(len(whole["hiddenItems"]), 13)
        back = self.driven["wholeBeanThenAnything"]
        self.assertEqual(len(back["visible"]), 12)
        self.assertTrue(any(c["kind"] != "Coffee" for c in back["visible"]))
        self.assertFalse(back["hiddenShown"])

    def test_every_shown_card_says_why_and_only_from_page_facts(self):
        for key in ("load", "wholeBean", "couponOnly", "combined", "specialty", "coffee5lb"):
            snap = self.driven[key]
            self.assertEqual(len(snap["whys"]), len(snap["visible"]), key)
            for why in snap["whys"]:
                self.assertTrue(why.startswith("Shown because "), key)
        by_name = dict(zip(names(self.driven["couponOnly"]),
                           self.driven["couponOnly"]["whys"]))
        rossa = by_name["Qualità Rossa Whole Bean, 2.2 lb bag"]
        self.assertIn("its own page printed AS20", rossa)
        self.assertIn("never tried", rossa)
        self.assertIn("the price is still the shelf price", rossa)
        for why in self.driven["couponOnly"]["whys"]:
            self.assertNotIn("save", why.lower())
        for card, why in zip(self.driven["specialty"]["visible"],
                             self.driven["specialty"]["whys"]):
            if card["quality"] == "independent-roastery":
                self.assertIn("listed first", why)
            else:
                self.assertIn("listed after", why)
        cheapest = self.driven["load"]["whys"][0]
        self.assertIn("lowest of", cheapest)

    def test_answers_combine_react_live_and_reset_restores_everything(self):
        combined = self.driven["combined"]
        for card in combined["visible"]:
            self.assertEqual(card["form"], "whole-bean")
            self.assertEqual(card["coupon"], "yes")
        self.assertTrue(combined["visible"])
        self.assertTrue(combined["hiddenShown"])
        self.assertIn("Whole bean", combined["status"])
        self.assertIn("Only with a printed coupon", combined["status"])
        self.assertIn("Specialty-roaster quality first", combined["status"])
        changed = self.driven["combinedChanged"]
        self.assertGreater(len(changed["visible"]), len(combined["visible"]))
        self.assertNotIn("Only with a printed coupon", changed["status"])
        reset = self.driven["resetAfterCombined"]
        self.assertEqual(len(reset["visible"]), 12)
        defaults = {"prefer": "price", "form": "", "coffee_size": "", "purchase": "any",
                    "shipping": "any", "coupon": "all"}
        checked = {c["key"]: c["value"] for c in reset["controls"]
                   if c["tag"] == "input" and c["checked"]}
        self.assertEqual(checked, defaults)
        self.assertFalse(reset["hiddenShown"])
        self.assertTrue(reset["status"].startswith("No answers set."))

    def test_guide_never_shows_a_coupon_the_page_did_not_print(self):
        coupons = self.driven["couponOnly"]
        self.assertTrue(coupons["visible"])
        self.assertTrue(all(card["coupon"] == "yes" for card in coupons["visible"]))
        self.assertNotIn("AirPods Pro 3", names(coupons))
        self.assertTrue(any("Midnight Axes" in h and "no coupon code" in h
                            for h in coupons["hiddenItems"]) or
                        all("Midnight Axes" not in n for n in names(coupons)))
        for key, snap in self.driven.items():
            self.assertFalse(snap["blockedClaim"], key)
            for why in snap["whys"]:
                if "AS20" in why or "EXTRA" in why:
                    self.assertIn("printed", why, key)
        exact = self.driven["exactSuper"]
        self.assertEqual(len(exact["visible"]), 1)
        self.assertNotIn("Which coupons?", exact["legends"])  # one item: nothing to narrow
        # a seen code is never in the best-price line or a subscribe/shipping view
        for key in ("subFree5lb", "subscribe", "coffee5lb"):
            self.assertNotRegex(self.driven[key]["best"], r"CAFE20|AS20|EXTRA")

    def test_exact_search_is_one_named_item(self):
        for key in ("exactQualita", "exactAccent"):
            shown = self.driven[key]
            self.assertEqual(names(shown), ["Qualità Rossa Whole Bean, 2.2 lb bag"], key)
            self.assertIn("one named item", shown["mode"])
            self.assertFalse(shown["exactNote"], key)
            self.assertFalse(shown["blockedClaim"], key)
        super_crema = self.driven["exactSuper"]
        self.assertEqual(len(super_crema["visible"]), 1)
        self.assertIn("Super Crema", super_crema["visible"][0]["name"])
        midnight = self.driven["exactMidnight"]
        self.assertEqual(len(midnight["visible"]), 1)
        self.assertIn("Midnight Axes", midnight["visible"][0]["name"])
        self.assertEqual(names(self.driven["exactAirpods"]), ["AirPods Pro 3"])
        self.assertEqual(self.driven["exactMidnight5lb"]["headings"],
                         ["Midnight Axes dark roast — 5 lb"])

    def test_kind_search_still_sorts_specialty_and_price(self):
        specialty = self.driven["specialty"]
        self.assertEqual(len(specialty["visible"]), 12)
        seen_other = False
        seen_roaster = False
        for card in specialty["visible"]:
            if card["quality"] == "independent-roastery":
                self.assertFalse(seen_other)
                seen_roaster = True
            else:
                seen_other = True
        self.assertTrue(seen_roaster)
        price_again = self.driven["specialtyThenPrice"]
        self.assertEqual(names(price_again), names(self.driven["allProducts"]))
        kind = self.driven["backToKind"]
        self.assertIn("similar checked products", kind["mode"])
        self.assertTrue(all(card["kind"] == "Coffee" for card in kind["visible"]))
        self.assertGreater(len(kind["visible"]), 1)

    def test_guide_text_makes_no_savings_or_retailer_claims(self):
        for key in ("load", "shoes", "clothing", "airpods", "tea", "subFree5lb"):
            text = self.driven[key]["guideText"].lower()
            for banned in ("savings", "discount", "target", "walmart", "kroger",
                           "best deal", "you save", "% off"):
                self.assertNotIn(banned, text, key)
        load = self.driven["load"]["guideText"]
        self.assertIn("never a lower price", load)
        self.assertIn("shelf price", load)
        self.assertIn("not guessed", self.driven["shoes"]["guideText"])

    # ---- smarter questions -------------------------------------------------

    def test_every_count_beside_an_answer_is_what_choosing_it_leaves(self):
        total = 0
        for name, rows in self.counts.items():
            self.assertTrue(rows, name)
            for row in rows:
                total += 1
                self.assertEqual(row["said"], row["left"], (name, row))
        self.assertGreater(total, 60)

    def test_an_answer_that_would_leave_nothing_is_not_offered(self):
        for key in ("load", "shoes", "clothing", "allProducts"):
            for c in self.driven[key]["controls"]:
                labels = c["options"] if c["tag"] == "select" else [c["label"]]
                for label in labels:
                    self.assertFalse(label.endswith("(0)"), (key, label))
        shoe = [c for c in self.driven["shoes"]["controls"] if c["key"] == "shoe_size"][0]
        self.assertNotIn("5 (0)", shoe["options"])
        self.assertIn("one that would leave nothing is not offered".replace("one", "an answer"),
                      self.driven["load"]["guideText"])

    def test_a_question_that_would_not_change_the_list_is_not_asked(self):
        d = self.driven
        # one result, or an exact item: nothing to narrow
        self.assertEqual(d["airpods"]["legends"], [])
        self.assertNotIn("Which coupons?", d["exactSuper"]["legends"])
        self.assertNotIn("Coffee bag size", d["tea"]["legends"])
        # free shipping is stated by no coffee page in the list: not asked
        self.assertNotIn("Shipping", d["load"]["legends"])
        self.assertIn("Shipping", d["clothing"]["legends"])
        # the order question appears only while it would reorder the list
        self.assertIn("What matters most?", d["load"]["legends"])
        self.assertNotIn("What matters most?", d["couponOnly"]["legends"])

    def test_questions_come_in_order_of_how_much_they_narrow(self):
        load = self.driven["load"]
        # coffee_size narrows 20 -> 1 at most, coupons 20 -> 3, kind 20 -> 6, subscribe 20 -> 6
        self.assertEqual(load["legends"][:2], ["Coffee bag size", "Which coupons?"])
        self.assertEqual(load["legends"][-1], "What matters most?")  # reorders, never narrows
        everything = self.driven["allProducts"]["legends"]
        self.assertLess(everything.index("Coffee bag size"), everything.index("Which coupons?"))

    def test_the_question_just_answered_keeps_keyboard_focus(self):
        for key in ("focusKept", "focusKeptSize"):
            focus = self.driven[key]["focus"]
            self.assertTrue(focus["inGuide"], key)
        self.assertEqual(self.driven["focusKept"]["focus"]["key"], "coupon")
        self.assertEqual(self.driven["focusKept"]["focus"]["value"], "yes")
        self.assertEqual(self.driven["focusKeptSize"]["focus"]["value"], "5 lb")

    def test_nothing_matching_offers_a_way_back_with_counts(self):
        d = self.driven
        empty = d["emptyAnswers"]
        self.assertEqual(empty["visible"], [])
        self.assertEqual(empty["noMatch"], "")
        self.assertIn("No checked page fits all of your answers", empty["emptyText"])
        self.assertEqual(empty["emptyActions"], [
            "Drop “Coffee bag size: 12 oz” — 2 would match",
            "Drop “Which coupons: Only with a printed coupon” — 1 would match",
            "Reset all answers — 3 would match"])
        dropped = d["emptyAnswersDrop"]
        self.assertEqual(len(dropped["visible"]), 1)
        self.assertEqual(dropped["noMatch"], "none")
        self.assertEqual(dropped["emptyActions"], [])
        self.assertIn("Coffee bag size: 12 oz", dropped["status"])
        self.assertNotIn("Only with a printed coupon", dropped["status"])
        reset = d["emptyAnswersReset"]
        self.assertEqual(len(reset["visible"]), 3)
        self.assertTrue(reset["status"].startswith("No answers set."))
        none = d["emptySearch"]
        self.assertEqual(none["visible"], [])
        self.assertIn("No checked page matches “blend”", none["emptyText"])
        self.assertIn("nothing is invented", none["emptyText"])
        self.assertEqual(len(none["emptyActions"]), 1)
        self.assertTrue(none["emptyActions"][0].startswith("Clear the search — show all "))
        cleared = d["emptySearchClear"]
        self.assertEqual(len(cleared["visible"]), 12)
        self.assertEqual(cleared["noMatch"], "none")
        exact = d["emptyExact"]
        self.assertIn("as one named product", exact["emptyText"])
        self.assertEqual(len(exact["emptyActions"]), 2)
        back = d["emptyExactSwitch"]
        self.assertIn("similar checked products", back["mode"])
        self.assertEqual(back["noMatch"], "none")  # the seller word matches in Kind of thing

    # ---- clearer savings ----------------------------------------------------

    def cards(self):
        return [c for c in re.split(r'(?=<section class="card)', self.page)
                if c.startswith('<section class="card bg-base-100')]

    def test_every_card_states_shelf_price_coupon_and_what_is_unknown(self):
        cards = self.cards()
        self.assertGreaterEqual(len(cards), 100)
        with_coupon = 0
        for c in cards:
            box = re.search(r'data-savings>(.*?)</ul></div>', c, re.S).group(1)
            text = re.sub(r"<[^>]+>", " ", box)
            text = re.sub(r"\s+", " ", text)
            label = re.search(r'data-price-label="([^"]*)"', c).group(1)
            self.assertTrue(re.sub(r"\s+([.])", r"\1", text).strip().startswith(
                label + " as printed on the page. "), text)
            self.assertIn("Confirm at checkout:", text)
            self.assertIn("tax", text.split("Confirm at checkout:")[1])
            if 'data-coupon="yes"' in c:
                with_coupon += 1
                code = re.search(r'data-coupon-code="([^"]*)"', c).group(1)
                self.assertIn("Coupon on this page: " + code, text)
                self.assertIn("the page says", text)
                self.assertIn("Conditions: only as that wording states them", text)
                self.assertIn("Not applied:", text)
                self.assertIn("does not include it", text)
                self.assertIn("whether the code works", text.split("Confirm at checkout:")[1])
            else:
                self.assertIn("No coupon printed on the page .", text)
                self.assertNotIn("Not applied", text)
                self.assertNotIn("whether the code works", text)
        self.assertEqual(with_coupon, 15)  # 9 + the 6 Untuckit pages that print NOIRON

    def test_a_seen_code_is_never_shown_as_a_lower_price(self):
        for c in self.cards():
            if 'data-coupon="yes"' not in c:
                continue
            label = re.search(r'data-price-label="([^"]*)"', c).group(1)
            price = re.search(r'data-price-text>([^<]*)<', c).group(1)
            self.assertEqual(price, label)
            line = re.search(r'<span data-shelf-line>([^<]*)</span>', c).group(1)
            self.assertEqual(line, label + " as printed on the page")
            self.assertNotRegex(line, r"(?i)code|coupon|off|save")
        for key, snap in self.driven.items():
            for line in snap["shelfLines"]:
                self.assertNotRegex(line, r"(?i)code|coupon|off\b|save", key)
            for text in snap["whys"]:
                if "own page printed" in text:
                    self.assertIn("never tried", text, key)

    def test_shelf_line_follows_the_chosen_bag_size(self):
        two = self.driven["coffee2lb"]
        self.assertEqual(two["shelfLines"], [
            "$38.00 for the 2 lb bag, as printed on the page",
            "$51.50 for the 2 lb bag, as printed on the page"])
        back = self.driven["coffee5lbBack"]
        self.assertEqual(back["shelfLines"], self.driven["load"]["shelfLines"])
        for line in self.driven["load"]["shelfLines"]:
            self.assertTrue(line.endswith("as printed on the page"))

    def test_each_card_gives_one_plain_sentence_on_why_it_is_shown(self):
        seen = 0
        for key, snap in self.driven.items():
            self.assertEqual(len(snap["whys"]), len(snap["visible"]), key)
            for why in snap["whys"]:
                seen += 1
                self.assertTrue(why.startswith("Shown because "), (key, why))
                self.assertTrue(why.endswith("."), (key, why))
                self.assertNotIn("·", why)
                self.assertNotIn("\n", why)
                self.assertNotIn("Why it is here", why)
        self.assertGreater(seen, 100)

    def test_guide_stays_quiet_no_urgency_or_scarcity(self):
        banned = ("hurry", "limited time", "ends soon", "last chance", "act now",
                  "don't miss", "countdown", "running out", "selling fast",
                  "only a few left", "expires", "deal of the day")
        for key, snap in self.driven.items():
            texts = [snap["guideText"], snap["emptyText"]] + snap["emptyActions"] + snap["whys"]
            for text in texts:
                low = text.lower()
                for word in banned:
                    self.assertNotIn(word, low, (key, word))
        low = self.page.lower()
        guide = low[low.index('id="guide"'):low.index('id="results"')]
        for word in ("countdown", "setinterval", "settimeout", "hurry", "limited time"):
            self.assertNotIn(word, guide)
        script = low[low.rindex("<script>"):]
        for word in ("setinterval", "settimeout", "date.now"):
            self.assertNotIn(word, script)

    def test_guide_is_labelled_and_keyboard_reachable(self):
        page = self.page
        self.assertIn('aria-label="Optional guide"', page)
        self.assertIn('role="status" aria-live="polite"', page)
        self.assertIn('<div id="no-match" class="alert mb-4" style="display:none" role="status">', page)
        self.assertIn("input:focus-visible", page)
        self.assertIn("min-height: 2.5rem", page)
        for c in self.driven["load"]["controls"]:
            self.assertTrue(c["label"] or c["options"])
        self.assertIn('name="viewport"', page)
        self.assertIn("minmax(15rem, 1fr)", page)  # one column at phone width

    # ---- freshness and what to confirm ----------------------------------------

    def test_each_card_says_how_old_its_stored_check_is_in_plain_days(self):
        # the page script runs with "today" pinned to 2026-10-05
        for c in self.cards():
            iso = re.search(r'data-observed="([^"]*)"', c).group(1)
            self.assertIn("Checked " + iso[:10] + "</p>", c)  # no-script fallback: date only
        seen = set()
        for key, snap in self.driven.items():
            self.assertEqual(len(snap["ages"]), len(snap["visible"]), key)
            for age in snap["ages"]:
                seen.add(age)
                self.assertRegex(age, r"^Checked (today|\d+ days?) ?(ago)?,? ?\d{4}-\d\d-\d\d$", age)
                low = age.lower()
                for word in ("fresh", "stale", "old", "expired", "recent", "outdated", "valid"):
                    self.assertNotIn(word, low, age)
        self.assertIn("Checked 3 days ago, 2026-10-02", seen)
        self.assertIn("Checked 2 days ago, 2026-10-03", seen)

    def test_age_comes_only_from_the_stored_time(self):
        for c in self.cards():
            iso = re.search(r'data-observed="([^"]*)"', c).group(1)
            self.assertEqual(iso, re.search(r"Checked: [^<]*\u00b7 (\d{4}[^<]*)</p>", c).group(1))
        script = self.page[self.page.rindex("<script>"):]
        self.assertEqual(script.count("new Date()"), 1)  # read once, for the age line only

    def test_confirm_at_checkout_lists_only_what_the_stored_evidence_leaves_unknown(self):
        saw_ship_known = saw_ship_unknown = 0
        for c in self.cards():
            box = re.search(r'data-savings>(.*?)</ul></div>', c, re.S).group(1)
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", box))
            line = re.search(r"Confirm at checkout: (.*?)\.(?: |$)", text).group(1)
            self.assertEqual(text.count("Confirm at checkout:"), 1)
            terms = json.loads(html_lib.unescape(re.search(r'data-terms="([^"]*)"', c).group(1)))
            self.assertIn("tax", line)
            if terms["sh"]:
                saw_ship_known += 1
                self.assertNotIn("shipping", line)
            else:
                saw_ship_unknown += 1
                self.assertIn("shipping cost (the page did not state it)", line)
            if 'data-coupon="yes"' in c:
                self.assertIn("whether the code works and what it would take off", line)
            else:
                self.assertNotIn("code", line)
        self.assertGreater(saw_ship_known, 0)
        self.assertGreater(saw_ship_unknown, 0)

    def test_savings_box_opens_with_shelf_price_and_plain_saving_status(self):
        for c in self.cards():
            label = re.search(r'data-price-label="([^"]*)"', c).group(1)
            lead = re.search(r"data-saving-lead>(.*?)</p>", c, re.S).group(1)
            lead = re.sub(r"<[^>]+>", "", lead)
            status = "Coupon printed, not applied" if 'data-coupon="yes"' in c \
                else "No coupon printed on the page"
            self.assertEqual(lead, label + " as printed on the page. " + status + ".")
            self.assertLess(c.index("data-saving-lead"), c.index("Confirm at checkout:"))
        for key, snap in self.driven.items():
            for lead, shelf, card in zip(snap["leads"], snap["shelfLines"], snap["visible"]):
                status = "Coupon printed, not applied" if card["coupon"] == "yes" \
                    else "No coupon printed on the page"
                if card["windowState"] == "ended":
                    status = "The page's printed window has ended"
                self.assertEqual(lead, shelf + ". " + status + ".", key)

    def test_vague_recheck_wording_is_gone(self):
        self.assertNotIn("recheck at checkout", self.page)
        self.assertNotIn("Not known:", self.page)


class PrintedWindowTest(unittest.TestCase):
    """A coupon page's own printed date window against the browser's date."""

    PAGE = os.path.join(ROOT, "demo", "index.html")
    UNTUCKIT = "NOIRON"
    CASES = {  # pinned browser time -> (state, status text)
        "2026-09-30T15:00:00Z": ("before", "Today (2026-09-30) is before the page's printed window."),
        "2026-10-01T15:00:00Z": ("inside", "Today (2026-10-01) is inside the page's printed window."),
        "2026-10-04T15:00:00Z": ("inside", "Today (2026-10-04) is inside the page's printed window."),
        "2026-10-05T15:00:00Z": ("ended", "The page's printed window has ended (today is 2026-10-05)."),
    }

    @classmethod
    def setUpClass(cls):
        cls.page = read("demo", "index.html")
        cls.runs = {now: drive(cls.PAGE, now=now, only_load=True)["load"]["windows"]
                    for now in cls.CASES}

    def untuckit(self, now):
        return [w for w in self.runs[now] if w["code"] == self.UNTUCKIT]

    def test_window_is_stated_before_inside_and_after_the_printed_dates(self):
        for now, (state, text) in self.CASES.items():
            rows = self.untuckit(now)
            self.assertEqual(len(rows), 6, now)
            for w in rows:
                self.assertEqual(w["state"], state, now)
                self.assertTrue(w["status"].startswith(text), (now, w["status"]))
                self.assertEqual(w["windowStart"], "2026-10-01")
                # never a lower price, in any state
                self.assertEqual(w["price"], w["priceLabel"])

    def test_an_ended_window_is_information_not_an_offer(self):
        for w in self.untuckit("2026-10-05T15:00:00Z"):
            self.assertEqual(w["lead"], w["priceLabel"] + " as printed on the page. "
                             "The page's printed window has ended.")
            self.assertTrue(w["label"].startswith("The page's printed window has ended"))
            self.assertIn("information only", w["label"])
            self.assertIn("not as an available offer", w["status"])
            self.assertIn("whether any offer is still available", w["confirm"])
            self.assertNotIn("Coupon printed, not applied", w["lead"])
        for now in ("2026-09-30T15:00:00Z", "2026-10-04T15:00:00Z"):
            for w in self.untuckit(now):
                self.assertNotIn("has ended", w["lead"])

    def test_before_and_inside_still_say_seen_never_tried(self):
        for now in ("2026-09-30T15:00:00Z", "2026-10-04T15:00:00Z"):
            for w in self.untuckit(now):
                self.assertEqual(w["lead"], w["priceLabel"] + " as printed on the page. "
                                 "Coupon printed, not applied.")
                self.assertEqual(w["label"], "Coupon on this page:")
                self.assertEqual(w["confirm"], "whether the code works and what it would take off")
        self.assertIn("The code is still never tried", self.untuckit("2026-10-04T15:00:00Z")[0]["status"])

    def test_coupons_with_no_printed_window_say_so_on_any_date(self):
        for now, rows in self.runs.items():
            others = [w for w in rows if w["code"] != self.UNTUCKIT]
            self.assertEqual(len(others), 9, now)
            for w in others:
                self.assertEqual(w["state"], "none", now)
                self.assertTrue(w["status"].startswith("the coupon text states no date window"), w["status"])
                self.assertIsNone(w["windowStart"])
                self.assertNotIn("has ended", w["lead"])
                self.assertEqual(w["lead"], w["priceLabel"] + " as printed on the page. "
                                 "Coupon printed, not applied.")

    def test_printed_conditions_are_quoted_word_for_word_from_the_stored_text(self):
        stored = json.loads(read("demo", "evidence", "untuckit-normand.json"))["coupon_snippets"][0]
        quote = "Cannot be combined with any offers or promotions."
        self.assertIn(quote, stored)
        for w in self.untuckit("2026-10-05T15:00:00Z"):
            self.assertEqual(len(w["conditions"]), 1)
            self.assertIn("\u201c" + quote + "\u201d", w["conditions"][0])
            for sentence in re.findall("\u201c([^\u201d]*)\u201d", w["conditions"][0]):
                self.assertIn(sentence, stored)
        # the window quote is a verbatim piece of the stored page text too
        for m in re.finditer(r"Window the page prints:</span> \u201c([^\u201d]*)\u201d",
                             html_lib.unescape(self.page)):
            self.assertEqual(m.group(1), "10/1/2026 at 12:00 AM ET through 10/4/2026 at 11:59 PM ET")
            self.assertIn(m.group(1), stored)

    def test_the_page_reads_the_date_once_and_adds_no_countdown_or_urgency(self):
        script = self.page[self.page.rindex("<script>"):]
        self.assertEqual(script.count("new Date()"), 1)
        for word in ("hurry", "last chance", "ends soon", "countdown", "only today"):
            self.assertNotIn(word, self.page.lower())


class PrintedWindowParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, os.path.join(ROOT, "demo"))
        sys.path.insert(0, ROOT)
        import build
        cls.window = staticmethod(build.printed_window)
        cls.conditions = staticmethod(build.printed_conditions)

    def test_two_explicit_dates_make_a_window(self):
        w = self.window("Offer valid 10/1/2026 at 12:00 AM ET through 10/4/2026 at 11:59 PM ET, online.")
        self.assertEqual((w["start"], w["end"]), ("2026-10-01", "2026-10-04"))
        self.assertEqual(w["quote"], "10/1/2026 at 12:00 AM ET through 10/4/2026 at 11:59 PM ET")
        w = self.window("Use code X from Oct 1, 2026 to October 4, 2026.")
        self.assertEqual((w["start"], w["end"]), ("2026-10-01", "2026-10-04"))

    def test_ambiguous_or_absent_dates_make_no_window(self):
        for text in (
            "Use code X at checkout.",
            "Ends 10/4/2026.",                       # one date: start or end unclear
            "Valid 10/1 to 10/4.",                   # no year
            "Valid 10/1/26 through 10/4/26.",        # two-digit year
            "Valid 10/4/2026 through 10/1/2026.",    # out of order
            "Valid 13/45/2026 through 14/45/2026.",  # impossible dates
            "Valid 10/1/2026, 10/4/2026 and 10/9/2026.",  # three dates
            "Valid through the end of the month.",
            "", None,
        ):
            self.assertIsNone(self.window(text), text)

    def test_conditions_are_whole_sentences_quoted_as_printed(self):
        text = ("Offer valid 10/1/2026 through 10/4/2026. Enter code X. Cannot be combined "
                "with any offers or promotions. Offer has no cash value and is not valid on gift c")
        self.assertEqual(self.conditions(text),
                         ["Cannot be combined with any offers or promotions."])  # truncated tail is not quoted
        self.assertEqual(self.conditions("Use code X."), [])


if __name__ == "__main__":
    unittest.main()
