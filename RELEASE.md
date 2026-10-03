# Deal Finder presentation cut, 2026-10-03

Cut from `origin/main` commit `8b45c3d7a962819ae716c3f0a1daa91a68971aa4`
("docs(readme): refresh for the live tool (#24)"). This release note plus two
factual count corrections in ACCEPTANCE.md and ASSUMPTIONS.md are the only
changes on the final-cut branch: no code, tests, catalog or generated-page edits.

Live site: https://thewyattbrocato.github.io/ai-deal-finder/

## What this version contains

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
