"""Release metrics assembly (Phase 7, §28).

Metrics are *referenced* from Phase 5 analysis artifacts, never
recomputed: this module only reshapes health/coverage/duplicate/
verification/audit/contamination payloads into the release-level
``ProductMetrics`` view. Counts come from the actual built splits.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .models import ProductMetrics, SplitName


def build_metrics(
    *,
    split_counts: dict[str, int],
    product_records: list[dict[str, Any]],
    health: dict[str, Any] | None = None,
    coverage: dict[str, Any] | None = None,
    duplicates: dict[str, Any] | None = None,
    verification_summary: dict[str, Any] | None = None,
    audit_summary: dict[str, Any] | None = None,
    contamination: dict[str, Any] | None = None,
) -> ProductMetrics:
    """Assemble release-level metrics from Phase 5 payloads + built splits."""
    families = Counter(str(r.get("task_family", "unknown")) for r in product_records)
    difficulties = Counter(str(r.get("difficulty", "unknown")) for r in product_records)
    return ProductMetrics(
        record_count=sum(split_counts.values()),
        train_count=split_counts.get("train", 0),
        public_eval_count=split_counts.get("public_eval", 0),
        private_eval_count=split_counts.get("private_eval", 0),
        benchmark_count=split_counts.get("benchmark", 0),
        family_distribution=dict(sorted(families.items())),
        difficulty_distribution=dict(sorted(difficulties.items())),
        coverage_summary=dict(coverage or {}),
        duplicate_summary=_summarize_duplicates(duplicates),
        verification_summary=dict(verification_summary or {}),
        audit_summary=dict(audit_summary or {}),
        contamination_summary=_summarize_contamination(contamination),
    )


def _summarize_duplicates(duplicates: dict[str, Any] | None) -> dict[str, Any]:
    if not duplicates:
        return {}
    groups = duplicates.get("groups", [])
    by_type: Counter[str] = Counter()
    for group in groups if isinstance(groups, list) else []:
        if isinstance(group, dict):
            by_type[str(group.get("duplicate_type", "UNKNOWN"))] += 1
    return {
        "group_count": duplicates.get("group_count", len(by_type)),
        "by_type": dict(sorted(by_type.items())),
        "total_records": duplicates.get("total_records"),
    }


def _summarize_contamination(contamination: dict[str, Any] | None) -> dict[str, Any]:
    if not contamination:
        return {}
    pairs = contamination.get("pairs", contamination.get("contaminated_pairs", []))
    count = len(pairs) if isinstance(pairs, list) else contamination.get("pair_count", 0)
    return {"pair_count": count, "summary": contamination.get("summary", "")}


def metrics_payload(metrics: ProductMetrics) -> dict[str, Any]:
    """JSON-ready metrics payload for the dataset card."""
    return metrics.model_dump(mode="json")


def split_record_view(
    splits: dict[SplitName, Any],
    records_by_id: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Ordered per-split record lists (candidate-id order within each split)."""
    view: dict[str, list[dict[str, Any]]] = {}
    for name, split in splits.items():
        view[str(name)] = [records_by_id[c] for c in split.candidate_ids if c in records_by_id]
    return view
