"""Fixture packaging tests: Phase 1 API reuse, canonical fixture untouched."""

import json

from verified_data_factory.sandbox import build_execution_package, build_execution_payload
from verified_data_factory.task_engine import canonical_json, generate_task


def test_package_rebuilds_canonical_fixture(registry):
    task = generate_task(registry.get("sql.retention.30_day"), seed=901)
    package = build_execution_package(task)
    assert package["task_id"] == task.task_id
    assert package["staging_version"] == "1.0"
    assert set(package["tables"]) == set(task.tables)
    for name, rows in package["tables"].items():
        assert rows == task.tables[name]


def test_payload_envelope_and_canonical_intact(registry):
    task = generate_task(registry.get("sql.joins.simple"), seed=101)
    before = canonical_json(task)
    package = build_execution_package(task)
    blob = build_execution_payload(package, "SELECT 1;", 100)
    envelope = json.loads(blob.decode("utf-8"))
    assert set(envelope) == {"fixture", "sql", "run"}
    assert envelope["sql"] == "SELECT 1;"
    assert envelope["run"]["max_result_rows"] == 100
    assert envelope["fixture"]["tables"] == task.tables
    assert canonical_json(task) == before
