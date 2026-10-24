"""Boundary semantics end-to-end (§21-25): crafted fixtures, real Docker.

Each test stages hand-built rows through the REAL Phase 3 sandbox
(``execute_on_rows``) and compares against the REAL oracle with the REAL
comparator. Any disagreement is a defect to investigate — never smoothed
over. Covers: temporal boundaries, window partitioning/ties/totals,
retention day 0/29/30/31, dedup winner/tie-break, funnel order/repeat/
missing/cross-session behavior.
"""

import pytest

from tests.verify_sql_samples import CORRECT_SQL
from tests.verify_testkit import make_candidate, make_task
from verified_data_factory.sandbox import DockerRunner, SandboxConfig, SandboxExecutor
from verified_data_factory.verification import compare, get_oracle

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

from tests.integration.sandbox.test_docker_available import requires_docker

_SANDBOX = SandboxConfig(timeout_seconds=60)


def _run_and_match(template_id, tables, sql):
    """Real sandbox execution on crafted rows vs real oracle. Returns both."""
    task = make_task(template_id)
    candidate = make_candidate(task, sql)
    execution = SandboxExecutor(_SANDBOX, DockerRunner(_SANDBOX)).execute_on_rows(
        task, candidate, tables
    )
    assert execution.status == "SUCCEEDED", (template_id, execution.failure)
    assert execution.result_data is not None
    entry = get_oracle(task.template_id, task.template_version)
    expected = entry.fn(dict(task.requirements), tables)
    comparison = compare(
        expected,
        [c.name for c in execution.result_data.columns],
        execution.result_data.rows,
        column_types=[c.type for c in execution.result_data.columns],
    )
    return comparison, expected


def _customers(ids, signup="2025-01-01"):
    return [
        {"customer_id": i, "name": f"C{i}", "country": "IN", "signup_date": signup} for i in ids
    ]


@requires_docker
def test_retention_day_boundaries():
    tables = {
        "customers": _customers([1, 2, 3, 4, 5]),
        "events": [
            {
                "event_id": 1,
                "customer_id": 1,
                "event_type": "purchase",
                "event_time": "2025-01-01 10:00:00",
            },
            {
                "event_id": 2,
                "customer_id": 2,
                "event_type": "purchase",
                "event_time": "2025-01-30 10:00:00",
            },
            {
                "event_id": 3,
                "customer_id": 3,
                "event_type": "purchase",
                "event_time": "2025-01-31 10:00:00",
            },
            {
                "event_id": 4,
                "customer_id": 4,
                "event_type": "purchase",
                "event_time": "2025-02-01 10:00:00",
            },
        ],
    }
    comparison, expected = _run_and_match(
        "sql.retention.30_day", tables, CORRECT_SQL["sql.retention.30_day"]
    )
    assert comparison.match, comparison.differences
    assert expected.rows == [[1, True], [2, True], [3, True], [4, False], [5, False]]


@requires_docker
def test_dedup_winner_and_tiebreak():
    tables = {
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
                "event_type": "click",
                "event_time": "2025-01-05 10:00:00",
            },
            {
                "event_id": 3,
                "customer_id": 1,
                "event_type": "click",
                "event_time": "2025-01-05 10:00:00",
            },
            {
                "event_id": 4,
                "customer_id": 2,
                "event_type": "view",
                "event_time": "2025-02-01 10:00:00",
            },
        ]
    }
    comparison, expected = _run_and_match(
        "sql.dedup.latest", tables, CORRECT_SQL["sql.dedup.latest"]
    )
    assert comparison.match, comparison.differences
    assert expected.rows == [
        [1, "click", "2025-01-05 10:00:00"],
        [2, "view", "2025-02-01 10:00:00"],
    ]


@requires_docker
def test_funnel_order_repeat_missing_and_cross_session():
    tables = {
        "customers": _customers([1, 2, 3, 4, 5], signup="2024-01-01"),
        "events": [
            # customer 1: perfect order, same session
            {
                "event_id": 1,
                "customer_id": 1,
                "event_type": "view",
                "event_time": "2025-01-01 10:00:00",
            },
            {
                "event_id": 2,
                "customer_id": 1,
                "event_type": "add_to_cart",
                "event_time": "2025-01-01 10:05:00",
            },
            {
                "event_id": 3,
                "customer_id": 1,
                "event_type": "checkout",
                "event_time": "2025-01-01 10:10:00",
            },
            {
                "event_id": 4,
                "customer_id": 1,
                "event_type": "purchase",
                "event_time": "2025-01-01 10:15:00",
            },
            # customer 2: wrong order (purchase first) -> partial
            {
                "event_id": 5,
                "customer_id": 2,
                "event_type": "purchase",
                "event_time": "2025-01-01 09:00:00",
            },
            {
                "event_id": 6,
                "customer_id": 2,
                "event_type": "view",
                "event_time": "2025-01-01 10:00:00",
            },
            {
                "event_id": 7,
                "customer_id": 2,
                "event_type": "add_to_cart",
                "event_time": "2025-01-01 10:05:00",
            },
            # customer 3: missing checkout -> partial
            {
                "event_id": 8,
                "customer_id": 3,
                "event_type": "view",
                "event_time": "2025-01-01 10:00:00",
            },
            {
                "event_id": 9,
                "customer_id": 3,
                "event_type": "add_to_cart",
                "event_time": "2025-01-01 10:05:00",
            },
            {
                "event_id": 10,
                "customer_id": 3,
                "event_type": "purchase",
                "event_time": "2025-01-01 10:10:00",
            },
            # customer 4: repeats + cross-session gaps -> still complete
            {
                "event_id": 11,
                "customer_id": 4,
                "event_type": "view",
                "event_time": "2025-01-01 10:00:00",
            },
            {
                "event_id": 12,
                "customer_id": 4,
                "event_type": "view",
                "event_time": "2025-01-01 12:00:00",
            },
            {
                "event_id": 13,
                "customer_id": 4,
                "event_type": "add_to_cart",
                "event_time": "2025-01-02 10:00:00",
            },
            {
                "event_id": 14,
                "customer_id": 4,
                "event_type": "checkout",
                "event_time": "2025-01-03 10:00:00",
            },
            {
                "event_id": 15,
                "customer_id": 4,
                "event_type": "purchase",
                "event_time": "2025-01-04 10:00:00",
            },
        ],
    }
    comparison, expected = _run_and_match(
        "sql.funnel.completion", tables, CORRECT_SQL["sql.funnel.completion"]
    )
    assert comparison.match, comparison.differences
    assert expected.rows == [
        [1, 4, True],
        [2, 2, False],
        [3, 2, False],
        [4, 4, True],
        [5, 0, False],
    ]


@requires_docker
def test_temporal_window_boundaries_and_months():
    tables = {
        "orders": [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-01-01",
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
                "order_date": "2024-12-31",
                "amount": 1.0,
                "status": "completed",
            },
            {
                "order_id": 4,
                "customer_id": 1,
                "order_date": "2025-04-01",
                "amount": 1.0,
                "status": "completed",
            },
            {
                "order_id": 5,
                "customer_id": 1,
                "order_date": "2025-01-31",
                "amount": 1.0,
                "status": "completed",
            },
            {
                "order_id": 6,
                "customer_id": 1,
                "order_date": "2025-02-01",
                "amount": 1.0,
                "status": "completed",
            },
        ],
        "events": [
            {
                "event_id": 1,
                "customer_id": 1,
                "event_type": "view",
                "event_time": "2025-01-01 00:00:00",
            },
            {
                "event_id": 2,
                "customer_id": 1,
                "event_type": "view",
                "event_time": "2025-03-31 23:59:59",
            },
            {
                "event_id": 3,
                "customer_id": 1,
                "event_type": "view",
                "event_time": "2025-04-01 00:00:00",
            },
        ],
    }
    comparison, expected = _run_and_match(
        "sql.temporal.monthly", tables, CORRECT_SQL["sql.temporal.monthly"]
    )
    assert comparison.match, comparison.differences
    assert expected.rows == [["2025-01", 2, 1], ["2025-02", 1, 0], ["2025-03", 1, 1]]


@requires_docker
def test_window_partition_ties_and_running_totals():
    tables = {
        "customers": _customers([1, 2]),
        "orders": [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-01-01",
                "amount": 100.0,
                "status": "completed",
            },
            {
                "order_id": 2,
                "customer_id": 1,
                "order_date": "2025-01-02",
                "amount": 100.0,
                "status": "completed",
            },
            {
                "order_id": 3,
                "customer_id": 1,
                "order_date": "2025-01-03",
                "amount": 50.0,
                "status": "completed",
            },
            {
                "order_id": 4,
                "customer_id": 2,
                "order_date": "2025-01-01",
                "amount": 7.0,
                "status": "completed",
            },
        ],
    }
    comparison, expected = _run_and_match(
        "sql.windows.ranked", tables, CORRECT_SQL["sql.windows.ranked"]
    )
    assert comparison.match, comparison.differences
    # Ties share RANK with gaps; running totals accumulate in date order.
    assert expected.rows == [
        [1, 1, "2025-01-01", 1, 100.0, None],
        [1, 2, "2025-01-02", 1, 200.0, 100.0],
        [1, 3, "2025-01-03", 3, 250.0, 100.0],
        [2, 4, "2025-01-01", 1, 7.0, None],
    ]
