// For every product on the page: type its exact name, each distinct word of its name, and each adjacent
// word pair, through the page's own engine, and list the product wherever it is not in the result list.
// Also lists every query that returns nothing although the same words typed in another spacing do.
// usage: node findability_driver.js page.html [engine.js]   (engine.js overrides the page's own engine)
const fs = require("fs");
const vm = require("vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const cat = JSON.parse(/<script type="application\/json" id="catalog">([\s\S]*?)<\/script>/.exec(html)[1]);
const src = process.argv[3] ? fs.readFileSync(process.argv[3], "utf8") : /<script>\n(\/\* Deal Finder search engine[\s\S]*?)<\/script>/.exec(html)[1];
const ctx = vm.createContext({});
vm.runInContext(src, ctx);
const E = ctx.DealFinderEngine.create(cat);
const st = q => Object.assign(E.blank(), { q: q });
const found = (q, i) => E.list(st(q)).rows.some(r => r.i === i);
const count = q => E.list(st(q)).rows.length;
const words = s => (s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[™®©]/g, "").match(/[a-z0-9]+/g) || []);
const out = { products: cat.length, misses: [], zeroDespiteOtherSpacing: [] };
const seenQ = {};
cat.forEach((p, i) => {
  const ws = words(p.n), qs = [["name", p.n]];
  const distinct = Array.from(new Set(ws)).filter(w => w.length > 1);
  distinct.forEach(w => qs.push(["word", w]));
  for (let j = 0; j + 1 < ws.length; j++) if (ws[j].length > 1 && ws[j + 1].length > 1) qs.push(["pair", ws[j] + " " + ws[j + 1]]);
  qs.forEach(([kind, q]) => {
    if (!found(q, i)) out.misses.push({ product: p.n, kind: kind, q: q });
    if (!seenQ[q]) {
      seenQ[q] = true;
      if (!count(q)) {
        // the same words typed in a different spacing: joined, or split at each place
        const alts = [q.replace(/\s+/g, "")];
        const w = q.split(/\s+/);
        if (w.length === 1) for (let k = 2; k <= q.length - 2; k++) alts.push(q.slice(0, k) + " " + q.slice(k));
        const hit = alts.filter(a => a !== q && count(a));
        if (hit.length) out.zeroDespiteOtherSpacing.push({ q: q, alsoWorks: hit.slice(0, 3) });
      }
    }
  });
});
process.stdout.write(JSON.stringify(out, null, 1));
