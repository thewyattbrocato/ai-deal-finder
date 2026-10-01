# Live Verification (V1, 2026-09-30)

First browser-executed check of the landed V1 engine against live-observed
evidence. Read-only anonymous observation only: no login, no checkout, no
payment, no personal data, no account mutation, no inventory reservation, and
no coupon cart tests (no consent solicited). Where observation was blocked,
the research-only fallback was used — that is correct behavior, not failure.

Method: `chrome-devtools-axi` browsing; engine runs via `deal_finder/`
(decide/judge composition, stdlib-only). Region for all observations: US.
No gate in `VALIDATION_RECORD.md` is claimed passed by this document; that
record stays `NOT RUN` until independent review. `ASSUMPTIONS.md` D1–D6 are
untouched.

## Observations

| ID | Source | Observed at (UTC) | What was seen | Evidence state |
| --- | --- | --- | --- | --- |
| OBS-1 | `https://www.apple.com/airpods-pro/` | 2026-09-30T14:08:20Z | "AirPods Pro 3 … $249" with Buy link, Apple US site | observed-now (item price) |
| OBS-2 | `https://www.apple.com/shop/buy-airpods/airpods-pro-3` | 2026-09-30T14:08Z | Buy page loads; generic "Get free delivery, or pick up available items at an Apple Store" template text; buy-box price absent from rendered text at observation time; no item-specific stock string | unverified (price/stock on this page) |
| OBS-3 | `https://www.apple.com/us-edu/shop/buy-airpods/airpods-pro-3` | 2026-09-30T14:09:36Z | Education-gated store loads; no price in rendered text; eligibility (student/teacher) not volunteered | retailer-stated at best; eligibility-gated (LC-003 pattern) |
| OBS-4 | Best Buy AirPods Pro 3 product URL | 2026-09-30T14:09:23Z | `chrome-error://chromewebdata/`, `ERR_HTTP2_PROTOCOL_ERROR`, page unreachable | primary page blocked (BLK-001 pattern) |
| OBS-5 | `https://www.sony.com/electronics/headphones/wh-1000xm5` | 2026-09-30T14:08Z | "Access Denied … Reference 0.e80a3517.1790777300.b9b3a8" | primary page blocked |
| OBS-6 | B&H Photo WH-1000XM5 product page | 2026-09-30T14:08Z | Cloudflare "Performing security verification" challenge | observation blocked |
| OBS-7 | `https://www.retailmenot.com/view/apple.com` | 2026-09-30T14:09Z | Cloudflare challenge; no code text observed | coupon evidence stays unverified (CP-003 pattern); no cart test (CS-001: no consent, correct refusal) |

Tax and shipping were not stated for the exact item and cart on any loaded
page (OBS-1 is a marketing page; OBS-2 shows only generic delivery template
text), so both stay `Unknown` — never inferred.

## Engine runs over observed evidence

Shopper scenario: "AirPods Pro 3, white, new, 1 pair", region US, browsing
mode, no coupon consent, no price history.

### LV-001 — single Apple direct offer, full provenance, tax/shipping Unknown

Input: candidate `apple-direct` (variant/quantity/condition/seller/
fulfillment/region matched; `in_stock=True` on the strength of the observed
Buy affordance — see caveat; evidence `observed-now` with source OBS-1 URL,
region US, timestamp above); landed cost $249.00 item price, shipping
`Unknown`, tax `Unknown` (range `USD 249.00 .. open-ended`); one aggregator
code with status `unverified`; no consent record.

Verdict (engine output, quoted):

```text
Verdict: buy
Winner: apple-direct
- code 'AGG20' is unverified; excluded from landed cost and must not decide the verdict
- exact identity matched for 'AirPods Pro 3, white' from Apple
- landed cost known or a still-winning range; decisive claims verified; in stock
Next action: Buy 'AirPods Pro 3, white' from Apple at the verified landed cost; recheck price/stock at purchase time.
```

Caveats recorded beside the verdict: the amount-due range is open-ended
(tax/shipping Unknown); stock rests on Buy-link presence, not an
item-specific stock reading; single-candidate robustness is vacuous (no rival
to flip with). The untested code was correctly excluded from the ranking.

### LV-002 — rival primary page blocked (OBS-4 as winner)

Input: candidate `bestbuy-listing` with `primary_page_blocked=True`.

Verdict (engine output, quoted):

```text
Verdict: verify
- primary merchant page blocked: indexed text is unverified discovery only
Manual check: Manually open the merchant page … and confirm the current price; only indexed text supports the claim.
(downgraded from buy)
```

Blocked evidence never upgrades. Matches fixture BLK-001.

### LV-003 — provenance-free "observed-now" (indexed text, no URL/timestamp)

Pre-fix, a winner with `evidence_state=observed-now` but empty
source/region/`observed_at` returned **buy** — a fail-open hole: pasted or
indexed text wearing a verified state could decide a purchase. Post-fix the
same input returns:

```text
Verdict: verify
Manual check: Re-observe the offer at its source (merchant page URL) and record the source, region, and timestamp, then re-run.
```

### LV-004 — coupon research-only fallback (OBS-7 + no consent)

No code text was observable and no consent was solicited, so the only honest
coupon status is `unverified`; the engine excludes such codes from landed
cost (seen in LV-001 reasons) and `CartTestGate.authorize()` refuses without
consent. Matches fixtures CP-003 and CS-001. No cart test was run, per the
read-only rule.

## Discrepancy fixed (fail-closed)

- **Hole:** `decide()` accepted `price_determining_states` membership in
  `VERIFIED_STATES` as sufficient for `buy`, ignoring provenance; and
  `check_no_upgrade()` only audited non-verified states, so a verified-state
  claim without source/region/timestamp passed both gates.
- **Fix:** `deal_finder/decision.py` — provenance gate before the buy
  minimums: a winner missing source, region, or `observed_at` downgrades to
  `verify` with a re-observe manual check. `deal_finder/evidence.py` —
  `check_no_upgrade()` now also flags verified-state claims lacking
  provenance ("presented as verified without proof").
- **Tests:** `test_verified_state_without_provenance_downgrades`
  (DecisionTest) and `test_verified_state_without_provenance_flagged`
  (EvidenceTest). Suite: 55 tests green
  (`python3 -m unittest discover -s tests`).

## Follow-ups (observed, not built)

- `Candidate.in_stock` is a bare bool with no evidence state; the live run
  could not represent "stock not confirmed" distinctly from in/out of stock.
  Noted, not modeled — a stock-provenance field is a captain call.
- Single-candidate vacuous robustness (`ranking_is_robust` returns True with
  no rivals, per its documented contract) let LV-001 reach `buy` on an
  open-ended range. Behavior matches the letter of LC-001 ("verify unless
  robust") and the function docstring, so it was left unchanged; whether
  single-offer open-ended ranges should buy is flagged for review.
- Live Jev integration, browser cart-test execution bindings, price
  monitoring, and monetization remain out of scope per the brief.

## Fixtures

Live cases LV-001 … LV-004 appended to `FIXTURES.json` in the existing case
schema. Their verdicts are observed engine outputs, **not** independent
labels — the file's reviewer-isolation rule still applies to every case.
