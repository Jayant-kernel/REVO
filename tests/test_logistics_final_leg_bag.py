"""Declared final-leg inner joins retain all three input bags."""
from scripts.phase3_diagnostic import _reference_sql
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.oracle_registry import get_oracle


def test_final_leg_nullable_keys_and_empty_populations():
    contract = "sql.joins.logistics_final_leg"
    task = generate_task(load_builtin_registry().get(contract, 1), 94001)
    tables = {"shipments": [{"shipment_id": 1, "delivered_on": "2025-01-01", "final_leg_id": None},
                            {"shipment_id": 2, "delivered_on": None, "final_leg_id": 10}],
              "legs": [{"leg_id": 10, "carrier_id": None, "depot": "unmatched"}],
              "carriers": []}
    assert get_oracle(contract, 1).fn(task.requirements, tables).rows == []
    assert get_oracle(contract, 1).fn(task.requirements, {name: [] for name in tables}).rows == []


def test_final_leg_preserves_duplicate_shipments_legs_and_carriers():
    contract = "sql.joins.logistics_final_leg"
    task = generate_task(load_builtin_registry().get(contract, 1), 94001)
    shipment = {"shipment_id": 7, "delivered_on": "2025-01-01", "final_leg_id": 10}
    leg = {"leg_id": 10, "carrier_id": 20, "depot": "declared"}
    carrier = {"carrier_id": 20, "carrier_name": "carrier"}
    tables = {"shipments": [shipment, dict(shipment)], "legs": [leg, dict(leg)],
              "carriers": [carrier, dict(carrier)]}
    connection = materialize_duckdb(task.schema_, tables)
    try:
        cursor = connection.execute(_reference_sql()[contract])
        columns = cursor.description
        actual = [list(row) for row in cursor.fetchall()]
        expected = get_oracle(contract, 1).fn(task.requirements, tables)
        assert len(actual) == 8
        assert compare(expected, [column[0] for column in columns], actual,
                       column_types=[str(column[1]) for column in columns]).match
    finally:
        connection.close()
