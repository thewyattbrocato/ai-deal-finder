# V1 Build Assumptions (for captain return review)

V1 was built from the frozen domain material without stalling, per the
launch brief. Every assumption below is recorded for review; none of them
required blocking the build.

## What V1 is

- Deterministic rules engine (`deal_finder/`, stdlib-only Python) + public
  skill (`SKILL.md`) + unittest suite (`tests/`). No network, no
  model calls, no credentials, no affiliate links, no tracking.
- Judgment layer ships as a **rules-only mirror** of `JUDGMENT_ENGINE.md`
  (`deal_finder/judgment.py`): same composition order, deterministic fit/
  strength gates, service-unavailable always falls back to `verify`.
  No live Jev integration, no API key handling.

## Assumptions made with best judgment

1. **Repo shape**: V1 is a Python skill package + `SKILL.md` at root. No
   prior code existed (planning-only main), so module boundaries follow the
   doc boundaries (`evidence`, `landed_cost`, `consent`, `discovery`,
   `decision`, `judgment`).
2. **No browser automation in V1**: coupon cart-testing is modeled as
   consent/budget/stop records and action logs, not executed. Real cart
   execution needs tool bindings that do not exist here yet. Update
   (captain's call, 2026-10-04): the cart path is now refused outright until
   the consent link is redesigned; see `CONSENT.md`.
3. **Timestamps are strings** (ISO-8601) with no staleness threshold in
   code; `observation_stale` is an input flag. A volatility-based
   threshold is a captain call (see below).
4. **Attempt budget default max 3** — "small declared attempt budget" was
   unspecified; 3 is a starting point, tunable per merchant.
5. **Substitute fit minimum >= 2** (the "proposed" value in
   `JUDGMENT_ENGINE.md`) is baked in as the code default; final value
   needs independently labeled data.
6. **Currency is a label only**; no FX conversion in V1 (cross-region
   comparison without conversion rules would be false precision).
7. **Tests pin behavior but pass no gates**: self-authored tests cannot
   satisfy reviewer-isolation; `VALIDATION_RECORD.md` stays NOT RUN.
   Untouched, as required.
8. **VISION.md untouched** (verified frozen). README updated to describe V1;
   planning docs otherwise unchanged.

## Needs-decision batch (genuine captain calls, none stalled the build)

- D1. Staleness threshold: what observation age forces `verify` per
  category volatility?
- D2. Attempt budget default (3) and per-merchant tuning policy.
- D3. Substitute-fit minimum (2) and evidence auto-accept threshold (0.8)
  pending independent corpus labeling.
- D4. TypeSafe account/key ownership and server-side key handling for
  live-Jev validation (V1 needs nothing; validation phase needs exactly
  one server-side `TYPESAFE_API_KEY`).
- D5. Public-visibility calls beyond the already-public repo (none made).
- D6. Whether `USER_VALIDATION_PLAN.md` sessions start now that a working
  V1 exists.

## Follow-ups (out of scope, not built)

- Live Jev integration + threshold/weight tuning on the relabeled corpus.
- Browser cart-test execution bindings.
- Price monitoring / recheck triggers beyond naming them.
- Any monetization, affiliate handling, or ranking-independence audit.
