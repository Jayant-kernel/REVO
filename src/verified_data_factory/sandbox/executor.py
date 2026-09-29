"""Sandbox orchestration (Phase 3).

``SandboxExecutor.execute`` maps (TaskInstance, CandidateSolution) to an
``ExecutionResult`` describing only what happened — never correctness.
Inputs are never mutated. The payload travels on container stdin and the
result returns on stdout; no host directories are staged or mounted, so
every path converges on a single cleanup step: container removal.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
from typing import Any

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.task_engine.models import TaskInstance

from . import fixture as staging
from .config import SandboxConfig
from .docker import ContainerRunner, DockerRunner, fresh_container_name
from .errors import DockerError, RunnerTimeoutError
from .models import (
    TERMINAL_STATUSES,
    ExecutionResult,
    FailureInfo,
    ResourceUsage,
    ResultColumn,
    ResultData,
    RunResult,
)
from .policy import check_policy

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def build_execution_id(candidate_id: str, started_at: str) -> str:
    """Traceable id binding task + candidate + attempt time."""
    digest = hashlib.sha256(f"{candidate_id}|{started_at}".encode()).hexdigest()[:12]
    return f"{candidate_id}.exec-{digest}"


def _truncate(text: str, cap_bytes: int) -> tuple[str, bool]:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= cap_bytes:
        return text, False
    cut = raw[:cap_bytes].decode("utf-8", errors="ignore")
    return cut, True


class SandboxExecutor:
    """Disposable-container executor. No shared mutable state between runs."""

    def __init__(self, config: SandboxConfig, runner: ContainerRunner | None = None) -> None:
        self._config = config
        self._runner = runner or DockerRunner(config)

    @property
    def config(self) -> SandboxConfig:
        return self._config

    def execute(self, task: TaskInstance, candidate: CandidateSolution) -> ExecutionResult:
        started_at = _utc_now_iso()
        execution_id = build_execution_id(candidate.candidate_id, started_at)
        base_kwargs: dict[str, Any] = {
            "execution_id": execution_id,
            "task_id": task.task_id,
            "candidate_id": candidate.candidate_id,
            "resource_limits": self._config.resource_limits(),
            "sandbox_image": self._config.image,
            "sandbox_image_digest": self._runner.image_digest(),
            "sandbox_config_version": self._config.config_version,
            "started_at": started_at,
        }

        sql, early = self._precheck(task, candidate, base_kwargs, started_at)
        if early is not None:
            return early

        # 3. Fixture package (Phase 1 public API; canonical fixture untouched).
        try:
            package = staging.build_execution_package(task)
        except Exception as exc:  # noqa: BLE001 — any staging failure is INTERNAL_ERROR data
            return self._terminal(
                base_kwargs,
                started_at,
                "SANDBOX_ERROR",
                "INTERNAL_ERROR",
                f"fixture staging failed: {exc}",
            )
        return self._run_package(base_kwargs, started_at, package, sql)

    def execute_on_rows(
        self,
        task: TaskInstance,
        candidate: CandidateSolution,
        tables: dict[str, list[dict[str, Any]]],
    ) -> ExecutionResult:
        """Execute ``candidate`` on caller-supplied fixture rows.

        Backward-compatible Phase 4 extension: identical pipeline to
        :meth:`execute` (binding + policy gates, disposable container,
        cleanup), except the staged fixture rows are overridden. Used for
        hidden/property/metamorphic fixtures that no TaskInstance seed can
        express (shuffles, injected rows). The canonical task fixture is
        never modified.
        """
        started_at = _utc_now_iso()
        execution_id = build_execution_id(candidate.candidate_id, started_at)
        base_kwargs: dict[str, Any] = {
            "execution_id": execution_id,
            "task_id": task.task_id,
            "candidate_id": candidate.candidate_id,
            "resource_limits": self._config.resource_limits(),
            "sandbox_image": self._config.image,
            "sandbox_image_digest": self._runner.image_digest(),
            "sandbox_config_version": self._config.config_version,
            "started_at": started_at,
        }

        sql, early = self._precheck(task, candidate, base_kwargs, started_at)
        if early is not None:
            return early

        try:
            package = staging.build_execution_package(task)
            package = {**package, "tables": tables}
        except Exception as exc:  # noqa: BLE001 — any staging failure is INTERNAL_ERROR data
            return self._terminal(
                base_kwargs,
                started_at,
                "SANDBOX_ERROR",
                "INTERNAL_ERROR",
                f"fixture staging failed: {exc}",
            )
        return self._run_package(base_kwargs, started_at, package, sql)

    def _precheck(
        self,
        task: TaskInstance,
        candidate: CandidateSolution,
        base_kwargs: dict[str, Any],
        started_at: str,
    ) -> tuple[str, ExecutionResult | None]:
        """Binding + policy gates. Returns (sql, None) or (\"\", terminal)."""
        # 1. Candidate binding + input validation (no container yet).
        if candidate.task_id != task.task_id:
            return "", self._terminal(
                base_kwargs,
                started_at,
                "POLICY_REJECTED",
                "POLICY_REJECTED",
                "candidate.task_id does not match task.task_id",
            )
        sql = candidate.candidate_sql or ""
        if not sql.strip():
            return "", self._terminal(
                base_kwargs,
                started_at,
                "POLICY_REJECTED",
                "INVALID_INPUT",
                "candidate carries no SQL",
            )

        # 2. SQL policy gate (defense in depth; container+DB are the boundary).
        decision = check_policy(sql, self._config.single_statement_only)
        if not decision.allowed:
            return "", self._terminal(
                base_kwargs,
                started_at,
                "POLICY_REJECTED",
                "POLICY_REJECTED",
                f"SQL policy rejected candidate: {decision.reason}",
                detail={"policy_reason": decision.reason or "UNKNOWN"},
            )
        return sql, None

    def _run_package(
        self,
        base_kwargs: dict[str, Any],
        started_at: str,
        package: dict[str, Any],
        sql: str,
    ) -> ExecutionResult:
        """Disposable single-shot run with guaranteed removal.

        The payload (fixture + SQL + run config) travels on stdin; the
        result arrives on stdout. No host directories are staged or
        mounted — there is nothing to clean except the container itself.
        """
        execution_id: str = base_kwargs["execution_id"]
        name = fresh_container_name()
        cleanup_error: str | None = None
        try:
            payload = staging.build_execution_payload(package, sql, self._config.max_result_rows)
            try:
                outcome = self._runner.run_container(
                    name, execution_id, payload, self._config.timeout_seconds
                )
            except RunnerTimeoutError:
                return self._terminal(
                    base_kwargs,
                    started_at,
                    "TIMEOUT",
                    "TIMEOUT",
                    f"execution exceeded {self._config.timeout_seconds}s; container killed",
                    exit_code=None,
                )
            result = self._collect(base_kwargs, started_at, outcome)
        except DockerError as exc:
            result = self._terminal(
                base_kwargs,
                started_at,
                "SANDBOX_ERROR",
                "SANDBOX_START_FAILED",
                f"sandbox startup/lifecycle failed: {exc}",
            )
        except Exception as exc:
            logger.exception("sandbox internal error for %s", execution_id)
            result = self._terminal(
                base_kwargs,
                started_at,
                "SANDBOX_ERROR",
                "INTERNAL_ERROR",
                f"sandbox internal error: {type(exc).__name__}",
            )
        finally:
            try:
                self._runner.remove(name)
            except Exception as exc:  # noqa: BLE001 — removal is best-effort by contract
                cleanup_error = f"container removal failed: {exc}"

        if cleanup_error is not None and result.status == "SUCCEEDED":
            # Conservative: untrusted artifacts when cleanup itself broke.
            return self._terminal(
                base_kwargs,
                started_at,
                "SANDBOX_ERROR",
                "SANDBOX_CLEANUP_ERROR",
                cleanup_error,
                exit_code=result.exit_code,
            )
        return result

    def _collect(
        self,
        base_kwargs: dict[str, Any],
        started_at: str,
        outcome: RunResult,
    ) -> ExecutionResult:
        cfg = self._config
        exit_code = outcome.exit_code
        raw_out = outcome.stdout
        oversized_stdout = len(raw_out) > cfg.max_result_bytes + 65536
        stdout, stdout_cut = _truncate(
            raw_out.decode("utf-8", errors="replace"), cfg.max_stdout_bytes
        )
        stdout_cut = stdout_cut or oversized_stdout
        stderr, stderr_cut = _truncate(
            outcome.stderr.decode("utf-8", errors="replace"), cfg.max_stderr_bytes
        )

        if exit_code == 137:
            return self._terminal(
                base_kwargs,
                started_at,
                "RESOURCE_LIMIT",
                "RESOURCE_LIMIT",
                "container was OOM-killed (exit 137)",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                stdout_cut=stdout_cut,
                stderr_cut=stderr_cut,
            )
        if oversized_stdout:
            return self._terminal(
                base_kwargs,
                started_at,
                "RESULT_LIMIT",
                "RESULT_LIMIT",
                "harness result exceeded the serialized size cap",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                stdout_cut=stdout_cut,
                stderr_cut=stderr_cut,
            )
        try:
            payload = json.loads(raw_out.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return self._terminal(
                base_kwargs,
                started_at,
                "SANDBOX_ERROR",
                "INTERNAL_ERROR",
                f"unparseable harness result: {exc}",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                stdout_cut=stdout_cut,
                stderr_cut=stderr_cut,
            )
        if exit_code != 0:
            return self._terminal(
                base_kwargs,
                started_at,
                "SANDBOX_ERROR",
                "INTERNAL_ERROR",
                f"harness crashed (exit {exit_code})",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                stdout_cut=stdout_cut,
                stderr_cut=stderr_cut,
            )
        if not isinstance(payload, dict) or payload.get("status") == "error":
            message = ""
            if isinstance(payload, dict):
                err = payload.get("error") or {}
                message = str(err.get("message", "unknown SQL error"))[:500]
            return self._terminal(
                base_kwargs,
                started_at,
                "EXECUTION_ERROR",
                "EXECUTION_ERROR",
                f"candidate SQL failed in sandbox: {message}",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                stdout_cut=stdout_cut,
                stderr_cut=stderr_cut,
                duckdb_version=payload.get("duckdb_version") if isinstance(payload, dict) else None,
            )
        return self._success(
            base_kwargs,
            started_at,
            payload,
            exit_code,
            stdout,
            stderr,
            stdout_cut,
            stderr_cut,
        )

    def _success(
        self,
        base_kwargs: dict[str, Any],
        started_at: str,
        payload: dict[str, Any],
        exit_code: int,
        stdout: str,
        stderr: str,
        stdout_cut: bool,
        stderr_cut: bool,
    ) -> ExecutionResult:
        cfg = self._config
        columns = [
            ResultColumn(name=str(c.get("name", "")), type=str(c.get("type", "")))
            for c in payload.get("columns", [])
            if isinstance(c, dict)
        ]
        rows = [r for r in payload.get("rows", []) if isinstance(r, list)]
        truncated = bool(payload.get("truncated", False))
        if len(rows) > cfg.max_result_rows:
            rows = rows[: cfg.max_result_rows]
            truncated = True
        blob = json.dumps({"columns": len(columns), "rows": rows}, default=str)
        if len(blob.encode("utf-8")) > cfg.max_result_bytes:
            finished = _utc_now_iso()
            return ExecutionResult(
                **base_kwargs,
                status="RESULT_LIMIT",
                failure=FailureInfo(
                    code="RESULT_LIMIT", message="result exceeded max_result_bytes"
                ),
                result_data=None,
                stdout=stdout,
                stderr=stderr,
                stdout_truncated=stdout_cut,
                stderr_truncated=stderr_cut,
                exit_code=exit_code,
                duration_ms=self._elapsed_ms(started_at, finished),
                resource_usage=ResourceUsage(
                    duration_ms=self._elapsed_ms(started_at, finished),
                    output_bytes=len(blob.encode("utf-8")),
                ),
                duckdb_version=payload.get("duckdb_version"),
                finished_at=finished,
            )
        finished = _utc_now_iso()
        data = ResultData(columns=columns, rows=rows, rows_returned=len(rows), truncated=truncated)
        return ExecutionResult(
            **base_kwargs,
            status="SUCCEEDED",
            failure=None,
            result_data=data,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_cut,
            stderr_truncated=stderr_cut,
            exit_code=exit_code,
            duration_ms=self._elapsed_ms(started_at, finished),
            resource_usage=ResourceUsage(
                duration_ms=self._elapsed_ms(started_at, finished),
                output_bytes=len(blob.encode("utf-8")),
            ),
            duckdb_version=payload.get("duckdb_version"),
            finished_at=finished,
        )

    def _terminal(
        self,
        base_kwargs: dict[str, Any],
        started_at: str,
        status: str,
        code: str,
        message: str,
        detail: dict[str, Any] | None = None,
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
        stdout_cut: bool = False,
        stderr_cut: bool = False,
        duckdb_version: str | None = None,
    ) -> ExecutionResult:
        assert status in TERMINAL_STATUSES, f"non-terminal result status: {status}"
        finished = _utc_now_iso()
        return ExecutionResult(
            **base_kwargs,
            status=status,
            failure=FailureInfo(code=code, message=message, detail=detail or {}),
            result_data=None,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_cut,
            stderr_truncated=stderr_cut,
            exit_code=exit_code,
            duration_ms=self._elapsed_ms(started_at, finished),
            resource_usage=ResourceUsage(duration_ms=self._elapsed_ms(started_at, finished)),
            duckdb_version=duckdb_version,
            finished_at=finished,
        )

    @staticmethod
    def _elapsed_ms(started_at: str, finished_at: str) -> int:
        try:
            start = _dt.datetime.fromisoformat(started_at)
            end = _dt.datetime.fromisoformat(finished_at)
            return max(0, int((end - start).total_seconds() * 1000))
        except ValueError:
            return 0


def execute_candidate(
    task: TaskInstance,
    candidate: CandidateSolution,
    config: SandboxConfig,
    runner: ContainerRunner | None = None,
) -> ExecutionResult:
    """One-shot helper over :class:`SandboxExecutor` (Phase 4 entry point)."""
    return SandboxExecutor(config, runner).execute(task, candidate)


__all__ = ["SandboxExecutor", "build_execution_id", "execute_candidate"]
