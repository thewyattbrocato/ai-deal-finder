# Similar products: output contract

Every answer in `SKILL.md`'s *Similar products and their offers* mode follows
this file: the markdown below, in this order, backed by one JSON record of the
same facts (contract `similar-v2`). `deal_finder/similar_contract.py` checks the
JSON (`validate`) and prints the markdown (`render`);
`tests/test_similar_contract.py` holds both to this file.

## The answer, in this order

Angle brackets are to fill in; write `unknown` or `not stated` instead of
guessing. A line in [square brackets] appears only when the rules below say so.

```markdown
## Similar products and their offers: <reference name> (<store>)

Checked <start> to <end> · <N> of <budget> pages read · <N> searches · took <time or not reported> · cost <cost or not reported>
Stopped because: <why the search stopped>

[**Your product:** <out of stock on its page: "<quote>" | no price could be read on its page | ...>; it is not counted below.]
[**Similar products:** none qualified; every product found was excluded, each listed below with why.]

**Lowest shelf price for <your size>:** <price> at <store>, <product> (<yours | the same product | a similar product>), <unit price>, read on its page at <time>. This is the price[: <amount> (<percent>) below yours at <your price>].
- Lower but not counted: <product> at <store>, <price>: <why it is not counted>

**Lowest price per <unit>:** <unit price> at <store>, <product> (<yours | the same product | a similar product>), <size> (<shelf price>)[; yours is <your unit price> per <unit>].
- Lower per <unit> but not counted: <product> at <store>, <unit price>: <why it is not counted>

**If a printed code applies (not tried, may not work):** <price> at <store> with code <CODE>: "<page's own words>". This is not the price.

### What it was compared with

<reference name> at <store>: <price> for <size> (<unit price>). <In stock ("quote") | Out of stock ("quote") | Stock not stated> on its page. <link, or described by you, no page>

- <attribute>: <value> (<must have | may vary>; <from the page: "quote" | from you | assumed: why>)

### Similar products, most similar first

1. **<product>** at <store>: <price> for <size> (<unit price or not comparable: reason>). [Same product at another store.] <Compared | Flagged: why | Excluded: why>.
   - Similar because: <reasons>
   - Not comparable: <reasons>
   - Offers seen: <kind> "<page's own words>" (<evidence state>, <no sign-up needed | gated: email, sms, first-order, subscription, member, ...>, <where>)
   - Checked <time>, <in stock ("quote") | out of stock ("quote") | stock not stated>: <link> (found via <search words or page>)

### Pages that could not be read

- <store>: <what happened>. Check it yourself: <link>

### Unknowns

- <each thing no page stated: tax, shipping for one item, roast date, ...>

No code was tried and nothing was added to a cart. A shelf price is the price; codes, subscribe prices and sign-up offers never lower it. No affiliate links; the order is by similarity, not by commission.
```

When `unit` is `none`, sizes and unit prices are left out of every line. A
price not read in the page's own text carries `(from a page reader's summary,
not confirmed in the page's own text)` beside it. Leave out a *Lower …* line
when there is none and the *Lowest price per* line when no counted item but
yours has a unit price and nothing cheaper per unit was left out. When no code
qualifies, the code line reads `none.` and says why. In your own words, name
products, not ids.

## Rules each part must meet

- **How each fact was read (`read`).** Every shelf price, size, stock state
  and offer says how it was read: `page-text` (the product page's own text: a
  browser's text after scripts run, or raw HTML from `curl`; where they differ,
  the browser's visible text), `reader-summary` (a page-reader tool's summary,
  such as WebFetch: it paraphrases and can be wrong), `listing-page` (a store's
  search or category page, not the product's own page) or `search-snippet` (a
  search result's text: offers only, with `state` `unverified`; a snippet price
  never enters the answer). Your product's size may also be `shopper` (they told
  you). Only `page-text` counts: an item whose price or stock was read another
  way is flagged, never compared, and never names a lowest line.
- **Times.** Copy each time from `date -u +%Y-%m-%dT%H:%M:%SZ`, run before the
  first search (`run.started_at`), right after each page read (`checked_at`, and
  `seen_at` for that page's offers) and when the answer is written
  (`run.finished_at`). Never estimate a time. The checker refuses a time outside
  the run and a `finished_at` later than its own clock; inside the run it cannot
  tell a copied time from a made-up one.
- **Shelf price.** The price the product's own page printed for the size and
  option shown, quoted (`quote` contains `amount`), `state` `observed-now` when
  read during this run. A "from" price or a range (`from $18.00`, `$17.00 -
  $99.00`) is not a shelf price: open the option you compare (clicking a size
  or option is fine; adding to cart is not) and quote its price, or flag the
  item. A price for pickup or delivery at a store the site picked, not the
  shopper, is flagged.
- **Stock (`availability`).** `in-stock` or `out-of-stock` with the page's
  words (`Add to Cart`, `Sold out`) in `quote`, or `not-stated`. Out of stock in
  the page's own text means excluded; out of stock only from a summary means
  flagged until a page-text read confirms it.
- **Unit (`unit`).** One unit for the whole answer: `oz`, `lb`, `g`, `kg`,
  `fl oz`, `ml`, `l` or `ct` (US coffee `oz`; tea bags, brush heads, pods
  `ct`), or `none` when the kind is sold one item at a time (shoes, earbuds):
  then every `size` is `null` and no `unit_price` is written.
- **Size and unit price.** `size` quotes the page (`quote`), states one size
  (`text`) and says how it was read, or is `null`; never guess a size. A size is
  written with oz, lb, g, kg, fl oz, ml, l or a count word (ct, count, each, ea,
  pack, heads, sachets, tea bags, bags, pods, capsules, cans, cartridges,
  filters, refills, pieces, pcs); a printed multipack counts its items
  (`12.5 oz (Case of 12)` is 12 x 12.5 oz). When an item's size is printed, its
  `unit_price` is its shelf price ÷ that size in the answer's unit, as
  `deal_finder/unit_price.py` computes it: 2 decimals, **3 decimals when under
  1.00** (`0.767`), half up. Otherwise `unit_price` is left out or `not
  comparable: <reason>` (`not comparable: size not stated`, different units,
  another currency). (The stored catalog's exact-size rule is separate and
  unchanged.)
- **Similarity.** `attributes_used` lists the quality attributes, each marked
  must-have or may-vary and sourced (`page` with a quote, `shopper`, or
  `assumed` with why). Each candidate's `checks` marks every attribute `same`,
  `differs`, `unknown` (**the page does not say**) or `not-read` (**you did not
  read that part of the page**). A must-have that `differs` means
  **excluded**; one that is `unknown` or `not-read` means **flagged**. Every
  candidate has at least one *similar because* and one *not comparable* reason.
  `same_product: true` marks the same product (same brand and name; size or
  seller may differ) at another store. Order: the same product first, then most
  `same` checks; excluded last within each.
- **Offers.** Only what the store itself printed and showed (`product page`,
  `site banner` or another `store page`; text hidden in the HTML is not
  printed), quoted, with `kind`: `code`, `sale` (already in the shelf price),
  `subscribe`, `autoship` (the pet stores' word for subscribe), `signup`,
  `shipping-threshold`, `bundle` (buy more, save more), `bulk` (a case or
  multi-bag price) or `other` (anything else, in the page's words); `state`
  `retailer-stated` (or `unverified` for indexed text of a page that could not
  be read, `rejected` for a code whose printed window has passed); `gate`:
  `none`, `email`, `sms`, `first-order`, `subscription`, `member`,
  `store-card`, `app` or `other`; and `read`. A `code` must appear in its quote;
  give its printed discount as `"discount": {"percent": "20"}` or `{"amount":
  "5.00"}` and a printed minimum as `min_spend`. Codes from coupon or deal sites
  are not listed.
- **Your product first.** When your product is not counted (out of stock, no
  price in its page's text, another currency, described with no page), the
  answer says so before the lowest lines.
- **Lowest shelf price.** Counted items are your product and `compared`
  candidates, priced and in stock in the page's own text, in the asked
  currency. The line compares only counted items **the same size as yours**
  (within 1%; with `unit` `none`, every item); a different size competes on the
  per-unit line. If your product's size is not printed, `shelf` is `null` and
  the answer asks the shopper for it. Less than 2% below your price reads `no
  meaningful saving found`, with both prices. When every counted price comes
  from one store, the line says only that store could be counted.
  `shelf_lower_not_counted` names each flagged or excluded item of your size (or
  of unknown size) priced below the line, with why.
- **Lowest price per unit.** The lowest unit price among counted items whose
  size is printed in the page's text; `null` when only yours has one and nothing
  cheaper per unit was left out. `unit_lower_not_counted` names each item not
  counted with a lower unit price, with why. The 2% rule applies against your
  unit price.
- **If a printed code applies.** `if_code` is `{"id", "code", "amount",
  "label": "not tried, may not work"}`: one ungated code the store printed on a
  counted item, read in the page's own text, with its discount stated in numbers
  (a printed minimum spend must be met by one item); never stacked; the lowest
  such price. A gated code is listed with its gate and never forms this line.
  When none qualifies, `if_code` is `null` and `if_code_none` says why.
- **Run.** `page_budget` at most 10. `pages_read` counts each distinct link
  opened, blocked ones and 404s included (at most the budget, at least the
  distinct pages named); re-reading a page already counted, to confirm it in a
  browser or raw HTML, is free. At least one search; candidates and blocked
  pages from at least two stores; start and end times; `took` and `cost` as the
  runtime reported them, or `not reported`.
- **Links.** Plain store links taken from search results or the store's own
  menu, never built or guessed: no `utm_*`, `_gsid`, `gclid`, `fbclid`, `ref`,
  `tag`, `aff…` or other tracking or affiliate parameters.
- **Wording.** None of `DECISION_TABLE.md`'s banned words (`safe`,
  `guaranteed`, `best ever`, `works`, `ending soon`, `lowest ever`) or
  "best deal", "great deal", "hurry", "act now", "don't miss" in your own
  words. Page quotes stay as printed.

## JSON shape

A real answer, read on 2026-10-04 (UTC) with `curl` (raw HTML) and a browser
(page text), every time copied from `date -u`, nothing added to a cart. The
three Kimbo pages were search results from an earlier run that day, read again
live. Prices may have changed since. It shows the same product at two other
stores, a cheaper excluded bag named under *Lower but not counted*, unit prices
under $1.00, a printed code with its discount, and `not-read` beside `same`.

```json
{
  "contract": "similar-v2",
  "request": {"said": "I buy Lavazza Super Crema whole bean, 2.2 lb, medium roast: https://www.lavazzausa.com/en/whole-bean-coffee/super-crema.4202. Find the same or a similar bag, the coupons each store prints and the lowest price.", "region": "US", "currency": "USD"},
  "unit": "oz",
  "reference": {
    "id": "R", "from": "page", "name": "Super Crema Whole Bean", "store": "Lavazza USA",
    "url": "https://www.lavazzausa.com/en/whole-bean-coffee/super-crema.4202",
    "checked_at": "2026-10-04T20:59:09Z",
    "shelf_price": {"amount": "26.99", "currency": "USD", "quote": "$26.99", "variant": "2.2 lb (each size has its own link)", "state": "observed-now", "read": "page-text"},
    "size": {"text": "2.2 lb", "quote": "Net quantity 2.2 lb", "read": "page-text"},
    "unit_price": {"amount": "0.767", "currency": "USD", "per": "oz"},
    "availability": {"state": "in-stock", "quote": "ADD TO CART", "read": "page-text"},
    "offers": [
      {"kind": "code", "code": "AS20", "quote": "AUTUMN SAVINGS EVENT: 20% OFF Coffee* with code AS20", "where": "site banner", "state": "retailer-stated", "gate": "none", "read": "page-text", "discount": {"percent": "20"}, "conditions": "the asterisk's terms are not printed on the page, so which coffees and sizes it covers is not stated", "seen_at": "2026-10-04T20:59:09Z"},
      {"kind": "other", "quote": "Extra Savings on Orders $49+", "where": "site banner", "state": "retailer-stated", "gate": "none", "read": "page-text", "min_spend": "49.00", "conditions": "the banner prints no amount; one bag is under $49", "seen_at": "2026-10-04T20:59:09Z"},
      {"kind": "subscribe", "quote": "SUBSCRIBE AND SAVE 25%", "where": "product page", "state": "retailer-stated", "gate": "subscription", "read": "page-text", "seen_at": "2026-10-04T20:59:09Z"},
      {"kind": "shipping-threshold", "quote": "Free delivery on orders over $50", "where": "site banner", "state": "retailer-stated", "gate": "none", "read": "page-text", "min_spend": "50.00", "seen_at": "2026-10-04T20:59:09Z"}
    ]
  },
  "attributes_used": [
    {"name": "whole bean", "value": "whole bean", "must_have": true, "from": "page", "quote": "Super Crema Whole Bean"},
    {"name": "roast level", "value": "medium", "must_have": true, "from": "shopper"},
    {"name": "blend", "value": "Arabica and Robusta", "must_have": false, "from": "page", "quote": "Blend Composition Arabica and Robusta"},
    {"name": "bag size", "value": "2.2 lb", "must_have": false, "from": "page", "quote": "Net quantity 2.2 lb"}
  ],
  "candidates": [
    {
      "id": "C1", "name": "Lavazza Super Crema Espresso - Whole Bean - 2.2 lb", "store": "Seattle Coffee Gear",
      "url": "https://www.seattlecoffeegear.com/products/lavazza-super-crema-espresso-whole-bean-2-2-lb",
      "found_via": "search: Lavazza Super Crema whole bean 2.2 lb",
      "checked_at": "2026-10-04T21:03:22Z",
      "same_product": true,
      "status": "compared",
      "shelf_price": {"amount": "36.29", "currency": "USD", "quote": "One Time Purchase $36.29", "variant": "one-time purchase", "state": "observed-now", "read": "page-text"},
      "size": {"text": "2.2 lb", "quote": "Product Size: 2.2 pounds", "read": "page-text"},
      "unit_price": {"amount": "1.03", "currency": "USD", "per": "oz"},
      "availability": {"state": "in-stock", "quote": "Add to Cart", "read": "page-text"},
      "checks": {"whole bean": "same", "roast level": "same", "blend": "same", "bag size": "same"},
      "similar_because": ["the same coffee: 'Lavazza Super Crema Espresso - Whole Bean - 2.2 lb'", "'Roast Level: Medium', 'combines washed and unwashed Arabica and washed Robusta'"],
      "not_comparable": ["costs more than the same bag at Lavazza's own store ($36.29, yours $26.99)", "its delivery estimate is for a ZIP the site picked ('Ship to: 37211 (Change)')"],
      "offers": [
        {"kind": "subscribe", "quote": "Subscribe Save 5% $36.29 $34.48", "where": "product page", "state": "retailer-stated", "gate": "subscription", "read": "page-text", "seen_at": "2026-10-04T21:00:09Z"},
        {"kind": "shipping-threshold", "quote": "Free Shipping On Orders $49+", "where": "product page", "state": "retailer-stated", "gate": "none", "read": "page-text", "min_spend": "49.00", "seen_at": "2026-10-04T21:00:09Z"}
      ]
    },
    {
      "id": "C2", "name": "Lavazza Super Crema Whole Bean Espresso 2.2 lb.", "store": "WebstaurantStore",
      "url": "https://www.webstaurantstore.com/lavazza-super-crema-whole-bean-espresso-2-2-lb/999LVECRMAW.html",
      "found_via": "search: Lavazza Super Crema whole bean 2.2 lb",
      "checked_at": "2026-10-04T21:00:30Z",
      "same_product": true,
      "status": "compared",
      "shelf_price": {"amount": "33.49", "currency": "USD", "quote": "Only $33.49/Each$15.22/Pound", "variant": "Each (one bag)", "state": "observed-now", "read": "page-text"},
      "size": {"text": "2.2 lb", "quote": "Package Size 2.2 lb.", "read": "page-text"},
      "unit_price": {"amount": "0.951", "currency": "USD", "per": "oz"},
      "availability": {"state": "in-stock", "quote": "Add to Cart", "read": "page-text"},
      "checks": {"whole bean": "same", "roast level": "same", "blend": "not-read", "bag size": "same"},
      "similar_because": ["the same coffee: 'Lavazza Super Crema Whole Bean Espresso 2.2 lb.'", "'Roast Level Medium', 'Style Whole Bean'"],
      "not_comparable": ["costs more than the same bag at Lavazza's own store ($33.49, yours $26.99)", "free shipping needs a paid WebstaurantPlus membership", "the blend: I did not read that part of the page"],
      "offers": [
        {"kind": "autoship", "quote": "Auto Reorder Get 25% off shipping every time this item ships automatically.", "where": "product page", "state": "retailer-stated", "gate": "subscription", "read": "page-text", "conditions": "25% off shipping, not off the price", "seen_at": "2026-10-04T21:00:30Z"},
        {"kind": "bulk", "quote": "6/Case $168.49 $28.08/Each", "where": "product page", "state": "retailer-stated", "gate": "none", "read": "page-text", "conditions": "six bags at once", "seen_at": "2026-10-04T21:00:30Z"},
        {"kind": "other", "quote": "Ships free with", "where": "product page", "state": "retailer-stated", "gate": "member", "read": "page-text", "conditions": "the word after it is the WebstaurantPlus logo, a picture: free shipping needs that paid membership", "seen_at": "2026-10-04T21:00:30Z"}
      ]
    },
    {
      "id": "C3", "name": "Carraro Globo Verde", "store": "Whole Latte Love",
      "url": "https://www.wholelattelove.com/products/carraro-globo-verde?variant=32786321408054",
      "found_via": "the store's own link under 'Recommended Alternatives' on its Segafredo page (search: Segafredo Espresso Casa whole bean 2.2 lb)",
      "checked_at": "2026-10-04T21:01:54Z",
      "status": "compared",
      "shelf_price": {"amount": "23.80", "currency": "USD", "quote": "Sale price $23.80 Regular price $28.00", "state": "observed-now", "read": "page-text"},
      "size": {"text": "2.2 lb", "quote": "Package Size 2.2 lb", "read": "page-text"},
      "unit_price": {"amount": "0.676", "currency": "USD", "per": "oz"},
      "availability": {"state": "in-stock", "quote": "ADD TO CART", "read": "page-text"},
      "checks": {"whole bean": "same", "roast level": "same", "blend": "same", "bag size": "same"},
      "similar_because": ["whole bean, medium roast: 'Coffee Type Whole Bean', 'Roast Profile Medium'", "an Italian Arabica and Robusta blend: 'a 50/50 blend of four Arabica qualities and three Robusta qualities'"],
      "not_comparable": ["a different brand and blend (Caffe Carraro), not Lavazza Super Crema", "'Regular price $28.00' has no dated history, so no saving from it is claimed", "shipping for one bag: not on the parts of the page read"],
      "offers": [
        {"kind": "sale", "quote": "Sale price $23.80 Regular price $28.00", "where": "product page", "state": "retailer-stated", "gate": "none", "read": "page-text", "conditions": "already in the $23.80 shelf price", "seen_at": "2026-10-04T21:01:54Z"}
      ]
    },
    {
      "id": "C4", "name": "Kimbo - Crema Intensa Whole Bean Coffee Bag 2.2lb (1kg)", "store": "Alma Gourmet",
      "url": "https://almagourmet.com/products/kimbo-crema-intensa-whole-bean-coffee-2-2lb-bag",
      "found_via": "a search result from an earlier run the same day (Lavazza Super Crema alternatives), read again live",
      "checked_at": "2026-10-04T20:59:44Z",
      "status": "compared",
      "shelf_price": {"amount": "26.95", "currency": "USD", "quote": "$26.95 2.2lb (1kg)", "variant": "one bag", "state": "observed-now", "read": "page-text"},
      "size": {"text": "2.2 lb", "quote": "Whole Bean Coffee Bag 2.2lb (1kg)", "read": "page-text"},
      "unit_price": {"amount": "0.766", "currency": "USD", "per": "oz"},
      "availability": {"state": "in-stock", "quote": "Add to Cart", "read": "page-text"},
      "checks": {"whole bean": "same", "roast level": "same", "blend": "same", "bag size": "same"},
      "similar_because": ["whole bean, 2.2 lb: 'Whole Bean Coffee Bag 2.2lb (1kg)'", "'Kimbo Crema Intensa is a medium roast', 'blends the best of Arabica and Robusta beans'"],
      "not_comparable": ["a different brand and blend (Kimbo), not Lavazza Super Crema", "Seattle Coffee Gear's page calls the same Kimbo coffee 'Roast Level: Dark'"],
      "offers": [
        {"kind": "bulk", "quote": "$159.00 Case of 6 - 2.2lb (1kg) x 6", "where": "product page", "state": "retailer-stated", "gate": "none", "read": "page-text", "conditions": "six bags at once", "seen_at": "2026-10-04T20:59:44Z"},
        {"kind": "shipping-threshold", "quote": "FREE SHIPPING on orders above $99", "where": "site banner", "state": "retailer-stated", "gate": "none", "read": "page-text", "min_spend": "99.00", "seen_at": "2026-10-04T20:59:44Z"}
      ]
    },
    {
      "id": "C5", "name": "Kimbo Crema Intesa Whole Coffee Beans (1kg / 2.2lb)", "store": "Home Coffee Solutions",
      "url": "https://www.homecoffeesolutions.com/products/kimbo-crema-intesa-whole-coffee-beans-1kg-2-2lb",
      "found_via": "a search result from an earlier run the same day, read again live (the link went to the same product on www.homecoffeesolutions.com)",
      "checked_at": "2026-10-04T21:01:04Z",
      "status": "excluded",
      "status_reason": "priced in Canadian dollars (never converted), 'Sold out', and 'ROAST: Medium Dark Roast'",
      "shelf_price": {"amount": "27.98", "currency": "CAD", "quote": "$27.98 CAD $29.99 CAD", "state": "observed-now", "read": "page-text"},
      "size": {"text": "1 kg", "quote": "FORMAT: 1kg / 2.2lb Bag of Whole Bean Coffee", "read": "page-text"},
      "unit_price": "not comparable: priced in CAD, never converted",
      "availability": {"state": "out-of-stock", "quote": "Sold out", "read": "page-text"},
      "checks": {"whole bean": "same", "roast level": "differs", "blend": "same", "bag size": "same"},
      "similar_because": ["Kimbo Crema Intensa, whole bean, 1 kg: 'FORMAT: 1kg / 2.2lb Bag of Whole Bean Coffee'", "'Blended Arabica & Robusta'"],
      "not_comparable": ["a Canadian store, priced in CAD", "'ROAST: Medium Dark Roast', not medium", "'Sold out'"],
      "offers": [
        {"kind": "shipping-threshold", "quote": "Ships Free With Orders Over $60.00 CAD", "where": "site banner", "state": "retailer-stated", "gate": "none", "read": "page-text", "seen_at": "2026-10-04T21:01:04Z"}
      ]
    },
    {
      "id": "C6", "name": "Kimbo Espresso Crema Intensa - 2.2 Lb", "store": "Seattle Coffee Gear",
      "url": "https://www.seattlecoffeegear.com/products/kimbo-espresso-crema-intensa-2-2-lb",
      "found_via": "a search result from an earlier run the same day, read again live",
      "checked_at": "2026-10-04T21:02:26Z",
      "status": "excluded",
      "status_reason": "its page says 'Roast Level: Dark', not medium",
      "shelf_price": {"amount": "23.59", "currency": "USD", "quote": "$23.59", "state": "observed-now", "read": "page-text"},
      "size": {"text": "2.2 lb", "quote": "Product Size: 2.2 pounds", "read": "page-text"},
      "unit_price": {"amount": "0.670", "currency": "USD", "per": "oz"},
      "availability": {"state": "in-stock", "quote": "Add to Cart", "read": "page-text"},
      "checks": {"whole bean": "same", "roast level": "differs", "blend": "not-read", "bag size": "same"},
      "similar_because": ["Kimbo Crema Intensa, whole bean, 2.2 lb: 'Coffee Type: Whole Bean Product Size: 2.2 pounds'"],
      "not_comparable": ["'QUICK SPECS: Roast Level: Dark', not medium (Alma Gourmet's page calls the same coffee 'a medium roast')", "the blend: I did not read that part of the page"],
      "offers": [
        {"kind": "shipping-threshold", "quote": "Free Shipping On Orders $49+", "where": "product page", "state": "retailer-stated", "gate": "none", "read": "page-text", "min_spend": "49.00", "seen_at": "2026-10-04T21:02:26Z"}
      ]
    }
  ],
  "lowest": {
    "shelf": {"id": "C3", "amount": "23.80", "currency": "USD"},
    "shelf_lower_not_counted": [
      {"id": "C6", "why": "its page says 'Roast Level: Dark' where you asked for medium; Alma Gourmet's page calls the same coffee a medium roast"}
    ],
    "unit": {"id": "C3", "amount": "0.676", "per": "oz"},
    "unit_lower_not_counted": [
      {"id": "C6", "why": "its page says 'Roast Level: Dark' where you asked for medium"}
    ],
    "if_code": {"id": "R", "code": "AS20", "amount": "21.59", "label": "not tried, may not work"}
  },
  "blocked": [
    {"store": "Walmart", "url": "https://www.walmart.com/ip/338351355", "what_happened": "the link went to a 'Robot or human? Activate and hold the button to confirm that you're human.' page; its search-result price was not used"},
    {"store": "Whole Latte Love", "url": "https://www.wholelattelove.com/products/segafredo-zanetti-massimo-whole-bean", "what_happened": "the page says 'It looks like you've found one of our old product listings!' and prints no price"}
  ],
  "run": {
    "searches": ["Lavazza Super Crema whole bean 2.2 lb", "Segafredo Espresso Casa whole bean 2.2 lb"],
    "pages_read": 9, "page_budget": 10,
    "started_at": "2026-10-04T20:58:32Z", "finished_at": "2026-10-04T21:03:40Z",
    "took": "about 5 minutes by date -u (the runtime did not report it)",
    "cost": "not reported by the runtime",
    "stopped_because": "a lower price for the same size and roast was read at a second store; 1 page of the budget was left unused"
  },
  "unknowns": [
    "Tax: not shown on any page read.",
    "Shipping for one bag: one bag is under each printed free-shipping line (Lavazza $50, Seattle Coffee Gear $49, Alma Gourmet $99); Whole Latte Love's shipping was not on the parts read.",
    "Whether AS20 covers this bag: the banner's asterisk terms are not printed on the page.",
    "Seattle Coffee Gear's raw HTML holds a hidden 'Save 10% With Code: ITALY10' block that its page did not show, so it is not listed as an offer.",
    "Roast date of the bag you would get: no page read prints one."
  ]
}
```

## Check an answer

With Python 3 and the checker (this repository, or the small checkout in
`README.md`'s *Install and use*), from the skill's folder:

```sh
scripts/deal-finder similar-check answer.json             # lists every broken rule, or ok
scripts/deal-finder similar-check answer.json --markdown  # prints the answer once it passes
```

Without them nothing checks the answer: follow every rule above by hand. The
mode never depends on running code, but an unchecked answer can carry a mistake
the checker would have caught.
