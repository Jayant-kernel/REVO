"""EXISTS returns customer-row bags; orphan orders cannot invent customer rows."""
from copy import deepcopy

from scripts.phase3_diagnostic import _reference_sql
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.oracle_registry import get_oracle


def test_orphan_qualifying_order_is_ignored_and_customer_multiplicity_preserved():
    task = generate_task(load_builtin_registry().get("sql.subqueries.exists", 1), 94001)
    customer = {**deepcopy(task.tables["customers"][0]), "customer_id": 1, "name": "present"}
    order = {**deepcopy(task.tables["orders"][0]), "order_id": 1, "customer_id": 1,
             "order_date": "2025-01-01", "amount": 501.0, "status": "completed"}
    tables = {"customers": [customer, deepcopy(customer)],
              "orders": [order, {**order, "order_id": 2, "customer_id": 999}]}
    connection = materialize_duckdb(task.schema_, tables)
    try:
        observed = [list(row) for row in connection.execute(_reference_sql()[task.template_id]).fetchall()]
    finally:
        connection.close()
    assert observed == [[1, "present"], [1, "present"]]
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
    assert expected.rows == observed
