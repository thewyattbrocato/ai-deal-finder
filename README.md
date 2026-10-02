# AI Deal Finder (V1)

Evidence-based deal and coupon discovery skill: one purchase decision backed
by attributable evidence, landed-cost ranking, explicit-consent
anonymous-cart-only coupon verification, and research-only fallback.

- Public skill: `SKILL.md`.
- Deterministic rules engine (stdlib only): `deal_finder/` —
  `evidence`, `landed_cost`, `consent`, `discovery`, `decision`,
  `judgment` (rules-only mirror of the Jev judgment layer; no live calls).
- Tests: `python3 -m unittest discover -s tests` (53 tests, stdlib only).
- Build assumptions + captain decision batch: `ASSUMPTIONS.md`.
- Acceptance policy: `VISION.md`.
- Author-approved baseline: `EVIDENCE.md`.
- Acceptance contract (reviewer isolation, severity, thresholds): `ACCEPTANCE.md`.
- Verdict meanings and downgrade rules: `DECISION_TABLE.md`.
- Prospective real-user study: `USER_VALIDATION_PLAN.md`.
- Consent and cart-action accountability: `CONSENT.md`.
- Discovery and substitute bounds: `DISCOVERY.md`.
- Unknown-cost behavior: `LANDED_COST.md`.
- Draft fixture corpus (21 cases, needs independent relabeling): `FIXTURES.json`.
- Judgment engine spec (Jev Choice/Score/Noul binding; no live integration): `JUDGMENT_ENGINE.md`.
- Gate-by-gate evidence record (all gates not run/blocked): `VALIDATION_RECORD.md`.
