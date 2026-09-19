# Validation Record (gates vs. evidence)

Status: **no gate has passed. Implementation remains blocked. The Captain's
conditional build approval is NOT met.**

Rule: no gate may be marked passed from authored fixtures, plans, self-review,
missing follow-up, or implementation-generated evidence. Unexecuted gates are
marked `NOT RUN` or `BLOCKED` with exactly what independent or real-user
evidence remains.

| Gate | Evidence required | Current result | What remains |
| --- | --- | --- | --- |
| Safety | Zero S0 fails across fixtures, consent negative tests, observed sessions; consent records with scope/timestamp/persistence/revocation/merchant/budget/actions/stop/cleanup. | NOT RUN | Independent fixture labeling + Captain-approved thresholds; consent negative tests (`CS-001`); observed-session safety log. None exist yet. |
| Evidence | Zero upgrades from discovery/retailer/user evidence to verification without matching proof, scored on frozen corpus by reviewers other than the implementer. | NOT RUN | Independent relabel of `FIXTURES.json`; blind scoring run. |
| Exactness | Independently measured error rates for variant, quantity, condition, seller, fulfillment, availability, landed-cost extraction within Captain-approved thresholds. | BLOCKED | Captain-approved per-field thresholds first; then prospective-task measurements. |
| Substitute | Every substitute satisfies must-haves with differences exposed; adversarial rejects hold (`SUB-A-001`, `SUB-A-002`); judged without implying undocumented equivalence. | NOT RUN | Independent relabel + blind scoring of substitute cases. |
| Decision | `buy`/`wait`/`verify`/`abstain` match frozen `DECISION_TABLE.md` under independent review; inter-reviewer agreement recorded before scoring output. Jev layer additionally requires: thresholds/weights fit on the independently labeled corpus with confidence-vs-accuracy plots, self-consistency repeats, substitute-ordering and claim-vs-source checks per `JUDGMENT_ENGINE.md`; no live API evidence used for tuning before independent relabeling. | NOT RUN | Frozen table approval; Jev spec approval; agreement study; blind scoring; Jev calibration runs. |
| Checkout | Represented vs. actual payable terms compared for every voluntarily reported real checkout; mismatches recorded; missing follow-up recorded as missing. | NOT RUN | Real-user sessions per `USER_VALIDATION_PLAN.md` plus voluntary checkout reports. Zero sessions run. |
| User-value | Acceptable correction burden; shoppers can explain why the recommendation follows from the evidence; no effectiveness claim until observed. | NOT RUN | Real-shopper sessions. Zero sessions run. |
| Simplicity | Smallest workflow passing the above; no tracking, broad automation, scoring machinery, or merchant complexity until measured failures require it. | NOT RUN | Cannot pass before the gates it depends on. |
| Boundary check | Coupon testing opt-in + logged-out anonymous-cart only; discovery keeps requested-item plus bounded comparable substitutes. | NOT RUN | Same evidence as Safety + Substitute gates. |

## What would activate build approval

Every row above reads passed with its required evidence attached. Until then,
work stays in planning and validation; no skill or app implementation begins.
