"""Candidate-execution backends (Phase 4).

Candidate SQL reaches a database ONLY through these backends. Production
uses Phase 3's disposable containers; tests use scripted fakes that return
data without executing anything. The verifier never executes SQL itself.
"""

from __future__ import annotations

import abc
from importlib import import_module
from pathlib import Path
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
        from verified_data_factory.task_engine.hidden_fixtures import diverse_hidden_tables

        from .hidden import derive_hidden_seed
        from .models import VERIFICATION_CONFIG_VERSION

        variant = next((i + 1 for i in range(3) if derive_hidden_seed(task.seed, VERIFICATION_CONFIG_VERSION, i) == hidden_seed), 1 + hidden_seed % 3)
        return diverse_hidden_tables(hidden_task, hidden_seed, variant)

    def independent_adversarial_tables(
        self, task: TaskInstance
    ) -> dict[str, list[dict[str, Any]]] | None:
        from .adversarial import independent_adversarial_tables

        return independent_adversarial_tables(task)

    def requirement_counterexample_tables(
        self, task: TaskInstance,
    ) -> list[dict[str, list[dict[str, Any]]]]:
        """Execute clause fixtures for supported versions, including noncanonical SQL.

        These are shared-author development discriminators, not independently
        authored evaluation material or a substitute for derived-fixture diversity.
        """
        from verified_data_factory.task_engine.hidden_fixtures import fixture_fingerprint

        from .behavior_authority import SUPPORTED_GRANULAR, public_behavior_map
        from .public_rule_proofs import public_proofs

        if (task.template_id, task.template_version) not in SUPPORTED_GRANULAR:
            return []
        authority = public_behavior_map(task)
        if not authority.task_matches_public_contract:
            raise BackendError("task differs from source-bound counterexample contract")
        _, proofs = public_proofs(task)
        fixtures = {}
        for rule in authority.rules:
            if rule.kind == "semantic":
                tables = proofs[rule.proof_key]["witness"]
                fixtures[fixture_fingerprint(task, tables)] = tables
        # Additional required challenges can witness valid-domain behavior not
        # covered by a clause's first discriminator (e.g. negative scrap values).
        collector = import_module("scripts.engineering_qualification_receipts")
        _, challenges, _ = collector.profile(Path(__file__).resolve().parents[3], task.template_id, task.template_version)
        for _, tables in challenges:
            fixtures[fixture_fingerprint(task, tables)] = tables
        if not fixtures:
            raise BackendError("supported public counterexample fixtures missing")
        return list(fixtures.values())
