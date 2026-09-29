"""Diversity, coverage, and difficulty tests."""

from tests.quality_dataset import build_fixture_dataset
from verified_data_factory.quality import QualityConfig, analyze_dataset


def _analysis():
    return analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.0))


def test_family_distribution_counts_and_entropy():
    analysis = _analysis()
    family = analysis.diversity.family
    assert sum(family.counts.values()) == len(analysis.qualities)
    assert abs(sum(family.percentages.values()) - 1.0) < 1e-9
    assert family.entropy > 0
    assert family.counts.get("simple_joins", 0) >= 4


def test_sql_schema_and_edge_diversity_present():
    analysis = _analysis()
    assert analysis.diversity.sql_constructs.get("select", 0) == len(analysis.qualities)
    assert analysis.diversity.sql_constructs.get("join", 0) >= 1
    assert len(analysis.diversity.schema_fingerprints) >= 2
    assert analysis.diversity.edge_cases, "edge features must be recorded"


def test_operator_diversity_tracks_constructs():
    analysis = _analysis()
    assert set(analysis.diversity.operator_categories) == set(analysis.diversity.sql_constructs)


def test_coverage_counts_rates_and_uncovered():
    analysis = _analysis()
    coverage = analysis.coverage
    assert coverage.families_total == 10
    assert 0 < coverage.family_coverage_rate < 1.0
    assert coverage.uncovered_families, "fixture dataset must miss families"
    assert "subqueries" in coverage.uncovered_families
    assert coverage.constructs_total == 16
    assert coverage.uncovered_constructs, "some constructs must be uncovered"
    assert coverage.edge_cases_total > 0
    assert set(coverage.families_covered) | set(coverage.uncovered_families) == {
        "simple_joins",
        "multi_joins",
        "aggregation",
        "cte",
        "subqueries",
        "window_functions",
        "temporal",
        "deduplication",
        "retention",
        "funnel",
    }


def test_coverage_deterministic():
    first = _analysis()
    second = _analysis()
    assert first.coverage == second.coverage
    assert first.diversity == second.diversity


def test_declared_difficulty_preserved():
    analysis = _analysis()
    bands = analysis.difficulty.declared_distribution
    assert sum(bands.values()) == len(analysis.qualities)
    assert len(bands) >= 3, f"expected difficulty spread, got {bands}"
    assert analysis.difficulty.method == "DECLARED"


def test_empirical_unavailable_without_data():
    analysis = _analysis()
    assert not analysis.difficulty.empirical_available
    assert "solve-rate" in analysis.difficulty.empirical_reason
    for quality in analysis.qualities:
        assert quality.difficulty_features, "complexity features must still be recorded"
        assert quality.difficulty_features["family_difficulty_prior"] >= 1.0
