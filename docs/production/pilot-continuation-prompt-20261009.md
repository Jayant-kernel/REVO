# Continuous implementation prompt: verified SQL pilot

Copy the following prompt into the AI working in this repository.

```text
You are implementing the next continuous engineering program for the Verified
SQL Data Factory at C:\Users\jayan\OneDrive\Desktop\Revo.

MISSION
Take the current five-contract checkpoint to a reproducible internal SQL
evaluation pilot, while extending and preserving the factory's correctness.
Execute the work in small verified steps, repair technical blockers, record the
evidence, and continue automatically to the next available task.

The proposed MVP is an executable DuckDB business-correctness evaluation pack
for SQL-agent developers, centered on subscription billing and operational
reporting. Include queries that execute yet return the wrong business answer,
with fixtures that expose the mistake. Preserve the full original factory roadmap.

Do not stop merely because one profile or stage passes. Continue until the pilot
milestones below are verified or all remaining work depends on explicit external
decisions. Do not substitute a guessed completion percentage for acceptance.

STARTING CONTEXT
Read applicable AGENTS.md instructions, README, architecture, task semantics, and:
- docs/research/sql-pilot-mvp-and-continuation-20261009.md
- docs/production/engineering-program-handoff-20261008.md
- scratch/funnel_experiment/engineering/PROGRAM-LEDGER-20261008.md
- scratch/funnel_experiment/engineering/checkpoint-two-families-v17-summary.json
- scratch/funnel_experiment/engineering/catalog-two-families-v17.json
- scratch/funnel_experiment/engineering/qualified-receipts-v17/readiness.json
- docs/production/engineering-rubric.md
- configs/package_a/engineering-rubric.json
- docs/licensing.md and relevant generation/provider policies

Confirm the current tree and latest artifacts instead of assuming these are still
latest. The last inspected baseline was:
- v17: five fully qualified contracts across four families, 52 quarantined / 57.
- Qualified: fulfillment_sla_dashboard@1, manufacturing_line_scrap@1,
  saas_activation_payment@2, saas_paid_invoices@1, and exists@2 (use their full
  registered IDs from the catalog).
- Full regression: 1,487 passes, seven reporting warnings, no failures/skips.
- Strict mypy: 177 source files; scoped Ruff and frozen-file guards passed.
- 36 remaining named-oracle engineering candidates, 16 semantic/schema cases.
- Zero accepted forward 80-record rows; engineering score NOT_COMPUTABLE.
- Retained SLA runtime early abort: exact cause unproven despite later passes.
- Differential verification; independent authorship unproven.
The previous 232-row dataset and seven-record original-fixture smoke are history,
not the new pilot, a private held-out benchmark, or current full qualification.

WORKING LOOP AND LEDGER
Create a scoped durable plan and task ledger in an appropriate new repository
document. Record task ID, acceptance condition, dependencies, status, source
identity, commands, evidence paths, failures, and next action. Reuse project tools.
For every unit: inspect -> reproduce/specify -> implement -> focused verification
-> integrate -> record -> continue. Do not request routine permission to proceed.
If a test fails, diagnose its cause, make an evidence-backed repair, and reverify.
Preserve failed attempts. Do not weaken assertions to obtain a pass.
If one item is blocked, record why and work on independent items. After repeated
failure of the same approach, change the diagnostic approach; avoid blind retries.
Checkpoint before context/session boundaries and resume from the ledger. A prompt
does not guarantee a process survives session limits; leave a precise resume action.
Keep regular concise progress updates with evidence and unresolved uncertainty.

MILESTONE 1: RELIABILITY BASELINE
Inspect the retained SLA early abort, execution payloads, limits and container
lifecycle. Use bounded reproductions to investigate it. Repair a proven cause and
add regression coverage. If it remains unexplained, retain the limitation and
prevent affected unresolved behavior from being silently certified for the pilot.
Do not conceal failures by increasing limits or adding unaccounted retries.
Preserve invoice/customer-row multiplicity, orphan-order behavior, types, numeric
precision, ordering, durable attempts, and quarantine/history protections.

MILESTONE 2: TARGETED ARCHITECTURE
Make each pilot task's business meaning explicit: entity/relationship keys,
measurement units, duplicates, NULLs, time boundaries, ordering, ties, exclusions,
and expected output. Never infer uniqueness from an ID-shaped column name.
Use a consistent profile interface and explicit contract/version registry for
public rules, fixtures, references, challenges, observation policies and evidence.
Consolidate demonstrated duplication/drift hazards; avoid a wholesale rewrite.
Keep the Python oracle and substantively different correct SQL implementations.
Create challenge cases from public requirements; document shared dependencies.
Agreement among correlated implementations is not proof of independent authorship.
Freeze separate development, disclosed-showcase and private-evaluation roles.
Respect the existing stricter lineage/schema/registry isolation rules. Cases used
to debug or tune become development/regression material and must leave holdout.

MILESTONE 3: QUALIFY THE MISSING FAMILIES
Start with sql.joins.logistics_final_leg@1. The contract refers to the declared
final_leg_id, not an invented latest-by-time rule. Then examine these queued tasks:
- sql.cte.order_line_reconciliation@1
- sql.windows.media_previous_play@1
- sql.temporal.clinic_weekly_visits@1
- sql.dedup.education_grade_revisions@1
- sql.retention.saas_repeat_payment@1
Verify the registered contracts before implementation. Resolve clearly specified
engineering work. Document genuinely missing business decisions and proceed with
another specified task if needed. Semantic changes require explicit new versions.
Target at least one currently qualified contract in all ten existing SQL families.
This is a breadth milestone, not full-catalog qualification or an earned score.

For every profile, retain all seven categories: rules, named_tests, relations,
mutation, challenge, fixture_diversity, fuzz. Meet the unchanged frozen thresholds:
complete applicable public/schema rules; >=4 distinct valid fixtures; >=3 correct
SQL formulations; >=20 witnessed wrong queries; >=3 valid non-equivalent semantic
mutants with applicable rule coverage; >=2 executed discriminating relations;
300 valid random cases per seed 1, 43, 94001 and required observed behaviors.
Count behaviors from actual data. Invalid SQL/infrastructure errors are not
semantic kills. Test supported candidates on the real runtime path, not only the
offline receipt path. Keep unsupported transformations UNKNOWN where required.

MILESTONE 4: REALISM AND DISCRIMINATION
For proposed pilot tasks, execute applicable skew, sparse/empty, join fanout,
duplicate/tie, missing-relationship, NULL, zero/negative, and time-history cases.
Use domain-valid constraints; do not assume undisclosed keys or impossible rules.
Demonstrate plausible wrong SQL that passes an ordinary fixture but fails a
discriminating fixture where feasible. Also verify correct alternative formulations
are accepted. Report false acceptance and false rejection with explicit denominators
on the executed challenge population. These are bounded measurements, not universal
correctness or model-accuracy claims. Minimize counterexamples where useful.

MILESTONE 5: FREEZE A SEPARATE PILOT SPECIFICATION
Create a versioned pilot specification before selecting generation outcomes.
House target: 12 accepted disclosed showcase records for 12 materially different
business questions, >=6 represented SQL families, >=4 meaningful schema designs,
and >=2 relevant business domains. At most one record per task/intent lineage.
Prefer billing/operations coherence. Add and qualify original contracts if needed.
Renamed tables, seed/literal variations, and paraphrases do not count as diversity.
Keep genuinely withheld evaluation material under a separate permitted lineage.
Do not reuse the disclosed showcase as an unseen benchmark.

Every selected row needs current contract admission and complete candidate-level
verification/provenance. Include at least one witnessed wrong-query counterexample
and a second correct formulation per showcase record, while meeting all stricter
contract-level requirements. Preserve origin labels for model-generated answers,
reference-authored answers, deliberate mutants, and observed model failures.

The pilot is a new, explicitly scoped acceptance profile. Keep the existing strict
80-record target and validator intact. If the product layer cannot represent an
internal pilot, implement a separate, tested profile with manifest-bound criteria
and rejection of attempts to label it as the premium 80-row release.
Do not quietly route an ineligible pilot through a weaker fallback export.

MILESTONE 6: BOUNDED REAL GENERATION
This prompt authorizes a small local generation experiment using an already
installed model that passes the repository's existing usage/rights preflight.
Inspect available providers and exact model identity first. No paid/cloud provider
calls, credential changes, model downloads or dependency installations.
Run one model worker at a time, at most 120 generation attempts and at most two
hours of generation wall time. Freeze task allocation, configuration, sampling,
retry accounting and stop conditions before the batch. Use normal production gates.
If limits are reached, retain partial results and report the deficit; do not
silently reset budgets or keep generating until the results look favorable.
If no eligible installed model is usable, record a blocking dependency and finish
independent engineering/reference-pack work. The real-generation milestone remains
incomplete; stub execution must not be substituted for model generation.
Never put reference answers, hidden fixtures or private evaluation material into
generation prompts. Keep complete prompts/responses, all attempts, errors,
rejections, timing, and provenance. Report acceptance yield and cost per novel
eligible task separately from curated-sample quality.

MILESTONE 7: SELECT, PACKAGE AND REPLAY
Filter by correctness/evidence eligibility before diversity selection. Preserve
selection rules and reasons for every inclusion/exclusion. Do not pad shortages.
Package each record with a plain-language question, schema/column descriptions,
SQL, fixtures, expected typed results, relevant edge cases, evidence links,
contract/model identities, and execution instructions.
Provide a documented sandboxed replay entry point, pinned environment dependencies,
checksums, provenance, a dataset card, scope/limitations and a machine-readable
report. Separate learner inputs from answers and private evaluation assets.
Test actual relocation to a clean environment, all selected records, typed round
trips, membership, tampering rejection, and relevant interruption/recovery paths.
Keep essential evidence durable in the repository's evidence conventions, not
solely in temporary OS folders. Preserve identities when copying retained evidence.
Report per-row results and denominators. Twelve passes cannot establish population
accuracy or training uplift. Add a concise reviewer guide and feedback form.

MILESTONE 8: CERTIFY AND HAND OFF
Run focused checks during development. Collect immutable fresh bundles after
coherent batches stabilize; refresh all invalidated supported profiles, then run
full regression against the admitted snapshot. Recollect again if relevant code
changes. Finish strict typing, scoped lint, fresh full-catalog reconciliation,
runtime smoke, export replay, authority consistency and all frozen-file guards.
Preserve the scorer/rubric/thresholds and all paused/historical runs.
Do not invoke the frozen scorer with substituted diagnostic counts or invented
zeros. Produce criterion-specific measurements only where their actual full
population and execution requirements are met; otherwise retain NOT_COMPUTABLE.
Do not shrink the frozen denominator to the selected pilot. Preserve all remaining
catalog and 80-record work in the roadmap.

Final report must give observed completion of each milestone, current qualified
contracts/families, accepted pilot count, all tests/failures, unresolved findings,
model usage/budget, selection yield, replay evidence, and exact remaining work.
Classify outcome: VERIFIED_INTERNAL_PILOT, PARTIAL, or BLOCKED, with reasons.
External-share eligibility is a separate field. Unknown model/output distribution
rights require an owner decision; never manufacture a clearance or reviewer vote.
Use: 'Technical evaluation sample - automated verification completed; human review
pending' only if the automated pilot gates actually pass.

AUTONOMY BOUNDARIES
Resolve ordinary technical defects without asking for routine approval. For missing
business intent, unavailable permitted model access, rights decisions, spending or
external communication, document the exact dependency and continue unrelated work.
Ask only the indispensable final question when no meaningful independent work
remains. Never claim a blocker was solved by weakening requirements.
No commits, pushes, destructive Git operations, publishing, emails, or company
contact. Do not fabricate customers, model improvement, independence, or a 90+ score.

Execute this program rather than stopping after a plan or the first new profile.
The terminal objective is verified pilot evidence and an honest remaining-work
ledger. It is not an unsupported claim that 80% of the entire factory is complete.
```
