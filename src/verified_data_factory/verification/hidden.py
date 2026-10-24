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
from typing import Any, Literal

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.task_engine.hidden_fixtures import (
    HIDDEN_FIXTURE_VERSION,
    fixture_fingerprint,
)
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
    """Execute derived and available independent fixtures against the oracle."""
    cases: list[HiddenCaseOutcome] = []
    fingerprints = {fixture_fingerprint(task, task.tables)}
    minimum_distinct = min(4, len(hidden_seeds) + 1)
    passed = failed = inconclusive = 0
    adversarial_provider = getattr(backend, "independent_adversarial_tables", None)
    adversarial_rows: dict[str, list[dict[str, Any]]] | None = None
    adversarial_error: str | None = None
    if callable(adversarial_provider):
        try:
            adversarial_rows = adversarial_provider(task)
        except Exception as exc:  # noqa: BLE001 — a broken fixture is inconclusive evidence
            adversarial_error = f"independent adversarial fixture error: {exc}"[:300]
    base_total = len(hidden_seeds) + int(adversarial_rows is not None or adversarial_error is not None)
    counterexamples: list[dict[str, list[dict[str, Any]]]] = []
    counterexample_error: str | None = None
    counterexample_provider = getattr(backend, "requirement_counterexample_tables", None)
    if callable(counterexample_provider):
        try:
            counterexamples = counterexample_provider(task)
        except Exception as exc:  # noqa: BLE001 — missing clause fixtures cannot silently pass
            counterexample_error = f"requirement counterexample fixture error: {exc}"[:300]
    total = base_total + len(counterexamples) + int(counterexample_error is not None)
    for index in range(total):
        targeted = index >= base_total
        independent = index >= len(hidden_seeds)
        seed = hidden_seeds[index] if not independent else 0
        source: Literal["DERIVED", "INDEPENDENT_ADVERSARIAL", "REQUIREMENT_COUNTEREXAMPLE"] = (
            "REQUIREMENT_COUNTEREXAMPLE" if targeted else "INDEPENDENT_ADVERSARIAL" if independent else "DERIVED"
        )
        try:
            if targeted and counterexample_error:
                raise BackendError(counterexample_error)
            if independent and not targeted and adversarial_error:
                raise BackendError(adversarial_error)
            rows = (counterexamples[index-base_total] if targeted else adversarial_rows if independent
                    else hidden_tables(task, seed, backend))
            if rows is None:
                raise BackendError("independent adversarial fixture is missing")
            try:
                fingerprint = fixture_fingerprint(task, rows)
            except Exception as exc:
                raise BackendError(f"fixture content validation failed: {exc}") from exc
            if not independent:
                fingerprints.add(fingerprint)
        except BackendError as exc:
            cases.append(
                HiddenCaseOutcome(
                    index=index, seed=seed, source=source,
                    status="INCONCLUSIVE", detail=str(exc)[:300]
                )
            )
            inconclusive += 1
            continue
        try:
            label = (f"hidden:requirement:{index}" if targeted else f"hidden:adversarial:{index}" if independent
                     else f"hidden:{index}")
            execution = backend.run(task, candidate, rows, label)
        except BackendError as exc:
            cases.append(
                HiddenCaseOutcome(
                    index=index, seed=seed, source=source,
                    status="INCONCLUSIVE", detail=str(exc)[:300]
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
                        source=source,
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
                        source=source,
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
                    source=source,
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
            column_types=[c.type for c in execution.result_data.columns],
        )
        if comparison.match:
            cases.append(HiddenCaseOutcome(index=index, seed=seed, source=source, status="PASS", fixture_sha256=fingerprint))
            passed += 1
        else:
            cases.append(
                HiddenCaseOutcome(
                    index=index,
                    seed=seed,
                    source=source,
                    status="FAIL",
                    failure_code="HIDDEN_MISMATCH",
                    detail=f"expected {comparison.expected_rows} rows, got {comparison.actual_rows}",
                )
            )
            failed += 1
    if not failed and not inconclusive and len(fingerprints) < minimum_distinct:
        cases.append(HiddenCaseOutcome(index=total, seed=0, status="INCONCLUSIVE",
                                       failure_code="WEAK_SUITE", detail=f"only {len(fingerprints)}/{minimum_distinct} distinct derived fixtures"))
        total += 1
        inconclusive += 1
    return HiddenTestResult(
        total=total,
        distinct_fixtures=len(fingerprints),
        minimum_distinct_fixtures=minimum_distinct,
        fixture_version=HIDDEN_FIXTURE_VERSION,
        passed=passed,
        failed=failed,
        inconclusive=inconclusive,
        seeds=list(hidden_seeds),
        cases=cases,
    )
