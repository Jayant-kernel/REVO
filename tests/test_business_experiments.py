"""Experiment identity, scoring, comparison, and verdict tests (§8, §16–§18, §55–§56)."""

import json

import pytest

from tests.business_fixtures import (
    baseline_outcomes,
    control_outcomes,
    fixture_experiment_config,
    treatment_outcomes,
)
from verified_data_factory.business import (
    ArmSpec,
    HypothesisCriteria,
    build_comparison,
    create_experiment,
    improvement,
    judge_hypothesis,
    run_experiment,
    score_outcomes,
    verified_value_template,
)
from verified_data_factory.business.experiments import ArtifactAdapter


def test_deterministic_experiment_identity():
    assert fixture_experiment_config().experiment_id == fixture_experiment_config().experiment_id
    other = create_experiment(
        benchmark_id="bench-fixture-1",
        baseline=ArmSpec(model="fixture-base", adaptation_method="NONE"),
        treatment=ArmSpec(model="other", adaptation_method="SFT"),
        experiment_version="1.0",
        scoring_method="external-harness-aggregation",
    )
    assert other.experiment_id != fixture_experiment_config().experiment_id


def test_scoring_primary_metrics():
    scores = score_outcomes(baseline_outcomes())
    assert scores.n == 12
    assert scores.execution_accuracy == pytest.approx(7 / 12)
    assert scores.benchmark_pass_rate == pytest.approx(7 / 12)
    assert set(scores.family_scores) == {"simple_joins", "aggregation", "cte", "window_functions"}
    assert scores.edge_scores["null_values"] == pytest.approx(2 / 4)
    assert scores.timeout_rate == 0.0
    assert scores.avg_latency_ms is not None and scores.p95_latency_ms is not None


def test_percentage_point_vs_relative_math():
    delta = improvement("execution_accuracy", 7 / 12, 10 / 12, 12)
    assert delta.absolute_pp == pytest.approx(25.0)
    assert delta.relative_pct == pytest.approx((10 - 7) / 7 * 100.0)
    assert delta.denominator_n == 12
    # Zero baseline: relative undefined, absolute still reported.
    zero = improvement("m", 0.0, 0.5, 10)
    assert zero.absolute_pp == pytest.approx(50.0)
    assert zero.relative_pct is None


def test_full_run_baseline_vs_treatment(tmp_path):
    for arm, outcomes in (
        ("baseline", baseline_outcomes()),
        ("treatment", treatment_outcomes()),
        ("control", control_outcomes()),
    ):
        (tmp_path / f"{arm}.jsonl").write_text(
            "\n".join(json.dumps(o.model_dump(mode="json")) for o in outcomes) + "\n",
            encoding="utf-8",
        )
    result = run_experiment(
        config=fixture_experiment_config(),
        adapter=ArtifactAdapter(),
        locator=str(tmp_path),
        run_id="run-1",
        criteria=HypothesisCriteria(
            primary_metric="execution_accuracy",
            improvement_threshold_pp=5.0,
            minimum_benchmark_size=10,
        ),
    )
    assert result.experiment_id == fixture_experiment_config().experiment_id
    assert result.control_metrics is not None
    assert result.control_metrics.execution_accuracy == pytest.approx(8 / 12)
    primary = next(m for m in result.deltas if m.metric == "execution_accuracy")
    assert primary.absolute_pp == pytest.approx(25.0)
    assert result.statistical_evidence is not None
    assert result.reproducibility["seeds"] == [42, 43]


def test_comparison_verdicts():
    comparison = build_comparison(
        experiment_id="x",
        baseline=score_outcomes(baseline_outcomes()),
        treatment=score_outcomes(treatment_outcomes()),
        criteria=HypothesisCriteria(
            primary_metric="execution_accuracy",
            improvement_threshold_pp=5.0,
            minimum_benchmark_size=10,
        ),
    )
    assert comparison.verdict == "HYPOTHESIS_SUPPORTED"
    strict = judge_hypothesis(comparison, HypothesisCriteria(minimum_benchmark_size=10_000))
    assert strict == "INSUFFICIENT_EVIDENCE"
    high_bar = judge_hypothesis(
        comparison,
        HypothesisCriteria(
            primary_metric="execution_accuracy",
            improvement_threshold_pp=50.0,
            minimum_benchmark_size=1,
        ),
    )
    assert high_bar == "HYPOTHESIS_NOT_SUPPORTED"


def test_verified_value_template_arms():
    config = verified_value_template(
        benchmark_id="b",
        verified_release_id="sha256:rel",
        generic_baseline_id="generic-1",
        model="m",
    )
    assert config.control is not None
    assert config.treatment.dataset_release_id == "sha256:rel"
    assert config.baseline.adaptation_method == "NONE"
