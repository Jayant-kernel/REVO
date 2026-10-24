"""Completed header-versus-line reconciliation, preserving header and line bags@1."""
from __future__ import annotations

from collections import Counter
from random import Random
from typing import Any

CONTRACT = "sql.cte.order_line_reconciliation"
Tables = dict[str, list[dict[str, Any]]]
BEHAVIORS = ("mismatch", "match", "no_lines", "zero_header_no_lines", "excluded_status", "prior_year",
             "next_year", "jan_first", "dec_last", "duplicate_header", "duplicate_line", "orphan_line",
             "negative_quantity", "negative_price", "zero_quantity", "multiple_lines")


def order(identifier: int, total: int = 99, day: str = "2025-01-01", status: str = "completed") -> dict[str, Any]:
    return {"order_id": identifier, "header_total_cents": total, "ordered_on": day, "order_status": status}


def line(identifier: int, owner: int = 1, quantity: int = 2, price: int = 7) -> dict[str, Any]:
    return {"line_id": identifier, "order_id": owner, "quantity": quantity, "unit_price_cents": price}


def rich_fixture() -> Tables:
    header = order(1)
    repeated = line(1)
    return {"orders": [header, dict(header), order(2, 14), order(3, 77), order(4, 0),
        order(5, status="cancelled"), order(6, day="2024-12-31"), order(7, day="2026-01-01"),
        order(8, day="2025-12-31"), order(9, 77), order(10, 77)],
        "order_lines": [repeated, dict(repeated), line(2, 1, 3, 11), line(3, 2),
            line(4, 5), line(5, 6), line(6, 7), line(7, 8, -3, 5), line(8, 8, 2, -7),
            line(9, 8, 0, 999), line(10, 99), line(11, 9, 2, 2147483647),
            line(12, 10, -2147483648, -2147483648)]}


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("WITH scoped AS (SELECT * FROM orders WHERE order_status='completed' AND ordered_on "
         "BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'), reconciled AS "
         "(SELECT o.*,COALESCE((SELECT SUM(CAST(l.quantity AS HUGEINT)*l.unit_price_cents) "
         "FROM order_lines l WHERE l.order_id=o.order_id),0) AS line_total_cents FROM scoped o) "
         "SELECT order_id,header_total_cents,line_total_cents FROM reconciled "
         "WHERE header_total_cents<>line_total_cents ORDER BY order_id"),
        ("WITH reconciled AS (SELECT o.order_id,o.header_total_cents,l.line_total_cents FROM orders o "
         "INNER JOIN LATERAL (SELECT COALESCE(SUM(CAST(quantity AS HUGEINT)*unit_price_cents),0) AS line_total_cents "
         "FROM order_lines WHERE order_id=o.order_id) l ON TRUE "
         "WHERE o.order_status='completed' AND EXTRACT(YEAR FROM o.ordered_on)=2025) "
         "SELECT * FROM reconciled WHERE header_total_cents<>line_total_cents ORDER BY order_id")]


def failures(reference: str) -> dict[str, str]:
    product = "CAST(quantity AS HUGEINT) * unit_price_cents"
    return {
        "price_only": reference.replace(product, "unit_price_cents"),
        "quantity_only": reference.replace(product, "quantity"),
        "add_not_multiply": reference.replace(product, "CAST(quantity AS HUGEINT) + unit_price_cents"),
        "absolute_product": reference.replace(product, f"ABS({product})"),
        "distinct_products": reference.replace(f"SUM({product})", f"SUM(DISTINCT {product})"),
        "maximum_line": reference.replace(f"SUM({product})", f"MAX({product})"),
        "count_lines": reference.replace(f"SUM({product})", "COUNT(*)"),
        "negative_quantity_excluded": reference.replace("FROM order_lines GROUP", "FROM order_lines WHERE quantity>=0 GROUP"),
        "negative_price_excluded": reference.replace("FROM order_lines GROUP", "FROM order_lines WHERE unit_price_cents>=0 GROUP"),
        "positive_price_only": reference.replace("FROM order_lines GROUP", "FROM order_lines WHERE unit_price_cents>0 AND quantity>0 GROUP"),
        "wrong_correlation": reference.replace("l.order_id=o.order_id", "l.order_id=o.header_total_cents"),
        "inner_join_loses_empty": reference.replace("LEFT JOIN", "INNER JOIN"),
        "empty_default_one": reference.replace("COALESCE(l.line_total_cents,0)", "COALESCE(l.line_total_cents,1)"),
        "matches_included": reference.replace("o.header_total_cents<>", "o.header_total_cents="),
        "only_understated": reference.replace("o.header_total_cents<>", "o.header_total_cents<"),
        "only_overstated": reference.replace("o.header_total_cents<>", "o.header_total_cents>"),
        "all_statuses": reference.replace("o.order_status='completed'", "TRUE"),
        "all_years": reference.replace("EXTRACT(YEAR FROM o.ordered_on)=2025", "TRUE"),
        "lower_excluded": reference.replace("EXTRACT(YEAR FROM o.ordered_on)=2025", "o.ordered_on>DATE '2025-01-01' AND o.ordered_on<DATE '2026-01-01'"),
        "upper_included": reference.replace("EXTRACT(YEAR FROM o.ordered_on)=2025", "o.ordered_on>=DATE '2025-01-01' AND o.ordered_on<=DATE '2026-01-01'"),
        "last_day_excluded": reference.replace("EXTRACT(YEAR FROM o.ordered_on)=2025", "o.ordered_on>=DATE '2025-01-01' AND o.ordered_on<DATE '2025-12-31'"),
        "header_bag_collapsed": reference.replace("SELECT o.order_id", "SELECT DISTINCT o.order_id"),
        "reverse_order": reference.replace("ORDER BY o.order_id ASC", "ORDER BY o.order_id DESC"),
        "id_as_text": reference.replace("SELECT o.order_id", "SELECT CAST(o.order_id AS VARCHAR) AS order_id"),
        "line_total_as_header": reference.replace("o.order_id,o.header_total_cents,", "o.order_id,COALESCE(l.line_total_cents,0) AS header_total_cents,"),
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "matches_included", "product": "price_only", "year": "all_years",
            "status_filter": "all_statuses", "top_tie_break": "reverse_order",
            "unmatched_behavior": "inner_join_loses_empty", "output_columns": "id_as_text",
            "order_by": "reverse_order", "bag": "header_bag_collapsed", "line_bag": "distinct_products"}
    return {key: {"witness": rich_fixture(), "wrong_sql": wrong[label], "outcome": "UNEXECUTED_RULE_SPEC"}
            for key, label in keys.items()}


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(wrong, rich_fixture()) for wrong in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"orders": [order(1)], "order_lines": [line(1)]}
    wrong = failures(reference)
    return [("RECONCILIATION_HEADER_DUPLICATE", wrong["header_bag_collapsed"], baseline),
            ("RECONCILIATION_LINE_DUPLICATE", wrong["distinct_products"], baseline)]


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"reconciliation:1:{seed}:{index}")
    tables = rich_fixture()
    for owner in range(100, rng.randint(101, 121)):
        tables["orders"].append(order(owner, rng.randint(-1000, 1000),
            rng.choice(["2024-12-31", "2025-01-01", "2025-06-15", "2025-12-31", "2026-01-01"]),
            rng.choice(["completed", "open", "cancelled"])))
        tables["order_lines"].extend(line(len(tables["order_lines"])+i+200, owner,
            rng.randint(-10, 10), rng.randint(-1000, 1000)) for i in range(rng.randrange(8)))
    for rows in tables.values():
        rng.shuffle(rows)
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    found: set[str] = set()
    totals: dict[int, int] = {}
    for row in tables["order_lines"]:
        owner = row["order_id"]
        totals[owner] = totals.get(owner, 0) + row["quantity"]*row["unit_price_cents"]
        if row["quantity"] < 0:
            found.add("negative_quantity")
        if row["unit_price_cents"] < 0:
            found.add("negative_price")
        if row["quantity"] == 0:
            found.add("zero_quantity")
    if totals.keys() - {row["order_id"] for row in tables["orders"]}:
        found.add("orphan_line")
    if any(count > 1 for count in Counter(row["order_id"] for row in tables["order_lines"]).values()):
        found.add("multiple_lines")
    for row in tables["orders"]:
        day = str(row["ordered_on"])
        if row["order_status"] != "completed":
            found.add("excluded_status")
        if day[:4] < "2025":
            found.add("prior_year")
        elif day[:4] > "2025":
            found.add("next_year")
        if day == "2025-01-01":
            found.add("jan_first")
        if day == "2025-12-31":
            found.add("dec_last")
        if row["order_status"] == "completed" and day[:4] == "2025":
            found.add("match" if row["header_total_cents"] == totals.get(row["order_id"], 0) else "mismatch")
            if row["order_id"] not in totals:
                found.add("no_lines")
                if row["header_total_cents"] == 0:
                    found.add("zero_header_no_lines")
    for name, label in (("orders", "duplicate_header"), ("order_lines", "duplicate_line")):
        if any(count > 1 for count in Counter(tuple(sorted(row.items())) for row in tables[name]).values()):
            found.add(label)
    return "reconciliation-observed-v1", BEHAVIORS, found
