/* Deal Finder search engine: pure functions over the embedded catalog.
 *
 * No DOM and no network. The page script (view.js) draws what this returns;
 * tests/test_page.py runs this file on its own in node.
 *
 * Catalog entry (built from stored evidence by demo/build.py, never typed here):
 *   n name, m store, k kind, kw extra search words, pc shelf price in cents,
 *   pl shelf price label, u store page url, c check date, cp printed coupon
 *   code or "", z page-listed sizes, sh page-stated shipping, sb page-stated
 *   subscribe option. Anything a page did not say is simply absent.
 *
 * Matching is whole words: "bean" finds bean/beans, never "beanie". A word
 * still being typed (the last one) may be a start of a word, but only while
 * no whole word in the catalog is exactly what was typed. A word nothing
 * matches may be a typo of a real catalog word, and the page says so.
 *
 * One predicate (judge) decides whether a product is listed under the current
 * choices; every chip count is the length of the list that predicate gives
 * with that chip on, so a count and its list cannot disagree.
 */
var DealFinderEngine = (function () {
"use strict";

function fold(s) {
  return String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[™®©]/g, "").replace(/[’‘`]/g, "'");
}
function words(s) { return fold(s).match(/[a-z0-9]+/g) || []; }
// A typed price: "$25", "$25.00", "25 dollars", "25 bucks", "25 usd". It names an exact amount, never a range.
var PRICE_RE = /\$\s?(\d{1,5}(?:\.\d{1,2})?)(?![\d.]*\d)|\b(\d{1,5}(?:\.\d{1,2})?)\s*(?:dollars?|bucks?|usd)\b/gi;
function pricesIn(q) {
  var out = [], m;
  PRICE_RE.lastIndex = 0;
  while ((m = PRICE_RE.exec(String(q)))) out.push(Math.round(parseFloat(m[1] || m[2]) * 100));
  return out;
}
// What a shopper types for a tee: "t-shirt", "t shirt", "tshirts" are the catalog's "tee".
// A typed price is not a word to look for: it is read apart by pricesIn().
function typed(q) { return String(q).replace(PRICE_RE, " ").replace(/\bt[\s-]?shirts?\b/gi, "tee"); }
function stem(w) {
  if (w.length > 4 && /ies$/.test(w)) return w.slice(0, -3) + "y";
  if (w.length > 4 && /(?:ch|sh|x|ss|z)es$/.test(w)) return w.slice(0, -2);
  if (w.length > 3 && w.charAt(w.length - 1) === "s" && w.charAt(w.length - 2) !== "s") return w.slice(0, -1);
  return w;
}
// Damerau-Levenshtein (optimal string alignment) with an early exit.
function dl(a, b, max) {
  var la = a.length, lb = b.length, d = [], i, j;
  if (Math.abs(la - lb) > max) return max + 1;
  for (i = 0; i <= la; i++) d[i] = [i];
  for (j = 0; j <= lb; j++) d[0][j] = j;
  for (i = 1; i <= la; i++) {
    for (j = 1; j <= lb; j++) {
      var c = a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c);
      if (i > 1 && j > 1 && a.charAt(i - 1) === b.charAt(j - 2) && a.charAt(i - 2) === b.charAt(j - 1)) {
        d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
      }
    }
  }
  return d[la][lb];
}
function maxEdits(n) { return n < 5 ? 0 : (n < 9 ? 1 : 2); }
// A single letter is not yet a word to search for: it waits for a second one.
function tokens(q) {
  return words(typed(q)).filter(function (w) { return w.length > 1; });
}

var FIELDS = [["n", 10], ["k", 8], ["m", 6], ["w", 4]];
var MULT = { exact: 1, prefix: 0.8, typo: 0.5 };
var SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"];

function sizeOrder(a, b) {
  var ia = SIZE_ORDER.indexOf(a), ib = SIZE_ORDER.indexOf(b);
  if (ia >= 0 && ib >= 0) return ia - ib;
  if (ia >= 0) return -1;
  if (ib >= 0) return 1;
  var na = parseFloat(a.replace(/^\D+/, "")), nb = parseFloat(b.replace(/^\D+/, ""));
  if (!isNaN(na) && !isNaN(nb) && na !== nb) return na - nb;
  return a.localeCompare(b, undefined, { numeric: true });
}

function create(P) {
  var D = [], vocab = {}, byStem = {}, kinds = {}, stores = {};
  function setOf(arr) {
    var o = Object.create(null);
    arr.forEach(function (w) { o[w] = true; });
    return o;
  }
  P.forEach(function (p, idx) {
    var f = { n: setOf(words(p.n)), k: setOf(words(p.k)), m: setOf(words(p.m)), w: setOf(words((p.kw || []).join(" "))) };
    D.push(f);
    FIELDS.forEach(function (fl) {
      Object.keys(f[fl[0]]).forEach(function (w) {
        vocab[w] = true;
        (byStem[stem(w)] = byStem[stem(w)] || {})[w] = true;
        // "hoodies" is the plural of "hoodie", not of a word "hoody"
        if (/ie$/.test(w)) (byStem[stem(w + "s")] = byStem[stem(w + "s")] || {})[w] = true;
      });
    });
    kinds[p.k] = (kinds[p.k] || 0) + 1;
    stores[p.m] = (stores[p.m] || 0) + 1;
  });
  var vocabList = Object.keys(vocab);
  var kindNames = Object.keys(kinds).sort(function (a, b) { return a.localeCompare(b); });
  var storeWords = {};
  Object.keys(stores).forEach(function (m) { storeWords[m] = words(m); });

  /* ---- two-word versus one-word spellings of a real catalog word ----
   * "sweat pants" is the catalog's "sweatpants" when that word exists, and "sweatpants"
   * is "sweat pants" when the catalog has no such word but has both parts. Only real
   * catalog words are ever joined or split; nothing else changes. */
  function known(w) { return !!byStem[stem(w)]; }
  function tokenize(q) {
    var ts = tokens(q), out = [], i, j;
    for (i = 0; i < ts.length; i++) {
      if (i + 1 < ts.length && known(ts[i] + ts[i + 1])) { out.push(ts[i] + ts[i + 1]); i++; continue; }
      var w = ts[i], last = i === ts.length - 1, done = false;
      if (w.length >= 6 && !known(w) && !(last && vocabList.some(function (v) { return v.indexOf(w) === 0; }))) {
        for (j = 3; j <= w.length - 3; j++) {
          if (known(w.slice(0, j)) && known(w.slice(j))) { out.push(w.slice(0, j), w.slice(j)); done = true; break; }
        }
      }
      if (!done) out.push(w);
    }
    return out;
  }

  /* ---- one typed word -> the catalog words it means ---- */
  var resCache = {};
  function resolve(t, last) {
    var key = t + "|" + (last ? 1 : 0);
    if (resCache[key]) return resCache[key];
    var ts = stem(t), set = Object.create(null), mode = "none", n = 0, w, i;
    var ex = byStem[ts];
    if (ex) { Object.keys(ex).forEach(function (x) { set[x] = true; n++; }); mode = "exact"; }
    if (!n && last && t.length >= 2) {
      for (i = 0; i < vocabList.length; i++) {
        if (vocabList[i].indexOf(t) === 0) { set[vocabList[i]] = true; n++; }
      }
      if (n) mode = "prefix";
    }
    if (!n && maxEdits(t.length)) {
      var m = maxEdits(t.length), best = m + 1;
      for (i = 0; i < vocabList.length; i++) {
        w = vocabList[i];
        if (w.length < 4 || w.charAt(0) !== t.charAt(0)) continue;
        var d = dl(stem(w), ts, m);
        if (d < best) { best = d; set = Object.create(null); n = 0; }
        if (d === best && d <= m) { set[w] = true; n++; }
      }
      if (n) mode = "typo";
    }
    return (resCache[key] = { t: t, mode: mode, set: set });
  }
  function resolveAll(q) {
    var ts = tokenize(q);
    return ts.map(function (t, i) { return resolve(t, i === ts.length - 1); });
  }
  function wordList(res) { return Object.keys(res.set).sort(); }

  /* ---- a product against the typed words ---- */
  function hitWeight(idx, res) {
    var f = D[idx], best = 0, fi, w, ws;
    for (fi = 0; fi < FIELDS.length; fi++) {
      ws = f[FIELDS[fi][0]];
      for (w in res.set) {
        if (ws[w]) {
          var sc = FIELDS[fi][1] * MULT[res.mode];
          if (sc > best) best = sc;
          break;
        }
      }
    }
    return best;
  }
  function inName(idx, res) {
    for (var w in res.set) if (D[idx].n[w]) return true;
    return false;
  }
  // Every typed word must hit, and every typed price must be the product's stored shelf price.
  // Nothing typed: every product, unscored.
  function match(q) {
    var rs = resolveAll(q), prices = pricesIn(q), out = [];
    P.forEach(function (p, idx) {
      var s = 0, ok = true, nameAll = true;
      for (var pi = 0; pi < prices.length; pi++) {
        if (p.pc !== prices[pi]) { ok = false; break; }
        s += 10;
      }
      if (!ok) return;
      for (var i = 0; i < rs.length; i++) {
        var h = rs[i].mode === "none" ? 0 : hitWeight(idx, rs[i]);
        if (!h) { ok = false; break; }
        s += h;
        if (!inName(idx, rs[i])) nameAll = false;
      }
      if (ok) out.push({ i: idx, s: s + (rs.length && nameAll ? 5 : 0) });
    });
    return { res: rs, rows: out };
  }

  /* ---- the one predicate: 1 listed, 0 not listed, -1 the page does not say ---- */
  function fShip(p, v) {
    var sh = p.sh;
    if (!sh) return -1;
    if (v === "free") return sh.k === "free" ? 1 : 0;
    // "over a minimum" is only what the page printed; members-only is never free shipping
    return sh.k === "threshold" && !sh.members ? 1 : 0;
  }
  function fSub(p) { return p.sb ? 1 : -1; }
  function fSize(p, v) {
    if (!p.z || !p.z.length) return -1;
    for (var i = 0; i < p.z.length; i++) if (p.z[i].k === v) return p.z[i].ok === false ? 0 : 1;
    return 0;
  }
  function judge(idx, st) {
    var p = P[idx], unk = false, r;
    if (st.kind && p.k !== st.kind) return 0;
    if (st.store && p.m !== st.store) return 0;
    if (st.coupon && !p.cp) return 0;
    if (st.ship) { r = fShip(p, st.ship); if (r === 0) return 0; if (r < 0) unk = true; }
    if (st.sub) { r = fSub(p); if (r === 0) return 0; if (r < 0) unk = true; }
    if (st.size) { r = fSize(p, st.size); if (r === 0) return 0; if (r < 0) unk = true; }
    return unk ? -1 : 1;
  }

  /* ---- price shown: the page's own price for a chosen size, else the shelf price ---- */
  function shown(idx, st) {
    var p = P[idx];
    if (st.size && p.z) {
      for (var i = 0; i < p.z.length; i++) {
        if (p.z[i].k === st.size && p.z[i].c != null) return { cents: p.z[i].c, size: st.size, resized: true };
      }
    }
    return { cents: p.pc, size: null, resized: false };
  }
  function sortRows(rows, st) {
    var mode = st.sort || "rel";
    rows.sort(function (a, b) {
      if (mode === "lo") return shown(a.i, st).cents - shown(b.i, st).cents || a.i - b.i;
      if (mode === "hi") return shown(b.i, st).cents - shown(a.i, st).cents || a.i - b.i;
      return (b.s - a.s) || (a.i - b.i);   // relevance, then the fixed catalog order: never reshuffles
    });
    return rows;
  }

  // The list a shopper sees (rows) and the pages that say nothing about a chosen fact (unk).
  function list(st, m) {
    m = m || match(st.q);
    var rows = [], unk = [];
    m.rows.forEach(function (r) {
      var j = judge(r.i, st);
      if (j === 1) rows.push(r); else if (j === -1) unk.push(r);
    });
    return { rows: sortRows(rows, st), unk: sortRows(unk, st), m: m };
  }
  function withMod(st, mod) {
    var o = {};
    Object.keys(st).forEach(function (k) { o[k] = st[k]; });
    Object.keys(mod).forEach(function (k) { o[k] = mod[k]; });
    return o;
  }
  function count(st, mod, m) { return list(withMod(st, mod), m).rows.length; }

  function hasIntent(st) {
    return !!(tokens(st.q).length || pricesIn(st.q).length || st.kind || st.store || st.browse || st.size || st.ship || st.sub || st.coupon);
  }

  // Chips for the current results. Each count is count(): the list with that chip on.
  function chips(st, cur) {
    var m = cur.m, out = { kinds: [], sizes: [], facts: [] };
    if (!st.kind) {
      var kc = {};
      m.rows.forEach(function (r) {
        if (judge(r.i, withMod(st, { kind: null })) === 1) kc[P[r.i].k] = (kc[P[r.i].k] || 0) + 1;
      });
      var ks = Object.keys(kc).sort(function (a, b) { return kc[b] - kc[a] || a.localeCompare(b); });
      if (ks.length > 1) out.kinds = ks.slice(0, 8).map(function (k) { return { v: k, n: count(st, { kind: k }, m) }; });
    }
    var seen = {};
    m.rows.forEach(function (r) {
      if (judge(r.i, withMod(st, { size: null })) !== 0) {
        (P[r.i].z || []).forEach(function (z) { if (z.ok !== false) seen[z.k] = true; });
      }
    });
    Object.keys(seen).sort(sizeOrder).forEach(function (z) {
      var n = count(st, { size: z }, m);
      if (n || st.size === z) out.sizes.push({ v: z, n: n });
    });
    [["ship", "free", "Free shipping, no minimum"], ["ship", "min", "Free over a minimum"],
     ["sub", true, "Subscribe option stated"], ["coupon", true, "Printed coupon"]].forEach(function (c) {
      var on = st[c[0]] === c[1], n = on ? cur.rows.length : count(st, (function (o) { o[c[0]] = c[1]; return o; })({}), m);
      if (n || on) out.facts.push({ key: c[0], v: c[1], label: c[2], n: n, on: on });
    });
    return out;
  }

  // Which chosen facts the unlisted pages are silent about, for the "don't state" line.
  function silentOn(st) {
    var w = [];
    if (st.size) w.push("size");
    if (st.ship) w.push("shipping");
    if (st.sub) w.push("a subscribe option");
    return w;
  }

  // Plain notes for words that matched only as a typo of a real catalog word.
  function notes(m) {
    var out = [];
    m.res.forEach(function (r) {
      if (r.mode === "typo") {
        out.push("No exact word “" + r.t + "” in the catalog — showing close spellings: " + wordList(r).slice(0, 4).join(", ") + ".");
      }
    });
    return out;
  }

  /* ---- nothing listed: the closest real products, and which word each matched ---- */
  function nearest(q) {
    var ts = tokenize(q), rs = resolveAll(q), out = [];
    if (ts.length === 1 && rs[0].mode === "none" && ts[0].length >= 5) {
      var head = ts[0].slice(0, 4), set = Object.create(null), any = false;
      vocabList.forEach(function (w) { if (w.indexOf(head) === 0) { set[w] = true; any = true; } });
      if (any) rs = [{ t: ts[0], mode: "prefix", set: set, head: head }];
    }
    // a word few products carry says more about a close match than a common one
    var df = rs.map(function (r) {
      var n = 0;
      if (r.mode !== "none") P.forEach(function (p, idx) { if (hitWeight(idx, r)) n++; });
      return n;
    });
    P.forEach(function (p, idx) {
      var hit = [], miss = [], s = 0, rare = 0, set = Object.create(null);
      rs.forEach(function (r, ri) {
        var h = r.mode === "none" ? 0 : hitWeight(idx, r);
        if (h) {
          s += h;
          rare += 1 / df[ri];
          hit.push(r.head ? r.head : r.t);
          Object.keys(r.set).forEach(function (w) { set[w] = true; });
        } else miss.push(r.t);
      });
      if (hit.length) out.push({ i: idx, s: s, rare: rare, hit: hit, miss: miss, set: set, head: !!(rs[0] && rs[0].head) });
    });
    out.sort(function (a, b) { return b.hit.length - a.hit.length || b.rare - a.rare || b.s - a.s || a.i - b.i; });
    return out.slice(0, 3);
  }

  /* ---- suggestions while typing ---- */
  function suggest(st) {
    var ts = tokenize(st.q), items = [];
    if (!ts.length) return items;
    var rs = resolveAll(st.q), lastRes = rs[rs.length - 1];
    kindNames.filter(function (k) {
      return words(k).some(function (w) { return lastRes.mode !== "none" && lastRes.set[w]; });
    }).slice(0, 2).forEach(function (k) {
      items.push({ type: "kind", val: k, label: k, sub: "kind · " + kinds[k] + (kinds[k] === 1 ? " product" : " products") });
    });
    Object.keys(stores).filter(function (m) {
      return rs.every(function (r) { return r.mode !== "none" && storeWords[m].some(function (w) { return r.set[w]; }); });
    }).sort(function (a, b) { return stores[b] - stores[a] || a.localeCompare(b); }).slice(0, 2).forEach(function (m) {
      items.push({ type: "store", val: m, label: m, sub: "store · " + stores[m] + (stores[m] === 1 ? " product" : " products") });
    });
    var rows = match(st.q).rows.filter(function (r) { return judge(r.i, st) !== 0; });
    sortRows(rows, { sort: "rel" }).slice(0, 5).forEach(function (r) {
      items.push({ type: "product", val: P[r.i].n, label: P[r.i].n, sub: P[r.i].pl + " · " + P[r.i].m, i: r.i });
    });
    return items;
  }

  // Parts of text whose word the typed words hit: [{t: text, hit: bool}].
  function marks(text, rs) {
    var out = [];
    String(text).split(/([A-Za-z0-9À-ɏ]+)/).forEach(function (seg) {
      if (!seg) return;
      if (/^[A-Za-z0-9À-ɏ]+$/.test(seg)) {
        var w = words(seg)[0];
        out.push({ t: seg, hit: !!w && rs.some(function (r) { return r.mode !== "none" && r.set[w]; }) });
      } else out.push({ t: seg, hit: false });
    });
    return out;
  }

  /* ---- the address bar: what the page is showing, so Back and refresh work ---- */
  function blank() {
    return { q: "", kind: null, store: null, size: null, ship: null, sub: false, coupon: false, sort: "rel", browse: false };
  }
  function encode(st) {
    var a = [];
    function add(k, v) { a.push(k + "=" + encodeURIComponent(v)); }
    if (st.q) add("q", st.q);
    if (st.kind) add("kind", st.kind);
    if (st.store) add("store", st.store);
    if (st.size) add("size", st.size);
    if (st.ship) add("ship", st.ship);
    if (st.sub) add("sub", "1");
    if (st.coupon) add("coupon", "1");
    if (st.sort && st.sort !== "rel") add("sort", st.sort);
    if (st.browse) add("all", "1");
    return a.join("&");
  }
  function decode(hash) {
    var st = blank(), h = String(hash || "").replace(/^#/, "");
    if (!h) return st;
    h.split("&").forEach(function (kv) {
      var i = kv.indexOf("="), k, v;
      if (i < 0) return;
      k = kv.slice(0, i);
      try { v = decodeURIComponent(kv.slice(i + 1)); } catch (e) { return; }
      if (k === "q") st.q = v;
      else if (k === "kind" && kinds[v]) st.kind = v;
      else if (k === "store" && stores[v]) st.store = v;
      else if (k === "size" && v) st.size = v;
      else if (k === "ship" && (v === "free" || v === "min")) st.ship = v;
      else if (k === "sub") st.sub = true;
      else if (k === "coupon") st.coupon = true;
      else if (k === "sort" && /^(?:rel|lo|hi)$/.test(v)) st.sort = v;
      else if (k === "all") st.browse = true;
    });
    return st;
  }

  return {
    P: P, kinds: kinds, stores: stores, kindNames: kindNames,
    resolve: resolveAll, wordList: wordList, match: match, judge: judge, list: list, count: count,
    chips: chips, silentOn: silentOn, notes: notes, nearest: nearest, suggest: suggest, marks: marks,
    shown: shown, hasIntent: hasIntent, blank: blank, encode: encode, decode: decode,
    tokens: tokenize, prices: pricesIn,
  };
}

return { create: create, fold: fold, words: words, stem: stem, tokens: tokens, sizeOrder: sizeOrder };
})();
