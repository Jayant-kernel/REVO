"""Test-only scripted execution backend (Phase 4).

Returns canned ``ExecutionResult`` objects keyed by fixture label without
executing any SQL — the unit suite never needs Docker or DuckDB for
candidate execution. NEVER used in production paths.
"""

from __future__ import annotations

from typing import Any

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.sandbox.models import ExecutionResult
from verified_data_factory.task_engine.models import TaskInstance

from .backend import ExecutionBackend
from .errors import BackendError


class FakeBackend(ExecutionBackend):
    """Scripted backend: ``script`` maps labels (or indices) to results."""

    def __init__(
        self,
        results: dict[str, ExecutionResult] | None = None,
        default: ExecutionResult | None = None,
        raise_on: dict[str, Exception] | None = None,
        hidden_rows: dict[int, dict[str, list[dict[str, Any]]]] | None = None,
    ) -> None:
        self._results = dict(results or {})
        self._default = default
        self._raise_on = dict(raise_on or {})
        self._hidden_rows = dict(hidden_rows or {})
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        task: TaskInstance,
        candidate: CandidateSolution,
        tables: dict[str, list[dict[str, Any]]] | None,
        label: str,
    ) -> ExecutionResult:
        self.calls.append({"task_id": task.task_id, "label": label})
        if label in self._raise_on:
            raise self._raise_on[label]
        if label in self._results:
            return self._results[label]
        if self._default is not None:
            return self._default
        raise BackendError(f"fake backend has no result for label {label!r}")

    def hidden_tables(
        self, task: TaskInstance, hidden_seed: int
    ) -> dict[str, list[dict[str, Any]]]:
        """Serve canned hidden rows for scripted verification tests."""
        try:
            return self._hidden_rows[hidden_seed]
        except KeyError as exc:
            raise BackendError(f"fake backend has no hidden rows for seed {hidden_seed}") from exc
