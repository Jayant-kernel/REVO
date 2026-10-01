from types import SimpleNamespace

from verified_data_factory.quality.population_metrics import (
    cross_task_semantic_duplicate_rate,
    population_duplicate_report,
)


def _quality(
    candidate: str, task: str, group: str | None, decision: str = "EXCLUDED"
) -> SimpleNamespace:
    return SimpleNamespace(
        candidate_id=candidate,
        task_id=task,
        template_id="template",
        template_version=1,
        role="UNKNOWN",
        semantic_duplicate_group=group,
        structural_duplicate_group=None,
        exact_duplicate_group=None,
        decision=decision,
    )


def test_siblings_are_not_cross_task_duplication() -> None:
    siblings = [_quality(f"c{i}", "one", "sem-one") for i in range(3)]
    assert cross_task_semantic_duplicate_rate(siblings) == 0.0
    report = population_duplicate_report(siblings)
    assert report["candidate_population"]["sibling_candidate_rows"] == 2
    assert report["external_benchmark_overlap"]["status"] == "NOT_MEASURED"


def test_cross_task_collision_and_selected_denominator() -> None:
    qualities = [
        _quality("a", "one", "sem-same", "GOLDEN"),
        _quality("b", "one", "sem-same"),
        _quality("c", "two", "sem-same", "GOLDEN"),
        _quality("d", "three", None),
    ]
    assert cross_task_semantic_duplicate_rate(qualities) == 2 / 3
    report = population_duplicate_report(qualities)
    assert report["selected_population"]["rows"] == 2
    assert report["selected_population"]["semantic_collision_members"] == 2
