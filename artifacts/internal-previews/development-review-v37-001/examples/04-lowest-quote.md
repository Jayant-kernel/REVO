# 04 — Lowest quote per part

> DEVELOPMENT REVIEW PREVIEW · exposed development/TRAIN · human review PENDING · external sharing BLOCKED.

Illustrative replay based on retained public base fixture; not full authoritative validation.

Candidate: `sql.dedup.lowest_quote.v1.c5a5d681007c.qwen3-8b.00.f5fcd4f8535f`  
Task: `sql.dedup.lowest_quote.v1.c5a5d681007c`  
[Machine-readable fixture](04-lowest-quote.json) · [Example index](index.json)

## Original question

Return ['part', 'supplier', 'price_cents'] with types VARCHAR,VARCHAR,INTEGER, ordered by part ascending. Each input row is a supplier's unit quote in integer currency cents for a part; price_cents is nullable and otherwise in [0,2147483647]. All other fields are nonnull text, including empty text; no uniqueness is assumed. For each part select minimum nonnull price, then lexicographically smallest supplier under DuckDB default binary text ordering. Exact repeats and tied identical projected winners produce one row, not multiple rows. NULL price means unknown and is excluded before selection; all-NULL parts are omitted. Empty input gives empty output. No time, year, status, or latest-row filter.

## Declared schema and assumptions

Original schema objects are retained in the JSON fixture. `quotes`: declared `row_count=8`, `row_kind=generic`; actual retained rows: **20**. Declared row counts are source metadata, not replay insertion counts. Original `task.constraints` is `{}`. The question declares price units/range, text ordering, bag inputs and winner rules; no extra column meanings or uniqueness are inferred.

| Column | Type | Nullable |
| --- | --- | --- |
| part | VARCHAR | false |
| supplier | VARCHAR | false |
| price_cents | INTEGER | true |

## Retained public base inputs

Strings are JSON-quoted to preserve whitespace and case. `null` means SQL NULL. Rows retain original fixture order.

| part | supplier | price_cents |
| --- | --- | --- |
| "p " | " s " | 11 |
| "frame:101010:0:1: " | "é" | 0 |
| "P" | "s" | 12 |
| "p" | "A" | 20 |
| "max" | "s" | 2147483647 |
| "p" | "B" | 10 |
| "p" | "z" | 10 |
| "unicode" | "z" | 7 |
| "p" | "" | null |
| "" | "" | 0 |
| "frame:101010:0:1: " | "" | 891432997 |
| "frame:101010:0:0:é" | "A" | 0 |
| "case" | "a" | 8 |
| "frame:101010:0:0:é" | "a" | null |
| "frame:101010:0:1: " | "Z" | 1415936655 |
| "case" | "Z" | 8 |
| "null" | "s" | null |
| "unicode" | "é" | 7 |
| "p" | "B" | 10 |
| "frame:101010:0:0:é" | "Z" | 463527351 |

## Original candidate SQL

```sql
SELECT part, supplier, MIN(price_cents) OVER (PARTITION BY part) AS price_cents
FROM quotes
WHERE price_cents IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY part ORDER BY price_cents ASC, supplier ASC) = 1
ORDER BY part ASC
```

## Expected output — original initial execution

`rows_returned=9`, `truncated=false`. Column names/types and row order are retained exactly.

| part (VARCHAR) | supplier (VARCHAR) | price_cents (INTEGER) |
| --- | --- | --- |
| "" | "" | 0 |
| "P" | "s" | 12 |
| "case" | "Z" | 8 |
| "frame:101010:0:0:é" | "A" | 0 |
| "frame:101010:0:1: " | "é" | 0 |
| "max" | "s" | 2147483647 |
| "p" | "B" | 10 |
| "p " | " s " | 11 |
| "unicode" | "z" | 7 |

## Verification summary

Historical candidate proof: **PASS/STRONG**; original initial execution **SUCCEEDED**, DuckDB **1.5.5**. Hidden cases **7/7**; metamorphic **3/3** applicable; properties **1/1** applicable; mutations caught **12/12**, coverage complete. Inapplicable checks are not counted as passes.

Delivery37 proof kind: `retained_final_same_source_suite`; admission, export and relocated replay **PASS**. These describe retained historical evidence. Qualification is differential verification; independent authorship is unproven.

Worker A's light local DuckDB **1.5.5** execution loaded these exact rows and matched column names, output types, ordered rows and typed values. This is only the illustrative fixture check. A fresh full-authoritative claim requires replay B and immutable-package trust checks.

## Traceability

The fixture's `source_bindings` contains repository-relative paths and SHA256 digests for membership, initial execution, candidate verification and FINAL result. Resolve membership by this exact candidate ID: `golden.task` supplies question/schema/tables; `golden.candidate_solution` supplies SQL. `expected` is the unchanged initial execution `result_data`.

Initial execution: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/003-execution.json`  
SHA256: `9deb3c142760c0d551590445d232d310666fea55c15facf1419e74a7dd7b07e6`

Candidate proof: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/003-verification.json`  
SHA256: `b886fca44c46b515277d3cccf1dd73c434dfab20b261c9adc5587821de292f40`
