# Phase 4 — Independent Verification Engine

Status: **implemented**. Given `(TaskInstance, CandidateSolution,
ExecutionResult)`, determines whether the candidate satisfies the task
specification using executable, deterministic evidence. No LLM judge
exists anywhere. Inputs are never mutated; candidate SQL runs only
through Phase 3.

## 1. Verification architecture

```text
TaskInstance + CandidateSolution + ExecutionResult
        │ gate on execution outcome (faults -> FAIL, infra -> INCONCLUSIVE)
        ▼
oracle_registry.get(template_id, version)  ->  Python oracle(requirements, rows)
        │ ExpectedResult{columns, rows, order}
        ▼
comparator.compare  ->  mismatch -> FAIL (early exit, no wasted runs)
        │ hidden fixtures (derived seeds, backend execution)
        ▼  any fail -> FAIL (overfit); any infra gap -> INCONCLUSIVE
properties (family-justified)  ->  any fail -> FAIL
        ▼
metamorphic relations (family-justified)  ->  any fail -> FAIL
        ▼
mutation campaign  ->  weak suite -> INCONCLUSIVE (never FAIL)
        ▼
performance evidence (never a verdict)  ->  VerificationResult
```

Stages are individually testable (`compute_oracle`, `compare`,
`run_hidden_checks`, `run_property_checks`, `run_metamorphic_checks`,
`run_mutation_checks`).

## 2. Oracle independence

Oracles take only `(requirements, fixture rows)` — structural, asserted by
static tests (no candidate/execution/model identifiers, no database
imports, exact 2-parameter signatures). Reference implementations are pure
Python over the task semantics, never SQL (no shared bug class with the
candidate's DuckDB execution), never candidate-derived. The comparator sees
only `ExecutionResult.result_data`.

## 3. Oracle registry

`(template_id, version) -> (fn, oracle_version, strategy)`; all 10 Phase 1
templates registered at oracle v1 with strategies matching the template
`oracle_spec` (consistency-tested). Unknown pairs raise — no generic
fallback. Version bumps required on semantic change.

## 4. Result comparison

Strict column names (case-insensitive) + order; unordered results compare
as tolerance-aware multisets; ordered results must be sorted per order
keys (ties in any order) + multiset-equal. NULL==NULL; booleans
type-strict; numerics (incl. Decimal-serialized strings) with
abs 1e-9 + rel 1e-7 (configurable, sane); dates/timestamps as strings.
Differences bounded to 3 rows.

## 5. Hidden testing

`hidden_cases` (default 3) fixtures from
`SHA256("{task_seed}:{config_version}:{index}")`; rebuilt via Phase 1
public API, executed via backend, compared with the oracle. Seeds recorded,
contents never stored. Same config twice → identical hidden sets (tested).

## 6. Property testing

Registry family -> checks, all backend-executed: ROW_ORDER_INVARIANCE (all
10 — outputs fully ordered), DUPLICATE_INVARIANCE (dedup/funnel),
IRRELEVANT_NONQUALIFYING_EVENT (retention). Unknown families raise.

## 7. Metamorphic testing

ROW_PERMUTATION (all), ADD_IRRELEVANT_CUSTOMER
(simple/multi/cte/subquery/windows — INNER-JOIN exclusion),
ADD_DUPLICATE_EVENT (dedup/funnel/retention — repeat invariance). Relation
= transformed candidate result vs original candidate result under the
oracle's order spec. Unknown families raise.

## 8. Mutation testing

Family-aware text operators (`agg-sum-to-avg`, `agg-count-distinct-one`,
`order-flip`, `join-inner-to-left`, `threshold-to-zero`,
`window-widen-30-to-300`, `partition-column-swap`, `where-clause-drop`).
Mutants execute on the original fixture; killed = suite rejects (mismatch
or clean execution failure); infra faults excluded; zero applicable →
score `None` (NOT_APPLICABLE, never 100%). `score = caught/decided`,
default threshold 0.9, cap 20.

## 9. Performance evidence

`duration_ms` from Phase 3 + optional `warn_after_ms` budget; evidence
only, never a verdict (Phase 5 owns thresholds).

## 10. Verdict rules

PASS iff: execution SUCCEEDED untruncated + oracle ok + comparison match +
hidden all pass + properties/metamorphic all pass + infra healthy +
(mutation n/a or score >= min_score). FAIL on positive candidate evidence
(mismatch, hidden/property/relation failure, execution faults).
INCONCLUSIVE on oracle errors/unknown, infra faults, truncation, weak
suites. Early exit: comparison failure skips hidden+ (asserted: no hidden
backend calls).

## 11. Failure handling

`INVALID_INPUT` (binding), `EXECUTION_FAILED`/`POLICY_REJECTED` (candidate
faults), `RESULT_MISMATCH`/`HIDDEN_MISMATCH`/`PROPERTY_FAILED`/
`METAMORPHIC_FAILED`, `TRUNCATED_RESULT`, `ORACLE_ERROR`/`ORACLE_UNKNOWN`,
`SANDBOX_INFRA_ERROR`, `WEAK_SUITE`. Oracle crash never blames the
candidate.

## 12. Reproducibility

Deterministic id over logical inputs; hidden seeds deterministic;
same inputs twice → same verdict/evidence (timings excluded). Full-env
locking remains Phase 6.

## 13. Evidence schema

`oracle{version,strategy,runtime,columns,rows}`,
`comparison{match,counts,order,policy,<=3 diffs}`,
`hidden{total,passed,failed,seeds}`,
`properties/metamorphic{applicable,passed,failed,ids}`,
`mutation{applicable,run,caught,survived,score,threshold,details}`,
`performance{duration,budget}`, `verification_strength`, versions,
timestamps. Bounded, secret-free, fixture-free.

## 14. Testing strategy

Hand-fixture oracle tests (caught a real CTE tie-break bug),
comparator matrix + Hypothesis (permutation, tolerance, NULL, seeds),
verdict matrix incl. overfit/weak-suite/infra paths, independence static
tests, hidden determinism, operator + scoring tests, serialization bounds,
offline CLI tests, Docker end-to-end (correct->PASS x10, wrong->FAIL,
mutants die, oracle-unknown). Simulated backend documents its own
tautology boundary: pipeline logic unit-tested; SQL execution proven only
in containers.

## 15. Phase 5 handoff

Per candidate-task run, Phase 5 consumes: `verdict`, `failure_code`,
`verification_strength`, `mutation_score`, stage evidence, and the
underlying `task_id/candidate_id` links — to assess duplicates, diversity,
coverage, difficulty, contamination, audit sampling, and dataset quality.
No dataset-wide logic lives here.

## Oracle interpretation log (decisions beyond the letter of task-semantics)

- temporal: months with zero orders AND zero events produce no row (natural
  GROUP BY reading).
- windows: within-customer row order not checkable from the output contract
  (no date column); gate enforces customer grouping + full value equality,
  where rank/running totals already encode date ordering.
