"""Compare reconstructed legacy SQL with the SaaS oracle using project semantics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.oracle_registry import get_oracle

ROOT = Path(__file__).resolve().parent


def json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return {"type": type(value).__name__, "repr": repr(value)}


def main() -> None:
    sql = (ROOT / "legacy_saas.sql").read_text(encoding="ascii")
    task = generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment"), 1)
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, task.tables)
    connection = materialize_duckdb(task.schema_, task.tables)
    try:
        cursor = connection.execute(sql)
        columns = [column[0] for column in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
    finally:
        connection.close()
    result = compare(expected, columns, rows)
    output = {
        "label": "reconstructed legacy-generic formulation",
        "actual_columns": columns,
        "actual_rows": [[json_value(value) for value in row] for row in rows],
        "oracle_columns": expected.columns,
        "oracle_rows": [[json_value(value) for value in row] for row in expected.rows],
        "comparison_match": result.match,
        "comparison_notes": result.notes,
        "provenance": "Historical SaaS assignment was not independently recovered.",
    }
    (ROOT / "legacy_vs_oracle_normalized.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
