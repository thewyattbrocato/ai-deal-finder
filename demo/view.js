/* Deal Finder page script: draws what DealFinderEngine returns.
 *
 * The product cards are written by demo/build.py from stored evidence; this
 * script only searches, orders, shows and hides them, and says how old each
 * check is. It adds no price, coupon, size or shipping fact of its own.
 */
(function () {
"use strict";
var P = JSON.parse(document.getElementById("catalog").textContent);
var E = DealFinderEngine.create(P);
var PAGE = 24;

function $(id) { return document.getElementById(id); }
function show(el, on) { el.style.display = on ? "" : "none"; }
function text(s) { return document.createTextNode(s); }
function h(tag, attrs, kids) {
  var e = document.createElement(tag);
  Object.keys(attrs || {}).forEach(function (k) {
    if (k === "class") e.className = attrs[k];
    else if (k === "text") e.textContent = attrs[k];
    else e.setAttribute(k, attrs[k]);
  });
  (kids || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? text(c) : c); });
  return e;
}
function clear(e) { e.textContent = ""; }
function fmt(cents) { return "$" + (cents / 100).toFixed(2); }
function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

var q = $("q"), sugg = $("sugg"), clearq = $("clearq"), results = $("results");
var cards = [];
results.querySelectorAll("[data-i]").forEach(function (c) { cards[parseInt(c.getAttribute("data-i"), 10)] = c; });
function first(c, attr) { return c.querySelectorAll("[" + attr + "]")[0]; }
var base = cards.map(function (c) {
  return { price: first(c, "data-price-text").textContent, shelf: first(c, "data-shelf-line").textContent };
});

// ---- how old each stored check is, from its stored time only: whole days, no verdict, no threshold
var NOW = new Date();  // the one read of "today", for the age line and the printed windows
function checkedAge(iso) {
  var d = iso.slice(0, 10);
  var then = Date.parse(d + "T00:00:00Z");
  var today = Date.UTC(NOW.getUTCFullYear(), NOW.getUTCMonth(), NOW.getUTCDate());
  var days = Math.round((today - then) / 86400000);
  if (isNaN(days) || days < 0) return "Checked " + d;
  if (days === 0) return "Checked today, " + d;
  return "Checked " + days + (days === 1 ? " day" : " days") + " ago, " + d;
}
cards.forEach(function (c) {
  var el = first(c, "data-age");
  el.textContent = checkedAge(el.getAttribute("data-observed"));
});

// A coupon page's own printed date window against the browser's date (calendar days, ISO strings compare).
// Ended means information only: never an available offer, never a lower price.
// Printed ends are US Eastern ("11:59 PM ET"), so "today" is the Eastern calendar date, not the viewer's.
var TODAY = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit" }).format(NOW);
function windowState(start, end) {
  if (!start || !end) return "none";
  if (TODAY < start) return "before";
  if (TODAY > end) return "ended";
  return "inside";
}
var WINDOW_TEXT = {
  before: "Today in US Eastern time (" + TODAY + ") is before the page's printed window.",
  inside: "Today in US Eastern time (" + TODAY + ") is inside the page's printed window. The code is still never tried: confirm it at checkout.",
  ended: "The page's printed window has ended (today in US Eastern time is " + TODAY + "). Shown as information only, not as an available offer."
};
cards.forEach(function (c) {
  var row = first(c, "data-window-row");
  if (!row) return;
  var state = windowState(row.getAttribute("data-window-start"), row.getAttribute("data-window-end"));
  c.setAttribute("data-window-state", state);
  if (state === "none") return;
  first(row, "data-window-status").textContent = WINDOW_TEXT[state];
  if (state !== "ended") return;
  first(c, "data-saving-status").textContent = "The page's printed window has ended";
  first(c, "data-coupon-label").textContent = "The page's printed window has ended — code the page printed, information only:";
  first(c, "data-confirm-code").textContent = "whether any offer is still available (the page's printed window has ended)";
  first(c, "data-coupon-ended").textContent = " Its printed window has ended: information only, not an available offer.";
});

// ---- state, kept in the address bar so Back and refresh work
var S = E.blank();
var limit = PAGE, unkOpen = false, popOpen = false, lastHash = "", sgItems = [], sgActive = -1;

function pushState(replace) {
  var hash = E.encode(S);
  if (hash === lastHash) return;
  lastHash = hash;
  try {
    var url = location.pathname + location.search + (hash ? "#" + hash : "");
    if (replace) history.replaceState(null, "", url); else history.pushState(null, "", url);
  } catch (e) { /* a page opened without an address still works */ }
}
function commit(replace) { pushState(replace); render(); }
function fromHash() { S = E.decode(location.hash); lastHash = E.encode(S); q.value = S.q; }
window.addEventListener("popstate", function () { fromHash(); limit = PAGE; render(); });

// ---- first screen
var kindsByCount = E.kindNames.slice().sort(function (a, b) { return E.kinds[b] - E.kinds[a] || a.localeCompare(b); });
function renderStart() {
  var tiles = $("tiles"), more = $("morekinds");
  kindsByCount.slice(0, 5).forEach(function (k) {
    var b = h("button", { type: "button", class: "tile" }, [h("b", { text: k }), h("span", { text: plural(E.kinds[k], "product", "products") })]);
    b.addEventListener("click", function () { pickKind(k); });
    tiles.appendChild(h("li", {}, [b]));
  });
  kindsByCount.slice(5).forEach(function (k) {
    var b = h("button", { type: "button", class: "chip" }, [text(k + " "), h("span", { class: "n", text: String(E.kinds[k]) })]);
    b.addEventListener("click", function () { pickKind(k); });
    more.appendChild(h("li", {}, [b]));
  });
  $("allcount").textContent = P.length;
  var dates = P.map(function (p) { return p.c; }).sort();
  $("range").textContent = "Store pages read " + dates[0] + (dates[0] !== dates[dates.length - 1] ? " to " + dates[dates.length - 1] : "")
    + " · " + P.length + " products, " + Object.keys(E.stores).length + " stores.";
}
function pickKind(k) { S.kind = k; S.q = ""; q.value = ""; limit = PAGE; commit(false); focusBox(); }
$("morebtn").addEventListener("click", function () {
  var m = $("morekinds"), open = m.style.display === "none";
  show(m, open);
  this.setAttribute("aria-expanded", open ? "true" : "false");
  this.textContent = open ? "Fewer kinds" : "More kinds";
});
$("browseall").addEventListener("click", function () { S.browse = true; limit = PAGE; commit(false); });

// ---- suggestions (kinds, stores, products with their shelf price)
var sgY = 0;  // page scroll when the list opened (or last followed a highlight)
function pageY() { return window.pageYOffset || 0; }
function hideSugg() {
  show(sugg, false);
  clear(sugg);
  q.setAttribute("aria-expanded", "false");
  q.setAttribute("aria-activedescendant", "");
  sgActive = -1;
}
function appendMarked(parent, str, res) {
  E.marks(str, res).forEach(function (m) { parent.appendChild(m.hit ? h("mark", { text: m.t }) : text(m.t)); });
}
function showSuggestions() {
  sgItems = E.suggest(S);
  sgActive = -1;
  if (!sgItems.length) { hideSugg(); return; }
  clear(sugg);
  var last = "", titles = { kind: "Kinds", store: "Stores", product: "Products" }, res = E.resolve(q.value);
  sgItems.forEach(function (it, i) {
    if (it.type !== last) { sugg.appendChild(h("p", { class: "sg-h", role: "presentation", text: titles[it.type] })); last = it.type; }
    var label = h("span", { class: "t" });
    if (it.type === "product") appendMarked(label, it.label, res); else label.appendChild(text(it.label));
    var row = h("div", { class: "sg", role: "option", id: "sg" + i, "data-i": String(i), "aria-selected": "false" }, [label, h("span", { class: "s", text: it.sub })]);
    row.addEventListener("mousedown", function (e) { e.preventDefault(); });  // keep the cursor in the box
    row.addEventListener("click", function () { choose(i); });
    sugg.appendChild(row);
  });
  show(sugg, true);
  q.setAttribute("aria-expanded", "true");
  sgY = pageY();
}
function setActive(i) {
  var els = sugg.querySelectorAll("[data-i]");
  if (!els.length) return;
  if (i < 0) i = els.length - 1;
  if (i >= els.length) i = 0;
  els.forEach(function (e) { e.setAttribute("aria-selected", "false"); });
  els[i].setAttribute("aria-selected", "true");
  q.setAttribute("aria-activedescendant", els[i].getAttribute("id"));
  if (els[i].scrollIntoView) els[i].scrollIntoView({ block: "nearest" });
  sgY = pageY();  // following the highlight is not the shopper scrolling away
  sgActive = i;
}
function choose(i) {
  var it = sgItems[i];
  if (!it) return;
  if (it.type === "kind") { S.kind = it.val; S.q = ""; q.value = ""; }
  else if (it.type === "store") { S.store = it.val; S.q = ""; q.value = ""; }
  else { S.q = it.val; q.value = it.val; }
  limit = PAGE;
  hideSugg();
  commit(false);
}

// ---- the search box: results change on every keystroke, no Search button
q.addEventListener("input", function () {
  S.q = q.value;
  limit = PAGE;
  if (S.browse && S.q) S.browse = false;
  commit(true);
  showSuggestions();
});
var booting = true;  // focusing the box when the page opens must not open the suggestions
q.addEventListener("focus", function () { if (q.value && !booting) showSuggestions(); });
q.addEventListener("keydown", function (e) {
  var open = sugg.style.display !== "none";
  if (e.key === "ArrowDown") { e.preventDefault(); if (!open) showSuggestions(); setActive(sgActive + 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); if (open) setActive(sgActive - 1); }
  else if (e.key === "Enter") { e.preventDefault(); if (open && sgActive >= 0) choose(sgActive); else hideSugg(); }
  else if (e.key === "Escape") {
    e.preventDefault();
    if (open) hideSugg();
    else if (q.value) { q.value = ""; S.q = ""; limit = PAGE; commit(false); }
  }
  else if (e.key === "Tab") hideSugg();
});
clearq.addEventListener("click", function () { q.value = ""; S.q = ""; hideSugg(); limit = PAGE; commit(false); q.focus(); });
$("sort").addEventListener("change", function () { S.sort = this.value; limit = PAGE; commit(true); });
document.addEventListener("click", function (e) {
  var t = e.target, inBox = false;
  while (t) { if (t === q || t === sugg) inBox = true; t = t.parent || t.parentNode; }
  if (!inBox) hideSugg();
});
// The list sits over the top results, and scrolling does not move it off them, so a shopper who scrolls to read the results gets them uncovered with no extra click or key.
window.addEventListener("scroll", function () {
  if (sugg.style.display === "none") return;
  if (Math.abs(pageY() - sgY) > 24) hideSugg();
});
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape" && popOpen) { popOpen = false; render(); focusChip("size"); }
});

// ---- chips
function findAttr(root, attr, value) {
  var all = root.querySelectorAll("[" + attr + "]");  // a NodeList: no filter()
  for (var i = 0; i < all.length; i++) if (all[i].getAttribute(attr) === value) return all[i];
  return null;
}
function shownEl(n) {
  for (; n; n = n.parentNode) if (n.style && n.style.display === "none") return false;
  return true;
}
// Where focus goes when the control that had it is redrawn away: the count line above the list.
// It takes focus without raising a phone keyboard and is read out as the new result count.
function focusResults() {
  var c = $("count");
  if (c.focus) c.focus({ preventScroll: true });
}
// After a change the shopper made with a pointer: type at once on a desktop; on a phone, do not raise the keyboard over the list.
function focusBox() {
  if (window.matchMedia && matchMedia("(hover: hover) and (pointer: fine)").matches) q.focus(); else focusResults();
}
function focusChip(key) {
  var n = findAttr(document, "data-chip", key);
  if (!n || !shownEl(n)) {
    // a picked size closes its list and a picked kind moves to "Showing": follow the choice
    if (/^size:/.test(key)) n = findAttr(document, "data-chip", "size");
    else if (/^kind:/.test(key)) n = findAttr(document, "data-remove", "kind");
  }
  if (n && shownEl(n) && n.focus) n.focus(); else focusResults();
}
function chip(label, n, pressed, key, onClick) {
  var b = h("button", { type: "button", class: "chip", "aria-pressed": pressed ? "true" : "false", "data-chip": key,
    "aria-label": n == null ? label : label + ", " + plural(n, "result", "results") });
  b.appendChild(text(label));
  if (n != null) { b.appendChild(text(" ")); b.appendChild(h("span", { class: "n", "aria-hidden": "true", text: String(n) })); }
  b.addEventListener("click", function () { onClick(); limit = PAGE; commit(false); focusChip(key); });
  return b;
}
// A labelled row of chips; the label sits at the start of the row to keep the panel short.
function row(label, id, items) {
  var ul = h("ul", { class: "chiprow", "aria-labelledby": id },
    [h("li", {}, [h("span", { class: "rowlabel", id: id, text: label })])].concat(items.map(function (c) { return h("li", {}, [c]); })));
  return [ul];
}
var SHIP_LABEL = { free: "Free shipping, no minimum", min: "Free over a minimum" };
function activeList() {
  var a = [];
  if (S.kind) a.push(["kind", "Kind: " + S.kind, function () { S.kind = null; }]);
  if (S.store) a.push(["store", "Store: " + S.store, function () { S.store = null; }]);
  if (S.size) a.push(["size", "Size: " + S.size, function () { S.size = null; }]);
  if (S.ship) a.push(["ship", SHIP_LABEL[S.ship], function () { S.ship = null; }]);
  if (S.sub) a.push(["sub", "Subscribe option stated", function () { S.sub = false; }]);
  if (S.coupon) a.push(["coupon", "Printed coupon", function () { S.coupon = false; }]);
  if (S.browse && !a.length && !S.q) a.push(["browse", "Everything checked", function () { S.browse = false; }]);
  return a;
}
function renderActive() {
  var box = $("active"), a = activeList();
  clear(box);
  if (!a.length) return;
  var ul = h("ul", { class: "chiprow", "aria-labelledby": "lbl-active" }, [h("li", {}, [h("span", { class: "rowlabel", id: "lbl-active", text: "Showing" })])]);
  a.forEach(function (c) {
    var b = h("button", { type: "button", class: "chip active", "data-remove": c[0], "aria-label": "Remove: " + c[1] }, [text(c[1] + " "), h("span", { "aria-hidden": "true", text: "×" })]);
    b.addEventListener("click", function () { c[2](); limit = PAGE; commit(false); focusBox(); });
    ul.appendChild(h("li", {}, [b]));
  });
  if (a.length > 1) {
    var all = h("button", { type: "button", class: "linkbtn", "data-clearall": "1", text: "Clear all" });
    all.addEventListener("click", function () { S = E.blank(); q.value = ""; limit = PAGE; commit(false); focusBox(); });
    ul.appendChild(h("li", {}, [all]));
  }
  box.appendChild(ul);
}
function renderBar(cur) {
  var bar = $("bar"), refine = $("refine");
  clear(bar);
  if (!cur.rows.length && !cur.unk.length) { show(refine, false); return; }
  show(refine, true);
  var c = E.chips(S, cur), n = activeList().length;
  $("refine-count").textContent = n ? " (" + n + " on)" : "";
  if (c.kinds.length) {
    row("Kind", "lbl-kind", c.kinds.map(function (k) {
      return chip(k.v, k.n, false, "kind:" + k.v, function () { S.kind = k.v; });
    })).forEach(function (n2) { bar.appendChild(n2); });
  }
  var facts = [];
  if (c.sizes.length || S.size) {
    var open = h("button", { type: "button", class: "chip" + (S.size ? " active" : ""), "aria-pressed": S.size ? "true" : "false", "data-chip": "size",
      "aria-haspopup": "true", "aria-expanded": popOpen ? "true" : "false", text: "Size" + (S.size ? ": " + S.size : " \u25be") });
    // the size button opens the list; it does not change the results by itself
    open.addEventListener("click", function () { popOpen = !popOpen; render(); focusChip("size"); });
    var pop = h("div", { class: "popbody", role: "group", "aria-label": "Sizes the pages list" }, [
      h("p", { text: "Sizes the store page lists (sizes it shows out of stock are left out). The number is how many results list that size." }),
      h("div", { class: "grid" }, c.sizes.map(function (z) {
        return chip(z.v, z.n, S.size === z.v, "size:" + z.v, function () { S.size = S.size === z.v ? null : z.v; popOpen = false; });
      }))
    ]);
    show(pop, popOpen);
    facts.push(h("div", { class: "pop" }, [open, pop]));
  }
  c.facts.forEach(function (f) {
    facts.push(chip(f.label, f.n, f.on, f.key + ":" + f.v, function () {
      if (f.key === "ship") S.ship = S.ship === f.v ? null : f.v;
      else S[f.key] = !S[f.key];
    }));
  });
  if (facts.length) row("Narrow these results", "lbl-narrow", facts).forEach(function (n2) { bar.appendChild(n2); });
}

// ---- the one list, the pages that do not say, and the empty state
function renderEmpty(cur) {
  var box = $("empty"), toks = E.tokens(S.q), n = P.length;
  clear(box);
  var chipsOn = !!(S.size || S.ship || S.sub || S.coupon || S.kind || S.store);
  function btn(label, sub, fn, attrs) {
    var b = h("button", Object.assign({ type: "button", class: "chip" }, attrs || {}), [text(label)].concat(sub ? [text(" "), h("span", { class: "n", text: sub })] : []));
    b.addEventListener("click", function () { fn(); limit = PAGE; commit(false); focusResults(); });
    return h("li", {}, [b]);
  }
  if (S.q && cur.m.rows.length && chipsOn) {
    box.appendChild(h("h2", { text: "“" + S.q + "” matches " + plural(cur.m.rows.length, "checked product", "checked products") + ", but none also fit your choices" }));
    box.appendChild(h("p", { text: "Nothing is shown that doesn’t fit. Drop a choice to see what remains:" }));
    var drops = h("ul", { class: "chiprow" });
    activeList().forEach(function (a) {
      var mod = { kind: { kind: null }, store: { store: null }, size: { size: null }, ship: { ship: null }, sub: { sub: false }, coupon: { coupon: false } }[a[0]];
      var left = mod ? E.count(S, mod, cur.m) : 0;
      if (left) drops.appendChild(btn("Drop " + a[1], left + " would show", a[2], { "data-drop": a[0] }));
    });
    drops.appendChild(btn("Clear all choices", null, function () { S = E.blank(); S.q = q.value; }, { "data-clearall": "1" }));
    box.appendChild(drops);
    return;
  }
  if (!S.q) {
    box.appendChild(h("h2", { text: "No checked product fits these choices" }));
    box.appendChild(h("p", { text: "Nothing is shown that doesn’t fit." }));
    box.appendChild(h("ul", { class: "chiprow" }, [btn("Clear all choices", null, function () { S = E.blank(); q.value = ""; }, { "data-clearall": "1" })]));
    return;
  }
  box.appendChild(h("h2", { text: "No checked product matches “" + S.q + "”" }));
  if (E.prices(S.q).length) {
    box.appendChild(h("p", { "data-price-note": "1", text: "Search matches words and an exact shelf price (“$25” finds products priced exactly $25.00). It does not find “under” or “over” a price. To see prices in order, browse everything and sort by price." }));
  }
  box.appendChild(h("p", { text: "Searched " + n + " checked products by name, store and kind" + (toks.length > 1 ? " for all of: " + toks.map(function (t) { return "“" + t + "”"; }).join(", ") : "")
    + ". Nothing is shown that doesn’t match, and nothing is guessed." }));
  var near = E.nearest(S.q);
  if (near.length) {
    box.appendChild(h("h3", { text: "Closest checked products" }));
    box.appendChild(h("p", { text: "Each one matches only part of what you typed. The matched part is marked." }));
    var ul = h("ul", { class: "near" });
    near.forEach(function (r) {
      var p = P[r.i], nm = h("div", { class: "nm" });
      appendMarked(nm, p.n, [{ mode: "prefix", set: r.set }]);
      var why = r.head ? "Shares only the start “" + r.hit[0] + "”"
        : "Matches “" + r.hit.join(", ") + "” · doesn’t match “" + r.miss.join(", ") + "”";
      var link = h("a", { href: p.u, target: "_blank", rel: "noopener", text: "See at " + p.m + " →" });
      ul.appendChild(h("li", { class: "nearitem", "data-near": p.n }, [h("div", { style: "min-width:0" }, [nm, h("div", { class: "why", text: p.pl + " · " + p.m + " · " + why })]), link]));
    });
    box.appendChild(ul);
  } else {
    box.appendChild(h("p", { text: "No checked product shares a word with that, so there is no close match to offer." }));
  }
  box.appendChild(h("h3", { text: "One tap to somewhere real" }));
  var kinds = h("ul", { class: "chiprow" });
  kindsByCount.slice(0, 6).forEach(function (k) {
    kinds.appendChild(btn(k, String(E.kinds[k]), function () { S.kind = k; S.q = ""; q.value = ""; }, { "data-kind": k }));
  });
  if (E.prices(S.q).length) {
    kinds.appendChild(btn("Browse all " + n + ", lowest price first", null, function () { S.q = ""; q.value = ""; S.browse = true; S.sort = "lo"; }, { "data-price-sort": "1" }));
  }
  kinds.appendChild(btn("Browse all " + n, null, function () { S.q = ""; q.value = ""; S.browse = true; }, { "data-browse": "1" }));
  kinds.appendChild(btn("Clear search", null, function () { S.q = ""; q.value = ""; }, { "data-clearq": "1" }));
  box.appendChild(kinds);
}

function markName(c, p, res) {
  var hd = first(c, "data-heading");
  clear(hd);
  appendMarked(hd, p.n, res);
}
function render() {
  var intent = E.hasIntent(S);
  show($("start"), !intent);
  show($("hint"), !intent);
  show($("resultsArea"), intent);
  show(clearq, !!q.value);
  $("sort").value = S.sort;
  if (!intent) { $("count").textContent = ""; show($("refine"), false); renderActive(); return; }

  var cur = E.list(S), res = cur.m.res;
  renderActive();
  renderBar(cur);

  var main = cur.rows.slice(0, limit);
  var listUnk = cur.unk.length && (unkOpen || !cur.rows.length);
  var unkShown = listUnk ? cur.unk.slice(0, limit) : [];
  var order = main.concat(unkShown);
  cards.forEach(function (c) { show(c, false); });
  var divider = $("unk-head");
  show(divider, false);
  main.forEach(function (r) { drawCard(r, res); });
  if (unkShown.length) { results.appendChild(divider); show(divider, true); }
  unkShown.forEach(function (r) { drawCard(r, res); });

  var cnt = $("count");
  cnt.textContent = cur.rows.length
    ? plural(cur.rows.length, "checked product", "checked products") + (S.q ? " for “" + S.q + "”" : "")
    : (S.q && !cur.m.rows.length ? "No checked product matches “" + S.q + "”" : "No checked product fits these choices");
  show($("sortbox"), cur.rows.length > 1);
  var notes = $("notes");
  clear(notes);
  E.notes(cur.m).forEach(function (n) { notes.appendChild(h("p", { class: "hint", "data-typo-note": "1", text: n })); });

  // pages that say nothing about a chosen fact are never counted as "no": they are listed apart
  var unk = $("unk");
  clear(unk);
  if (cur.unk.length) {
    var which = E.silentOn(S).join(" or "), many = cur.unk.length !== 1;
    if (cur.rows.length) {
      var tog = h("button", { type: "button", class: "linkbtn", "data-unk": "1", "aria-expanded": listUnk ? "true" : "false", text: listUnk ? "Hide them" : "Show them" });
      tog.addEventListener("click", function () { unkOpen = !listUnk; render(); focusAttr("data-unk"); });
      unk.appendChild(h("p", { class: "unk", role: "status" }, [
        cur.unk.length + " more " + (many ? "products don’t" : "product doesn’t") + " state " + which + " on the page, so " + (many ? "they aren’t" : "it isn’t") + " counted above. ", tog]));
    } else {
      // nothing fits: these pages are not matches, only pages that cannot be ruled out; listed below the box
      unk.appendChild(h("p", { class: "unk", role: "status" }, [
        "Not matches, but " + cur.unk.length + (many ? " products don’t" : " product doesn’t") + " state " + which + " on the page, so " + (many ? "they are" : "it is") + " listed below, apart from the empty result."]));
    }
  }
  show(unk, !!cur.unk.length);

  var empty = $("empty");
  var isEmpty = !cur.rows.length;
  show(empty, isEmpty);
  clear(empty);
  if (isEmpty) renderEmpty(cur);

  var more = $("show-more"), left = Math.max(cur.rows.length - limit, listUnk ? cur.unk.length - limit : 0);
  show(more, left > 0);
  more.textContent = "Show " + Math.min(PAGE, left) + " more (" + left + " left)";
  var hasCoffee = main.some(function (r) { return cards[r.i].getAttribute("data-coffee-note") === "yes"; });
  show($("coffee-note"), hasCoffee);
  return order;
}
function focusAttr(attr) {
  var n = document.querySelectorAll("[" + attr + "]")[0];
  if (n && n.focus) n.focus();
}
function drawCard(r, res) {
  var c = cards[r.i], p = P[r.i], sh = E.shown(r.i, S);
  show(c, true);
  results.appendChild(c);
  var price = first(c, "data-price-text"), shelf = first(c, "data-shelf-line"), line = first(c, "data-size-line");
  price.textContent = sh.resized ? fmt(sh.cents) : base[r.i].price;
  shelf.textContent = sh.resized ? fmt(sh.cents) + " for the " + sh.size + " bag, as printed on the page" : base[r.i].shelf;
  if (sh.resized) {
    line.textContent = "Showing the " + sh.size + " bag — the shelf price its page lists at that size.";
    show(line, true);
  } else show(line, false);
  markName(c, p, res);
}
$("show-more").addEventListener("click", function () { limit += PAGE; render(); if (!shownEl($("show-more"))) focusResults(); });

// ---- boot
renderStart();
fromHash();
if (window.matchMedia && matchMedia("(min-width: 641px)").matches) $("refine").setAttribute("open", "");
render();
if (window.matchMedia && matchMedia("(hover: hover) and (pointer: fine)").matches) q.focus();  // desktop: type at once
booting = false;
})();
