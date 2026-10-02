# Incomplete Landed-Cost Behavior

Status: **rules draft for Captain review. Fixtures: `LC-001` … `LC-004` in
`FIXTURES.json`.**

Exact tax and some shipping costs often require a precise location or checkout
progression the skill must not pursue. Returning quickly with explicit unknowns
is safer than inventing a precise total — but the unknown must then control the
ranking, not decorate it.

## Rules

- Known landed cost = item price − immediate discount + shipping + mandatory
  fees + known tax + required membership/bundle cost − credit actually applied
  at checkout. Nothing else enters the ranked number. Unproven
  `checkout_credit` is disclosed with delayed value and is never subtracted.
- Tax is a known value or an explicit `Unknown`. Never infer a precise total
  from city or postal code alone when the merchant has not calculated it.
- Shipping is a known value, a range, or `Unknown`. A full address is never
  requested; a postal code is requested only when materially needed for
  shipping, tax, or local availability, and volunteered location is preferred.
- Eligibility-gated prices (member, student, first-order) are shown as
  retailer-stated with the condition attached. Eligibility is never assumed;
  private identifiers are never requested.
- Cash back, rebates, points, and gift cards are separate conditional value and
  never change the ranked winner unless they reduce the amount due at checkout.
- Subscription-only pricing is excluded from V1 even when the first payment is
  lower.
- No false precision: when unknown spans overlap such that the ranking could
  flip, the output shows the range overlap and the verdict follows
  `DECISION_TABLE.md` downgrade rules (`verify` unless robust).

## Fixture coverage

| Fixture | Unknown | Required behavior |
| --- | --- | --- |
| `LC-001` | Tax | Tax `Unknown`; no point ranking over overlap. |
| `LC-002` | Shipping | Shipping `Unknown`/range; no full address. |
| `LC-003` | Eligibility | Retailer-stated with condition; eligibility asked once or `verify`. |
| `LC-004` | Delayed value | Shown separately; ranked by amount due today. |
