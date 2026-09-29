"""Deterministic Phase 8 fixtures (no models, no network, no customers).

Every record is synthetic and explicitly tagged TEST_FIXTURE where it
enters the evidence model. Fixture data is quarantined from production
evidence by construction — it exists to exercise the framework, never
to support a business claim.
"""

from verified_data_factory.business import (
    ArmSpec,
    BenchmarkItem,
    PredictionOutcome,
    create_benchmark,
    create_experiment,
    freeze_benchmark,
)

FIXTURE_NOTE = "TEST_FIXTURE synthetic data for framework tests only"

FAMILIES = ("simple_joins", "aggregation", "cte", "window_functions")


def benchmark_items(n: int = 12) -> list[BenchmarkItem]:
    """Private benchmark members with groups, templates, and answers."""
    items = []
    for index in range(n):
        family = FAMILIES[index % len(FAMILIES)]
        items.append(
            BenchmarkItem(
                record_id=f"bench-{index:03d}",
                family=family,
                edge_cases=["null_values"] if index % 3 == 0 else [],
                template_id=f"sql.test.{family}",
                semantic_group=f"sem-{index % 4}",
                exact_group=f"exa-{index % 6}",
                expected_sql=f"SELECT * FROM t WHERE id > {index};",
            )
        )
    return items


def frozen_fixture_benchmark():
    """A frozen private benchmark plus its member items."""
    definition, items = create_benchmark(
        items=benchmark_items(),
        benchmark_version="1.0",
        split="private_benchmark",
        evaluation_policy="owner-harness-execution",
        scoring_policy="aggregation-v1",
        privacy_level="PRIVATE",
        dataset_release_id="sha256:fixture-release",
    )
    return freeze_benchmark(definition), items


def training_context() -> tuple[list[str], dict[str, dict]]:
    """Training ids + quality-style groups, disjoint from the benchmark.

    Template ids live in a separate ``sql.train.*`` namespace so the
    clean context shares families (for scoring) but no template identity.
    """
    ids = [f"train-{index:03d}" for index in range(20)]
    groups = {
        record_id: {
            "semantic_duplicate_group": f"tr-sem-{index % 5}",
            "exact_duplicate_group": f"tr-exa-{index % 7}",
            "template_id": f"sql.train.{FAMILIES[index % len(FAMILIES)]}",
        }
        for index, record_id in enumerate(ids)
    }
    return ids, groups


def contaminated_training_context() -> tuple[list[str], dict[str, dict]]:
    """Training context that leaks: shares ids, groups, and templates."""
    ids = ["bench-000", "bench-001", "train-000"]
    groups = {
        "bench-000": {"semantic_duplicate_group": "sem-0", "template_id": "sql.test.simple_joins"},
        "bench-001": {"exact_duplicate_group": "exa-1", "template_id": "sql.test.aggregation"},
        "train-000": {"template_id": "sql.test.cte"},
    }
    return ids, groups


def _outcomes(correct_ids: set[str], *, latency: float = 12.0) -> list[PredictionOutcome]:
    outcomes = []
    for index in range(12):
        record_id = f"bench-{index:03d}"
        family = FAMILIES[index % len(FAMILIES)]
        outcomes.append(
            PredictionOutcome(
                record_id=record_id,
                correct=record_id in correct_ids,
                family=family,
                edge_cases=["null_values"] if index % 3 == 0 else [],
                latency_ms=latency + index,
                error_type=None if record_id in correct_ids else "wrong_result",
            )
        )
    return outcomes


def baseline_outcomes() -> list[PredictionOutcome]:
    """7/12 correct (ids 0,1,2,4,6,8,10)."""
    return _outcomes(
        {"bench-000", "bench-001", "bench-002", "bench-004", "bench-006", "bench-008", "bench-010"}
    )


def treatment_outcomes() -> list[PredictionOutcome]:
    """10/12 correct: fixes 3 of baseline's 5 misses, regresses none (+2 net)."""
    return _outcomes(
        {
            "bench-000",
            "bench-001",
            "bench-002",
            "bench-003",
            "bench-004",
            "bench-006",
            "bench-007",
            "bench-008",
            "bench-010",
            "bench-011",
        }
    )


def control_outcomes() -> list[PredictionOutcome]:
    """8/12 correct: generic synthetic helps a little (+1 vs baseline)."""
    return _outcomes(
        {
            "bench-000",
            "bench-001",
            "bench-002",
            "bench-004",
            "bench-005",
            "bench-006",
            "bench-008",
            "bench-010",
        }
    )


def repeated_values() -> list[float]:
    return [0.70, 0.75, 0.72, 0.74, 0.71]


def fixture_experiment_config():
    """Deterministic VERIFIED DATA VALUE experiment contract."""
    return create_experiment(
        benchmark_id="bench-fixture-1",
        baseline=ArmSpec(model="fixture-base", adaptation_method="NONE"),
        treatment=ArmSpec(
            model="fixture-base",
            dataset_release_id="sha256:fixture-release",
            adaptation_method="SFT",
        ),
        control=ArmSpec(
            model="fixture-base",
            baseline_dataset_id="generic-fixture",
            adaptation_method="SFT",
        ),
        experiment_version="1.0",
        scoring_method="external-harness-aggregation",
        seeds=[42, 43],
    )
