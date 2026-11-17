"""Compare the recovered legacy generic mapping with the registered SaaS oracle."""
from pathlib import Path

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.oracle_registry import get_oracle

ROOT = Path(__file__).resolve().parent
SQL = (ROOT / "legacy_saas.sql").read_text(encoding="ascii")
task = generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment"), 1)
connection = materialize_duckdb(task.schema_, task.tables)
try:
    legacy_rows = connection.execute(SQL).fetchall()
finally:
    connection.close()
oracle_rows = get_oracle(task.template_id, 1).fn(task.requirements, task.tables).rows
output = [
    "label: legacy generic",
    f"legacy rows: {legacy_rows!r}",
    f"oracle rows: {oracle_rows!r}",
    f"disagreement: {legacy_rows != oracle_rows}",
]
(ROOT / "legacy_vs_oracle.txt").write_text("\n".join(output) + "\n", encoding="ascii")
