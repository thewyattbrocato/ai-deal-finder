// Runs the generated page's own scripts against its markup (a small DOM model,
// no browser) and prints what a reader would see after each scripted action.
// Not a source search: tests/test_page.py asserts on this output.
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
El.prototype.removeAttribute = function (name) { delete this.attrs[name]; };
El.prototype.addEventListener = function (type, fn) {
  (this.listeners[type] = this.listeners[type] || []).push(fn);
};
let ACTIVE = null;
El.prototype.focus = function () { ACTIVE = this; };
// Clicks and keys bubble up through the parents to the document, as in a browser.
let DOC = null;
El.prototype.dispatch = function (type, ev) {
  const e = Object.assign({ type: type, target: this, preventDefault() { e.prevented = true; } }, ev || {});
  for (let n = this; n; n = n.parent) {
    for (const fn of n.listeners[type] || []) fn.call(n, e);
    if (type !== "click" && type !== "keydown") break;
  }
  if ((type === "click" || type === "keydown") && DOC) DOC.dispatch(type, e);
  return e;
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
    if (/display:\s*none/.test(el.attrs.style || "")) el.style.display = "none";
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

function visibleText(el) {
  if (!el || el.tag === "script" || el.tag === "style") return "";
  if (el.style && el.style.display === "none") return "";
  if (el.tag === "#text") return el._text;
  let s = el.tag === "#document" ? "" : (el._text || "");
  for (const c of el.children) s += visibleText(c);
  return s;
}
function shownCard(c) { return c.style.display !== "none"; }

// The page reads "today" once to say how old each stored check is; pin it.
const NOW = process.env.PAGE_NOW ? Date.parse(process.env.PAGE_NOW) : Date.UTC(2026, 9, 5, 15, 0, 0);
class FixedDate extends Date {
  constructor(...a) { if (a.length) super(...a); else super(NOW); }
}

// Boots the page as a browser would: scripts run in order against the parsed markup.
function boot(opts) {
  opts = opts || {};
  ACTIVE = null;
  const root = parse(html);
  const listeners = {};
  const document = {
    getElementById(id) {
      let found = null;
      walk(root, el => { if (!found && el.attrs && el.attrs.id === id) found = el; });
      return found;
    },
    createElement(tag) { return new El(tag); },
    createTextNode(s) { const t = new El("#text"); t._text = String(s); return t; },
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    dispatch(type, ev) {
      const e = Object.assign({ type: type, target: root, preventDefault() {} }, ev || {});
      for (const fn of listeners[type] || []) fn(e);
    },
    get activeElement() { return ACTIVE; },
    querySelectorAll(sel) { return root.querySelectorAll(sel); },
    _root: root,
  };
  DOC = document;
  const winListeners = {};
  const location = { hash: opts.hash || "", pathname: "/", search: "" };
  const log = [];
  const history = {
    pushState(_s, _t, url) { log.push(["push", url]); location.hash = url.indexOf("#") >= 0 ? url.slice(url.indexOf("#")) : ""; },
    replaceState(_s, _t, url) { log.push(["replace", url]); location.hash = url.indexOf("#") >= 0 ? url.slice(url.indexOf("#")) : ""; },
  };
  const fine = opts.pointer !== "coarse";
  const matchMedia = q => ({ matches: /min-width/.test(q) ? opts.wide !== false : (/hover/.test(q) ? fine : false) });
  const window = {
    addEventListener(type, fn) { (winListeners[type] = winListeners[type] || []).push(fn); },
    matchMedia: matchMedia,
    pageYOffset: 0,
  };
  const context = vm.createContext({
    document: document, window: window, location: location, history: history, matchMedia: matchMedia,
    console: console, Date: FixedDate, Intl: Intl,
  });
  const scripts = [];
  walk(root, el => {
    if (el.tag === "script" && !el.attrs.src && el.attrs.type !== "application/json") scripts.push(el.textContent);
  });
  for (const code of scripts) vm.runInContext(code, context);
  return {
    full: !!opts.full, document, location, history, log,
    scrollTo(y) { window.pageYOffset = y; for (const fn of winListeners.scroll || []) fn({}); },
    back(hash) { location.hash = hash; for (const fn of winListeners.popstate || []) fn({}); },
  };
}

function $(page, id) { return page.document.getElementById(id); }
function type(page, value) {
  const q = $(page, "q");
  q.value = value;
  q.dispatch("input");
}
function key(page, k) { return $(page, "q").dispatch("keydown", { key: k }); }
function buttons(root) {
  const out = [];
  walk(root, el => { if (el.tag === "button") out.push(el); });
  return out;
}
function byAttr(page, attr, value) {
  let found = null;
  walk(page.document._root, el => {
    if (!found && el.attrs && el.attrs[attr] === value && el.style.display !== "none") found = el;
  });
  return found;
}
function clickChip(page, k) {
  const el = byAttr(page, "data-chip", k);
  if (!el) throw new Error("missing chip " + k);
  el.dispatch("click");
}
function clickText(page, root, prefix) {
  const el = buttons(root).filter(b => collect(b).trim().indexOf(prefix) === 0)[0];
  if (!el) throw new Error("missing button " + prefix);
  el.dispatch("click");
}
function clickId(page, id) { $(page, id).dispatch("click"); }

function firstOf(c, attr) { return c.querySelectorAll("[" + attr + "]")[0]; }
function textOf(c, attr) { const e = c.querySelectorAll("[" + attr + "]")[0]; return e ? collect(e).trim() : null; }

function cardInfo(c) {
  return {
    i: parseInt(c.attrs["data-i"], 10),
    name: c.attrs["data-name"],
    kind: c.attrs["data-kind"],
    coupon: c.attrs["data-coupon"],
    code: c.attrs["data-coupon-code"],
    windowState: c.attrs["data-window-state"] || null,
    price: textOf(c, "data-price-text"),
    priceLabel: c.attrs["data-price-label"],
    heading: textOf(c, "data-heading"),
    age: textOf(c, "data-age"),
    shelf: textOf(c, "data-shelf-line"),
    lead: textOf(c, "data-saving-lead"),
    facts: textOf(c, "data-facts"),
    couponLine: textOf(c, "data-coupon-line"),
    sizeLine: firstOf(c, "data-size-line").style.display === "none" ? "" : textOf(c, "data-size-line"),
    readLine: textOf(c, "data-page-read"),
    link: collect(c.querySelectorAll("[href]")[0]).trim(),
    href: c.querySelectorAll("[href]")[0].attrs.href,
    marks: (function () { const out = []; walk(firstOf(c, "data-heading"), e => { if (e.tag === "mark") out.push(collect(e)); }); return out; })(),
  };
}

function snap(page) {
  const d = page.document, results = $(page, "results");
  const divider = $(page, "unk-head");
  const list = [];
  let dividerAt = -1;
  for (const c of results.children) {
    if (c === divider) { dividerAt = divider.style.display === "none" ? -1 : list.length; continue; }
    if (c.attrs["data-i"] != null && shownCard(c)) list.push(c);
  }
  const main = dividerAt < 0 ? list : list.slice(0, dividerAt);
  const unk = dividerAt < 0 ? [] : list.slice(dividerAt);
  const chips = [];
  walk($(page, "bar"), el => {
    if (el.tag === "button" && el.attrs["data-chip"]) {
      chips.push({ key: el.attrs["data-chip"], label: el.attrs["aria-label"] || collect(el).trim(),
        text: collect(el).trim(), pressed: el.attrs["aria-pressed"] === "true", visible: true });
    }
  });
  const sg = [];
  walk($(page, "sugg"), el => {
    if (el.attrs.role === "option") sg.push({ text: collect(el).trim(), selected: el.attrs["aria-selected"] === "true", id: el.attrs.id });
  });
  const q = $(page, "q");
  return {
    q: q.value,
    hash: page.location.hash,
    history: page.log.slice(),
    startShown: $(page, "start").style.display !== "none",
    areaShown: $(page, "resultsArea").style.display !== "none",
    startText: visibleText($(page, "start")).replace(/\s+/g, " ").trim(),
    pageText: visibleText(d._root).replace(/\s+/g, " ").trim(),
    count: collect($(page, "count")).trim(),
    notes: $(page, "notes").children.map(n => collect(n).trim()),
    active: $(page, "active").children.length ? buttons($(page, "active")).filter(b => b.attrs["data-remove"]).map(b => ({ key: b.attrs["data-remove"], label: b.attrs["aria-label"] })) : [],
    clearAll: buttons($(page, "active")).some(b => b.attrs["data-clearall"]),
    refineShown: $(page, "refine").style.display !== "none",
    refineOpen: Object.prototype.hasOwnProperty.call($(page, "refine").attrs, "open"),
    rowLabels: $(page, "bar").children.filter(e => e.tag === "p").map(e => collect(e).trim()),
    chips: chips,
    sizeButton: (function () { const b = byAttr(page, "data-chip", "size"); return b ? { text: collect(b).trim(), expanded: b.attrs["aria-expanded"] } : null; })(),
    unk: $(page, "unk").style.display === "none" ? "" : collect($(page, "unk")).replace(/\s+/g, " ").trim(),
    unkOpen: dividerAt >= 0,
    empty: $(page, "empty").style.display === "none" ? null : {
      text: visibleText($(page, "empty")).replace(/\s+/g, " ").trim(),
      buttons: buttons($(page, "empty")).map(b => collect(b).trim()),
      near: $(page, "empty").querySelectorAll("[data-near]").map(n => ({ name: n.attrs["data-near"], text: collect(n).replace(/\s+/g, " ").trim(),
        href: n.querySelectorAll("[href]")[0].attrs.href })),
    },
    coffeeNote: $(page, "coffee-note").style.display,
    sortShown: $(page, "sortbox").style.display !== "none",
    showMore: $(page, "show-more").style.display === "none" ? null : collect($(page, "show-more")).trim(),
    sugg: { shown: $(page, "sugg").style.display !== "none", items: sg, expanded: q.attrs["aria-expanded"], active: q.attrs["aria-activedescendant"] || "" },
    focus: ACTIVE ? { id: ACTIVE.attrs.id || null, chip: ACTIVE.attrs["data-chip"] || null, isQ: ACTIVE === q } : null,
    main: main.map(cardInfo),
    unkCards: unk.map(cardInfo),
    all: !page.full ? undefined : $(page, "results").querySelectorAll("[data-i]").map(cardInfo),
    windows: !page.full ? undefined : $(page, "results").querySelectorAll("[data-i]").filter(c => c.attrs["data-coupon"] === "yes").map(c => ({
      name: c.attrs["data-name"],
      code: c.attrs["data-coupon-code"],
      state: c.attrs["data-window-state"],
      status: textOf(c, "data-window-status"),
      lead: textOf(c, "data-saving-lead"),
      label: textOf(c, "data-coupon-label"),
      confirm: textOf(c, "data-confirm-code"),
      price: textOf(c, "data-price-text"),
      priceLabel: c.attrs["data-price-label"],
      couponLine: textOf(c, "data-coupon-line"),
      conditions: c.querySelectorAll("[data-conditions-row]").map(r => collect(r).trim()),
      windowStart: c.querySelectorAll("[data-window-row]")[0].attrs["data-window-start"] || null,
    })),
  };
}

const out = {};
const only = process.env.ONLY_LOAD;
const OPEN = { hash: process.env.PAGE_HASH || "" };
function fresh(fn, opts) { const p = boot(Object.assign({}, OPEN, opts || {})); if (fn) fn(p); return snap(p); }

out.load = fresh(null, { full: true });
if (only) { process.stdout.write(JSON.stringify(out), () => process.exit(0)); return; }

out.loadPhone = fresh(null, { pointer: "coarse", wide: false });
out.phoneCoffee = fresh(p => type(p, "coffee"), { pointer: "coarse", wide: false });
out.loadWithHash = fresh(null, { hash: "#q=cofee&ship=min" });

// typing: results follow the characters, with no Search button
out.typed = {};
for (const w of ["c", "co", "cof", "coff", "coffe", "coffee", "cofee", "bean", "beanie", "beani", "espresso", "espreso",
  "old nav", "old navy", "old navy sweatpants", "sneaker", "sneakers", "shoes", "clothing", "tea", "airpods", "dog",
  "zzyzx", "espresso machine", "qualità rossa", "super crema", "nike", "bambino", "midnight"]) {
  out.typed[w] = fresh(p => type(p, w));
}
out.sweatpantsLetters = [];
{
  const p = boot();
  for (const ch of "sweatpants") { type(p, $(p, "q").value + ch); out.sweatpantsLetters.push(snap(p)); }
}

// chips and their counts: click each chip offered, compare its count with the list that results
// How many products the page says it lists (the count line), whatever part of them is on screen.
function listedTotal(s) {
  const m = /^(\d+) checked products?/.exec(s.count);
  return m ? parseInt(m[1], 10) : 0;
}
function chipsFor(query, extra) {
  const p = boot();
  if (query != null) type(p, query);
  if (extra) extra(p);
  const s = snap(p);
  const rows = [];
  for (const c of s.chips) {
    const said = /, (\d+) results?$/.exec(c.label);
    if (c.key === "size") continue;
    if (c.pressed) {  // already on: its count is the list on screen now
      rows.push({ key: c.key, said: said ? parseInt(said[1], 10) : null, listed: listedTotal(s), pressed: true });
      continue;
    }
    const q = boot();
    if (query != null) type(q, query);
    if (extra) extra(q);
    if (c.key.indexOf("size:") === 0) clickChip(q, "size");
    clickChip(q, c.key);
    const t = snap(q);
    rows.push({ key: c.key, said: said ? parseInt(said[1], 10) : null, listed: listedTotal(t), pressed: false });
  }
  return rows;
}
out.chipCounts = {};
for (const w of ["coffee", "shoes", "clothing", "kitchen", "dog", "nike", "tea", "bag", "old navy", "lavazza", "sneaker", "shirt"]) {
  out.chipCounts[w] = chipsFor(w);
}
out.chipCounts.browseAll = chipsFor(null, p => clickId(p, "browseall"));
out.chipCounts.coffeeSub = chipsFor("coffee", p => clickChip(p, "sub:true"));
out.chipCounts.shoesMin = chipsFor("shoes", p => clickChip(p, "ship:min"));
out.chipCounts.clothingCoupon = chipsFor("clothing", p => clickChip(p, "coupon:true"));

// chips as a shopper uses them
out.coffee = fresh(p => type(p, "coffee"));
out.coffeeSub = fresh(p => { type(p, "coffee"); clickChip(p, "sub:true"); });
out.coffeeSubShown = fresh(p => { type(p, "coffee"); clickChip(p, "sub:true"); clickText(p, $(p, "unk"), "Show them"); });
out.coffeeSubHidden = fresh(p => {
  type(p, "coffee"); clickChip(p, "sub:true"); clickText(p, $(p, "unk"), "Show them"); clickText(p, $(p, "unk"), "Hide them");
});
out.coffeeShipMin = fresh(p => { type(p, "coffee"); clickChip(p, "ship:min"); });
out.clothingShipMin = fresh(p => { type(p, "clothing"); clickChip(p, "ship:min"); });
out.clothingShipFree = fresh(p => { type(p, "clothing"); clickChip(p, "ship:free"); });
out.coffeeCoupon = fresh(p => { type(p, "coffee"); clickChip(p, "coupon:true"); });
out.coffeeSize2lb = fresh(p => { type(p, "coffee"); clickChip(p, "size"); clickChip(p, "size:2 lb"); });
out.coffeeSizeOpen = fresh(p => { type(p, "coffee"); clickChip(p, "size"); });
out.coffeeSizeBack = fresh(p => { type(p, "coffee"); clickChip(p, "size"); clickChip(p, "size:2 lb"); clickChip(p, "size"); clickChip(p, "size:2 lb"); });
out.midnight5lb = fresh(p => { type(p, "midnight"); clickChip(p, "size"); clickChip(p, "size:5 lb"); });
out.shoesSize = fresh(p => { type(p, "shoes"); clickChip(p, "size"); clickChip(p, "size:W 8 / M 6.5"); });
out.clothingSizeM = fresh(p => { type(p, "clothing"); clickChip(p, "size"); clickChip(p, "size:M"); });
out.shoesKind = fresh(p => { type(p, "shoes"); });
out.afterKind = fresh(p => { type(p, "coffee"); clickChip(p, "kind:Coffee"); });
out.removeKind = fresh(p => { type(p, "coffee"); clickChip(p, "kind:Coffee"); byAttr(p, "data-remove", "kind").dispatch("click"); });
out.sortLo = fresh(p => { type(p, "coffee"); $(p, "sort").value = "lo"; $(p, "sort").dispatch("change"); });
out.sortHi = fresh(p => { type(p, "coffee"); $(p, "sort").value = "hi"; $(p, "sort").dispatch("change"); });

// the first screen: tiles, browse, and no query wiped by anything
out.tile = fresh(p => { $(p, "tiles").children[0].children[0].dispatch("click"); });
out.browseAll = fresh(p => clickId(p, "browseall"));
out.moreKinds = fresh(p => clickId(p, "morebtn"));
out.queryKept = fresh(p => { type(p, "coffee"); clickChip(p, "coupon:true"); clickChip(p, "sub:true"); });

// empty states
// a chip stays on while the words change, so the box can end up with words its choices rule out
const airpodsCoupon = p => { type(p, "clothing"); clickChip(p, "coupon:true"); type(p, "airpods"); };
out.emptyFilters = fresh(airpodsCoupon);
out.emptyFiltersDrop = fresh(p => { airpodsCoupon(p); clickText(p, $(p, "empty"), "Drop"); });
out.emptyFiltersClearAll = fresh(p => { airpodsCoupon(p); clickText(p, $(p, "empty"), "Clear all choices"); });
out.emptyNoQuery = fresh(null, { hash: "#kind=Clothing&coupon=1&ship=free" });
out.emptyNoQueryClear = fresh(p => { clickText(p, $(p, "empty"), "Clear all choices"); }, { hash: "#kind=Clothing&coupon=1&ship=free" });
out.emptySearchKind = fresh(p => { type(p, "zzyzx"); clickText(p, $(p, "empty"), "Kitchen"); });
out.emptySearchBrowse = fresh(p => { type(p, "zzyzx"); clickText(p, $(p, "empty"), "Browse all"); });
out.emptySearchClear = fresh(p => { type(p, "zzyzx"); clickText(p, $(p, "empty"), "Clear search"); });

// keyboard: arrow keys in suggestions, Enter, Escape
out.kbOpen = fresh(p => { type(p, "cof"); });
out.kbDown = fresh(p => { type(p, "cof"); key(p, "ArrowDown"); });
out.kbDown2 = fresh(p => { type(p, "cof"); key(p, "ArrowDown"); key(p, "ArrowDown"); });
out.kbUp = fresh(p => { type(p, "cof"); key(p, "ArrowUp"); });
out.kbEnterKind = fresh(p => { type(p, "cof"); key(p, "ArrowDown"); key(p, "Enter"); });
out.kbEnterNone = fresh(p => { type(p, "cof"); key(p, "Enter"); });
out.kbEscape1 = fresh(p => { type(p, "cof"); key(p, "Escape"); });
out.kbEscape2 = fresh(p => { type(p, "cof"); key(p, "Escape"); key(p, "Escape"); });
out.kbProduct = fresh(p => {
  type(p, "bambino");
  const items = snap(p).sugg.items;
  const i = items.findIndex(x => /Bambino/.test(x.text));
  for (let n = 0; n <= i; n++) key(p, "ArrowDown");
  key(p, "Enter");
});
out.kbEscapePop = fresh(p => { type(p, "coffee"); clickChip(p, "size"); p.document.dispatch("keydown", { key: "Escape" }); });
out.clickSugg = fresh(p => {
  type(p, "old nav");
  const rows = []; walk($(p, "sugg"), e => { if (e.attrs.role === "option") rows.push(e); });
  rows[0].dispatch("click");
});
// the list sits over the top results; scrolling to read them closes it, and arrows bring it back
const gesture = (p, y) => { p.scrollTo(y); };
out.scrollSmall = fresh(p => { type(p, "coffee"); gesture(p, 10); });
out.scrollFar = fresh(p => { type(p, "coffee"); gesture(p, 300); });
out.scrollThenArrow = fresh(p => { type(p, "coffee"); gesture(p, 300); key(p, "ArrowDown"); });
out.scrollThenType = fresh(p => { type(p, "coffee"); gesture(p, 300); type(p, "coffee beans"); });
out.clearButton = fresh(p => { type(p, "coffee"); clickId(p, "clearq"); });

// the address bar: typing replaces, choices push, Back restores
{
  const p = boot();
  type(p, "cof"); type(p, "coffee");
  clickChip(p, "sub:true");
  clickChip(p, "coupon:true");
  const forward = snap(p);
  p.back("#q=coffee&sub=1");
  const back1 = snap(p);
  p.back("#q=coffee");
  const back2 = snap(p);
  p.back("");
  const back3 = snap(p);
  out.history = { forward: forward, back1: back1, back2: back2, back3: back3 };
}
out.hashRestore = {};
for (const h of ["#q=cofee&ship=min", "#kind=Shoes", "#all=1", "#q=coffee&size=2%20lb", "#store=Lavazza", "#q=coffee&sort=lo", "#kind=Nope&ship=weird&q=tea", "#q=%E0%A4%A"]) {
  out.hashRestore[h] = fresh(null, { hash: h });
}

process.stdout.write(JSON.stringify(out));
