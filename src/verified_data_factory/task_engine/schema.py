"""Schema helpers: DDL generation and DuckDB type mapping (Phase 1)."""

from __future__ import annotations

from .models import TableDefinition

_DUCKDB_DECL: dict[str, str] = {
    "INTEGER": "INTEGER",
    "BIGINT": "BIGINT",
    "DOUBLE": "DOUBLE",
    "VARCHAR": "VARCHAR",
    "BOOLEAN": "BOOLEAN",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP",
    "DECIMAL": "DECIMAL(18, 2)",
}


def ddl_for_table(table: TableDefinition) -> str:
    """Render a ``CREATE TABLE`` statement for a table definition."""
    cols = []
    for col in table.columns:
        decl = _DUCKDB_DECL[col.type]
        null = "" if col.nullable else " NOT NULL"
        cols.append(f'"{col.name}" {decl}{null}')
    return f'CREATE TABLE "{table.name}" ({", ".join(cols)})'


def ddl_for_schema(tables: list[TableDefinition]) -> list[str]:
    """Render DDL for every table, sorted by table name for stability."""
    return [ddl_for_table(t) for t in sorted(tables, key=lambda t: t.name)]
