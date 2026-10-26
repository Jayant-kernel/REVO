# Serial engineering program — verified local handoff, 2026-10-08

Latest continuation: [Automated pre-review V21 checkpoint](automated-quality-checkpoint-20261009.md).
Current full catalog is 10 FULLY_VERIFIED / 47 QUARANTINED (57 total), nine
qualified families; full regression 1544 passed and strict mypy 182 files.
Forward accepted rows remain zero and score NOT_COMPUTABLE. Sections below retain
the V17 and earlier historical checkpoints; their former stopping objectives
do not replace the continuous automated-quality assignment.

## Current two-family checkpoint, 2026-10-09

**Checkpoint achieved: 5 FULLY_VERIFIED contracts across 4 families, with all 57
contracts retained in the denominator and 52 still QUARANTINED.** The seven-stage
program is not complete. Accepted forward 80-record dataset: zero records.
Engineering-1.0: NOT_COMPUTABLE. Authorship remains **differential verification;
independent authorship unproven**.

Current authoritative snapshot:
`scratch/funnel_experiment/engineering/qualified-receipts-v17/`.
Its `readiness.json` records exact versions, artifact digests and admission results.
The post-regression full-catalog replay is
`scratch/funnel_experiment/engineering/catalog-two-families-v17.json`.
The hash-checked receipt summary is
`scratch/funnel_experiment/engineering/checkpoint-two-families-v17-summary.json`.

| Contract | Registered family | Status |
| --- | --- | --- |
| `sql.aggregation.fulfillment_sla_dashboard@1` | aggregation | FULLY_VERIFIED, freshly recollected |
| `sql.aggregation.manufacturing_line_scrap@1` | aggregation | FULLY_VERIFIED, freshly recollected |
| `sql.funnel.saas_activation_payment@2` | funnel | FULLY_VERIFIED, freshly recollected |
| `sql.joins.saas_paid_invoices@1` | simple_joins | FULLY_VERIFIED, newly implemented |
| `sql.subqueries.exists@2` | subqueries | FULLY_VERIFIED, newly implemented |

### Implementation and actual discrimination

The complete path was traced through public declarations, oracle/fixtures, profile
dispatch, rule/challenge/relation/mutation specifications, retained fuzz observations,
receipt replay, runtime candidate attribution and durable authority admission.
Version-only proof dispatch is replaced by explicit contract/version pairs in both
the public map and collector/proof paths. Unsupported pairs fail closed; EXISTS v1
does not borrow EXISTS v2 qualification or the SaaS funnel's version-2 proofs.
Runtime relations also use exact version-bound overrides.

Paid invoices now have 30 public obligations (21 semantic, 9 domain), ten distinct
valid semantic mutants covering the applicable ledger, 22 witnessed wrong queries,
three correct formulations, four distinct valid fixtures, two discriminating
relations and all 900 seed/index cases with 2700 alternative executions. Tests and
challenges cover account/invoice correlation, current active status, paid status,
calendar boundaries, excluded unmatched rows, both input bags, integer minor units,
zero/negative amounts, output schema/types and ordering. The reference inner join,
prefiltered-CTE inner join and lateral inner join preserve these semantics.

The public schema declares no uniqueness constraint on account IDs. A real SQL
reproducer returned four rows for two repeated account rows and two repeated invoice
rows while the old dictionary-based oracle returned two. The oracle now emits the
matching account-row/invoice-row bag, preserving zero and negative minor units;
its implementation identity advanced from 2 to 3 without changing contract version 1.
Canonical generated fixtures keep their relationship validation; schema-valid
adversarial SQL witnesses test unmatched/orphan behavior without inventing a public
key-uniqueness constraint.

EXISTS v2 has 28 public obligations (19 semantic, 9 domain), ten distinct valid
semantic mutants, 23 witnessed wrong queries, three correct formulations, four
distinct fixtures, two discriminating relations and all 900 cases/2700 executions.
All three formulations retain EXISTS: correlated filtering, an eligible-ID CTE with
EXISTS, and a lateral correlated EXISTS flag. Challenges additionally test absent,
wrong and inverted correlation, the exact 500 threshold, status/date boundaries,
existential versus join fanout/all-order/aggregate/latest-order interpretations,
orderless customers, customer-row multiplicity, irrelevant nullable country,
output types and ordering. The previous orphan-order and customer-row-bag repair
and EXISTS implementation identity 3 remain intact. Nullable `country` has an
executed DOMAIN_CONFORMANCE probe, not a false NULL-rejection waiver.

The two new random campaigns combine fixed targeted boundary/bag scaffolds with
seeded random extra rows, statuses, dates, cardinalities and amounts. Observed
behaviors are recomputed from actual retained fixture content, not generator labels.
All fourteen required behaviors per new contract were observed in all 300 cases
per seed (1, 43, 94001). This is targeted randomized differential conformance,
not distributional realism, training utility or universal equivalence proof.
Qualification cases are not accepted training-dataset rows.

Runtime canonical candidates earned STRONG through actual Phase 3/backend public
clause executions, retaining execution IDs/results. The capped campaign stays
incomplete; generic mutation ratios and unsupported transformations still do not
earn STRONG. No SQL-execution or admission mock replaces these checks.

### Evidence, regression and retained failures

Evidence root: `C:/Users/jayan/AppData/Local/Temp/opencode/`. Each command directory
below retains launch/post identities, exact command, terminal log, receipt, frozen
authorities and the 15-file paused-run guard.

| Command directory | Observed result |
| --- | --- |
| `revo-checkpoint-two-families-baseline-r1` | Fresh pre-edit replay: 57 total, 3 FULLY_VERIFIED, 54 QUARANTINED |
| `revo-checkpoint-two-families-join-red` | Expected failing SQL reproducer: actual 4 rows versus old oracle 2; failure retained |
| `revo-checkpoint-two-families-focused-r1` | 26 passed, 1 failed in 809.64s; both full new 900-case fuzz tests passed |
| `revo-checkpoint-two-families-focused-r2` | 47 passed, 2 deselected in 242.19s; only the two already executed full-fuzz cases deselected here |
| `revo-checkpoint-two-families-refresh-v17` | Five complete fresh bundles collected, replayed, promoted and admitted; matching source identities |
| `revo-checkpoint-two-families-full-r1` | **1487 passed, 7 warnings in 6470.96s (1:47:50)**; zero failures/errors/skips/deselections |
| `revo-checkpoint-two-families-mypy` | Strict mypy: 177 source files, no issues |
| `revo-checkpoint-two-families-ruff` | Scoped source/producer/test Ruff: all checks passed |
| `revo-checkpoint-two-families-catalog-v17` | Post-regression authoritative replay: 57 total, 5 FULLY_VERIFIED, 52 QUARANTINED |
| `revo-checkpoint-two-families-binding-v17` | Current receipt/source/runtime/authority bindings pass; original quarantine manifest unchanged; all three old v16 source bindings correctly rejected |

Full JUnit report:
`C:/Users/jayan/AppData/Local/Temp/opencode/revo-checkpoint-two-families-full-r1.xml`.
The seven full-run warnings concern `record_property` with the outer report's
default xunit2 format. Qualification's attributed child reports explicitly use
xunit1 and were parsed/replayed successfully. Warnings were retained.

Initial direct typing/lint checks found one cross-branch variable-name type conflict
and one import-format issue; both were repaired. Initial direct focused checks:
13 passed, 2 full-fuzz cases deselected. The first larger focused run's failure was
the existing SLA capped-runtime test returning before mutation, so its mutation
result was absent. Runtime tests now retain the complete normal/capped payloads and
explicitly require PASS before inspecting mutation. A direct rerun passed all five
runtime profiles, the subsequent focused run passed, and the full regression passed.
The original transient's exact cause remains unproven; it is not relabelled PASS
and no assertion was weakened. Further intermittent-backend diagnosis remains in
the reliability queue.

Strict export regression consumes current authoritative bundles. Therefore v17 was
collected after focused checks and source stability, before the full regression,
then replayed through the complete catalog afterward. No executable-source change
occurred between collection and the successful full regression/final replay.
Documentation added afterward is not retroactively part of the regression's byte
snapshot. All five live bundles are current against their locked dependencies;
v16 and earlier artifacts/history remain retained. Only exact historical
missing-evidence quarantines were evidence-resolved; the original manifest bytes
match the pre-edit baseline. Unrelated semantic quarantines remain blocked, and
renewal/journal/index/stale-input rejection regressions passed in the full suite.

No unresolved semantic finding remains for these two profiles. This narrower
checkpoint leaves 36 other engineering-profile candidates and 16 historically
identified semantic/forward-schema cases unqualified. No commits, pushes,
dependency installations, paid services, provider/model calls or large dataset
generation were performed; the current checkout remains local `main`.

### Ordered remaining queue

1. **The six missing families.** Next executable profile: `sql.joins.logistics_final_leg@1`
   (multi_joins), then `sql.cte.order_line_reconciliation@1` (cte),
   `sql.windows.media_previous_play@1` (window_functions),
   `sql.temporal.clinic_weekly_visits@1` (temporal),
   `sql.dedup.education_grade_revisions@1` (deduplication), and
   `sql.retention.saas_repeat_payment@1` (retention). Inspect each public contract
   before implementing the same seven-category qualification path.
2. **Broader business-task coverage.** Complete the remaining well-specified
   engineering-profile queue across domains, materially different instructions,
   schema roles, constructs and edges; a single contract per family is insufficient
   for the forward product.
3. **Unresolved semantic cases.** Retain all sixteen IDs listed in the checkpoint
   summary. Establish exact correlation/business keys, measure source, event
   selection, order/ties/windows, unmatched and NULL behavior where the generic
   schema does not state them. Do not reinterpret generic arithmetic as the named
   business objective. Historical logistics-v2 and ranked-v1 boundaries also remain
   explicit; no unrelated quarantine was cleared by this checkpoint.
4. **Remaining export/recovery checks.** Broaden publication interruption/corrupt
   inventory/delivery-boundary coverage beyond the already executed reservation and
   validation kills, retain content-bound role/membership/relocation proof, and
   investigate intermittent backend early aborts. Current strict JSONL/Parquet,
   tamper/relocation and process-recovery regressions passed.
5. **Realism testing.** Execute targeted skew, sparsity, fanout and long-history
   profiles, genuine minimized counterexamples and boundary/cardinality inventories
   against the current source. Old catalog-wide realism diagnostics predate this
   snapshot and are not current-source certification.
6. **Accepted forward dataset.** Only after sufficient qualified diversity, build
   exactly 80 accepted records/eight per family, with >=40 materially different
   instructions, >=10 schema roles, >=5 domains, <=12 rows/schema and complete
   construct/edge/duplicate/lineage isolation. Currently accepted records: zero.
7. **Final certification/scoring.** Produce every frozen criterion-specific metric
   with complete denominator/dependency authority, final protocol smoke/resume and
   dataset/export certification, then rerun affected final checks. Keep
   engineering-1.0 NOT_COMPUTABLE until those inputs exist; retain historical 52/100
   and training utility NOT_MEASURED. Do not substitute qualification counts for
   criterion metrics or training rows.

## Prior continuation snapshot, 2026-10-09 (v16 history)

The sections below retain the pre-SLA regression history. The current admitted
qualification snapshot is now `scratch/funnel_experiment/engineering/qualified-receipts-v16/`:
fulfillment SLA v1, manufacturing scrap v1 and SaaS activation/payment v2.
Fresh full-population reconciliation reports **57 contracts: 3 FULLY_VERIFIED,
54 QUARANTINED** in `scratch/funnel_experiment/engineering/catalog-current-20261009-v16.json`.
The seven-stage program remains incomplete, the forward accepted dataset remains
empty, and engineering-1.0 remains NOT_COMPUTABLE.

SLA retains ten semantic-clause discriminators, twenty witnessed wrong queries,
three correct formulations, executable nullable-domain conformance, two
discriminating relations, distinct fixtures and the full three-seed campaign.
Every v16 bundle retains all seven categories, 900 random cases and 2700 actual
correct-formulation executions. Promotion preserves the original quarantine
manifest and journals only an exact missing-evidence resolution after full replay.
Renewal carries that resolution onto the new supporting members; stale sources,
unrelated semantic quarantines and inconsistent journal/index state deny admission.

The continuation evidence directories under the temporary evidence root are:

- `revo-program-20261009-sla-resolution-r2`: **88 passed, 1 deselected in 969.29s**.
  The deselected standalone full-fuzz case is covered by two complete 900-case
  collections in the authentic resolution/renewal test. Only the temporary copy's
  Git metadata lookup uses the actual parent checkout identity; detailed receipt
  checks, SQL execution and authority transactions run normally.
- `revo-program-20261009-stage5-refresh-v16`: three fresh complete bundles collected,
  promoted and admitted through the actual repository authority, with matching
  launch/post identities and frozen/15-file guards.
- `revo-program-20261009-catalog-v16`: all 57 latest contracts reconciled, matching
  launch/post identities and frozen/15-file guards.

Strict mypy passed 174 source files; scoped Ruff passed the changed producer,
observation policy and regression test. The initial resolution test attempt is
retained as `revo-program-20261009-sla-resolution-r1` (87 passed, one failure caused
by the copied fixture lacking Git metadata). A prior direct test command timed out;
it is not counted as passing evidence. The historical 1449-test regression below
does not certify the later SLA changes; a new final full regression is still due.

The previously pending Stage 4 publication-kill probe also passed at both
post-reservation and post-validation boundaries: no premature final path,
conservative reservations retained, and same-role recovery validated. Evidence:
`revo-program-20261008-publication-kill` and the retained `publication-kill-probe.json`
under `revo-strict-parquet-20261008`. This covers those two boundaries, not every
possible publication failure.

Producer and consumer remain **differential verification; independent authorship
unproven**. The next engineering work is the remaining contract-profile queue,
then the diverse accepted forward dataset and criterion-specific score inputs.

## Historical pre-SLA snapshot

The current software snapshot has a passing full regression and a genuine
two-contract qualification/export path. **The full seven-stage program is not
complete, no 80-record forward dataset is accepted, and engineering-1.0 remains
NOT_COMPUTABLE.** Historical commercial assessment remains 52/100. Training value,
rights approval, human SQL review and buyer acceptance remain NOT_MEASURED/open.

All changes are local on `main`; HEAD stayed
`22ecfeb4e8a92c7c4909c11197dee1e455c4f500`. No commits, pushes, installations,
downloads, paid services or actual model/provider network calls were performed.
All frozen measuring assets and 15 paused premium-run files passed the guard.
The current stage ledger is `scratch/funnel_experiment/engineering/PROGRAM-LEDGER-20261008.md`.

## What changed

Detailed qualification replaced the legacy summary-producing entry point. Each
supported bundle retains public clauses/schema domains, attributed test XML,
wrong/correct SQL and typed executions, discriminating relations, mutation
attribution, fixture diversity and all 900 per-seed fuzz cases. Source, consumed
input and runtime/package identities are locked. A single durable journal event
commits all seven categories; the deterministically materialized index must match
the journal. Kernel locks serialize writers. Snapshot-qualified evidence IDs and
explicit supersession preserve earlier attempts. Current accepted snapshot:
`scratch/funnel_experiment/engineering/qualified-receipts-v15/`.

Runtime public-rule coverage executes the actual canonical candidate and its
clause-specific transforms through the Phase 3 backend, retaining actual
execution IDs/results and fixture attribution. This narrowly supports SaaS
activation-payment v2 and manufacturing scrap v1; unproven alternative
formulations/generic operator campaigns remain UNKNOWN. Offline qualification
replay lives under `verification/qualification/`, preserving the existing module
imports/instrumentation boundary. Pure rule specifications no longer execute
candidate SQL inside the runtime verifier. Producer and consumer share logic:
**differential verification; independent authorship unproven**.

The durable runner now checks exact FAIL/visible-diagnostic eligibility, approved
arm/provider pairing, exact integer versions/slots/seeds/retries, logical-slot
seed stability and retry progression. Evaluation-start is fsynced before actual
execution; interrupted starts spend the two-attempt budget. Saved SQL is reused,
indeterminate generation is not silently repeated, and kernel locks release on
process death. Four-arm reports distinguish new physical calls, reused logical
results, cumulative calls/evaluations and new/cumulative unique rescues.

Strict exports now use a fixed factory registry identity, locked role inventory,
private staging and final rename only after validation. Acceptance binds actual
source records/snapshot membership, explicit exclusions, exported content, current
qualification, SQL replay and registry/role reservations. Replay source/input
assets are bundled with `validate_engineering.py`; an absolute checkout hint is
not the replay mechanism. Recomputed checksum metadata does not validate changed
SQL. Historical consumed JSON remains opaque input, rather than being mistakenly
expanded into obsolete live dependencies. Windows extended-length IO supports
nested replay bundles without OS-policy changes. Failed private staging and
conservative reservations are retained for diagnosis/same-role recovery.

The profile pass exposed an EXISTS oracle crash on qualifying orphan orders and
collapse of duplicate customer rows. A real SQL reproducer failed first; the
oracle now emits the customer-row bag and ignores orphan orders, with affected
oracle implementation identities advanced to 3. Latest logistics v2 measurements
use explicit v2 reference SQL, while legacy diagnostic mappings remain historical.
The original scope-drop survivor is retained with a newly executed counterexample,
not erased or described as universal equivalence.

Quality/provenance unit fixtures now explicitly model accepted upstream inputs
and mark them `MODELED_UPSTREAM_INPUT_NOT_QUALIFICATION`. They are neither actual
runtime qualification nor production dataset material. Production strength gates
remain unchanged. Tests expecting generic kills to earn STRONG were corrected to
assert UNKNOWN and incomplete public coverage. Typed comparison audits still
check every production call, including the two added runtime calls.

## Current evidence

All directories below are under `C:/Users/jayan/AppData/Local/Temp/opencode/`.
Each command directory contains `launch.json`, `post.json`, `terminal.log` and
`receipt.json` with exact command/times/status and matching relevant source hashes.

- `revo-program-20261008-full-regression-r2`: **1449 passed in 2659.23s (44:19)**,
  zero failures/errors/skips, launch/post match. Parsed JUnit is alongside it as
  `revo-program-20261008-full-regression-r2.xml`.
- `revo-program-20261008-stage2-refresh-v15`: fresh complete bundles collected,
  replayed, promoted and admitted for both supported contracts. Each full fuzz
  category retains 900 cases and 2700 real correct-alternative executions.
- `revo-program-20261008-stage4-acceptance-r3`: actual strict JSONL export,
  checksum-recomputed wrong SQL rejection and actual relocated bootstrap replay
  passed. The same case passed again in the final full regression.
- `revo-program-20261008-strict-parquet`: actual qualified strict Parquet row,
  typed round trip, standalone validation and bundled bootstrap replay passed;
  source identities matched. Probe data: `revo-strict-parquet-20261008/probe.json`.
- `revo-program-20261008-catalog-reconciliation`: **57 contracts; 55 QUARANTINED,
  2 FULLY_VERIFIED**. Durable report:
  `scratch/funnel_experiment/engineering/catalog-current-20261008.json`.
- `revo-program-20261008-realism-r1`: all 57 have at least three observed passing
  cardinalities. Durable report:
  `scratch/funnel_experiment/engineering/realism-current-20261008-r1.json`.
  This does not establish complete business qualification or distributional utility.
- `revo-program-20261008-final-smoke` and `revo-program-20261008-final-resume`:
  actual evaluator/stub generation only; 18 fresh physical calls, resume 0 new
  calls/evaluations and 18 cumulative; three initial successes/three cumulative
  rescues per provider. Prompt scan passed; model network calls 0. Raw immutable
  reports: `revo-final-four-arm-20261008/report-000001.json` and `report-000002.json`.

Final package typing: `python -m mypy src --strict` passed **173 source files**.
Scoped Ruff passed the changed source, producer and test files. The full regression
snapshot tracked-diff SHA256 was
`48e42e2368b84689216eab96ea7430c41908dcb44bde6dcfeab96feb30f7e081`;
full untracked/per-file content identities are in its launch/post manifests.
This handoff is added documentation, not a claim that its later documentation
bytes were included in the earlier regression snapshot.

## Retained failures and boundaries

The initial full run had 32 failures, 1396 passes and 21 setup errors. Most were
obsolete upstream-STRONG unit-fixture assumptions; runtime/qualification boundary
and version/count assertions were also repaired. R1 had one failed strict fresh
sandbox replay and 1448 passes. An observational rerun passed without substituting
outcomes; r2 subsequently passed the full suite. The exact origin of intermittent
runtime failures remains unproven; their records are retained, not recast as PASS.

V10 collected both full bundles but was refused before publication because
contract-folder-only evidence IDs collided. V11 and later use snapshot-qualified
IDs. Earlier v9–v14 are retained/superseded; no old receipt hashes were merely
refreshed to manufacture freshness. The interrupted acceptance run r2 remains
incomplete. Subsequent resumed acceptance used a new command directory.

Stage 4 still needs broader
process-kill publication/recovery tests. Schema/AST fingerprints are conservative
screens, not semantic-equivalence proof or a global cross-factory registry.
Declared key/relationship roles are retained where present; arity-based relationship
screens do not establish graph equivalence.

## Remaining work and human decisions

The catalog still has 55 unqualified contracts. Of the historical queue, 39 have
named-oracle evidence candidates requiring actual profile implementation: granular
public maps, three substantive correct formulations, 20 witnessed wrong queries,
three distinct valid mutants/full applicable rule coverage, two discriminating
relations, four fixtures and 300 valid cases for each required seed. **These are
remaining engineering tasks, not claimed human-only blockers.** Continue in family
batches without changing the population denominator.

Sixteen generic semantic/forward-specification cases need contract-by-contract
disposition. Where the public intent is explicit, implement its forward business
model and prove it. Where a named objective implies matching/window/latest/funnel
semantics absent from its generic event-ledger schema, the business owner must
specify correlation keys, source-of-measure, event selection, tie/order/window
rules, and unmatched/NULL behavior. Do not infer those from the generic aggregate
oracle or admit renamed arithmetic as semantic diversity. The full catalog report
retains exact contract IDs and public obligations; historical plan evidence is
`phase9-diversity-and-blocked-plan-r1.json`.

For the forward dataset there are currently **zero accepted new records** in an
80-record release. Only two qualified families cannot supply ten families,
40 materially different instructions, ten schema roles/five domains, all required
constructs/edges or duplicate/lineage acceptance. Seed-only variations and the
historical seven-family 232-row file cannot solve this. Build new qualifying
forward contracts before attempting that dataset. The one-row strict probes are
engineering acceptance cases, not a deliverable 80-row training product.

Metric preflight rejects partial/duplicated/stale populations and recomputes the
supported diagnostic catalog counts. Those counts are explicitly **not frozen
criterion-specific metrics**. Complete metric producers/inputs are still needed;
no scorer invocation or earned engineering score is justified. No unsupported zero
was supplied, the scorer/rubric/thresholds stayed unchanged, and 86 was not forced.

Smallest next actions: complete the remaining crash acceptance cases, implement
the next well-specified family qualification batch, resolve precise semantic gaps,
then build/accept the composed forward dataset and complete all criterion-specific
measurement. Any relevant source edit invalidates v15 and requires new immutable
qualification and affected certification before final scoring.
