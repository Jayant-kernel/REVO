"""Candidate-execution backends (Phase 4).

Candidate SQL reaches a database ONLY through these backends. Production
uses Phase 3's disposable containers; tests use scripted fakes that return
data without executing anything. The verifier never executes SQL itself.
"""

from __future__ import annotations

import abc
from typing import Any

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.sandbox import SandboxConfig, SandboxExecutor
from verified_data_factory.sandbox.models import ExecutionResult
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.models import TaskInstance

from .errors import BackendError


class ExecutionBackend(abc.ABC):
    """Run candidate SQL on fixture rows; return the Phase 3 result."""

    @abc.abstractmethod
    def run(
        self,
        task: TaskInstance,
        candidate: CandidateSolution,
        tables: dict[str, list[dict[str, Any]]] | None,
        label: str,
    ) -> ExecutionResult:
        """Execute on ``tables`` (None = the task's own fixture)."""


class SandboxBackend(ExecutionBackend):
    """Production backend: Phase 3 disposable-container execution."""

    def __init__(self, sandbox_config: SandboxConfig | None = None) -> None:
        self._config = sandbox_config or SandboxConfig()
        self._executor = SandboxExecutor(self._config)

    @property
    def sandbox_config(self) -> SandboxConfig:
        return self._config

    def run(
        self,
        task: TaskInstance,
        candidate: CandidateSolution,
        tables: dict[str, list[dict[str, Any]]] | None,
        label: str,
    ) -> ExecutionResult:
        try:
            if tables is None:
                return self._executor.execute(task, candidate)
            return self._executor.execute_on_rows(task, candidate, tables)
        except Exception as exc:
            raise BackendError(f"sandbox backend failed on {label}: {exc}") from exc


class DerivedTaskBackend(SandboxBackend):
    """Hidden-fixture backend: regenerates rows from derived seeds.

    Hidden cases are expressed as ordinary task fixtures (same template,
    version, and config; new seed), so hidden execution stays entirely on
    public Phase 1 + Phase 3 APIs.
    """

    def hidden_tables(
        self, task: TaskInstance, hidden_seed: int
    ) -> dict[str, list[dict[str, Any]]]:
        registry = load_builtin_registry()
        template = registry.get(task.template_id, task.template_version)
        hidden_task = generate_task(template, hidden_seed, dict(task.generation_metadata.config))
        return hidden_task.tables

    def independent_adversarial_tables(
        self, task: TaskInstance
    ) -> dict[str, list[dict[str, Any]]] | None:
        from .adversarial import independent_adversarial_tables

        return independent_adversarial_tables(task)
