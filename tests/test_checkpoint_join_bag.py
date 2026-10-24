"""Undeclared key uniqueness cannot erase SQL inner-join row multiplicity."""
from scripts.phase3_diagnostic import _reference_sql
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.oracle_registry import get_oracle


def test_paid_invoice_join_preserves_both_input_bags():
    contract = "sql.joins.saas_paid_invoices"
    task = generate_task(load_builtin_registry().get(contract, 1), 94001)
    account = {"account_id": 1, "account_name": "same", "account_status": "active"}
    invoice = {"invoice_id": 7, "account_id": 1, "issued_on": "2025-01-01",
               "amount_cents": -1, "invoice_status": "paid"}
    tables = {"accounts": [account, dict(account)], "invoices": [invoice, dict(invoice)]}
    connection = materialize_duckdb(task.schema_, tables)
    try:
        cursor = connection.execute(_reference_sql()[contract])
        columns = cursor.description
        actual = [list(row) for row in cursor.fetchall()]
        expected = get_oracle(contract, 1).fn(task.requirements, tables)
        assert len(actual) == 4
        assert compare(expected, [column[0] for column in columns], actual,
                       column_types=[str(column[1]) for column in columns]).match
    finally:
        connection.close()
