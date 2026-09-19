# AI Deal Finder

An agent skill for one evidence-backed `buy`, `wait`, `verify`, or `abstain`
purchase decision. `SKILL.md` is the operating contract; the Python runtime owns
deterministic validation, landed-cost arithmetic, consent gates, and optional Jev
composition. It does not browse, mutate carts, log in, or purchase.

The acceptance corpus is still authored draft evidence. Building the skill does
not mark any gate in `VALIDATION_RECORD.md` passed or establish effectiveness.

## Run

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

## Evidence JSON

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
for a bounded range. `delayed_value` is disclosed but never enters ranking.
`immediate_discount` tied to a coupon is accepted only when coupon status is
`applied-in-anonymous-cart` or `shopper-confirmed-at-checkout`.

## Cart authorization

The CLI persists explicit consent, but performs no browser action. `cart-check`
requires a run JSON naming `merchant`, `session_id`, `browser_tools`,
`merchant_rules` (`allow` only), `logged_out`, `cleanup_guaranteed`,
`scarce_inventory`, `attempt_budget` (1-3), and `attempts_planned`. Any missing,
false, ambiguous, or revoked prerequisite returns `research-only`.

- Frozen product vision: `VISION.md` (do not edit; SHA-256
  `8ff9483d1c343490d9ab6ee752957ca7ef894853102f101557fed4157b8d8484`).
- Author-approved baseline: `EVIDENCE.md`.
- Acceptance contract (reviewer isolation, severity, thresholds): `ACCEPTANCE.md`.
- Verdict meanings and downgrade rules: `DECISION_TABLE.md`.
- Prospective real-user study: `USER_VALIDATION_PLAN.md`.
- Consent and cart-action accountability: `CONSENT.md`.
- Discovery and substitute bounds: `DISCOVERY.md`.
- Unknown-cost behavior: `LANDED_COST.md`.
- Draft fixture corpus (21 cases, needs independent relabeling): `FIXTURES.json`.
- Judgment engine spec and Jev Choice/Score/Noul binding: `JUDGMENT_ENGINE.md`.
- Gate-by-gate evidence record (all gates not run/blocked): `VALIDATION_RECORD.md`.
- Key-dependent Jev validation still required: `KEYED_VALIDATION.md`.
