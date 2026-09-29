"""JSON / JSONL export for task instances (Phase 1).

Normalized, machine-readable, round-trippable. A future Phase 7 dataset
exporter builds on this representation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import canonical_task_dict
from .models import TaskInstance


def task_to_dict(task: TaskInstance) -> dict[str, Any]:
    return canonical_task_dict(task)


def task_to_json(task: TaskInstance) -> str:
    return json.dumps(task_to_dict(task), indent=2)


def task_from_dict(data: dict[str, Any]) -> TaskInstance:
    return TaskInstance.model_validate(data)


def task_from_json(text: str) -> TaskInstance:
    # Tolerant of UTF-8 BOMs written by Windows tooling.
    return task_from_dict(json.loads(text.lstrip("\ufeff")))


def write_jsonl(tasks: list[TaskInstance], path: str | Path) -> Path:
    path = Path(path)
    with path.open("w", encoding="utf-8") as fh:
        for task in tasks:
            fh.write(json.dumps(task_to_dict(task), sort_keys=True) + "\n")
    return path


def read_jsonl(path: str | Path) -> list[TaskInstance]:
    tasks = []
    with Path(path).open(encoding="utf-8-sig") as fh:
        for line in fh:
            if line.strip():
                tasks.append(task_from_dict(json.loads(line)))
    return tasks
