# Phase A Classification: Phase 13 Authoritative Artifact

Artifact: `scratch/funnel-generation-experiment/phase13-authoritative/`

Classification: `SUPERSEDED_INFORMATIONAL`.

The artifact's append-only `calls.jsonl` contains 36 real-call records: six
`pinned-baseline`, twelve `pinned-feedback`, six `qwen-baseline`, and twelve
`qwen-feedback`. It remains retained unchanged for audit only. It is excluded
from Phase A execution, readiness, scoring, and all future Phase 13 decisions.

Reason: its treatment lock binds an earlier runner SHA-256, while the current
runner identity differs. Resuming or modifying that 36-call artifact would
change the locked Phase 13 protocol. Phase A makes no Phase 13 provider calls.

This is an additive classification record; it does not alter any file within
the classified artifact.
