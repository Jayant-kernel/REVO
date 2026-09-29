"""GoldenRecord → product record transformations (§13, §32–§34).

Deterministic, documented, versioned; the source GoldenRecord is never
modified. Every function stamps ``transformation_version`` so the exact
mapping is traceable. SQL dialect is DuckDB-only unless the record
contract says otherwise (it does not in this MVP).
"""

from __future__ import annotations

from typing import Any

from verified_data_factory.quality.models import GoldenRecord

from .models import (
    TRANSFORMATION_VERSION,
    BenchmarkRecord,
    EvaluationRecord,
    SplitName,
    TrainingRecord,
)
from .profiles import ProductProfile


def _ddl_text(schema: list[dict[str, Any]] | Any) -> str:
    """Render a stable DDL string from a GoldenRecord schema payload."""
    tables = schema if isinstance(schema, list) else []
    blocks: list[str] = []
    for table in sorted(tables, key=lambda t: str(t.get("name", ""))):
        columns = table.get("columns", []) or []
        rendered = ", ".join(
            f"{col.get('name')} {col.get('type')}"
            + ("" if col.get("nullable", True) else " NOT NULL")
            for col in sorted(columns, key=lambda c: str(c.get("name", "")))
        )
        blocks.append(f"CREATE TABLE {table.get('name')} ({rendered});")
    return "\n".join(blocks)


def _task_fields(golden: GoldenRecord) -> dict[str, Any]:
    task = golden.task if isinstance(golden.task, dict) else {}
    return {
        "task_id": task.get("task_id", golden.candidate_id),
        "instruction": golden.instruction,
        "schema": _ddl_text(golden.schema_),
        "template_id": str(task.get("template_id", "")),
        "template_version": int(task.get("template_version", 1)),
        "task_family": str(task.get("family", "")),
        "difficulty": int(task.get("difficulty", 1)),
    }


def to_training_record(
    golden: GoldenRecord,
    dataset_snapshot_id: str,
    transformation_version: str = TRANSFORMATION_VERSION,
) -> TrainingRecord:
    """GoldenRecord → canonical TrainingRecord (input + target)."""
    if not golden.candidate_solution:
        raise ValueError(f"golden record {golden.candidate_id} has no candidate SQL")
    base = _task_fields(golden)
    return TrainingRecord(
        task_id=base["task_id"],
        instruction=base["instruction"],
        schema_=base["schema"],
        sql=golden.candidate_solution,
        template_id=base["template_id"],
        template_version=base["template_version"],
        task_family=base["task_family"],
        difficulty=base["difficulty"],
        golden_record_id=golden.record_id,
        dataset_snapshot_id=dataset_snapshot_id,
    )


def to_evaluation_record(
    golden: GoldenRecord,
    dataset_snapshot_id: str,
    split: SplitName,
    profile: ProductProfile,
    transformation_version: str = TRANSFORMATION_VERSION,
) -> EvaluationRecord:
    """GoldenRecord → EvaluationRecord honoring target exposure policy."""
    base = _task_fields(golden)
    sql = golden.candidate_solution if profile.include_sql_target else None
    if profile.include_sql_target and not sql:
        raise ValueError(f"golden record {golden.candidate_id} has no candidate SQL")
    return EvaluationRecord(
        task_id=base["task_id"],
        instruction=base["instruction"],
        schema_=base["schema"],
        sql=sql,
        template_id=base["template_id"],
        template_version=base["template_version"],
        task_family=base["task_family"],
        difficulty=base["difficulty"],
        golden_record_id=golden.record_id,
        dataset_snapshot_id=dataset_snapshot_id,
        split=split,
    )


def to_benchmark_record(
    golden: GoldenRecord,
    dataset_snapshot_id: str,
    split: SplitName,
    profile: ProductProfile,
    index: int,
    transformation_version: str = TRANSFORMATION_VERSION,
) -> BenchmarkRecord:
    """GoldenRecord → BenchmarkRecord with a stable benchmark item id."""
    evaluation = to_evaluation_record(
        golden, dataset_snapshot_id, split, profile, transformation_version
    )
    return BenchmarkRecord(
        **evaluation.model_dump(by_alias=True),
        benchmark_item_id=f"bench-{index:06d}-{golden.record_id}",
    )


def transform_version() -> str:
    """Current transformation version stamped on every product record."""
    return TRANSFORMATION_VERSION
