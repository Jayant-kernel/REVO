"""10x3 end-to-end verdict matrix (real Docker + real oracle, no fakes).

Per family: correct -> PASS, obvious fault -> FAIL, subtle fault -> FAIL.
Seeds are fixed catalog seeds, so every expectation below is deterministic;
a subtle candidate receiving PASS is treated as a defect to investigate
(§6), never as a test to weaken.

The matrix executes ONCE per session (module cache): parametrized tests
and the §32 report both read the same real outcomes.
"""

import pytest

from tests.verify_sql_samples import CORRECT_SQL
from tests.verify_testkit import TEMPLATE_SEEDS, make_candidate, make_task
from verified_data_factory.sandbox import DockerRunner, SandboxConfig, SandboxExecutor
from verified_data_factory.verification import VerificationConfig, verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

from tests.integration.sandbox.test_docker_available import requires_docker

OBVIOUS_SQL: dict[str, str] = {
    "sql.joins.simple": (
        "SELECT c.customer_id, SUM(o.amount) AS total_revenue FROM customers c "
        "INNER JOIN orders o ON o.customer_id = c.customer_id "
        "GROUP BY c.customer_id ORDER BY total_revenue DESC;"
    ),
    "sql.joins.multi": (
        "SELECT c.customer_id, p.category, SUM(oi.quantity) AS line_revenue "
        "FROM customers c INNER JOIN orders o ON o.customer_id = c.customer_id "
        "INNER JOIN order_items oi ON oi.order_id = o.order_id "
        "INNER JOIN products p ON p.product_id = oi.product_id "
        "WHERE o.status = 'completed' AND o.order_date >= DATE '2025-01-01' "
        "AND o.order_date < DATE '2026-01-01' GROUP BY c.customer_id, p.category "
        "ORDER BY line_revenue DESC;"
    ),
    "sql.aggregation.grouped": (
        "SELECT status, COUNT(*) AS order_count, SUM(amount) AS total_amount, "
        "SUM(amount) AS avg_amount FROM orders "
        "WHERE order_date >= DATE '2025-01-01' AND order_date < DATE '2026-01-01' "
        "GROUP BY status ORDER BY status;"
    ),
    "sql.cte.monthly": (
        "WITH monthly AS (SELECT customer_id, strftime(order_date, '%Y-%m') AS revenue_month, "
        "SUM(amount) AS monthly_revenue FROM orders "
        "WHERE order_date >= DATE '2025-01-01' AND order_date < DATE '2026-01-01' "
        "GROUP BY customer_id, revenue_month) SELECT customer_id, revenue_month, monthly_revenue "
        "FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY monthly_revenue DESC, "
        "revenue_month ASC) AS rn FROM monthly) t WHERE rn = 1 ORDER BY customer_id;"
    ),
    "sql.subqueries.exists": (
        "SELECT customer_id, name FROM customers c WHERE EXISTS (SELECT 1 FROM orders o "
        "WHERE o.customer_id = c.customer_id AND o.status = 'completed' "
        "AND o.order_date >= DATE '2025-01-01' AND o.order_date < DATE '2026-01-01') "
        "ORDER BY customer_id;"
    ),
    "sql.windows.ranked": (
        "SELECT customer_id, order_id, "
        "RANK() OVER (ORDER BY amount DESC) AS order_rank, "
        "SUM(amount) OVER (ORDER BY order_date, order_id "
        "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total "
        "FROM orders WHERE status = 'completed' AND order_date >= DATE '2025-01-01' "
        "AND order_date < DATE '2026-01-01' ORDER BY customer_id, order_date, order_id;"
    ),
    "sql.temporal.monthly": (
        "WITH o AS (SELECT strftime(order_date, '%Y-%m') AS m, COUNT(*) AS c FROM orders GROUP BY m), "
        "e AS (SELECT strftime(event_time, '%Y-%m') AS m, COUNT(*) AS c FROM events GROUP BY m), "
        "months AS (SELECT m FROM o UNION SELECT m FROM e) "
        "SELECT m AS activity_month, COALESCE((SELECT c FROM o WHERE o.m = months.m), 0) AS order_count, "
        "COALESCE((SELECT c FROM e WHERE e.m = months.m), 0) AS event_count "
        "FROM months ORDER BY m;"
    ),
    "sql.dedup.latest": (
        "SELECT customer_id, event_type, event_time FROM (SELECT *, ROW_NUMBER() OVER "
        "(PARTITION BY customer_id ORDER BY event_time ASC, event_id ASC) AS rn FROM events) t "
        "WHERE rn = 1 ORDER BY customer_id;"
    ),
    "sql.retention.30_day": (
        "SELECT c.customer_id, EXISTS (SELECT 1 FROM events e WHERE e.customer_id = c.customer_id "
        "AND e.event_type = 'view' AND DATE(e.event_time) >= c.signup_date "
        "AND DATE(e.event_time) <= c.signup_date + INTERVAL 30 DAY) AS retained "
        "FROM customers c ORDER BY c.customer_id;"
    ),
    "sql.funnel.completion": (
        "WITH distinct_steps AS (SELECT customer_id, COUNT(DISTINCT event_type) AS n FROM events "
        "WHERE event_type IN ('view', 'add_to_cart', 'checkout', 'purchase') GROUP BY customer_id) "
        "SELECT c.customer_id, COALESCE(d.n, 0) AS max_step_reached, (COALESCE(d.n, 0) = 4) AS completed "
        "FROM customers c LEFT JOIN distinct_steps d USING (customer_id) ORDER BY c.customer_id;"
    ),
}

SUBTLE_SQL: dict[str, str] = {
    "sql.joins.simple": (
        "SELECT c.customer_id, AVG(o.amount) AS total_revenue FROM customers c "
        "INNER JOIN orders o ON o.customer_id = c.customer_id "
        "WHERE o.status = 'completed' AND o.order_date >= DATE '2025-01-01' "
        "AND o.order_date < DATE '2026-01-01' GROUP BY c.customer_id "
        "ORDER BY total_revenue DESC;"
    ),
    "sql.joins.multi": (
        "SELECT c.customer_id, p.category, SUM(oi.quantity * o.amount) AS line_revenue "
        "FROM customers c INNER JOIN orders o ON o.customer_id = c.customer_id "
        "INNER JOIN order_items oi ON oi.order_id = o.order_id "
        "INNER JOIN products p ON p.product_id = oi.product_id "
        "WHERE o.status = 'completed' AND o.order_date >= DATE '2025-01-01' "
        "AND o.order_date < DATE '2026-01-01' GROUP BY c.customer_id, p.category "
        "ORDER BY line_revenue DESC;"
    ),
    "sql.aggregation.grouped": (
        "SELECT status, COUNT(amount) AS order_count, SUM(amount) AS total_amount, "
        "AVG(amount) AS avg_amount FROM orders "
        "WHERE order_date >= DATE '2025-01-01' AND order_date < DATE '2026-01-01' "
        "GROUP BY status ORDER BY status;"
    ),
    "sql.cte.monthly": (
        "WITH yearly AS (SELECT customer_id, strftime(order_date, '%Y') AS revenue_month, "
        "SUM(amount) AS monthly_revenue FROM orders WHERE status = 'completed' "
        "AND order_date >= DATE '2025-01-01' AND order_date < DATE '2026-01-01' "
        "GROUP BY customer_id, revenue_month) SELECT customer_id, revenue_month, monthly_revenue "
        "FROM yearly ORDER BY customer_id;"
    ),
    "sql.subqueries.exists": (
        "SELECT customer_id, name FROM customers c WHERE EXISTS (SELECT 1 FROM orders o "
        "WHERE o.customer_id = c.customer_id AND o.status = 'completed' "
        "AND o.order_date >= DATE '2025-01-01' AND o.order_date < DATE '2026-01-01' "
        "AND o.amount > 0) ORDER BY customer_id;"
    ),
    "sql.windows.ranked": (
        "SELECT customer_id, order_id, "
        "RANK() OVER (PARTITION BY country ORDER BY amount DESC) AS order_rank, "
        "SUM(amount) OVER (PARTITION BY country ORDER BY order_date, order_id "
        "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total "
        "FROM customers JOIN orders USING (customer_id) WHERE status = 'completed' "
        "AND order_date >= DATE '2025-01-01' AND order_date < DATE '2026-01-01' "
        "ORDER BY customer_id, order_date, order_id;"
    ),
    "sql.temporal.monthly": (
        "WITH o AS (SELECT strftime(order_date, '%Y-%W') AS m, COUNT(*) AS c FROM orders "
        "WHERE order_date BETWEEN DATE '2025-01-01' AND DATE '2025-03-31' GROUP BY m), "
        "e AS (SELECT strftime(event_time, '%Y-%W') AS m, COUNT(*) AS c FROM events "
        "WHERE DATE(event_time) BETWEEN DATE '2025-01-01' AND DATE '2025-03-31' GROUP BY m), "
        "months AS (SELECT m FROM o UNION SELECT m FROM e) "
        "SELECT m AS activity_month, COALESCE((SELECT c FROM o WHERE o.m = months.m), 0) AS order_count, "
        "COALESCE((SELECT c FROM e WHERE e.m = months.m), 0) AS event_count "
        "FROM months ORDER BY m;"
    ),
    "sql.dedup.latest": (
        "SELECT customer_id, event_type, event_time FROM (SELECT *, ROW_NUMBER() OVER "
        "(PARTITION BY event_type ORDER BY event_time DESC, event_id DESC) AS rn FROM events) t "
        "WHERE rn = 1 ORDER BY customer_id;"
    ),
    "sql.retention.30_day": (
        "SELECT c.customer_id, (SELECT COUNT(*) FROM events e WHERE e.customer_id = c.customer_id "
        "AND e.event_type = 'purchase' AND DATE(e.event_time) >= c.signup_date "
        "AND DATE(e.event_time) <= c.signup_date + INTERVAL 30 DAY) >= 2 AS retained "
        "FROM customers c ORDER BY c.customer_id;"
    ),
    "sql.funnel.completion": (
        "WITH s1 AS (SELECT customer_id, MAX(event_time) AS t1 FROM events WHERE event_type = 'view' GROUP BY customer_id), "
        "s2 AS (SELECT e.customer_id, MIN(e.event_time) AS t2 FROM events e JOIN s1 USING (customer_id) "
        "WHERE e.event_type = 'add_to_cart' AND e.event_time >= s1.t1 GROUP BY e.customer_id), "
        "s3 AS (SELECT e.customer_id, MIN(e.event_time) AS t3 FROM events e JOIN s2 USING (customer_id) "
        "WHERE e.event_type = 'checkout' AND e.event_time >= s2.t2 GROUP BY e.customer_id), "
        "s4 AS (SELECT e.customer_id, MIN(e.event_time) AS t4 FROM events e JOIN s3 USING (customer_id) "
        "WHERE e.event_type = 'purchase' AND e.event_time >= s3.t3 GROUP BY e.customer_id) "
        "SELECT c.customer_id, "
        "(CASE WHEN s4.customer_id IS NOT NULL THEN 4 WHEN s3.customer_id IS NOT NULL THEN 3 "
        "WHEN s2.customer_id IS NOT NULL THEN 2 WHEN s1.customer_id IS NOT NULL THEN 1 ELSE 0 END) AS max_step_reached, "
        "(s4.customer_id IS NOT NULL) AS completed FROM customers c "
        "LEFT JOIN s1 USING (customer_id) LEFT JOIN s2 USING (customer_id) "
        "LEFT JOIN s3 USING (customer_id) LEFT JOIN s4 USING (customer_id) ORDER BY c.customer_id;"
    ),
}

_SQL_BY_KIND = {"correct": CORRECT_SQL, "obvious": OBVIOUS_SQL, "subtle": SUBTLE_SQL}
MATRIX_CELLS = [
    (template_id, kind, expected)
    for template_id in CORRECT_SQL
    for kind, expected in (("correct", "PASS"), ("obvious", "FAIL"), ("subtle", "FAIL"))
]

_E2E_SANDBOX = SandboxConfig(timeout_seconds=60)
_E2E_CONFIG = VerificationConfig()

_MATRIX_CACHE = None


def run_matrix_case(template_id, kind):
    """Full real pipeline for one matrix cell; returns the VerificationResult."""
    task = make_task(template_id, TEMPLATE_SEEDS[template_id])
    candidate = make_candidate(task, _SQL_BY_KIND[kind][template_id])
    execution = SandboxExecutor(_E2E_SANDBOX, DockerRunner(_E2E_SANDBOX)).execute(task, candidate)
    return verify_candidate(
        task, candidate, execution, _E2E_CONFIG, DerivedTaskBackend(_E2E_SANDBOX)
    )


def get_matrix():
    """Execute the full matrix once per session; every test reads one run."""
    global _MATRIX_CACHE
    if _MATRIX_CACHE is None:
        _MATRIX_CACHE = {(t, k): run_matrix_case(t, k) for t, k, _ in MATRIX_CELLS}
    return _MATRIX_CACHE


@requires_docker
@pytest.mark.parametrize("template_id,kind,expected", MATRIX_CELLS)
def test_matrix_verdict(template_id, kind, expected):
    result = get_matrix()[(template_id, kind)]
    assert result.verdict == expected, (
        template_id,
        kind,
        result.verdict,
        result.failure_code,
        result.summary,
    )
    if expected == "PASS":
        assert result.hidden is not None and result.hidden.failed == 0
        assert result.hidden.total > 0
        assert result.properties is not None and result.properties.failed == 0
        assert result.properties.applicable > 0
        assert result.metamorphic is not None and result.metamorphic.failed == 0
        assert result.metamorphic.applicable > 0
        assert result.mutation is not None
        assert result.mutation.run > 0


@requires_docker
def test_matrix_report_from_actual_outcomes(tmp_path):
    """Machine-readable matrix (§32) generated from real outcomes, not asserted."""
    matrix = get_matrix()
    rows = []
    for template_id, kind, expected in MATRIX_CELLS:
        result = matrix[(template_id, kind)]
        rows.append(
            {
                "task_family": template_id,
                "candidate_type": kind,
                "expected_verdict": expected,
                "actual_verdict": result.verdict,
                "failure_code": result.failure_code,
                "oracle_version": result.oracle_version,
                "verification_config_version": result.verification_config_version,
                "sandbox_config_version": _E2E_SANDBOX.config_version,
                "mutation_score": result.mutation.mutation_score if result.mutation else None,
            }
        )
    mismatches = [r for r in rows if r["expected_verdict"] != r["actual_verdict"]]
    assert not mismatches, mismatches
