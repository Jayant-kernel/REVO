# Dataset card — development review only

## Identity and intended use

This preview contains exactly the eight members of `artifacts/internal-deliveries/v37-original8-001/original8/packet/membership.json`, in delivery37 `FINAL-RESULT.json` row order. IDs 01–08 refer to that order, not to new candidates. The [machine index](evidence-index.json) preserves exact task IDs, candidate IDs, Golden record IDs and original SQL SHA256 values, bound to each pinned candidate verification and FINAL-RESULT row.

The intended use is **local/internal early review** of task readability, business semantics, provenance, counterexample usefulness and replay operation. All records are exposed development material with persistent **TRAIN** role. They are unsuitable as unseen evaluation items. No reviewer utility, fine-tuning improvement, generalization, commercial readiness or company acceptance score has been measured.

## Composition

| ID | Contract/version | Business semantics illustrated |
|---|---|---|
| 01 | `sql.aggregation.fulfillment_sla_dashboard` v1 | Eligible delivered fulfillment counts and on-time counts by warehouse |
| 02 | `sql.dedup.education_grade_revisions` v2 | Latest valid grade revision per student/course |
| 03 | `sql.windows.media_previous_play` v1 | Previous completed play within viewer/title and requested year |
| 04 | `sql.dedup.lowest_quote` v1 | Lowest non-null quote with supplier tie-breaking |
| 05 | `sql.joins.requested_language_titles` v1 | Requested-language left join with duplicate multiplicity |
| 06 | `sql.subqueries.pareto_shipping` v1 | Per-lane nondominated shipping choices |
| 07 | `sql.retention.renewal_coverage` v1 | Same-member confirmed renewal covering the timestamp threshold |
| 08 | `sql.windows.queue_batches` v1 | Three ordered queue batches, including null timestamps |

These are selected survivors from a retained development process, not a representative random sample of SQL work. The small count and contract selection do not support a general benchmark score. Business semantics and wrong-answer examples are anchored to existing named profiles and their qualification receipts in [the evidence mapping](evidence-index.md).

## Provenance and verification

The original delivered candidate SQL was retained; profile-authored reference or alternative SQL did not replace it. V37 reports original task/request/response binding validation, admission, export and relocated replay for all eight. This layer intentionally references sanitized IDs and hashes rather than reproducing raw requests, responses, credentials or private endpoints.

Candidate-specific evidence is fresh native V37 rejudge for 01–03 and retained exact-candidate same-source final-suite proof for 04–08. All eight have PASS/STRONG verification, complete actual-candidate mutation coverage and one passing pipeline-category `INDEPENDENT_ADVERSARIAL` case. The independently named category is differential runtime verification, not proof of independent authorship. Qualification challenges and mutation operators are authored controls; their wrong queries are not reported as model failures.

Each selected profile challenge retains executable SQL, fixture tables, expected output, candidate object, execution, comparison and a `KILLED_WRONG_ANSWER` outcome. A selected correct alternative has `MATCH`; this demonstrates a recorded match on that witness, not universal SQL equivalence. Candidate mutation entries separately retain the actual original SQL, transformed SQL, tables, expected output and both successful executions with a semantic kill. For 04–08, the original final-suite artifacts also bind the candidate identity and record separate authored `WRONG_SQL` failures.

## Distribution and dependencies

This directory is a thin navigation/evidence layer. Worker A owns the original public/base fixture presentation, and Worker B owns the replay entry points. Replay A is illustrative and does not certify Replay B. Authoritative B still requires the 602,194,502-byte immutable package (123,854 total files; 123,765 declared), exact anchors and supplied-quality context, trust checks and bundled validation in a fresh writable workclone. A historical replay inspection cannot substitute for a new validation claim.

The coordinator's [fresh-location integration](../audit/integration-result.json) now reports PASS for eight A and eight B records without original-checkout imports; the local dependency package remains required. The [new native bundled report](../audit/native-bundled-validation-result.json) is VALID with zero errors/warnings and exact pinned supplied context, and [all eight per-record statuses](../audit/native-per-record-results.json) are PASS. This preview result is separate from the retained V37 baseline and does not establish a zero-skip full-suite certificate. The [separate internal AI review](../audit/INTERNAL-REVIEW.md) is PASS with prior authorship/access disclosed; its pending-integration language describes its earlier snapshot. It is not human or blind review.

No license grant, external distribution permission or downstream-use approval is inferred from having the local files or passing integration. External sharing remains BLOCKED; approval must cover outputs, attribution, exact preview scope and reviewer destination. Read [limitations](limitations.md) and [sharing readiness](sharing-readiness.md) together with this card. Historical baseline and separate preview-integration SHA256 pins are in [evidence-index.json](evidence-index.json).
