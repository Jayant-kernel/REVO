# Evidence index — eight business-query rejection mappings

**Historical V37 mappings plus separately retained coordinator preview integration.** Worker C inspects evidence and does not launch new runtime validation. [evidence-index.json](evidence-index.json) pins installed source files with SHA256 and original candidate/record/SQL identities; its `preview_integration` section separately pins the new coordinator results. Source paths in that JSON are relative to repository root; Markdown sibling links are relative to this directory. No raw requests or private endpoints are reproduced.

## How to follow a claim

The global `final_result` and `handoff` bind the delivery status and each candidate row. `membership` binds exact package membership. `verification` and `evidence_origin` bind the original candidate to fresh V37 rejudge (01–03) or retained same-source suite proof (04–08). The verification's `/mutation/details/0` contains `retained_executions`: original candidate SQL, authored transformed SQL, tables, expected result, and both successful executions. It records `SEMANTIC_KILL`; compare the original SQL digest with the row's `sql_sha256`. This is actual-candidate evidence, distinct from profile challenges.

For every row, the pinned V37 `challenge` receipt's `/details/wrong/0` retains candidate, SQL, fixture-table and execution references with hashes, expected output, comparison and `KILLED_WRONG_ANSWER`. The selected SQL and execution pins are repeated in the machine index. `/details/correct/0` retains a `MATCH` with equivalent reference detail; its SQL is also pinned explicitly. Both selected executions were inspected as SUCCEEDED. These are authored challenges/correct alternatives on retained witnesses, not observed model failures or a claim of universal equivalence. The eight existing named profile sources are pinned too; `FINAL-RESULT.rows[n].qualification.evidence` additionally binds mutation and named-test receipts. The installed challenge/mutation/named-test receipts and selected wrong/correct references passed 88 source-hash comparisons during this documentation task.

## Selected profile wrong query and verified correction

| ID | Existing profile | Recorded wrong-query mistake | Recorded correct alternative | Witness selector |
|---|---|---|---|---|
| 01 | `sla_profile.py` | `COUNT(DISTINCT warehouse)` collapses fulfillment count within a warehouse | `COUNT(*)`; run-62 matches | V37 challenge wrong[0]: v27 run-42; correct[0]: v27 run-62 |
| 02 | `grade_revisions_profile.py` | `WHERE TRUE` ranks invalid grade revisions too | Filter `revision_status='valid'` before ranking; run-69 matches | V37 challenge wrong[0]: v27 run-45; correct[0]: v27 run-69 |
| 03 | `previous_play_profile.py` | `WHERE TRUE` allows non-completed plays into `LAG` | Filter `status='completed'` before the window; run-70 matches | V37 challenge wrong[0]: v27 run-47; correct[0]: v27 run-70 |
| 04 | `lowest_quote_profile.py` | Descending price selects the highest rather than lowest quote | Ascending price then supplier; run-86 matches | V37 challenge wrong[0]: v28 run-61; correct[0]: v28 run-86 |
| 05 | `language_titles_profile.py` | Inner join loses unmatched requests | Requested-language LEFT JOIN; run-118 matches | V37 challenge wrong[0]: v30 run-93; correct[0]: v30 run-118 |
| 06 | `pareto_shipping_profile.py` | Missing lane correlation allows another lane to dominate | Correlate `p.lane=o.lane`; run-101 matches | V37 challenge wrong[0]: v30 run-76; correct[0]: v30 run-101 |
| 07 | `renewal_coverage_profile.py` | Missing member correlation lets another member's renewal cover an episode | Correlate `r.member_id=e.member_id`; run-133 matches | V37 challenge wrong[0]: v33 run-107; correct[0]: v33 run-133 |
| 08 | `queue_batches_profile.py` | `RANK()` gives row ranks rather than three batches | `NTILE(3)` with NULLS LAST and ID tie-break; run-110 matches | V37 challenge wrong[0]: v34 run-84; correct[0]: v34 run-110 |

All eight selected wrong queries executed successfully and were recorded as wrong answers, not syntax/runtime errors. The corrections above summarize the actual pinned correct SQL; their profile candidate identities differ from the original delivered candidates.

## Candidate-transform cross-check

Each machine row's `mutation_selector` resolves inside that candidate's pinned verification. For example 01's first retained transform changes the fulfillment count: expected `['a',2,2]`, mutant `['a',1,2]`, with original and mutant SUCCEEDED. 03's first transform substitutes zero for missing previous-play IDs where expected is null. These are not necessarily the same SQL bytes or same business mistake as the profile's first challenge. Retained executions allow the reviewer to inspect the exact SQL and fixture rather than inferring a rejection from a summary score. No quality score is invented or extrapolated.

## Additional final-suite wrong-query evidence for 04–08

Pinned `tests/test_delivery_adversarial.py` defines `WRONG_SQL` (lines 42–70), checks successful execution plus a semantic mismatch (95–98), and retains wrong execution / hidden checks for the original-candidate test (150–159). The original-identity check and fixture result are also retained. All five indexed `wrong-execution.json` files report SUCCEEDED and their `wrong-hidden.json` files have one `INDEPENDENT_ADVERSARIAL` FAIL. `identity.json` matches the original candidate ID; `fixture-execution.json` is the positive original-candidate counterpart. These are real installed full-suite artifacts, not assertions inferred merely from test source. The machine index pins all four files per case.

| ID | Separate authored suite `WRONG_SQL` mistake | Retained suite slot |
|---|---|---|
| 04 | Supplier descending reverses the ascending tie-break | `test_original_native_verifier_0` |
| 05 | DISTINCT erases required duplicate multiplicity | `test_original_native_verifier_1` |
| 06 | Strictly smaller in both dimensions misses one-dimension equality domination | `test_original_native_verifier_2` |
| 07 | Casting to DATE loses the exact 14-day timestamp boundary | `test_original_native_verifier_3` |
| 08 | NULLS FIRST puts null timestamps in the wrong NTILE order | `test_original_native_verifier_4` |

The suite root is an installed local Temp directory outside the repository, expressed only as a relative path in JSON. Its presence was checked here; durable inclusion in a relocated preview is not claimed. 01–03 do not have this five-contract `WRONG_SQL` suite mapping; their profile challenges and candidate-specific retained mutations supply recorded executable negatives instead.

## Baseline, trust and remaining gates

The coordinator's [new fresh-location integration](../audit/integration-result.json) is PASS with eight illustrative A and eight authoritative B records, no original-checkout imports, and the local package dependency still required. [New native bundled validation](../audit/native-bundled-validation-result.json) reports VALID/eight records/zero errors/zero warnings and the exact pinned supplied context. [Per-record native results](../audit/native-per-record-results.json) identify all eight original record/candidate pairs as PASS. The [focused log](../audit/focused.stderr.log) records six tests OK, with [exit 0 and no timeout](../audit/focused-terminal.json). These are new preview results, not replacements for historical baseline measurements or authored challenge evidence.

The [separate internal AI review](../audit/INTERNAL-REVIEW.md) reports PASS, prior Worker A authorship/access disclosed and no blocking findings, with minor M01 concerning the renewal navigation label. [START-HERE](../START-HERE.md) now correctly describes coverage for each eligible episode. The review's then-pending B language and snapshot hashes are retained as written; later coordinator reports above establish B completion. This index update does not imply that the earlier review covered subsequent edits, or that AI review satisfies pending human review.

Global pins cover delivery counts, original checklist and frozen package size. `anchor`, `quality_context` and `manifest` are authoritative V37 pins, not a new preview validation result. `HANDOFF.md` explains source freeze, seven trust/role rejection controls and certification limits. The 123,854 total-file baseline differs intentionally from 123,765 manifest-declared files. The preview does not slim or replace the 602,194,502-byte package. Replay A differs from B; original progress remains 2/16, accepted80/company-showcase 0, HUMAN_PENDING, SHARE_BLOCKED, utility unmeasured, strict certificate false. Full80 gates and W14 remain open.
