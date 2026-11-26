# Agency decision ledger — 2026-10-07

This ledger is append-only for the current agency campaign attempt.

| ID | Decision | Basis | Consequence |
|---|---|---|---|
| D-001 | Select FULL tier. | User explicitly requires FULL and the campaign spans multiple stages/modules with independent verification. | All five agency roles and ordered gates are mandatory. |
| D-002 | Treat every pre-existing worktree change as preserved user/campaign work. | Worktree is extremely dirty and the user forbids reverting unknown changes. | No reset, restore, clean, stash, branch switch, or overwrite. |
| D-003 | Treat the Phase 0 lock, its four measurement sources, and four frozen assets as immutable. | `phase0-lock.json` is the named frozen authority; all eight hashes currently match. | No edits to these paths; future checks must fail closed on a mismatch. |
| D-004 | Do not reinterpret the 11-phase historical handoff as the missing seven-stage draft. | The user says the preceding seven-stage prompt is exact; that prompt is unavailable. | SPEC remains unfrozen and Stage 1 cannot receive a PASS. |
| D-005 | Do not simulate agency roles in one context or invoke model-backed CLI workers. | Agency requires isolated contexts; user prohibits real-model calls; no spawn tool is exposed. | Pipeline dispatch is blocked pending a permitted worker mechanism. |
| D-006 | Do not run scoring or claim a current regression during intake. | Stage boundaries and proof requirements are unavailable; historical handoff says scoring/final smoke were pending. | Preserve historical claims as historical only; current score remains uncomputed. |

Verdict: DECISIONS-RECORDED

## Append — runtime qualification v32, stopped checkpoint

Scope: runtime qualification only, not the earlier intake verdict or full v2
certification. Historical v31 success remains historical; no frozen package or
old receipt hash was rewritten. Current producer and 537 frozen source/input
files, runtime and generation budget are unchanged at the bounded post-stop audit.

`NEW v2/qualification-v32.py` froze the 18 historical authoritative records,
20 supported profiles and 62 latest IDs. It emitted three renewal-coverage@1
receipts: rules (51 covered; 33 semantic, 18 domain), named tests (one passed),
relations (two discriminating, eight checks). No fuzz batches, complete bundles,
public promotions, or new individually qualified bundles were produced. The
pre-collection quarantine API returned 52 latest quarantined IDs; the target
20 qualified / 42 latest quarantined / 62 IDs / 140 receipts was NOT achieved.
Historical unresolved46/nonlatest4 was not re-audited and is not a current claim.

The exclusive-create progress logger collided on Windows `time_ns()` filename
`progress-1792181176909490500.json` immediately before mutation collection.
This is a controller FileExistsError, not evidence of a semantic gate failure.
No retry or repair of the frozen producer was attempted after receipt emission.
Resume requires an authorized collision-safe controller/new frozen identity;
do not modify this producer or retrofit its source hashes.

Evidence: `scratch/funnel_experiment/engineering/qualified-receipts-v32/`
contains freeze.json, per-category checkpoints, retained raw SQL/wire artifacts,
failure-1792181176910491000.json and stopped-checkpoint-audit.json. Audit command:
`python "NEW v2/qualification-v32-audit.py"`. It checks frozen bytes/runtime/budget
and emitted-envelope metadata, not a repeated 18-bundle SQL census. All18
historical authoritative records remain unchanged. Budget28/400.483 unchanged,
zero new physical model calls and no unfinished attempts. No active Python
worker remained at the post-stop check. No core/scripts/tests/templates edits,
full regression, model calls, role writes, installs, network activity or commits.
Strict export remains deferred; no completion PASS or live20 claim is made.
