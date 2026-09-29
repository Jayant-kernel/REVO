"""Canonical product schema, field classification, validation (§6, §10–§12, §38).

Schema ``verified-data-factory/sql/1.0``. Every GoldenRecord field is
explicitly classified so internal data cannot leak silently; product
records validate strictly (malformed records fail, never repaired).
"""

from __future__ import annotations

from typing import Any

from .errors import ProductConfigError
from .models import (
    SQL_DIALECT,
    SQL_SCHEMA_NAME,
    SQL_SCHEMA_VERSION,
    TRANSFORMATION_VERSION,
    FieldClass,
    FieldExposure,
    ProductSchema,
)

# GoldenRecord field → (exposure class, product field name or None).
FIELD_CLASSIFICATION: dict[str, tuple[FieldClass, str | None]] = {
    "candidate_id": ("METADATA", "golden_record_id"),
    "task.task_id": ("METADATA", "task_id"),
    "task.instruction": ("MODEL_INPUT", "instruction"),
    "task.schema": ("MODEL_INPUT", "schema"),
    "candidate.candidate_sql": ("MODEL_TARGET", "sql"),
    "task.template_id": ("METADATA", "template_id"),
    "task.template_version": ("METADATA", "template_version"),
    "task.family": ("METADATA", "task_family"),
    "task.difficulty": ("METADATA", "difficulty"),
    "task.seed": ("METADATA", None),
    "task.fixture": ("METADATA", None),
    "task.requirements": ("INTERNAL_ONLY", None),
    "task.edge_cases": ("METADATA", None),
    "candidate.model": ("PROVENANCE", None),
    "candidate.prompt_version": ("PROVENANCE", None),
    "candidate.raw_response": ("INTERNAL_ONLY", None),
    "execution": ("INTERNAL_ONLY", None),
    "verification": ("INTERNAL_ONLY", None),
    "verification.verdict": ("METADATA", None),
    "verification.mutation_score": ("METADATA", None),
    "quality.decision": ("METADATA", None),
    "quality.reasons": ("METADATA", None),
    "provenance.snapshot": ("PROVENANCE", None),
    "provenance.nodes": ("PROVENANCE", None),
}

TRAINING_FIELDS = ("task_id", "instruction", "schema", "sql")
EVALUATION_FIELDS = ("task_id", "instruction", "schema", "sql")


def canonical_schema() -> ProductSchema:
    """The versioned canonical schema for analytical-SQL products."""
    fields = [
        FieldExposure(field="instruction", exposure="MODEL_INPUT", product_field="instruction"),
        FieldExposure(field="schema", exposure="MODEL_INPUT", product_field="schema"),
        FieldExposure(field="candidate_sql", exposure="MODEL_TARGET", product_field="sql"),
        FieldExposure(field="task_id", exposure="METADATA", product_field="task_id"),
        FieldExposure(field="template_id", exposure="METADATA", product_field="template_id"),
        FieldExposure(
            field="template_version", exposure="METADATA", product_field="template_version"
        ),
        FieldExposure(field="task_family", exposure="METADATA", product_field="task_family"),
        FieldExposure(field="difficulty", exposure="METADATA", product_field="difficulty"),
        FieldExposure(
            field="golden_record_id", exposure="METADATA", product_field="golden_record_id"
        ),
        FieldExposure(
            field="dataset_snapshot_id", exposure="PROVENANCE", product_field="dataset_snapshot_id"
        ),
    ]
    return ProductSchema(
        schema_name=SQL_SCHEMA_NAME,
        schema_version=SQL_SCHEMA_VERSION,
        dialect=SQL_DIALECT,
        fields=fields,
        transformation_version=TRANSFORMATION_VERSION,
    )


def schema_compatible(required_name: str, required_version: str, schema: ProductSchema) -> bool:
    """Same name + same major version → compatible under documented rules."""
    if schema.schema_name != required_name:
        return False
    try:
        required_major = int(str(required_version).split(".")[0])
        actual_major = int(str(schema.schema_version).split(".")[0])
    except (ValueError, IndexError):
        return False
    return required_major == actual_major


def validate_product_record(
    record: dict[str, Any], schema: ProductSchema, *, require_sql: bool
) -> list[str]:
    """Strict validation; returns error strings (empty means valid).

    ``require_sql`` reflects the product profile: eval products withhold
    targets, so ``sql`` must be absent-or-null rather than present.
    """
    errors: list[str] = []
    expected = {f.product_field for f in schema.fields if f.product_field}
    if not require_sql:
        expected.discard("sql")
    for field in sorted(expected):
        if field not in record:
            errors.append(f"missing required field: {field}")
    if require_sql and not record.get("sql"):
        errors.append("missing required target: sql")
    if "task_id" in record and (not isinstance(record["task_id"], str) or not record["task_id"]):
        errors.append("task_id must be a non-empty string")
    if "sql" in record and record["sql"] is not None and not isinstance(record["sql"], str):
        errors.append("sql must be a string or null")
    if "difficulty" in record and record["difficulty"] not in (1, 2, 3, 4, 5):
        errors.append("difficulty must be an integer 1-5")
    dialect = record.get("dialect", schema.dialect)
    if dialect != schema.dialect:
        errors.append(f"dialect mismatch: {dialect!r} != {schema.dialect!r}")
    return errors


def assert_supported_schema(schema: ProductSchema) -> None:
    """Fail clearly on unsupported schema versions (§38)."""
    canonical = canonical_schema()
    if not schema_compatible(canonical.schema_name, canonical.schema_version, schema):
        raise ProductConfigError(
            f"unsupported schema {schema.schema_name}/{schema.schema_version}; "
            f"this build supports {canonical.schema_name}/{canonical.schema_version}"
        )
