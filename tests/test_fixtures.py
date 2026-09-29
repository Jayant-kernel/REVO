"""Fixture tests: materialization, schema fidelity, determinism, relationships."""

from verified_data_factory.task_engine import (
    ddl_for_schema,
    generate_task,
    materialize_duckdb,
)


def test_database_creation_and_tables(registry):
    template = registry.get("sql.joins.multi")
    task = generate_task(template, seed=201)
    con = materialize_duckdb(task.schema_, task.tables)
    try:
        for table in task.schema_:
            count = con.execute(f'SELECT COUNT(*) FROM "{table.name}"').fetchone()[0]
            assert count == task.fixture_metadata.tables[table.name].row_count
            assert count == len(task.tables[table.name])
    finally:
        con.close()


def test_correct_columns_and_types(registry):
    template = registry.get("sql.joins.simple")
    task = generate_task(template, seed=101)
    con = materialize_duckdb(task.schema_, task.tables)
    try:
        for table in task.schema_:
            info = con.execute(f"DESCRIBE {table.name}").fetchall()
            got = {row[0] for row in info}
            want = {c.name for c in table.columns}
            assert got == want
    finally:
        con.close()


def test_ddl_renders_for_all_templates(registry):
    for template in registry.list():
        assert ddl_for_schema(template.schema_definition)


def test_relationships_are_valid(registry):
    """Every FK-like value must reference an existing parent row."""
    for template in registry.list():
        task = generate_task(template, seed=7)
        tables = task.tables
        if "customers" in tables and "orders" in tables:
            valid = {r["customer_id"] for r in tables["customers"]}
            assert valid
            for row in tables["orders"]:
                assert row["customer_id"] in valid
        if "orders" in tables and "order_items" in tables:
            valid_orders = {r["order_id"] for r in tables["orders"]}
            for row in tables["order_items"]:
                assert row["order_id"] in valid_orders


def test_edge_cases_recorded(registry):
    template = registry.get("sql.retention.30_day")
    task = generate_task(template, seed=901)
    assert set(task.edge_cases) == set(template.edge_cases)


def test_fixtures_are_deterministic(registry):
    template = registry.get("sql.temporal.monthly")
    a = generate_task(template, seed=701)
    b = generate_task(template, seed=701)
    assert a.tables == b.tables
    assert a.fixture_metadata == b.fixture_metadata


def test_retention_fixture_materializes_day_30_and_day_31(registry):
    task = generate_task(registry.get("sql.retention.30_day"), seed=901)
    customer = task.tables["customers"][0]
    signup = str(customer["signup_date"])
    events = [
        event
        for event in task.tables["events"]
        if event["customer_id"] == customer["customer_id"]
        and event["event_type"] == "purchase"
    ]
    from datetime import date, timedelta

    start = date.fromisoformat(signup)
    assert any(str(e["event_time"]).startswith(str(start + timedelta(days=30))) for e in events)
    assert any(str(e["event_time"]).startswith(str(start + timedelta(days=31))) for e in events)


def test_temporal_fixture_has_final_day_timestamp(registry):
    task = generate_task(registry.get("sql.temporal.monthly"), seed=701)
    assert any(
        str(event["event_time"]).startswith("2025-03-31 23:59:59")
        for event in task.tables["events"]
    )


def test_funnel_fixture_materializes_event_id_tie_break(registry):
    task = generate_task(registry.get("sql.funnel.completion"), seed=1001)
    customer_id = task.tables["customers"][0]["customer_id"]
    events = sorted(
        (e for e in task.tables["events"] if e["customer_id"] == customer_id),
        key=lambda e: e["event_id"],
    )
    assert [e["event_type"] for e in events] == ["view", "add_to_cart", "checkout", "purchase"]
    assert len({e["event_time"] for e in events}) == 1
