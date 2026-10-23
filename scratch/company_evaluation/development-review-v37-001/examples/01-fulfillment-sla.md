# 01 — Warehouse fulfillment SLA

> DEVELOPMENT REVIEW PREVIEW · exposed development/TRAIN · human review PENDING · external sharing BLOCKED.

Illustrative replay based on retained public base fixture; not full authoritative validation.

Candidate: `sql.aggregation.fulfillment_sla_dashboard.v1.ee6cf26ee225.qwen3-8b.00.b8142874a73f`  
Task: `sql.aggregation.fulfillment_sla_dashboard.v1.ee6cf26ee225`  
[Machine-readable fixture](01-fulfillment-sla.json) · [Example index](index.json)

## Original question

For 2025, build a warehouse fulfillment SLA dashboard from fulfillments. Include only 'delivered' fulfillments shipped in the year with a non-null delivery timestamp. Return warehouse, delivered_fulfillments, and on_time_fulfillments, where on time means delivered_at is no later than promised_at. Order by warehouse. Exclude cancelled, unresolved, and out-of-year fulfillments (ineligible_rows, null_values, year_boundary).

## Declared schema and assumptions

Original schema objects are retained in the JSON fixture. `fulfillments`: declared `row_count=8`, `row_kind=generic`; actual retained rows: **7**. Declared row counts are source metadata, not replay insertion counts. Original `task.constraints` is `{}`. The question defines the filters, boundary comparisons and ordering; no extra column meanings or uniqueness are inferred.

| Column | Type | Nullable |
| --- | --- | --- |
| fulfillment_id | INTEGER | false |
| warehouse | VARCHAR | false |
| shipped_at | TIMESTAMP | false |
| promised_at | TIMESTAMP | false |
| delivered_at | TIMESTAMP | true |
| fulfillment_status | VARCHAR | false |

## Retained public base inputs

Strings are JSON-quoted to preserve whitespace and case. `null` means SQL NULL. Rows retain original fixture order.

| fulfillment_id | warehouse | shipped_at | promised_at | delivered_at | fulfillment_status |
| --- | --- | --- | --- | --- | --- |
| 5 | "north" | "2024-12-31 23:59:59" | "2025-01-02 00:00:00" | "2025-01-01 00:00:00" | "delivered" |
| 4 | "west" | "2025-02-02 08:00:00" | "2025-02-03 08:00:00" | "2025-02-02 12:00:00" | "delivered" |
| 2 | "east" | "2025-01-02 08:00:00" | "2025-01-03 08:00:00" | "2025-01-03 08:00:01" | "delivered" |
| 3 | "west" | "2025-02-01 08:00:00" | "2025-02-02 08:00:00" | null | "in_transit" |
| 6 | "north" | "2025-06-01 08:00:00" | "2025-06-02 08:00:00" | "2025-06-01 10:00:00" | "cancelled" |
| 1 | "east" | "2025-01-01 08:00:00" | "2025-01-03 08:00:00" | "2025-01-03 08:00:00" | "delivered" |
| 7 | "east" | "2025-12-31 08:00:00" | "2026-01-01 08:00:00" | "2026-01-01 08:00:00" | "delivered" |

## Original candidate SQL

```sql
SELECT 
    warehouse, 
    COUNT(*) AS delivered_fulfillments, 
    SUM(CASE WHEN delivered_at <= promised_at THEN 1 ELSE 0 END) AS on_time_fulfillments
FROM 
    fulfillments
WHERE 
    fulfillment_status = 'delivered'
    AND shipped_at >= DATE '2025-01-01'
    AND shipped_at < DATE '2026-01-01'
    AND delivered_at IS NOT NULL
GROUP BY 
    warehouse
ORDER BY 
    warehouse
```

## Expected output — original initial execution

`rows_returned=2`, `truncated=false`. Column names/types and row order are retained exactly.

| warehouse (VARCHAR) | delivered_fulfillments (BIGINT) | on_time_fulfillments (HUGEINT) |
| --- | --- | --- |
| "east" | 3 | 2 |
| "west" | 1 | 1 |

## Verification summary

Historical candidate proof: **PASS/STRONG**; original initial execution **SUCCEEDED**, DuckDB **1.5.5**. Hidden cases **10/10**; metamorphic **1/1** applicable; properties **1/1** applicable; mutations caught **9/9**, coverage complete. Inapplicable checks are not counted as passes.

Delivery37 proof kind: `fresh_original_candidate_native_rejudge`; admission, export and relocated replay **PASS**. These describe retained historical evidence. Qualification is differential verification; independent authorship is unproven.

Worker A's light local DuckDB **1.5.5** execution loaded these exact rows and matched column names, output types, ordered rows and typed values. This is only the illustrative fixture check. A fresh full-authoritative claim requires replay B and immutable-package trust checks.

## Traceability

The fixture's `source_bindings` contains repository-relative paths and SHA256 digests for membership, initial execution, candidate verification and FINAL result. Resolve membership by this exact candidate ID: `golden.task` supplies question/schema/tables; `golden.candidate_solution` supplies SQL. `expected` is the unchanged initial execution `result_data`.

Initial execution: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/000-execution.json`  
SHA256: `383e1622cb0aa175f59ac284f764810b442fd911236addf4773b5a06732dad03`

Candidate proof: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/000-verification.json`  
SHA256: `0a583a89c8b6ab3f2dc54a009e946c302e02153e6251279f6210d62c5fdcb9a2`
