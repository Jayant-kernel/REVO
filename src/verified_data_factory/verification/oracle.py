"""Independent reference oracles (Phase 4).

Each oracle implements the mathematical/business semantics from
``docs/task-semantics.md`` directly in Python over fixture rows —
never SQL, never candidate text, never execution output. Signatures take
only ``(requirements, tables)`` so independence is structural, not just
discipline (asserted by static tests).

All oracles return :class:`ExpectedResult` with an explicit order spec.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping
from typing import Any

from .models import ExpectedResult, OrderSpec


def _out_cols(requirements: Mapping[str, Any]) -> list[str]:
    return [str(c).split(".")[-1] for c in requirements.get("output_columns", [])]


def _in_year(date_str: Any, year: int) -> bool:
    return str(date_str)[:4] == f"{year:04d}"


def _month(date_str: Any) -> str:
    return str(date_str)[:7]


def _parse_date(value: Any) -> _dt.date:
    return _dt.date.fromisoformat(str(value)[:10])


def _is_completed(row: Mapping[str, Any], requirements: Mapping[str, Any]) -> bool:
    return bool(row.get("status") == requirements.get("status_filter", "completed"))


def oracle_simple_joins(
    requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]
) -> ExpectedResult:
    """Total completed-year revenue per customer (INNER JOIN, exclusions)."""
    year = int(requirements["year"])
    totals: dict[Any, float] = {}
    for order in tables["orders"]:
        if not _is_completed(order, requirements):
            continue
        if not _in_year(order["order_date"], year):
            continue
        totals[order["customer_id"]] = totals.get(order["customer_id"], 0.0) + float(
            order["amount"]
        )
    rows = [[cid, totals[cid]] for cid in totals]
    rows.sort(key=lambda r: (-r[1], r[0]))
    return ExpectedResult(
        columns=_out_cols(requirements),
        rows=rows,
        order=OrderSpec(type="ordered", keys=[("total_revenue", "desc")]),
    )


def oracle_multi_joins(
    requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]
) -> ExpectedResult:
    """Revenue per (customer, category) across the full join chain."""
    year = int(requirements["year"])
    valid_orders = {
        o["order_id"]
        for o in tables["orders"]
        if _is_completed(o, requirements) and _in_year(o["order_date"], year)
    }
    order_customer = {o["order_id"]: o["customer_id"] for o in tables["orders"]}
    price = {p["product_id"]: float(p["price"]) for p in tables["products"]}
    category = {p["product_id"]: p["category"] for p in tables["products"]}
    totals: dict[tuple[Any, Any], float] = {}
    for item in tables["order_items"]:
        if item["order_id"] not in valid_orders:
            continue
        key = (order_customer[item["order_id"]], category[item["product_id"]])
        totals[key] = totals.get(key, 0.0) + int(item["quantity"]) * price[item["product_id"]]
    rows = [[cid, cat, val] for (cid, cat), val in totals.items()]
    rows.sort(key=lambda r: (-r[2], r[0], str(r[1])))
    return ExpectedResult(
        columns=_out_cols(requirements),
        rows=rows,
        order=OrderSpec(type="ordered", keys=[("line_revenue", "desc")]),
    )


def oracle_aggregation(
    requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]
) -> ExpectedResult:
    """Per-status COUNT(*), SUM (skip NULL), AVG (skip NULL, else NULL)."""
    year = int(requirements["year"])
    groups: dict[Any, list[Any]] = {}
    for order in tables["orders"]:
        if not _in_year(order["order_date"], year):
            continue
        groups.setdefault(order["status"], []).append(order["amount"])
    rows = []
    for status in sorted(groups, key=str):
        amounts = groups[status]
        present = [float(a) for a in amounts if a is not None]
        # SQL semantics: SUM/AVG over zero non-NULL inputs is NULL, not 0.
        total: float | None = sum(present) if present else None
        avg = total / len(present) if present and total is not None else None
        rows.append([status, len(amounts), total, avg])
    return ExpectedResult(
        columns=_out_cols(requirements),
        rows=rows,
        order=OrderSpec(type="ordered", keys=[("status", "asc")]),
    )


def oracle_cte(
    requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]
) -> ExpectedResult:
    """Top revenue month per customer; ties break to the earliest month."""
    year = int(requirements["year"])
    monthly: dict[tuple[Any, str], float] = {}
    for order in tables["orders"]:
        if not _is_completed(order, requirements):
            continue
        if not _in_year(order["order_date"], year):
            continue
        key = (order["customer_id"], _month(order["order_date"]))
        monthly[key] = monthly.get(key, 0.0) + float(order["amount"])
    best: dict[Any, tuple[str, float]] = {}
    for (cid, month), revenue in monthly.items():
        current = best.get(cid)
        if (
            current is None
            or revenue > current[1]
            or (revenue == current[1] and month < current[0])
        ):
            best[cid] = (month, revenue)
    rows = [[cid, month, revenue] for cid, (month, revenue) in sorted(best.items())]
    return ExpectedResult(
        columns=_out_cols(requirements),
        rows=rows,
        order=OrderSpec(type="ordered", keys=[("customer_id", "asc")]),
    )


def oracle_subqueries(
    requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]
) -> ExpectedResult:
    """Customers with >=1 completed year-order strictly above the threshold."""
    year = int(requirements["year"])
    threshold = float(requirements["min_amount"])
    qualifying = {
        o["customer_id"]
        for o in tables["orders"]
        if _is_completed(o, requirements)
        and _in_year(o["order_date"], year)
        and float(o["amount"]) > threshold
    }
    names = {c["customer_id"]: c["name"] for c in tables["customers"]}
    rows = [[cid, names[cid]] for cid in sorted(qualifying)]
    return ExpectedResult(
        columns=_out_cols(requirements),
        rows=rows,
        order=OrderSpec(type="ordered", keys=[("customer_id", "asc")]),
    )


def oracle_windows(
    requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]
) -> ExpectedResult:
    """RANK with gaps over amount desc + running totals over (date, id)."""
    year = int(requirements["year"])
    partitions: dict[Any, list[dict[str, Any]]] = {}
    for order in tables["orders"]:
        if not _is_completed(order, requirements):
            continue
        if not _in_year(order["order_date"], year):
            continue
        partitions.setdefault(order["customer_id"], []).append(order)
    output_columns = _out_cols(requirements)
    rows = []
    for cid in sorted(partitions):
        members = partitions[cid]
        amounts = [float(o["amount"]) for o in members if o["amount"] is not None]
        ordered = sorted(members, key=lambda o: (str(o["order_date"]), o["order_id"]))
        running: float | None = None
        previous: float | None = None
        for order in ordered:
            raw_amount = order["amount"]
            amount = float(raw_amount) if raw_amount is not None else None
            rank = (
                1 + sum(1 for value in amounts if value > amount)
                if amount is not None
                else 1 + len(amounts)
            )
            if amount is not None:
                running = (running or 0.0) + amount
            values = {
                "customer_id": cid,
                "order_id": order["order_id"],
                "order_date": order["order_date"],
                "order_rank": rank,
                "running_total": running,
                "previous_amount": previous,
            }
            rows.append([values[column] for column in output_columns])
            previous = amount
    order_keys = [("customer_id", "asc")]
    if "order_date" in output_columns:
        order_keys.extend([("order_date", "asc"), ("order_id", "asc")])
    return ExpectedResult(
        columns=output_columns,
        rows=rows,
        order=OrderSpec(type="ordered", keys=order_keys),
    )


def oracle_temporal(
    requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]
) -> ExpectedResult:
    """Per-month order/event counts inside the inclusive window.

    Oracle interpretation (recorded): only months containing at least one
    order or event produce rows — matching natural GROUP BY semantics.
    """
    start = str(requirements["window_start"])
    end = str(requirements["window_end"])
    orders: dict[str, int] = {}
    for order in tables["orders"]:
        day = str(order["order_date"])
        if start <= day <= end:
            month = day[:7]
            orders[month] = orders.get(month, 0) + 1
    events: dict[str, int] = {}
    for event in tables["events"]:
        day = str(event["event_time"])[:10]
        if start <= day <= end:
            month = day[:7]
            events[month] = events.get(month, 0) + 1
    rows = [[m, orders.get(m, 0), events.get(m, 0)] for m in sorted(set(orders) | set(events))]
    return ExpectedResult(
        columns=_out_cols(requirements),
        rows=rows,
        order=OrderSpec(type="ordered", keys=[("activity_month", "asc")]),
    )


def oracle_dedup(
    requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]
) -> ExpectedResult:
    """Latest event per customer; timestamp ties go to the highest event_id."""
    best: dict[Any, dict[str, Any]] = {}
    for event in tables["events"]:
        cid = event["customer_id"]
        key = (str(event["event_time"]), event["event_id"])
        if cid not in best or key > (str(best[cid]["event_time"]), best[cid]["event_id"]):
            best[cid] = event
    rows = [[cid, best[cid]["event_type"], best[cid]["event_time"]] for cid in sorted(best)]
    return ExpectedResult(
        columns=_out_cols(requirements),
        rows=rows,
        order=OrderSpec(type="ordered", keys=[("customer_id", "asc")]),
    )


def oracle_retention(
    requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]
) -> ExpectedResult:
    """Retained iff a purchase falls in [signup, signup+window], inclusive."""
    window = int(requirements["retention_window_days"])
    qualifying = str(requirements["qualifying_event"])
    by_customer: dict[Any, list[dict[str, Any]]] = {}
    for event in tables["events"]:
        by_customer.setdefault(event["customer_id"], []).append(event)
    rows = []
    for customer in sorted(tables["customers"], key=lambda c: c["customer_id"]):
        signup = _parse_date(customer["signup_date"])
        retained = any(
            e["event_type"] == qualifying
            and signup <= _parse_date(e["event_time"]) <= signup + _dt.timedelta(days=window)
            for e in by_customer.get(customer["customer_id"], [])
        )
        rows.append([customer["customer_id"], retained])
    return ExpectedResult(
        columns=_out_cols(requirements),
        rows=rows,
        order=OrderSpec(type="ordered", keys=[("customer_id", "asc")]),
    )


def oracle_funnel(
    requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]
) -> ExpectedResult:
    """Longest ordered step-prefix per customer; first occurrences chain."""
    steps = [str(s) for s in requirements["funnel_steps"]]
    by_customer: dict[Any, list[dict[str, Any]]] = {}
    for event in tables["events"]:
        by_customer.setdefault(event["customer_id"], []).append(event)
    rows = []
    for customer in sorted(tables["customers"], key=lambda c: c["customer_id"]):
        events = sorted(
            by_customer.get(customer["customer_id"], []),
            key=lambda e: (str(e["event_time"]), e["event_id"]),
        )
        reached = 0
        for event in events:
            if reached < len(steps) and event["event_type"] == steps[reached]:
                reached += 1
        rows.append([customer["customer_id"], reached, reached == len(steps)])
    return ExpectedResult(
        columns=_out_cols(requirements),
        rows=rows,
        order=OrderSpec(type="ordered", keys=[("customer_id", "asc")]),
    )
