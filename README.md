<p align="center">
  <a href="https://thewyattbrocato.github.io/ai-deal-finder/"><img src="docs/readme/banner.svg" width="880" alt="AI Deal Finder. Price, decision and coupon, only when the store page really showed it. Open the live tool."></a>
</p>

# AI Deal Finder

### **[Open the live tool: thewyattbrocato.github.io/ai-deal-finder →](https://thewyattbrocato.github.io/ai-deal-finder/)**

Nothing to download or install. It runs in your browser.

Deal Finder searches a set of store product pages that were opened and read
ahead of time. For each product it shows the shelf price, and a coupon code only
when that product's own page printed one. It never guesses a
price and never fills in what a page did not say.

<p align="center">
  <img src="docs/readme/tool-desktop-search.png" width="880" alt="Screenshot of the live tool's first view at desktop width: the page header, an empty search box with the cursor in it and the hint Results update as you type, and buttons for starting with a kind such as Kitchen, Clothing, Tech, Pantry and Home, each with its product count.">
</p>

## Use it in four steps

1. **Type what you want.** The search box is focused when the page opens.
   Results appear as you type, with no Search button. Type a product, a store or
   a kind, such as `coffee`, `Old Navy` or `sneaker`. Partial words work, and so
   do small typos: when a word matched only as a close spelling of a word in the
   checked pages, the page says so and names the spellings it used. As you type,
   suggestions list kinds, stores and products (with their shelf price); you can
   also start from a kind button or *Browse all checked products*. By default
   results are ordered by best word match; a sort control switches to price, low
   to high or high to low. Results are shown 24 at a time with a *Show more*
   button.
2. **Narrow it, if you want to.** *Refine results* is optional and appears above
   the results. Its chips (kind, a size the pages list, free shipping, subscribe,
   printed coupon) each show how many of the current results they would keep, and
   only chips that apply to your results are offered. If a chip would leave
   nothing, or no product matches, the page says so and offers *Drop* buttons
   that show what would be left, plus *Clear all choices*. Nothing is shown that
   doesn't fit, and nothing is guessed. Products whose page doesn't state a
   fact you narrowed by (for example size or shipping) are not counted in the
   results. A line such as "3 more products don't state size on the page" lists
   them separately behind *Show them*.
3. **Read the card.** Each card is compact: the product's photo when one was
   captured, its name, store, shelf price, the line *Price read from the store
   page* (with *Not compared with other stores*), when it was checked, any printed
   coupon with the page's own words, and what the page stated about size,
   shipping and subscribe, plus a *See at the store* link. *Full details* opens on
   the same card, with the savings line, the coupon's printed date window,
   conditions the page printed, *Confirm at checkout* items and the terms read.
4. **Go to the store and recheck.** The price was true when the page was
   checked. The card says to recheck at checkout, and the store's own page has
   the final say.

<p align="center">
  <img src="docs/readme/tool-desktop-result.png" width="880" alt="Screenshot of a search for waffle knit hoodie in the live tool: the Refine results chips, one result card for the UNTUCKit Waffle-Knit Hoodie Sweater at $128 with the page-printed code NOIRON shown as printed and not applied, and the opened Full details box with the page's printed date window and that today is inside it.">
</p>

<p align="center"><sub>Real, unedited capture of the live tool on 2026-10-03. The coupon window on that card ends 2026-10-04, so a later visit shows the card's own passed/not-passed line instead.</sub></p>

A result card shows the shelf price exactly as the store page printed it, and how
old the check is ("Checked today", or "Checked 2 days ago"). If the page printed a
coupon, the card quotes the page's own words and says the code was printed, not
applied, so the price never includes it. It also quotes the coupon's printed date
window and says whether today, in US Eastern time, is inside it or has passed, or
that the text states no clear window. Shipping that needs a membership is not
counted as free: the card says the check was not signed in. Whatever the page did
not show, such as tax or whether a code works, is listed on a *Confirm at
checkout* line in *Full details*.

On a phone the same page works at narrow width:

<p align="center">
  <img src="docs/readme/tool-phone.png" width="390" alt="Screenshot of the live tool at a 390 px phone width, with no sideways scrolling: the same waffle knit hoodie search with the compact card and its opened Full details.">
</p>

## What the evidence rules mean

- **A coupon is shown only when that product's own page printed it.** The card
  gives the code, the page, and the time it was seen. If the page printed none,
  the card says *No coupon on this page*.
- **A seen code is never a lower price.** The code is listed beside the price
  and marked *seen, not tried*. Nothing is added to a bag and no code is
  tested, so the price you see does not include it.
- **The shelf price stays the shelf price.** Products are ordered and compared
  by what the page showed, with no savings maths added. A *was* price appears
  only when the page marked one.
- **Unknown stays unknown.** If a page did not show size, shipping, tax or a
  subscribe price, the card says so instead of filling it in. A product that
  does not list the size you picked is hidden, not guessed.

<img src="docs/readme/coupon-vs-shelf.svg" width="880" alt="Diagram with a placeholder product name. Left: a product's own page shows a shelf price and may print a code. Middle: the tool ranks by the shelf price and lists the code as a coupon on this page, seen and not tried. Right: the rules. A code is listed only if the page printed it, a seen code is never a lower price, and with no code the card says no coupon on this page.">

The page covers only products that were checked and stored in this repo
(`demo/evidence/`).
It holds 244 products, each one stored read of that product's own page. The page
header's "244 products, 79 stores" counts 244 stored product pages and 79
distinct store names as the catalog labels them. Some of those labels are a
sub-brand or product line rather than a separate website, so the same site can
appear under more than one name. Counted by the web address of the product
pages instead, the products come from 60 distinct hosts (for example
`www.untuckit.com`), so 79 stores is a count of labels, not of websites. It is not a live search of the web: a product that is not
there cannot be found, and prices may have changed since the check. The page
is rebuilt offline from that stored evidence with `python3 demo/build.py`.

## Use it as an agent skill

For one evidence-backed `buy`, `wait`, `verify`, or `abstain` purchase decision,
`SKILL.md` is the operating contract. The Python runtime owns deterministic
validation, landed-cost arithmetic, consent gates, and optional Jev
composition. It does not browse, mutate carts, log in, or purchase.

The acceptance corpus is still authored draft evidence. Building the skill does
not mark any gate in `VALIDATION_RECORD.md` passed or establish effectiveness.

### Run

Python 3.11+ is the only local requirement.

```sh
python3 -m unittest discover -v
scripts/deal-finder --help
scripts/deal-finder evaluate evidence.json
```

`evaluate` defaults to the deterministic fail-closed path and returns `verify`
when no judgment is available. To execute the accepted Jev Choice/Score/Noul
layer, set the server-side `TYPESAFE_API_KEY` and add `--live-jev`. The pinned
model is `jev-1.13.0`. A 429/529 is retried with bounded backoff; outages degrade
to `verify`; 401 and 422 halt for configuration/developer review. Key-dependent
validation is listed in `KEYED_VALIDATION.md` and is not claimed by local tests.

### Evidence JSON

The top level is the `State` object in `JUDGMENT_ENGINE.md`: `request`,
`candidates`, `consent`, and `history`. Each candidate must include identity and
provenance fields plus deterministic cost inputs:

```json
{
  "request": {
    "item": "Exact product",
    "must_have_attributes": ["attribute"],
    "may_vary": ["color"],
    "region": "US",
    "currency": "USD",
    "mode": "browsing",
    "category": "general"
  },
  "candidates": [{
    "id": "C1",
    "variant": "exact variant",
    "quantity_terms": "1 unit",
    "condition": "new",
    "bundle": "none",
    "seller": "Merchant",
    "fulfilled_by": "Merchant",
    "region": "US",
    "source": "https://merchant.example/item",
    "observed_at": "2026-09-19T12:00:00Z",
    "evidence_state": "observed-now",
    "availability": "in-stock",
    "is_substitute": false,
    "exact_match": true,
    "item_price": "20.00",
    "immediate_discount": "0",
    "shipping": "0",
    "mandatory_fees": "0",
    "tax": null,
    "flags": []
  }],
  "consent": {"status": "absent"},
  "history": {}
}
```

Costs are decimal strings, `null` for unknown, or `{"min":"0","max":"5"}`
for a bounded range. Ranking follows `LANDED_COST.md`. `immediate_discount`
tied to a coupon is accepted only when coupon status is
`applied-in-anonymous-cart` or `shopper-confirmed-at-checkout`.

### Cart authorization

The CLI persists explicit consent, but performs no browser action. Consent
grant records the merchant and coupon attempt the grant covers. `cart-check`
requires a run JSON naming `merchant`, `attempt`, `session_id`, `browser_tools`,
`merchant_rules` (`allow` only), `logged_out`, `cleanup_guaranteed`,
`scarce_inventory`, `attempt_budget` (1-3), and `attempts_planned`. Consent for
one merchant or attempt cannot authorize a different merchant's cart test. Any
missing, false, ambiguous, or revoked prerequisite returns `research-only`.

## Policy and acceptance documents

- Frozen product vision: `VISION.md` (do not edit; SHA-256
  `22a01c3cee76da7092e1a912c1035c6da0c05b9b97b7884a56816fe47a642cae`).
- Author-approved baseline: `EVIDENCE.md`.
- Acceptance contract (reviewer isolation, severity, thresholds): `ACCEPTANCE.md`.
- Verdict meanings and downgrade rules: `DECISION_TABLE.md`.
- Prospective real-user study: `USER_VALIDATION_PLAN.md`.
- Consent and cart-action accountability: `CONSENT.md`.
- Discovery and substitute bounds: `DISCOVERY.md`.
- Unknown-cost behavior: `LANDED_COST.md`.
- Draft fixture corpus (53 cases, needs independent relabeling): `FIXTURES.json`.
- Judgment engine spec and Jev Choice/Score/Noul binding: `JUDGMENT_ENGINE.md`.
- Gate-by-gate evidence record (all gates not run/blocked): `VALIDATION_RECORD.md`.
- Key-dependent Jev validation still required: `KEYED_VALIDATION.md`.
- Build assumptions and captain decision batch: `ASSUMPTIONS.md`.
- Real-browser check of the engine against live-observed pages: `LIVE_VERIFICATION.md`.
