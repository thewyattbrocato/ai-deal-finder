# Real-User Validation Plan (prospective)

Status: **plan only. No sessions run. No effectiveness claimed.**

This experiment may reject the product hypothesis. It must not be presented as
demand proof in advance, and its sample is a learning threshold, not a
statistically representative market claim.

## Design

- **Prospective, real purchases only.** Participants bring pending, real purchase
  intents (not invented prompts). Sessions run before purchase, against the
  shopper's normal method (manual search / existing tools) or a general agent,
  on the same intent.
- **Minimum corpus.** 20–30 bounded purchases across at least five product
  categories, three merchant types, two regions, several deliberately
  stale/ineligible codes, marketplace-seller cases, and both browsing and
  no-browsing modes. Include requests where a substitute should win and requests
  where no substitute is genuinely comparable.
- **No implementation-generated evidence.** Wizard-of-Oz or manual-protocol
  runs are acceptable; output of any built skill is not validation evidence for
  its own acceptance.

## Records per session

- Shopper's normal-method result vs. protocol result on the same intent.
- Final recommendation correctness at checkout (voluntarily reported actual
  payable terms vs. represented terms; mismatches recorded).
- Exact-item match result and any substitute-constraint violation.
- Landed-cost error where checkout truth is available.
- Unsupported-claim count (claims above their evidence state).
- User correction burden (number and kind of user corrections needed to reach
  an actionable answer).
- Whether the user could act on the answer, and in their own words why the
  recommendation follows (or fails to follow) from the evidence.
- Unresolved uncertainty remaining at decision time.

## Checkout follow-up rule

Actual checkout outcomes count only when users voluntarily report them.
Missing follow-up is recorded as **missing** — never as success, and never as
evidence for any gate.

## What would pass the User-value, Checkout, and Exactness gates

Recorded in `VALIDATION_RECORD.md`. In short: acceptable correction burden with
users able to explain the recommendation from the evidence (user-value);
represented-vs-actual comparison with mismatches recorded (checkout); and
independently measured extraction error rates within Captain-approved
thresholds (exactness). None of these can pass from plans, authored fixtures,
or self-review.
