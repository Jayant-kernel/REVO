# Internal review — DEVELOPMENT REVIEW PREVIEW

**Verdict: PASS for this separate internal review, with one deferred minor correction. Fresh full-B integration: PENDING coordinator evidence/disposition. External sharing remains BLOCKED; human review remains PENDING.**

## Reviewer disclosure and scope

This is an AI-agent review by the same session that authored Worker A's eight example pages, eight public/base JSON fixtures and examples index. The reviewer previously read original V37 membership, FINAL result, candidate execution/verification evidence and Worker B's illustrative entry, and executed light replay A during that implementation. This pass is a separate review assignment with disclosed prior access, **not blind, not human, and not fully independent**. Self-authorship limits the assurance of the example review.

Read the integrated `START-HERE.md`, frozen `SPEC.md`, all examples/fixtures, all four `replay/*.py` files, both replay documents, every `review/*` document/index, and `audit/baseline.json`. Also inspected selected original V37 sources and the pinned external trust driver's implementation. Paths below are relative to this preview directory unless explicitly described as repository-relative.

This assignment writes only this report. It does not change examples, replay code, documentation, immutable packages, old evidence, source code or baseline. No native/container replay, qualification, model call, installation or full suite was launched. The coordinator owns the active fresh full-B run and final integration/ship decision.

## Findings and disposition

### M01 — deferred minor navigation-label error

**Location:** `START-HERE.md:29`.

The example 07 question label says “Episodes without qualifying member renewal coverage.” The original task returns **every supplied episode expiring in 2025** with `covered BOOLEAN`, including both true and false. The original question, SQL and displayed 16-row result in `examples/07-renewal-coverage.md` are correct; `review/dataset-card.md:19` also describes coverage correctly.

**Bounded fix for the coordinator:** replace that one table-cell label with “Coverage Boolean for each eligible expiry episode.” Preserve the task, SQL, fixture and expected result. This is a misleading navigation summary, not a candidate/fixture or replay-integrity defect. Suitable for explicit minor deferral; no edit was made by this reviewer.

**Blocking actionable findings: none identified in the reviewed snapshot.**

## Checks and evidence

### Exact membership, SQL, fixture and displayed output

Read-only Python assertions cross-checked all eight `examples/index.json` entries against both membership and delivery37 FINAL row order, with IDs exactly `01` through `08`. The example, review evidence index and FINAL row agree on exact candidate/task identity and original record identity. The membership has exactly eight members, each development/TRAIN. No profile-authored alternative replaces an original candidate.

For every example, question, original schema objects and complete table row lists equal `membership.members[exact candidate].golden.task`; SQL equals `golden.candidate_solution`, including whitespace, and its SHA256 equals the FINAL row and review evidence index. `expected` equals the candidate's original initial execution `result_data`, including columns/types, ordered rows, `rows_returned` and `truncated`. All four source bindings per fixture were checked against installed file bytes.

The Markdown input/output tables were parsed back and compared with the fixture data: **286 retained input rows and 209 expected output rows**, all matching. Displayed output type headers, exact question text, SQL code blocks and Markdown links also passed. The pages retain the full fixtures; no reduced examples were substituted.

| ID | Retained input rows | Declared input schema row_count | Expected output rows |
| --- | --- | --- | ---: |
| 01 | fulfillments 7 | 8 | 2 |
| 02 | grade_revisions 40 | 42 | 23 |
| 03 | plays 7 | 10 | 5 |
| 04 | quotes 20 | 8 | 9 |
| 05 | requests 20; translations 18 | 5; 5 | 30 |
| 06 | options 32 | 8 | 15 |
| 07 | episodes 18; renewals 15 | 4; 8 | 16 |
| 08 | submissions 109 | 10 | 109 |

Each page's “Declared schema and assumptions” section explicitly distinguishes original `row_count` metadata from retained insertion counts. `rows_returned` is separately and correctly displayed for output. No generated rows are implied by schema metadata. Original `task.constraints={}` is disclosed without erasing question/domain requirements. Example 02 explicitly distinguishes invalid-grade conflict rejection from executing a valid fixture.

Example 05's expected-output section explicitly preserves the task's **unordered bag** semantics while identifying replay A's exact recorded sequence as a runtime observation, not a portable SQL ordering contract. The duplicate and NULL rows are retained. `START-HERE.md:47-51` and `replay/README.md:24-37` repeat this boundary. No sorting/deduplication was introduced to manufacture a match.

### All eight wrong-query mappings

Read and hash-checked the selected wrong and correct SQL for every indexed V37 profile challenge. Resolved `/details/wrong/0` and `/details/correct/0`, their candidate/SQL/fixture/execution bindings, successful execution statuses, recorded comparison mismatch/match and `KILLED_WRONG_ANSWER`/`MATCH` outcomes. These are inspections of historical execution evidence, not new executions or model-failure observations.

| ID | Selected authored wrong-query mistake confirmed | Correct witness alternative confirmed |
| --- | --- | --- |
| 01 | COUNT(DISTINCT warehouse) undercounts fulfillment rows | COUNT(*) with the eligibility/on-time aggregation |
| 02 | WHERE TRUE admits invalid revisions before ranking | Filter valid revisions before ROW_NUMBER |
| 03 | WHERE TRUE admits non-completed plays into LAG | Filter completed plays before the window |
| 04 | Descending price chooses the highest eligible quote | Ascending price then supplier |
| 05 | Inner join drops unmatched requests | LEFT JOIN on item and requested language |
| 06 | Missing lane correlation permits cross-lane dominance | Correlated same-lane dominance check |
| 07 | Missing member correlation accepts another member's renewal | Same-member interval and exact 14-day threshold |
| 08 | RANK produces row ranks rather than balanced batches | NTILE(3), NULLS LAST, submission-ID tie-break |

All eight first candidate-mutation witnesses separately retain the **actual original candidate SQL**, a caught `SEMANTIC_KILL`, and SUCCEEDED candidate and mutant executions. They were checked against original SQL identity rather than assumed to be the same control as the selected profile challenge.

For 04–08, all **20** indexed historical suite files were present and SHA256-matched. Their original-candidate identities, successful positive/wrong executions and one failing `INDEPENDENT_ADVERSARIAL` case per wrong-hidden artifact were confirmed. The separate suite mistakes (supplier DESC, DISTINCT, both-dimensions-strict dominance, DATE casting and NULLS FIRST) are distinguished from the profile mistakes in `review/evidence-index.md:30-42`. The installed Temp location and lack of relocation/durability promise are explicitly disclosed.

The review performed **161 path/SHA256 binding comparisons** across the machine evidence index, example bindings and selected nested challenge references, plus the **20 suite-file hashes** above. Repeated references are counted as comparisons, not unique files. No hash discrepancy or missing inspected historical source was found.

### Replay claims, workflow and dependencies

Replay A creates isolated in-memory tables, inserts retained rows in order and compares exact names/types, ordered typed rows, count and truncation (`replay/replay.py:83-144`). It disables DuckDB external access and extension auto-loading and requires one SELECT. Its source bindings are explicitly metadata rather than authenticated provenance (`replay/README.md:33-37`), so matching A is not represented as a trust/qualification check.

Reused direct Worker A evidence: the actual eight-fixture illustrative CLI invocation on DuckDB 1.5.5 returned `passed=true` with **all five comparison flags true for all eight records**. That was prior implementation-stage evidence from this same reviewer, not an independent retest. The focused test source was reviewed for names/types/order/value tampering (including bool/int/float distinction), count/truncation, multi-statement refusal, hash and identity failures, fresh-location CLI, selected-pin inspection and a light Windows Job child. This pass did not rerun that suite or convert documented Worker B results into newly observed results.

B1 is accurately limited to selected pins/context/historical inspection (`replay/replay.py:55-80`). It does not claim the full trust traversal. B2 uses fresh disjoint work/output locations, copies the package before writing validation, owns its child in a Windows Job and records terminal state. The native worker checks the pinned trust driver, invokes its full packet/declaration-hash check, checks exact eight-member acceptance/context equality, imports bundled validation and calls the original check_source through observation instrumentation (`replay/native_worker.py:26-86`). Success requires VALID/eight records/zero errors/zero warnings and all eight source checks observed passing. The supervisor's native timeout begins after preparation; documentation states that limitation rather than implying a whole-invocation bound.

The quick-start specifies working directory, installed runtime, new result filename, expected status and failure diagnostics. B documents fresh paths, required package and writing only a workclone. The dependency versions match the immutable `engineering_dependencies.json` runtime map and Python version. Its 49,029 discovered files agree with the census. The baseline distinguishes **123,854 total package files / 602,194,502 bytes** from **123,765 declared release assets / 528,602,604 bytes**. No unsupported slim-package closure is claimed.

**Fresh preview B2 and fresh-location integration remain PENDING coordinator-run evidence and disposition.** This report does not certify that active run, infer a failure from unfinished evidence, or close P04/P08. The coordinator must inspect its terminal/report/per-record outputs and bind the final inventory before claiming completed new B integration. No second heavy run was started for this review.

### Disclosure and sharing

Inspected the thin reviewer layer for raw generation requests/responses, credentials, private endpoints and unrelated content. A bounded, non-value-printing credential/private-endpoint pattern scan over START-HERE, examples, review and replay files returned no matches. Manual inspection found synthetic task data, exact task/candidate identities, hashes and necessary local paths. Absolute Windows example paths reveal local filesystem context but are internal operator instructions, not credentials or service endpoints; package paths are explicitly replaceable. This is not a security audit or permission to distribute the broad dependency package.

The overview, dataset card, limitations, sharing checklist and examples consistently preserve exposed TRAIN, human PENDING, external BLOCKED and utility NOT_MEASURED. Authored controls, actual-candidate transforms, suite controls and the pipeline's INDEPENDENT_ADVERSARIAL label are kept distinct from model failures and independent/human review. Full80/company acceptance stay zero, original completion stays 2/16, strict certification stays false, historical native incidents stay unresolved and W14 stays open. This pass changes none of those statuses.

## Reviewed snapshot identity

These hashes identify the snapshot inspected; coordinator edits after this review require disposition and a focused recheck where relevant.

| File | SHA256 |
| --- | --- |
| START-HERE.md | `9633cd96f343d1045d0e121274c752b1aa62fc798195280ee6d97c6bb2418868` |
| SPEC.md | `e36c65908926032ca4914fe5723e5bca940a37516aa9f471940a329f0ca6cd3b` |
| examples/index.json | `2120acfbf57bfe197ca9c4cf0c17972adb0c055e6cb74e7fdb0f92a0980f5e13` |
| review/evidence-index.json | `0bb7c4a326de0eca40f7a6d0d992b80f3cdb8fa03b02790b71b5f371c0626f07` |
| replay/replay.py | `65e1bc38508b712fc3ffb8d1ae205383ea08d733cd2da5eedabfd975db5ba6ca` |
| replay/native_worker.py | `69595d292c8ddbcdf04443b07c05162f66562409fbfee6586899d297abfdff3c` |
| replay/windows_job.py | `48f66aac69abddc0081e7a502a7b22a7933f47974e0e1ea0e6d6da0c0be98e44` |
| replay/test_replay.py | `9e98b4f9231a5951190d2591951cf2daad998a1eea2172c55676f2baae3b0b5c` |
| audit/baseline.json | `c09e46c9beb124afeaf0aaf4d9bcd285b7973f0ba7ce5c3e2b8fa896acb71ce2` |

**Handoff:** PASS with M01 deferred for coordinator disposition; full-B/fresh-location integration PENDING. This is an internal, prior-access-disclosed AI review only, with no external-sharing authorization.
