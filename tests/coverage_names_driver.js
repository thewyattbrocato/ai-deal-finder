// Runs the page's own search engine (no DOM) over the page's embedded catalog for
// the product names and kinds given as JSON on argv[3]; prints what each search lists.
const fs = require("fs");
const vm = require("vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const cat = JSON.parse(/<script type="application\/json" id="catalog">([\s\S]*?)<\/script>/.exec(html)[1]);
const src = /<script>\n(\/\* Deal Finder search engine[\s\S]*?)<\/script>/.exec(html)[1];
const ctx = vm.createContext({});
vm.runInContext(src, ctx);
const E = ctx.DealFinderEngine.create(cat);
const st = o => Object.assign(E.blank(), o || {});
const out = { names: {}, kinds: {} };
JSON.parse(process.argv[3]).names.forEach(n => {
  out.names[n] = E.list(st({ q: n })).rows.map(r => cat[r.i].n);
});
JSON.parse(process.argv[3]).kinds.forEach(k => {
  const typed = E.list(st({ q: k })), opened = E.list(st({ browse: true, kind: k }));
  out.kinds[k] = { typed: typed.rows.map(r => cat[r.i].n), opened: opened.rows.map(r => cat[r.i].n) };
});
console.log(JSON.stringify(out));
