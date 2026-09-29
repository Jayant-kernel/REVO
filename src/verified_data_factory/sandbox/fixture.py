"""Execution fixture packaging (Phase 3).

Reconstructs the task fixture through the Phase 1 public API
(``task_engine.api``) — no fixture-generation logic is duplicated here.
The canonical task fixture is never touched: the package is serialized to
bytes and delivered on container stdin, so no host directory is staged,
mounted, or copied.
"""

from __future__ import annotations

import json
from typing import Any

from verified_data_factory.task_engine import (
    get_template,
    load_builtin_registry,
)
from verified_data_factory.task_engine.api import recreate_fixture
from verified_data_factory.task_engine.models import TaskInstance

STAGING_VERSION = "1.0"


def build_execution_package(task: TaskInstance) -> dict[str, Any]:
    """Rebuild fixture rows + schema payload for ``task`` (pure, no I/O)."""
    registry = load_builtin_registry()
    template = get_template(registry, task.template_id, task.template_version)
    tables, metadata = recreate_fixture(template, task.seed)
    schema = [
        {
            "name": table.name,
            "columns": [
                {"name": col.name, "type": col.type, "nullable": col.nullable}
                for col in table.columns
            ],
        }
        for table in sorted(task.schema_, key=lambda t: t.name)
    ]
    return {
        "staging_version": STAGING_VERSION,
        "task_id": task.task_id,
        "schema": schema,
        "tables": tables,
        "fixture_metadata": metadata.model_dump(mode="json"),
    }


def build_execution_payload(
    package: dict[str, Any], candidate_sql: str, max_result_rows: int
) -> bytes:
    """Serialize the execution package for container-stdin delivery.

    One JSON envelope ``{fixture, sql, run}``; the harness reads it from
    stdin, so no host directory is ever staged, mounted, or copied.
    """
    return json.dumps(
        {
            "fixture": {"schema": package["schema"], "tables": package["tables"]},
            "sql": candidate_sql,
            "run": {
                "task_id": package["task_id"],
                "max_result_rows": max_result_rows,
                "staging_version": STAGING_VERSION,
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")
