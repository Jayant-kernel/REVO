"""Shared hand-authored candidate SQL for verification tests (no models).

CORRECT_SQL holds genuinely correct DuckDB for each template (validated by
design against docs/task-semantics.md; Docker integration tests execute
them). WRONG_SQL holds characteristic faults. Unit tests use these strings
for operator-applicability and pipeline tests; only integration tests run
them in containers.
"""

CORRECT_SQL: dict[str, str] = {
    "sql.joins.simple": (
        "SELECT c.customer_id, SUM(o.amount) AS total_revenue FROM customers c "
        "INNER JOIN orders o ON o.customer_id = c.customer_id "
        "WHERE o.status = 'completed' AND o.order_date >= DATE '2025-01-01' "
        "AND o.order_date < DATE '2026-01-01' GROUP BY c.customer_id "
        "ORDER BY total_revenue DESC;"
    ),
    "sql.joins.multi": (
        "SELECT c.customer_id, p.category, SUM(oi.quantity * p.price) AS line_revenue "
        "FROM customers c INNER JOIN orders o ON o.customer_id = c.customer_id "
        "INNER JOIN order_items oi ON oi.order_id = o.order_id "
        "INNER JOIN products p ON p.product_id = oi.product_id "
        "WHERE o.status = 'completed' AND o.order_date >= DATE '2025-01-01' "
        "AND o.order_date < DATE '2026-01-01' GROUP BY c.customer_id, p.category "
        "ORDER BY line_revenue DESC;"
    ),
    "sql.aggregation.grouped": (
        "SELECT status, COUNT(*) AS order_count, SUM(amount) AS total_amount, "
        "AVG(amount) AS avg_amount FROM orders "
        "WHERE order_date >= DATE '2025-01-01' AND order_date < DATE '2026-01-01' "
        "GROUP BY status ORDER BY status;"
    ),
    "sql.cte.monthly": (
        "WITH monthly AS (SELECT customer_id, strftime(order_date, '%Y-%m') AS revenue_month, "
        "SUM(amount) AS monthly_revenue FROM orders WHERE status = 'completed' "
        "AND order_date >= DATE '2025-01-01' AND order_date < DATE '2026-01-01' "
        "GROUP BY customer_id, revenue_month) SELECT customer_id, revenue_month, monthly_revenue "
        "FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY monthly_revenue DESC, "
        "revenue_month ASC) AS rn FROM monthly) t WHERE rn = 1 ORDER BY customer_id;"
    ),
    "sql.subqueries.exists": (
        "SELECT customer_id, name FROM customers c WHERE EXISTS (SELECT 1 FROM orders o "
        "WHERE o.customer_id = c.customer_id AND o.status = 'completed' "
        "AND o.order_date >= DATE '2025-01-01' AND o.order_date < DATE '2026-01-01' "
        "AND o.amount > 500) ORDER BY customer_id;"
    ),
    "sql.windows.ranked": (
        "SELECT customer_id, order_id, order_date, "
        "RANK() OVER (PARTITION BY customer_id ORDER BY amount DESC NULLS LAST) AS order_rank, "
        "SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_date, order_id "
        "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total, "
        "LAG(amount) OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS previous_amount "
        "FROM orders WHERE status = 'completed' AND order_date >= DATE '2025-01-01' "
        "AND order_date < DATE '2026-01-01' ORDER BY customer_id, order_date, order_id;"
    ),
    "sql.temporal.monthly": (
        "WITH o AS (SELECT strftime(order_date, '%Y-%m') AS m, COUNT(*) AS c FROM orders "
        "WHERE order_date BETWEEN DATE '2025-01-01' AND DATE '2025-03-31' GROUP BY m), "
        "e AS (SELECT strftime(event_time, '%Y-%m') AS m, COUNT(*) AS c FROM events "
        "WHERE DATE(event_time) BETWEEN DATE '2025-01-01' AND DATE '2025-03-31' GROUP BY m), "
        "months AS (SELECT m FROM o UNION SELECT m FROM e) "
        "SELECT m AS activity_month, COALESCE((SELECT c FROM o WHERE o.m = months.m), 0) AS order_count, "
        "COALESCE((SELECT c FROM e WHERE e.m = months.m), 0) AS event_count "
        "FROM months ORDER BY m;"
    ),
    "sql.dedup.latest": (
        "SELECT customer_id, event_type, event_time FROM (SELECT *, ROW_NUMBER() OVER "
        "(PARTITION BY customer_id ORDER BY event_time DESC, event_id DESC) AS rn FROM events) t "
        "WHERE rn = 1 ORDER BY customer_id;"
    ),
    "sql.retention.30_day": (
        "SELECT c.customer_id, EXISTS (SELECT 1 FROM events e WHERE e.customer_id = c.customer_id "
        "AND e.event_type = 'purchase' AND DATE(e.event_time) >= c.signup_date "
        "AND DATE(e.event_time) <= c.signup_date + INTERVAL 30 DAY) AS retained "
        "FROM customers c ORDER BY c.customer_id;"
    ),
    "sql.funnel.completion": (
        "WITH s1 AS (SELECT customer_id, event_time AS t1, event_id AS i1 FROM events WHERE event_type = 'view' "
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY event_time, event_id) = 1), "
        "s2 AS (SELECT e.customer_id, e.event_time AS t2, e.event_id AS i2 FROM events e JOIN s1 USING (customer_id) "
        "WHERE e.event_type = 'add_to_cart' AND (e.event_time > s1.t1 OR (e.event_time = s1.t1 AND e.event_id > s1.i1)) "
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY e.customer_id ORDER BY e.event_time, e.event_id) = 1), "
        "s3 AS (SELECT e.customer_id, e.event_time AS t3, e.event_id AS i3 FROM events e JOIN s2 USING (customer_id) "
        "WHERE e.event_type = 'checkout' AND (e.event_time > s2.t2 OR (e.event_time = s2.t2 AND e.event_id > s2.i2)) "
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY e.customer_id ORDER BY e.event_time, e.event_id) = 1), "
        "s4 AS (SELECT e.customer_id, e.event_time AS t4, e.event_id AS i4 FROM events e JOIN s3 USING (customer_id) "
        "WHERE e.event_type = 'purchase' AND (e.event_time > s3.t3 OR (e.event_time = s3.t3 AND e.event_id > s3.i3)) "
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY e.customer_id ORDER BY e.event_time, e.event_id) = 1) "
        "SELECT c.customer_id, "
        "(CASE WHEN s4.customer_id IS NOT NULL THEN 4 WHEN s3.customer_id IS NOT NULL THEN 3 "
        "WHEN s2.customer_id IS NOT NULL THEN 2 WHEN s1.customer_id IS NOT NULL THEN 1 ELSE 0 END) AS max_step_reached, "
        "(s4.customer_id IS NOT NULL) AS completed FROM customers c "
        "LEFT JOIN s1 USING (customer_id) LEFT JOIN s2 USING (customer_id) "
        "LEFT JOIN s3 USING (customer_id) LEFT JOIN s4 USING (customer_id) ORDER BY c.customer_id;"
    ),
}

WRONG_SQL: dict[str, str] = {
    # Dropped filter / wrong threshold / wrong key per family.
    "sql.joins.simple": (
        "SELECT c.customer_id, SUM(o.amount) AS total_revenue FROM customers c "
        "INNER JOIN orders o ON o.customer_id = c.customer_id "
        "GROUP BY c.customer_id ORDER BY total_revenue DESC;"
    ),
    "sql.aggregation.grouped": (
        "SELECT status, COUNT(amount) AS order_count, SUM(amount) AS total_amount, "
        "AVG(amount) AS avg_amount FROM orders GROUP BY status ORDER BY status;"
    ),
}
