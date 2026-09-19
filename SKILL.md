---
name: deal-finder
description: Find and compare a requested product and bounded substitutes using attributable current evidence, honest landed costs, and optional consent-gated anonymous-cart coupon checks. Use for one buy, wait, verify, or abstain purchase decision; not for checkout, account access, subscriptions, or continuous tracking.
---

# Deal Finder

Produce one defensible purchase decision. Evidence outranks deal volume.

## Hard boundaries

- Never log in, enter checkout, submit payment or personal data, mutate an account, reserve scarce inventory, negotiate, or buy anything.
- Never request a full address, credentials, payment data, government identifiers, or unrelated browsing history.
- Never claim a seller is safe or a price is guaranteed, best ever, or urgent without scope-matched evidence.
- Never count an untested coupon, delayed cash back, rebate, points, or gift card as money due today.
- V1 has no affiliate links. State that ranking is independent of commission.
- For subscriptions, financial or medical products, controlled goods, resale speculation, or negotiation, abstain without ranking.

## Workflow

1. Ask for the exact item or bounded need, region/currency, deadline, acceptable condition, and which attributes must stay fixed versus may vary. Ask what "local" or "similar" means rather than assuming.
2. Search at most 6 exact-item offers and 4 substitutes. Prefer fewer. A substitute qualifies only when every must-have is documented; state material differences beside savings and never imply lookalike equivalence.
3. Record each candidate's exact variant, quantity, condition, bundle, seller, fulfillment party, region, availability, source URL, absolute observation time, and evidence state.
4. Prefer merchant/manufacturer pages for current terms. Use third-party sources for discovery, history, and cross-checking. Blocked-page indexed text remains `unverified` and requires a manual check.
5. Assemble input using `README.md`'s schema and run `scripts/deal-finder evaluate <input.json>`. Without Jev, the runtime intentionally returns `verify`. With a server-side `TYPESAFE_API_KEY`, use `--live-jev`; never expose or log the key. A saved Jev response can be supplied with `--judgment`.
6. Present `buy`, `wait`, `verify`, or `abstain` exactly as defined in `DECISION_TABLE.md`. Put each caveat beside the claim it limits. In non-browsing mode, say live facts were not independently verified; one pasted offer cannot support buy or wait.

## Coupon testing

Coupon research is allowed without cart mutation. Testing in a cart is optional and requires the user's explicit yes.

1. Ask once: "May I test public coupon codes in a logged-out anonymous cart? I will stop before login or checkout, use no personal or payment data, reserve no scarce inventory, and restore an empty cart plus clean up the browser session. You can revoke this at any time."
2. Only after an actual yes, persist it with `scripts/deal-finder consent grant --file <consent.json> --session <session-id> --confirmed`. Never infer consent or add `--confirmed` without that yes.
3. Before every merchant run, create a run JSON and execute `scripts/deal-finder cart-check --consent <consent.json> --run <run.json>`. Proceed only when `allowed: true`.
4. Use no more than the declared budget (maximum 3 combinations), prioritizing published terms. Stop immediately on login, checkout, personal-data, payment, account, reservation, budget, rule, or cleanup boundaries.
5. Restore a visibly empty cart, clean the browser session, and record merchant, actions, budget used/declared, stop reason, and observed cleanup. Do not claim knowledge of merchant-side identifiers.
6. Revoke immediately on request with `scripts/deal-finder consent revoke --file <consent.json>`. Any denial or uncertainty means research-only verification.

## Output contract

Lead with the verdict and one next action. Show the winner and at most one decision-changing alternative. For every material claim include source, region, absolute timestamp, and one evidence state: `observed-now`, `applied-in-anonymous-cart`, `retailer-stated`, `third-party-historical`, `user-provided`, `unverified`, `rejected`, or `unknown`.

Rank known amount due today: item price minus immediate proven discount, plus shipping, mandatory fees, known tax, required membership/bundle cost, minus credit actually applied at checkout. Show unknowns or ranges. If ranges overlap or an unknown could flip the winner, return `verify` with exactly one check that would decide it.

For `wait`, name the history provider, item/marketplace coverage, region, and window plus an actionable recheck trigger. Never invent a future target or imply monitoring.
