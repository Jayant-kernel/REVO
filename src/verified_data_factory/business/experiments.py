"""Experiment orchestration with pluggable execution adapters (§13–§14, §55).

Phase 8 does not train models and does not call proprietary APIs. An
experiment binds a content-addressed config to outcome artifacts
supplied by the owner (local harness, self-hosted server, or external
command). Two adapters ship: ``artifact`` (reads outcome files) and
``external`` (invokes a controlled command that must emit them).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Protocol, cast

from verified_data_factory.provenance import utc_now_iso

from .comparison import build_comparison
from .config import experiment_id_for
from .errors import BusinessConfigError, BusinessIOError
from .models import (
    FAILURE_MODE_VALUES,
    AdaptationMethod,
    ArmSpec,
    BenchmarkScores,
    ExperimentComparison,
    ExperimentConfig,
    ExperimentResult,
    FailureMode,
    HypothesisCriteria,
    ImprovementMetrics,
    PredictionOutcome,
    RunStatus,
)
from .scoring import outcomes_from_list, score_outcomes
from .stats import compare_paired


class OutcomeAdapter(Protocol):
    """Source of per-arm prediction outcomes for one experiment run."""

    def load_outcomes(self, locator: str, arm: str) -> list[PredictionOutcome]:
        """Return outcomes for ``arm`` (baseline/control/treatment)."""
        ...  # pragma: no cover


class ArtifactAdapter:
    """Load outcomes from JSONL/JSON files (reference adapter)."""

    def load_outcomes(self, locator: str, arm: str) -> list[PredictionOutcome]:
        path = Path(locator)
        if path.is_dir():
            path = path / f"{arm}.jsonl"
        try:
            text = path.read_text(encoding="utf-8-sig").strip()
        except OSError as exc:
            raise BusinessIOError(f"cannot read outcomes at {path}: {exc}") from exc
        if not text:
            raise BusinessConfigError(f"empty outcomes artifact at {path}")
        try:
            rows = (
                json.loads(text)
                if text.lstrip().startswith("[")
                else [json.loads(line) for line in text.splitlines() if line.strip()]
            )
        except ValueError as exc:
            raise BusinessConfigError(f"malformed outcomes at {path}: {exc}") from exc
        if isinstance(rows, dict):
            rows = rows.get("outcomes", [])
        return outcomes_from_list(rows)


class ExternalAdapter:
    """Invoke a controlled command that must produce an outcomes file.

    The command receives ``{outcomes_path}`` and ``{arm}`` interpolated
    into its argv; anything else (GPU orchestration, scheduling) lives
    outside this system.
    """

    def __init__(self, command: list[str], timeout_s: int = 600) -> None:
        if not command:
            raise BusinessConfigError("external adapter needs a command")
        self._command = list(command)
        self._timeout_s = timeout_s

    def load_outcomes(self, locator: str, arm: str) -> list[PredictionOutcome]:
        out_path = Path(locator) / f"{arm}.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        argv = [
            part.replace("{outcomes_path}", str(out_path)).replace("{arm}", arm)
            for part in self._command
        ]
        try:
            subprocess.run(argv, timeout=self._timeout_s, check=True)
        except subprocess.SubprocessError as exc:
            raise BusinessConfigError(f"external evaluation command failed: {exc}") from exc
        return ArtifactAdapter().load_outcomes(str(out_path), arm)


def create_experiment(
    *,
    benchmark_id: str,
    baseline: ArmSpec,
    treatment: ArmSpec,
    experiment_version: str,
    scoring_method: str,
    control: ArmSpec | None = None,
    evaluation_config: dict[str, Any] | None = None,
    seeds: list[int] | None = None,
    prompt_version: str = "",
    code_revision: str | None = None,
    environment: str | None = None,
) -> ExperimentConfig:
    """Create a content-addressed experiment contract (§23–§24)."""
    payload: dict[str, Any] = {
        "benchmark_id": benchmark_id,
        "baseline": baseline.model_dump(mode="json"),
        "treatment": treatment.model_dump(mode="json"),
        "evaluation_config": evaluation_config or {},
        "seeds": seeds or [],
        "scoring_method": scoring_method,
        "prompt_version": prompt_version,
        "experiment_version": experiment_version,
    }
    if control is not None:
        payload["control"] = control.model_dump(mode="json")
    return ExperimentConfig(
        experiment_id=experiment_id_for(payload),
        experiment_version=experiment_version,
        benchmark_id=benchmark_id,
        baseline=baseline,
        control=control,
        treatment=treatment,
        evaluation_config=evaluation_config or {},
        seeds=seeds or [],
        scoring_method=scoring_method,
        prompt_version=prompt_version,
        code_revision=code_revision,
        environment=environment,
    )


def verified_value_template(
    *,
    benchmark_id: str,
    verified_release_id: str,
    generic_baseline_id: str,
    model: str,
    experiment_version: str = "1.0",
    adaptation_method: AdaptationMethod = "SFT",
    seeds: list[int] | None = None,
) -> ExperimentConfig:
    """The canonical VERIFIED DATA VALUE template (§55).

    Baseline (no additional data) vs control (generic synthetic) vs
    treatment (Verified Data Factory release), scored on an unseen
    private benchmark with execution correctness primary.
    """
    return create_experiment(
        benchmark_id=benchmark_id,
        baseline=ArmSpec(model=model, adaptation_method="NONE"),
        control=ArmSpec(
            model=model,
            baseline_dataset_id=generic_baseline_id,
            adaptation_method=adaptation_method,
        ),
        treatment=ArmSpec(
            model=model,
            dataset_release_id=verified_release_id,
            adaptation_method=adaptation_method,
        ),
        experiment_version=experiment_version,
        scoring_method="external-harness-aggregation",
        evaluation_config={"primary_metric": "execution_accuracy"},
        seeds=seeds or [42],
    )


def run_experiment(
    *,
    config: ExperimentConfig,
    adapter: OutcomeAdapter,
    locator: str,
    run_id: str,
    status: RunStatus = "COMPLETED",
    failure_modes: list[str] | None = None,
    failure_notes: list[str] | None = None,
    criteria: HypothesisCriteria | None = None,
) -> ExperimentResult:
    """Bind a config to owner-supplied outcomes; failures stay visible (§57)."""
    baseline_outcomes = adapter.load_outcomes(locator, "baseline")
    treatment_outcomes = adapter.load_outcomes(locator, "treatment")
    baseline_scores = score_outcomes(baseline_outcomes)
    treatment_scores = score_outcomes(treatment_outcomes)
    control_scores: BenchmarkScores | None = None
    if config.control is not None:
        try:
            control_scores = score_outcomes(adapter.load_outcomes(locator, "control"))
        except BusinessConfigError:
            control_scores = None
    stats = compare_paired(baseline_outcomes, treatment_outcomes)
    comparison: ExperimentComparison = build_comparison(
        experiment_id=config.experiment_id,
        baseline=baseline_scores,
        treatment=treatment_scores,
        stats=stats,
        criteria=criteria,
    )
    modes: list[FailureMode] = []
    for mode in failure_modes or []:
        if mode not in FAILURE_MODE_VALUES:
            raise BusinessConfigError(f"unknown failure mode: {mode!r}")
        modes.append(cast("FailureMode", mode))
    return ExperimentResult(
        experiment_id=config.experiment_id,
        run_id=run_id,
        status=status,
        baseline_metrics=baseline_scores,
        treatment_metrics=treatment_scores,
        control_metrics=control_scores,
        deltas=[_comparison_row_to_improvement(row) for row in comparison.metrics],
        statistical_evidence=stats,
        family_table=list(comparison.families),
        edge_table=list(comparison.edge_cases),
        failure_modes=modes,
        failure_notes=list(failure_notes or []),
        reproducibility={
            "dataset_release": config.treatment.dataset_release_id,
            "benchmark_version": config.benchmark_id,
            "model_revision": config.treatment.model_revision,
            "prompt_version": config.prompt_version,
            "training_config": dict(config.treatment.training_config),
            "evaluation_config": dict(config.evaluation_config),
            "code_revision": config.code_revision,
            "environment": config.environment,
            "seeds": list(config.seeds),
        },
        created_at=utc_now_iso(),
    )


def _comparison_row_to_improvement(row: dict[str, Any]) -> ImprovementMetrics:
    return ImprovementMetrics(
        metric=str(row["metric"]),
        baseline=float(row["baseline"]),
        treatment=float(row["treatment"]),
        denominator_n=int(row["denominator_n"]),
        absolute_pp=float(row["absolute_pp"]),
        relative_pct=row.get("relative_pct"),
        error_reduction=row.get("error_reduction"),
    )
