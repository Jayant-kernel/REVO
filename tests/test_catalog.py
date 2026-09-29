"""Export + catalog tests: 100 reproducible tasks, unique ids, round-trip."""

from tests.conftest import catalog_entries
from verified_data_factory.task_engine import (
    canonical_json,
    generate_batch,
    generate_task,
    task_from_json,
    task_to_json,
)


def test_catalog_has_100_tasks():
    entries = catalog_entries()
    assert len(entries) == 10
    assert sum(len(e["seeds"]) for e in entries) == 100


def test_100_tasks_unique_ids_serializable_recreatable(registry, tmp_path):
    tasks = []
    for entry in catalog_entries():
        template = registry.get(entry["template_id"], entry.get("version"))
        tasks.extend(generate_batch(template, list(entry["seeds"])))
    assert len(tasks) == 100
    ids = [t.task_id for t in tasks]
    assert len(set(ids)) == 100, "task ids must be unique"

    for task in tasks:
        blob = task_to_json(task)
        restored = task_from_json(blob)
        assert canonical_json(restored) == canonical_json(task)
        again = generate_task(registry.get(task.template_id, task.template_version), task.seed)
        assert canonical_json(again) == canonical_json(task)


def test_seed_replay_contract_holds(registry):
    for entry in catalog_entries():
        template = registry.get(entry["template_id"], entry.get("version"))
        for seed in entry["seeds"][:2]:
            a = generate_task(template, seed)
            b = generate_task(template, seed)
            assert canonical_json(a) == canonical_json(b)
            assert a.generation_metadata.engine_version == b.generation_metadata.engine_version
