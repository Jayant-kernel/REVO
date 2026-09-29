"""Serialization tests: JSON/JSONL round-trips preserve all semantics."""

import json

import pytest

from verified_data_factory.task_engine import (
    canonical_json,
    deserialize_task,
    generate_task,
    read_jsonl,
    recreate_fixture,
    recreate_task,
    serialize_task,
    task_from_dict,
    task_to_dict,
    task_to_json,
    write_jsonl,
)
from verified_data_factory.task_engine.errors import ValidationError


def test_external_json_uses_schema_key(registry):
    task = generate_task(registry.get("sql.joins.simple"), seed=101)
    blob = serialize_task(task)
    data = json.loads(blob)
    assert "schema" in data
    assert "schema_" not in data
    assert data["seed"] == 101
    assert data["template_version"] == 1


def test_json_round_trip_preserves_semantics(registry):
    for template in registry.list():
        task = generate_task(template, seed=55)
        restored = deserialize_task(serialize_task(task))
        assert canonical_json(restored) == canonical_json(task)
        assert restored.schema_ == task.schema_
        assert restored.oracle_spec == task.oracle_spec
        assert restored.fixture_metadata == task.fixture_metadata
        assert restored.edge_cases == task.edge_cases
        assert restored.generation_metadata == task.generation_metadata


def test_jsonl_round_trip(registry, tmp_path):
    from tests.conftest import catalog_entries
    from verified_data_factory.task_engine import generate_batch

    tasks = []
    for entry in catalog_entries():
        template = registry.get(entry["template_id"], entry.get("version"))
        tasks.extend(generate_batch(template, list(entry["seeds"])))
    path = write_jsonl(tasks, tmp_path / "tasks.jsonl")
    restored = read_jsonl(path)
    assert len(restored) == 100
    for original, back in zip(tasks, restored):
        assert canonical_json(back) == canonical_json(original)


def test_deserialize_rejects_tampered_id(registry):
    task = generate_task(registry.get("sql.joins.simple"), seed=101)
    data = task_to_dict(task)
    data["task_id"] = "sql.joins.simple.v1.deadbeefcafe"
    with pytest.raises(ValidationError):
        deserialize_task(json.dumps(data))


def test_deserialize_tolerates_utf8_bom(registry):
    task = generate_task(registry.get("sql.joins.simple"), seed=101)
    restored = deserialize_task("\ufeff" + serialize_task(task))
    assert canonical_json(restored) == canonical_json(task)


def test_dict_round_trip_uses_alias(registry):
    task = generate_task(registry.get("sql.dedup.latest"), seed=801)
    d = task_to_dict(task)
    assert "schema" in d and "schema_" not in d
    assert canonical_json(task_from_dict(d)) == canonical_json(task)
    assert task_to_json(task) == serialize_task(task)


def test_recreate_task_and_fixture(registry):
    template = registry.get("sql.temporal.monthly")
    task = generate_task(template, seed=701)
    again = recreate_task(registry, task)
    assert canonical_json(again) == canonical_json(task)
    tables, meta = recreate_fixture(template, 701)
    assert tables == task.tables
    assert meta == task.fixture_metadata
