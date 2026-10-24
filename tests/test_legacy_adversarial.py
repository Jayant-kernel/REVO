"""Base legacy templates must have independent adversarial runtime fixtures.

Phase 1 of the technical hardening: the ten base templates (one per
family) previously had no independent adversarial case, so selected rows
failed the premium screen's ``independent adversarial runtime case is
missing or did not pass`` gate. Each fixture here is separately authored
and must be executable, oracle-consistent, and discriminating.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.adversarial import independent_adversarial_tables
from verified_data_factory.verification.oracle_registry import get_oracle

BASE_TEMPLATES = [
    "sql.joins.simple",
    "sql.joins.multi",
    "sql.aggregation.grouped",
    "sql.cte.monthly",
    "sql.subqueries.exists",
    "sql.windows.ranked",
    "sql.temporal.monthly",
    "sql.dedup.latest",
    "sql.retention.30_day",
    "sql.funnel.completion",
]

REFERENCE_SQL = {
    "sql.joins.simple": """
        SELECT o.customer_id, SUM(o.amount) AS total_revenue FROM orders o
        WHERE o.status='completed' AND o.order_date >= DATE '2025-01-01'
          AND o.order_date < DATE '2026-01-01'
        GROUP BY o.customer_id ORDER BY total_revenue DESC, o.customer_id
    """,
    "sql.joins.multi": """
        SELECT o.customer_id, p.category, SUM(oi.quantity * p.price) AS line_revenue
        FROM orders o JOIN order_items oi ON oi.order_id=o.order_id
        JOIN products p ON p.product_id=oi.product_id
        WHERE o.status='completed' AND o.order_date >= DATE '2025-01-01'
          AND o.order_date < DATE '2026-01-01'
        GROUP BY o.customer_id, p.category
        ORDER BY line_revenue DESC, o.customer_id, p.category
    """,
    "sql.aggregation.grouped": """
        SELECT status, COUNT(*) AS order_count, SUM(amount) AS total_amount,
               AVG(amount) AS avg_amount FROM orders
        WHERE order_date >= DATE '2025-01-01' AND order_date < DATE '2026-01-01'
        GROUP BY status ORDER BY status
    """,
    "sql.cte.monthly": """
        WITH monthly AS (
          SELECT customer_id,
                 strftime('%Y-%m', CAST(order_date AS DATE)) AS revenue_month,
                 SUM(amount) AS monthly_revenue FROM orders
          WHERE status='completed' AND order_date >= DATE '2025-01-01'
            AND order_date < DATE '2026-01-01'
          GROUP BY customer_id, strftime('%Y-%m', CAST(order_date AS DATE)))
        SELECT customer_id, revenue_month, monthly_revenue FROM (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY customer_id ORDER BY monthly_revenue DESC, revenue_month ASC
          ) AS rn FROM monthly) WHERE rn=1 ORDER BY customer_id
    """,
    "sql.subqueries.exists": """
        SELECT c.customer_id, c.name FROM customers c
        WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id=c.customer_id
          AND o.status='completed' AND o.amount > 500
          AND o.order_date >= DATE '2025-01-01' AND o.order_date < DATE '2026-01-01')
        ORDER BY c.customer_id
    """,
    "sql.windows.ranked": """
        SELECT customer_id, order_id, order_date, order_rank, running_total,
               previous_amount FROM (
          SELECT customer_id, order_id, order_date,
            RANK() OVER (PARTITION BY customer_id ORDER BY amount DESC NULLS LAST) AS order_rank,
            SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_date ASC, order_id ASC
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
            LAG(amount) OVER (PARTITION BY customer_id ORDER BY order_date ASC, order_id ASC)
              AS previous_amount
          FROM orders WHERE status='completed'
            AND order_date >= DATE '2025-01-01' AND order_date < DATE '2026-01-01')
        ORDER BY customer_id, order_date, order_id
    """,
    "sql.temporal.monthly": """
        WITH orders_by_month AS (
          SELECT strftime('%Y-%m', CAST(order_date AS DATE)) AS activity_month,
                 COUNT(*) AS order_count FROM orders
          WHERE order_date >= DATE '2025-01-01' AND order_date < DATE '2025-04-01'
          GROUP BY strftime('%Y-%m', CAST(order_date AS DATE))),
        events_by_month AS (
          SELECT strftime('%Y-%m', CAST(event_time AS DATE)) AS activity_month,
                 COUNT(*) AS event_count FROM events
          WHERE event_time >= TIMESTAMP '2025-01-01 00:00:00'
            AND event_time < TIMESTAMP '2025-04-01 00:00:00'
          GROUP BY strftime('%Y-%m', CAST(event_time AS DATE)))
        SELECT COALESCE(o.activity_month, e.activity_month) AS activity_month,
               COALESCE(o.order_count,0) AS order_count,
               COALESCE(e.event_count,0) AS event_count
        FROM orders_by_month o FULL OUTER JOIN events_by_month e
          ON o.activity_month=e.activity_month ORDER BY activity_month
    """,
    "sql.dedup.latest": """
        SELECT customer_id, event_type, event_time FROM (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY customer_id ORDER BY event_time DESC, event_id DESC) AS rn
          FROM events) WHERE rn=1 ORDER BY customer_id
    """,
    "sql.retention.30_day": """
        SELECT c.customer_id,
          EXISTS (SELECT 1 FROM events e WHERE e.customer_id=c.customer_id
            AND e.event_type='purchase' AND CAST(e.event_time AS DATE) >= c.signup_date
            AND CAST(e.event_time AS DATE) <= c.signup_date + 30) AS retained
        FROM customers c ORDER BY c.customer_id
    """,
    "sql.funnel.completion": """
        WITH RECURSIVE ordered AS (
          SELECT customer_id, event_type,
            ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY event_time, event_id) AS rn
          FROM events),
        rec AS (
          SELECT customer_id, 0 AS reached, 0 AS rn
          FROM (SELECT DISTINCT customer_id FROM customers)
          UNION ALL
          SELECT r.customer_id,
            r.reached + CASE WHEN o.event_type = (CASE r.reached WHEN 0 THEN 'view'
              WHEN 1 THEN 'add_to_cart' WHEN 2 THEN 'checkout' WHEN 3 THEN 'purchase'
              ELSE NULL END) THEN 1 ELSE 0 END, o.rn
          FROM rec r JOIN ordered o ON o.customer_id = r.customer_id AND o.rn = r.rn + 1)
        SELECT c.customer_id, COALESCE(MAX(r.reached),0) AS max_step_reached,
               COALESCE(MAX(r.reached),0)=4 AS completed
        FROM customers c LEFT JOIN rec r ON r.customer_id=c.customer_id
        GROUP BY c.customer_id ORDER BY c.customer_id
    """,
}

WRONG_SQL = {
    "sql.joins.simple": "SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id",
    "sql.joins.multi": (
        "SELECT o.customer_id, p.category, SUM(oi.quantity*p.price) FROM orders o "
        "JOIN order_items oi ON oi.order_id=o.order_id "
        "JOIN products p ON p.product_id=oi.product_id "
        "GROUP BY o.customer_id, p.category"
    ),
    "sql.aggregation.grouped": (
        "SELECT status, COUNT(amount), SUM(amount), AVG(amount) FROM orders "
        "GROUP BY status ORDER BY status"
    ),
    "sql.cte.monthly": (
        "SELECT customer_id, max(strftime('%Y-%m', CAST(order_date AS DATE))), SUM(amount) "
        "FROM orders WHERE status='completed' GROUP BY customer_id ORDER BY customer_id"
    ),
    "sql.subqueries.exists": (
        "SELECT c.customer_id, c.name FROM customers c WHERE EXISTS (SELECT 1 FROM orders o "
        "WHERE o.customer_id=c.customer_id AND o.amount >= 500) ORDER BY c.customer_id"
    ),
    "sql.windows.ranked": (
        "SELECT customer_id, order_id, order_date, "
        "ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount DESC) AS order_rank, "
        "SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_date) AS running_total, "
        "LAG(amount) OVER (PARTITION BY customer_id ORDER BY order_date) AS previous_amount "
        "FROM orders WHERE status='completed' ORDER BY customer_id, order_date, order_id"
    ),
    "sql.temporal.monthly": (
        "SELECT strftime('%Y-%m', CAST(order_date AS DATE)), COUNT(*), 0 FROM orders "
        "WHERE order_date <= DATE '2025-03-31' GROUP BY 1 ORDER BY 1"
    ),
    "sql.dedup.latest": (
        "SELECT customer_id, event_type, event_time FROM events "
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY event_id DESC)=1 "
        "ORDER BY customer_id"
    ),
    "sql.retention.30_day": (
        "SELECT c.customer_id, EXISTS (SELECT 1 FROM events e "
        "WHERE e.customer_id=c.customer_id AND e.event_type='purchase') "
        "FROM customers c ORDER BY c.customer_id"
    ),
    "sql.funnel.completion": "SELECT customer_id, 0, FALSE FROM customers ORDER BY customer_id",
}


def _normalize(rows):
    normalized = []
    for row in rows:
        normalized.append(
            [str(v) if isinstance(v, (date, datetime)) else v for v in row]
        )
    return normalized


@pytest.mark.parametrize("template_id", BASE_TEMPLATES)
def test_base_template_has_executable_discriminating_adversarial_fixture(template_id):
    task = generate_task(load_builtin_registry().get(template_id), 7)
    tables = independent_adversarial_tables(task)
    assert tables is not None
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
    assert expected.rows
    con = materialize_duckdb(task.schema_, tables)
    try:
        actual = _normalize([list(row) for row in con.execute(REFERENCE_SQL[template_id]).fetchall()])
        wrong = _normalize([list(row) for row in con.execute(WRONG_SQL[template_id]).fetchall()])
    finally:
        con.close()
    assert actual == expected.rows, template_id
    assert wrong != expected.rows, template_id
