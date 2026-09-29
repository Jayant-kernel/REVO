"""Validation tests: invalid tasks rejected loudly."""

import pytest

from verified_data_factory.task_engine import generate_task, validate_task
from verified_data_factory.task_engine.errors import ValidationError


def test_invalid_task_id_rejected(registry):
    task = generate_task(registry.get("sql.joins.simple"), seed=101)
    bad = task.model_copy(update={"task_id": "totally-unrelated"})
    with pytest.raises(ValidationError):
        validate_task(bad)


def test_schema_mismatch_rejected(registry):
    task = generate_task(registry.get("sql.joins.simple"), seed=101)
    tables = dict(task.tables)
    tables["orders"] = [{**r, "bogus_col": 1} for r in tables["orders"]]
    bad = task.model_copy(update={"tables": tables})
    with pytest.raises(ValidationError):
        validate_task(bad)


def test_broken_fk_rejected(registry):
    task = generate_task(registry.get("sql.joins.simple"), seed=101)
    tables = {k: [dict(r) for r in v] for k, v in task.tables.items()}
    tables["orders"][0]["customer_id"] = 999_999
    bad = task.model_copy(update={"tables": tables})
    with pytest.raises(ValidationError):
        validate_task(bad)


def test_malformed_requirements_rejected(registry):
    task = generate_task(registry.get("sql.joins.simple"), seed=101)
    reqs = dict(task.requirements)
    reqs["output_columns"] = ["customers.no_such_column"]
    bad = task.model_copy(update={"requirements": reqs})
    with pytest.raises(ValidationError):
        validate_task(bad)
