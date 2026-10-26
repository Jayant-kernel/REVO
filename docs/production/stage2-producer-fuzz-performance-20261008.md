# Stage2 retained-fuzz performance correction — 2026-10-08

Status: **both supported full fuzz-category positives passed**. Whole-contract
Stage2 qualification remains incomplete. This is new evidence; the preliminary
handoff, its failed attempts and 1200-second timeout record remain unchanged.
No v9, journal/index, scorer, provider, installation, commit or Stage3+ work.
The frozen qualification thresholds were read, never changed.

## Measured diagnosis, before rerunning full proofs

`scripts/engineering_receipt_benchmark.py` executes ten genuine scrap fixtures,
three alternatives each, and three independent validation traversals. It does not
emit a qualification receipt, construct a reduced FuzzDetail or override rubric
thresholds. Timed wrappers count the actual materialization/hash call sites. The
benchmark runs outside the workspace in the approved temporary directory.

Command (before optimization, then the identical command with `before` replaced
by `after` following the source correction):

```powershell
python -m scripts.engineering_receipt_benchmark --cases 10 --temporary-parent "C:\Users\jayan\AppData\Local\Temp\opencode" --output "C:\Users\jayan\AppData\Local\Temp\opencode\stage2-benchmark-before-20261008.json"
```

Measured seconds, preserving the reported precision:

| Measurement | Before | After |
| --- | ---: | ---: |
| Writer | 1.7915050000010524 | 0.8553748000122141 |
| Validation traversal 1 | 4.505544000014197 | 0.6330661000101827 |
| Validation traversal 2 | 3.8267956000054255 | 0.6790076000033878 |
| Validation traversal 3 | 4.081231399992248 | 0.9631905000132974 |
| Writer materializations / seconds | 40 / 1.3214963999052998 | 20 / 0.6330677001387812 |
| Validator materializations / seconds | 210 / 5.9026572999719065 | 30 / 0.7114508000959177 |
| Fingerprint materializations / seconds | 190 / 4.548756400006823 | 30 / 0.7359610999701545 |
| Writer hashes / seconds | 130 / 0.010380399966379628 | 140 / 0.010818900162121281 |
| Validator hashes / seconds | 390 / 0.053714200417743996 | 600 / 0.04892489980557002 |

The measured root cause was repeated database materialization, not artifact
hashing: 440 materializations before, with 11.77 seconds in those call sites,
versus about 0.064 seconds hashing. The benchmark did not separately time startup
versus INSERT cost inside materialization, so it does not claim startup alone
accounts for that time. No Python processes were listed by the initial targeted
process check; no concurrency or storage failure was observed.

The comparable three-traversal total decreased from 14.21 to 3.13 seconds (about
4.54x). The real producer additionally eliminates its redundant second complete
validation pass; the benchmark deliberately retains all three traversals for
comparison. Raw JSON measurements remain at the two named temporary paths.

## Bounded correction and cache safety

- The existing fingerprint implementation was extracted into
  `materialized_fixture_fingerprint`; `fixture_fingerprint` delegates to it with
  unchanged semantics. A shared typed-cell reader serves writer and validator.
- The writer executes three alternatives against one materialized fixture
  connection via `sql_many`, not three separately staged databases. Each query
  really executes; no generated or retained execution is synthesized or skipped.
- `DetailValidator` holds at most one replay fixture connection within an explicit
  validation scope, evicting it before materializing another fixture. Cache keys
  bind the complete witness, complete current task, oracle/comparison identifiers
  and DuckDB version. Expected rows, fingerprint, origin/seed, comparison and outcome
  cannot change while retaining a cache hit.
- Every fixture/SQL/candidate/execution reference is rehashed before reuse.
  Verified execution cache hits require the full witness key, not an execution ID
  alone. Run counts remain unique successful execution IDs. Failed validation
  does not insert a successful execution into the cache.
- Returned typed tables are detached copies; caller edits cannot corrupt cached
  oracle inputs. Caches never cross validation scopes. Connections and interrupt
  timers are closed/joined on both success and exceptions.
- Each SQL statement must pass the existing policy and DuckDB's parsed SELECT
  classification. Queries run inside a rolled-back transaction with external
  access disabled, one thread, 128 MB and the existing time/row bounds. One query
  cannot persist table changes for another alternative.
- Producer receipt metrics already require a complete fresh category replay.
  That result is used directly; the second complete producer replay was removed.
  The independent `receipt()` consumer still creates a fresh validator and
  recomputes the retained category from scratch.

Regressions cover stale bytes at all four reference kinds, updated candidate and
execution references, altered expected rows/fingerprint/comparison/outcome,
task/oracle/comparison binding changes, detached table copies, one connection for
three distinct executions, unique counts on exact repeated witnesses and closed
connections/new scopes. Existing accounting/canonicalization adversarial tests
also pass.

## Unchanged full proofs

The 2400-second per-profile ceiling was selected only after the small measured
improvement, with ample headroom above extrapolated scrap runtime. Each test keeps
all 900 source-bound seed/index cases, three alternatives (2700 distinct genuine
executions), per-seed observed coverage thresholds, retained typed witnesses,
producer category validation and independent consumer validation.

Scrap command:

```powershell
python -m pytest "tests/test_stage2_receipt_producer.py::test_full_900_case_fuzz_has_2700_real_executions[scrap]" -q --basetemp "C:\Users\jayan\AppData\Local\Temp\opencode\stage2-full-scrap-20261008" --junitxml "C:\Users\jayan\AppData\Local\Temp\opencode\stage2-full-scrap-20261008.xml"
```

Output verbatim:

```text
.                                                                        [100%]
1 passed in 234.10s (0:03:54)
```

SaaS command:

```powershell
python -m pytest "tests/test_stage2_receipt_producer.py::test_full_900_case_fuzz_has_2700_real_executions[saas]" -q --basetemp "C:\Users\jayan\AppData\Local\Temp\opencode\stage2-full-saas-20261008" --junitxml "C:\Users\jayan\AppData\Local\Temp\opencode\stage2-full-saas-20261008.xml"
```

Output verbatim:

```text
.                                                                        [100%]
1 passed in 420.78s (0:07:00)
```

Both retained XML reports show one test, zero failures, zero errors and zero
skips. These top-level full-fuzz reports are test-run proof, not named-test-category
receipts with contract attribution properties. The isolated roots under the named
basetemp directories retain the full source closure, all detail artifacts and
their validated fuzz receipts. They are local test evidence, not production v9
authority or whole-contract qualification.

## Final focused verification

```powershell
python -m pytest tests/test_stage2_receipt_producer.py tests/test_stage2_receipt_validation.py -q -k "not full_900"
```

```text
........................................................................ [ 90%]
........                                                                 [100%]
80 passed, 2 deselected in 59.77s
```

The two deselected tests are the full proofs executed individually above, not
omitted or substituted by the benchmark.

```powershell
python -m ruff check scripts/engineering_receipt_artifacts.py scripts/engineering_receipt_benchmark.py src/verified_data_factory/task_engine/hidden_fixtures.py src/verified_data_factory/verification/receipt_validation.py tests/test_stage2_receipt_producer.py
```

```text
All checks passed!
```

```powershell
$env:MYPYPATH='src;.'; python -m mypy scripts/engineering_receipt_artifacts.py scripts/engineering_receipt_benchmark.py src/verified_data_factory/task_engine/hidden_fixtures.py src/verified_data_factory/verification/receipt_validation.py --explicit-package-bases --follow-imports=silent
```

```text
Success: no issues found in 4 source files
```

Strict settings come from the repository configuration; imports were silently
followed. Scoped `git diff --check` returned no output. The first intermediate
lint/type invocation found import ordering/`Self` annotation and duplicate namespace
mapping issues; those were corrected before the benchmark/full proofs. Its focused
tests already passed (80 passed, 2 deselected in 49.49s).

Files changed by this continuation: `scripts/engineering_receipt_artifacts.py`,
new `scripts/engineering_receipt_benchmark.py`,
`src/verified_data_factory/task_engine/hidden_fixtures.py`,
`src/verified_data_factory/verification/receipt_validation.py`,
`tests/test_stage2_receipt_producer.py`, and this new evidence document. Source was
unchanged between the two full proofs and final focused verification; only this
new evidence document was added afterward. Remaining granular rule/domain,
mutation, production-profile and runtime-authority work in the preliminary handoff
is not resolved by these fuzz-category positives.
