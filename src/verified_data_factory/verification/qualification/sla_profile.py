"""Version-bound public discriminators for fulfillment SLA dashboard@1."""
from __future__ import annotations

from typing import Any

CONTRACT = "sql.aggregation.fulfillment_sla_dashboard"


def row(identifier: int, warehouse: str = "a", *, year: int = 2025, status: str = "delivered",
        delivery: str | None = "2025-01-02 12:00:00") -> dict[str, Any]:
    return {"fulfillment_id": identifier, "warehouse": warehouse,
            "shipped_at": f"{year}-01-01 12:00:00", "promised_at": "2025-01-02 12:00:00",
            "delivered_at": delivery, "fulfillment_status": status}


def proofs(sql: str) -> dict[str, Any]:
    base = {"fulfillments": [row(1), row(2), row(3, "b", delivery="2025-01-03 12:00:00") ]}
    excluded = {"fulfillments": [*base["fulfillments"], row(4, "excluded", status="cancelled")]}
    unresolved = {"fulfillments": [row(1, delivery=None)]}
    year = {"fulfillments": [row(1, year=2024)]}
    count = sql.replace("COUNT(*)", "COUNT(DISTINCT warehouse)")
    cases = {
        "objective": (base, sql.replace("THEN 1 ELSE 0", "THEN 0 ELSE 1")),
        "year": (year, sql.replace("EXTRACT(YEAR FROM shipped_at)=2025", "TRUE")),
        "status_filter": (excluded, sql.replace("fulfillment_status='delivered'", "TRUE")),
        "group_by": (base, sql.replace("SELECT warehouse,", "SELECT MIN(warehouse) AS warehouse,")
                     .replace("GROUP BY warehouse", "").replace("ORDER BY warehouse ASC", "ORDER BY warehouse ASC")),
        "null_handling": (unresolved, sql.replace("delivered_at IS NOT NULL", "TRUE")),
        "count_semantics": (base, count),
        "empty_group_behavior": (excluded, sql.replace("fulfillment_status='delivered'", "TRUE")),
        "output_columns": (base, sql.replace("AS delivered_fulfillments", "AS wrong_count")),
        "order_by": (base, sql.replace("ORDER BY warehouse ASC", "ORDER BY warehouse DESC")),
        "deadline_inclusive": ({"fulfillments": [row(1)]}, sql.replace("delivered_at <= promised_at", "delivered_at < promised_at")),
    }
    return {key: {"witness": tables, "wrong_sql": wrong, "outcome": "UNEXECUTED_RULE_SPEC"}
            for key, (tables, wrong) in cases.items()}


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("SELECT warehouse, COUNT(*) AS delivered_fulfillments, "
         "COUNT(*) FILTER (WHERE delivered_at <= promised_at) AS on_time_fulfillments "
         "FROM fulfillments WHERE fulfillment_status='delivered' AND delivered_at IS NOT NULL "
         "AND EXTRACT(YEAR FROM shipped_at)=2025 GROUP BY warehouse ORDER BY warehouse ASC"),
        ("SELECT DISTINCT warehouse, COUNT(*) OVER (PARTITION BY warehouse) AS delivered_fulfillments, "
         "SUM(CASE WHEN delivered_at <= promised_at THEN 1 ELSE 0 END) OVER (PARTITION BY warehouse) AS on_time_fulfillments "
         "FROM fulfillments WHERE fulfillment_status='delivered' AND delivered_at IS NOT NULL "
         "AND EXTRACT(YEAR FROM shipped_at)=2025 ORDER BY warehouse ASC")]


def challenge_specs(reference: str) -> list[tuple[str, dict[str, list[dict[str, Any]]]]]:
    base = {"fulfillments": [row(1), row(2), row(3, "b", delivery="2025-01-03 12:00:00"),
            row(4, "cancelled", status="cancelled"), row(5, "unresolved", delivery=None), row(6, "old", year=2024)]}
    wrong = [reference.replace("COUNT(*)", expression) for expression in (
        "COUNT(DISTINCT warehouse)", "SUM(fulfillment_id)", "COUNT(*)+1", "COUNT(*)-1", "COUNT(*)*2", "COUNT(*)*0")]
    wrong += [reference.replace("delivered_at <= promised_at", predicate) for predicate in (
        "delivered_at < promised_at", "delivered_at > promised_at", "TRUE", "FALSE", "delivered_at >= promised_at")]
    wrong += [reference.replace("fulfillment_status='delivered'", "TRUE"),
              reference.replace("delivered_at IS NOT NULL", "TRUE"),
              reference.replace("EXTRACT(YEAR FROM shipped_at)=2025", "TRUE"),
              reference.replace("=2025", "=2024"), reference.replace("=2025", "=2026"),
              reference.replace("ORDER BY warehouse ASC", "ORDER BY warehouse DESC"),
              reference.replace("AS delivered_fulfillments", "AS wrong_count"),
              reference.replace("THEN 1 ELSE 0", "THEN 2 ELSE 0"),
              reference.replace("THEN 1 ELSE 0", "THEN 1 ELSE 1")]
    return [(sql, base) for sql in wrong]
