# Similar products: output contract

Every answer in `SKILL.md`'s *Similar products and their offers* mode follows
this file: the markdown below, in this order, backed by one JSON record of the
same facts. `deal_finder/similar_contract.py` checks the JSON (`validate`) and
prints the markdown (`render`); `tests/test_similar_contract.py` holds both to
this file.

## The answer, in this order

Write the shopper's answer with these headings and fixed labels. Angle brackets
are to fill in; leave nothing in them out, and write `unknown` or `not stated`
instead of guessing.

```markdown
## Similar products and their offers: <reference name> (<store>)

Checked <start> to <end> · <N> of <budget> pages read · <N> searches · took <time or not reported> · cost <cost or not reported>
Stopped because: <why the search stopped>

**Lowest shelf price:** <price> at <store>, <product>, <size> (<unit price, or not comparable: size not stated>), read on its page at <time>. This is the price.
- Lower but not counted: <product> at <store>, <price>: <why it is not counted>

**Lowest price per <unit> (both sizes printed):** <unit price> at <store>, <product>, <size>.

**If a printed code applies (not tried, may not work):** <price> at <store> with code <CODE>: "<page's own words>". This is not the price.

### What it was compared with

<reference name> at <store>: <price> for <size>. <link, or described by you, no page>

- <attribute>: <value> (<must have | may vary>; <from the page: "quote" | from you | assumed: why>)

### Similar products, most similar first

1. **<product>** at <store>: <price> for <size> (<unit price or not comparable: reason>). <Compared | Flagged: why | Excluded: why>.
   - Similar because: <reasons>
   - Not comparable: <reasons>
   - Offers seen: <kind> "<page's own words>" (<evidence state>, <no sign-up needed | gated: email, sms, first-order, subscription, member, ...>, <where>)
   - Checked <time>: <link> (found via <search words or page>)

### Pages that could not be read

- <store>: <what happened>. Check it yourself: <link>

### Unknowns

- <each thing no page stated: tax, shipping for one item, roast date, ...>

No code was tried and nothing was added to a cart. A shelf price is the price; codes, subscribe prices and sign-up offers never lower it. No affiliate links; the order is by similarity, not by commission.
```

Leave out the *Lower but not counted* line when there is none and the *Lowest
price per* line when fewer than two compared items have a unit price. When no
code qualifies, the code line reads `none.` and says why.

## Rules each part must meet

- **Shelf price.** The price the product's own page printed for the size and
  option shown, quoted (`shelf_price.quote` contains `amount`), with its
  evidence state (`deal_finder/evidence.py`): `observed-now` when read on that
  page during this run. A search-result snippet price is `unverified` and never
  compared.
- **Size and unit price.** `size` quotes the page (`quote`) and states that
  one size (`text`), or is `null`. A unit price (one unit for the whole answer:
  `oz`, `lb`, `g`, `kg`, `fl oz`, `ml`, `l` or `ct`) appears only when **both**
  the item's and the reference's sizes are printed on their pages; otherwise
  `unit_price` is exactly `not comparable: size not stated` (or `not
  comparable: <reason>` for different units or a page printing several sizes).
  Never guess a size. The number is shelf price ÷ printed size as
  `deal_finder/unit_price.py` computes it (2 decimals, 3 below 1.00, half up);
  the checker recomputes it. (The stored catalog's exact-size rule is separate
  and unchanged.)
- **Similarity.** `attributes_used` lists the quality attributes, each marked
  must-have or may-vary and sourced (`page` with a quote, `shopper`, or
  `assumed` with why). Each candidate's `checks` marks every attribute `same`,
  `differs` or `unknown` from its own page. A must-have that `differs` means
  **excluded**; one that is `unknown` means **flagged**. Every candidate has at
  least one *similar because* and one *not comparable* reason. Order: most
  `same` checks first, excluded last.
- **Offers.** Only what the store itself printed (`product page`, `site banner`
  or another `store page`), quoted, with `state` `retailer-stated` (or
  `unverified` for indexed text of a page that could not be read, `rejected`
  for a code whose printed window has passed) and `gate`: `none`, `email`,
  `sms`, `first-order`, `subscription`, `member`, `store-card`, `app` or
  `other`. A `code` must appear in its quote. Codes from coupon or deal sites
  are not listed.
- **Lowest shelf price.** The lowest shelf price among compared items (the
  reference counts) read on their own pages in the asked currency, exactly as
  printed. Every *flagged* item with a lower shelf price is named under
  `also_lower_not_counted` with why.
- **If a printed code applies.** Labelled exactly `not tried, may not work`.
  Uses only an ungated, store-printed code on a compared item whose discount is
  stated in numbers (percent or amount; a printed minimum spend must be met by
  one item); one code, never stacked; the lowest such price. A gated code is
  listed with its gate and never forms this line. When none qualifies,
  `if_code` is `null` and `if_code_none` says why.
- **Run.** `page_budget` at most 10; `pages_read` at most the budget and at
  least the distinct pages named; at least one search; candidates and blocked
  pages from at least two stores; start and end times; `took` and `cost` as the
  runtime reported them, or `not reported`.
- **Links.** Plain store links: no `utm_*`, `_gsid`, `gclid`, `fbclid`, `ref`,
  `tag`, `aff…` or other tracking or affiliate parameters.
- **Wording.** None of `DECISION_TABLE.md`'s banned words (`safe`,
  `guaranteed`, `best ever`, `works`, `ending soon`, `lowest ever`) or
  "best deal", "great deal", "hurry", "act now", "don't miss" in your own
  words. Page quotes stay as printed.

## JSON shape

A real answer, read on 2026-10-04 (UTC) with the page reader and a browser,
nothing added to a cart. The reference and the Brookshire's page came from one
web search; The Well, Honest Coffee and Intelligentsia were picked from the
repo's stored coffee pages and read again live. Prices may have changed since.
Unit prices are shelf price ÷ printed ounces from `deal_finder/unit_price.py`.

```json
{
  "contract": "similar-v1",
  "request": {"said": "I have this coffee bag: Counter Culture Big Trouble, 12 oz. Find similar ones and their coupons.", "region": "US", "currency": "USD"},
  "reference": {
    "id": "R", "from": "page", "name": "Big Trouble", "store": "Counter Culture Coffee",
    "url": "https://counterculturecoffee.com/collections/coffee/products/big-trouble",
    "checked_at": "2026-10-04T20:07:17Z",
    "shelf_price": {"amount": "19.50", "currency": "USD", "quote": "$19.50", "variant": "12 oz, One-Time Purchase", "state": "observed-now"},
    "size": {"text": "12 oz", "quote": "SIZE 12 oz"},
    "unit_price": {"amount": "1.63", "currency": "USD", "per": "oz"},
    "offers": [
      {"kind": "shipping-threshold", "quote": "Free shipping on $30 & up!", "where": "site banner", "state": "retailer-stated", "gate": "none", "min_spend": "30.00", "seen_at": "2026-10-04T20:07:17Z"},
      {"kind": "subscribe", "quote": "Subscribe + Save $2", "where": "product page", "state": "retailer-stated", "gate": "subscription", "seen_at": "2026-10-04T20:07:17Z"}
    ]
  },
  "attributes_used": [
    {"name": "whole bean", "value": "whole bean", "must_have": true, "from": "page", "quote": "Grind the whole beans immediately before brewing"},
    {"name": "origin printed", "value": "the page names where the coffee was grown", "must_have": true, "from": "assumed", "why": "'similar quality' read as specialty coffee, checked by the roaster printing the origin"},
    {"name": "roast level", "value": "medium dark", "must_have": false, "from": "page", "quote": "ROAST LEVEL medium dark roast"},
    {"name": "blend or single origin", "value": "blend", "must_have": false, "from": "page", "quote": "this medium-dark roast blend"},
    {"name": "bag size", "value": "12 oz", "must_have": false, "from": "page", "quote": "SIZE 12 oz"}
  ],
  "candidates": [
    {
      "id": "C1", "name": "Counter Culture Coffee Caramel, Nutty, Round Whole Bean Coffee Big Trouble - 12 Ounce", "store": "Brookshire's",
      "url": "https://brookshires.com/product/counter-culture-coffee-whole-bean-big-trouble-id-00663505002063",
      "found_via": "search: Counter Culture Coffee Big Trouble whole bean 12 oz",
      "checked_at": "2026-10-04T20:09:52Z",
      "status": "flagged",
      "status_reason": "in-store or curbside pickup price at a Brookshire's store that was not chosen; the page offers no shipping ('Delivery - Coming Soon!')",
      "shelf_price": {"amount": "12.99", "currency": "USD", "quote": "$12.99 was $15.99 $1.08/oz", "state": "observed-now"},
      "size": {"text": "12 oz", "quote": "Big Trouble - 12 Ounce"},
      "unit_price": {"amount": "1.08", "currency": "USD", "per": "oz"},
      "checks": {"whole bean": "same", "origin printed": "same", "roast level": "unknown", "blend or single origin": "same", "bag size": "same"},
      "similar_because": ["the same coffee: Counter Culture Big Trouble, whole bean, 12 oz", "blend parts printed: '50% COMPRONIL, HONDURAS 50% FINCA AURORA, NICARAGUA'"],
      "not_comparable": ["pickup or in-store only, at a store that was not chosen", "'was $15.99' has no dated history, so it is not shown as a saving", "roast level not printed on this page"],
      "offers": [
        {"kind": "sale", "quote": "Sales price valid from 09/21/2026 until 10/26/2026", "where": "product page", "state": "retailer-stated", "gate": "none", "conditions": "the $12.99 shelf price already includes it", "seen_at": "2026-10-04T20:09:52Z"}
      ]
    },
    {
      "id": "C2", "name": "Watershed", "store": "The Well Coffee Roasters",
      "url": "https://wellcoffeeroasters.com/products/watershed",
      "found_via": "the repo's stored coffee pages (demo/evidence/handcards), read again live",
      "checked_at": "2026-10-04T20:08:28Z",
      "status": "compared",
      "shelf_price": {"amount": "20.50", "currency": "USD", "quote": "One-time $20.50", "variant": "12oz, Whole Bean", "state": "observed-now"},
      "size": {"text": "12 oz", "quote": "Size 12oz"},
      "unit_price": {"amount": "1.71", "currency": "USD", "per": "oz"},
      "checks": {"whole bean": "same", "origin printed": "same", "roast level": "differs", "blend or single origin": "differs", "bag size": "same"},
      "similar_because": ["whole bean, 12 oz: 'Grind Whole Bean'", "origin printed: 'Region: Santa Rosa, Guatemala', 'Process: Washed'"],
      "not_comparable": ["light roast ('Roast Level: Light'), not medium dark", "single farm ('Farmer: John Schippers'), not a blend", "roast date not printed"],
      "offers": [
        {"kind": "signup", "quote": "Save 10% Off Your First Purchase. Sign up for a discount code towards your first purchase.", "where": "site banner", "state": "retailer-stated", "gate": "email", "conditions": "first purchase only; no code is printed on the page", "seen_at": "2026-10-04T20:08:28Z"},
        {"kind": "subscribe", "quote": "Subscribe & Save … Discounted price: $18.45 … Save up to 10%", "where": "product page", "state": "retailer-stated", "gate": "subscription", "seen_at": "2026-10-04T20:08:28Z"},
        {"kind": "shipping-threshold", "quote": "Free Shipping On All Orders $75+", "where": "site banner", "state": "retailer-stated", "gate": "none", "min_spend": "75.00", "seen_at": "2026-10-04T20:08:28Z"}
      ]
    },
    {
      "id": "C3", "name": "Midnight Axes", "store": "Honest Coffee Roasters",
      "url": "https://www.honest.coffee/shop-3Ooj8/p/nguvu-bcntn-ksj2y-dy3ra-jzxhp-9wphr",
      "found_via": "the repo's stored coffee pages (demo/evidence/handcards), read again live",
      "checked_at": "2026-10-04T20:08:08Z",
      "status": "flagged",
      "status_reason": "its page does not say whole bean or ground",
      "shelf_price": {"amount": "18.00", "currency": "USD", "quote": "One time purchase $18.00", "variant": "12oz", "state": "observed-now"},
      "size": {"text": "12 oz", "quote": "Size: 12oz"},
      "unit_price": {"amount": "1.50", "currency": "USD", "per": "oz"},
      "checks": {"whole bean": "unknown", "origin printed": "same", "roast level": "differs", "blend or single origin": "differs", "bag size": "same"},
      "similar_because": ["12 oz bag", "origin printed: 'Country: Nicaragua', 'Process: Washed'"],
      "not_comparable": ["whole bean or ground not stated", "dark roast ('our best foot forward into the dark roast game'), not medium dark", "single producer ('Producer: Finca Cantagallo'), not a blend", "shipping not stated"],
      "offers": [
        {"kind": "subscribe", "quote": "Subscribe Sale Price: $13.50 Original Price: $18.00", "where": "product page", "state": "retailer-stated", "gate": "subscription", "seen_at": "2026-10-04T20:08:08Z"}
      ]
    },
    {
      "id": "C4", "name": "Honduras La Tortuga Batian 7oz", "store": "Intelligentsia",
      "url": "https://www.intelligentsia.com/products/honduras-la-tortuga-batian-7oz",
      "found_via": "the repo's stored coffee pages (demo/evidence), read again live",
      "checked_at": "2026-10-04T20:11:57Z",
      "status": "compared",
      "shelf_price": {"amount": "25.00", "currency": "USD", "quote": "$25", "state": "observed-now"},
      "size": {"text": "7 oz", "quote": "HONDURAS LA TORTUGA BATIAN 7OZ"},
      "unit_price": {"amount": "3.57", "currency": "USD", "per": "oz"},
      "checks": {"whole bean": "same", "origin printed": "same", "roast level": "differs", "blend or single origin": "differs", "bag size": "differs"},
      "similar_because": ["whole bean: 'GRIND TYPE Whole Bean (WB)'", "origin printed: 'COUNTRY Honduras', 'PROCESSING METHOD Washed'"],
      "not_comparable": ["7 oz bag, not 12 oz: compare the price per oz", "bright roast ('ROAST LEVEL: BRIGHT'), not medium dark", "single origin, not a blend"],
      "offers": [
        {"kind": "shipping-threshold", "quote": "You’re $49 away from free shipping over $49.", "where": "product page", "state": "retailer-stated", "gate": "none", "min_spend": "49.00", "conditions": "text in the page's cart panel", "seen_at": "2026-10-04T20:11:57Z"}
      ]
    }
  ],
  "lowest": {
    "shelf": {
      "id": "R", "amount": "19.50", "currency": "USD",
      "also_lower_not_counted": [
        {"id": "C1", "why": "pickup or in-store price at a Brookshire's store that was not chosen; counts only if you can pick it up there"},
        {"id": "C3", "why": "its page does not say whole bean or ground"}
      ]
    },
    "unit": {"id": "R", "amount": "1.63", "per": "oz"},
    "if_code": null,
    "if_code_none": "No compared page printed a code anyone can use. The Well offers 10% off a first purchase only after an email sign-up and prints no code."
  },
  "blocked": [
    {"store": "ShopRite", "url": "https://www.shoprite.com/product/00663505002063", "what_happened": "the page reader got HTTP 403, and a browser got a Cloudflare 'Performing security verification' page"},
    {"store": "Lowes Foods", "url": "https://shop.lowesfoods.com/products/counter-culture-coffee-big-trouble-whole-bean-coffee-12-oz/115167", "what_happened": "the page reader got an empty page; a browser showed prices only for a pickup store the site picked itself"},
    {"store": "Whole Foods Market", "url": "https://www.wholefoodsmarket.com/grocery/product/big-trouble-b018csy6z6", "what_happened": "the page reader got no price, and a browser got 'Page Not Found'"}
  ],
  "run": {
    "searches": ["Counter Culture Coffee Big Trouble whole bean 12 oz"],
    "pages_read": 8, "page_budget": 10,
    "started_at": "2026-10-04T20:07:10Z", "finished_at": "2026-10-04T20:13:11Z",
    "took": "about 6 minutes, from the check times (the runtime did not report it)",
    "cost": "not reported by the runtime",
    "stopped_because": "the other search results were Instacart listings priced for a chosen store and a Singapore store, so 2 pages of the budget were left unused"
  },
  "unknowns": [
    "Tax: not shown on any page read.",
    "Shipping for one bag: not stated; one bag is under each printed free-shipping line (Counter Culture $30, Intelligentsia $49, The Well $75), and Honest Coffee prints no shipping text.",
    "Roast date of the bag you would get: no page read prints one; Counter Culture lists blend parts by roast-date range only.",
    "Whether the Brookshire's price differs by store: not stated; no store was chosen."
  ]
}
```

## Check an answer

With Python 3 and this repository:

```sh
scripts/deal-finder similar-check answer.json             # lists every broken rule, or ok
scripts/deal-finder similar-check answer.json --markdown  # prints the answer once it passes
```

Without Python, follow the template and rules above by hand; the mode never
depends on running code.
