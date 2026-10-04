# Recommendation Semantics (decision table)

Status: **draft for Captain review. Frozen on approval; the Decision gate scores
output against this exact table.**

`buy`, `wait`, and `verify` sound decisive, so this table fixes what each verdict
promises, the minimum evidence each requires, what forces a downgrade, and when
to abstain instead. Independent reviewers apply this table without seeing
implementation internals. The Jev judgment-layer binding of this table —
verdict Choice, eligibility/ranking Scores, condition Nouls, composition order,
and confidence gates — is specified in `JUDGMENT_ENGINE.md`; this table remains
the semantic authority and the Decision gate scores output against both.

## Minimum evidence per verdict

| Verdict | Minimum evidence (all required) |
| --- | --- |
| `buy` | Exact variant, quantity, condition, bundle, seller, fulfillment party, and region matched; winning landed cost known or a range that still wins under every stated unknown (see `LANDED_COST.md`); every price-determining claim observed now at a stated timestamp (cart-applied results are not accepted; `CONSENT.md`); coupon counted only if the shopper confirmed it at checkout; in stock; no unresolved seller flags; one next action named. |
| `wait` | Same identity matching as `buy`; current options documented with evidence states; a history or stock reason grounded in a named provider, coverage, region, and window (fixture `HIST-001`); no deadline or stock pressure forcing now; an actionable recheck trigger named. `wait` never names a future target price from history alone when the price cannot be monitored or the threshold grounded in current actionable evidence (fixture `HIST-002`). V1 does not monitor prices. |
| `verify` | Default fallback. Used whenever `buy`/`wait` minimums are not met, with exactly one manual check that would change the decision, named beside the uncertainty. |
| `abstain` | Reserved for scope and safety stops, not uncertainty: excluded categories (subscriptions, financial/medical/controlled goods, resale speculation, negotiation), unresolvable identity (cannot establish what the item is), or a stop condition that even `verify` guidance cannot safely bound. Abstention states what was refused and why, and offers no ranking. |

## Downgrade triggers (any one forces `buy` → `verify`, `wait` → `verify`)

- Any price-determining component is `Unknown` and the ranking is not robust to it.
- The winner depends on an untested code (`retailer-stated` or `unverified`).
- A seller/fulfillment flag is unresolved, or the seller cannot be identified.
- The primary merchant page was blocked; only indexed text supports the claim.
- Sources conflict and nothing observed resolves the conflict (cart-level proof is not accepted).
- Non-browsing mode with fewer than two comparable offers, or a single pasted
  offer with no comparative evidence (fixture `NB-001`).
- Observation is stale relative to price/stock volatility and cannot be rechecked.
- Pasted or indexed content shows tampering/injection signs or cannot be
  corroborated to the exact item and cart.

## Abstention vs. `verify`

- Uncertainty about the market → `verify` (one check that would resolve it).
- Out-of-scope request or unmeetable stop condition → `abstain` (no ranking).
- `verify` must never smuggle a recommendation ("looks good, just double-check"
  is a `buy` claim and needs `buy` evidence).

## Language bans

Without scope-matched evidence: "safe", "guaranteed", "best ever", "works",
urgency ("ending soon" unless source states the date and now makes it true),
and any claim that converts a tracker window into a universal market price.
