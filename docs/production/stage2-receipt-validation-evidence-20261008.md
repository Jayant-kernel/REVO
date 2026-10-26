# Stage 2 bounded receipt-validation evidence — 2026-10-08

Status: **validation slice implemented; Stage 2 remains active/partial**.
Schema: `stage2-receipt-schema-v2-20261008.md` and executable receipt models.
No producer v9 profiles, full qualification positives or cold certification.

## Interrupted work preserved and completed

At resume, the edge-case generator binding patch and five receipt-admission red
tests were present. `readiness.py` was still legacy-only and no receipt model or
validator modules existed. The prior edits were preserved, then integrated with
schema v2 and authoritative qualification. Earlier evidence files were not edited.

The confirmed edge-case witness now denies a model/task-validated grouped task
whose generated edge list was erased and instruction re-rendered. Three seeds
also prove that binding follows actual ensured edges, not blanket declared cases.

Pre-fix edge command:

```powershell
python -m pytest tests/test_stage2_behavior_authority.py -q -k "edge_instruction or actually_ensured"
```

```text
FAILED tests/test_stage2_behavior_authority.py::test_caller_cannot_rewrite_generated_edge_instruction_binding
1 failed, 3 passed, 20 deselected in 0.88s
```

Pre-validator command:

```powershell
python -m pytest tests/test_stage2_receipt_validation.py -q
```

```text
=========================== short test summary info ===========================
FAILED tests/test_stage2_receipt_validation.py::test_summary_only_receipt_is_explicitly_denied_as_legacy
FAILED tests/test_stage2_receipt_validation.py::test_unknown_public_contract_is_not_admitted
FAILED tests/test_stage2_receipt_validation.py::test_caller_cannot_erase_versioned_authoritative_quarantine
FAILED tests/test_stage2_receipt_validation.py::test_missing_or_malformed_quarantine_authority_denies[None]
FAILED tests/test_stage2_receipt_validation.py::test_missing_or_malformed_quarantine_authority_denies[malformed1]
5 failed in 0.44s
```

## Proven scope

- Real scrap v1 canonical fixtures plus content-diverse canonical hidden fixtures
  establish a positive individual fixture validator, not full qualification.
- A separately executed single real-contract pytest probe produces the retained
  XML positive. It is not an invented XML/name list or credited shared test count.
- Actual local DuckDB executions establish positive SQL detail validation, twenty
  distinct wrong challenges with three correct alternatives, and two identified
  relation-transform/discriminator category positives. No sandbox/provider run
  or historical attestation is claimed for these local test executions.
- Negative detail tests hit intended checks for summary disagreement, missing
  reports, report subsets, public/version mismatches, stale producer/core inputs,
  fingerprint/oracle tampering, invented execution IDs, row counts, retained-output
  forgery, invalid SQL, comparison forgery, mutant rule subsets, duplicate
  challenges, altered relation preconditions and invented domain waivers.
- Source-bound observed recipes/classifiers match existing profile helpers on
  both supported contracts. A 900-fixture classified inventory proves arithmetic
  and rejects fake observed counts. This is **not** an executed fuzz receipt
  positive; that requires all retained alternative runs and final validation.
- Journal/index-only binding tests reject index tampering, supersession,
  category/version misattribution and never treat journal shells as category
  positives. Quarantine tests prove missing/malformed authority denial, exact
  versions, erased caller state denial and rejection of invented caller status.
- The independent counter uses the same authoritative qualification function.
  Legacy invented-contract fixtures remain negative forgery/history cases, never
  positive baselines; historical generation-time receipt assertions stay history.

## Files touched by this slice

- `src/verified_data_factory/verification/behavior_authority.py`
- `src/verified_data_factory/verification/readiness.py`
- New `receipt_models.py`, `receipt_validation.py`, `receipt_observations.py` in
  that verification directory.
- `scripts/engineering_readiness_count.py`
- `tests/test_stage2_behavior_authority.py`
- New `tests/test_stage2_receipt_validation.py`
- `tests/test_engineering_readiness.py`
- `tests/test_engineering_receipt_outcomes.py`
- `tests/test_engineering_qualification_receipts.py`
- New schema/evidence documents; one scoped Unreleased changelog entry.

Every other dirty change was preserved. No histories, existing receipts,
authoritative manifests, frozen scorer/rubric/score tests/known-edge assets or
journals/indexes were edited. Test artifacts are isolated temporary fixtures.

## Verification and remaining limitations

Final focused commands/results after the names-only clarification of legacy test
functions:

```powershell
python -m pytest tests/test_stage2_receipt_validation.py tests/test_stage2_behavior_authority.py tests/test_engineering_readiness.py tests/test_engineering_receipt_outcomes.py tests/test_engineering_qualification_receipts.py tests/test_verify_mutations.py tests/test_engineering_strength.py tests/test_engineering_mutation_details.py -q
```

```text
........................................................................ [ 66%]
.....................................                                    [100%]
109 passed in 25.01s
```

```powershell
python -m ruff check src/verified_data_factory/verification/behavior_authority.py src/verified_data_factory/verification/readiness.py src/verified_data_factory/verification/receipt_models.py src/verified_data_factory/verification/receipt_validation.py src/verified_data_factory/verification/receipt_observations.py scripts/engineering_readiness_count.py tests/test_stage2_behavior_authority.py tests/test_stage2_receipt_validation.py tests/test_engineering_readiness.py tests/test_engineering_receipt_outcomes.py tests/test_engineering_qualification_receipts.py
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

Scoped `git diff --check` returned no output. Mypy silently followed dependencies;
this is not a whole-project type-check claim. No full regression, score, provider
call, installation, commit or Stage 3+ work occurred.

The producer is unchanged. Rules/mutations deliberately remain blocked where the
public ledger lacks granular instruction coverage or a supported domain proof.
Core source closure is conservative and broad, not a narrow producer closure.
Retained execution consistency plus replay is not cryptographic attestation.
Independent cold review and real producer positives, including full retained fuzz
execution evidence, are still required before Stage 2 completion or fresh v9.
