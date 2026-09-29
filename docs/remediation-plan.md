# Golden Dataset Remediation Plan

Existing run artifacts are immutable evidence and are never rewritten.

## Phase 1 — Integrity foundation

Status: implemented; focused checks pass.

- Bind every Golden export to a content-derived record identity.
- Correct contamination health serialization and distinguish sibling overlap.
- Require `STRONG` verification when configured.
- Prevent ineligible duplicate members from displacing eligible records.

Acceptance: focused identity, quality, and export tests pass.

## Phase 2 — Semantic verification

Status: implemented; boundary and mutation checks pass.

- Align temporal, retention, window, and funnel contracts with their oracles.
- Add discriminating timestamp, NULL, tie, LAG, and ordering cases.
- Separate executable semantic mutant kills from invalid SQL.

Acceptance: boundary counterexamples and mutation classifications are tested.

## Phase 3 — Release and evidence safety

Status: implemented; public releases fail closed and provenance artifacts resolve.

- Fail closed when public/commercial evidence is absent.
- Exclude private verification evidence from public products.
- Require complete, resolvable lineage for shipped records.

Acceptance: omission and leakage tests fail closed.

## Phase 4 — Production controls

Status: implemented; the runner batches work, checks budgets before generation,
evaluates pause conditions, honors its target, and persists stop reasons.

- Enforce configured batch, budget, pause, audit, diversity, and target controls.
- Persist explicit stop reasons.

Acceptance: deterministic tests demonstrate every stop condition.

## Phase 5 — Controlled qualification

Status: completed by controlled requalification. The final strict export has
46 Golden records at `runs/controlled-requalification-002/quality/export/golden.jsonl`.

- Create a new internal run without modifying historical evidence.
- Target 60 Golden records, require at least 30, and cap at 80.
- Report technical, human-review, rights, and buyer-value evidence separately.

Acceptance: rescore the new artifacts. Commercial readiness remains blocked
until human review, rights clearance, and buyer-value evidence actually exist.
