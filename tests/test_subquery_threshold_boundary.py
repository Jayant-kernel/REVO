from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb


def test_v2_subquery_fixture_discriminates_threshold_mutant() -> None:
    template = load_builtin_registry().get("sql.subqueries.exists", 2)
    for seed in (1, 94001, 99999):
        task = generate_task(template, seed)
        orders = task.tables["orders"]
        customers = task.tables["customers"]
        correct = {
            order["customer_id"]
            for order in orders
            if order["status"] == "completed"
            and order["order_date"][:4] == "2025"
            and order["amount"] > 500
        }
        mutant = {
            order["customer_id"]
            for order in orders
            if order["status"] == "completed"
            and order["order_date"][:4] == "2025"
            and order["amount"] > 0
        }
        assert mutant - correct
        assert mutant - correct <= {row["customer_id"] for row in customers}
        assert task.template_version == 2
        connection = materialize_duckdb(task.schema_, task.tables)
        try:
            query = (
                "SELECT c.customer_id FROM customers c WHERE EXISTS ("
                "SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id "
                "AND o.status = 'completed' AND o.order_date >= '2025-01-01' "
                "AND o.order_date < '2026-01-01' AND o.amount > 500)"
            )
            actual_correct = {row[0] for row in connection.execute(query).fetchall()}
            actual_mutant = {
                row[0]
                for row in connection.execute(
                    query.replace("amount > 500", "amount > 0")
                ).fetchall()
            }
            assert actual_correct == correct
            assert actual_mutant == mutant
            assert actual_mutant != actual_correct
        finally:
            connection.close()
