"""Canonical database contents for hidden-fixture diversity checks."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from .fixtures import materialize_duckdb
from .models import FixtureTableMetadata, TaskInstance
from .validation import validate_task

HIDDEN_FIXTURE_VERSION = "2.0-content"


def diverse_hidden_tables(task: TaskInstance, seed: int, variant: int) -> dict[str, list[dict[str, Any]]]:
    """Disjoint valid frames, or legal graph/value variation for legacy profiles."""
    from ..verification.qualification.delivery_profiles import get_profile

    profile = get_profile(task.template_id, task.template_version)
    if profile is not None:
        followup_tables: dict[str, list[dict[str, Any]]] = profile.fixture(seed, variant)
        return followup_tables
    if (task.template_id, task.template_version) == ("sql.dedup.lowest_quote", 1):
        from ..verification.qualification.lowest_quote_profile import fixture

        return fixture(seed, variant)
    id_values = [abs(value) for rows in task.tables.values() for row in rows
                 for name, value in row.items() if (name == "id" or name.endswith("_id"))
                 and isinstance(value, int) and not isinstance(value, bool)]
    maximum = max(id_values, default=1)
    stride = 2 * maximum + 1
    copies = variant
    capacity = (2**31 - 1 - maximum) // stride - copies - 1
    if capacity < 1:
        raise ValueError("cannot safely vary IDs inside the declared integer domain")
    anchor = 1 + seed % capacity
    delta = timedelta(days=seed % 15 - 7)
    factor = variant + 1
    result: dict[str, list[dict[str, Any]]] = {}
    monetary = {"amount", "amount_cents", "price", "mrr_cents", "header_total_cents", "unit_price_cents"}
    for table in task.schema_:
        original = task.tables[table.name]
        has_ids = any((c.name == "id" or c.name.endswith("_id")) and c.type == "INTEGER" for c in table.columns)
        produced = []
        for copy in range(copies if has_ids else 1):
            offset = (anchor + copy) * stride
            for row in original:
                fresh = dict(row)
                for column in table.columns:
                    name, value = column.name, row[column.name]
                    if value is None:
                        continue
                    if (name == "id" or name.endswith("_id")) and column.type == "INTEGER":
                        fresh[name] = int(value) + offset
                    elif name == "group_key" and column.type == "VARCHAR":
                        fresh[name] = f"{value}|hidden-{seed}-{copy}"
                    elif name in monetary and column.type in {"INTEGER", "DOUBLE", "DECIMAL"}:
                        scaled = Decimal(str(value)) * factor
                        fresh[name] = int(scaled) if column.type == "INTEGER" else float(scaled)
                    elif column.type == "DATE":
                        fresh[name] = (date.fromisoformat(str(value)) + delta).isoformat()
                    elif column.type == "TIMESTAMP":
                        fresh[name] = (datetime.fromisoformat(str(value)) + delta).isoformat(sep=" ")
                produced.append(fresh)
        ledger_columns = {"entity_id", "group_key", "occurred_at", "sequence"}
        if ledger_columns <= {c.name for c in table.columns} and variant == 2:
            entities: dict[Any, list[dict[str, Any]]] = {}
            for row in produced:
                entities.setdefault(row["entity_id"], []).append(row)
            for rows in entities.values():
                if len({r["sequence"] for r in rows}) == len(rows):
                    for row in rows:
                        year = str(row["occurred_at"])[:4]
                        row["occurred_at"] = f"{year}-06-15 12:00:00"
        result[table.name] = produced
    # Validate the full generated shape and declared cross-table relationships.
    metadata = task.fixture_metadata.model_copy(update={
        "tables": {name: FixtureTableMetadata(row_count=len(rows)) for name, rows in result.items()}
    })
    validate_task(task.model_copy(update={"tables": result, "fixture_metadata": metadata}))
    return result


def fixture_fingerprint(task: TaskInstance, tables: dict[str, list[dict[str, Any]]]) -> str:
    """Ignore insertion order, preserve multiplicity and database cell semantics."""
    connection = materialize_duckdb(task.schema_, tables)
    try:
        return materialized_fixture_fingerprint(task, connection)
    finally:
        connection.close()


def materialized_fixture_fingerprint(task: TaskInstance, connection: Any) -> str:
    """The same fingerprint algorithm on an already materialized fixture database."""
    canonical = {}
    for table in task.schema_:
        name = table.name.replace('"', '""')
        cursor = connection.execute(f'SELECT * FROM "{name}"')
        canonical[table.name] = {"types": [str(c[1]) for c in cursor.description],
                                 "rows": sorted(json.dumps(list(row), default=str, sort_keys=True)
                                                for row in cursor.fetchall())}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def materialized_fixture_tables(task: TaskInstance, connection: Any) -> dict[str, list[dict[str, Any]]]:
    """Read actual typed cells for oracle evaluation from the fixture database."""
    tables = {}
    for table in task.schema_:
        name = table.name.replace('"', '""')
        cursor = connection.execute(f'SELECT * FROM "{name}"')
        columns = [column[0] for column in cursor.description]
        tables[table.name] = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    return tables
