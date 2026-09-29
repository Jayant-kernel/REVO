"""Hidden-fixture testing (Phase 4).

Hidden cases regenerate the task fixture from derived seeds::

    hidden_seed = SHA256("{task_seed}:{config_version}:{index}")[:8] -> int

Seeds are deterministic, distinct from the original seed, and recorded in
the verification evidence (seeds, never fixture contents). Candidate SQL
runs on hidden rows exclusively through the execution backend (Phase 3 in
production); the solver prompt never sees them.
"""

from __future__ import annotations

import hashlib
from typing import Any

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.task_engine.models import TaskInstance

from . import comparator as compare_mod
from .backend import ExecutionBackend
from .errors import BackendError
from .models import (
    ComparisonPolicy,
    ExpectedResult,
    HiddenCaseOutcome,
    HiddenTestResult,
)


def derive_hidden_seed(task_seed: int, config_version: str, index: int) -> int:
    """Deterministic hidden seed; independent of dictionary ordering."""
    digest = hashlib.sha256(f"{task_seed}:{config_version}:{index}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def hidden_tables(
    task: TaskInstance, hidden_seed: int, backend: ExecutionBackend
) -> dict[str, list[dict[str, Any]]]:
    """Regenerate fixture rows for a hidden seed.

    Production backends rebuild rows through the Phase 1 public API;
    scripted backends serve canned rows. Either way the rows — never the
    candidate — flow into the oracle and the sandbox.
    """
    provider = getattr(backend, "hidden_tables", None)
    if not callable(provider):
        raise BackendError("backend cannot regenerate hidden fixtures")
    try:
        result = provider(task, hidden_seed)
    except BackendError:
        raise
    except Exception as exc:
        raise BackendError(f"hidden fixture regeneration failed: {exc}") from exc
    if not isinstance(result, dict):
        raise BackendError("hidden fixture regeneration returned non-mapping")
    return result


def run_hidden_checks(
    task: TaskInstance,
    candidate: CandidateSolution,
    expected_fn: Any,
    backend: ExecutionBackend,
    hidden_seeds: list[int],
    policy: ComparisonPolicy,
) -> HiddenTestResult:
    """Execute the candidate on each hidden fixture; compare with the oracle."""
    cases: list[HiddenCaseOutcome] = []
    passed = failed = inconclusive = 0
    for index, seed in enumerate(hidden_seeds):
        try:
            rows = hidden_tables(task, seed, backend)
        except BackendError as exc:
            cases.append(
                HiddenCaseOutcome(
                    index=index, seed=seed, status="INCONCLUSIVE", detail=str(exc)[:300]
                )
            )
            inconclusive += 1
            continue
        try:
            execution = backend.run(task, candidate, rows, f"hidden:{index}")
        except BackendError as exc:
            cases.append(
                HiddenCaseOutcome(
                    index=index, seed=seed, status="INCONCLUSIVE", detail=str(exc)[:300]
                )
            )
            inconclusive += 1
            continue
        if execution.status != "SUCCEEDED" or execution.result_data is None:
            if execution.status in (
                "TIMEOUT",
                "RESOURCE_LIMIT",
                "EXECUTION_ERROR",
                "POLICY_REJECTED",
            ):
                cases.append(
                    HiddenCaseOutcome(
                        index=index,
                        seed=seed,
                        status="FAIL",
                        failure_code="HIDDEN_MISMATCH",
                        detail=f"hidden execution {execution.status}",
                    )
                )
                failed += 1
            else:
                cases.append(
                    HiddenCaseOutcome(
                        index=index,
                        seed=seed,
                        status="INCONCLUSIVE",
                        detail=f"hidden execution {execution.status}",
                    )
                )
                inconclusive += 1
            continue
        try:
            expected: ExpectedResult = expected_fn(dict(task.requirements), rows)
        except Exception as exc:  # noqa: BLE001 — oracle faults are INCONCLUSIVE data
            cases.append(
                HiddenCaseOutcome(
                    index=index,
                    seed=seed,
                    status="INCONCLUSIVE",
                    detail=f"oracle error: {exc}"[:300],
                )
            )
            inconclusive += 1
            continue
        comparison = compare_mod.compare(
            expected,
            [c.name for c in execution.result_data.columns],
            execution.result_data.rows,
            policy,
        )
        if comparison.match:
            cases.append(HiddenCaseOutcome(index=index, seed=seed, status="PASS"))
            passed += 1
        else:
            cases.append(
                HiddenCaseOutcome(
                    index=index,
                    seed=seed,
                    status="FAIL",
                    failure_code="HIDDEN_MISMATCH",
                    detail=f"expected {comparison.expected_rows} rows, got {comparison.actual_rows}",
                )
            )
            failed += 1
    return HiddenTestResult(
        total=len(hidden_seeds),
        passed=passed,
        failed=failed,
        inconclusive=inconclusive,
        seeds=list(hidden_seeds),
        cases=cases,
    )
