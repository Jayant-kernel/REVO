# Frozen agency specification — Revo SQL verification campaign

Frozen: 2026-10-07

Verdict: **SPEC-FROZEN**

## Goal

Complete a seven-stage, foundation-first SQL verification campaign that makes
the current Revo engineering assessment as correct, fail-closed, reproducible,
and evidence-backed as the existing frozen rubric permits. Advance only when
executed evidence supports the preceding stage. Report shortfalls and blocked
business contracts honestly; do not tune thresholds or narrow denominators.

## Execution contract

- FULL agency pipeline: researcher, spec challenger, at most three bounded
  builders on disjoint paths, build challenger, and independent verifier.
- Internal Task-tool agency subagents are permitted and required.
- No Revo experiment/provider/Ollama/OpenAI generation calls from product code.
  Stubs and deterministic local execution are permitted where specified.
- No commit, push, publication, release, or model download.
- Preserve the dirty worktree and every unrelated or unknown change. Never
  reset, restore, clean, stash, rebase, switch branches, or overwrite work.
- Existing frozen files and historical artifacts are immutable. New campaign
  evidence and status artifacts are append-only with unique names.
- Use existing repository patterns and minimal diffs. Delete or replace an old
  path only where it is campaign-owned, not frozen/historical, and the frozen
  specification requires it.
- Ask the user only for genuinely missing business intent or authorization.
  Mark affected contracts blocked and continue safe work elsewhere.
- Per brief: at most three build attempts, three verification rounds, and 50
  tool calls per role. Apply one failure-cascade decision per failure.

## Frozen authorities

The lock is `scratch/funnel_experiment/engineering/phase0-lock.json`.
Everything named under its `measurement_sources` and `frozen_assets` is
immutable for this campaign:

- `docs/production/engineering-rubric.md`
- `configs/package_a/engineering-rubric.json`
- `scripts/engineering_score.py`
- `tests/test_engineering_score.py`
- `configs/production/premium_qualification_80.yaml`
- `configs/quality_premium_93.yaml`
- `docs/release-93-spec.md`
- `scratch/paused-run.baseline.sha256.txt`

All pre-existing files below `scratch/funnel_experiment/engineering/` and the
pre-existing `scratch/funnel_experiment/ENGINEERING-HANDOFF.md` are historical
artifacts and must not be modified or overwritten. Newly named artifacts from
this run may only be created once and subsequently treated as immutable.

## Seven ordered stages

### Stage 1 — Authoritative correctness

Deliver explicit, version-bound oracle output schemas, including empty results.
Candidate-provided types must never redefine expected types. Enforce exact
numeric, temporal, ordering, null, and bag semantics; unsupported types fail
closed. Version or re-adjudicate changed contracts and certify the result.

Acceptance:

1. Every changed oracle path returns an authoritative typed result for nonempty
   and empty output.
2. Candidate metadata cannot alter the oracle's expected schema or semantics.
3. Unsupported or ambiguous comparison types fail closed rather than coercing.
4. Relevant contract/oracle registry versions and evidence are consistent; any
   semantic change is versioned or explicitly re-adjudicated.
5. Focused and adversarial tests pass, lint/mypy pass for the changed surface,
   identity and 15-file guard pass, and an append-only Stage 1 certificate is
   produced. No later stage begins before independent Stage 1 VERIFY-PASS.

### Stage 2 — Qualification evidence

Derive required rules from public versioned contracts. Require at least three
valid semantic mutants and coverage of every applicable rule. Persist detailed
evidence, not summary labels. Quarantine is authoritative and fail-closed.
Enforce dependency closure and contract/category attribution. Add adversarial
tests for stale, incomplete, and misattributed evidence.

### Stage 3 — Retry and crash semantics

Only an exact FAIL with an eligible diagnostic may repair a candidate. Enforce
arm/model/version/slot in the runner. Persist durable evaluation start/finish;
interrupted evaluations consume budget. Prove kill/recovery boundaries,
same-SQL bounded evaluation retries, no silent regeneration, honest accounting,
and prompt provenance using stubs only.

### Stage 4 — Isolation and export

Define authoritative registry identity and concurrency semantics. Use
key/relationship-aware roles and rename tests. Export through staging followed
by atomic finalize with failure cleanup. Produce a content-bound standalone
acceptance receipt and relocatable replay. Verify JSONL and Parquet paths and
corruption handling.

### Stage 5 — Qualify every current contract family-by-family

For every current contract, build rule maps, ambiguity detection,
fixtures/wrong-query counterexamples, at least three correct formulations, at
least two discriminating relations, frozen coverage floors, and positive,
negative, boundary, and degenerate evidence. Implement generic gaps only where
specified; otherwise block or forward-version. Prioritize SQL semantic
distinctions. Quarantines remain in the denominator.

### Stage 6 — Research-backed forward dataset

Create a primary-source-informed gap matrix covering dirty values, cardinality,
skew, fanout, boundaries, and efficiency only after correctness and
reproducibility. Do not leak benchmark gold or claim unsupported dialects.
Create the permitted deterministic forward 80-row dataset only if all frozen
requirements can genuinely be met; otherwise report the exact shortfall.

### Stage 7 — Final measurement

Verify frozen hashes. Build evidence-backed metrics, then run the unchanged
scorer with unchanged denominators. Report all deductions and preserve
`learning_value: NOT MEASURED`. After the last source edit, run one final full
regression with source identities, then final smoke LAST. Produce a new HANDOFF.

## Per-stage proof contract

Every stage requires:

- focused tests for intended behavior;
- adversarial negative tests for fail-closed behavior;
- repository lint and strict mypy appropriate to the changed surface;
- append-only evidence and status artifacts;
- identity checks and the frozen 15-file guard;
- cold build challenge with no actionable findings;
- independent deterministic verification against this specification.

One final full regression is required after the last source edit. Earlier full
regressions are evidence snapshots, not substitutes. Stage 7 smoke runs last.

## Non-goals

- Commercial release approval, human adjudication, rights clearance, buyer
  approval, or claims about learning value.
- Calling real generation providers or downloading models.
- Editing scoring authorities, frozen assets, thresholds, historical receipts,
  or denominators.
- Treating test success, summary PASS labels, or two qualified profiles as
  evidence for unexecuted all-catalog criteria.
- Producing an 80-row release merely to satisfy a count.

## Required final output

Report per-stage PASS/PARTIAL/BLOCKED; files changed; exact checks and results;
qualification counts; engineering score and deductions only if valid;
regression and final smoke; remaining blockers; and the append-only handoff
path. Claims must not exceed executed evidence.
