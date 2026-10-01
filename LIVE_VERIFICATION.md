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

---

# Coupon slice (V1, 2026-10-01)

Follow-up slice: real products where a public coupon or promo is actually
visible on the page, observed read-only without logging in, checking out, or
testing a cart. Same method and region (US) as above. No gate in
`VALIDATION_RECORD.md` is claimed passed; `ASSUMPTIONS.md` D1–D6 untouched.

## Observations

| ID | Source | Observed at (UTC) | What was seen | Evidence state |
| --- | --- | --- | --- | --- |
| OBS-8 | `https://oldnavy.gap.com/browse/product.do?pid=777363182` | 2026-10-01T19:50:21Z | "High-Waisted SoComfy Wide-Leg Sweatpants … $25.00" (was $36.99) with "Extra 30% Off with Code: EXTRA"; site banner "Fall Faves Up To 50% Off + Extra 30% Off Purchase … Code: EXTRA … Exclusions apply" | observed-now (item price); code EXTRA retailer-stated, untested (CP-002 pattern) |
| OBS-9 | `https://www.gap.com/browse/product.do?pid=800546212` | 2026-10-01T19:50:30Z | "CashSoft Crop Cardigan … $79.95"; site offer texts "50–60% off limited-time deals / Select styles", "Extra 50% off sale", credit-card offer "Extra 25% off your first purchase with your new card. Ends 10/3." No code seen | observed-now (item price); offer texts retailer-stated, applicability to this item unconfirmed — excluded; no coupon |
| OBS-10 | `https://www.nike.com/t/air-jordan-og-womens-shoes-6JW206/CW0907-002` | 2026-10-01T19:50:41Z | "Air Jordan OG Women's Shoes … $87.97" (was $155, 43% off); "Members: Free Shipping on Orders $50+"; "You'll see our shipping options at checkout." No code seen | observed-now (item price = $87.97; the was-price is reference text, never subtracted); shipping Unknown with membership eligibility note (LC-003 pattern); no coupon |
| OBS-11 | `https://www.apple.com/airpods-pro/` | 2026-10-01T19:50:52Z | "AirPods Pro 3 … $249" with Buy link; coupon/promo/code text search over rendered page: zero hits | observed-now (item price); no-coupon result stands |

Tax and shipping were not stated for the exact item and cart on any loaded
page, so both stay `Unknown` — never inferred. Membership-gated free-shipping
notes (Old Navy, Gap, Nike) keep shipping `Unknown` with the eligibility
condition attached; membership was not volunteered (LC-003). The Gap
credit-card offer text is recorded as seen and excluded — it is not a coupon
for this item and must never decide a verdict.

## Engine runs over observed evidence

### LV-005 — Old Navy sweatpants with retailer-stated code EXTRA

Input: candidate `oldnavy-sweatpants` (identity matched; `observed-now` with
OBS-8 source, US region, timestamp); landed cost $25.00 item price, shipping
`Unknown` (eligibility: free shipping on $50+ for Rewards Members; membership
not volunteered), tax `Unknown` (range `USD 25.00 .. open-ended`); coupon
`EXTRA` status `retailer-stated` (merchant-published on the page, never
cart-tested — no consent, read-only rule); no consent record.

Verdict (engine output, quoted):

```text
Verdict: buy
Winner: oldnavy-sweatpants
- code 'EXTRA' is retailer-stated; excluded from landed cost and must not decide the verdict
- exact identity matched for 'High-Waisted SoComfy Wide-Leg Sweatpants' from Old Navy
- landed cost known or a still-winning range; decisive claims verified; in stock
Next action: Buy 'High-Waisted SoComfy Wide-Leg Sweatpants' from Old Navy at the verified landed cost; recheck price/stock at purchase time.
```

CP-002 second path: the winner holds without the code, so buy stands with the
code excluded — never counted. Same open-ended-range and single-candidate
caveats as LV-001.

### LV-006 — Gap cardigan with offer text, no code

Input: candidate `gap-cardigan` ($79.95 observed-now with OBS-9 provenance);
shipping/tax `Unknown`; no coupons (no code was seen — a product with no
public coupon stays a no-coupon result); site offer texts recorded beside the
verdict, excluded from the ranking (applicability to this item unconfirmed).

Verdict: `buy` at range `USD 79.95 .. open-ended`, winner `gap-cardigan`.
Offer text without a code never becomes a coupon and never enters landed cost.

### LV-007 — Nike markdown price, membership-gated shipping note

Input: candidate `nike-jordan-og` ($87.97 observed-now with OBS-10
provenance; the "$155 / 43% off" reference is context text — the ranked item
price is the observed $87.97, no phantom subtraction); shipping/tax
`Unknown`, eligibility note "members free shipping on orders $50+; membership
not volunteered"; no coupons.

Verdict: `buy` at range `USD 87.97 .. open-ended`, winner `nike-jordan-og`.
No savings figure is fabricated: the page's was-price is quoted as seen, not
computed into the total.

## Discrepancies: none — engine already fail-closed

The runs above needed no engine change: retailer-stated codes are excluded by
`Coupon.may_count_in_landed_cost()` (fixtures CP-002/CP-003), membership
notes stay `Unknown` with eligibility attached (LC-003), and reference prices
never enter `LandedCost` arithmetic. New focused tests pin these behaviors
(`CouponSliceTest`: retailer-stated code excluded while winner holds;
offer-text-without-code stays coupon-free; membership shipping stays Unknown;
markdown reference never subtracted). Suite: 59 tests green
(`python3 -m unittest discover -s tests`).

## Fixtures (slice)

Live cases LV-005 … LV-007 appended to `FIXTURES.json` in the existing case
schema. Their verdicts are observed engine outputs, **not** independent
labels — the file's reviewer-isolation rule still applies to every case.
