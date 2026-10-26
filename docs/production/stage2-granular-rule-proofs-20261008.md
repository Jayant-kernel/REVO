# Stage 2 granular rule and mutation proofs — 2026-10-08

Status: **supported rule/mutation categories verified; Stage 2 remains partial**.
This continuation completed the partially written granular-rule slice left by
the interrupted session. It does not certify whole-contract qualification,
runtime STRONG coverage, catalog eligibility, or an engineering score.

## Public authority and retained execution

Exactly two public versions have explicit granular maps:
`sql.funnel.saas_activation_payment@2` and
`sql.aggregation.manufacturing_line_scrap@1`. Other contracts retain their opaque
instruction obligations and cannot inherit these dispositions.

The maps retain every requirement, declared edge case and schema column, and
add exact version-bound instruction clauses. Scrap instruction proofs distinguish
SUM semantics, eligibility, grouping, year filtering and ascending order. SaaS
proofs distinguish ordered steps, first matching events, sequence ties, scope,
matched payment, segment aggregation, incomplete-segment zero totals, ordering,
ignored unexpected steps, fixed entity segments and unique event ordering.

The validator reconstructs the full public ledger and canonical discriminators.
It replays retained correct/wrong SQL and checks SQL text and fixture attribution;
receipt-supplied subsets or unrelated mutant rule IDs cannot earn coverage.
Mutation receipts require the unchanged minimum of at least three distinct
semantic mutants and complete applicable public semantic-rule coverage. Shared
clauses reuse a discriminator only when their canonical proof SQL and fixture
actually coincide.

Input-domain proofs are separate from semantic mutation kills. Schema witnesses
retain column-specific NOT NULL rejection, replay declared type/nullability via
DESCRIBE, and execute invalid conversion probes for INTEGER/TIMESTAMP. VARCHAR's
unrestricted non-null coercive SQL domain has an explicit applicability reason
and an executed conversion check. No enum, positivity or uniqueness restrictions
are invented. SaaS fixed-segment and duplicate event-order rejection use the
public oracle's existing valid-input constraints.

## Verification on the final source

```powershell
python -m pytest tests/test_stage2_granular_rules.py tests/test_stage2_behavior_authority.py tests/test_stage2_receipt_validation.py tests/test_stage2_receipt_producer.py tests/test_engineering_rule_qualification.py tests/test_engineering_mutation_details.py tests/test_verify_mutations.py tests/test_engineering_readiness.py -q -k "not full_900"
```

Result: **145 passed, 2 deselected in 70.75s**. The two deselected tests are the
expensive full fuzz proofs. Their earlier results remain historical evidence in
`stage2-producer-fuzz-performance-20261008.md`; they were not rerun or represented
as fresh full-bundle receipts for this source revision.

Both supported contracts emitted rule and mutation category receipts into pytest
temporary folders and passed fresh independent consumer replay. Negative cases
cover incomplete ledgers, invented required-rule subsets, unrelated SQL
attribution, missing/mismatched type checks, invented source clauses and
unsupported contracts. Existing blocked-receipt assertions remain intact.

```powershell
python -m ruff check src/verified_data_factory/verification/behavior_authority.py src/verified_data_factory/verification/public_rule_proofs.py src/verified_data_factory/verification/receipt_models.py src/verified_data_factory/verification/receipt_validation.py scripts/engineering_receipt_artifacts.py scripts/engineering_rule_audit.py tests/test_stage2_granular_rules.py
python -m mypy src --strict
```

Results: **All checks passed**; **no issues found in 166 source files**.
The scoped five-file producer/validator mypy command with explicit package bases
also passed before the final optional-tool import adjustment. The final full-src
command above is the current package typing evidence.

```powershell
python -c "from scripts.engineering_campaign import safety; safety(); print('Frozen asset and paused-run guard passed')"
git diff --check
```

The frozen asset/paused-run guard passed. Diff checking found no whitespace errors
(Git printed existing LF/CRLF notices). Intermediate lint/type failures in the
unfinished code and two ordering-of-validation regressions were repaired before
the final passing run; no assertions were weakened.

## Remaining serial work

The legacy `engineering_qualification_receipts.py` entry point still emits
summary-only evidence and needs integration with the detailed writer. Complete
current bundles must cover all categories, consumed private/reference inputs,
exact named-test attribution and catalog enumeration. Authoritative journal/index
promotion, runtime candidate rule coverage, independent Stage 2 certification and
fresh v9 generation remain outstanding. Current all-catalog qualification and
engineering scoring have not been established by this slice. No v9, journal/index,
provider calls, commits or pushes were performed.
