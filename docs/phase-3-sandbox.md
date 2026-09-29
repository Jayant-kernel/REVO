# Phase 3 — Secure Execution Sandbox

Status: **implemented** (plus one backward-compatible Phase 4 extension:
`SandboxExecutor.execute_on_rows`, same pipeline with caller-supplied rows
for hidden/property/metamorphic fixtures — see §9). Executes untrusted
candidate SQL against a recreated task fixture inside a disposable,
resource-bounded Linux container and returns an `ExecutionResult`
describing *what happened* — never whether the candidate is correct
(Phase 4).

## 1. Threat model

| ID | Threat | Mitigation |
|----|--------|-----------|
| T1 | Host filesystem access | No mounts, no `docker cp` (stdin/stdout only); read-only root + tmpfs; DuckDB `disabled_filesystems='LocalFileSystem'` |
| T2 | Network access | `--network none`; DuckDB external access disabled |
| T3 | Credential/secret access | No `-e` secrets (only `VDF_EXECUTION_ID`); no env inheritance; no host mounts |
| T4 | Docker socket access | Never mounted; probe-asserted absent |
| T5 | Resource exhaustion | `--memory`+swap cap, `--cpus`, `--pids-limit`, wall-clock timeout + kill, row/byte output caps |
| T6 | Persistent process survival | `docker kill` on timeout; `docker rm -f` on every path; leftover-container tests |
| T7 | Cross-job contamination | One candidate → one payload → one container; nothing shared writable |
| T8 | External database/file access | Filesystem lock; `ATTACH`/`COPY` policy-rejected; in-memory DB only |
| T9 | Extension abuse | `INSTALL`/`LOAD` policy-rejected AND DuckDB autoinstall/autoload off, unsigned off |
| T10 | Shell/command injection | No `shell=True`; candidate SQL travels via files, never argv |
| T11 | Excessive output | Row cap (+truncation flag), serialized-byte cap, stdout/stderr caps |
| T12 | Sandbox escape | Non-root (uid 10000, asserted), `--cap-drop ALL`, `no-new-privileges`, default seccomp |

**Outside the Phase 3 guarantee (explicit):** kernel/Docker zero-days;
side-channel exfiltration; bit-for-bit image reproducibility without a
pinned digest (digest is *recorded*, pinning is a deployment choice);
Windows/macOS Docker Desktop VM nuances (see §14). No "perfect isolation"
is claimed — Docker alone is not a complete boundary (see `docs/security.md`).

## 2. Architecture

```text
(TaskInstance, CandidateSolution)   # inputs never mutated
        │ binding check (task_id) + policy gate (no container on reject)
        ▼
fixture.py → task_engine.api.recreate_fixture  # canonical fixture untouched
        │ serialize package → stdin bytes (no staging dirs, no mounts)
        ▼
docker.py DockerRunner  →  docker run -i (isolation flags, stdin payload)
        │  stdout = result JSON, stderr = status line
        ▼  timeout → kill → rm -f (always)
harness/run.py --stdin (in-container, stdlib+DuckDB): lockdown SETs → build DB
        → execute ONE statement → bounded fetch → result JSON on stdout
        ▼
executor.py → ExecutionResult (terminal status + taxonomy + provenance)
```

`DockerRunner` ⇄ `SandboxExecutor` separation lets unit tests fake Docker.
Harness speaks stdin/stdout in production (`--stdin`); file mode remains
for dev/probe convenience. Rationale recorded: `docker cp` is rejected by
the daemon for read-only-rootfs containers, so delivery is stdin-only by
construction (proven during integration).

## 3. Docker isolation

`--network none`, `--read-only`, `--cap-drop ALL`,
`--security-opt no-new-privileges`, `--user 10000:10000`, `--workdir /work`,
`--tmpfs /tmp + /work/tmp` (64m), `--memory/--memory-swap`, `--cpus`,
`--pids-limit`, `--stop-timeout 5`, single `-e VDF_EXECUTION_ID`. No `-v`,
`--volume`, `--mount`, no socket, no source tree, no host env. Default
Docker seccomp profile applies (no custom profile invented).

## 4. Network policy

Runtime `network = none`, no allowlists. Build-time network (pip) is a
separate, documented phase. Sandbox stays useful with host internet on.

## 5. Filesystem policy

Read-only root + two tmpfs mounts; the payload enters on stdin and the
result leaves on stdout (no mounts, no copies, no host temp dirs at all).

## 6. Database policy (DuckDB 1.5.5, verified by probe)

Applied in order (order-sensitive): `enable_external_access=false`,
`disabled_filesystems='LocalFileSystem'`, `autoinstall_known_extensions=false`,
`autoload_known_extensions=false`, `allow_unsigned_extensions=false`.
Verified blocked: `read_csv` on local paths, `INSTALL`, `LOAD`.
In-memory `ATTACH ':memory:'` still runs (harmless); file `ATTACH`/`COPY`
are additionally policy-rejected pre-execution.

## 7. Resource limits

`SandboxConfig` defaults: 10s timeout, 512MB, 1 CPU, 64 PIDs, 10k rows,
1MB result, 64KB stdout/stderr each. Exit 137 → `RESOURCE_LIMIT`; row
overflow → `SUCCEEDED(truncated)` or `RESULT_LIMIT` on bytes; timeout →
kill + `TIMEOUT`.

## 8. SQL policy

Tokenizing classifier (strings/comments stripped): single `SELECT`/`WITH`
only by default; `MULTIPLE_STATEMENTS`, `DISALLOWED_STATEMENT`
(INSERT/UPDATE/DELETE/DDL/ATTACH/COPY/INSTALL/LOAD/PRAGMA/...),
`NON_QUERY_STATEMENT`, `EMPTY_STATEMENT`. Defense in depth, not the boundary.

## 9. Fixture handling

Rebuilt from `(template_id, template_version, seed, config)` via the frozen
Phase 1 API; serialized to a stdin envelope (`fixture`/`sql`/`run`);
canonical fixture never written to; nothing staged on the host. Hidden and
transformed fixtures for Phase 4 travel the same path via
`execute_on_rows`.

## 10. Result model

`ExecutionResult{execution_id, task_id, candidate_id, status, failure?,
result_data?, stdout/stderr(+truncated), exit_code?, duration_ms,
resource_limits, resource_usage, sandbox_image(+digest), sandbox_config_version,
duckdb_version, started/finished_at}`. No correctness fields (test-asserted).

## 11. Error taxonomy

`INVALID_INPUT`, `POLICY_REJECTED`, `SANDBOX_START_FAILED`, `TIMEOUT`,
`RESOURCE_LIMIT`, `EXECUTION_ERROR`, `RESULT_LIMIT`, `SANDBOX_CLEANUP_ERROR`,
`INTERNAL_ERROR` — never collapsed to one `FAILED`.

## 12. Cleanup guarantees

`rm -f` in `finally` on all paths (the only host-side artifact is the
container itself — no staging dirs exist anymore); timeout path kills
first; cleanup failure after success conservatively demotes to
`SANDBOX_ERROR/SANDBOX_CLEANUP_ERROR`; leftover-container tests in
integration; `FakeDockerRunner` asserts kill/remove in unit tests.

## 13. Testing strategy

Unit (`tests/test_sandbox_*`, FakeDockerRunner, no daemon): policy matrix,
command-flag boundary, executor state machine, taxonomy, cleanup, binding,
payload envelope, serialization. Integration (`tests/integration/sandbox`,
daemon-gated with explicit skips): legitimate/invalid SQL, policy rejects,
filesystem/network/extension/attach blocks, timeout+gone-container, row/byte
caps, cgroup memory enforcement, isolation repeatability, probe (uid 10000,
no socket/sentinel/secret, DuckDB locks). E2E (`tests/e2e`, real Docker):
10x3 verdict matrix, boundary semantics, overfit, binding.

## 14. Platform limitations

- Dev host here: Windows 11; containers are Linux (Docker Desktop VM).
  Isolation flags are Linux-kernel/Docker-Engine features and behave
  identically inside the container regardless of host OS.
- `--user`, caps, seccomp, tmpfs require a Linux Docker Engine (or
  Desktop's Linux VM) — not Windows-container mode.
- Integration tests need a running daemon; `docker_available()` gates them.
- Memory-inflected tests are conservative by design (bounded queries only).

## 15. Known limitations

- No image digest pinning by default (recorded, not enforced); no Sigstore.
- No custom seccomp profile (Docker default applies).
- Container stdout (the result channel) is collected whole then truncated
  host-side; the harness emits only the bounded result object, and the
  executor caps bytes before parsing, so this is bounded in practice.
- Peak container memory is not sampled (usage reports duration + bytes;
  OOM surfaces as exit 137).
- Single worker, sequential; no pool (by design — no long-lived containers).
