"""Freeze the fresh, targeted Pilot-002 diagnostic task set."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from verified_data_factory import __version__ as FACTORY_VERSION
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.export import task_to_dict

OUT = Path("runs/pilot-002-diagnostic")
PROBLEM_FAMILIES = (
    "sql.aggregation.grouped",
    "sql.cte.monthly",
    "sql.dedup.latest",
    "sql.funnel.completion",
    "sql.temporal.monthly",
)
WORKING_FAMILIES = (
    "sql.joins.simple",
    "sql.joins.multi",
    "sql.subqueries.exists",
    "sql.windows.ranked",
    "sql.retention.30_day",
)


def main() -> None:
    tasks_dir = OUT / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    registry = load_builtin_registry()
    rows = []
    versions: dict[str, int] = {}
    for family_index, template_id in enumerate(PROBLEM_FAMILIES):
        template = registry.get(template_id)
        versions[template_id] = template.version
        for offset in range(30):
            rows.append(task_to_dict(generate_task(template, 20_000 + family_index * 100 + offset)))
    for family_index, template_id in enumerate(WORKING_FAMILIES):
        template = registry.get(template_id)
        versions[template_id] = template.version
        for offset in range(2):
            rows.append(task_to_dict(generate_task(template, 21_000 + family_index * 10 + offset)))
    path = tasks_dir / "tasks.jsonl"
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )
    manifest = {
        "pilot_id": "pilot-002-diagnostic",
        "tasks": len(rows),
        "problem_family_tasks": 30,
        "working_family_tasks": 10,
        "seed_policy": "fresh deterministic seeds 20000-21499",
        "template_versions": versions,
        "prompt_version": "sql-v2",
        "task_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "factory_version": FACTORY_VERSION,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
