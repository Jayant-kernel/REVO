"""Population-specific redundancy measurements for production decisions.

These are screening signals, not proof of semantic equivalence or external
benchmark cleanliness. Historical health artifacts retain their original names.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from .duplicate_detection import schema_fingerprint
from .models import RecordQuality, VerifiedRecord


def cross_task_semantic_duplicate_rate(qualities: Sequence[Any]) -> float:
    """Fraction of distinct tasks in a semantic group spanning multiple tasks.

    Sibling candidates for the same task contribute one task, never a collision.
    The semantic fingerprint is a screening heuristic, not an SQL equivalence proof.
    """
    tasks = {q.task_id for q in qualities}
    if not tasks:
        return 0.0
    groups: dict[str, set[str]] = defaultdict(set)
    for quality in qualities:
        if quality.semantic_duplicate_group:
            groups[quality.semantic_duplicate_group].add(quality.task_id)
    repeated = set().union(*(ids for ids in groups.values() if len(ids) > 1))
    return len(repeated) / len(tasks)


def population_duplicate_report(
    qualities: Sequence[RecordQuality], records: Sequence[VerifiedRecord] = ()
) -> dict[str, Any]:
    """Keep candidate and selected-release denominators distinct."""
    candidates = list(qualities)
    selected = [q for q in candidates if q.decision == "GOLDEN"]

    def selected_collisions(attribute: str) -> int:
        groups: dict[str, int] = defaultdict(int)
        for quality in selected:
            group = getattr(quality, attribute)
            if group:
                groups[group] += 1
        return sum(count for count in groups.values() if count > 1)

    roles_by_task: dict[str, set[str]] = defaultdict(set)
    roles_by_template: dict[tuple[str, int], set[str]] = defaultdict(set)
    for quality in candidates:
        if quality.role != "UNKNOWN":
            roles_by_task[quality.task_id].add(quality.role)
            roles_by_template[(quality.template_id, quality.template_version)].add(quality.role)
    cross_role_tasks = sorted(task for task, roles in roles_by_task.items() if len(roles) > 1)
    cross_role_templates = sorted(
        f"{template_id}@{version}"
        for (template_id, version), roles in roles_by_template.items()
        if len(roles) > 1
    )
    roles_by_schema: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.role != "UNKNOWN":
            schema = [table.model_dump(mode="json") for table in record.task.schema_]
            roles_by_schema[schema_fingerprint(schema)].add(record.role)
    cross_role_schemas = sorted(
        fingerprint for fingerprint, roles in roles_by_schema.items() if len(roles) > 1
    )
    return {
        "candidate_population": {
            "rows": len(candidates),
            "unique_tasks": len({q.task_id for q in candidates}),
            "sibling_candidate_rows": len(candidates) - len({q.task_id for q in candidates}),
            "cross_task_semantic_duplicate_rate": cross_task_semantic_duplicate_rate(candidates),
            "method": "task IDs across semantic fingerprint groups; heuristic",
        },
        "selected_population": {
            "rows": len(selected),
            "unique_tasks": len({q.task_id for q in selected}),
            "exact_collision_members": selected_collisions("exact_duplicate_group"),
            "structural_collision_members": selected_collisions("structural_duplicate_group"),
            "semantic_collision_members": selected_collisions("semantic_duplicate_group"),
            "limitation": "fingerprint groups are screening signals and do not prove semantic equivalence",
        },
        "cross_split": {
            "status": "MEASURED" if roles_by_task else "NOT_MEASURED",
            "cross_role_task_ids": cross_role_tasks,
            "cross_role_template_versions": cross_role_templates,
            "cross_role_schema_fingerprints": cross_role_schemas,
            "limitation": "UNKNOWN roles cannot establish split separation; schema overlap alone is not proof of leakage",
        },
        "external_benchmark_overlap": {
            "status": "NOT_MEASURED",
            "reference_sources": [],
            "reason": "No versioned external fingerprint corpus supplied",
        },
    }
