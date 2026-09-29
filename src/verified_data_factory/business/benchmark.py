"""Private benchmark lifecycle and contamination checks (§9–§11).

Benchmarks are created, frozen (immutable), validated, scored, and
compared. Freezing locks the membership fingerprint: any silent change
is detected, not tolerated. A benchmark is not private because its file
is local — it is private only when membership is separated from TRAIN /
PUBLIC_EVAL releases and contamination checks pass.
"""

from __future__ import annotations

from typing import Any

from .config import benchmark_fingerprint, benchmark_id_for
from .errors import BusinessConfigError, BusinessValidationError
from .models import BenchmarkDefinition, BenchmarkItem, ContaminationCheck, PrivacyLevel


def create_benchmark(
    *,
    items: list[BenchmarkItem],
    benchmark_version: str,
    split: str,
    evaluation_policy: str,
    scoring_policy: str,
    privacy_level: PrivacyLevel = "PRIVATE",
    dataset_release_id: str | None = None,
) -> tuple[BenchmarkDefinition, list[BenchmarkItem]]:
    """Create an unfrozen benchmark from explicit member items."""
    if not items:
        raise BusinessConfigError("benchmark needs at least one member item")
    record_ids = [item.record_id for item in items]
    if len(set(record_ids)) != len(record_ids):
        raise BusinessConfigError("benchmark member record ids must be unique")
    benchmark_id = benchmark_id_for(
        record_ids=record_ids,
        benchmark_version=benchmark_version,
        evaluation_policy=evaluation_policy,
        scoring_policy=scoring_policy,
    )
    ordered = sorted(items, key=lambda item: item.record_id)
    definition = BenchmarkDefinition(
        benchmark_id=benchmark_id,
        benchmark_version=benchmark_version,
        dataset_release_id=dataset_release_id,
        split=split,
        task_families=sorted({item.family for item in ordered}),
        record_ids=[item.record_id for item in ordered],
        fingerprint=benchmark_fingerprint(record_ids),
        evaluation_policy=evaluation_policy,
        scoring_policy=scoring_policy,
        privacy_level=privacy_level,
        frozen=False,
    )
    return definition, ordered


def freeze_benchmark(definition: BenchmarkDefinition) -> BenchmarkDefinition:
    """Freeze a benchmark: membership becomes immutable from here on."""
    return definition.model_copy(update={"frozen": True})


def validate_benchmark(definition: BenchmarkDefinition, items: list[BenchmarkItem]) -> list[str]:
    """Return violations (empty means valid). Frozen drift always fails."""
    violations: list[str] = []
    current_ids = sorted(item.record_id for item in items)
    if current_ids != sorted(definition.record_ids):
        violations.append("benchmark membership differs from definition record_ids")
    if benchmark_fingerprint(current_ids) != definition.fingerprint:
        violations.append("benchmark fingerprint mismatch: membership changed")
    if definition.frozen and violations:
        violations.append("frozen benchmark was modified")
    return violations


def check_contamination(
    *,
    benchmark_id: str,
    benchmark_items: list[BenchmarkItem],
    training_record_ids: list[str],
    training_groups: dict[str, dict[str, Any]] | None = None,
) -> ContaminationCheck:
    """Benchmark-vs-training overlap across five categories (§11).

    ``training_groups`` maps training record id → quality-style dict with
    optional ``exact_duplicate_group``, ``structural_duplicate_group``,
    ``semantic_duplicate_group``, and ``template_id`` keys (Phase 5
    concepts reused, not reimplemented).
    """
    groups = training_groups or {}
    training_ids = set(training_record_ids)

    def _group_hit(field: str, group_value: str | None) -> bool:
        return bool(group_value) and any(g.get(field) == group_value for g in groups.values())

    exact = sorted(
        ({i.record_id for i in benchmark_items} & training_ids)
        | {
            i.record_id
            for i in benchmark_items
            if _group_hit("exact_duplicate_group", i.exact_group)
        }
    )

    structural = sorted(
        {
            i.record_id
            for i in benchmark_items
            if _group_hit("structural_duplicate_group", i.structural_group)
        }
    )
    semantic = sorted(
        {
            i.record_id
            for i in benchmark_items
            if _group_hit("semantic_duplicate_group", i.semantic_group)
        }
    )
    train_templates = {str(g.get("template_id")) for g in groups.values() if g.get("template_id")}
    template = sorted(
        {i.record_id for i in benchmark_items if i.template_id and i.template_id in train_templates}
    )
    membership = sorted(set(exact) | set(structural) | set(semantic))
    is_clean = not (exact or structural or semantic or template or membership)
    return ContaminationCheck(
        benchmark_id=benchmark_id,
        exact_overlap=exact,
        structural_overlap=structural,
        semantic_overlap=semantic,
        template_overlap=template,
        membership_leakage=membership,
    ).model_copy(update={"is_clean": is_clean})


def benchmark_from_dict(data: dict[str, Any]) -> BenchmarkDefinition:
    try:
        return BenchmarkDefinition.model_validate(data)
    except Exception as exc:
        raise BusinessValidationError(f"invalid benchmark definition: {exc}") from exc


def benchmark_items_from_list(data: list[Any]) -> list[BenchmarkItem]:
    try:
        return [BenchmarkItem.model_validate(item) for item in data]
    except Exception as exc:
        raise BusinessValidationError(f"invalid benchmark items: {exc}") from exc
