"""Paired statistics tests (Phase 8, §19–§20)."""

from tests.business_fixtures import baseline_outcomes, repeated_values, treatment_outcomes
from verified_data_factory.business import (
    compare_paired,
    mcnemar_exact_p,
    summarize_repeated,
    wilson_interval,
)


def test_mcnemar_exact_known_values():
    # b=0, c=3: p = 2 * (C(3,0)/8) = 0.25 — not significant, honestly reported.
    assert mcnemar_exact_p(0, 3) == 0.25
    assert mcnemar_exact_p(0, 0) == 1.0
    assert 0.0 < mcnemar_exact_p(1, 9) < 0.05


def test_wilson_interval_bounds():
    low, high = wilson_interval(7, 12)
    assert 0.0 <= low < 7 / 12 < high <= 1.0
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_paired_comparison_fixture():
    stats = compare_paired(baseline_outcomes(), treatment_outcomes())
    assert stats.method == "MCNEMAR_EXACT"
    assert stats.n == 12
    assert stats.discordant_pairs == 3
    assert stats.delta_pp == 25.0
    assert stats.p_value == 0.25
    assert stats.baseline_ci is not None and stats.treatment_ci is not None
    # n=12 and 3 discordant pairs: limited power, explicitly warned.
    assert stats.sufficient is False
    assert any("small sample" in w for w in stats.warnings)
    assert any("discordant" in w for w in stats.warnings)


def test_no_shared_instances_insufficient():
    from verified_data_factory.business import PredictionOutcome

    left = [PredictionOutcome(record_id="a", correct=True, family="f")]
    right = [PredictionOutcome(record_id="b", correct=True, family="f")]
    stats = compare_paired(left, right)
    assert stats.method == "INSUFFICIENT_DATA"
    assert stats.sufficient is False


def test_repeated_run_variance():
    summary = summarize_repeated(repeated_values())
    assert summary.n == 5
    assert summary.mean == 0.724
    assert summary.minimum == 0.70 and summary.maximum == 0.75
    assert summary.std is not None and summary.std > 0
    assert summarize_repeated([]).n == 0
    single = summarize_repeated([0.8])
    assert single.std == 0.0 and single.mean == 0.8
