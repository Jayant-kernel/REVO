"""Canonical representation for deterministic comparison (Phase 1).

Two tasks are semantically identical at the Task Engine level iff their
canonical JSON strings are equal. Normalizes dict ordering and table
ordering; preserves everything that changes task semantics (column order
within a table, row order is normalized by sorting rows).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import TaskInstance


def canonical_task_dict(task: TaskInstance) -> dict[str, Any]:
    """Return a normalized dict for a task instance.

    Serialized with field aliases, so the external contract keeps the
    ``"schema"`` key (internal attribute is ``schema_``).
    """
    data = task.model_dump(mode="json", by_alias=True)
    schema = sorted(data["schema"], key=lambda t: t["name"])
    tables = {
        name: sorted(rows, key=lambda r: json.dumps(r, sort_keys=True, default=str))
        for name, rows in sorted(data["tables"].items())
    }
    data["schema"] = schema
    data["tables"] = tables
    data["edge_cases"] = sorted(data["edge_cases"])
    return data


def canonical_json(task: TaskInstance) -> str:
    """Stable, pretty-printed JSON string for comparison and hashing."""
    return json.dumps(canonical_task_dict(task), sort_keys=True, indent=2, default=str)


def canonical_hash(task: TaskInstance) -> str:
    """SHA-256 hex digest of the canonical representation."""
    return hashlib.sha256(canonical_json(task).encode("utf-8")).hexdigest()
