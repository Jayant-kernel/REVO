"""Per-template tests: happy path, edge cases, determinism, serialization."""

import pytest

from verified_data_factory.task_engine import (
    canonical_json,
    generate_task,
    materialize_duckdb,
    task_from_dict,
    task_to_dict,
    validate_task,
)


@pytest.mark.parametrize("seed", [12345])
def test_every_template_generates_valid_task(registry, seed):
    for template in registry.list():
        task = generate_task(template, seed=seed)
        validate_task(task)  # must not raise
        assert task.task_id.startswith(template.template_id)
        assert task.template_version == template.version
        assert task.seed == seed
        assert task.tables  # non-empty fixtures


def test_every_template_declared_edge_cases_present(registry):
    for template in registry.list():
        task = generate_task(template, seed=999)
        assert set(task.edge_cases) == set(template.edge_cases)


def test_every_template_materializes_in_duckdb(registry):
    for template in registry.list():
        task = generate_task(template, seed=42)
        con = materialize_duckdb(task.schema_, task.tables)
        try:
            for table in task.schema_:
                n = con.execute(f'SELECT COUNT(*) FROM "{table.name}"').fetchone()[0]
                assert n == len(task.tables[table.name])
                assert n > 0
        finally:
            con.close()


def test_every_template_serialization_round_trip(registry):
    for template in registry.list():
        task = generate_task(template, seed=2024)
        restored = task_from_dict(task_to_dict(task))
        assert canonical_json(restored) == canonical_json(task)
