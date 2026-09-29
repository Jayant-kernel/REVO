# Verified Data Factory — Authoritative Base Idea

This file is the authoritative base for all future work on the Verified Data Factory.

Current score against this idea: **58/100**.

The source handoff is preserved verbatim below.

You are taking over an existing project called the **Verified Data Factory**.

Your job is to understand the entire project state from this document before making recommendations, writing code, or proposing new phases.

Do NOT assume earlier work is incomplete.
Do NOT restart completed phases.
Do NOT invent missing evidence.
Do NOT weaken verification standards to improve dataset yield.
Treat historical run artifacts as immutable evidence.

============================================================
0. PROJECT IN ONE SENTENCE
==========================

We are building a production system that generates synthetic analytical SQL using an open-weight/local LLM, executes the SQL in a locked-down sandbox, independently verifies correctness using executable Python oracles plus hidden/property/metamorphic/mutation testing, applies dataset-level quality selection, records complete provenance, and packages verified records into auditable dataset products.

Core principle:

"The model generates; executable infrastructure decides correctness. Dataset-level systems decide whether correct records are worth releasing. Provenance records exactly how the release was produced."

The business goal is eventually to sell useful, independently verified synthetic SQL/data records.

The system is NOT yet commercially ready.

============================================================

1. CURRENT BUSINESS / PRODUCT POSITION
   ============================================================

The strongest demonstrated property is:

* independently verified synthetic SQL
* executable correctness evidence
* deterministic task generation
* sandboxed execution
* independent Python oracles
* hidden fixtures
* property testing
* metamorphic testing
* mutation testing
* quality gates
* provenance
* reproducibility
* release validation

The current weakness is NOT primarily SQL correctness infrastructure.

Current weaknesses:

* dataset scale is still small
* instruction/semantic diversity is limited
* some family coverage is still weak
* funnel remains a known weaker family
* model supply-chain/legal governance is unresolved for the currently used checkpoint
* commercial release is therefore blocked

Do NOT claim:

* proven training-value superiority
* proven customer ROI
* commercial clearance
* broad 10-family coverage for the current production corpus
* model superiority based on informal comparison
* that a Golden record is automatically commercially usable

============================================================
2. MVP DOMAIN
=============

Domain:

Analytical SQL

Execution engine:

DuckDB

Current SQL families:

1. simple JOINs
2. multi-table JOINs
3. aggregation
4. CTEs
5. subqueries
6. window functions
7. temporal analysis
8. deduplication
9. customer retention
10. funnel/session analysis

Initial long-term dataset target:

~1,000 genuinely useful Golden records.

But the target is NOT "1,000 rows at any cost."

The real target is:

* verified Goldens
* novel Goldens
* broader semantic coverage
* broader SQL structural coverage
* schema diversity
* edge-case diversity
* instruction diversity
* measurable generation economics

============================================================
3. SYSTEM PHASES
================

PHASE 1 â€” Task Engine
PHASE 2 â€” Candidate Generation
PHASE 3 â€” Secure Execution Sandbox
PHASE 4 â€” Independent Verification
PHASE 5 â€” Dataset Quality & Audit
PHASE 6 â€” Provenance & Reproducibility
PHASE 7 â€” Data Products
PHASE 8 â€” Business / GTM / Customer Validation

ALL EIGHT PHASES ARE IMPLEMENTED.

The project is now in iterative production/validation rather than initial architecture development.

============================================================
4. PHASE 1 â€” TASK ENGINE
========================

Location:

src/verified_data_factory/task_engine/

Responsibilities:

* versioned YAML templates
* deterministic fixture generation
* task instance models
* template registry
* instruction rendering
* task validation
* canonicalization
* export
* API/CLI

Important design:

* deterministic task IDs based on canonical task identity
* task IDs use SHA-256 derived identity
* task metadata explicitly tracks edge cases
* semantic contracts are frozen/versioned
* no LLM involvement
* no verification logic in Phase 1

Important semantic contracts were explicitly defined for:

* joins
* aggregation
* CTEs
* subqueries
* windows
* temporal
* deduplication
* retention
* funnel

Task Engine is considered complete/frozen except for legitimate versioned changes.

There was later template/oracle registry drift because v1 templates were retired from generation while historical v1 oracles remained necessary for replay.

This was fixed by introducing explicit retired-version semantics.

Current intended contract:

RETIRED version:

* not generatable
* still historically replayable/readable

Do NOT restore obsolete v1 YAML templates merely to make equality tests pass.

============================================================
5. PHASE 2 â€” CANDIDATE GENERATION
=================================

Location:

src/verified_data_factory/generation/

Responsibilities:

* model/provider abstraction
* OpenAI-compatible local provider
* Qwen provider
* Devstral provider
* registry
* deterministic prompts
* parser
* batch generation
* FakeProvider for tests

CandidateSolution records:

* candidate ID
* task ID
* model
* revision
* prompt version
* generation schema version
* provider
* endpoint identity/hash
* raw response
* candidate SQL
* config
* timestamps/duration
* finish reason
* token metadata
* generation status/failure reason

IMPORTANT:
Candidate generation does NOT contain correctness judgments.

Prompt isolation is deliberate.

SolverContext exposes only:

* task ID
* dialect
* DDL
* instruction
* requirements
* prompt version

It must NOT expose:

* oracle answers
* hidden tests
* verifier metadata
* mutation operators
* quality metadata
* internal correctness information

Current prompt version:

sql-v2

Current main model configuration:

alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest

Current observed digest:

ollama-digest:a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4

Provider:
local Ollama OpenAI-compatible endpoint

Endpoint:
http://localhost:11434/v1

Current generation settings:
temperature 0.4
top-p 0.95
max tokens 2048

IMPORTANT:
The exact checkpoint above currently has:

supply-chain status:
REVIEW_REQUIRED

commercially_cleared:
false

Do not invent licensing information.

============================================================
6. PHASE 3 â€” SECURE EXECUTION SANDBOX
=====================================

Location:

src/verified_data_factory/sandbox/

Execution architecture:

* Docker
* SQL passed through controlled stdin/file mechanisms
* never shell-interpolated
* no host mounts
* no Docker socket

Current sandbox restrictions:

--network none
--read-only
--cap-drop ALL
--security-opt no-new-privileges
non-root UID 10000
tmpfs for temporary paths
CPU limit
512 MB memory/swap
PIDs 64
10 second timeout
10,000 row cap
1 MB result cap
64 KB stdout/stderr caps

DuckDB is locked down against:

* external access
* extension installation
* extension loading
* unsigned extensions
* filesystem access

Production sandbox image and digest are pinned.

Known caveat:

* Windows 11 + Docker Desktop is current primary environment
* Linux CI remains a separate environment validation concern

Never claim perfect isolation.

============================================================
7. PHASE 4 â€” INDEPENDENT VERIFICATION
=====================================

Location:

src/verified_data_factory/verification/

Pipeline:

execution gate
â†’ pure-Python oracle
â†’ comparator
â†’ hidden fixtures
â†’ properties
â†’ metamorphic tests
â†’ mutation campaign
â†’ performance evidence
â†’ VerificationResult

The oracle is NOT reference SQL.

Each family has an independent Python oracle.

Comparator semantics include:

* case-insensitive column handling
* explicit ordered/unordered semantics
* NULL == NULL
* strict boolean comparison
* numeric tolerance:
  absolute 1e-9
  relative 1e-7
* capped diff reporting

Hidden seeds are deterministic.

Property tests include:

* row-order invariance
* duplicate invariance for appropriate families
* irrelevant-event retention invariance

Metamorphic testing includes:

* permutation
* irrelevant customers for relevant join-ish families
* duplicate-event transformations
* other family-appropriate transformations

Mutation testing includes:

* family-aware operators
* universal WHERE-drop
* applicability rules
* infrastructure-fault exclusion

Mutation threshold:

0.90

IMPORTANT:
DO NOT LOWER THIS THRESHOLD.

Mutation score:

caught / decided

Infrastructure failures are excluded from mutation scoring.

If zero applicable mutants:

* state is NOT_APPLICABLE
* it is NOT an artificial 1.0
* it now requires explicit justification before a record can become Golden
* missing justification prevents Golden selection

This rule was introduced after an audit found a Pilot-001 outlier.

============================================================
8. PHASE 5 â€” QUALITY & AUDIT
============================

Location:

src/verified_data_factory/quality/

Phase 5 consumes:

* TaskInstance
* CandidateSolution
* ExecutionResult
* VerificationResult

It must NOT:

* rerun SQL
* regenerate candidates
* re-judge correctness

Quality assesses:

* semantic completeness
* ambiguity
* edge completeness
* schema consistency
* instruction/spec consistency
* execution/verification evidence
* duplicate rates
* diversity
* coverage
* difficulty
* contamination
* audit requirements
* failure breakdown

CRITICAL:

PASS != Golden automatically.

Golden selection applies:

* hard gates
* duplicate/survivor selection
* family quotas/selection rules
* deterministic selection

RecordQuality now contains:
mutation_justification

Known quarantine mechanism:
Pilot-001 contains one historical Golden outlier with:

* verification strength UNKNOWN
* zero applicable mutants
* null mutation score

It remains byte-unchanged historically.

It is now explicitly QUARANTINED and:
release_eligible=false

Do NOT modify historical Pilot-001 data.

Production-001 is NOT affected by this problem.

Production-001:
232/232 Golden are STRONG
232/232 have mutation score 1.0
zero applicable-mutant rows = 0

============================================================
9. PHASE 6 â€” PROVENANCE & REPRODUCIBILITY
=========================================

Location:

src/verified_data_factory/provenance/

Nodes include:

* TASK_TEMPLATE
* TASK_INSTANCE
* GENERATION_RUN
* CANDIDATE_SOLUTION
* EXECUTION_RUN
* EXECUTION_RESULT
* VERIFICATION_RUN
* VERIFICATION_RESULT
* QUALITY_RUN
* RECORD_QUALITY
* AUDIT_SAMPLE
* AUDIT_RESULT
* GOLDEN_SELECTION
* GOLDEN_RECORD
* DATASET_SNAPSHOT
* CONFIGURATION
* SOURCE_SNAPSHOT
* ENVIRONMENT_SNAPSHOT
* MODEL_SNAPSHOT
* ARTIFACT

Edges include:

* DERIVED_FROM
* GENERATED_BY
* EXECUTED_BY
* VERIFIED_BY
* QUALIFIED_BY
* AUDITED_BY
* SELECTED_BY
* INCLUDED_IN
* EXPORTED_AS
* USES_CONFIGURATION
* USES_ENVIRONMENT
* USES_MODEL
* USES_ARTIFACT

Content identity:

* canonical JSON
* domain-separated SHA-256
* volatile timestamps/run IDs excluded from content identity

Artifacts:

* streaming SHA-256
* secrets scrubbed
* environment metadata captured
* append-only JSONL
* lineage indexes
* BFS lineage traversal

Reproducibility is explicitly separated into levels.

Important:
same seed does NOT imply same model output unless serving guarantees it.

Current reproducibility philosophy:
record what is actually reproducible and explicitly label uncertainty.

============================================================
10. PHASE 7 â€” DATA PRODUCTS
===========================

Location:

src/verified_data_factory/products/

Product profiles:

* TRAIN
* PUBLIC_EVAL
* PRIVATE_EVAL
* BENCHMARK
* SAMPLE

The schema separates:

* MODEL_INPUT
* MODEL_TARGET
* METADATA
* PROVENANCE
* INTERNAL_ONLY

Canonical schema:

verified-data-factory/sql/1.0

Products support:

* JSONL
* typed Parquet
* deterministic sharding
* manifest
* SHA256SUMS
* dataset card
* preview
* release identity
* split policies

Selection and visibility are code enforced.

PUBLIC profile must reject:

* private
* internal
* restricted records

Release validation fails on:

* quarantine inclusion
* missing provenance
* unjustified zero-applicable mutation evidence
* sub-threshold mutation score
* missing contamination evidence
* unresolved commercial clearance

The release system must not silently pass incomplete audit inputs.

============================================================
11. PHASE 8 â€” BUSINESS / GTM
============================

Location:

src/verified_data_factory/business/

Implemented:

* business evidence model
* benchmark framework
* contamination validation
* experiment framework
* metrics
* economics
* customer feedback model
* pilot lifecycle
* GTM artifacts
* claim validator

Current business hypothesis status:

INSUFFICIENT_EVIDENCE

There is currently NO real:

* customer training experiment
* proven benchmark improvement
* production customer
* validated price
* proven ROI

Do not invent these.

============================================================
12. REAL RUN â€” PILOT-001
========================

Pilot-001:

* 100 tasks
* 10/family
* 300 candidates
* 300 generation successes
* 247 executions
* 53 execution errors
* 0 timeouts
* 101 PASS
* 199 FAIL
* 0 INCONCLUSIVE
* 49 Golden

Golden yield:
16.3% candidates

Important findings:
Several families initially had zero Golden.

Root causes were task-contract/interface problems, not verifier bugs:

* aggregation alias mismatch
* CTE timestamp/month representation
* temporal representation mismatch
* dedup partitioning semantics
* funnel zero-event customer handling

These were repaired through versioned templates and prompt contract changes.

Do NOT rewrite Pilot-001.

============================================================
13. REAL RUN â€” PILOT-002
========================

Pilot-002:

* 160 tasks
* 30 each for aggregation
* 30 CTE
* 30 dedup
* 30 funnel
* 30 temporal
* 10 controls

480 candidates.

Results:

* 480 generated
* 356 execution successes
* 124 execution errors
* 216 PASS
* 251 FAIL
* 13 INCONCLUSIVE
* 54 Golden
* 11.25% candidate Golden yield

Family results:

* aggregation: 77/90 PASS, 15 Golden
* CTE: 1/90 PASS, 1 Golden
* dedup: 90/90 PASS, 14 Golden
* funnel: 0/90 PASS
* temporal: 25/90 PASS, 24 Golden
* controls: 23/30 PASS

Major failure:
CTE and temporal still had model/dialect problems.
Funnel still frequently miscomputed customer inclusion.
Semantic duplicate rate was very high.

============================================================
14. MODEL INVESTIGATION
=======================

Compared operationally:

* Mistral Small 24B
* Devstral Small 24B

The exact production checkpoint selected was:

alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest

IMPORTANT:

The user chose to use Devstral operationally.

Do NOT claim a scientifically rigorous superiority result between models.

The selection was operational, not a controlled model-value experiment.

============================================================
15. TARGETED QUALIFICATION HISTORY
==================================

Earlier qualification cycles repaired CTE/temporal/window issues.

The most important final qualification is:

TQ-005

---

16. TQ-005 FINAL RESULTS

---

Run:

runs/targeted-qualification-005/

Configuration:
sha256:919937c31acfdca7b8d58e0bacca95274e4dbb705e84c3f6c2015c7dc9cab268

Model:
alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest

Observed digest:
ollama-digest:a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4

Prompt:
sql-v2

Generation:
temp 0.4
top-p 0.95
max tokens 2048

Sandbox:
pinned digest

DuckDB:
1.5.5

Mutation threshold:
0.90

Results:
246 candidates
246 executed
2 execution failures
0 timeouts
239 PASS
7 FAIL
0 INCONCLUSIVE
67 Golden

CTE:
90/90 PASS
27 Golden
mutation 1.0
zero dialect errors

Temporal:
90/90 PASS
30 Golden
mutation 1.0

Window:
30/30 PASS
10 Golden
mutation 1.0
partition-column-swap killed 30/30

Overall:
239 scored
mutation min = 1.0
mutation mean = 1.0
threshold remained 0.90
zero applicable-mutant rows = 0

TQ-005 recommendation:

READY

This means the repaired technical path is ready for another production batch.

IMPORTANT:
TQ-005 did NOT authorize production execution.
Production authorization remains a business/user decision.

============================================================
17. PRODUCTION-001 FINAL DATASET
================================

Production-001:

* 1,500 candidates
* 1,500 executions
* 1,500 verification attempts
* 820 PASS
* 177 INCONCLUSIVE
* 966 quality exclusions
* 232 Golden

Golden yield:
15.47%

Golden coverage:
7/10 families

Golden counts:

* aggregation: 23
* deduplication: 35
* funnel: 8
* multi-joins: 50
* retention: 45
* simple joins: 38
* subqueries: 33

Zero Golden:

* CTE
* temporal
* windows

VERY IMPORTANT:
Despite missing family coverage, the surviving Production-001 corpus itself is very strong.

Production-001 Golden census:
232/232 STRONG
232/232 mutation score 1.0
0 zero-applicable rows
0 unjustified rows
hard contamination count 0

Do not confuse:
"dataset coverage is incomplete"
with
"the existing Golden records are weak."

They are different claims.

============================================================
18. PRODUCTION-001 AUDIT REMEDIATION
====================================

Audit found:

1. Pilot Golden gate allowed one zero-applicable outlier
2. model/checkpoint supply-chain provenance unresolved
3. sample packaging did not expose per-row provenance sufficiently
4. coverage incomplete
5. yield modest
6. instruction/semantic diversity weak
7. dataset scale still small

Remediation is COMPLETE.

Added:

* mutation justification
* explicit quarantine
* ModelSupplyChain
* row manifest
* diversity metrics
* census
* audit report
* stronger release gates
* retired-version registry semantics

Production-001 historical bytes were untouched.

Production-001 row manifest:
232 rows
0 provenance violations

Production-001 diversity evidence:

* unique instructions: 7 / 232
* unique SQL: 44 / 232
* 6 schema identities
* semantic duplicate rate: ~0.862
* 12/14 edge categories

This means:
verification quality is strong,
but diversity is a significant dataset-value limitation.

============================================================
19. PRODUCTION-001 SUPPLY-CHAIN STATUS
======================================

Current checkpoint:

Huihui abliterated quant

Status:

REVIEW_REQUIRED

commercially_cleared:
false

Historical Production-001 artifact honestly records revision as unspecified because the handoff digest was not present in those historical run artifacts.

DO NOT backfill historical artifacts with newer knowledge.

A later live run observed the exact digest, but historical records should stay historically accurate.

Commercial release is currently BLOCKED.

This is a governance issue, not a SQL-correctness issue.

Do not claim:

* this model is commercially licensed
* redistribution is permitted
* commercial sale is allowed
  unless actual evidence establishes it.

============================================================
20. PRODUCTION-002 PREPARATION
==============================

Production-002 is PREPARED but NOT EXECUTED.

Planned batch:

500 tasks Ã— 3 candidates
= 1,500 candidates

Proposed allocation:

CTE: 100
Temporal: 100
Window: 60
Funnel: 80
Multi-joins: 40
Retention: 40
Simple joins: 20
Subqueries: 20
Aggregation: 20
Deduplication: 20

The allocation is intentionally validation/coverage-driven.

Projected Golden estimate:
~330 central

Planning range:
280â€“380

Do NOT use the old "~400" estimate.

The latest planning model uses:

* TQ-005 family evidence
* Production-001 family evidence
* audit holdback
* expected duplicate pressure
* known funnel weakness
* historical healthy-family rates

This is only a projection.

It is NOT a guarantee.

============================================================
21. PRODUCTION-002 ECONOMICS
============================

Observed TQ-005:

* 262.5 minutes generation
* 141k+ input tokens
* 48k output tokens
* 246 executions
* ~18 MB artifacts

Projected Batch 1:

* ~15â€“27 hours generation
* ~865k+ input tokens
* ~295k output tokens
* ~18 minutes sandbox estimate
* ~2 hours verification estimate
* ~60â€“110 MB artifacts

Central approximate generation time per Golden:
~290 seconds

Central estimate:
~80 hours of generation time per 1,000 Golden records

IMPORTANT:
These are compute/runtime projections, not final â‚¹ costs.

Unknown:

* actual machine power draw
* actual electricity cost
* hardware amortization
* exact verification wall time
* cost per novel Golden

The economics framework explicitly distinguishes:
OBSERVED
PROJECTED
ASSUMED
UNKNOWN

Never invent cost numbers.

Most important future economic metric:

COST PER NOVEL VERIFIED GOLDEN

not merely:

COST PER GOLDEN

because duplicate-heavy data has less marginal value.

============================================================
22. PRODUCTION-002 DESIGN PRINCIPLE
===================================

Production-002 should NOT optimize solely for Golden count.

It should optimize for:

* missing-family coverage
* semantic novelty
* instruction diversity
* SQL structural diversity
* schema diversity
* edge-case diversity
* verified Golden count
* cost per novel Golden

Track:

* exact duplicates
* semantic duplicate groups
* structural near-duplicates
* genuinely novel Goldens

Do not create an arbitrary single "diversity score."

Use raw, auditable metrics.

============================================================
23. CURRENT GATE STATE
======================

TECHNICAL PIPELINE:
READY

TQ-005:
READY

PRODUCTION-002:
PREPARED â€” NOT EXECUTED

TECHNICAL PRECHECKS:
PASS

COMMERCIAL RELEASE:
BLOCKED

SUPPLY CHAIN:
REVIEW_REQUIRED

COMMERCIAL CLEARANCE:
false

PRODUCTION EXECUTION AUTHORIZATION:
NOT GIVEN

Very important:
"technically possible"
does NOT mean
"commercially cleared"

Those are deliberately separate.

============================================================
24. HYPOTHESIS TEST ENVIRONMENT ISSUE
=====================================

File:

test_verify_hypothesis.py

It is not collected in the current Windows environment because the Hypothesis native DLL is blocked by AppControl policy.

This was independently demonstrated to be environmental:

* bare import fails outside repo
* fallback deterministic tests were added
* relevant invariant behavior is covered elsewhere
* nothing was silently disabled
* verification standards were not weakened

Do NOT describe this as "Hypothesis testing removed."

It remains a known environment-specific test-collection limitation.

When possible, validate it in a compatible environment/CI.

============================================================
25. REPOSITORY / TEST STATUS
============================

After remediation/prequalification:

* Unit: 559 passed / 0 failed
* Docker: 38 passed
* ruff clean on touched files
* format clean
* mypy-strict clean on touched files

Unrelated pre-existing lint may exist in:

* production/
* runs/ scripts
* mutations.py

Do NOT modify unrelated workstreams just to claim a cleaner diff.

============================================================
26. HISTORICAL DATA IMMUTABILITY
================================

Historical artifacts are evidence.

NEVER:

* rewrite Production-001
* rewrite Pilot-001
* delete failures
* delete execution errors
* replace old model metadata retroactively
* overwrite historical reports
* silently change historical task semantics

Add new artifacts instead.

============================================================
27. MAJOR LESSONS LEARNED
=========================

1. Model failures often initially looked like verifier failures, but root-cause analysis showed several were task-contract/interface problems.

2. Versioned task semantics matter.

3. Prompt/model correctness and oracle correctness must remain independent.

4. PASS is not automatically Golden.

5. Mutation testing is useful but must distinguish:

   * scored
   * not applicable
   * inconclusive

6. Zero applicable mutants require explicit explanation.

7. Production corpus quality must be evaluated at dataset level, not just row level.

8. A dataset can be technically excellent but commercially weak because of:

   * poor diversity
   * insufficient scale
   * governance problems

9. Provenance should be automatically attached to every row.

10. Do not confuse model selection made operationally with scientific evidence of model superiority.

============================================================
28. CURRENT REAL BOTTLENECK
===========================

The technical verification stack is now mature enough that another huge architecture effort is not justified.

The current real bottlenecks are:

A. Model/checkpoint governance
B. Dataset diversity
C. Dataset scale
D. Funnel performance
E. Production economics
F. Eventually proving customer/training value

============================================================
29. WHAT SHOULD HAPPEN NEXT
===========================

Before a large Production-002 run:

1. Persist exact model revision/digest into every NEW qualification/production run artifact.
2. Keep historical runs untouched.
3. Resolve or explicitly accept the supply-chain status.
4. If changing checkpoint, create a new model snapshot + config identity + run identity.
5. Run a tiny disposable smoke test.
6. Explicitly authorize Production-002.
7. Run Batch 1:
   500 tasks Ã— 3 candidates = 1,500 candidates
8. Measure actual:

   * Golden
   * novel Golden
   * family coverage
   * instruction diversity
   * semantic duplicate rate
   * SQL diversity
   * generation hours
   * verification hours
   * cost proxies
9. Recalculate projections after Batch 1.
10. Continue adaptively until the dataset is sufficiently broad.
11. Human audit.
12. Dataset snapshot.
13. Release validation.
14. Commercial/public release only if governance and release gates are satisfied.

============================================================
30. WHAT NOT TO DO
==================

Do NOT:

* start Production-002 automatically
* assume READY means authorized
* claim commercial clearance
* lower mutation threshold
* weaken the verifier
* add an LLM-as-judge
* mark INCONCLUSIVE as PASS
* assign artificial mutation scores
* backfill historical provenance
* overwrite historical runs
* regenerate Production-001 unless explicitly running a new versioned dataset
* optimize solely for Golden count
* invent cost assumptions
* invent licenses
* invent benchmark improvements
* claim customer ROI without evidence
* create arbitrary quality/diversity scores
* restart the architecture from Phase 0
* treat planning projections as actual measurements

============================================================
31. RECOMMENDED DECISION LOGIC
==============================

If the goal is a SELLABLE dataset:

Prefer:
approved/commercially defensible checkpoint
â†’ smoke test
â†’ Production-002
â†’ diversity/economics measurement
â†’ human audit
â†’ release

If the goal is TECHNICAL RESEARCH only:

The current checkpoint may be used only with explicit:

* non-commercial/review-required status
* provenance
* governance labeling

Never merge those statuses into one ambiguous dataset identity.

============================================================
32. IMPORTANT DISTINCTIONS
==========================

Maintain these distinctions at all times:

CORRECT
â‰ 
GOLDEN

GOLDEN
â‰ 
COMMERCIAL

TECHNICALLY READY
â‰ 
AUTHORIZED

MODEL SELECTION
â‰ 
SCIENTIFIC MODEL COMPARISON

HIGH MUTATION SCORE
â‰ 
HIGH DATASET DIVERSITY

HIGH GOLDEN COUNT
â‰ 
HIGH DATASET VALUE

LOCAL INFERENCE
â‰ 
ZERO TOTAL COST

REPRODUCIBLE TASK
â‰ 
DETERMINISTIC MODEL OUTPUT

============================================================
33. IF ASKED "WHAT IS THE PROJECT STATUS?"
==========================================

Answer approximately:

"The eight implementation phases are complete. The verification and provenance machinery is production-capable, and TQ-005 is READY. Production-001 contains 232 strongly verified Goldens, but it covers only 7/10 families and has substantial diversity limitations. Production-002 is prepared but has not been executed. Commercial release remains blocked because the current model checkpoint has unresolved supply-chain status. The next meaningful step is a checkpoint/governance decision followed by a controlled production batch, with novelty and economics measured explicitly."

============================================================
34. IF ASKED "SHOULD WE GENERATE 1,000 NOW?"
============================================

Do NOT answer with an unconditional yes.

First verify:

* checkpoint governance
* current config
* exact runtime model identity
* smoke test
* production authorization

Then generate adaptively.

The intended Production-002 Batch 1 is:
500 tasks Ã— 3 candidates = 1,500 candidates

Expected planning range:
~280â€“380 Golden
central estimate ~330

But actual observed results must replace projections after Batch 1.

============================================================
35. IF ASKED TO GIVE AN OPENCODE PROMPT
=======================================

Write a prompt that:

* references the exact current state
* preserves historical artifacts
* tells OpenCode what NOT to touch
* asks for deterministic evidence
* avoids speculative claims
* does not redo completed phases
* includes exact validation commands/results expected
* distinguishes preparation from execution
* uses versioned identities for meaningful changes

Do not casually suggest broad rewrites.

============================================================
36. CURRENT COMMAND / PRODUCTION INTENT
=======================================

The Production-002 runner is prepared.

The project supports a guarded production command pattern like:

factory production run 
--config <production-v2-config> 
--run runs/production-002 
--execute

DO NOT execute that command merely because it appears here.

Execution requires explicit user authorization after the checkpoint/governance decision.

============================================================
37. FINAL MENTAL MODEL
======================

Think of the project as five independent proof layers:

LAYER 1 â€” GENERATION
Can the model produce candidates?

LAYER 2 â€” CORRECTNESS
Can executable infrastructure prove/disprove the SQL?

LAYER 3 â€” DATASET QUALITY
Are the verified survivors diverse, useful, non-duplicate, uncontaminated, and auditable?

LAYER 4 â€” PROVENANCE / PRODUCT
Can every released row be traced, reproduced, validated, and packaged correctly?

LAYER 5 â€” BUSINESS VALUE
Does a customer actually value it, buy it, and/or does training/evaluation on it produce measurable benefit?

Current status:

LAYER 1 âœ…
LAYER 2 âœ…
LAYER 3 âš  still expanding
LAYER 4 âœ… technically implemented, commercial gate blocked by checkpoint governance
LAYER 5 âŒ insufficient evidence

Do not treat completion of Layers 1â€“4 as proof of Layer 5.

============================================================
38. TAKEOVER INSTRUCTION
========================

You are now the new AI responsible for continuing this project.

Before recommending any next action:

1. Respect all facts above.
2. Do not restart completed work.
3. Do not weaken any verification gate.
4. Treat historical artifacts as immutable.
5. Separate technical evidence from business assumptions.
6. Use the latest qualification evidence over obsolete pilot evidence when projecting current behavior.
7. Keep commercial governance separate from technical execution.
8. Prefer real measurements over forecasts.
9. Prefer diversity and novelty over raw row count.
10. Ask only when an essential unknown cannot reasonably be resolved from the repository/artifacts; otherwise make the best evidence-backed decision.

The immediate strategic goal is:

Build the next production batch into a broader, more diverse, economically measurable corpus while preserving the unusually strong verification/provenance properties already demonstrated.

The long-term goal is:

Produce a commercially defensible, independently verified synthetic SQL dataset whose value can eventually be demonstrated with external benchmark/customer/training evidence.

END OF HANDOFF
