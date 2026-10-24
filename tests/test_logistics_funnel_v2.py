"""Focused verification for bounded-consecutive logistics funnel v2."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.oracle_registry import get_oracle

LOGISTICS_V2_WINDOW_SQL = """WITH scoped AS (
    SELECT * FROM parcel_scans
    WHERE EXTRACT(YEAR FROM occurred_at) = 2025
      AND status IN ('accepted', 'sorted', 'dispatched', 'delivered')
), sequenced AS (
    SELECT *,
      LEAD(status, 1) OVER parcel_order AS next_status_1,
      LEAD(status, 2) OVER parcel_order AS next_status_2,
      LEAD(status, 3) OVER parcel_order AS next_status_3,
      LEAD(occurred_at, 1) OVER parcel_order AS next_at_1,
      LEAD(occurred_at, 2) OVER parcel_order AS next_at_2,
      LEAD(occurred_at, 3) OVER parcel_order AS next_at_3,
      LEAD(amount, 3) OVER parcel_order AS delivered_amount
    FROM scoped WINDOW parcel_order AS (PARTITION BY entity_id ORDER BY occurred_at, sequence)
), candidates AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY occurred_at, sequence) AS candidate_rank
    FROM sequenced
    WHERE status = 'accepted' AND next_status_1 = 'sorted'
      AND next_status_2 = 'dispatched' AND next_status_3 = 'delivered'
      AND next_at_1 - occurred_at <= INTERVAL 60 MINUTE
      AND next_at_2 - next_at_1 <= INTERVAL 60 MINUTE
      AND next_at_3 - next_at_2 <= INTERVAL 60 MINUTE
), depots AS (SELECT DISTINCT group_key FROM scoped)
SELECT d.group_key, COALESCE(SUM(c.delivered_amount), 0) AS total_amount
FROM depots d LEFT JOIN candidates c ON c.group_key = d.group_key AND c.candidate_rank = 1
GROUP BY d.group_key ORDER BY d.group_key ASC"""

LOGISTICS_V2_SELF_JOIN_SQL = """WITH scoped AS (
    SELECT * FROM parcel_scans
    WHERE EXTRACT(YEAR FROM occurred_at) = 2025
      AND status IN ('accepted', 'sorted', 'dispatched', 'delivered')
), candidates AS (
    SELECT a.entity_id, a.group_key, d.amount, a.occurred_at, a.sequence,
      ROW_NUMBER() OVER (PARTITION BY a.entity_id ORDER BY a.occurred_at, a.sequence) AS candidate_rank
    FROM scoped a JOIN scoped b ON b.entity_id = a.entity_id
      AND (b.occurred_at, b.sequence) > (a.occurred_at, a.sequence)
    JOIN scoped c ON c.entity_id = a.entity_id
      AND (c.occurred_at, c.sequence) > (b.occurred_at, b.sequence)
    JOIN scoped d ON d.entity_id = a.entity_id
      AND (d.occurred_at, d.sequence) > (c.occurred_at, c.sequence)
    WHERE a.status = 'accepted' AND b.status = 'sorted'
      AND c.status = 'dispatched' AND d.status = 'delivered'
      AND NOT EXISTS (SELECT 1 FROM scoped x WHERE x.entity_id = a.entity_id
        AND (x.occurred_at, x.sequence) > (a.occurred_at, a.sequence)
        AND (x.occurred_at, x.sequence) < (b.occurred_at, b.sequence))
      AND NOT EXISTS (SELECT 1 FROM scoped x WHERE x.entity_id = a.entity_id
        AND (x.occurred_at, x.sequence) > (b.occurred_at, b.sequence)
        AND (x.occurred_at, x.sequence) < (c.occurred_at, c.sequence))
      AND NOT EXISTS (SELECT 1 FROM scoped x WHERE x.entity_id = a.entity_id
        AND (x.occurred_at, x.sequence) > (c.occurred_at, c.sequence)
        AND (x.occurred_at, x.sequence) < (d.occurred_at, d.sequence))
      AND b.occurred_at - a.occurred_at <= INTERVAL 60 MINUTE
      AND c.occurred_at - b.occurred_at <= INTERVAL 60 MINUTE
      AND d.occurred_at - c.occurred_at <= INTERVAL 60 MINUTE
), depots AS (SELECT DISTINCT group_key FROM scoped)
SELECT d.group_key, COALESCE(SUM(c.amount), 0) AS total_amount
FROM depots d LEFT JOIN candidates c ON c.group_key = d.group_key AND c.candidate_rank = 1
GROUP BY d.group_key ORDER BY d.group_key ASC"""


def _row(record_id: int, status: str, sequence: int, *, entity: int = 1, group: str = "north", amount: int = 0, occurred_at: str | None = None) -> dict[str, object]:
    timestamp = f"2025-01-01 {sequence // 6:02d}:{sequence % 6 * 10:02d}:00"
    return {"record_id": record_id, "entity_id": entity, "group_key": group, "occurred_at": occurred_at or timestamp, "status": status, "amount": amount, "sequence": sequence}


def _task() -> Any:
    return generate_task(load_builtin_registry().get("sql.funnel.logistics_parcel_delivery", 2), 1)


def _evaluate(rows: list[dict[str, object]]) -> list[list[object]]:
    task = _task()
    return get_oracle(task.template_id, task.template_version).fn(task.requirements, {"parcel_scans": rows}).rows


def _execute(tables: dict[str, list[dict[str, object]]], sql: str) -> list[list[object]]:
    connection = materialize_duckdb(_task().schema_, tables)
    try:
        return [[str(value) if isinstance(value, (date, datetime)) else value for value in row] for row in connection.execute(sql).fetchall()]
    finally:
        connection.close()


def test_same_timestamp_uses_sequence() -> None:
    rows = [_row(4, "delivered", 4, amount=7, occurred_at="2025-01-01 00:00:00"), _row(3, "dispatched", 3, occurred_at="2025-01-01 00:00:00"), _row(2, "sorted", 2, occurred_at="2025-01-01 00:00:00"), _row(1, "accepted", 1, occurred_at="2025-01-01 00:00:00")]
    assert _evaluate(rows) == [["north", 7]]


def test_non_consecutive_in_scope_scan_interrupts_then_later_chain_counts() -> None:
    rows = [_row(1, "accepted", 1), _row(2, "sorted", 2), _row(3, "accepted", 3), _row(4, "sorted", 4), _row(5, "dispatched", 5), _row(6, "delivered", 6, amount=8)]
    assert _evaluate(rows) == [["north", 8]]


def test_gap_at_boundary_counts_and_gap_over_boundary_does_not() -> None:
    boundary = [_row(1, "accepted", 1, occurred_at="2025-01-01 00:00:00"), _row(2, "sorted", 2, occurred_at="2025-01-01 01:00:00"), _row(3, "dispatched", 3, occurred_at="2025-01-01 02:00:00"), _row(4, "delivered", 4, amount=9, occurred_at="2025-01-01 03:00:00")]
    over = [dict(row) for row in boundary]
    over[1]["occurred_at"] = "2025-01-01 01:01:00"
    assert _evaluate(boundary) == [["north", 9]]
    assert _evaluate(over) == [["north", 0]]


def test_first_complete_chain_per_parcel_is_used() -> None:
    rows = [_row(1, "accepted", 1), _row(2, "sorted", 2), _row(3, "dispatched", 3), _row(4, "delivered", 4, amount=7), _row(5, "accepted", 5), _row(6, "sorted", 6), _row(7, "dispatched", 7), _row(8, "delivered", 8, amount=99)]
    assert _evaluate(rows) == [["north", 7]]


def test_year_and_out_of_scope_rows_do_not_create_depot() -> None:
    assert _evaluate([_row(1, "accepted", 1, occurred_at="2024-12-31 23:59:00"), _row(2, "exception", 2)]) == []


def test_duplicate_order_key_and_group_change_are_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="unique occurred_at and sequence"):
        _evaluate([_row(1, "accepted", 1), _row(2, "sorted", 1)])
    with pytest.raises(ValueError, match="one group_key"):
        _evaluate([_row(1, "accepted", 1), _row(2, "sorted", 2, group="south")])


def test_named_sql_formulations_agree_with_oracle_on_fixture_and_adversarial() -> None:
    from verified_data_factory.task_engine.business_fixtures import business_tables
    from verified_data_factory.verification.adversarial import independent_adversarial_tables

    task = _task()
    for tables in (business_tables("logistics_parcel_delivery_v2", 1), independent_adversarial_tables(task)):
        assert tables is not None
        expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables).rows
        assert _execute(tables, LOGISTICS_V2_WINDOW_SQL) == expected
        assert _execute(tables, LOGISTICS_V2_SELF_JOIN_SQL) == expected
