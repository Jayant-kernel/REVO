"""Separately authored counterexamples for the base legacy templates.

These fixtures are hand-authored, independent of the seeded fixture
generator, and deliberately exercise each base contract's weakest
boundary (status/year filters, NULL handling, ties, and window edges).
They are authored by the engineering agent, NOT human reviewed. They are
deliberately small so a wrong-but-plausible query diverges from the
independent oracle on at least one row.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Rows = dict[str, list[dict[str, Any]]]


def _simple_joins() -> Rows:
    return {
        "customers": [
            {"customer_id": 1, "name": "Alpha", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 2, "name": "Bravo", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 3, "name": "Charlie", "country": "US", "signup_date": "2025-01-01"},
        ],
        "orders": [
            {"order_id": 1, "customer_id": 1, "order_date": "2025-01-01", "amount": 100.0, "status": "completed"},
            {"order_id": 2, "customer_id": 1, "order_date": "2025-02-01", "amount": 50.0, "status": "cancelled"},
            {"order_id": 3, "customer_id": 1, "order_date": "2024-12-31", "amount": 999.0, "status": "completed"},
            {"order_id": 4, "customer_id": 2, "order_date": "2025-03-01", "amount": 100.0, "status": "completed"},
        ],
    }


def _multi_joins() -> Rows:
    return {
        "customers": [
            {"customer_id": 1, "name": "Alpha", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 2, "name": "Bravo", "country": "US", "signup_date": "2025-01-01"},
        ],
        "orders": [
            {"order_id": 1, "customer_id": 1, "order_date": "2025-01-01", "amount": 0.0, "status": "completed"},
            {"order_id": 2, "customer_id": 1, "order_date": "2025-01-02", "amount": 0.0, "status": "cancelled"},
            {"order_id": 3, "customer_id": 2, "order_date": "2024-12-31", "amount": 0.0, "status": "completed"},
        ],
        "products": [
            {"product_id": 1, "name": "Widget", "category": "Alpha", "price": 10.0},
            {"product_id": 2, "name": "Gadget", "category": "Beta", "price": 5.0},
        ],
        "order_items": [
            {"item_id": 1, "order_id": 1, "product_id": 1, "quantity": 2},
            {"item_id": 2, "order_id": 2, "product_id": 1, "quantity": 5},
            {"item_id": 3, "order_id": 3, "product_id": 2, "quantity": 5},
            {"item_id": 4, "order_id": 1, "product_id": 2, "quantity": 3},
        ],
    }


def _grouped() -> Rows:
    return {
        "orders": [
            {"order_id": 1, "customer_id": 1, "order_date": "2025-01-01", "amount": 100.0, "status": "completed"},
            {"order_id": 2, "customer_id": 1, "order_date": "2025-01-02", "amount": None, "status": "completed"},
            {"order_id": 3, "customer_id": 2, "order_date": "2025-01-03", "amount": 0.0, "status": "pending"},
            {"order_id": 4, "customer_id": 2, "order_date": "2024-12-31", "amount": 999.0, "status": "completed"},
            {"order_id": 5, "customer_id": 3, "order_date": "2025-02-01", "amount": 50.0, "status": "cancelled"},
        ],
    }


def _cte_monthly() -> Rows:
    return {
        "customers": [
            {"customer_id": 1, "name": "Alpha", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 2, "name": "Bravo", "country": "US", "signup_date": "2025-01-01"},
        ],
        "orders": [
            {"order_id": 1, "customer_id": 1, "order_date": "2025-01-10", "amount": 100.0, "status": "completed"},
            {"order_id": 2, "customer_id": 1, "order_date": "2025-02-10", "amount": 100.0, "status": "completed"},
            {"order_id": 3, "customer_id": 1, "order_date": "2025-03-10", "amount": 50.0, "status": "cancelled"},
            {"order_id": 4, "customer_id": 2, "order_date": "2024-12-10", "amount": 500.0, "status": "completed"},
        ],
    }


def _subqueries_exists() -> Rows:
    return {
        "customers": [
            {"customer_id": 1, "name": "Alpha", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 2, "name": "Bravo", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 3, "name": "Charlie", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 4, "name": "Delta", "country": "US", "signup_date": "2025-01-01"},
        ],
        "orders": [
            {"order_id": 1, "customer_id": 1, "order_date": "2025-01-01", "amount": 500.0, "status": "completed"},
            {"order_id": 2, "customer_id": 2, "order_date": "2025-01-02", "amount": 500.01, "status": "completed"},
            {"order_id": 3, "customer_id": 3, "order_date": "2025-01-03", "amount": 1000.0, "status": "cancelled"},
            {"order_id": 4, "customer_id": 3, "order_date": "2024-12-31", "amount": 1000.0, "status": "completed"},
        ],
    }


def _windows_ranked() -> Rows:
    return {
        "customers": [
            {"customer_id": 1, "name": "Alpha", "country": "US", "signup_date": "2025-01-01"},
        ],
        "orders": [
            {"order_id": 2, "customer_id": 1, "order_date": "2025-01-01", "amount": 100.0, "status": "completed"},
            {"order_id": 1, "customer_id": 1, "order_date": "2025-01-02", "amount": 100.0, "status": "completed"},
            {"order_id": 3, "customer_id": 1, "order_date": "2025-01-03", "amount": None, "status": "completed"},
            {"order_id": 4, "customer_id": 1, "order_date": "2025-01-04", "amount": 50.0, "status": "cancelled"},
        ],
    }


def _temporal_monthly() -> Rows:
    return {
        "orders": [
            {"order_id": 1, "customer_id": 1, "order_date": "2025-01-15", "amount": 10.0, "status": "completed"},
            {"order_id": 2, "customer_id": 1, "order_date": "2024-12-31", "amount": 10.0, "status": "completed"},
            {"order_id": 3, "customer_id": 1, "order_date": "2025-03-31", "amount": 10.0, "status": "completed"},
            {"order_id": 4, "customer_id": 1, "order_date": "2025-04-01", "amount": 10.0, "status": "completed"},
        ],
        "events": [
            {"event_id": 1, "customer_id": 1, "event_type": "click", "event_time": "2025-02-10 00:00:00"},
            {"event_id": 2, "customer_id": 1, "event_type": "click", "event_time": "2025-03-31 23:59:59"},
            {"event_id": 3, "customer_id": 1, "event_type": "click", "event_time": "2025-04-05 00:00:00"},
        ],
    }


def _dedup_latest() -> Rows:
    return {
        "events": [
            {"event_id": 5, "customer_id": 1, "event_type": "alpha", "event_time": "2025-01-01 00:00:00"},
            {"event_id": 9, "customer_id": 1, "event_type": "bravo", "event_time": "2025-01-01 00:00:00"},
            {"event_id": 1, "customer_id": 2, "event_type": "charlie", "event_time": "2025-05-01 00:00:00"},
            {"event_id": 2, "customer_id": 2, "event_type": "delta", "event_time": "2025-04-01 00:00:00"},
        ],
    }


def _retention_30_day() -> Rows:
    return {
        "customers": [
            {"customer_id": 1, "name": "Alpha", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 2, "name": "Bravo", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 3, "name": "Charlie", "country": "US", "signup_date": "2025-01-01"},
        ],
        "events": [
            {"event_id": 1, "customer_id": 1, "event_type": "purchase", "event_time": "2025-01-31 12:00:00"},
            {"event_id": 2, "customer_id": 2, "event_type": "purchase", "event_time": "2025-02-01 12:00:00"},
            {"event_id": 3, "customer_id": 3, "event_type": "signup", "event_time": "2025-01-05 12:00:00"},
            {"event_id": 4, "customer_id": 3, "event_type": "purchase", "event_time": "2024-12-31 12:00:00"},
        ],
    }


def _funnel_completion() -> Rows:
    same = "2025-01-01 00:00:00"
    return {
        "customers": [
            {"customer_id": 1, "name": "Alpha", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 2, "name": "Bravo", "country": "US", "signup_date": "2025-01-01"},
            {"customer_id": 3, "name": "Charlie", "country": "US", "signup_date": "2025-01-01"},
        ],
        "events": [
            {"event_id": 1, "customer_id": 1, "event_type": "view", "event_time": same},
            {"event_id": 2, "customer_id": 1, "event_type": "add_to_cart", "event_time": same},
            {"event_id": 3, "customer_id": 1, "event_type": "checkout", "event_time": same},
            {"event_id": 4, "customer_id": 1, "event_type": "purchase", "event_time": same},
            {"event_id": 5, "customer_id": 2, "event_type": "view", "event_time": same},
            {"event_id": 6, "customer_id": 2, "event_type": "purchase", "event_time": same},
            {"event_id": 7, "customer_id": 2, "event_type": "add_to_cart", "event_time": same},
        ],
    }


#: template_id -> (latest selectable version, fixture factory)
LEGACY_ADVERSARIAL: dict[str, tuple[int, Callable[[], Rows]]] = {
    "sql.joins.simple": (1, _simple_joins),
    "sql.joins.multi": (1, _multi_joins),
    "sql.aggregation.grouped": (2, _grouped),
    "sql.cte.monthly": (4, _cte_monthly),
    "sql.subqueries.exists": (2, _subqueries_exists),
    "sql.windows.ranked": (2, _windows_ranked),
    "sql.temporal.monthly": (5, _temporal_monthly),
    "sql.dedup.latest": (2, _dedup_latest),
    "sql.retention.30_day": (2, _retention_30_day),
    "sql.funnel.completion": (3, _funnel_completion),
}


def legacy_adversarial(template_id: str, template_version: int) -> Rows | None:
    entry = LEGACY_ADVERSARIAL.get(template_id)
    if entry is None:
        return None
    version, factory = entry
    if template_version != version:
        return None
    return factory()
