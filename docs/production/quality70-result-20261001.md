# Local quality improvement: evidence and assessment

## Outcome and dataset identity

**INFERRED — 59/100**, with roughly five-point judgment sensitivity, for the
**new 15-row diagnostic candidate only**. The 70 target was **not justified**.
The historical 46-row assessment remains 52/100. No human-review, rights or
demonstrated-utility credit has been added for implementation work.

**FACT** — The 80-row premium qualification was not executed: the unchanged
four-independent-template-per-family preflight gate remains blocked. The new
library has 21 IDs (two per family except aggregation's three), 19 below that
40-ID library floor. The smoke also lacks premium row balance, instruction
count, selected construct coverage and adversarial evidence on nine survivors.
These are remaining engineering requirements, not claimed completed work.

Frozen identities:

- Run: `runs/diverse-smoke-002`, config
  `configs/production/diverse_smoke_002.yaml`, config ID
  `sha256:e13ee43fa796dbb591686c8f5124ddc031cc7286beafa3982382c38111b1bbb9`.
- Source Golden JSONL hash:
  `sha256:caa7f7c4c88eeb76c9441c9af7915e4d1242d6c529cd9f1e18d476f8d409457a`.
- Derived provenance snapshot:
  `sha256:063c06ee6642a97a0e9e0504837fdbde567aacdfd95d44e626656444325831e8`.
- Diagnostic review package:
  `sha256:04dc605d20a6640981f21cdb7d7c142e29d0ed19462bc96e030084e897540723`.
- Implementation receipt in the source manifest:
  `sha256:6c7f847f711cc459a448e548151a2e0beca8b869fa193075be850a13a2edf019`.
- Derived artifacts: `runs/diverse-smoke-002-evidence/manifest.json` binds source
  hashes and the provenance, diagnosis, replay and pending-review artifacts.

The review package is labeled **DIAGNOSTIC**; it is not a premium-qualified
release package. Internal label: “Internal verified diagnostic review candidate
— human review pending.” No production decisions were inserted.

## Baseline and implementation register

The checkout started clean at `22ecfeb`, on main. No applicable AGENTS.md was
found in the repository. No commits, pushes, uploads or paid generation occurred.

| Area | Verified state / remaining work |
| --- | --- |
| Historical evidence | Recounted: controlled requalification 46 Goldens / 57 re-verifications; Production-001 232 Goldens / 1,500 candidates; earlier smoke 6 Goldens / 30 candidates. The requalification run reuses candidates and has no generation bundles of its own. |
| Taxonomy/library | Ten families. Original HEAD had 14 distinct IDs and 23 generatable versions. Now 21 IDs / 30 versions; versions and seed variants do not count as independent questions. Seven new contracts, Python oracles and separately authored adversarial fixtures are implemented and tested. |
| Runtime | Local Devstral provider, no fallback; Ollama digest and Docker image matched their pinned values. All smoke preflight checks passed. No new commercial clearance decision. |
| Runner repairs | Hidden/property/metamorphic/mutation executions now share the pinned production SandboxConfig. Source content is pinned for resume; nonempty unmanifested destinations are rejected. Task batches and states publish atomically. Checkpoint artifact hashes reject changed evidence. Cumulative wall-time checks operate between expensive calls and across resumptions; elapsed receipts are persisted. Pause conditions precede target-count success. |
| Post-smoke interruption repair | Generation now reserves logical candidate attempts durably before each provider group. Interrupted groups consume budget rather than silently getting free retries on resume. Regression tests exercise exhausted reservations with no committed responses. This source change followed the frozen smoke/replay and requires a new run identity; historical receipts are unchanged. |
| Existing controls verified | Policy content hashes, template catalog identity, one-batch authorization, output-directory matching, candidate/task caps, Docker isolation, no provider fallback, immutable historical artifacts and current release gates. |
| Review repairs | Duplicate frozen item lines now fail closed; surrounding whitespace cannot provide a second reviewer identity. Persistent hash-chained decisions, disagreements, export consumption and public-release gating remain covered by tests. Reviewer authentication/access control remain a coordinator's responsibility. |
| Post-smoke public-content repair | Public validation now compares shipped question, rendered schema and any exposed SQL with the content-verified review item, not just its record ID and PASS status. Changed content requires new review even when someone preserves the old ID or recomputes release checksums. Tests use synthetic review fixtures only. |
| Designed only | Most of the original 40-question matrix; schema-disjoint utility protocol below. Neither designs nor templates are accepted Goldens. |
| Missing engineering | 19 further independent IDs for four per family; more materially distinct tasks for 80 nonduplicate rows; missing adversarial fixtures for legacy survivor tasks; selected HAVING/LIMIT/UNION coverage; richer realistic distributions and empirical difficulty calibration. |
| External/human dependency | Two blind human decisions per row, adjudication, owner-specific rights decision, independently operated replay and buyer-approved utility effect threshold. External contamination matching corpus is absent. |

**FACT** — The frozen release specification says its premium score remains 52
until human review, rights, replay and utility exist. This report preserves that
rule and does not claim PREMIUM_93 acceptance. The user-requested new-dataset
pre-review assessment is separately identified; it is neither a revision of the
historical score nor an alternative public release gate.

## Commands and actual checks

Run from the repository root:

```powershell
python -m pytest -q
python -m verified_data_factory.cli production preflight --config configs/production/diverse_smoke_002.yaml
python -m verified_data_factory.cli production run --config configs/production/diverse_smoke_002.yaml --run runs/diverse-smoke-002 --execute
python -m verified_data_factory.cli production report --run runs/diverse-smoke-002
python scripts/prepare_smoke_evidence.py --config configs/production/diverse_smoke_002.yaml --out-dir runs/diverse-smoke-002-evidence
python -m verified_data_factory.cli provenance validate --bundle runs/diverse-smoke-002-evidence/provenance
python -m verified_data_factory.cli quality review-status --package runs/diverse-smoke-002-evidence/review
```

The run commands are recorded receipts, not instructions to rerun or overwrite
the completed identity. The derived evidence script refuses an existing output.

- **MEASURED** baseline: 718 passed in 550.46 seconds.
- **MEASURED** new task/pinned-Docker/integrity focus: 40 passed in 63.02 seconds.
- **MEASURED** intermediate full suite: 761 passed / one registry-coverage test
  failed because its enumerated template set needed the seven new IDs. Updated
  the explicit set; no assertion about correctness was removed.
- **MEASURED** one concurrent full-suite attempt reached the 1,200-second tool
  timeout; it is not recorded as a passing suite. The background smoke worker
  exited before checkpointing candidates; the frozen task/checkpoint hashes
  allowed a foreground resume of the same input identity.
- **MEASURED** full suite before attempt-reservation repair: **762 passed in
  555.67 seconds**, no skips. After that repair, one full suite passed 763
  tests in 510.43 seconds; after the public frozen-content binding repair and
  final historical-artifact comparison, the final full suite passed **766 tests
  in 590.77 seconds**, no skips.
- **MEASURED** Ruff passed on affected production, product, verification/review
  modules, new task modules, diagnostic scripts and affected tests. Strict mypy
  passed on nine affected source/script files. `git diff --check` passed.
- **MEASURED** provenance: `golden=15 incomplete=0 graph_problems=0`.
- **MEASURED** same-host replay: 15/15 regenerated tasks/content IDs and semantic
  verification results matched, including mutation, hidden, property and
  metamorphic outcomes. Fresh pinned containers were used.
- **NOT_MEASURED** clean independent host/dependency-environment attestation and
  full health-metric replay. A same-host replay is not independent reproduction.

## Smoke outcome and population distinctions

**MEASURED** — 20 tasks, three local-model attempts each; 60/60 generated and
executed, 37 PASS / 23 FAIL / zero INCONCLUSIVE. Seven execution failures,
15 initial-result mismatches and one hidden mismatch. All 15 selected rows
have STRONG verification and mutation 1.0. Runtime receipt: 1,719.171 seconds
(28.65 minutes), excluding interrupted work before the first candidate receipt.

| Family | PASS / FAIL | Selected |
| --- | --- | --- |
| Simple joins | 6 / 0 | 2 |
| Multi joins | 6 / 0 | 2 |
| Aggregation | 3 / 3 | 1 |
| CTE | 3 / 3 | 1 |
| Subqueries | 1 / 5 | 1 |
| Window functions | 6 / 0 | 2 |
| Temporal | 3 / 3 | 1 |
| Deduplication | 3 / 3 | 2 |
| Retention | 5 / 1 | 2 |
| Funnel | 1 / 5 | 1 |

Receipts: source `quality/export/population_metrics.json`, and derived
`premium-screen.json`, `diagnosis.json`, `golden.jsonl` and `qualities.jsonl`.

1. Candidate siblings: 60 rows / 20 tasks, **40 excess sibling candidate rows**.
2. Selected duplication: 15 rows / 15 tasks; zero exact, structural and semantic
   fingerprint collision members. This is screening evidence, not AST proof.
3. Cross-task semantic collisions: measured task participation rate **0.0**.
4. Cross-split leakage: **NOT_MEASURED**, because roles are UNKNOWN. Zero observed
   role-overlap counts are not a validated training/evaluation split.
5. External overlap: **NOT_MEASURED**, no versioned external comparison corpus.

The 60 internal EXACT_OVERLAP flags have scoped sibling evidence. All 15 selected
rows retain those flags; none is globally erased or treated as external matching.
Historical unscoped flags remain unresolved. Selected coverage: 10 families,
15 exact instructions, 12 schema fingerprints, six explicit domains, 13/16
constructs and 15/17 declared edges. Schema counts and edge labels still require
semantic review. Whole-candidate coverage (15 constructs / 16 edges) is not
substituted for selected-record coverage.

**MEASURED economics proxy** — 114.61 checkpointed run seconds per selected,
screening-novel Golden (15 denominator), versus 28.65 seconds per candidate.
This excludes the interrupted attempt, reviewer work, electricity, hardware and
an independent equivalence assessment. Cost per truly novel eligible **premium**
Golden is **NOT_MEASURED**: this is not an eligible 80-row pool.

The smoke's interruption predated the durable attempt-reservation repair.
Its exact total logical/transport calls including abandoned work are
**NOT_MEASURED**; 60 is the checkpointed candidate-response population, not proof
that no additional requests occurred. New runners conservatively charge
interrupted logical groups, with provider transport retries separately bounded.
Wall-time enforcement checks between bounded calls; it is not hard preemption
of an in-flight request. The old complete run is never resumed with new code.

## Failure diagnosis and difficulty limits

The protocol was frozen before generation: one seed per independent template,
three attempts, temperature 0.3, top_p 0.9 and a 2,048-token cap. No task answers
were changed to accept a model solution. The following diagnoses are grounded in
the retained SQL and executor/oracle differences in `diagnosis.json`:

- Payment candidates negate already signed reversal amounts, adding reversals
  rather than subtracting their effect. This is candidate arithmetic error.
- Inventory candidates subtract an aggregate from itself or reference a nonexistent
  `table` discriminator. These are candidate semantic/binder failures.
- Education candidates filter to passed courses before counting requirements,
  or violate grouping/reference rules. Missing courses then disappear from the
  comparison. Contract tests include the missing-course counterexample.
- Clinic SQL returns a timestamp for week_start although the contract asks for
  an ISO DATE. Counts agree; representation fails. No coercion was added to
  make that output pass; the test query demonstrates the DATE contract works.
- Existing subquery failures join multiple matching purchases without deduplicating
  buyers. This is candidate duplicate-output error, not the old threshold mutant.
- Retail funnel candidates still count step presence/maximum rather than an
  ordered prefix; one has a DuckDB syntax error. Support funnel candidates lose
  event-ID tie order or accept a chain on the normal fixture that fails the
  separately authored ordered counterexample. One support candidate passes.
- Grade revision failures omit timestamp tie-breaking or use invalid grouped
  subqueries. One repeat-payment candidate uses another dialect's DATE_ADD.

**INFERRED** — This supplies useful difficulty/error-mode evidence. It does not
identify a checkpoint-independent difficulty scale: only three correlated
attempts on one instance of each task were observed. Passing a hand-authored
test query is not evidence of generation difficulty or downstream utility.

## New assessment under the unchanged rubric

All new scores below are **INFERRED**, with explicit deductions. The reference
column is the untouched historical assessment, not a paired causal baseline.

| Dimension / weight | Reference | New | Evidence supporting judgment and remaining deduction |
| --- | ---: | ---: | --- |
| Semantic correctness / 15 | 13 | 13 | 15 PASS/STRONG survivors, exact task binding and same-host semantic replay; no independent expert intent/oracle review. |
| Verification discrimination / 15 | 13 | 12 | Mutation 1.0 across ten selected families, new executable counterexamples; nine survivors lack independent-adversarial runtime cases, and one invalid mutant is separately exposed. Full premium adequacy is not claimed. |
| Instruction quality and independence / 10 | 6 | 7 | 15 distinct selected business contracts including payment retention, media history and support progression; small library, some legacy query-recipe language, no human naturalness review. Contract text differs materially in inferred objectives, not just wording. |
| Diversity and independent coverage / 15 | 2 | 8 | All ten selected families, 12 schema fingerprints, six domains, 13 constructs / 15 edges, zero selected fingerprint collisions; only 15 questions, uneven counts, no AST/equivalence attestation, HAVING/LIMIT/UNION missing among survivors. |
| Realism and demonstrated difficulty / 10 | 2 | 4 | Synthetic multi-domain relationships and discriminating NULL/tie/calendar boundaries; observed 37/60 solve outcomes and retained wrong SQL. Small constructed distributions and three-attempt, one-model protocol limit generalization. |
| Human review / 10 | 1 | 1 | Zero decisions, 15 PENDING items. Tooling and AI-authored fixtures earn no completed-review points. |
| Identity/provenance/reproducibility / 10 | 9 | 9 | Exact dataset hash/snapshot, complete graph, artifact hashes, 15/15 same-host replay; provenance derived after execution, no independent environment attestation. |
| Separation/contamination / 5 | 4 | 3 | Sibling-scoped flags retained and selected collisions measured; external matching and UNKNOWN-role split separation are NOT_MEASURED. Deductions are stricter than the historical assessment. |
| Rights/clearance / 5 | 0 | 0 | REVIEW_REQUIRED_NON_COMMERCIAL, no affirmative release-specific owner decision. |
| Documentation/utility / 5 | 2 | 2 | Contracts, failures, cost proxy and replay documented; utility protocol below is designed only, no experiment or buyer threshold established. |
| **Total / 100** | **52** | **59** | **No 70 claim; no premium or commercial acceptance.** |

## Utility protocol (DESIGNED ONLY)

Before any utility trial, seal a schema/template-disjoint evaluation set, content
hashes and ground-truth verifier configuration. Separate diagnostic generation
tasks from training and evaluation roles. Compare the same unchanged base model
under no added data, the historical 46 rows, a future qualified 80 rows and a
size/token-matched control. Pre-register three seeds, token exposure, prompts,
training procedure if applicable, a primary semantic pass-rate metric, per-family
guardrails, paired confidence intervals and a buyer-approved minimum useful
effect. Required rights and compute authorization must precede execution.

This 15-row smoke is not a substituted 80-row treatment. No fine-tuning was run,
no lift or customer ROI was measured, and the required effect threshold is pending
the product owner. The existing business experiment framework remains the
implementation entry point; this prose does not create experiment results.

## Exact next acceptance actions

1. Implement and validate at least 19 more independent IDs to reach four per
   family. Expand further where eight genuinely nonduplicate records cannot be
   supplied by four questions; seeds/paraphrases do not fill that gap.
2. Add separately authored runtime fixtures for the nine legacy survivor tasks
   lacking them, preserving old version/run evidence. Investigate incorrect model
   outputs with the retained counterexamples before changing contracts.
3. Design missing selected HAVING/LIMIT/UNION outcomes and meaningful empty/negative
   results, and add realistic skew/sparsity. Validate before a new smoke identity.
4. Require the new diverse smoke and unchanged premium preflight to pass; then
   authorize one bounded qualification batch under a new identity. Do not resume
   this completed diagnostic run as a production dataset.
5. Freeze an actually qualified 80-row package, independently replay it, execute
   external overlap/split checks and obtain real human judgments and rights
   decisions. Only then consider release/utility approvals and a revised score.
