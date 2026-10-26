# Stage2 preliminary retained-artifact producer — 2026-10-08

Status: **partial, blocked; Stage2 remains incomplete**. No qualified-receipts-v9
directory, authority events, index materialization, runtime STRONG attribution,
scoring, installations, model calls or commits were made by this work.
Historical files and the frozen rubric were preserved.

## Implemented bounded preliminary outcome

`scripts/engineering_receipt_artifacts.py` adds an append-only `ArtifactWriter`
for exactly SaaS@2 and manufacturing scrap@1. It retains the canonical base task,
canonical materialized fixture cells and typed oracle expectations, SQL text,
manual/local candidate metadata, genuine execution records from the existing
sandbox wire collector, and complete comparisons. SQL actually executes locally
with external access disabled, one DuckDB thread, 128 MB, an interrupt timer and
a bounded row fetch. Local provenance is explicit: no container or model run is
claimed, and unmeasured memory is not invented. The collector records actual
timestamps, IDs and the existing result/stdout byte conventions. Invalid SQL
retains an EXECUTION_ERROR record and raises rather than becoming a semantic kill.

Builders exist for fixture diversity, attributed named-test XML, challenges,
contract relations and deterministic observed fuzz. Category metrics and execution
counts come from the existing detail validator, not caller claims; receipts are
replay-validated before emission. The source closure conservatively locks all src,
template, script and test Python inputs plus the core rubric/journal helper and
explicit additional consumed inputs. A source changed during collection denies
emission rather than being silently rehashed. Consumers must explicitly register
additional private JSON/Python, reference SQL and configuration inputs. This is
not yet a complete production-profile dependency inventory.

`catalog_blockers()` enumerates all latest public template identities and reports
each as ineligible; it does not hardcode a population or infer qualification from
profile support. `qualified-receipts-v9` is explicitly reserved pending source
stability and independent cold review. This helper does not invoke `qualify` to
invent positive eligibility, and cannot emit rules/mutation categories.

## Focused proof

Command:

```powershell
python -m pytest tests/test_stage2_receipt_producer.py -q -k "not full_900"
```

Output verbatim:

```text
........                                                                 [100%]
8 passed, 2 deselected in 20.80s
```

These positives exercise both profiles' local SQL and four-fixture diversity,
one genuinely executed named scrap test with exact node/contract/version XML
properties, twenty distinct scrap wrong challenges with three correct alternatives
on their retained fixture, and two scrap relation transforms whose wrong query
matches before and is killed afterward. Negative probes cover stale producer
sources, append-only paths, SQL execution failure and the v9 reservation.
They explicitly do not establish whole-contract eligibility.

Commands:

```powershell
python -m ruff check scripts/engineering_receipt_artifacts.py tests/test_stage2_receipt_producer.py
$env:MYPYPATH='src'; python -m mypy scripts/engineering_receipt_artifacts.py --follow-imports=silent
```

Outputs verbatim:

```text
All checks passed!
Success: no issues found in 1 source file
```

Strict mypy uses the repository configuration and silently follows imports;
this is scoped checking, not whole-project certification.

## Full fuzz attempt did not complete

Command:

```powershell
python -m pytest tests/test_stage2_receipt_producer.py -q
```

Output and tool result verbatim:

```text
.....

<shell_metadata>
shell tool terminated command after exceeding timeout 1200000 ms. If this command is expected to take longer and is not waiting for interactive input, retry with a larger timeout value in milliseconds.
</shell_metadata>
```

The run did not establish either full 900-case positive. Do not interpret partial
temporary artifacts as completed receipts or authoritative evidence. Two full
fuzz tests are present for later execution, each requesting 900 source-bound cases
and 2700 distinct real executions. Their runtime needs investigation before
rerunning: the writer and receipt API perform repeated per-witness materialization
and replay, and the test writes many separate artifacts on Windows. These are
possible cost sources, not profiled findings. No fourth blind retry was attempted.

Earlier failures were diagnosed and fixed: the initial mypy invocation lacked the
src module search path, Ruff found an unused import/string-parenthesization issue,
and the initial receipt envelope omitted its required category field. The focused
green commands above ran after those corrections.

## Remaining director-owned scope

- Explicit source-bound granular public instruction/requirements/schema behaviors,
  including tie/null domains and legal dispositions, are not implemented here.
- Rules and mutation receipt positives remain blocked by the existing opaque
  instruction ledger and rule validator's unconditional unresolved-coverage gate.
  No generic mutant was arbitrarily assigned to unrelated rule IDs.
- Contract-specific executed runtime discriminator attribution is not implemented;
  operator-name guessing and fake STRONG status remain forbidden.
- Full SaaS challenge/relation/named-test profile integration, actual 900-case
  positives for both contracts, and final consumed private-input closure remain.
- The existing `engineering_qualification_receipts.py` legacy CLI is unchanged;
  it is not a v2 producer entry point and should not be used to claim completion.
- Per-category ACTIVE events and legitimate index materialization must wait for
  completed source-stable profiles and independent cold review. Existing journal
  and index history were not touched.

Changed files for this preliminary work are only the new helper, its new producer
test file and this new evidence/handoff document. Full certification, cold review,
the v9 production run and Stage3+ work were not performed.
