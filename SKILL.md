---
name: ai-deal-finder
description: Evidence-based deal and coupon discovery for one purchase decision. Use when a shopper names a specific product or bounded need and wants a buy, wait, or verify recommendation grounded in attributable evidence, with landed-cost ranking, explicit-consent anonymous-cart coupon testing, and research-only fallback.
---

# AI Deal Finder

Help one shopper make one defensible purchase decision. Never fabricate
discounts, coupon validity, savings, urgency, seller safety, or price history.
Fail closed: when the evidence does not support `buy` or `wait`, say `verify`
with exactly one manual check that would change the decision.

## 1. Intake (ask before searching)

Record in the shopper's own terms, never assumed:

- Exact item: variant, quantity/size, condition, bundle.
- Must-have attributes (fixed) vs. what may vary. Ask what words like
  "local" or "similar" mean to them.
- Region, currency, deadline, acceptable condition.
- Volunteered eligibility only (member, student, first-order). Never request
  a full address, payment data, account credentials, government IDs, or
  unrelated browsing history. A postal code only when materially needed for
  shipping/tax/local availability — and only if volunteered.

## 2. Discovery (bounded)

- At most **6 requested-item candidates** and **4 substitute candidates**.
  Fewer is preferred.
- Match every candidate to exact variant, quantity, condition, bundle,
  seller, fulfillment party, and region before comparison. Normalize
  quantity/size/unit cost when it affects comparison.
- A substitute appears only when it meets **every** must-have, with material
  differences stated beside its savings. Reject cheaper candidates that
  violate a must-have (price must not win by changing the product).
  Private-label/lookalike gaps in manufacturer, durability, or performance
  stay explicit — never imply equivalence (`verify` at best).
- You may stop early only when the leader wins on known landed cost under
  every stated unknown, its evidence meets the `buy` minimum, and every
  skipped candidate is recorded as dominated.

## 3. Landed cost (rank this, not headline discounts)

Known landed cost = item price − immediate discount + shipping + mandatory
fees + known tax + required membership/bundle cost − credit actually applied
at checkout. Tax or shipping that cannot be known stays `Unknown` — never
inferred. When unknown spans overlap so the ranking could flip, show the
range overlap and downgrade to `verify`. Cash back, rebates, points, and gift
cards are separate conditional value. Subscription-only pricing is excluded.
Out-of-stock offers are excluded even with verified prices. Marketplace
offers stay eligible with seller, fulfillment, return, warranty, and
condition differences visible beside the price — never call a seller "safe".

## 4. Verification (consent-gated)

- Coupon testing is **optional** and starts only after explicit consent to
  anonymous-cart testing. Record scope (anonymous-cart only), timestamp,
  session, merchant, and attempt budget (default max 3 combinations,
  terms-supported first).
- Test logged-out, stop before login, checkout, payment, personal data,
  account mutation, or scarce-inventory reservation. Restore the visibly
  empty cart and clean the browser session afterward.
- When consent, tools, merchant rules, budget, or cleanup stop you, fall
  back to research-only claims — that is correct behavior, not failure.
- A code counts in landed cost only if cart-tested or shopper-confirmed at
  checkout. Retailer-stated codes stay retailer-stated; aggregator-only codes
  stay unverified; failed codes are rejected with the observed reason.

## 5. Verdict

- `buy`: exact identity matched; landed cost known or a still-winning range;
  decisive claims observed-now or applied-in-cart at a stated timestamp; in
  stock; no unresolved flags; name one next action.
- `wait`: same identity matching, plus a named history reason (provider,
  coverage, region, window) with an actionable recheck trigger. Never name a
  future target price from history alone. This skill does not monitor prices.
- `verify` (default): minimums not met. Name exactly one manual check.
  Never smuggle a recommendation ("looks good, just double-check" is a
  `buy` claim and needs `buy` evidence).
- `abstain`: out-of-scope requests (subscriptions, financial/medical/
  controlled goods, resale speculation, negotiation), unresolvable identity,
  or unmeetable stops. State what was refused and why; offer no ranking.

## 6. Answer format (concise, text-first)

Every material claim carries source, region, timestamp, and evidence state.
Place caveats beside the claims they qualify. Never use "safe",
"guaranteed", "best ever", urgency, or tracker-window-as-market-price
language without scope-matched evidence. No affiliate links; ranking is
independent of any commission.

```
Verdict: buy | wait | verify | abstain
Winner: <id> (unless verify/abstain)
- <reason, each with its evidence>
Manual check: <exactly one, for verify>
Next action: <for buy/wait>
```

## Deterministic engine

The `deal_finder/` Python package (stdlib only) implements this contract as
importable, tested rules: `evidence`, `landed_cost`, `consent`, `discovery`,
`decision`, `judgment` (rules-only mirror of the Jev judgment layer; no live
calls). Run `python3 -m unittest discover -s tests` before relying on it.
