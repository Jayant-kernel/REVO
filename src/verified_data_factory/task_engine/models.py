"""Pydantic domain models for the Task Engine (Phase 1).

The structured ``TaskInstance`` is the source of truth (ADR-005).
The natural-language instruction is a rendering of it, never the reverse.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Difficulty = Literal[1, 2, 3, 4, 5]

SUPPORTED_DUCKDB_TYPES = frozenset(
    {
        "INTEGER",
        "BIGINT",
        "DOUBLE",
        "VARCHAR",
        "BOOLEAN",
        "DATE",
        "TIMESTAMP",
        "DECIMAL",
    }
)


class ColumnDefinition(BaseModel):
    model_config = {"frozen": True}

    name: str = Field(min_length=1)
    type: str
    nullable: bool = True

    @field_validator("type")
    @classmethod
    def _normalize_type(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in SUPPORTED_DUCKDB_TYPES:
            raise ValueError(f"unsupported DuckDB type: {v!r}")
        return upper


class TableDefinition(BaseModel):
    model_config = {"frozen": True}

    name: str = Field(min_length=1)
    columns: list[ColumnDefinition] = Field(min_length=1)
    row_count: int = Field(ge=0, le=100_000)
    row_kind: str = Field(min_length=1, default="generic")

    @field_validator("columns")
    @classmethod
    def _unique_columns(cls, v: list[ColumnDefinition]) -> list[ColumnDefinition]:
        names = [c.name for c in v]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate column names: {names}")
        return v


class OracleSpec(BaseModel):
    """Metadata describing what future verification needs (Phase 4).

    The Task Engine defines the requirement only; it never implements
    reference-query execution or verdict logic here.
    """

    model_config = {"frozen": True}

    type: str = Field(min_length=1)
    strategy: str = Field(min_length=1)


class FixtureTableMetadata(BaseModel):
    model_config = {"frozen": True}

    row_count: int = Field(ge=0)


class FixtureMetadata(BaseModel):
    model_config = {"frozen": True}

    engine: Literal["duckdb"] = "duckdb"
    seed: int = Field(ge=0)
    generation_version: int = Field(ge=1, default=1)
    tables: dict[str, FixtureTableMetadata]


class GenerationMetadata(BaseModel):
    model_config = {"frozen": True}

    engine_version: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class TaskTemplate(BaseModel):
    """Reusable, versioned task definition loaded from YAML DSL."""

    model_config = {"frozen": True}

    template_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    family: str = Field(min_length=1)
    description: str = Field(min_length=1)
    difficulty: Difficulty
    schema_definition: list[TableDefinition] = Field(min_length=1)
    generation_config: dict[str, Any] = Field(default_factory=dict)
    requirements: dict[str, Any] = Field(default_factory=dict)
    edge_cases: list[str] = Field(default_factory=list)
    oracle_spec: OracleSpec
    instruction_template: str = Field(min_length=1)

    @field_validator("schema_definition")
    @classmethod
    def _unique_tables(cls, v: list[TableDefinition]) -> list[TableDefinition]:
        names = [t.name for t in v]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate table names: {names}")
        return v

    @field_validator("template_id")
    @classmethod
    def _template_id_shape(cls, v: str) -> str:
        if not v.startswith("sql."):
            raise ValueError("template_id must start with 'sql.'")
        if any(ch.isspace() for ch in v):
            raise ValueError("template_id must not contain whitespace")
        return v


class TaskInstance(BaseModel):
    """One concrete, reproducible task instantiation.

    The schema field is stored internally as ``schema_`` to avoid shadowing
    ``BaseModel.schema``; it serializes under the external name ``"schema"``
    (the Phase 1 contract), so JSON/JSONL output is unchanged.
    """

    model_config = {"frozen": True, "populate_by_name": True}

    task_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: int = Field(ge=1)
    seed: int = Field(ge=0)
    family: str = Field(min_length=1)
    difficulty: Difficulty
    instruction: str = Field(min_length=1)
    schema_: list[TableDefinition] = Field(alias="schema", min_length=1)
    tables: dict[str, list[dict[str, Any]]]
    fixture_metadata: FixtureMetadata
    requirements: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    edge_cases: list[str] = Field(default_factory=list)
    oracle_spec: OracleSpec
    generation_metadata: GenerationMetadata
