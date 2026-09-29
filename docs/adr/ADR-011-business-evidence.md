# ADR-011 — Business evidence is measured, classified, and never inferred

- Status: accepted
- Date: 2026-09-23 (Phase 8)

## Context

Phases 1–7 prove we can generate, verify, audit, trace, package, and
release high-confidence synthetic SQL data. None of that proves the
data improves models, helps customers, or will sell. Phase 8 must
produce commercial evidence without manufacturing it.

## Decision

1. Every business record carries a load-bearing evidence status
   (`OBSERVED`, `MEASURED`, `USER_REPORTED`, `ASSUMED`, `UNKNOWN`;
   plus quarantined `TEST_FIXTURE`). Status gates what claims may be
   made: measured status needs measured evidence, customer validation
   needs user-reported evidence.
2. Experiment, benchmark, and report identities are content-defined
   over material configuration (Phase 6 conventions). Operational
   fields never enter identities.
3. Correctness judgments stay with the owner's harness (ideally
   Phase 3/4 infrastructure). Phase 8 aggregates outcomes; it never
   re-judges and never requires a proprietary model API.
4. `INSUFFICIENT_EVIDENCE` is a first-class, reportable outcome at
   every level — experiment verdict, hypothesis verdict, report
   verdict, cost totals.
5. Willingness and funnel entries record observed actions only, with
   code-enforced escalation rules (purchase-level signals need
   evidence references). Private answers, secrets, and confidential
   fields are blocked from exports by code, not policy text.

## Rationale

- A single invented customer or improvement figure would poison every
  downstream decision; structural honesty (types, validators,
  quarantines) beats procedural honesty (asking people to be careful).
- Content identities make experiments citable and rebuild-stable,
  matching the provenance guarantees of Phase 6.
- Keeping training/evaluation out of the system (adapters over
  supplied artifacts) avoids building a GPU platform while staying
  reproducible without proprietary APIs.

## Consequences

- The core hypothesis ships as `INSUFFICIENT_EVIDENCE` until a real
  experiment says otherwise — this is correct behavior, not a gap.
- GTM materials are generated from facts with explicit UNKNOWNs; any
  future performance or market claim must arrive with linked MEASURED
  or USER_REPORTED evidence or fail `claims validate`.
- No payments, CRM, portals, or sales automation may be added under
  this ADR; commercial evidence recording is the ceiling.

## Alternatives considered

- Marketing-led GTM docs: rejected (claims without evidence links
  fail validation by design).
- Built-in training harness: rejected (scope explosion; proprietary
  API lock-in risk; duplicates Phase 2/3 concerns).
- Single business score: rejected (hides which link of the chain is
  actually unproven).
