# 02 — Current valid grade revisions

> DEVELOPMENT REVIEW PREVIEW · exposed development/TRAIN · human review PENDING · external sharing BLOCKED.

Illustrative replay based on retained public base fixture; not full authoritative validation.

Candidate: `sql.dedup.education_grade_revisions.v2.78bb3766bf95.qwen3-8b.04.1e77446511d8`  
Task: `sql.dedup.education_grade_revisions.v2.78bb3766bf95`  
[Machine-readable fixture](02-grade-revisions.json) · [Example index](index.json)

## Original question

From the grade_revisions table, show the current grade for each student and course from the most recently recorded valid revision. Ignore cancelled corrections before choosing a winner. If valid revisions share a timestamp, use the higher revision_id. Leave out student-course pairs with no valid revision. Among valid rows, equal student_id, course_id, recorded_at, and revision_id identify an immutable revision whose grade must agree; reject conflicting valid grades at that identity. Exact repeated valid rows are allowed and do not create another winner. Return student_id, course_id, grade, recorded_at, and revision_id, ordered by student_id and course_id.

## Declared schema and assumptions

Original schema objects are retained in the JSON fixture. `grade_revisions`: declared `row_count=42`, `row_kind=grade_revisions`; actual retained rows: **40**. Declared row counts are source metadata, not replay insertion counts. Original `task.constraints` is `{}`. The question defines immutable valid revision identity, filtering and tie-breaking; no additional column meanings or uniqueness are inferred. Rejecting conflicting grades is an input-domain validation requirement; replay of this valid fixture does not prove that rejection behavior.

| Column | Type | Nullable |
| --- | --- | --- |
| revision_id | INTEGER | false |
| student_id | INTEGER | false |
| course_id | INTEGER | false |
| recorded_at | TIMESTAMP | false |
| revision_status | VARCHAR | false |
| grade | VARCHAR | false |

## Retained public base inputs

Strings are JSON-quoted to preserve whitespace and case. `null` means SQL NULL. Rows retain original fixture order.

| revision_id | student_id | course_id | recorded_at | revision_status | grade |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | "2025-01-01 10:00:00" | "valid" | "B" |
| 2 | 1 | 1 | "2025-02-01 10:00:00" | "valid" | "A" |
| 3 | 1 | 1 | "2025-03-01 10:00:00" | "cancelled" | "F" |
| 4 | 1 | 1 | "2025-02-01 10:00:00" | "valid" | "A+" |
| 5 | 2 | 2 | "2025-07-01 10:00:00" | "cancelled" | "C" |
| 6 | 3 | 3 | "2025-05-01 10:00:00" | "valid" | "B" |
| 7 | 1 | 2 | "2025-04-01 10:00:00" | "valid" | "C" |
| 8 | 5 | 1 | "2025-07-22 05:00:00" | "valid" | "D" |
| 9 | 6 | 2 | "2025-12-02 20:00:00" | "cancelled" | "A" |
| 10 | 7 | 3 | "2025-03-22 19:00:00" | "valid" | "C" |
| 11 | 10 | 2 | "2025-05-03 13:00:00" | "valid" | "B" |
| 12 | 5 | 2 | "2025-12-19 21:00:00" | "valid" | "B" |
| 13 | 12 | 4 | "2025-05-25 22:00:00" | "cancelled" | "C" |
| 14 | 6 | 2 | "2025-07-19 16:00:00" | "valid" | "C" |
| 15 | 10 | 1 | "2025-04-23 18:00:00" | "valid" | "D" |
| 16 | 7 | 2 | "2025-03-27 23:00:00" | "valid" | "C" |
| 17 | 8 | 1 | "2025-07-30 19:00:00" | "cancelled" | "A" |
| 18 | 7 | 3 | "2025-08-20 16:00:00" | "valid" | "D" |
| 19 | 6 | 2 | "2025-01-21 05:00:00" | "valid" | "B" |
| 20 | 9 | 5 | "2025-01-30 09:00:00" | "valid" | "B" |
| 21 | 10 | 1 | "2025-02-26 17:00:00" | "valid" | "B" |
| 22 | 9 | 5 | "2025-12-14 04:00:00" | "valid" | "D" |
| 23 | 8 | 5 | "2025-08-25 20:00:00" | "valid" | "A" |
| 24 | 11 | 3 | "2025-10-28 03:00:00" | "valid" | "D" |
| 25 | 7 | 4 | "2025-09-20 15:00:00" | "valid" | "A" |
| 26 | 8 | 5 | "2025-07-17 02:00:00" | "cancelled" | "C" |
| 27 | 4 | 2 | "2025-06-11 13:00:00" | "valid" | "D" |
| 28 | 4 | 4 | "2025-03-08 03:00:00" | "valid" | "D" |
| 29 | 5 | 2 | "2025-12-18 20:00:00" | "valid" | "C" |
| 30 | 11 | 5 | "2025-12-12 14:00:00" | "valid" | "B" |
| 31 | 8 | 2 | "2025-02-21 11:00:00" | "valid" | "B" |
| 32 | 6 | 3 | "2025-03-27 02:00:00" | "valid" | "D" |
| 33 | 11 | 4 | "2025-11-26 22:00:00" | "valid" | "A" |
| 34 | 5 | 4 | "2025-04-29 03:00:00" | "valid" | "B" |
| 35 | 12 | 3 | "2025-07-24 12:00:00" | "valid" | "B" |
| 36 | 12 | 1 | "2025-11-01 22:00:00" | "valid" | "A" |
| 37 | 9 | 5 | "2025-11-26 20:00:00" | "valid" | "B" |
| 38 | 9 | 4 | "2025-05-14 17:00:00" | "cancelled" | "A" |
| 39 | 7 | 3 | "2025-04-22 09:00:00" | "valid" | "C" |
| 40 | 5 | 2 | "2025-09-14 18:00:00" | "valid" | "D" |

## Original candidate SQL

```sql
SELECT 
    student_id, 
    course_id, 
    grade, 
    recorded_at, 
    revision_id
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY student_id, course_id 
            ORDER BY 
                recorded_at DESC, 
                revision_id DESC
        ) AS rn
    FROM (
        SELECT 
            *,
            CASE WHEN revision_status = 'valid' THEN 1 ELSE 0 END AS is_valid
        FROM grade_revisions
    )
    WHERE is_valid = 1
) 
WHERE rn = 1
ORDER BY student_id, course_id
```

## Expected output — original initial execution

`rows_returned=23`, `truncated=false`. Column names/types and row order are retained exactly.

| student_id (INTEGER) | course_id (INTEGER) | grade (VARCHAR) | recorded_at (TIMESTAMP) | revision_id (INTEGER) |
| --- | --- | --- | --- | --- |
| 1 | 1 | "A+" | "2025-02-01 10:00:00" | 4 |
| 1 | 2 | "C" | "2025-04-01 10:00:00" | 7 |
| 3 | 3 | "B" | "2025-05-01 10:00:00" | 6 |
| 4 | 2 | "D" | "2025-06-11 13:00:00" | 27 |
| 4 | 4 | "D" | "2025-03-08 03:00:00" | 28 |
| 5 | 1 | "D" | "2025-07-22 05:00:00" | 8 |
| 5 | 2 | "B" | "2025-12-19 21:00:00" | 12 |
| 5 | 4 | "B" | "2025-04-29 03:00:00" | 34 |
| 6 | 2 | "C" | "2025-07-19 16:00:00" | 14 |
| 6 | 3 | "D" | "2025-03-27 02:00:00" | 32 |
| 7 | 2 | "C" | "2025-03-27 23:00:00" | 16 |
| 7 | 3 | "D" | "2025-08-20 16:00:00" | 18 |
| 7 | 4 | "A" | "2025-09-20 15:00:00" | 25 |
| 8 | 2 | "B" | "2025-02-21 11:00:00" | 31 |
| 8 | 5 | "A" | "2025-08-25 20:00:00" | 23 |
| 9 | 5 | "D" | "2025-12-14 04:00:00" | 22 |
| 10 | 1 | "D" | "2025-04-23 18:00:00" | 15 |
| 10 | 2 | "B" | "2025-05-03 13:00:00" | 11 |
| 11 | 3 | "D" | "2025-10-28 03:00:00" | 24 |
| 11 | 4 | "A" | "2025-11-26 22:00:00" | 33 |
| 11 | 5 | "B" | "2025-12-12 14:00:00" | 30 |
| 12 | 1 | "A" | "2025-11-01 22:00:00" | 36 |
| 12 | 3 | "B" | "2025-07-24 12:00:00" | 35 |

## Verification summary

Historical candidate proof: **PASS/STRONG**; original initial execution **SUCCEEDED**, DuckDB **1.5.5**. Hidden cases **5/5**; metamorphic **3/3** applicable; properties **1/1** applicable; mutations caught **8/8**, coverage complete. Inapplicable checks are not counted as passes.

Delivery37 proof kind: `fresh_original_candidate_native_rejudge`; admission, export and relocated replay **PASS**. These describe retained historical evidence. Qualification is differential verification; independent authorship is unproven.

Worker A's light local DuckDB **1.5.5** execution loaded these exact rows and matched column names, output types, ordered rows and typed values. This is only the illustrative fixture check. A fresh full-authoritative claim requires replay B and immutable-package trust checks.

## Traceability

The fixture's `source_bindings` contains repository-relative paths and SHA256 digests for membership, initial execution, candidate verification and FINAL result. Resolve membership by this exact candidate ID: `golden.task` supplies question/schema/tables; `golden.candidate_solution` supplies SQL. `expected` is the unchanged initial execution `result_data`.

Initial execution: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/001-execution.json`  
SHA256: `821e31c0a71972c6f5b7933b43adc952c948d91d6670b6140a58d353e2d15c8d`

Candidate proof: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/original-pool/001-verification.json`  
SHA256: `d883491cbcd3706e01f09d206c85e131ca5d616fd818984b8efdb3a4c3454be0`
