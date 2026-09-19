# Bounded Discovery and Substitute Rules

Status: **rules draft for Captain review. Bounds are fixed before execution;
implementations may stop early only under the stopping rule below.**

"Small", "bounded", and "materially better" must mean the same thing to every
reviewer. These rules make them reproducible.

## Candidate limits (fixed before execution)

- At most **6 requested-item candidates** and at most **4 substitute candidates**
  per decision. Fewer is preferred; the caps bound effort, not targets.
- At most **one additional option** beyond the best requested-item offer and the
  best qualifying substitute, and only when it changes the decision.

## Attribute rules

- Before searching substitutes, record which attributes must remain fixed
  (must-haves) and which may vary, in the shopper's own terms. Geographic or
  product interpretations of words like "local" or "similar" are asked, never
  assumed.
- Every candidate — requested or substitute — is matched to exact variant,
  quantity, condition, bundle, seller, fulfillment party, and region before
  comparison. Quantity, size, and unit cost are normalized when they affect
  comparison.
- A substitute appears only with its material differences stated beside its
  savings. Private-label and lookalike products are compared on documented
  attributes only; unknown manufacturer, durability, and performance differences
  stay explicit and equivalence is never implied.

## Stopping rule

The search may stop before exhausting the caps only when **all** hold:

1. A leading candidate wins on known landed cost under every stated unknown
   (robust range, per `LANDED_COST.md`).
2. Its evidence meets the `buy` minimum in `DECISION_TABLE.md`.
3. Remaining unexamined candidates cannot change the verdict (record which were
   skipped and why — e.g., strictly dominated on price with weaker evidence).

## Ties

- Tied or overlapping-range candidates are presented together with unknowns
  visible; the tie is never broken on headline discount percentage.
- If no further evidence can separate them within the stop boundary, the verdict
  is `verify` with the single check that would separate them.

## Adversarial cases (must hold)

- `SUB-A-001`: a cheaper candidate violating a must-have is rejected, however
  large the saving. Price must not win by changing the product.
- `SUB-A-002`: a lookalike with unknown manufacturer/durability/performance
  differences is never bought on implied equivalence; `verify` at best.
- Requests where no substitute is genuinely comparable must return a
  requested-item-only verdict, with the absence stated.
