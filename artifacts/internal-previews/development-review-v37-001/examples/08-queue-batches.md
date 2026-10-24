# 08 — Balanced queue processing batches

> DEVELOPMENT REVIEW PREVIEW · exposed development/TRAIN · human review PENDING · external sharing BLOCKED.

Illustrative replay based on retained public base fixture; not full authoritative validation.

Candidate: `sql.windows.queue_batches.v1.11f188ba5320.qwen3-8b.00.dfda1f1b90f0`  
Task: `sql.windows.queue_batches.v1.11f188ba5320`  
[Machine-readable fixture](08-queue-batches.json) · [Example index](index.json)

## Original question

The year policy is not_applicable_all_history: use all history. Allocate every submission to one of three balanced consecutive processing batches per queue using NTILE(3), never value RANK, equal-time shared rank, or running amount totals. Order within a queue by submitted_at ascending NULLS LAST then submission_id ascending, including NULL peers. If N=3q+r, the first r batches have q+1 rows and the rest q rows; when N<3 use batches 1..N. Return submission_id INTEGER and batch_number BIGINT ordered submission_id ascending. Queues are exact VARCHAR labels, no normalization; empty queues are absent. No episodes/status/year exclusion. submission_id must be unique globally; otherwise equal payloads with different IDs are distinct submissions. submitted_at is the only nullable input, naive timezone-free microsecond-resolution TIMESTAMP. No other domain/foreign-key restriction. All years and unknown-time submissions participate. Empty input gives no output. Batch number is a dimensionless integer.

## Declared schema and assumptions

Original schema objects are retained in the JSON fixture. `submissions`: declared `row_count=10`, `row_kind=generic`; actual retained rows: **109**. Declared row counts are source metadata, not replay insertion counts. Original `task.constraints` is `{}`. The question declares globally unique IDs, exact queue labels, timestamp precision and batch rules; no extra column meanings or uniqueness are inferred. “Empty queues are absent” does not exclude the retained empty-text queue label `""`; it describes queues without submissions.

| Column | Type | Nullable |
| --- | --- | --- |
| submission_id | INTEGER | false |
| queue | VARCHAR | false |
| submitted_at | TIMESTAMP | true |

## Retained public base inputs

Strings are JSON-quoted to preserve whitespace and case. `null` means SQL NULL. All 109 rows retain original fixture order; this is not a reduced fixture.

| submission_id | queue | submitted_at |
| --- | --- | --- |
| 2147483647 | "A" | "9999-12-31T23:59:59.999999" |
| 1018 | "large" | "2024-01-01T00:00:00.000021" |
| 1039 | "large" | null |
| 806 | "size8" | null |
| 1004 | "large" | "2025-01-01T00:00:00.000035" |
| 605 | "size6" | null |
| 2016 | "frame:101010:0" | "2025-02-01T00:00:00.734065" |
| 704 | "size7" | null |
| 302 | "size3" | null |
| 1037 | "large" | null |
| 2001 | "frame:101010:0" | "2025-02-01T00:00:00.468022" |
| 1034 | "large" | null |
| 1017 | "large" | "2026-01-01T00:00:00.000022" |
| 705 | "size7" | null |
| 1023 | "large" | "2026-01-01T00:00:00.000016" |
| 706 | "size7" | null |
| -2 | "" | null |
| 1016 | "large" | "2025-01-01T00:00:00.000023" |
| 402 | "size4" | null |
| 1033 | "large" | null |
| 1002 | "large" | "2026-01-01T00:00:00.000037" |
| 500 | "size5" | "2025-01-01T00:00:00.000000" |
| 2020 | "frame:101010:0" | "2025-02-01T00:00:00.792637" |
| 601 | "size6" | "2025-01-01T00:00:00.000001" |
| 2008 | "frame:101010:0" | "2025-02-01T00:00:00.208449" |
| 201 | "size2" | null |
| 802 | "size8" | "2025-01-01T00:00:00.000000" |
| 1015 | "large" | "2024-01-01T00:00:00.000024" |
| -3 | " A " | null |
| 2003 | "frame:101010:0" | "2025-02-01T00:00:00.246432" |
| 2021 | "frame:101010:0" | "2025-02-01T00:00:00.667981" |
| 2025 | "frame:101010:0" | "2025-02-01T00:00:00.864012" |
| 1003 | "large" | "2024-01-01T00:00:00.000036" |
| -1 | "a" | null |
| 2022 | "frame:101010:0" | "2025-02-01T00:00:00.145388" |
| 700 | "size7" | "2025-01-01T00:00:00.000000" |
| 100 | "size1" | null |
| 2024 | "frame:101010:0" | "2025-02-01T00:00:00.704682" |
| 1035 | "large" | null |
| 1012 | "large" | "2024-01-01T00:00:00.000027" |
| 1020 | "large" | "2026-01-01T00:00:00.000019" |
| 1010 | "large" | "2025-01-01T00:00:00.000029" |
| 2006 | "frame:101010:0" | "2025-02-01T00:00:00.324774" |
| 2015 | "frame:101010:0" | "2025-02-01T00:00:00.942442" |
| 2014 | "frame:101010:0" | "2025-02-01T00:00:00.164380" |
| 602 | "size6" | "2025-01-01T00:00:00.000000" |
| 1000 | "large" | "2024-01-01T00:00:00.000039" |
| 401 | "size4" | "2025-01-01T00:00:00.000001" |
| 1031 | "large" | null |
| 703 | "size7" | null |
| 1024 | "large" | "2024-01-01T00:00:00.000015" |
| 2017 | "frame:101010:0" | "2025-02-01T00:00:00.950833" |
| 2005 | "frame:101010:0" | "2025-02-01T00:00:00.945340" |
| 807 | "size8" | null |
| 1028 | "large" | "2025-01-01T00:00:00.000011" |
| 604 | "size6" | null |
| 803 | "size8" | "2025-01-01T00:00:00.000001" |
| 2010 | "frame:101010:0" | "2025-02-01T00:00:00.513857" |
| 503 | "size5" | null |
| 1005 | "large" | "2026-01-01T00:00:00.000034" |
| 2018 | "frame:101010:0" | "2025-02-01T00:00:00.318999" |
| 702 | "size7" | "2025-01-01T00:00:00.000000" |
| 1006 | "large" | "2024-01-01T00:00:00.000033" |
| 1011 | "large" | "2026-01-01T00:00:00.000028" |
| 504 | "size5" | null |
| 1032 | "large" | null |
| 2007 | "frame:101010:0" | "2025-02-01T00:00:00.876651" |
| 301 | "size3" | null |
| 2019 | "frame:101010:0" | "2025-02-01T00:00:00.429057" |
| 2027 | "frame:101010:0" | "2025-02-01T00:00:00.256919" |
| 2002 | "frame:101010:0" | "2025-02-01T00:00:00.583807" |
| 501 | "size5" | "2025-01-01T00:00:00.000001" |
| 2011 | "frame:101010:0" | "2025-02-01T00:00:00.823407" |
| 801 | "size8" | "2025-01-01T00:00:00.000001" |
| 2026 | "frame:101010:0" | "2025-02-01T00:00:00.217587" |
| 200 | "size2" | "2025-01-01T00:00:00.000000" |
| 1036 | "large" | null |
| 403 | "size4" | null |
| 1014 | "large" | "2026-01-01T00:00:00.000025" |
| 1009 | "large" | "2024-01-01T00:00:00.000030" |
| 400 | "size4" | "2025-01-01T00:00:00.000000" |
| 1025 | "large" | "2025-01-01T00:00:00.000014" |
| 1026 | "large" | "2026-01-01T00:00:00.000013" |
| 2013 | "frame:101010:0" | "2025-02-01T00:00:00.707594" |
| 1027 | "large" | "2024-01-01T00:00:00.000012" |
| 701 | "size7" | "2025-01-01T00:00:00.000001" |
| 1001 | "large" | "2025-01-01T00:00:00.000038" |
| 1007 | "large" | "2025-01-01T00:00:00.000032" |
| 1021 | "large" | "2024-01-01T00:00:00.000018" |
| 1030 | "large" | "2024-01-01T00:00:00.000009" |
| 1008 | "large" | "2026-01-01T00:00:00.000031" |
| 1022 | "large" | "2025-01-01T00:00:00.000017" |
| 1038 | "large" | null |
| 1029 | "large" | "2026-01-01T00:00:00.000010" |
| 2023 | "frame:101010:0" | "2025-02-01T00:00:00.828230" |
| 804 | "size8" | null |
| 2009 | "frame:101010:0" | "2025-02-01T00:00:00.944998" |
| 603 | "size6" | null |
| 1019 | "large" | "2025-01-01T00:00:00.000020" |
| -2147483648 | "A" | "0001-01-01T00:00:00" |
| 2004 | "frame:101010:0" | "2025-02-01T00:00:00.084503" |
| 300 | "size3" | "2025-01-01T00:00:00.000000" |
| 502 | "size5" | null |
| 2012 | "frame:101010:0" | "2025-02-01T00:00:00.717462" |
| 1013 | "large" | "2025-01-01T00:00:00.000026" |
| 805 | "size8" | null |
| 2000 | "frame:101010:0" | "2025-02-01T00:00:00.871926" |
| 800 | "size8" | "2025-01-01T00:00:00.000000" |
| 600 | "size6" | "2025-01-01T00:00:00.000000" |

## Original candidate SQL

```sql
SELECT submission_id, batch_number
FROM (
    SELECT 
        submission_id,
        NTILE(3) OVER (
            PARTITION BY queue
            ORDER BY submitted_at ASC NULLS LAST, submission_id ASC
        ) AS batch_number
    FROM submissions
) sub
ORDER BY submission_id ASC
```

## Expected output — original initial execution

`rows_returned=109`, `truncated=false`. Column names/types and row order are retained exactly. All rows are shown.

| submission_id (INTEGER) | batch_number (BIGINT) |
| --- | --- |
| -2147483648 | 1 |
| -3 | 1 |
| -2 | 1 |
| -1 | 1 |
| 100 | 1 |
| 200 | 1 |
| 201 | 2 |
| 300 | 1 |
| 301 | 2 |
| 302 | 3 |
| 400 | 1 |
| 401 | 1 |
| 402 | 2 |
| 403 | 3 |
| 500 | 1 |
| 501 | 1 |
| 502 | 2 |
| 503 | 2 |
| 504 | 3 |
| 600 | 1 |
| 601 | 2 |
| 602 | 1 |
| 603 | 2 |
| 604 | 3 |
| 605 | 3 |
| 700 | 1 |
| 701 | 1 |
| 702 | 1 |
| 703 | 2 |
| 704 | 2 |
| 705 | 3 |
| 706 | 3 |
| 800 | 1 |
| 801 | 1 |
| 802 | 1 |
| 803 | 2 |
| 804 | 2 |
| 805 | 2 |
| 806 | 3 |
| 807 | 3 |
| 1000 | 1 |
| 1001 | 2 |
| 1002 | 3 |
| 1003 | 1 |
| 1004 | 2 |
| 1005 | 3 |
| 1006 | 1 |
| 1007 | 2 |
| 1008 | 3 |
| 1009 | 1 |
| 1010 | 2 |
| 1011 | 3 |
| 1012 | 1 |
| 1013 | 2 |
| 1014 | 2 |
| 1015 | 1 |
| 1016 | 2 |
| 1017 | 2 |
| 1018 | 1 |
| 1019 | 2 |
| 1020 | 2 |
| 1021 | 1 |
| 1022 | 1 |
| 1023 | 2 |
| 1024 | 1 |
| 1025 | 1 |
| 1026 | 2 |
| 1027 | 1 |
| 1028 | 1 |
| 1029 | 2 |
| 1030 | 1 |
| 1031 | 3 |
| 1032 | 3 |
| 1033 | 3 |
| 1034 | 3 |
| 1035 | 3 |
| 1036 | 3 |
| 1037 | 3 |
| 1038 | 3 |
| 1039 | 3 |
| 2000 | 3 |
| 2001 | 2 |
| 2002 | 2 |
| 2003 | 1 |
| 2004 | 1 |
| 2005 | 3 |
| 2006 | 1 |
| 2007 | 3 |
| 2008 | 1 |
| 2009 | 3 |
| 2010 | 2 |
| 2011 | 3 |
| 2012 | 2 |
| 2013 | 2 |
| 2014 | 1 |
| 2015 | 3 |
| 2016 | 2 |
| 2017 | 3 |
| 2018 | 1 |
| 2019 | 1 |
| 2020 | 2 |
| 2021 | 2 |
| 2022 | 1 |
| 2023 | 3 |
| 2024 | 2 |
| 2025 | 3 |
| 2026 | 1 |
| 2027 | 1 |
| 2147483647 | 2 |

## Verification summary

Historical candidate proof: **PASS/STRONG**; original initial execution **SUCCEEDED**, DuckDB **1.5.5**. Hidden cases **6/6**; metamorphic **2/2** applicable; properties **1/1** applicable; mutations caught **18/18**, coverage complete. Inapplicable checks are not counted as passes; `QUEUE_RELABEL` was inapplicable here.

Delivery37 proof kind: `retained_final_same_source_suite`; admission, export and relocated replay **PASS**. These describe retained historical evidence. Qualification is differential verification; independent authorship is unproven.

Worker A's light local DuckDB **1.5.5** execution loaded these exact rows and matched column names, output types, ordered rows and typed values. This is only the illustrative fixture check. A fresh full-authoritative claim requires replay B and immutable-package trust checks.

## Traceability

The fixture's `source_bindings` contains repository-relative paths and SHA256 digests for membership, initial execution, candidate verification and FINAL result. Resolve membership by this exact candidate ID: `golden.task` supplies question/schema/tables; `golden.candidate_solution` supplies SQL. `expected` is the unchanged initial execution `result_data`.

Initial execution: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/007-execution.json`  
SHA256: `5b201c7cf1797d2ee6ae31228edec0df5239bfde08f455338cb1f74c5e475150`

Candidate proof: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/007-verification.json`  
SHA256: `afa3f22ff32d0eb7b8fa4f27905ec7f513bba233b8f4fddd9b840189e33976cc`
