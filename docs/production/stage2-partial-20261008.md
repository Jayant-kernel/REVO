# Stage 2 partial implementation — 2026-10-08

Status: **PARTIAL; not qualification-ready; no v9 receipts generated.**

Scope authority read: Stage 2 in
`scratch/funnel_experiment/engineering/SEVEN-STAGE-IMPLEMENTATION-PROMPT-r1.md`,
review S2-01 through S2-04 in `SEVEN-STAGE-REVIEW-r1.md`, and the external
`C:\Users\jayan\AppData\Local\Temp\opencode\EVIDENCE.md` researcher pack.
Stage 1 phase10r3 certification was supplied by the user, not rerun here.

## Implemented slice

`verification/behavior_authority.py` loads the exact builtin template/version,
retains each actual requirement value, the complete declared instruction template,
and each input column's declared type/nullability. Its version-1 declaration digest
includes contract/version and these declarations. Schema obligations are separate
from semantic obligations. The instruction is deliberately opaque: this slice does
not fabricate granular business intent from free-form text. Free-form requirements
remain semantic until an explicit public disposition is implemented; there is no
heuristic waiver for domain-sounding names.

Task requirements, schema, family, oracle specification and rendered instruction
must agree with the loaded public template. Unknown identity/version yields no
invented authority. Caller subsets cannot shrink the public obligations.

`run_mutation_checks()` now derives required rule IDs from that public authority,
not the selected operator names. The old generic operator-to-rule attribution was
removed. Kills, survivors, invalid/inconclusive counters and mutation scores retain
their prior behavior. Generic kills do not substantiate requirement-specific
discrimination: covered IDs remain empty and coverage incomplete. PASS stays PASS;
the simulated all-kills test now explicitly proves UNKNOWN rather than STRONG,
including >=3 semantic kills and score 1.0. This is not a waiver of the strength
gate. No runtime campaign currently proves all public obligations in this slice.

This declaration ledger is a conservative foundation, **not the finished granular
requirement-to-behavior authority or receipt schema**. It has no admission claims.

Files changed in this session (existing dirty changes were preserved):

- `src/verified_data_factory/verification/behavior_authority.py` (new)
- `src/verified_data_factory/verification/mutations.py` (import and coverage tail only)
- `tests/test_stage2_behavior_authority.py` (new)
- `tests/test_verify_mutations.py` (generic-kills strength test only)
- `tests/test_engineering_strength.py` (execution-alone attribution test only)
- `CHANGELOG.md` (one Unreleased entry)
- This partial artifact.

No commits, installations, provider calls, Stage 3+ edits, journal/index writes,
historical receipt changes or full regression were performed. Frozen scorer,
rubric, score test, known-edge assets and history were not edited.

## Focused evidence

Initial red command:

```powershell
python -m pytest tests/test_stage2_behavior_authority.py -q
```

Terminal failure before the new implementation:

```text
E   ModuleNotFoundError: No module named 'verified_data_factory.verification.behavior_authority'
=========================== short test summary info ===========================
ERROR tests/test_stage2_behavior_authority.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.36s
```

After implementation, focused runs exposed two old assertions that generic
execution proved STRONG/attributed rule IDs. Those assertions were replaced with
explicit public-coverage nonclaims, retaining their execution/score checks.

Final focused commands and terminal output:

```powershell
python -m pytest tests/test_stage2_behavior_authority.py tests/test_verify_mutations.py tests/test_engineering_mutation_details.py tests/test_engineering_strength.py -q
```

```text
.........................................                                [100%]
41 passed in 10.54s
```

```powershell
python -m ruff check src/verified_data_factory/verification/behavior_authority.py src/verified_data_factory/verification/mutations.py tests/test_stage2_behavior_authority.py tests/test_verify_mutations.py tests/test_engineering_strength.py
```

```text
All checks passed!
```

```powershell
python -m mypy src/verified_data_factory/verification/behavior_authority.py src/verified_data_factory/verification/mutations.py --follow-imports=silent
```

```text
Success: no issues found in 2 source files
```

Mypy proof is limited to the two source files; silently followed dependencies are
not a whole-project type-check claim. `git diff --check` reported only CRLF
conversion warnings, no whitespace errors. The tracked diff includes extensive
pre-existing work; do not treat it as this session's diff.

## Exact continuation / open findings

1. Cold-review this slice before expanding it. The public ledger needs explicit,
   source-bound granular instruction behaviors for SaaS v2 and scrap v1, including
   zero totals and one completion per entity. Bind domain dispositions explicitly
   (tie uniqueness/null handling), rather than guessing them. Add executed
   requirement-specific discriminator attribution before permitting any runtime
   rule coverage. Output neighbors must not replace missing business semantics.
2. Implement a new typed receipt schema and effective authority in `readiness.py`.
   It is **unchanged and still vulnerable to summary-only admission**. Reject
   historical schema explicitly as denied legacy while preserving historical
   files. Resolve quarantine and supersession from the authoritative manifest and
   materialized journal/index, rejecting absent/malformed authority. Caller None
   or ACTIVE must not erase effective state. Inspect/reuse pure readers in
   `scripts/package_a_evidence.py`; do not rewrite history.
3. Retain and validate all seven category details. Reuse fixture fingerprints,
   versioned oracle lookup, ExpectedResult/comparator and ExecutionResult. Validate
   exact SQL/task/candidate/execution/fixture identity and typed results; recompute
   oracle output, disagreements, actual executions and category counts. IDs alone
   are not execution evidence. Parse terminal named-test reports with exact node
   attribution; dereference the bound report. Retain relation preconditions,
   transforms and wrong-query discriminators, challenge witnesses and three
   correct alternatives, distinct fixtures and per-case/per-seed fuzz observations.
4. Update `engineering_rejudge.py`, relation helpers, rule audit and
   `engineering_qualification_receipts.py` together to retain those real records.
   Producer remains **unchanged**. Read thresholds from the frozen rubric, enumerate
   latest public templates, and compute exact category/contract execution counts.
   Close dependencies over executed tests, helpers, reference SQL, private Python
   corpus/JSON, relation JSON, fixtures, thresholds and loaded template inputs.
   Update count consumer to use the same authoritative admission path.
5. Replace invented contract `c` as the positive receipt baseline with a real
   public contract and isolated real-source fixture authority. Negative tests must
   reach their intended checks from a valid detailed baseline. Add adversarial
   red/green tests for summary forgery, erased quarantine, rule subsets, missing
   test reports, fake observation counts, execution IDs/consistency, invalid SQL,
   tampered fixtures, versions and consumed producer inputs. These receipt-level
   adversarial tests have **not** been implemented in this slice.
6. Only after validators/producers and source are stable, emit new v9 profiles for
   the two existing supported contracts, without claims for the unresolved 39+16.
   Append journal/index events if required by the admission authority; do not
   overwrite prior artifacts. Report actual fresh eligibility and unresolved
   semantics honestly. No fresh eligibility count is established by this artifact.
7. Run focused receipt/runtime checks, Ruff and scoped mypy, then independent cold
   review. Do not run full regression before cold review or edit Stage 3+.
