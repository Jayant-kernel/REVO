# 07 — Renewal bridge coverage

> DEVELOPMENT REVIEW PREVIEW · exposed development/TRAIN · human review PENDING · external sharing BLOCKED.

Illustrative replay based on retained public base fixture; not full authoritative validation.

Candidate: `sql.retention.renewal_coverage.v1.63a1c0fefc7c.qwen3-8b.00.b9dbae6d29b5`  
Task: `sql.retention.renewal_coverage.v1.63a1c0fefc7c`  
[Machine-readable fixture](07-renewal-coverage.json) · [Example index](index.json)

## Original question

For each supplied membership episode expiring in calendar 2025, return episode_id INTEGER and covered BOOLEAN ordered by episode_id ascending. One confirmed renewal for that member must begin at or before expiry and end at or after expiry plus 14 elapsed 24-hour days. These endpoint comparisons are inclusive even though no activity interval union is computed. Multiple adjacent renewals cannot be stitched. All renewal years participate; other statuses do not. An episode is the supplied unique episode_id, not the member's first purchase; multiple episodes per member are independently tested and one renewal may cover multiple episodes. No renewal gives FALSE. Renewal rows are arbitrary bags: repeated and conflicting intervals are separate evidence and existence prevents multiplication. Empty episodes produce no rows. All times are naive, timezone-free, microsecond-resolution timestamps; no calendar-date cast or rounding. All input columns are nonnull, episodes.episode_id must be unique and every renewal ends_at must be >= begins_at. No other uniqueness, foreign-key or status-enum restriction; orphan renewals are ignored. No tie selection or NULL ordering is applicable.

## Declared schema and assumptions

Original schema objects are retained in the JSON fixture. `episodes` declares `row_count=4`; `renewals` declares `row_count=8`; both have `row_kind=generic`. Actual retained rows: **18 episodes**, **15 renewals**. Declared row counts are source metadata, not replay insertion counts. Original `task.constraints` is `{}`. The question declares episode identity, timestamp precision, interval validity and coverage rules; no extra column meanings or uniqueness are inferred.

| Table | Column | Type | Nullable |
| --- | --- | --- | --- |
| episodes | episode_id | INTEGER | false |
| episodes | member_id | INTEGER | false |
| episodes | expires_at | TIMESTAMP | false |
| renewals | member_id | INTEGER | false |
| renewals | begins_at | TIMESTAMP | false |
| renewals | ends_at | TIMESTAMP | false |
| renewals | status | VARCHAR | false |

## Retained public base inputs

Strings are JSON-quoted to preserve whitespace and case. `null` means SQL NULL. Rows retain original fixture order.

### episodes

| episode_id | member_id | expires_at |
| --- | --- | --- |
| 4 | 4 | "2025-01-01T00:00:00" |
| 6 | 6 | "2025-01-01T00:00:00" |
| -2147483648 | -1 | "2025-01-01T00:00:00" |
| 5 | 5 | "2025-01-01T00:00:00" |
| 13 | 7 | "2024-12-31T23:59:59.999999" |
| 1 | 1 | "2025-01-01T00:00:00" |
| 9 | 9 | "2025-01-01T12:00:00.000001" |
| 7 | 7 | "2025-01-01T00:00:00" |
| 102 | 102 | "2025-09-03T06:37:23.383679" |
| 101 | 101 | "2025-09-04T06:43:50.432267" |
| 12 | 7 | "2026-01-01T00:00:00" |
| 11 | 7 | "2025-12-30T23:59:59.999999" |
| 2147483647 | 8 | "2025-01-01T00:00:00" |
| 100 | 100 | "2025-03-23T16:37:26.699334" |
| 10 | 7 | "2025-12-31T23:59:59.999999" |
| 3 | 3 | "2025-01-01T00:00:00" |
| 8 | 8 | "2025-01-01T00:00:00" |
| 2 | 2 | "2025-01-01T00:00:00" |

### renewals

| member_id | begins_at | ends_at | status |
| --- | --- | --- | --- |
| 1 | "2025-01-01T00:00:00" | "2025-01-15T00:00:00" | "pending" |
| 9 | "2025-01-01T00:00:00" | "2025-01-15T12:00:00" | "confirmed" |
| 102 | "2025-09-03T06:37:23.383679" | "2025-09-17T06:37:23.383680" | "pending" |
| 3 | "2024-12-01T00:00:00" | "2025-01-14T23:59:59.999999" | "confirmed" |
| 4 | "2025-01-01T00:00:00" | "2025-01-08T00:00:00" | "confirmed" |
| 4 | "2025-01-08T00:00:00" | "2025-02-01T00:00:00" | "confirmed" |
| 8 | "2024-12-01T00:00:00" | "2025-01-15T00:00:00" | "confirmed" |
| 100 | "2025-03-23T16:37:26.699333" | "2025-04-06T16:37:26.699334" | "pending" |
| 101 | "2025-09-04T06:43:50.432266" | "2025-09-18T06:43:50.432268" | "confirmed" |
| 1 | "2025-01-01T00:00:00" | "2025-01-15T00:00:00" | "confirmed" |
| 99 | "2020-01-01T00:00:00" | "2030-01-01T00:00:00" | "confirmed" |
| 1 | "2025-01-01T00:00:00" | "2025-01-15T00:00:00" | "confirmed" |
| 7 | "2025-12-30T23:59:59.999999" | "2026-01-14T23:59:59.999999" | "confirmed" |
| 2 | "2025-01-01T00:00:00.000001" | "2025-01-15T00:00:00" | "confirmed" |
| 5 | "2025-01-01T00:00:00" | "2025-01-15T00:00:00" | "unknown" |

## Original candidate SQL

```sql
SELECT episodes.episode_id, 
       CASE WHEN EXISTS (
           SELECT 1
           FROM renewals
           WHERE renewals.member_id = episodes.member_id
             AND renewals.status = 'confirmed'
             AND renewals.begins_at <= episodes.expires_at
             AND renewals.ends_at >= episodes.expires_at + INTERVAL '14 days'
       ) THEN TRUE ELSE FALSE END AS covered
FROM episodes
WHERE EXTRACT(YEAR FROM episodes.expires_at) = 2025
ORDER BY episodes.episode_id ASC
```

## Expected output — original initial execution

`rows_returned=16`, `truncated=false`. Column names/types and row order are retained exactly. `true`/`false` are Boolean values, not strings or integers.

| episode_id (INTEGER) | covered (BOOLEAN) |
| --- | --- |
| -2147483648 | false |
| 1 | true |
| 2 | false |
| 3 | false |
| 4 | false |
| 5 | false |
| 6 | false |
| 7 | false |
| 8 | true |
| 9 | false |
| 10 | true |
| 11 | true |
| 100 | false |
| 101 | true |
| 102 | false |
| 2147483647 | true |

## Verification summary

Historical candidate proof: **PASS/STRONG**; original initial execution **SUCCEEDED**, DuckDB **1.5.5**. Hidden cases **5/5**; metamorphic **3/3** applicable; properties **1/1** applicable; mutations caught **17/17**, coverage complete. Inapplicable checks are not counted as passes.

Delivery37 proof kind: `retained_final_same_source_suite`; admission, export and relocated replay **PASS**. These describe retained historical evidence. Qualification is differential verification; independent authorship is unproven.

Worker A's light local DuckDB **1.5.5** execution loaded these exact rows and matched column names, output types, ordered rows and typed values. This is only the illustrative fixture check. A fresh full-authoritative claim requires replay B and immutable-package trust checks.

## Traceability

The fixture's `source_bindings` contains repository-relative paths and SHA256 digests for membership, initial execution, candidate verification and FINAL result. Resolve membership by this exact candidate ID: `golden.task` supplies question/schema/tables; `golden.candidate_solution` supplies SQL. `expected` is the unchanged initial execution `result_data`.

Initial execution: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/006-execution.json`  
SHA256: `8f292d89f96b53bf1ddefbc3ab63dd590d6f00e9be7279ebd83f61f29f98946d`

Candidate proof: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/006-verification.json`  
SHA256: `cf063834035edbcdfb01b474d0b4889dc68ad20339edba6ec8b707cdc1f4efed`
