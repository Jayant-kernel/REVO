# Eight-record DEVELOPMENT REVIEW PREVIEW — frozen scope

This is an early-feedback milestone, not frozen full80 acceptance or completion
of W14. Human review is PENDING; external sharing is BLOCKED. All eight examples
remain exposed development/TRAIN. Generation remains stopped.

## Inputs and preservation

Source delivery: `artifacts/internal-deliveries/v37-original8-001/original8/`.
Evidence: `scratch/company_evaluation/record-delivery-v3/runtime/delivery37/`.
Use its exact eight membership records, original SQL, existing fixtures and
expected results. Reuse unchanged qualification/candidate/package replay evidence.
No core/source/old package edits, generation, installs, privileges or external calls.

## Ownership

- A: only `examples/` (eight Markdown pages, eight JSON fixtures, `index.json`).
- B: only `replay/` (entry points, instructions, focused tests, dependency census).
- C: only `review/` (overview, dataset card, limitations, feedback, evidence index,
  sharing-readiness checklist).
- Coordinator: root documents, integration, `audit/`, retained execution results,
  review assignment and final ship decision. No Git writes or external publication.
- Available worker later gets a separate review pass with disclosed prior access.
  Report writes go only to `audit/INTERNAL-REVIEW.md` when explicitly assigned.

All workers know others are active and must preserve their changes. No heavy
native/container/replay/qualification/full-suite operation without coordinator
lane assignment. Light local DuckDB runs and evidence reads may be parallel.

## Shared interface

`examples/index.json`: object with `examples` list, exactly eight entries;
each has `example_id`, `candidate_id`, `page` and `fixture` (filenames relative
to examples/). Use IDs `01` through `08`, in delivery37 FINAL-RESULT row order.

Every fixture JSON contains:
`example_id`, `candidate_id`, `task_id`, `schema` (original task schema objects),
`tables` (original generated public/base fixture tables), `sql` (original
candidate SQL), `expected` (original initial execution `result_data` with
columns/rows/rows_returned/truncated), `source_bindings` (relative source paths
and SHA256 digests), `fixture_scope` (retained public base fixture).
No newly authored reduced fixtures are needed. A writes UTF-8 JSON and pages.

Replay A: lightweight illustrative execution of those public/base fixtures;
depends on installed DuckDB and reviewer layer only. Compare column names,
declared output types, ordered rows and typed values. Does NOT imply B.

Replay B: thin fresh-work/output entry over the immutable V37 package and its
anchored supplied-quality context. Exact full trust checks and bundled validation
are mandatory for a new B claim. A verify-existing/check-inputs command may reuse
old replay evidence, but must label that as historical evidence inspection.
No slimming of the 123,765-file dependency tree without demonstrated closure.
Never execute a writing validator against the immutable package.

## Completion: eight equally counted preview tasks

P01 Baseline identities, workers, budget and original checklist verified/frozen.
P02 Eight readable pages and fixtures traceable to original tasks/SQL/results.
P03 Tested illustrative replay A plus meaningful focused tamper/failure checks.
P04 Usable thin authoritative B workflow, clearly documented dependency/claims;
    entry tested from fresh location, reuse of historical full replay labeled.
P05 Overview, dataset card, limitations and feedback form ready.
P06 Eight-example claim/evidence mapping and explicit sharing restrictions.
P07 Separate internal review, no unresolved correctness/integrity/replay blockers;
    bounded fixes and deferred minor issues recorded.
P08 Fresh-location integration proof, artifact hashes, files/bytes and handoff.

No requirement closes merely through more prose. Full original checklist remains
2/16=12.5% unless its actual acceptance conditions independently close. Original
suite 1980 passed/2 skipped/22 warnings; strict flag false; native incidents remain
unresolved. No full suite needed for this presentation/operator layer.
