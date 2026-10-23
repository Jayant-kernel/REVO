# 05 — Requested-language titles

> DEVELOPMENT REVIEW PREVIEW · exposed development/TRAIN · human review PENDING · external sharing BLOCKED.

Illustrative replay based on retained public base fixture; not full authoritative validation.

Candidate: `sql.joins.requested_language_titles.v1.0d54c5975c5a.qwen3-8b.00.49d13f9284e6`  
Task: `sql.joins.requested_language_titles.v1.0d54c5975c5a`  
[Machine-readable fixture](05-language-titles.json) · [Example index](index.json)

## Original question

For requested_language_titles, left join each request to translations on both item_id and exact case-sensitive language equality. Each request row emits one row per matching translation row, or exactly one row with NULL title if none matches. Any NULL key component prevents matching, including NULL to NULL. A matched NULL title remains NULL; it is not replaced. No language fallback, status/year filter or deduplication. Translation-only rows emit nothing. Inputs are bags; request_id/item_id/language are not unique. Return request_id INTEGER, title nullable VARCHAR as an unordered bag with all multiplicities, no tie/winner selection. Units are categorical text. JSON INTEGER is bounded signed32 integer excluding bool/string; VARCHAR is text; NULL only nullable columns. Exact declared table/column sets required; no other domain restrictions.

## Declared schema and assumptions

Original schema objects are retained in the JSON fixture. Both tables declare `row_count=5`, `row_kind=generic`; actual retained rows: **20 requests**, **18 translations**. Declared row counts are source metadata, not replay insertion counts. Original `task.constraints` is `{}`. The question declares bag multiplicities, key matching and domains; no extra column meanings or uniqueness are inferred.

| Table | Column | Type | Nullable |
| --- | --- | --- | --- |
| requests | request_id | INTEGER | false |
| requests | item_id | INTEGER | true |
| requests | language | VARCHAR | true |
| translations | item_id | INTEGER | true |
| translations | language | VARCHAR | true |
| translations | title | VARCHAR | true |

## Retained public base inputs

Strings are JSON-quoted to preserve whitespace and case. `null` means SQL NULL. Rows retain original fixture order.

### requests

| request_id | item_id | language |
| --- | --- | --- |
| 1 | 13 | "en" |
| 8 | null | null |
| 2147483647 | 2147483647 | "en" |
| 3 | null | "en" |
| 1 | 10 | "en" |
| 105808409 | 1001 | "frame:101010:0:1:é" |
| -2147483648 | -2147483648 | "en" |
| 4 | 10 | null |
| 1246072600 | 1002 | "frame:101010:0:2:" |
| 1 | 10 | "en" |
| -812412271 | 1002 | "frame:101010:0:2:" |
| -1554236575 | 1001 | "frame:101010:0:1:é" |
| 6 | 11 | "en" |
| 1770174249 | 1000 | "frame:101010:0:0:EN" |
| -1791047232 | 1000 | "frame:101010:0:0:EN" |
| -1619429116 | 1002 | "frame:101010:0:2:" |
| 5 | 10 | "EN" |
| 7 | 12 | "" |
| 2 | 10 | "fr" |
| -1 | -1 | " en " |

### translations

| item_id | language | title |
| --- | --- | --- |
| 1000 | "frame:101010:0:0:EN" | null |
| -1 | "en" | "trim trap" |
| 13 | "en" | "Other" |
| 11 | "en" | null |
| 99 | "de" | "orphan" |
| 2147483647 | "en" | "maximum" |
| 10 | null | "null language" |
| null | "en" | "null item" |
| -1 | " en " | "literal" |
| 12 | "" | "" |
| 1000 | "frame:101010:0:0:EN" | "" |
| 10 | "en" | "Book" |
| null | null | "both null" |
| 1000 | "frame:101010:0:0:EN" | "" |
| 10 | "en" | "Book" |
| 10 | "en" | "Volume" |
| -2147483648 | "en" | "minimum" |
| 1000 | "frame:101010:0:0:EN" | "Title" |

## Original candidate SQL

```sql
SELECT requests.request_id, translations.title
FROM requests
LEFT JOIN translations
ON requests.item_id = translations.item_id
AND requests.language = translations.language
```

## Expected output — original initial execution

`rows_returned=30`, `truncated=false`. Column names/types and recorded row order are retained exactly. The task itself declares an **unordered bag** and the SQL has no `ORDER BY`. Replay A's ordered comparison is deliberately a retained-execution illustration on the tested DuckDB configuration, not a portable ordering guarantee or a change to the task's bag semantics. Do not sort or deduplicate the stored expected rows.

| request_id (INTEGER) | title (VARCHAR) |
| --- | --- |
| -1791047232 | null |
| 1 | "Other" |
| 6 | null |
| 2147483647 | "maximum" |
| -1 | "literal" |
| 7 | "" |
| -1791047232 | "" |
| 1 | "Book" |
| -1791047232 | "" |
| 1 | "Book" |
| 1 | "Volume" |
| -2147483648 | "minimum" |
| -1791047232 | "Title" |
| 1770174249 | null |
| 1770174249 | "" |
| 1 | "Book" |
| 1770174249 | "" |
| 1 | "Book" |
| 1 | "Volume" |
| 1770174249 | "Title" |
| 2 | null |
| 4 | null |
| 3 | null |
| 8 | null |
| 1246072600 | null |
| -812412271 | null |
| -1619429116 | null |
| 105808409 | null |
| -1554236575 | null |
| 5 | null |

## Verification summary

Historical candidate proof: **PASS/STRONG**; original initial execution **SUCCEEDED**, DuckDB **1.5.5**. Hidden cases **5/5**; metamorphic **3/3** applicable; properties **1/1** applicable; mutations caught **15/15**, coverage complete. Inapplicable checks are not counted as passes.

Delivery37 proof kind: `retained_final_same_source_suite`; admission, export and relocated replay **PASS**. These describe retained historical evidence. Qualification is differential verification; independent authorship is unproven.

Worker A's light local DuckDB **1.5.5** execution, with one thread, loaded these exact rows and matched column names, output types, recorded ordered rows and typed values. This is only the illustrative fixture check. A fresh full-authoritative claim requires replay B and immutable-package trust checks.

## Traceability

The fixture's `source_bindings` contains repository-relative paths and SHA256 digests for membership, initial execution, candidate verification and FINAL result. Resolve membership by this exact candidate ID: `golden.task` supplies question/schema/tables; `golden.candidate_solution` supplies SQL. `expected` is the unchanged initial execution `result_data`.

Initial execution: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/004-execution.json`  
SHA256: `e85732302552253130873fe82dc3fdc6431c0755f87a5bc15217581bddffc9b7`

Candidate proof: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/004-verification.json`  
SHA256: `d02c196babf2668447b5154d0030432f05f348bcc59902617a87b70e1dc5e572`
