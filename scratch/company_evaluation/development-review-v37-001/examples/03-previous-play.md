# 03 — Previous completed playback

> DEVELOPMENT REVIEW PREVIEW · exposed development/TRAIN · human review PENDING · external sharing BLOCKED.

Illustrative replay based on retained public base fixture; not full authoritative validation.

Candidate: `sql.windows.media_previous_play.v1.cd1ead8f4849.qwen3-8b.11.a9e4c8f9f042`  
Task: `sql.windows.media_previous_play.v1.cd1ead8f4849`  
[Machine-readable fixture](03-previous-play.json) · [Example index](index.json)

## Original question

For completed playbacks in 2025, find the previous completed playback of the same title by the same viewer within that year. Order history by played_at then play_id; partial plays do not participate. Return play_id and previous_play_id ordered by play_id. The first playback in each history has NULL previous_play_id.

## Declared schema and assumptions

Original schema objects are retained in the JSON fixture. `plays`: declared `row_count=10`, `row_kind=generic`; actual retained rows: **7**. Declared row counts are source metadata, not replay insertion counts. Original `task.constraints` is `{}`. The question defines the history partitions, filters and tie-breaking; no extra column meanings or uniqueness are inferred.

| Column | Type | Nullable |
| --- | --- | --- |
| play_id | INTEGER | false |
| viewer_id | INTEGER | false |
| title_id | INTEGER | false |
| played_at | TIMESTAMP | false |
| status | VARCHAR | false |

## Retained public base inputs

Strings are JSON-quoted to preserve whitespace and case. `null` means SQL NULL. Rows retain original fixture order.

| play_id | viewer_id | title_id | played_at | status |
| --- | --- | --- | --- | --- |
| 7 | 1 | 10 | "2024-12-31 00:00:00" | "completed" |
| 4 | 2 | 10 | "2025-01-02 00:00:00" | "completed" |
| 2 | 1 | 10 | "2025-01-01 00:00:00" | "completed" |
| 3 | 1 | 20 | "2025-01-02 00:00:00" | "completed" |
| 1 | 1 | 10 | "2025-01-01 00:00:00" | "completed" |
| 5 | 1 | 10 | "2025-01-03 00:00:00" | "partial" |
| 6 | 1 | 10 | "2025-01-04 00:00:00" | "completed" |

## Original candidate SQL

```sql
SELECT play_id, previous_play_id
FROM (
  SELECT 
    p1.play_id,
    LAG(p1.play_id, 1) OVER (PARTITION BY p1.viewer_id, p1.title_id ORDER BY p1.played_at, p1.play_id) AS previous_play_id
  FROM plays p1
  WHERE p1.status = 'completed'
    AND EXTRACT(YEAR FROM p1.played_at) = 2025
)
ORDER BY play_id
```

## Expected output — original initial execution

`rows_returned=5`, `truncated=false`. Column names/types and row order are retained exactly.

| play_id (INTEGER) | previous_play_id (INTEGER) |
| --- | --- |
| 1 | null |
| 2 | 1 |
| 3 | null |
| 4 | null |
| 6 | 2 |

## Verification summary

Historical candidate proof: **PASS/STRONG**; original initial execution **SUCCEEDED**, DuckDB **1.5.5**. Hidden cases **5/5**; metamorphic **3/3** applicable; properties **1/1** applicable; mutations caught **12/12**, coverage complete. Inapplicable checks are not counted as passes.

Delivery37 proof kind: `fresh_original_candidate_native_rejudge`; admission, export and relocated replay **PASS**. These describe retained historical evidence. Qualification is differential verification; independent authorship is unproven.

Worker A's light local DuckDB **1.5.5** execution loaded these exact rows and matched column names, output types, ordered rows and typed values. This is only the illustrative fixture check. A fresh full-authoritative claim requires replay B and immutable-package trust checks.

## Traceability

The fixture's `source_bindings` contains repository-relative paths and SHA256 digests for membership, initial execution, candidate verification and FINAL result. Resolve membership by this exact candidate ID: `golden.task` supplies question/schema/tables; `golden.candidate_solution` supplies SQL. `expected` is the unchanged initial execution `result_data`.

Initial execution: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/002-execution.json`  
SHA256: `9c9341723bf919282676c880214978ed782d47f818af28c9da68c86d5458d379`

Candidate proof: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/002-verification.json`  
SHA256: `6ac37ae44eab5e80b6e8c48f51a93d9701c491222a4862b9b4355435f2e3f90e`
