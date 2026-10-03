// Compound-word rule on a small made-up catalog (test fixture only, never shown on the page):
// the joined or split reading adds products, it never removes one the typed words match.
const fs = require("fs");
const vm = require("vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const src = process.argv[3] ? fs.readFileSync(process.argv[3], "utf8") : /<script>\n(\/\* Deal Finder search engine[\s\S]*?)<\/script>/.exec(html)[1];
const ctx = vm.createContext({});
vm.runInContext(src, ctx);
const P = n => ({ n: n, m: "Fixture", k: "Fixture", pc: 100, pl: "$1.00" });
const cat = [P("Himalayan Green Tea, 12 oz"), P("Sparkling Water 12oz Can"), P("Sweatpants Fleece"), P("Sweat Band Pants Set"),
  P("Extra Virgin Olive Oil"), P("Olive Branch Oil Lamp"), P("Plain Mug")];
const E = ctx.DealFinderEngine.create(cat);
const rows = q => E.list(Object.assign(E.blank(), { q: q })).rows.map(r => cat[r.i].n);
const out = {};
["12 oz", "12oz", "green tea 12 oz", "tea 12 oz", "sweat pants", "sweatpants", "oliveoil", "olive oil", "tea 12oz", "oz"].forEach(q => { out[q] = rows(q); });
process.stdout.write(JSON.stringify(out));
