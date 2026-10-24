"""Exact EXISTS@2 discriminators: customer-row bags and existential correlation."""
from __future__ import annotations

from typing import Any

CONTRACT = "sql.subqueries.exists"
Tables = dict[str, list[dict[str, Any]]]


def customer(identifier: int, *, country: str | None = "US") -> dict[str, Any]:
    return {"customer_id": identifier, "name": f"customer-{identifier}",
            "country": country, "signup_date": "2025-01-01"}


def order(identifier: int, owner: int = 1, *, amount: float = 501,
          status: str = "completed", day: str = "2025-06-15") -> dict[str, Any]:
    return {"order_id": identifier, "customer_id": owner, "amount": amount,
            "status": status, "order_date": day}


def rich_fixture() -> Tables:
    return {"customers": [customer(1, country=None), customer(1, country=None),
                         *[customer(i) for i in range(2, 11)]],
            "orders": [order(11, day="2025-01-01"), order(12, amount=499),
                order(13, amount=1, day="2025-12-31"), order(21, 2, amount=500),
                order(31, 3, amount=501, status="pending"),
                order(41, 4, amount=600, day="2024-12-31"), order(51, 5, day="2026-01-01"),
                order(61, 6, amount=700, day="2025-12-31"),
                order(71, 7, amount=250), order(72, 7, amount=300),
                order(81, 8, amount=700), order(82, 8, amount=701), order(99, 99)]}


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("WITH qualified_ids AS (SELECT DISTINCT customer_id FROM orders WHERE status='completed' "
         "AND amount > 500 AND EXTRACT(YEAR FROM order_date)=2025) "
         "SELECT c.customer_id, c.name FROM customers c WHERE EXISTS "
         "(SELECT 1 FROM qualified_ids q WHERE q.customer_id=c.customer_id) ORDER BY c.customer_id"),
        ("SELECT c.customer_id, c.name FROM customers c INNER JOIN LATERAL "
         "(SELECT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id=c.customer_id "
         "AND o.status='completed' AND o.amount > 500 AND o.order_date BETWEEN "
         "DATE '2025-01-01' AND DATE '2025-12-31') AS qualifies) q ON q.qualifies "
         "ORDER BY c.customer_id")]


def failures(reference: str) -> dict[str, str]:
    matching = ("o.customer_id=c.customer_id AND o.status='completed' AND o.amount > 500 "
                "AND o.order_date >= DATE '2025-01-01' AND o.order_date < DATE '2026-01-01'")
    join = ("SELECT c.customer_id, c.name FROM customers c INNER JOIN orders o ON "
            + matching + " ORDER BY c.customer_id")
    return {
        "uncorrelated": reference.replace("o.customer_id=c.customer_id", "TRUE"),
        "wrong_correlation_key": reference.replace("o.customer_id=c.customer_id", "o.order_id=c.customer_id"),
        "negated_correlation": reference.replace("o.customer_id=c.customer_id", "o.customer_id<>c.customer_id"),
        "threshold_equal_included": reference.replace("o.amount > 500", "o.amount >= 500"),
        "threshold_inverted": reference.replace("o.amount > 500", "o.amount < 500"),
        "status_dropped": reference.replace("o.status='completed'", "TRUE"),
        "status_pending": reference.replace("o.status='completed'", "o.status='pending'"),
        "lower_year_unbounded": reference.replace("o.order_date >= DATE '2025-01-01'", "TRUE"),
        "upper_year_unbounded": reference.replace("o.order_date < DATE '2026-01-01'", "TRUE"),
        "jan_first_excluded": reference.replace(">= DATE '2025-01-01'", "> DATE '2025-01-01'"),
        "next_jan_included": reference.replace("< DATE '2026-01-01'", "<= DATE '2026-01-01'"),
        "last_day_excluded": reference.replace("< DATE '2026-01-01'", "< DATE '2025-12-31'"),
        "anti_exists": reference.replace("WHERE EXISTS", "WHERE NOT EXISTS"),
        "join_fanout": join,
        "distinct_customer_collapse": reference.replace("SELECT c.customer_id", "SELECT DISTINCT c.customer_id"),
        "nullable_country_excluded": reference.replace("WHERE EXISTS", "WHERE c.country IS NOT NULL AND EXISTS"),
        "wrong_name_projection": reference.replace("SELECT c.customer_id, c.name", "SELECT c.customer_id, c.country AS name"),
        "id_as_text": reference.replace("SELECT c.customer_id", "SELECT CAST(c.customer_id AS VARCHAR) AS customer_id"),
        "reverse_order": reference.replace("ORDER BY c.customer_id", "ORDER BY c.customer_id DESC"),
        "first_only": reference.rstrip() + " LIMIT 1",
        "aggregate_threshold": ("SELECT c.customer_id, c.name FROM customers c WHERE "
            "(SELECT SUM(o.amount) FROM orders o WHERE o.customer_id=c.customer_id AND o.status='completed' "
            "AND EXTRACT(YEAR FROM o.order_date)=2025)>500 ORDER BY c.customer_id"),
        "all_orders_threshold": reference.replace("WHERE EXISTS", "WHERE NOT EXISTS").replace("o.amount > 500", "o.amount <= 500"),
        "latest_order_only": ("SELECT c.customer_id, c.name FROM customers c WHERE "
            "(SELECT o.amount FROM orders o WHERE o.customer_id=c.customer_id AND o.status='completed' "
            "AND EXTRACT(YEAR FROM o.order_date)=2025 ORDER BY o.order_date DESC, o.order_id DESC "
            "LIMIT 1)>500 ORDER BY c.customer_id"),
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "uncorrelated", "year": "lower_year_unbounded",
            "status_filter": "status_dropped", "min_amount": "threshold_inverted",
            "threshold_operator": "threshold_equal_included", "exists_semantics": "join_fanout",
            "no_match_behavior": "anti_exists", "output_columns": "id_as_text",
            "order_by": "reverse_order", "customer_bag": "distinct_customer_collapse"}
    return {key: {"witness": rich_fixture(), "wrong_sql": wrong[label],
                  "outcome": "UNEXECUTED_RULE_SPEC"} for key, label in keys.items()}


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(wrong, rich_fixture()) for wrong in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"customers": [customer(1)], "orders": [order(11)]}
    wrong = failures(reference)
    return [("EXISTS_QUALIFYING_ORDER_DUPLICATE", wrong["join_fanout"], baseline),
            ("EXISTS_CUSTOMER_ROW_DUPLICATE", wrong["distinct_customer_collapse"], baseline)]
