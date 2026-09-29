"""Result comparison with explicit denominators (§18, §26, §56).

Absolute improvement is treatment minus baseline in percentage points;
relative improvement always names the baseline denominator. There is no
single overall model-improvement score — the comparison is a table of
metrics, families, and edge cases plus a hypothesis verdict.
"""

from __future__ import annotations

from .models import (
    BenchmarkScores,
    EdgeDelta,
    ExperimentComparison,
    ExperimentResult,
    FamilyDelta,
    HypothesisCriteria,
    HypothesisVerdict,
    ImprovementMetrics,
    StatisticalEvidence,
)


def improvement(
    metric: str, baseline: float, treatment: float, denominator_n: int
) -> ImprovementMetrics:
    """One metric delta; relative/error terms need a nonzero baseline.

    ``error_reduction`` is the relative error reduction for
    accuracy-style metrics: (treatment - baseline) / (1 - baseline).
    """
    absolute_pp = (treatment - baseline) * 100.0
    relative_pct = (treatment - baseline) / baseline * 100.0 if baseline != 0 else None
    error_reduction = (
        (treatment - baseline) / (1.0 - baseline) * 100.0 if baseline not in (0.0, 1.0) else None
    )
    return ImprovementMetrics(
        metric=metric,
        baseline=baseline,
        treatment=treatment,
        denominator_n=denominator_n,
        absolute_pp=absolute_pp,
        relative_pct=relative_pct,
        error_reduction=error_reduction,
    )


def compare_scores(
    baseline: BenchmarkScores, treatment: BenchmarkScores
) -> list[ImprovementMetrics]:
    """Primary + secondary metric deltas between two score sets."""
    pairs = [("execution_accuracy", baseline.execution_accuracy, treatment.execution_accuracy)]
    optional = [
        ("benchmark_pass_rate", baseline.benchmark_pass_rate, treatment.benchmark_pass_rate),
        ("parse_rate", baseline.parse_rate, treatment.parse_rate),
        (
            "execution_success_rate",
            baseline.execution_success_rate,
            treatment.execution_success_rate,
        ),
        ("invalid_sql_rate", baseline.invalid_sql_rate, treatment.invalid_sql_rate),
        ("timeout_rate", baseline.timeout_rate, treatment.timeout_rate),
    ]
    for name, base_value, treat_value in optional:
        if base_value is not None and treat_value is not None:
            pairs.append((name, base_value, treat_value))
    return [
        improvement(name, base_value, treat_value, min(baseline.n, treatment.n))
        for name, base_value, treat_value in pairs
    ]


def family_table(baseline: BenchmarkScores, treatment: BenchmarkScores) -> list[FamilyDelta]:
    """Per-family deltas over the union of observed families."""
    rows: list[FamilyDelta] = []
    for family in sorted(set(baseline.family_scores) | set(treatment.family_scores)):
        base_value = baseline.family_scores.get(family)
        treat_value = treatment.family_scores.get(family)
        delta = (
            (treat_value - base_value) * 100.0
            if base_value is not None and treat_value is not None
            else None
        )
        rows.append(
            FamilyDelta(
                family=family,
                baseline=base_value,
                treatment=treat_value,
                delta_pp=delta,
                n=min(
                    baseline.family_counts.get(family, 0), treatment.family_counts.get(family, 0)
                ),
            )
        )
    return rows


def edge_table(baseline: BenchmarkScores, treatment: BenchmarkScores) -> list[EdgeDelta]:
    """Per-edge-case deltas over the union of observed categories."""
    rows: list[EdgeDelta] = []
    for edge in sorted(set(baseline.edge_scores) | set(treatment.edge_scores)):
        base_value = baseline.edge_scores.get(edge)
        treat_value = treatment.edge_scores.get(edge)
        delta = (
            (treat_value - base_value) * 100.0
            if base_value is not None and treat_value is not None
            else None
        )
        rows.append(
            EdgeDelta(
                edge_case=edge,
                baseline=base_value,
                treatment=treat_value,
                delta_pp=delta,
                n=min(baseline.edge_counts.get(edge, 0), treatment.edge_counts.get(edge, 0)),
            )
        )
    return rows


def judge_hypothesis(
    comparison: ExperimentComparison, criteria: HypothesisCriteria
) -> HypothesisVerdict:
    """Configurable acceptance verdict; INSUFFICIENT_EVIDENCE is valid (§56)."""
    if comparison.sample_size < criteria.minimum_benchmark_size:
        return "INSUFFICIENT_EVIDENCE"
    families_covered = sum(1 for row in comparison.families if row.n > 0)
    if families_covered < criteria.minimum_family_coverage:
        return "INSUFFICIENT_EVIDENCE"
    primary = next((m for m in comparison.metrics if m["metric"] == criteria.primary_metric), None)
    if primary is None:
        return "INSUFFICIENT_EVIDENCE"
    if primary["absolute_pp"] >= criteria.improvement_threshold_pp:
        return "HYPOTHESIS_SUPPORTED"
    return "HYPOTHESIS_NOT_SUPPORTED"


def build_comparison(
    *,
    experiment_id: str,
    baseline: BenchmarkScores,
    treatment: BenchmarkScores,
    stats: StatisticalEvidence | None = None,
    criteria: HypothesisCriteria | None = None,
) -> ExperimentComparison:
    """Assemble the presentation-ready comparison (no single score)."""
    deltas = compare_scores(baseline, treatment)
    comparison = ExperimentComparison(
        experiment_id=experiment_id,
        metrics=[d.model_dump(mode="json") for d in deltas],
        families=family_table(baseline, treatment),
        edge_cases=edge_table(baseline, treatment),
        sample_size=min(baseline.n, treatment.n),
    )
    verdict = judge_hypothesis(comparison, criteria) if criteria else "INSUFFICIENT_EVIDENCE"
    return comparison.model_copy(update={"verdict": verdict})


def compare_experiments(
    result: ExperimentResult, criteria: HypothesisCriteria | None = None
) -> ExperimentComparison:
    """Rebuild the comparison view from a stored experiment result (§61)."""
    return build_comparison(
        experiment_id=result.experiment_id,
        baseline=result.baseline_metrics,
        treatment=result.treatment_metrics,
        stats=result.statistical_evidence,
        criteria=criteria,
    )
