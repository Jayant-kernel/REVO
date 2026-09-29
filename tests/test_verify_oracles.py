"""Oracle tests: hand-built fixtures, hand-computed expectations.

No candidates, no execution, no models — pure oracle semantics against
``docs/task-semantics.md``. Registry coverage + strategy consistency included.
"""

import pytest

from verified_data_factory.task_engine import load_builtin_registry
from verified_data_factory.verification import (
    get_oracle,
    known_templates,
)
from verified_data_factory.verification import oracle as O
from verified_data_factory.verification.errors import OracleUnknownError


def _req(**overrides):
    base = {"output_columns": []}
    base.update(overrides)
    return base


def test_simple_joins_oracle():
    req = _req(
        output_columns=["customers.customer_id", "total_revenue"],
        year=2025,
        status_filter="completed",
    )
    tables = {
        "customers": [
            {"customer_id": 1, "name": "A"},
            {"customer_id": 2, "name": "B"},
            {"customer_id": 3, "name": "C"},
        ],
        "orders": [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-02-01",
                "amount": 10.0,
                "status": "completed",
            },
            {
                "order_id": 2,
                "customer_id": 1,
                "order_date": "2025-03-01",
                "amount": 20.0,
                "status": "completed",
            },
            {
                "order_id": 3,
                "customer_id": 2,
                "order_date": "2025-01-01",
                "amount": 5.0,
                "status": "pending",
            },
            {
                "order_id": 4,
                "customer_id": 2,
                "order_date": "2024-12-31",
                "amount": 99.0,
                "status": "completed",
            },
        ],
    }
    exp = O.oracle_simple_joins(req, tables)
    assert exp.columns == ["customer_id", "total_revenue"]
    assert exp.rows == [[1, 30.0]]  # only completed 2025; customer 3 excluded
    assert exp.order.keys == [("total_revenue", "desc")]


def test_multi_joins_oracle():
    req = _req(
        output_columns=["customers.customer_id", "products.category", "line_revenue"],
        year=2025,
        status_filter="completed",
    )
    tables = {
        "orders": [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-01-05",
                "amount": 0.0,
                "status": "completed",
            },
            {
                "order_id": 2,
                "customer_id": 1,
                "order_date": "2025-01-06",
                "amount": 0.0,
                "status": "cancelled",
            },
        ],
        "products": [
            {"product_id": 1, "name": "P", "category": "books", "price": 10.0},
            {"product_id": 2, "name": "Q", "category": "toys", "price": 7.5},
        ],
        "order_items": [
            {"item_id": 1, "order_id": 1, "product_id": 1, "quantity": 2},
            {"item_id": 2, "order_id": 1, "product_id": 2, "quantity": 1},
            {"item_id": 3, "order_id": 2, "product_id": 1, "quantity": 9},
        ],
    }
    exp = O.oracle_multi_joins(req, tables)
    assert exp.rows == [[1, "books", 20.0], [1, "toys", 7.5]]


def test_aggregation_null_semantics():
    req = _req(
        output_columns=["orders.status", "order_count", "total_amount", "avg_amount"],
        year=2025,
        group_by=["orders.status"],
    )
    tables = {
        "orders": [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-01-01",
                "amount": 10.0,
                "status": "completed",
            },
            {
                "order_id": 2,
                "customer_id": 1,
                "order_date": "2025-01-02",
                "amount": None,
                "status": "completed",
            },
            {
                "order_id": 3,
                "customer_id": 1,
                "order_date": "2025-01-03",
                "amount": 0.0,
                "status": "pending",
            },
        ]
    }
    exp = O.oracle_aggregation(req, tables)
    assert exp.rows == [["completed", 2, 10.0, 10.0], ["pending", 1, 0.0, 0.0]]


def test_aggregation_all_null_avg_is_null():
    req = _req(
        output_columns=["orders.status", "order_count", "total_amount", "avg_amount"],
        year=2025,
        group_by=["orders.status"],
    )
    tables = {
        "orders": [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-01-01",
                "amount": None,
                "status": "completed",
            },
        ]
    }
    exp = O.oracle_aggregation(req, tables)
    # SQL: SUM and AVG over all-NULL inputs are NULL (regression: oracle once emitted 0).
    assert exp.rows == [["completed", 1, None, None]]


def test_cte_top_month_earliest_tiebreak():
    req = _req(
        output_columns=["customers.customer_id", "revenue_month", "monthly_revenue"],
        year=2025,
        status_filter="completed",
    )
    tables = {
        "orders": [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-02-01",
                "amount": 50.0,
                "status": "completed",
            },
            {
                "order_id": 2,
                "customer_id": 1,
                "order_date": "2025-01-01",
                "amount": 50.0,
                "status": "completed",
            },
            {
                "order_id": 3,
                "customer_id": 2,
                "order_date": "2025-03-01",
                "amount": 5.0,
                "status": "pending",
            },
        ]
    }
    exp = O.oracle_cte(req, tables)
    assert exp.rows == [[1, "2025-01", 50.0]]  # tie -> earliest; customer 2 excluded


def test_subqueries_strict_threshold():
    req = _req(
        output_columns=["customers.customer_id", "customers.name"],
        year=2025,
        status_filter="completed",
        min_amount=500,
    )
    tables = {
        "customers": [
            {"customer_id": 1, "name": "A"},
            {"customer_id": 2, "name": "B"},
            {"customer_id": 3, "name": "C"},
        ],
        "orders": [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-01-01",
                "amount": 500.0,
                "status": "completed",
            },
            {
                "order_id": 2,
                "customer_id": 2,
                "order_date": "2025-01-01",
                "amount": 500.01,
                "status": "completed",
            },
        ],
    }
    exp = O.oracle_subqueries(req, tables)
    assert exp.rows == [[2, "B"]]  # exactly-500 excluded (strict); orderless excluded


def test_windows_rank_gaps_and_running_total():
    req = _req(
        output_columns=["customers.customer_id", "orders.order_id", "order_rank", "running_total"],
        year=2025,
        status_filter="completed",
    )
    tables = {
        "orders": [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-01-01",
                "amount": 30.0,
                "status": "completed",
            },
            {
                "order_id": 2,
                "customer_id": 1,
                "order_date": "2025-01-02",
                "amount": 30.0,
                "status": "completed",
            },
            {
                "order_id": 3,
                "customer_id": 1,
                "order_date": "2025-01-03",
                "amount": 10.0,
                "status": "completed",
            },
        ]
    }
    exp = O.oracle_windows(req, tables)
    assert exp.rows == [[1, 1, 1, 30.0], [1, 2, 1, 60.0], [1, 3, 3, 70.0]]


def test_temporal_inclusive_window_present_months_only():
    req = _req(
        output_columns=["activity_month", "order_count", "event_count"],
        year=2025,
        window_start="2025-01-01",
        window_end="2025-03-31",
    )
    tables = {
        "orders": [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-01-15",
                "amount": 1.0,
                "status": "completed",
            },
            {
                "order_id": 2,
                "customer_id": 1,
                "order_date": "2025-03-31",
                "amount": 1.0,
                "status": "completed",
            },
            {
                "order_id": 3,
                "customer_id": 1,
                "order_date": "2025-04-01",
                "amount": 1.0,
                "status": "completed",
            },
        ],
        "events": [
            {
                "event_id": 1,
                "customer_id": 1,
                "event_type": "view",
                "event_time": "2025-02-01 10:00:00",
            },
        ],
    }
    exp = O.oracle_temporal(req, tables)
    assert exp.rows == [["2025-01", 1, 0], ["2025-02", 0, 1], ["2025-03", 1, 0]]


def test_dedup_latest_and_tiebreak():
    req = _req(output_columns=["events.customer_id", "events.event_type", "events.event_time"])
    tables = {
        "events": [
            {
                "event_id": 1,
                "customer_id": 1,
                "event_type": "view",
                "event_time": "2025-01-02 00:00:00",
            },
            {
                "event_id": 2,
                "customer_id": 1,
                "event_type": "click",
                "event_time": "2025-01-02 00:00:00",
            },
            {
                "event_id": 3,
                "customer_id": 1,
                "event_type": "view",
                "event_time": "2025-01-01 00:00:00",
            },
        ]
    }
    exp = O.oracle_dedup(req, tables)
    assert exp.rows == [[1, "click", "2025-01-02 00:00:00"]]  # tie -> highest event_id


def test_retention_boundaries():
    req = _req(
        output_columns=["customers.customer_id", "retained"],
        retention_window_days=30,
        qualifying_event="purchase",
    )
    tables = {
        "customers": [
            {"customer_id": 1, "signup_date": "2025-01-01"},
            {"customer_id": 2, "signup_date": "2025-01-01"},
            {"customer_id": 3, "signup_date": "2025-01-01"},
            {"customer_id": 4, "signup_date": "2025-01-01"},
        ],
        "events": [
            {
                "event_id": 1,
                "customer_id": 1,
                "event_type": "purchase",
                "event_time": "2025-01-31 23:59:59",
            },
            {
                "event_id": 2,
                "customer_id": 2,
                "event_type": "purchase",
                "event_time": "2025-02-01 00:00:00",
            },
            {
                "event_id": 3,
                "customer_id": 3,
                "event_type": "view",
                "event_time": "2025-01-10 00:00:00",
            },
        ],
    }
    exp = O.oracle_retention(req, tables)
    assert exp.rows == [[1, True], [2, False], [3, False], [4, False]]  # day-30 counts, day-31 not


def test_funnel_prefix_and_repeats():
    req = _req(
        output_columns=["customers.customer_id", "max_step_reached", "completed"],
        funnel_steps=["view", "add_to_cart", "checkout", "purchase"],
    )
    tables = {
        "customers": [{"customer_id": 1}, {"customer_id": 2}],
        "events": [
            {
                "event_id": 1,
                "customer_id": 1,
                "event_type": "view",
                "event_time": "2025-01-01 10:00:00",
            },
            {
                "event_id": 2,
                "customer_id": 1,
                "event_type": "checkout",
                "event_time": "2025-01-01 11:00:00",
            },
            {
                "event_id": 3,
                "customer_id": 1,
                "event_type": "add_to_cart",
                "event_time": "2025-01-01 12:00:00",
            },
            {
                "event_id": 4,
                "customer_id": 1,
                "event_type": "checkout",
                "event_time": "2025-01-01 13:00:00",
            },
            {
                "event_id": 5,
                "customer_id": 1,
                "event_type": "purchase",
                "event_time": "2025-01-01 14:00:00",
            },
            {
                "event_id": 6,
                "customer_id": 1,
                "event_type": "view",
                "event_time": "2025-01-01 15:00:00",
            },
        ],
    }
    exp = O.oracle_funnel(req, tables)
    assert exp.rows == [[1, 4, True], [2, 0, False]]


def test_oracle_registry_covers_all_templates():
    registry = load_builtin_registry()
    for template in registry.list():
        entry = get_oracle(template.template_id, template.version)
        assert entry.oracle_version >= 1
        assert entry.strategy == template.oracle_spec.strategy
    # Versioned semantic clarifications keep v1 available for historical runs.
    assert len(known_templates()) == 23


def test_oracle_unknown_raises():
    with pytest.raises(OracleUnknownError):
        get_oracle("sql.nope.missing", 1)
    with pytest.raises(OracleUnknownError):
        get_oracle("sql.joins.simple", 999)


def test_oracles_run_on_real_phase1_fixtures(registry):
    """Every oracle executes cleanly on real generated fixtures (smoke)."""
    from verified_data_factory.task_engine import generate_task

    seeds = {
        "sql.joins.simple": 101,
        "sql.joins.multi": 201,
        "sql.aggregation.grouped": 301,
        "sql.cte.monthly": 401,
        "sql.subqueries.exists": 501,
        "sql.windows.ranked": 601,
        "sql.temporal.monthly": 701,
        "sql.dedup.latest": 801,
        "sql.retention.30_day": 901,
        "sql.funnel.completion": 1001,
    }
    for template in registry.list():
        task = generate_task(template, seeds[template.template_id])
        entry = get_oracle(task.template_id, task.template_version)
        expected = entry.fn(dict(task.requirements), task.tables)
        assert expected.columns
        assert isinstance(expected.rows, list)
