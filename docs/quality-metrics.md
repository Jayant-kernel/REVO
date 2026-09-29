# Quality Metrics

Status: **implemented** (Phase 5). Definitions for every number in
`DatasetHealthReport`. All rates are counts over the analyzed set unless
noted; distributions expose raw counts alongside shares.

## Production

- `candidate_count` — input records analyzed.
- `verified_count` — verification verdict PASS.
- `golden_count`, `golden_yield` — GOLDEN decisions and share.
- `excluded_count`, `inconclusive_count` — terminal non-golden outcomes
  (`AUDIT_REQUIRED` is pending, counted separately in failures).

## Correctness (from Phase 4 evidence, restated not recomputed)

- `verification_pass_rate` — PASS share.
- `hidden_pass_rate`, `property_pass_rate`, `metamorphic_pass_rate`.
- `mutation_score_mean` — mean over SCORED records only; `mutation_scored_share`.
- `strong_verification_rate`, `weak_verification_rate`.

## Task health

- `task_validity_rate` — Task Engine validation passes.
- `ambiguity_rate` — any deterministic ambiguity flag.
- `semantic_completeness_rate` — all family-required keys present.
- `schema_consistency_rate` — fixture/schema/metadata agreement.
- `edge_case_coverage_rate` — mean family-expected edge presence.

## Duplicates

- `exact_duplicate_rate` — members of exact groups / total.
- `structural_duplicate_rate`, `semantic_duplicate_rate` — same per level.
- `duplicate_groups` — group count.

## Diversity

- `family` counts/percentages/entropy (Shannon, bits).
- `sql_constructs`, `operator_categories` — operator-signature hits.
- `schema_fingerprints` — distinct schema shapes.
- `edge_cases` — edge tag hits.

## Reliability

- `verification_inconclusive_rate`, `execution_failure_rate`,
  `oracle_failure_rate` (ORACLE_* codes), `audit_failure_rate`
  (decided FAIL / decided).

## Contamination

- `contamination_flag_count`, `contaminated_rate`, `split_overlap_count`
  (exact-private-eval + template-leakage hits).

## Golden

- `golden_count`, `golden_yield`, family/difficulty distributions,
  `golden_coverage_families` (distinct families in Golden).

## Difficulty

- Declared histogram (Phase 1 bands 1–5); `method` is DECLARED.
- `complexity_features` — mean structural signals (advisory).
- Empirical solve-rate: unavailable by design until multi-attempt data
  exists (`empirical_available: false` with reason).

## Coverage

- Family/construct/edge counts, rates, and explicit uncovered lists
  (families fixed to the 10 Phase 1 families; constructs fixed at 16;
  edge cases fixed to `KNOWN_EDGE_CASES`).
