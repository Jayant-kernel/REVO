# Security Model — Verified SQL Data Factory

Status: **Phase 3 — sandbox implemented per this model. See
`docs/phase-3-sandbox.md` for the as-built threat matrix (T1–T12).**

## Core stance

Treat generated code/queries as hostile. Every candidate is untrusted input
until it has executed safely inside isolation and been verified.

## Threats considered

- Malicious SQL / code (exfiltration attempts, filesystem access via extensions,
  resource exhaustion, fork bombs, crypto-mining-shaped workloads).
- Accidental damage (runaway cartesian joins, temp-file floods, disk exhaustion).
- Supply-chain risk (unpinned dependencies, tampered container images).
- Secret leakage (env vars, cloud credentials, host files mounted by mistake).

## Future execution environment requirements

- Network disabled (no egress; no Docker socket; no metadata-service access).
- No host filesystem access; no host credential access.
- Non-root execution (unprivileged user, no privilege escalation).
- Resource limits: memory, CPU, process/PID count, disk, execution timeout.
- Filesystem restrictions: read-only root where possible, small scratch tmp.
- Syscall restrictions (seccomp / equivalent allowlist thinking).
- Dependency allowlists: pinned, hashed, minimal.
- Ephemeral workers: fresh environment per run, full cleanup afterwards.
- Image integrity: pinned digests, verified provenance.

> Docker alone is not considered a complete security boundary.

Implemented in Phase 3 (not just planned): disposable containers with
`--network none`, read-only root + tmpfs, `--cap-drop ALL`,
`no-new-privileges`, non-root uid 10000, memory/CPU/PID limits, execution
timeout with kill, single-statement + statement-class policy gate, DuckDB
lockdown (`enable_external_access=false`,
`disabled_filesystems='LocalFileSystem'`, extensions off), file-based
harness I/O (no shell interpolation, no SQL in argv), no mounts, no socket,
no secrets, full cleanup on every path. Residual gaps (kernel zero-days,
digest pinning by default, custom seccomp) are listed in
`docs/phase-3-sandbox.md` §15.

## Phase 0 rules

- No code execution of generated artifacts.
- No secrets in the repo (see `.gitignore`).
- Security-relevant decisions recorded as ADRs.
