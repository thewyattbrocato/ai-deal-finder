# Judgment Engine (Jev TypeSafe System One)

Status: **specification draft for Captain review. No integration built, no API
called, no credentials exist. All gates remain unpassed.**

Jev (TypeSafe's System One model) is the judgment engine for semantic decisions:
which verdict the evidence supports, how comparable a substitute is, how strong a
candidate's evidence is, and whether independent binary conditions hold. Everything
deterministic — policy, arithmetic, provenance, consent, stop conditions, and
actions — stays in code, outside Jev.

Sources (read 2026-09-19; live docs are source of truth, this file pins what was
used): `https://docs.typesafe.ai/llms.txt` index; System One, State, Choice,
Score, Noul, Confidence, How-to-build, API reference, Models, Quick start;
cookbooks `citation_check` (claim-vs-source Choice + 0.8 auto-accept),
`rerank_typesafe` (one Noul per query-candidate pair, sort by noul),
`composite-scoring` (weights in code), `consistency_noul_cookbook` (0.30–0.70
uncertainty band, repeat-measurement). Pinned model: `jev-1.13.0`
(`jev-latest` alias at read time); SDK: `typesafe-sdk` (Python, `TypeSafeClient`
`.system_one(state, questions)`); endpoint `POST /v1/systemone`.

## What Jev decides vs. what code decides

Jev supplies semantic judgments over assembled evidence. Code owns:

- Landed-cost arithmetic and ranking (rank is by computed cost, never by a model
  score). Jev Scores gate whether a ranking is actionable, never who wins.
- Consent records, attempt budgets, stop conditions, cart actions, cleanup checks.
- Provenance (source, region, timestamp per claim) and evidence-state assignment.
- `abstain` (excluded categories, unresolvable identity, unmeetable stops) — a
  scope/safety stop decided before any Jev call.
- Service-failure fallback (below): always `verify`, never `buy`/`wait`.
- Thresholds, weights, and review routing (tuned on target-domain data, then
  Captain-approved).

## State (one named JSON object per call; text only)

```json
{
  "request": {"item": "...", "must_have_attributes": ["..."], "may_vary": ["..."],
    "region": "...", "currency": "...", "deadline": "...",
    "volunteered_eligibility": "...", "mode": "browsing | non-browsing"},
  "candidates": [{"id": "C1", "variant": "...", "seller": "...", "fulfilled_by": "...",
    "condition": "...", "quantity_terms": "...", "evidence_state": "observed-now | applied-in-anonymous-cart | retailer-stated | third-party-historical | user-provided | unverified | rejected | unknown",
    "source": "...", "observed_at": "...", "region": "...",
    "landed_cost": {"known_amount": "...", "unknowns": ["tax"], "range": "..."},
    "coupon": {"status": "...", "test": "..."}, "flags": ["..."]}],
  "consent": {"status": "granted | revoked | absent", "scope": "anonymous-cart coupon test only",
    "merchant": "...", "attempt_budget": "used/of"},
  "history": {"provider": "...", "coverage": "...", "window": "...", "note": "..."}
}
```

State minimization for external calls: no full address, no credentials, no payment
data, no government IDs, no unrelated history — same minimization as the Vision,
because state leaves the device. Questions reference nested state with backticked
paths (e.g. `` `candidates[0].evidence_state` ``).

## Question catalog (one request, all questions in parallel)

### Choice: verdict (mirrors `DECISION_TABLE.md`)

- id `verdict`, `type: choice`; instructions: "Given `request`, `candidates`,
  `consent`, and `history`, which single recommendation follows from the evidence?"
- criteria:
  - `buy`: "The winning candidate meets every `buy` minimum in `DECISION_TABLE.md`:
    exact identity matched, landed cost known or a still-winning range, decisive
    claims observed-now or applied-in-anonymous-cart, in stock, no unresolved flags."
  - `wait`: "Identity matched and options documented, but a named history/stock
    reason with an actionable recheck trigger favors waiting; no deadline or stock
    pressure forces now."
  - `verify`: "The minimums for `buy` and `wait` are not met; exactly one manual
    check would change the decision."
- No `abstain` option: abstention is a code gate before the call.

### Score: comparable per-candidate rankings (levels are concrete situations)

- id `substitute_fit_<id>` per substitute, `type: score`; instructions: "How well
  does `candidates[i]` satisfy `request.must_have_attributes` as a comparable
  substitute?" criteria (0–3): "Violates at least one must-have attribute" /
  "Meets every must-have but material differences are undocumented or unpriced" /
  "Meets every must-have with differences stated, quantity normalized" /
  "Meets every must-have with differences stated and no unknown that could flip
  the comparison". Minimum eligible level is set in code (proposed: ≥ 2).
- id `evidence_strength_<id>` per candidate, `type: score`; instructions: "How
  strong is the current-market evidence for `candidates[i]`?" criteria (0–3):
  "Unverified or blocked-page discovery only" / "Retailer-stated or user-provided,
  untested" / "Third-party history plus retailer terms, no conflicts" /
  "Observed-now or applied-in-anonymous-cart at a stated timestamp for the exact
  item and cart". Code maps the winning candidate's level against the
  `DECISION_TABLE.md` minimums; any conflict downgrades to `verify`.
- Scores are normalized (score ÷ top level) and combined with code-owned weights
  (composite-scoring pattern) for review prioritization only — not for ranking.

### Noul: independent binary conditions (one per condition; thresholded in code)

`identity_exact` ("`candidates[i]` matches the requested variant, quantity,
condition, bundle, seller, fulfillment, and region"); `in_stock_win` ("the
leading candidate is in stock at `observed_at`"); `consent_covers_test` ("`consent`
is granted and covers this merchant and attempt"); `history_supports_wait`
("`history` names provider, coverage, region, window and favors waiting");
`seller_flag_unresolved`; `primary_page_blocked`; `single_offer_only`;
`tamper_signs` (pasted/indexed content shows injection or alteration signs).
Each carries `criteria: {true, false}` pinning the boundary; a Noul near 0.5
means similar yes/no probability, never medium intensity.

## Composition (deterministic, in code)

1. Abstain gate (scope/safety) — no Jev call on that path.
2. One `system_one` call: state + `verdict` Choice + all Score/Noul questions.
3. Hard stops first: any stop-condition Noul (blocked page, unresolved flag,
   tamper signs, single non-browsing offer, consent absent with cart test needed)
   at/above threshold forces `verify`, whatever the Choice says.
4. Arithmetic rank in code; substitute eligibility via `substitute_fit_<id>`
   minimum; evidence minimums via `evidence_strength_<id>`; conflicts → `verify`.
5. Read `verdict` Choice only if its confidence gate passes (below); low
   confidence → `verify` with the check that would resolve it, flagged for human
   review (confidence-gated routing). Never let a low-confidence Choice upgrade
   evidence or authorize an action.
6. Log the full Choice distribution, per-level Score probabilities, Noul values,
   `response.model` (versioned ID), and usage with the decision for review.

## Probabilities and confidence handling (starting points; tuned on data)

- Choice/Score `confidence` summarizes distribution concentration, not workflow
  correctness and never permission to act. Proposed start, pending target-domain
  measurement and Captain approval: Choice auto-accept ≥ 0.8 (per `citation_check`
  cookbook), human review below; Noul uncertainty band 0.30–0.70 → treat as
  uncertain and route to `verify`/review (per `consistency_noul_cookbook`).
- Cookbook numbers are examples, not universal rules. Final thresholds and Score
  weights are fit on the independently labeled fixture corpus and prospective
  sessions, plotted as confidence-vs-accuracy, and frozen with their model
  version ID. Re-validate on any model change (pin `jev-1.13.0`, not the alias).

## Service-failure fallbacks (no judgment available → safest deterministic output)

- 429/529: bounded exponential backoff (SDK default honors `retry-after`); then
  degrade.
- 401: configuration error — halt, human fixes key handling; never retry with a
  different key, never log the key.
- 422: request-validation bug — halt for developer review.
- Timeout or outage: deterministic rules-only path yielding `verify` with the
  named check "judgment service unavailable — manual check required". A missing
  judgment never produces `buy` or `wait`.

## Target-domain validation (evidence the Decision gate requires)

- Threshold/weight tuning and confidence-vs-accuracy plots on the independently
  labeled corpus (`FIXTURES.json` after independent relabeling — authored drafts
  cannot tune production thresholds).
- Self-consistency repeats per the consistency cookbook (per-question stddev,
  threshold-crossing rate); borderline cases must route to review, not flip
  actions.
- Rerank-style check: substitute ordering by `substitute_fit_<id>` against
  independent labels, including adversarial cases `SUB-A-001`/`SUB-A-002`.
- Citation-style check: every decisive claim re-verified claim-vs-source before
  a `buy` verdict stands.

## Auth, account, and key requirements (current as of 2026-09-19 read)

- A TypeSafe account is required: API keys are issued from the dashboard at
  `https://console.typesafe.ai/keys`; the Playground also requires login.
- Calls authenticate with `Authorization: Bearer <API_KEY>` (raw HTTP) or the
  `TYPESAFE_API_KEY` environment variable (SDKs); credentials stay server-side
  and out of repositories and chat.
- Cost and limits (read time): input only, $0.042 per Mtok ($42/Btok), output
  tokens free; 250k tokens/s and 1,200 requests/min (stated as dynamically
  adjusting); 64k tokens per request (32k for state plus longest question).
- Privacy: Jev is not trained on customer requests/responses per the Models page;
  zero-retention terms are enterprise-only (see Legal page) — a later compliance
  decision, not this contract.
- No credentials are requested, recorded, or needed for this planning PR. At
  implementation time the project needs exactly one server-side API key; nothing
  else (no OAuth scopes, no per-user keys in V1).

## Fixture coverage map

`EX-001`, `VA-001`, `MKT-001`, `STK-001` → `identity_exact`, `in_stock_win`,
`evidence_strength_*`; `SUB-Q-001` → `substitute_fit_*` ≥ minimum;
`SUB-A-001`/`SUB-A-002` → `substitute_fit_*` below minimum (reject);
`CP-001`/`CP-002`/`CP-003`/`CP-004` → `consent_covers_test` + evidence levels;
`LC-001`…`LC-004` → ranges in state, never point-ranked over overlap;
`BLK-001` → `primary_page_blocked`; `CON-001` → conflict downgrade;
`NB-001` → `single_offer_only`; `CS-001` → consent Noul negative test;
`HIST-001`/`HIST-002` → `history_supports_wait` plus the no-target-price rule.
