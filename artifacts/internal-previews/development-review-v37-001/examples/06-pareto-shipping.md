# 06 — Lane-local Pareto shipping options

> DEVELOPMENT REVIEW PREVIEW · exposed development/TRAIN · human review PENDING · external sharing BLOCKED.

Illustrative replay based on retained public base fixture; not full authoritative validation.

Candidate: `sql.subqueries.pareto_shipping.v1.5505da8aaef5.qwen3-8b.00.02876080a37c`  
Task: `sql.subqueries.pareto_shipping.v1.5505da8aaef5`  
[Machine-readable fixture](06-pareto-shipping.json) · [Example index](index.json)

## Original question

Return ['option_id', 'lane', 'cost_cents', 'duration_minutes'] with types INTEGER,VARCHAR,INTEGER,INTEGER, option_id ascending. Each row is one unique option_id shipping proposal for a nonnull arbitrary text lane (empty text allowed). Cost is integer currency cents; duration is whole elapsed minutes. Both metrics are nullable and otherwise [0,2147483647]. Incomplete options (either metric NULL) are excluded as both candidates and competitors. Retain complete options unless some same-lane complete competitor has cost <= candidate cost AND duration <= candidate duration AND at least one strict improvement. Use a correlated NOT EXISTS subquery. Equal metric pairs do not dominate each other and all their distinct option_ids survive; no single-winner tie-break. Self cannot dominate itself. Output once per surviving option. Empty input or all incomplete options gives empty output. No date/status filter or missing-settlement history semantics.

## Declared schema and assumptions

Original schema objects are retained in the JSON fixture. `options`: declared `row_count=8`, `row_kind=generic`; actual retained rows: **32**. Declared row counts are source metadata, not replay insertion counts. Original `task.constraints` is `{}`. The question declares unique option IDs, metric units/ranges and dominance rules; no extra column meanings or uniqueness are inferred.

| Column | Type | Nullable |
| --- | --- | --- |
| option_id | INTEGER | false |
| lane | VARCHAR | false |
| cost_cents | INTEGER | true |
| duration_minutes | INTEGER | true |

## Retained public base inputs

Strings are JSON-quoted to preserve whitespace and case. `null` means SQL NULL. Rows retain original fixture order.

| option_id | lane | cost_cents | duration_minutes |
| --- | --- | --- | --- |
| 14 | "é" | 3 | 4 |
| 109 | "frame:101010:0:0" | null | null |
| -2147483648 | "" | 0 | 0 |
| 103 | "frame:101010:0:0" | 0 | null |
| 110 | "frame:101010:0:1" | 2147483647 | null |
| 4 | "A" | 0 | null |
| 104 | "frame:101010:0:1" | 2147483647 | 0 |
| 111 | "frame:101010:0:2" | 2127522790 | 998890224 |
| 113 | "frame:101010:0:1" | 0 | null |
| 13 | " A " | 9 | 9 |
| 9 | "D" | 8 | 0 |
| 8 | "D" | 7 | 0 |
| 0 | "A" | 20 | 10 |
| 2 | "A" | 10 | 20 |
| 107 | "frame:101010:0:1" | 2147483647 | 2147483647 |
| 106 | "frame:101010:0:0" | null | 2141513025 |
| 108 | "frame:101010:0:2" | 2147483647 | 0 |
| 10 | "E" | 5 | 5 |
| 7 | "B" | 2147483647 | 5 |
| 105 | "frame:101010:0:2" | null | 2147483647 |
| 100 | "frame:101010:0:0" | null | 1660823064 |
| 112 | "frame:101010:0:0" | 549487647 | 2147483647 |
| 3 | "A" | null | 0 |
| 11 | "E" | 8 | 8 |
| 12 | "a" | 1 | 1 |
| 101 | "frame:101010:0:1" | 0 | null |
| 5 | "null" | null | null |
| 2147483647 | "max" | 2147483647 | 2147483647 |
| 6 | "B" | 2147483647 | 2147483647 |
| -1 | "A" | 10 | 20 |
| 1 | "A" | 20 | 20 |
| 102 | "frame:101010:0:2" | 1088014310 | null |

## Original candidate SQL

```sql
SELECT option_id, lane, cost_cents, duration_minutes
FROM options o
WHERE NOT EXISTS (
    SELECT 1
    FROM options o2
    WHERE o2.lane = o.lane
      AND o2.cost_cents <= o.cost_cents
      AND o2.duration_minutes <= o.duration_minutes
      AND (o2.cost_cents < o.cost_cents OR o2.duration_minutes < o.duration_minutes)
      AND o2.option_id != o.option_id
)
AND cost_cents IS NOT NULL
AND duration_minutes IS NOT NULL
ORDER BY option_id
```

## Expected output — original initial execution

`rows_returned=15`, `truncated=false`. Column names/types and row order are retained exactly.

| option_id (INTEGER) | lane (VARCHAR) | cost_cents (INTEGER) | duration_minutes (INTEGER) |
| --- | --- | --- | --- |
| -2147483648 | "" | 0 | 0 |
| -1 | "A" | 10 | 20 |
| 0 | "A" | 20 | 10 |
| 2 | "A" | 10 | 20 |
| 7 | "B" | 2147483647 | 5 |
| 8 | "D" | 7 | 0 |
| 10 | "E" | 5 | 5 |
| 12 | "a" | 1 | 1 |
| 13 | " A " | 9 | 9 |
| 14 | "é" | 3 | 4 |
| 104 | "frame:101010:0:1" | 2147483647 | 0 |
| 108 | "frame:101010:0:2" | 2147483647 | 0 |
| 111 | "frame:101010:0:2" | 2127522790 | 998890224 |
| 112 | "frame:101010:0:0" | 549487647 | 2147483647 |
| 2147483647 | "max" | 2147483647 | 2147483647 |

## Verification summary

Historical candidate proof: **PASS/STRONG**; original initial execution **SUCCEEDED**, DuckDB **1.5.5**. Hidden cases **6/6**; metamorphic **3/3** applicable; properties **1/1** applicable; mutations caught **12/12**, coverage complete. Inapplicable checks are not counted as passes.

Delivery37 proof kind: `retained_final_same_source_suite`; admission, export and relocated replay **PASS**. These describe retained historical evidence. Qualification is differential verification; independent authorship is unproven.

Worker A's light local DuckDB **1.5.5** execution loaded these exact rows and matched column names, output types, ordered rows and typed values. This is only the illustrative fixture check. A fresh full-authoritative claim requires replay B and immutable-package trust checks.

## Traceability

The fixture's `source_bindings` contains repository-relative paths and SHA256 digests for membership, initial execution, candidate verification and FINAL result. Resolve membership by this exact candidate ID: `golden.task` supplies question/schema/tables; `golden.candidate_solution` supplies SQL. `expected` is the unchanged initial execution `result_data`.

Initial execution: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/005-execution.json`  
SHA256: `b0308015d56f775b08d97a74403f628210a7e6146ca692ccd890b886e4f784e2`

Candidate proof: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/005-verification.json`  
SHA256: `4659b27a17cdd02e514365b256fe8d5062c25d04f048767513ade8c6557fbdb1`
