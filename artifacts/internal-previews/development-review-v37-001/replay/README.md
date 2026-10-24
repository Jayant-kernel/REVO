# Replay operator layer — DEVELOPMENT REVIEW PREVIEW

**A is illustrative. The coordinator's fresh full native B integration passed
for all eight records** ([integration result](../audit/integration-result.json)).
Human review remains PENDING, external sharing BLOCKED, and these eight
examples remain development/TRAIN. This layer makes no full80 or W14 claim.

## A: simplest local public/base-fixture replay

Run from the checkout root, using installed Python and DuckDB (no installation,
project imports, container or model access):

```powershell
python -B "scratch/company_evaluation/development-review-v37-001/replay/replay.py" illustrative --examples "scratch/company_evaluation/development-review-v37-001/examples"
```

The command reads the exact eight entries of `examples/index.json` in order,
creates their original tables in separate in-memory databases, executes each
original SQL, and reports actual/expected results plus independent comparison
flags for column names, declared output types, ordered typed rows, row count and
truncation. Exit 1 means a comparison failed; malformed input also fails. Optional
`--result <new-file.json>` retains the full report; its parent must already exist
and the file must not exist. Coordinator-retained results belong in `audit/`.

No row sorting, bag comparison, float tolerance, whitespace normalization, or
numeric coercion is applied. JSON `true`, `1`, and `1.0` differ. Decimal and temporal
values use the existing harness's string serialization, with exact DuckDB declared
types also compared. The row cap matches the retained harness default (10,000).
Some original queries have underspecified ordering: exact retained row-order
agreement here is an observation on this runtime, not a cross-version SQL ordering
guarantee. The process disables DuckDB external access and extension auto-loading;
it is an illustrative local reviewer, not the production sandbox.

`source_bindings` are provenance metadata for coordinator integration; A does not
traverse or authenticate those original checkout paths. This keeps A runnable
with just this reviewer layer, index, fixtures and installed DuckDB. A passing
result is **not** B, hidden/mutation qualification, new engineering acceptance or
proof that fixtures were independently authorized.

## B1: light identity / historical-evidence inspection

```powershell
python -B "scratch/company_evaluation/development-review-v37-001/replay/replay.py" check-inputs --package "artifacts/internal-deliveries/v37-original8-001/original8" --history "scratch/company_evaluation/record-delivery-v3/runtime/delivery37"
```

This verifies the four externally supplied pins, selected manifest-bound acceptance
and dependency files, the exact supplied context, and SHA256-bound historical
result, terminal and per-record event log. Omit `--history` for just package input
inspection. It does **not** hash all 123,765 declared assets or execute native
validation. The historical report is VALID / eight records / 123,765 files, with
worker exit 0 and elapsed 1513.375 seconds. This is reuse of delivery37 evidence,
explicitly **not a new native replay**. Pins are constants in `replay.py`, not
caller-overridable values read from the package.

## B2: full fresh native replay — coordinator lane only

**Worker B did not itself run B; the coordinator ran a fresh copy successfully.**
The retained [bundled report](../audit/native-bundled-validation-result.json) is
VALID for eight records and 123,765 files, with zero errors and warnings;
[all eight per-record results](../audit/native-per-record-results.json) are PASS.
The [native terminal](../audit/native-terminal.json) records exit 0, no timeout
and 1293.5 seconds elapsed (coordinator action elapsed: 1293.578 seconds).
Future full runs still require the coordinator's native lane. From checkout root,
the complete command is (replace both unique suffixes together for every attempt):

```powershell
python -B "scratch/company_evaluation/development-review-v37-001/replay/replay.py" validate --package "artifacts/internal-deliveries/v37-original8-001/original8" --work "C:\Users\jayan\AppData\Local\Temp\opencode\rb37-w-001" --output "C:\Users\jayan\AppData\Local\Temp\opencode\rb37-o-001" --timeout 7200
```

Both directories must be absent, disjoint, outside checkout/preview and package,
with existing parents. Never reuse a failed run identity. The wrapper creates
them exclusively, writes a unique `identity.json`, checks inputs, and copies the
complete release and origin packet into work. Only this writable clone is passed
to bundled validation. Source package files are read, never validated in place.
On Windows, extended-length IO supports retained deep paths.

The native child waits for GO before doing work. The supervisor assigns it to a
kill-on-close Windows Job, records PID, command, supervisor, timestamp and timeout
in `launch.json`, then sends GO. The native phase is bounded to 1..10,800 seconds
(default 7200); package copy preparation precedes that timeout. Timeout, error or
supervisor unwind terminates the owned child/descendants; it does not target
unrelated parallel workers. `stdout.log`, `stderr.log`, `terminal.json`, flushed
`worker-events.jsonl`, `faulthandler.log` and `per-record-results.json` retain
diagnostics; a hard crash may leave only partial events. Exit success also
requires all eight original `check_source` calls to be observed passing.

The child imports the **pinned** external trust driver and calls its `check`
function directly, not its writing CLI. That checks the pinned release manifest,
anchor, entire packet inventory, every declared release hash and safe paths.
Then it checks exact acceptance/context and eight-member packet equality and
imports the bundled `validate_release` with supplied qualities and justifications.
Instrumentation calls the original bundled `engineering.check_source` unchanged;
no replay, qualification, checksum, isolation or supplied-context check is skipped.
The bundled validator writes only into the clone. Its report is retained as
`bundled-validation-result.json`; a VALID/eight/error-free/warning-free report and worker exit
0 are required for a new B claim. Success does not
close the historical native incidents or original strict acceptance checklist.

The wrapper ships its own bounded worker and Job helper: no dependency on the
old recovery worker or original source checkout. For relocation, copy all four
Python files in this directory together, run with absolute `--package`, `--work`
and `--output` paths from any fresh location. The full immutable package remains
required. The tested fresh copy was
`C:\Users\jayan\AppData\Local\Temp\opencode\review-preview37-copy-001`, with
separate `preview37-work-001` and `preview37-result-001` directories under the
same temp parent. It required the local immutable V37 package, installed pinned
runtimes and the existing Docker sandbox/image, with no original-checkout imports
and no auto-download authorization
([tested dependency record](../audit/integration-result.json)). Dependencies must
already be installed; see `DEPENDENCIES.md`.

## Focused checks and current proof

```powershell
python -B "scratch/company_evaluation/development-review-v37-001/replay/test_replay.py"
```

Tests use short unique directories beneath the pre-existing approved temp parent,
local miniature unit fixtures, and installed DuckDB. They cover execution with
NULL/decimal values, names/types/order/typed value tampering, count/truncation,
multi-statement refusal, hash tampering, existing/overlapping identity rejection,
exclusive result creation, fresh-location eight-fixture CLI and pinned B1 entry,
and an owned lightweight Windows Job child. No full native replay is launched.

Worker B also ran A over all eight actual A fixtures with every comparison true,
and B1 against the real package and pinned historical evidence. The coordinator's
[fresh-copy integration](../audit/integration-result.json) subsequently passed
both A and full B2 for eight records, and the
[focused-check terminal](../audit/focused-terminal.json) records exit 0 with no
timeout. Worker B inspected these retained results rather than rerunning B.
The relative `../audit/` links resolve in the source preview; the coordinator's
delivery includes the selected audit evidence. No integration blocker remains.

## Preview change record

- Added standalone illustrative replay, pinned native entry, focused tests and
  dependency census for this early development-review preview.
