# Deal Finder presentation cut, 2026-10-03

Cut from `origin/main` commit `8b45c3d7a962819ae716c3f0a1daa91a68971aa4`
("docs(readme): refresh for the live tool (#24)"). This release note plus two
factual count corrections in ACCEPTANCE.md and ASSUMPTIONS.md are the only
changes on the final-cut branch: no code, tests, catalog or generated-page edits.

> **This file describes the cut of 2026-10-03 at commit `8b45c3d`, not the
> page as it is now.** The page and catalog have changed since. The counts in
> "What this version contains" are that cut's, kept as a historical record; the
> current counts are in "Current state" below.
>
> Merged since that cut (from `git log 8b45c3d..origin/main`):
>
> - #25 docs: record the presentation cut and correct corpus counts
> - #26 docs(release): correct scope of final-cut branch changes
> - #27 feat(page): search-first Deal Finder (instant search, live-count refinements, compact cards)
> - #28 fix(page): scrolling the page closes the suggestion list that covers the top results
> - #29 docs(readme): refresh screenshots and text for the search-first page; spell out what each count means
> - #30 fix(page): hoodies, t-shirt and dog/phone/sneakers/bedding searches find what the word names
> - #31 feat(catalog): 37 checked products from 9 new merchants (Wellness, Tea, Drinks, Grooming, Office)
> - #32 fix(page): chip clicks no longer throw in real browsers, focus lands somewhere real, phone taps don't raise the keyboard, sweat pants finds sweatpants
> - #33 feat(evidence): re-read 67 of the oldest product pages; earlier observations kept as dated history
> - #34 fix(catalog): store label is the merchant for the page's host, stated pre-orders say so, 23 kind misfiles moved, Apple short line says free delivery
> - #35 fix(page): neutral price line on every card, phone Size list fits, empty box when nothing fits, favicon, coffee-only band, exact-price search
> - #36 feat(evidence): re-read the 140 oldest product pages; changed price and shipping lines recorded, earlier observations kept as dated history
> - #37 feat(catalog): 54 checked products from 19 new merchants (coffee and espresso makers, pet food, perfume, sunglasses, candles, plants, watches, books, stationery, travel, yoga)

Live site: https://thewyattbrocato.github.io/ai-deal-finder/

## What this version contains (the 2026-10-03 cut at `8b45c3d`)

Counts below were computed by commands run against this commit (see the PR
body for the commands and their output).

- 244 products on the live page, each a stored read of the product's own page.
- 79 stores, as the page header says: distinct store names (the catalog's
  merchant label) across those 244 products. Some labels are a sub-brand or
  product line, so this is a count of labels, not of websites.
- 60 distinct page hosts: distinct web addresses (host names) of the 244
  product pages. This is why it is lower than 79: 12 hosts appear under more
  than one store name (for example `counterculturecoffee.com` under three).
- 19 products with a coupon code printed on the product's own page.
- 164 products with a known shipping condition the page stated.
- 24 products with a known subscribe condition the page stated.
- 279 tests at commit e502a4b, all passing (`python3 -m unittest discover -s tests`).
- 53 fixture cases in `FIXTURES.json`.

## Current state (2026-10-03, commit `ee4d953`)

Computed from the built page `demo/index.html`, the tests and `FIXTURES.json`
at that commit. The commands are in the README section on what the numbers
mean; the live page header reads "335 products, 88 stores".

- 335 products on the page, each a stored read of the product's own page.
- 88 stores: distinct store names (the catalog's merchant label), as the page
  header counts them. A count of labels, not of websites.
- 88 distinct page hosts: distinct host names of the 335 product pages. It now
  equals the store count because #34 made the store label the merchant for the
  page's host.
- 19 products with a coupon code printed on the product's own page.
- 229 products with a known shipping condition the page stated.
- 42 products with a known subscribe condition the page stated.
- 28 products with known sizes.
- 17 kinds.
- 363 tests, all passing on Python 3.9.6 (`python3 -m unittest discover -s tests`).
- 53 fixture cases in `FIXTURES.json`.

The page no longer prints a verdict on a card: each card says *Price read from
the store page* and *Not compared with other stores*.

## Safety behaviors

- A coupon is shown only if the product's own page printed it. It is never
  applied; the shelf price stays the price.
- The shelf price is the price. A code that was seen but not tried never
  lowers it.
- Evidence that is stale, or dated in the future, is refused when a freshness
  window is stated.
- Urgency text ("only N left", countdowns) is labelled as not evidence and is
  never counted.
- A was-price the page does not support is labelled, not subtracted.
- Anything the page did not state stays unknown; nothing is filled in.

## Deliberately unknown

- Tax, everywhere. No page shows it before checkout.
- Shipping, wherever the product's page states none.
- Sizes the pages do not state.
- Whether any code that was seen actually works.
- A per-unit price across sizes. The page computes none; non-exact sizes are
  not compared today.

## Waits on the captain (open, nothing decided here)

- The V1 decision batch D1-D6 in `ASSUMPTIONS.md`.
- The per-unit versus bundle pricing call.
- The skill consent question.
