"""Benchmark lifecycle, separation, and contamination tests (§9–§11)."""

import pytest

from tests.business_fixtures import (
    benchmark_items,
    contaminated_training_context,
    frozen_fixture_benchmark,
    training_context,
)
from verified_data_factory.business import (
    benchmark_fingerprint,
    check_contamination,
    create_benchmark,
    validate_benchmark,
)
from verified_data_factory.business.errors import BusinessConfigError


def test_deterministic_benchmark_identity():
    first, _ = create_benchmark(
        items=benchmark_items(),
        benchmark_version="1.0",
        split="private_benchmark",
        evaluation_policy="p",
        scoring_policy="s",
    )
    second, _ = create_benchmark(
        items=list(reversed(benchmark_items())),
        benchmark_version="1.0",
        split="private_benchmark",
        evaluation_policy="p",
        scoring_policy="s",
    )
    assert first.benchmark_id == second.benchmark_id
    assert first.fingerprint == benchmark_fingerprint(first.record_ids)


def test_frozen_benchmark_validates_clean():
    definition, items = frozen_fixture_benchmark()
    assert definition.frozen is True
    assert definition.privacy_level == "PRIVATE"
    assert validate_benchmark(definition, items) == []


def test_frozen_membership_drift_detected():
    definition, items = frozen_fixture_benchmark()
    assert "frozen benchmark was modified" in " ".join(validate_benchmark(definition, items[1:]))


def test_empty_and_duplicate_benchmarks_rejected():
    with pytest.raises(BusinessConfigError):
        create_benchmark(
            items=[], benchmark_version="1", split="s", evaluation_policy="p", scoring_policy="s"
        )
    doubled = benchmark_items() + benchmark_items()[:1]
    with pytest.raises(BusinessConfigError):
        create_benchmark(
            items=doubled,
            benchmark_version="1",
            split="s",
            evaluation_policy="p",
            scoring_policy="s",
        )


def test_clean_training_context_passes():
    definition, items = frozen_fixture_benchmark()
    ids, groups = training_context()
    report = check_contamination(
        benchmark_id=definition.benchmark_id,
        benchmark_items=items,
        training_record_ids=ids,
        training_groups=groups,
    )
    assert report.is_clean is True
    assert report.exact_overlap == [] and report.membership_leakage == []


def test_contaminated_context_detected_by_category():
    definition, items = frozen_fixture_benchmark()
    ids, groups = contaminated_training_context()
    report = check_contamination(
        benchmark_id=definition.benchmark_id,
        benchmark_items=items,
        training_record_ids=ids,
        training_groups=groups,
    )
    assert report.is_clean is False
    assert "bench-000" in report.exact_overlap  # shared id
    assert "bench-000" in report.semantic_overlap  # shared sem-0
    assert "bench-001" in report.exact_overlap  # shared id (and exa-1 group)
    assert report.template_overlap  # sql.test.cte / simple_joins / aggregation leak
    assert report.membership_leakage  # union of id/group overlap
