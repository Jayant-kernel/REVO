# Reproducibility

Status: **implemented** (Phase 6). Layered assessment with honest
statuses — never a lone boolean, never a false VERIFIED.

## Levels (evaluated independently)

| Layer | VERIFIED means |
|---|---|
| `LOGICAL_TASK` | template/version/seed/config/engine-version present (Phase 1 contract replays it) |
| `CANDIDATE_TRACEABLE` | response artifact retrievable by hash (plus deterministic-replay flag when the stack guarantees it) |
| `EXECUTION_REPRODUCIBLE` | image digest + policy + fixture + runtime versions pinned |
| `VERIFICATION_REPRODUCIBLE` | oracle version + stage configs pinned (deterministic Python oracles) |
| `QUALITY_REPRODUCIBLE` | quality inputs + config + deterministic rules pinned |
| `DATASET_REPRODUCIBLE` | snapshot id recomputes from members |
| `END_TO_END_REPRODUCIBLE` | worst of the above |

## Statuses

- `VERIFIED` — all required identities pinned and validated.
- `CONDITIONAL` — logically reproducible, but an environment or model
  dependency is not fully pinned (e.g. origin reconstructable, model
  regeneration unguaranteed; image pinned, host/daemon unpinned).
- `NOT_VERIFIED` — checked and insufficient (e.g. image digest missing).
- `NON_REPLAYABLE` — origin itself unrecoverable (e.g. response artifact
  missing with no deterministic replay).
- `UNKNOWN` — insufficient evidence to judge.

Overall status is the worst layer status, with per-layer reasons and a
`missing_evidence` list. Reports never output only pass/fail.

## Limitations (deliberate)

- Execution caps at CONDITIONAL without full environment pins, and the
  overall chain inherits that ceiling — by design, not by accident.
- Model generation is CONDITIONAL at best for nondeterministic stacks;
  the exact preserved response (by artifact hash) is the ground truth.
- The MVP compares manifests and evidence; it does not re-run the
  factory (see `replay_scope: "comparison"` in reproduction manifests).
  Full automated replay is a later-phase option.
- Bit-for-bit regeneration across machines is not claimed; logical
  reproducibility plus pinned identities is.
