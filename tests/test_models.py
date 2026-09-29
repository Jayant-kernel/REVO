"""Model tests: valid/invalid templates, instances, difficulty, schema."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from verified_data_factory.task_engine.errors import TemplateError
from verified_data_factory.task_engine.models import (
    ColumnDefinition,
    OracleSpec,
    TableDefinition,
    TaskTemplate,
)
from verified_data_factory.task_engine.validation import validate_template


def _template_kwargs(**overrides):
    base = {
        "template_id": "sql.test.example",
        "version": 1,
        "family": "test",
        "description": "Example template",
        "difficulty": 2,
        "schema_definition": [
            TableDefinition(
                name="t",
                columns=[ColumnDefinition(name="id", type="INTEGER", nullable=False)],
                row_count=5,
                row_kind="generic",
            )
        ],
        "oracle_spec": OracleSpec(type="reference_query", strategy="s"),
        "instruction_template": "Using the {tables} table do things.",
    }
    base.update(overrides)
    return base


def test_valid_task_template():
    t = TaskTemplate(**_template_kwargs())
    assert t.template_id == "sql.test.example"


def test_invalid_difficulty_rejected():
    with pytest.raises((PydanticValidationError, TemplateError, ValueError)):
        TaskTemplate(**_template_kwargs(difficulty=9))


def test_invalid_schema_duplicate_columns():
    with pytest.raises((PydanticValidationError, ValueError)):
        TableDefinition(
            name="t",
            columns=[
                ColumnDefinition(name="id", type="INTEGER", nullable=False),
                ColumnDefinition(name="id", type="VARCHAR", nullable=True),
            ],
            row_count=5,
        )


def test_invalid_duckdb_type_rejected():
    with pytest.raises((PydanticValidationError, ValueError)):
        ColumnDefinition(name="c", type="NOTATYPE", nullable=True)


def test_template_id_must_start_with_sql():
    with pytest.raises((PydanticValidationError, ValueError)):
        TaskTemplate(**_template_kwargs(template_id="nope"))


def test_template_validation_rejects_bad_edge_case():
    t = TaskTemplate(**_template_kwargs(edge_cases=["teleportation"]))
    with pytest.raises(TemplateError):
        validate_template(t)


def test_template_validation_rejects_bad_oracle():
    t = TaskTemplate(**_template_kwargs(oracle_spec=OracleSpec(type="vibes", strategy="trust me")))
    with pytest.raises(TemplateError):
        validate_template(t)
