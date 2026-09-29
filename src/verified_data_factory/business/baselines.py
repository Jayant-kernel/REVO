"""Baseline dataset references (Phase 8, §21–§22).

External datasets are recorded as source-backed metadata; their
contents are never copied. Treat external claims as what the source
says, not as verified facts.
"""

from __future__ import annotations

from .errors import BusinessConfigError
from .models import BaselineDataset, BaselineRun, BaselineSource, BenchmarkScores


def reference_baseline_dataset(
    *,
    baseline_dataset_id: str,
    baseline_dataset_source: str,
    source_type: BaselineSource = "NONE",
    baseline_dataset_version: str = "",
    license_identifier: str | None = None,
    observed_attributes: dict[str, object] | None = None,
) -> BaselineDataset:
    """Record a baseline dataset reference (metadata only)."""
    if source_type == "NONE" and baseline_dataset_id not in ("none", "no-additional-data"):
        raise BusinessConfigError(
            "source_type NONE is only valid for the no-additional-data baseline"
        )
    return BaselineDataset(
        baseline_dataset_id=baseline_dataset_id,
        baseline_dataset_version=baseline_dataset_version,
        baseline_dataset_source=baseline_dataset_source,
        source_type=source_type,
        license_identifier=license_identifier,
        observed_attributes=dict(observed_attributes or {}),
    )


def record_baseline_run(
    *,
    run_id: str,
    model: str,
    benchmark_id: str,
    result: BenchmarkScores,
    model_revision: str = "",
    provider: str = "",
    generation_config: dict[str, object] | None = None,
    dataset_context: str = "",
    baseline_dataset: BaselineDataset | None = None,
    prompt_version: str = "",
    evaluation_version: str = "1.0",
    timestamp: str = "",
) -> BaselineRun:
    """Record one baseline evaluation with its full context (§12)."""
    return BaselineRun(
        run_id=run_id,
        model=model,
        model_revision=model_revision,
        provider=provider,
        generation_config=dict(generation_config or {}),
        dataset_context=dataset_context,
        baseline_dataset=baseline_dataset,
        benchmark_id=benchmark_id,
        prompt_version=prompt_version,
        evaluation_version=evaluation_version,
        timestamp=timestamp,
        result=result,
    )
