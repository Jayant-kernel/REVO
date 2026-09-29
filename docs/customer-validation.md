# Customer validation

## Records, not relationships

`CustomerValidation` stores role-level interaction records: segment,
role (never personal names or contacts — those fields do not exist),
use case, problem, current solution, release tested, feedback class,
free-text feedback (redactable on export), requested features,
willingness signal, and evidence type. This is research evidence, not a
CRM.

## Feedback classes

`PROBLEM_CONFIRMED`, `PROBLEM_NOT_CONFIRMED`, `PRODUCT_USEFUL`,
`PRODUCT_NOT_USEFUL`, `QUALITY_CONCERN`, `PRICE_CONCERN`,
`INTEGRATION_CONCERN`, `FORMAT_CONCERN`, `COMPLIANCE_CONCERN`,
`NO_DECISION` — observations about feedback, never scores of customers.

## Willingness ladder (observed actions, increasing commitment)

`INTEREST` → `MEETING_REQUEST` → `PILOT_ACCEPTED` → `DATASET_TESTED` →
`PURCHASE_INTENT` → `PAID_PILOT` → `PAID_PURCHASE` → `REPEAT_PURCHASE`.

Signals move only upward on new observation, and purchase-level
signals require an explicit evidence reference — enforced in code. A
conversation or interest signal can never automatically become a
purchase.

## Pilots

`PLANNED` → `ACTIVE` → `COMPLETED`, with `PAUSED`/`CANCELLED` exits;
terminal states are final. Every pilot carries configurable success
criteria (metric + threshold + direction); evaluation reports
`MET`/`UNMET`/`UNEVALUATED` per criterion. Concrete value metrics
(benchmark improvement, time saved, coverage added, failures found)
replace vague statements like "customers loved it". Feedback links
forward to product decisions via `feedback_ids` — never to automatic
dataset modification.

## Current status: UNKNOWN

FACT: the recording, ladder, lifecycle, and redaction machinery is
implemented and tested.

UNKNOWN: every customer fact — no real customer interaction has been
recorded. The funnel is zeroed, not filled.
