"""Quiet public page: interactive guide, two-search explanation, coffee note.

Checks the generated demo/index.html and its GitHub Pages copy
docs/index.html. Offline; no invented products, prices, or coupons.

The coffee note and card attributes are the generated page contract.
Search, guide, and exact-product behavior are executed in the page script.
"""

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
Object.defineProperty(El.prototype, "innerText", { get() { return this.textContent; } });
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

function boot() {
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
  const radios = [];
  walk(document._root, el => {
    if (el.tag === "input" && el.attrs["data-guide-key"]) {
      radios.push({
        key: el.attrs["data-guide-key"], value: el.attrs.value, checked: !!el.checked,
        label: collect(el.parent).trim(),
      });
    }
  });
  const hiddenItems = document.getElementById("hidden-list").children.map(li => collect(li).trim());
  return {
    status: collect(document.getElementById("guide-status")).trim(),
    radios: radios,
    hiddenItems: hiddenItems,
    hiddenShown: document.getElementById("hidden-by").style.display !== "none",
    whys: cards.filter(c => c.style.display !== "none").map(c => collect(c.querySelectorAll("[data-why]")[0]).trim()),
    visible: cards.filter(c => c.style.display !== "none").map(card),
    all: cards.map(card),
    mode: collect(document.getElementById("mode-text")).trim(),
    resultsInGuide: contained(results, document.getElementById("guide")),
    tables: tables,
    buttons: buttons,
    exactNote: document.getElementById("exact-note") !== null,
    blockedClaim: visibleText(document._root).indexOf("Target, Walmart, Kroger") !== -1,
    noMatch: document.getElementById("no-match").style.display,
  };
}
function card(c) {
  return {
    name: c.getAttribute("data-name"),
    kind: c.getAttribute("data-kind"),
    form: c.getAttribute("data-form"),
    coupon: c.getAttribute("data-coupon"),
    quality: c.getAttribute("data-quality"),
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
    if (el.tag === "input" && el.attrs["data-guide-key"] === key && el.attrs.value === value) found = el;
  });
  if (!found) throw new Error("missing answer " + key + "=" + value);
  found.checked = true;
  found.dispatch("change");
}
function clickId(document, id) {
  const el = document.getElementById(id);
  if (!el) throw new Error("missing #" + id);
  el.dispatch("click");
}

const out = {};
function fresh(fn) { const document = boot(); fn(document); return snap(document); }
out.load = fresh(() => {});
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
  answer(d, "form", "whole-bean"); answer(d, "coupon", "yes"); answer(d, "prefer", "specialty");
});
out.combinedChanged = fresh(d => {
  setQuery(d, "");
  answer(d, "form", "whole-bean"); answer(d, "coupon", "yes"); answer(d, "prefer", "specialty");
  answer(d, "coupon", "all");
});
out.resetAfterCombined = fresh(d => {
  setQuery(d, "");
  answer(d, "form", "whole-bean"); answer(d, "coupon", "yes"); answer(d, "prefer", "specialty");
  clickId(d, "guide-reset");
});
out.noSearchBoth = fresh(d => { setQuery(d, ""); });
out.exactQualita = fresh(d => { clickId(d, "mode-exact"); setQuery(d, "qualita rossa"); });
out.exactAccent = fresh(d => { clickId(d, "mode-exact"); setQuery(d, "qualit\u00e0 rossa"); });
out.exactSuper = fresh(d => { clickId(d, "mode-exact"); setQuery(d, "super crema"); });
out.exactMidnight = fresh(d => { clickId(d, "mode-exact"); setQuery(d, "midnight axes"); });
out.exactAirpodsAnyCoffee = fresh(d => {
  clickId(d, "mode-exact"); setQuery(d, "airpods pro"); answer(d, "form", "any-coffee");
});
out.exactAirpodsThenReset = fresh(d => {
  clickId(d, "mode-exact"); setQuery(d, "airpods pro"); answer(d, "form", "any-coffee");
  clickId(d, "guide-reset");
});
out.exactCouponOnly = fresh(d => {
  clickId(d, "mode-exact"); setQuery(d, "midnight axes"); answer(d, "coupon", "yes");
});
{
  const document = boot();
  clickId(document, "mode-exact");
  setQuery(document, "airpods pro");
  out.exactAirpods = snap(document);
  clickId(document, "mode-open");
  out.backToKind = snap(document);
}
process.stdout.write(JSON.stringify(out));
"""


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def drive(page_path):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(DRIVER)
        script = handle.name
    try:
        proc = subprocess.run(
            ["node", script, page_path],
            check=False, capture_output=True, text=True,
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

    def test_pages_copy_matches_demo(self):
        self.assertEqual(self.page, read("docs", "index.html"))

    def test_coffee_note_matches_evidence(self):
        m = re.search(r"Coffee note: ([^<]*)", self.page)
        self.assertIsNotNone(m)
        note = m.group(1)
        self.assertIn("Dolcevita Classico, Qualità Rossa and Super Crema "
                      "showed the code CAFE20", note)
        for seller in ("Honest Coffee Roasters", "The Well Coffee Roasters",
                       "Counter Culture Coffee"):
            self.assertIn(seller, note)
        self.assertIn("shelf price", note)

    def test_coupon_cards_match_note(self):
        cards = re.split(r'(?=<section class="card)', self.page)
        with_code = {re.search(r'data-name="([^"]*)"', c).group(1)
                     for c in cards if 'data-coupon="yes"' in c
                     and "CAFE20" in c}
        self.assertEqual(len(with_code), 3)
        for c in cards:
            if "Midnight Axes" in c or "Watershed" in c or "Big Trouble" in c:
                self.assertIn('data-coupon="no"', c)

    def test_card_names_are_unique(self):
        names_found = [card["name"] for card in self.driven["load"]["all"]]
        self.assertTrue(names_found)
        self.assertEqual(len(names_found), len(set(names_found)))

    def test_guide_shows_every_question_labelled_and_list_stays(self):
        load = self.driven["load"]
        self.assertFalse(load["resultsInGuide"])
        self.assertEqual(
            [(r["key"], r["value"], r["checked"]) for r in load["radios"]],
            [("prefer", "price", True), ("prefer", "specialty", False),
             ("form", "", True), ("form", "any-coffee", False),
             ("form", "whole-bean", False),
             ("coupon", "all", True), ("coupon", "yes", False)])
        self.assertEqual(
            [r["label"] for r in load["radios"]],
            ["Lowest price first", "Specialty-roaster quality first",
             "Anything", "Any coffee", "Whole bean",
             "Show all", "Only with a printed coupon"])
        self.assertEqual(load["buttons"], [
            "Kind of thing", "Exact product", "Search",
            "Reset \u2014 show everything"])
        self.assertGreater(len(load["visible"]), 0)
        self.assertTrue(all(card["kind"] == "Coffee" for card in load["visible"]))
        self.assertTrue(any(card["coupon"] == "yes" for card in load["visible"]))
        self.assertTrue(any(card["coupon"] == "no" for card in load["visible"]))
        self.assertEqual(load["tables"], 0)
        self.assertIn("similar checked products", load["mode"])
        self.assertIn("only when that product's own page printed it", load["mode"])
        self.assertIn("the price shown is the shelf price", load["mode"])
        self.assertEqual(load["status"], "No answers set. %d shown, 0 hidden by your answers."
                         % len(load["visible"]))
        self.assertFalse(load["hiddenShown"])

    def test_form_answers_narrow_and_can_be_changed_back(self):
        any_coffee = self.driven["anyCoffee"]
        coffee = [card for card in any_coffee["all"] if card["kind"] == "Coffee"]
        self.assertEqual(
            sorted(names(any_coffee)), sorted(card["name"] for card in coffee))
        self.assertNotIn("AirPods Pro 3", names(any_coffee))
        self.assertEqual(any_coffee["noMatch"], "none")

        whole = self.driven["wholeBean"]
        beans = [card for card in whole["all"] if card["form"] == "whole-bean"]
        self.assertEqual(
            sorted(names(whole)), sorted(card["name"] for card in beans))
        self.assertNotIn("AirPods Pro 3", names(whole))
        self.assertTrue(whole["hiddenShown"])
        self.assertTrue(any("AirPods Pro 3" in h and "Whole bean" in h
                            for h in whole["hiddenItems"]))

        back = self.driven["wholeBeanThenAnything"]
        self.assertEqual(len(back["visible"]), len(back["all"]))
        self.assertIn("AirPods Pro 3", names(back))
        self.assertFalse(back["hiddenShown"])

    def test_every_shown_card_says_why_and_only_from_page_facts(self):
        for key in ("load", "wholeBean", "couponOnly", "combined", "specialty"):
            snap = self.driven[key]
            self.assertEqual(len(snap["whys"]), len(snap["visible"]), key)
            for why in snap["whys"]:
                self.assertTrue(why.startswith("Why it is here: "), key)
        by_name = dict(zip(names(self.driven["couponOnly"]),
                           self.driven["couponOnly"]["whys"]))
        self.assertIn("its own page printed CAFE20", by_name[
            "Qualit\u00e0 Rossa Whole Bean, 2.2 lb bag"])
        self.assertIn("never tried", by_name["Qualit\u00e0 Rossa Whole Bean, 2.2 lb bag"])
        self.assertIn("the price is still the shelf price",
                      by_name["Qualit\u00e0 Rossa Whole Bean, 2.2 lb bag"])
        for why in self.driven["couponOnly"]["whys"]:
            self.assertNotIn("save", why.lower())
            self.assertNotIn("off", why.lower().split())
        for card, why in zip(self.driven["specialty"]["visible"],
                             self.driven["specialty"]["whys"]):
            if card["quality"] == "independent-roastery":
                self.assertIn("listed first", why)
            else:
                self.assertIn("listed after", why)
        cheapest = self.driven["load"]["whys"][0]
        self.assertIn("lowest of", cheapest)
        self.assertNotIn("Target, Walmart, Kroger", cheapest)

    def test_answers_combine_react_live_and_reset_restores_everything(self):
        combined = self.driven["combined"]
        for card in combined["visible"]:
            self.assertEqual(card["form"], "whole-bean")
            self.assertEqual(card["coupon"], "yes")
        self.assertTrue(combined["visible"])
        self.assertTrue(combined["hiddenShown"])
        self.assertIn("Your answers:", combined["status"])
        self.assertIn("Whole bean", combined["status"])
        self.assertIn("Only with a printed coupon", combined["status"])
        self.assertIn("Specialty-roaster quality first", combined["status"])

        changed = self.driven["combinedChanged"]
        self.assertGreater(len(changed["visible"]), len(combined["visible"]))
        self.assertNotIn("Only with a printed coupon", changed["status"])
        self.assertTrue(all(card["form"] == "whole-bean" for card in changed["visible"]))

        reset = self.driven["resetAfterCombined"]
        self.assertEqual(len(reset["visible"]), len(reset["all"]))
        self.assertEqual(
            [(r["key"], r["value"]) for r in reset["radios"] if r["checked"]],
            [("prefer", "price"), ("form", ""), ("coupon", "all")])
        self.assertFalse(reset["hiddenShown"])
        self.assertEqual(reset["hiddenItems"], [])
        self.assertTrue(reset["status"].startswith("No answers set."))

    def test_guide_never_shows_a_coupon_the_page_did_not_print(self):
        coupons = self.driven["couponOnly"]
        self.assertTrue(coupons["visible"])
        self.assertTrue(all(card["coupon"] == "yes" for card in coupons["visible"]))
        self.assertNotIn("AirPods Pro 3", names(coupons))
        self.assertNotIn("Midnight Axes", " ".join(names(coupons)))
        self.assertTrue(any("Midnight Axes" in h and "no coupon code" in h
                            for h in coupons["hiddenItems"]))
        for key, snap in self.driven.items():
            self.assertFalse(snap["blockedClaim"], key)
            for why in snap["whys"]:
                if "CAFE20" in why or "EXTRA" in why:
                    self.assertIn("printed", why, key)
        exact = self.driven["exactCouponOnly"]
        self.assertEqual(exact["visible"], [])
        self.assertEqual(exact["noMatch"], "")

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
        self.assertFalse(midnight["blockedClaim"])
        self.assertFalse(midnight["exactNote"])
        self.assertEqual(names(self.driven["exactAirpods"]), ["AirPods Pro 3"])
        self.assertEqual(self.driven["exactAirpodsAnyCoffee"]["visible"], [])
        self.assertEqual(self.driven["exactAirpodsAnyCoffee"]["noMatch"], "")
        self.assertTrue(any("AirPods Pro 3" in h
                            for h in self.driven["exactAirpodsAnyCoffee"]["hiddenItems"]))
        self.assertEqual(names(self.driven["exactAirpodsThenReset"]), ["AirPods Pro 3"])

    def test_kind_search_still_sorts_specialty_and_price(self):
        specialty = self.driven["specialty"]
        self.assertIn("AirPods Pro 3", names(specialty))
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
        prices = [card["name"] for card in price_again["visible"]]
        self.assertEqual(prices, names(self.driven["noSearchBoth"]))
        kind = self.driven["backToKind"]
        self.assertIn("similar checked products", kind["mode"])
        self.assertTrue(all(card["kind"] == "Coffee" for card in kind["visible"]))
        self.assertGreater(len(kind["visible"]), 1)

    def test_guide_text_makes_no_savings_or_retailer_claims(self):
        guide = re.search(r'<section id="guide".*?</section>', self.page, re.S).group(0)
        text = re.sub(r"<[^>]+>", " ", guide).lower()
        for banned in ("save", "savings", "cheaper", "discount", "target",
                       "walmart", "kroger", "best deal"):
            self.assertNotIn(banned, text)
        self.assertIn("never a lower price", text)
        self.assertIn("shelf price", text)


if __name__ == "__main__":
    unittest.main()
