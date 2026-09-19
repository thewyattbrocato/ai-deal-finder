# Consent and Action Accountability

Status: **specification draft for Captain review. No consent exists; no cart
action has been taken or observed.**

One stored approval must never become blanket permission. Every cart mutation
must trace to a visible consent record, and every run must end in a recorded
stop.

## Consent record (all fields required before any cart action)

- **Scope:** anonymous-cart coupon testing only; logged-out; pre-payment totals
  only. Explicitly excludes login, checkout, payment, personal data, account
  mutation, and scarce-inventory reservation.
- **Timestamp:** when consent was given (absolute time), and the session it covers.
- **Persistence:** saved once, honored until the user changes or revokes it; the
  stored record shows its current state (granted / revoked) and last change.
- **Revocation:** the user can revoke at any time in plain language; revocation
  takes effect immediately and is recorded; past actions keep their original
  consent reference, future actions stop.
- **Merchant:** each merchant and each coupon attempt is traceable to the consent
  (consent is per-test-run, cited per action, not a silent global flag).

## Attempt budget and stopping

- Each run declares a small attempt budget (max coupon combinations to try) and
  prioritizes combinations supported by published terms.
- The run stops before login, checkout, payment, personal data, account mutation,
  or scarce-inventory reservation; when browser tools are absent; when merchant
  rules prohibit testing (determined conservatively — ambiguous terms mean no
  test); or when the budget or cleanup boundary would be exceeded.
- Falling back to research-only claims when the budget or boundary would be
  exceeded is correct behavior, not a failure.

## Per-action log (all fields required per run)

Merchant, actions taken, attempt budget used vs. declared, stop reason, and
cleanup result. Cleanup means visible empty-cart restoration plus browser-session
cleanup; the record must not claim knowledge of unobservable merchant-side
identifiers.

## Negative tests (must hold; fixture `CS-001`)

- No cart mutation occurs without a preceding consent record.
- No action exceeds the logged-out anonymous-cart boundary, even with consent.
- Revocation mid-run halts further actions immediately.
- A missing or expired consent record behaves exactly like consent absent.
