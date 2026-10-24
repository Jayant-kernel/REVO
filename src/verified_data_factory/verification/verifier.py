"""Verification pipeline (Phase 4).

Explicit stage order with documented early exits::

    validate inputs
    -> gate on the provided ExecutionResult (candidate faults FAIL here)
    -> resolve + compute the independent oracle (faults -> INCONCLUSIVE)
    -> compare oracle vs observed rows (mismatch -> FAIL, stop)
    -> hidden fixtures (any fail -> FAIL; any infra gap -> INCONCLUSIVE)
    -> properties (any fail -> FAIL)
    -> metamorphic relations (any fail -> FAIL)
    -> mutation campaign (weak suite -> INCONCLUSIVE, never FAIL)
    -> performance evidence (never a verdict)
    -> verdict + VerificationResult

Backend infrastructure faults propagate as INCONCLUSIVE anywhere they
surface — never candidate blame. Inputs are never mutated.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import time
from typing import Any

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.sandbox.models import ExecutionResult
from verified_data_factory.task_engine.models import TaskInstance

from . import comparator as compare_mod
from .backend import DerivedTaskBackend, ExecutionBackend
from .errors import BackendError, OracleUnknownError
from .hidden import derive_hidden_seed, run_hidden_checks
from .metamorphic import MetamorphicContext, run_metamorphic_checks
from .models import (
    COMPARISON_VERSION,
    HiddenTestResult,
    MetamorphicResult,
    MutationResult,
    OracleOutcome,
    PropertyResult,
    Strength,
    VerificationConfig,
    VerificationFailureCode,
    VerificationResult,
)
from .mutations import MutationContext, run_mutation_checks
from .oracle_registry import get_oracle
from .performance import collect_performance
from .properties import PropertyContext, run_property_checks

logger = logging.getLogger(__name__)

_CANDIDATE_FAULT_STATUSES = frozenset(
    {"TIMEOUT", "RESOURCE_LIMIT", "EXECUTION_ERROR", "POLICY_REJECTED"}
)


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def build_verification_id(
    task_id: str,
    candidate_id: str,
    execution_id: str | None,
    config_version: str,
    oracle_version: int,
) -> str:
    """Deterministic id over logical inputs (timings excluded)."""
    digest = hashlib.sha256(
        f"{task_id}|{candidate_id}|{execution_id or ''}|{config_version}|{oracle_version}|{COMPARISON_VERSION}".encode()
    ).hexdigest()[:12]
    return f"{candidate_id}.verify-{digest}"


def compute_oracle(task: TaskInstance) -> OracleOutcome:
    """Resolve the registered oracle and compute the expected result."""
    try:
        entry = get_oracle(task.template_id, task.template_version)
    except OracleUnknownError as exc:
        return OracleOutcome(ok=False, error=str(exc))
    started = time.monotonic()
    try:
        expected = entry.fn(dict(task.requirements), task.tables)
    except Exception as exc:  # noqa: BLE001 — oracle faults are INCONCLUSIVE data
        return OracleOutcome(
            ok=False,
            strategy=entry.strategy,
            oracle_version=entry.oracle_version,
            runtime_ms=int((time.monotonic() - started) * 1000),
            error=f"{type(exc).__name__}: {exc}"[:500],
        )
    return OracleOutcome(
        ok=True,
        strategy=entry.strategy,
        oracle_version=entry.oracle_version,
        runtime_ms=int((time.monotonic() - started) * 1000),
        expected=expected,
    )


def _empty_result_shell(
    task: TaskInstance,
    candidate: CandidateSolution,
    execution: ExecutionResult,
    config: VerificationConfig,
    started_at: str,
    oracle_version: int,
) -> dict[str, Any]:
    return {
        "verification_id": build_verification_id(
            task.task_id,
            candidate.candidate_id,
            execution.execution_id,
            config.config_version,
            oracle_version,
        ),
        "task_id": task.task_id,
        "candidate_id": candidate.candidate_id,
        "execution_id": execution.execution_id,
        "verification_config_version": config.config_version,
        "oracle_version": oracle_version,
        "started_at": started_at,
        "evidence": {},
    }


def verify_candidate(
    task: TaskInstance,
    candidate: CandidateSolution,
    execution: ExecutionResult,
    config: VerificationConfig | None = None,
    backend: ExecutionBackend | None = None,
) -> VerificationResult:
    """Run the full verification pipeline for one candidate."""
    config = config or VerificationConfig()
    backend = backend or DerivedTaskBackend()
    started_at = _utc_now_iso()

    shell = _empty_result_shell(task, candidate, execution, config, started_at, 0)

    # Stage 0: input binding (caller error, not infrastructure).
    if (
        candidate.task_id != task.task_id
        or execution.task_id != task.task_id
        or execution.candidate_id != candidate.candidate_id
    ):
        return VerificationResult(
            **shell,
            verdict="FAIL",
            failure_code="INVALID_INPUT",
            summary="task/candidate/execution binding mismatch",
            finished_at=_utc_now_iso(),
        )

    # Stage 1: gate on the provided execution outcome.
    if execution.status in _CANDIDATE_FAULT_STATUSES:
        code: VerificationFailureCode = (
            "POLICY_REJECTED" if execution.status == "POLICY_REJECTED" else "EXECUTION_FAILED"
        )
        return VerificationResult(
            **shell,
            verdict="FAIL",
            failure_code=code,
            summary=f"candidate execution {execution.status}; no verification runs needed",
            performance=collect_performance(
                execution, config.performance_enabled, config.performance_warn_after_ms
            ),
            finished_at=_utc_now_iso(),
        )
    if execution.status != "SUCCEEDED" or execution.result_data is None:
        return VerificationResult(
            **shell,
            verdict="INCONCLUSIVE",
            failure_code="SANDBOX_INFRA_ERROR",
            summary=f"sandbox infrastructure outcome {execution.status}; candidate not blamed",
            finished_at=_utc_now_iso(),
        )
    if execution.result_data.truncated:
        return VerificationResult(
            **shell,
            verdict="INCONCLUSIVE",
            failure_code="TRUNCATED_RESULT",
            summary="truncated result cannot establish correctness",
            finished_at=_utc_now_iso(),
        )

    # Structure is an explicit contract obligation, not a semantic mutation kill.
    from .qualification.structural import structural_checks

    structural = structural_checks(task, candidate.candidate_sql or "")
    if structural is not None:
        shell["evidence"]["structural_requirements"] = structural
        if structural["status"] != "PASS":
            return VerificationResult(**shell,
                verdict="FAIL" if structural["status"] == "FAIL" else "INCONCLUSIVE",
                failure_code="STRUCTURAL_REQUIREMENT_FAILED" if structural["status"] == "FAIL" else "STRUCTURAL_CHECK_ERROR",
                summary=f"mandatory query structure not established: {structural['rule_id']}", finished_at=_utc_now_iso())

    # Stage 2: independent oracle.
    oracle = compute_oracle(task)
    shell["oracle_version"] = oracle.oracle_version
    shell["verification_id"] = build_verification_id(
        task.task_id,
        candidate.candidate_id,
        execution.execution_id,
        config.config_version,
        oracle.oracle_version,
    )
    if not oracle.ok or oracle.expected is None:
        oracle_code: VerificationFailureCode = (
            "ORACLE_UNKNOWN" if "no oracle registered" in (oracle.error or "") else "ORACLE_ERROR"
        )
        return VerificationResult(
            **shell,
            verdict="INCONCLUSIVE",
            failure_code=oracle_code,
            summary=f"oracle unavailable: {oracle.error}",
            oracle=oracle,
            finished_at=_utc_now_iso(),
        )

    # Stage 3: compare oracle vs observed (mismatch stops the pipeline).
    comparison = compare_mod.compare(
        oracle.expected,
        [c.name for c in execution.result_data.columns],
        execution.result_data.rows,
        config.comparison,
        column_types=[c.type for c in execution.result_data.columns],
    )
    performance = collect_performance(
        execution, config.performance_enabled, config.performance_warn_after_ms
    )
    if not comparison.match:
        return VerificationResult(
            **shell,
            verdict="FAIL",
            failure_code="RESULT_MISMATCH",
            summary=(
                f"result mismatch: expected {comparison.expected_rows} rows, "
                f"got {comparison.actual_rows}"
            ),
            oracle=oracle,
            comparison=comparison,
            performance=performance,
            finished_at=_utc_now_iso(),
        )

    # Stage 4: hidden fixtures.
    hidden_seeds = [
        derive_hidden_seed(task.seed, config.config_version, i) for i in range(config.hidden_cases)
    ]
    hidden: HiddenTestResult | None = None
    if config.hidden_cases:
        hidden = run_hidden_checks(
            task,
            candidate,
            get_oracle(task.template_id, task.template_version).fn,
            backend,
            hidden_seeds,
            config.comparison,
        )
        if hidden.failed:
            return VerificationResult(
                **shell,
                verdict="FAIL",
                failure_code="HIDDEN_MISMATCH",
                summary=f"hidden fixtures: {hidden.failed}/{hidden.total} failed (overfit?)",
                oracle=oracle,
                comparison=comparison,
                hidden=hidden,
                performance=performance,
                finished_at=_utc_now_iso(),
            )
        if hidden.inconclusive:
            return VerificationResult(
                **shell,
                verdict="INCONCLUSIVE",
                failure_code="WEAK_SUITE" if any(c.failure_code == "WEAK_SUITE" for c in hidden.cases) else "SANDBOX_INFRA_ERROR",
                summary=f"hidden fixtures: {hidden.inconclusive}/{hidden.total} inconclusive",
                oracle=oracle,
                comparison=comparison,
                hidden=hidden,
                performance=performance,
                finished_at=_utc_now_iso(),
            )
    else:
        hidden = HiddenTestResult(total=0, seeds=[])

    # Stage 5: properties.
    properties: PropertyResult | None = None
    if config.properties_enabled:
        try:
            properties = run_property_checks(
                PropertyContext(
                    task,
                    candidate,
                    task.tables,
                    get_oracle(task.template_id, task.template_version).fn,
                    backend,
                    config.comparison,
                    task.seed,
                )
            )
        except BackendError as exc:
            return VerificationResult(
                **shell,
                verdict="INCONCLUSIVE",
                failure_code="SANDBOX_INFRA_ERROR",
                summary=f"property backend fault: {exc}",
                oracle=oracle,
                comparison=comparison,
                hidden=hidden,
                performance=performance,
                finished_at=_utc_now_iso(),
            )
        if properties.failed:
            failed_ids = [
                o.property_id for o in properties.outcomes if o.applicable and not o.passed
            ]
            return VerificationResult(
                **shell,
                verdict="FAIL",
                failure_code="PROPERTY_FAILED",
                summary=f"properties failed: {failed_ids}",
                oracle=oracle,
                comparison=comparison,
                hidden=hidden,
                properties=properties,
                performance=performance,
                finished_at=_utc_now_iso(),
            )

    # Stage 6: metamorphic relations.
    metamorphic: MetamorphicResult | None = None
    if config.metamorphic_enabled:
        try:
            metamorphic = run_metamorphic_checks(
                MetamorphicContext(
                    task,
                    candidate,
                    task.tables,
                    [c.name for c in execution.result_data.columns],
                    execution.result_data.rows,
                    oracle.expected.order,
                    backend,
                    config.comparison,
                    task.seed,
                    candidate_types=[c.type for c in execution.result_data.columns],
                )
            )
        except BackendError as exc:
            return VerificationResult(
                **shell,
                verdict="INCONCLUSIVE",
                failure_code="SANDBOX_INFRA_ERROR",
                summary=f"metamorphic backend fault: {exc}",
                oracle=oracle,
                comparison=comparison,
                hidden=hidden,
                properties=properties,
                performance=performance,
                finished_at=_utc_now_iso(),
            )
        if metamorphic.failed:
            failed_ids = [
                o.relation_id for o in metamorphic.outcomes if o.applicable and not o.passed
            ]
            return VerificationResult(
                **shell,
                verdict="FAIL",
                failure_code="METAMORPHIC_FAILED",
                summary=f"relations failed: {failed_ids}",
                oracle=oracle,
                comparison=comparison,
                hidden=hidden,
                properties=properties,
                metamorphic=metamorphic,
                performance=performance,
                finished_at=_utc_now_iso(),
            )

    # Stage 7: mutation campaign (weak suite -> INCONCLUSIVE, never FAIL).
    mutation: MutationResult | None = None
    strength: Strength = "UNKNOWN"
    if config.mutation_enabled and candidate.candidate_sql:
        mutation = run_mutation_checks(
            MutationContext(
                task,
                candidate.candidate_sql,
                task.tables,
                oracle.expected,
                backend,
                config.comparison,
            ),
            config.max_mutations,
            config.mutation_min_score,
        )
        if mutation.mutation_score is None:
            strength = "UNKNOWN"
        elif (mutation.mutation_score >= config.mutation_min_score and mutation.semantic_kills >= 3
              and mutation.coverage_complete and mutation.invalid == mutation.inconclusive == 0):
            strength = "STRONG"
        elif mutation.mutation_score >= config.mutation_min_score:
            # A perfect ratio over a thin/unfinished campaign is not strong proof.
            strength = "UNKNOWN"
        else:
            strength = "WEAK"
            return VerificationResult(
                **shell,
                verdict="INCONCLUSIVE",
                failure_code="WEAK_SUITE",
                summary=(
                    f"candidate evidence passes but suite strength "
                    f"{mutation.mutation_score:.2f} < {config.mutation_min_score:.2f}"
                ),
                verification_strength=strength,
                oracle=oracle,
                comparison=comparison,
                hidden=hidden,
                properties=properties,
                metamorphic=metamorphic,
                mutation=mutation,
                performance=performance,
                finished_at=_utc_now_iso(),
            )
    elif config.mutation_enabled:
        mutation = MutationResult(applicable=0)

    shell["evidence"] = {
        "stages": {
            "comparison": "pass",
            "hidden": f"{hidden.passed}/{hidden.total}" if hidden else "disabled",
            "properties": f"{properties.passed}/{properties.applicable}"
            if properties
            else "disabled",
            "metamorphic": f"{metamorphic.passed}/{metamorphic.applicable}"
            if metamorphic
            else "disabled",
            "mutation": mutation.mutation_score
            if mutation and mutation.mutation_score is not None
            else "n/a",
        }
    }
    return VerificationResult(
        **shell,
        verdict="PASS",
        failure_code=None,
        summary="all mandatory verification requirements satisfied",
        verification_strength=strength,
        oracle=oracle,
        comparison=comparison,
        hidden=hidden,
        properties=properties,
        metamorphic=metamorphic,
        mutation=mutation,
        performance=performance,
        finished_at=_utc_now_iso(),
    )
