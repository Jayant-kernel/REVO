# Stage 2 targeted cold-review correction — 2026-10-08

Status: **targeted correction complete; broader Stage 2 remains partial**.
This adds evidence after `stage2-partial-20261008.md`; that document was not
overwritten. No readiness/producer changes or qualification claims were made.

## Changes

- `src/verified_data_factory/verification/behavior_authority.py`: compare
  requirements using type-sensitive canonical JSON (`_encode`) instead of Python
  equality. Reject duplicate task schema table names before constructing schema
  dictionaries/comparing declarations. Keep the public rules and declaration
  digest in the rejection result; duplicates receive an explicit denial reason.
- `tests/test_stage2_behavior_authority.py`: add a validated float-year regression
  and conflicting duplicate-table regressions in both declaration orders.
- This new evidence document. Every other dirty change was left untouched.

The year regression retains the original instruction, rebuilds through
`TaskInstance.model_validate`, and passes `validate_task`. The real scrap v1
oracle produces three rows for integer year 2025 and zero for float year 2025.0
on the same seed-94001 fixture. Authority must reject the altered requirements.

The duplicate regressions rebuild through `TaskInstance.model_validate` and keep
the original instruction. A nullable-true conflicting declaration preceding the
original formerly disappeared through dictionary overwrite and matched authority.
Both orders now receive `duplicate task schema table declarations`. The separate
`validate_task` routine already rejects duplicate table names; these tests protect
the authority consumer itself, which previously did not enforce that constraint.

## Red / green proof

The first red invocation had test setup errors (missing helper default seed and
using `schema` without alias serialization). These were corrected before recording
the intended-check red results; they are not evidence of the authority defects.

Corrected red command, before the source fix:

```powershell
python -m pytest tests/test_stage2_behavior_authority.py -q -k "numerically_equal_year or conflicting_duplicate"
```

Terminal summary, verbatim:

```text
=========================== short test summary info ===========================
FAILED tests/test_stage2_behavior_authority.py::test_numerically_equal_year_with_different_type_is_not_public_authority
FAILED tests/test_stage2_behavior_authority.py::test_conflicting_duplicate_table_declarations_are_rejected_in_either_order[True]
FAILED tests/test_stage2_behavior_authority.py::test_conflicting_duplicate_table_declarations_are_rejected_in_either_order[False]
3 failed, 17 deselected in 0.68s
```

The first two failures were authority returning True. The original-first duplicate
already returned False but lacked a duplicate-specific rejection; that case failed
on the intended explicit reason check.

Green command:

```powershell
python -m pytest tests/test_stage2_behavior_authority.py tests/test_verify_mutations.py tests/test_engineering_mutation_details.py tests/test_engineering_strength.py -q
```

```text
............................................                             [100%]
44 passed in 10.15s
```

Focused Ruff command:

```powershell
python -m ruff check src/verified_data_factory/verification/behavior_authority.py tests/test_stage2_behavior_authority.py
```

```text
All checks passed!
```

## Confirmed remaining edge-case binding bypass (reported, not fixed)

A local Python probe generated `sql.aggregation.grouped` v2, seed 301, using
`make_task`. It copied `task.model_dump(by_alias=True)`, replaced `edge_cases` with
`[]`, and re-rendered the public instruction template using the original tables
and requirements but `edge_cases=[]`. It rebuilt with `TaskInstance.model_validate`
and ran `validate_task`. The retained tables, seed and generation metadata did not
change. The result printed:

```text
{'contract': 'sql.aggregation.grouped', 'version': 2, 'seed': 301, 'generated_edges': ['null_values', 'single_row_groups', 'zero_values'], 'altered_edges': [], 'instruction_changed': True, 'baseline_matches': True, 'altered_matches': True, 'same_declaration_digest': True, 'model_and_task_validation': 'passed'}
```

Thus caller-controlled edge cases can rewrite the edge-case-dependent public
instruction while still receiving `task_matches_public_contract=True`. This is a
concrete generation/instruction binding bypass, not a demonstrated SQL oracle
output difference or qualification admission. The current map renders expected
instruction using that same untrusted list. The generator normally supplies
sorted `ensured_edges` from fixture generation, rather than blindly copying every
template edge declaration; any future fix must respect that generation contract.
No edge-case validation patch was included in this targeted correction.

No commits, installations, provider calls, full regression, scoring, historical
receipt edits, frozen-asset edits, or journal/index writes occurred. No fresh
profiles were produced. The prior partial document's readiness/producer and
granular-behavior-map continuation remains outstanding.
