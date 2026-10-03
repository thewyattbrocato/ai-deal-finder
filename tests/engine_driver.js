// Runs the page's search engine on its own (no DOM) over the page's own embedded
// catalog and prints facts about it. tests/test_page.py asserts on this output.
const fs = require("fs");
const vm = require("vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const cat = JSON.parse(/<script type="application\/json" id="catalog">([\s\S]*?)<\/script>/.exec(html)[1]);
const src = /<script>\n(\/\* Deal Finder search engine[\s\S]*?)<\/script>/.exec(html)[1];
const ctx = vm.createContext({});
vm.runInContext(src, ctx);
const E = ctx.DealFinderEngine.create(cat);
const st = o => Object.assign(E.blank(), o || {});
const names = rows => rows.map(r => cat[r.i].n);
const out = {};

out.catalogSize = cat.length;
out.kinds = E.kinds;
out.rows = q => names(E.list(st({ q: q })).rows);
const Q = ["bean", "beans", "beanie", "beani", "cof", "coffee", "cofee", "espresso", "expresso", "sneaker", "sneakers", "shoe",
  "old nav", "bambino", "zzyzx", "co", "c", "", "  ", "the", "dog", "dogs", "lavazza", "nike",
  "sweat pants", "sweatpants", "sweat-pants", "sweatpant", "sweat pant", "olive oil", "oliveoil", "pan cake", "hoodie", "hoodies", "t-shirt", "t shirt", "tshirts", "tee", "phone", "bedding", "cat", "sneakers"];
out.queries = {};
Q.forEach(q => {
  const cur = E.list(st({ q: q }));
  out.queries[q] = { rows: names(cur.rows), scores: cur.rows.map(r => r.s), notes: E.notes(cur.m),
    modes: E.resolve(q).map(r => [r.t, r.mode, E.wordList(r).slice(0, 5)]), intent: E.hasIntent(st({ q: q })) };
});

// the same query twice gives the same order, and equal scores keep the fixed catalog order
out.order = {};
["coffee", "shoes", "clothing", "bag", "dog", "kitchen", "tea"].forEach(q => {
  const a = E.list(st({ q: q })).rows, b = E.list(st({ q: q })).rows;
  let tiesInOrder = true;
  for (let i = 1; i < a.length; i++) if (a[i - 1].s === a[i].s && a[i - 1].i > a[i].i) tiesInOrder = false;
  out.order[q] = { same: JSON.stringify(a) === JSON.stringify(b), tiesInOrder: tiesInOrder, n: a.length };
});
// typing a word letter by letter never reorders products that tie
out.typing = [];
{
  const w = "sweatpants";
  for (let i = 2; i <= w.length; i++) out.typing.push(names(E.list(st({ q: w.slice(0, i) })).rows));
}

// independent oracles: how many products a chip should list, computed from the catalog alone
function oracle(q, mod) {
  let n = 0;
  E.match(q).rows.forEach(r => {
    const p = cat[r.i];
    if (mod.coupon && !p.cp) return;
    if (mod.sub && !p.sb) return;
    if (mod.ship === "free" && !(p.sh && p.sh.k === "free")) return;
    if (mod.ship === "min" && !(p.sh && p.sh.k === "threshold" && !p.sh.members)) return;
    if (mod.size && !(p.z || []).some(z => z.k === mod.size && z.ok !== false)) return;
    if (mod.kind && p.k !== mod.kind) return;
    n++;
  });
  return n;
}
out.chips = [];
["", "coffee", "shoes", "clothing", "kitchen", "dog", "bag", "tea", "nike", "old navy", "lavazza", "shirt", "pet", "home", "cof"].forEach(q => {
  const s0 = st(q ? { q: q } : { browse: true });
  const cur = E.list(s0), c = E.chips(s0, cur);
  c.kinds.forEach(k => out.chips.push({ q: q, key: "kind:" + k.v, said: k.n, listed: E.list(st(Object.assign({}, s0, { kind: k.v }))).rows.length, oracle: oracle(q, { kind: k.v }) }));
  c.sizes.forEach(z => out.chips.push({ q: q, key: "size:" + z.v, said: z.n, listed: E.list(st(Object.assign({}, s0, { size: z.v }))).rows.length, oracle: oracle(q, { size: z.v }) }));
  c.facts.forEach(f => {
    const mod = {}; mod[f.key] = f.v;
    out.chips.push({ q: q, key: f.key + ":" + f.v, said: f.n, listed: E.list(st(Object.assign({}, s0, mod))).rows.length, oracle: oracle(q, mod) });
  });
});

// unknown is never "no": the pages listed apart are exactly the ones silent on the chosen fact
out.unknown = [];
[["coffee", { sub: true }], ["clothing", { ship: "min" }], ["clothing", { size: "M" }], ["coffee", { size: "2 lb" }], ["", { ship: "free", browse: true }], ["dog", { sub: true }]].forEach(([q, mod]) => {
  const s = st(Object.assign({ q: q }, mod)), cur = E.list(s), m = E.match(q);
  const silent = r => { const p = cat[r.i]; return mod.sub ? !p.sb : mod.ship ? !p.sh : mod.size ? !(p.z && p.z.length) : false; };
  const listedSet = new Set(cur.rows.map(r => r.i)), unkSet = new Set(cur.unk.map(r => r.i));
  out.unknown.push({ q: q, mod: mod, unkAllSilent: cur.unk.every(silent),
    noSilentListed: cur.rows.every(r => !silent(r)),
    disjoint: [...listedSet].every(i => !unkSet.has(i)),
    everySilentInUnk: m.rows.filter(r => silent(r) && E.judge(r.i, Object.assign({}, s, mod.size ? {} : {})) !== 0).every(r => unkSet.has(r.i) || listedSet.has(r.i) === false) });
});
// members-only shipping is never free shipping
out.members = { free: [], min: [] };
["free", "min"].forEach(v => {
  const rows = E.list(st({ browse: true, ship: v })).rows;
  out.members[v] = rows.map(r => cat[r.i].sh).filter(sh => sh.members).length;
  out.members[v + "N"] = rows.length;
});
out.membersExist = cat.filter(p => p.sh && p.sh.members).length;

// suggestions, near matches, hash
out.suggest = {};
["cof", "old nav", "bambino", "shoe"].forEach(q => { out.suggest[q] = E.suggest(st({ q: q })).map(x => [x.type, x.label, x.sub]); });
out.nearest = {};
["espresso laptop", "zzyzx coffee", "espressoo"].forEach(q => { out.nearest[q] = E.nearest(q).map(r => [cat[r.i].n, r.hit, r.miss]); });
out.hash = {};
["q=coffee&sub=1&ship=min&size=2%20lb&kind=Coffee&store=Lavazza&coupon=1&sort=lo&all=1", "kind=Nope&ship=weird&q=tea&sort=zzz", "q=%E0%A4%A", "", "#q=a%26b"].forEach(h => {
  const s = E.decode(h);
  out.hash[h] = { state: s, again: E.encode(E.decode(E.encode(s))) === E.encode(s), encoded: E.encode(s) };
});
out.sizePrice = {};
{
  const s = st({ q: "midnight", size: "2 lb" });
  out.sizePrice.midnight = E.list(s).rows.map(r => [cat[r.i].n, E.shown(r.i, s).cents, cat[r.i].pc]);
  const s2 = st({ q: "airpods", size: "M" });
  out.sizePrice.airpods = E.list(s2).rows.length;
  const s3 = st({ q: "clothing", size: "M" });
  out.sizePrice.clothingMUnchanged = E.list(s3).rows.every(r => E.shown(r.i, s3).cents === cat[r.i].pc);
}
process.stdout.write(JSON.stringify(out));
