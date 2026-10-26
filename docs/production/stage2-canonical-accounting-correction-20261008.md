# Stage 2 canonical bindings and execution accounting correction — 2026-10-08

Status: targeted correction of two reproduced cold-verifier failures. This is a
new append-only evidence document; previous evidence/schema documents and all
historical receipts remain unchanged. No producer changes or new profiles.

## 1. Oracle and database content now agree

The old fixture validator fingerprinted typed DuckDB contents but passed raw JSON
to the oracle. An eligible scrap row with amount 3 and timestamp
`" 2025-01-01 00:00:00"` materialized as the same database row as its unpadded form.
The raw-JSON oracle returned no rows while correct SQL returned `["g", 3]`, so a
false `KILLED_WRONG_ANSWER` record passed validation.

`DetailValidator.fixture` now reads the materialized rows back into typed cells
before fingerprint validation and oracle evaluation. All semantic category paths
reuse that fixture method and receive those same cells for SQL replay, relation
transforms and observation classification. Rejected-domain witnesses remain raw
rejection inputs; they do not establish semantic oracle outcomes.

The old empty expected result now denies as
`fixture expected result differs from current oracle`. The correctly bound expected
result is `["g", 3]`, and the genuine SQL result remains MATCH. Additional positive
cases cover INTEGER coercion and VARCHAR conversion, proving that raw JSON types
cannot substitute for the database's actual typed contents in the oracle.

## 2. Successful execution accounting is reconciled

The actual serializer conventions were inspected in
`sandbox/executor.py:_success` and `_elapsed_ms`:

- Successful durations use elapsed start/finish timestamps, truncated to integer
  milliseconds. The validator accepts at most **1 ms** difference from actual
  timestamp elapsed time; missing timezone information and larger contradictions
  deny. Both duration fields must still agree.
- The timed container run sits inside staging/collection wall time. Success may
  exceed the declared timeout by only a fixed **250 ms** accounting overhead.
  This is an explicit bounded receipt policy, not measured evidence of the timing
  split. Six seconds under a five-second limit denies; longer unaccounted overhead
  cannot simply be labelled successful.
- If peak memory is reported, it must be finite, nonnegative and no greater than
  the retained applied memory limit. Missing measurement is not invented as zero;
  the actual sandbox serializer permits an unmeasured memory value.
- Untruncated retained stdout and stderr must fit their separate UTF-8 byte caps.
  Character counts cannot replace byte lengths.
- Result `output_bytes` must exactly equal the current serializer convention:
  `len(json.dumps({"columns": len(columns), "rows": rows}, default=str).encode("utf-8"))`.
  This intentionally uses the serializer's default separators and ASCII escaping,
  not compact/sorted receipt JSON or the entire stdout protocol envelope. The
  recomputed result bytes must fit `max_result_bytes`.

The local execution fixture now records actual start/finish timing and result-byte
accounting instead of placeholder zero bytes. A positive test executes real local
DuckDB SQL, passes its output through the real sandbox collector without creating
a Docker runner, and validates the resulting record at exact result/stdout byte
limits. This is a serializer/local-execution proof, not a container-run claim.
Unicode output and bounded millisecond tolerance are covered explicitly.

## Red evidence

Before the validator correction:

```powershell
python -m pytest tests/test_stage2_receipt_validation.py -q -k "noncanonical_timestamp or success_accounting"
```

Terminal output summary, verbatim:

```text
=========================== short test summary info ===========================
FAILED tests/test_stage2_receipt_validation.py::test_noncanonical_timestamp_cannot_turn_correct_sql_into_a_semantic_kill
FAILED tests/test_stage2_receipt_validation.py::test_success_accounting_forgeries_are_rejected[elapsed-execution timestamp/duration accounting mismatch]
FAILED tests/test_stage2_receipt_validation.py::test_success_accounting_forgeries_are_rejected[timeout-successful execution exceeds timeout accounting budget]
FAILED tests/test_stage2_receipt_validation.py::test_success_accounting_forgeries_are_rejected[memory-execution measured memory exceeds resource limit]
FAILED tests/test_stage2_receipt_validation.py::test_success_accounting_forgeries_are_rejected[stdout-execution retained stdout exceeds byte limit]
FAILED tests/test_stage2_receipt_validation.py::test_success_accounting_forgeries_are_rejected[stderr-execution retained stderr exceeds byte limit]
FAILED tests/test_stage2_receipt_validation.py::test_success_accounting_forgeries_are_rejected[result_bytes-execution output byte accounting mismatch]
7 failed, 1 passed, 45 deselected in 3.86s
```

The already-working result-limit check is the passing case. The canonical probe
initially allowed either rejection or canonicalization; the implemented policy
is canonicalization, with a separate positive MATCH witness and exact oracle
disagreement denial for the forged record.

## Focused green evidence

```powershell
python -m pytest tests/test_stage2_receipt_validation.py tests/test_stage2_behavior_authority.py tests/test_verify_mutations.py tests/test_engineering_strength.py tests/test_engineering_mutation_details.py -q
```

```text
........................................................................ [ 67%]
..................................                                       [100%]
106 passed in 28.69s
```

```powershell
python -m ruff check src/verified_data_factory/verification/receipt_validation.py tests/test_stage2_receipt_validation.py
```

```text
All checks passed!
```

```powershell
python -m mypy src/verified_data_factory/verification/behavior_authority.py src/verified_data_factory/verification/readiness.py src/verified_data_factory/verification/receipt_models.py src/verified_data_factory/verification/receipt_validation.py src/verified_data_factory/verification/receipt_observations.py scripts/engineering_readiness_count.py --follow-imports=silent
```

```text
Success: no issues found in 6 source files
```

Mypy silently followed imports; this is scoped evidence, not a whole-project
type-check. The recorded checks ran after source/test changes; only this new
evidence document and its scoped changelog entry were added afterward.

## Changed files and boundaries

- `src/verified_data_factory/verification/receipt_validation.py`
- `tests/test_stage2_receipt_validation.py`
- This new evidence document and one Unreleased changelog entry.

Other dirty changes were preserved. No producer, historical receipt, prior
evidence, frozen asset, authoritative journal/index or manifest edits. No full
regression, scoring, provider calls, installations, commits or Stage 3+ work.

Additional focused Ruff scope after the evidence append:

```powershell
python -m ruff check src/verified_data_factory/verification/behavior_authority.py src/verified_data_factory/verification/readiness.py src/verified_data_factory/verification/receipt_models.py src/verified_data_factory/verification/receipt_validation.py src/verified_data_factory/verification/receipt_observations.py scripts/engineering_readiness_count.py tests/test_stage2_behavior_authority.py tests/test_stage2_receipt_validation.py
```

```text
All checks passed!
```

Scoped `git diff --check` returned no output.
