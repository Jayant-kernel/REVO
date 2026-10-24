"""Approved inventory input-row bags, signed corrections and INTEGER boundaries@2."""
from __future__ import annotations

from collections import Counter
from random import Random
from typing import Any

CONTRACT = "sql.cte.inventory_net_flow"
Tables = dict[str, list[dict[str, Any]]]
BEHAVIORS = ("receipt", "issue", "receipt_only", "issue_only", "negative_units", "zero_units",
             "zero_net", "duplicate_payload", "repeated_id", "prior_year", "next_year", "unposted",
             "jan_first", "last_day", "minimum_integer", "maximum_integer", "multiple_warehouses")


def movement(identifier: int, warehouse: str = "A", units: int = 10, *,
             day: str = "2025-01-01", status: str = "posted") -> dict[str, Any]:
    return {"movement_id": identifier, "warehouse": warehouse, "units": units,
            "occurred_on": day, "status": status}


def rich_fixture() -> Tables:
    return {"receipts": [movement(1), movement(1), movement(1, units=7, day="2025-12-31"),
                movement(2,"zero",0), movement(3,"balanced",5), movement(4,"receipt-only",11),
                movement(5,"correction",-4), movement(6,"old",123,day="2024-12-31"),
                movement(7,"future",123,day="2026-01-01"), movement(8,"not-posted",123,status="failed"),
                movement(9,"max",2147483647)],
            "issues": [movement(1,units=3), movement(1,units=3), movement(2,"balanced",5),
                movement(3,"issue-only",7), movement(4,"correction",-8), movement(5,"min",-2147483648),
                movement(6,"old",2,day="2024-12-31"), movement(7,"future",2,day="2026-01-01"),
                movement(8,"not-posted",10,status="failed"), movement(9,"late",3,day="2025-12-31")]}


def alternatives(reference: str) -> list[str]:
    scoped = "status='posted' AND EXTRACT(YEAR FROM occurred_on)=2025"
    return [reference,
        (f"WITH r AS (SELECT warehouse,SUM(CAST(units AS HUGEINT)) AS total FROM receipts WHERE {scoped} GROUP BY warehouse), "
         f"i AS (SELECT warehouse,SUM(CAST(units AS HUGEINT)) AS total FROM issues WHERE {scoped} GROUP BY warehouse) "
         "SELECT COALESCE(r.warehouse,i.warehouse) AS warehouse,COALESCE(r.total,0)-COALESCE(i.total,0) AS net_units "
         "FROM r FULL OUTER JOIN i ON r.warehouse=i.warehouse ORDER BY warehouse"),
        (f"WITH warehouses AS (SELECT warehouse FROM receipts WHERE {scoped} UNION SELECT warehouse FROM issues WHERE {scoped}) "
         "SELECT w.warehouse,COALESCE((SELECT SUM(CAST(r.units AS HUGEINT)) FROM receipts r WHERE r.warehouse=w.warehouse "
         "AND r.status='posted' AND r.occurred_on>=DATE '2025-01-01' AND r.occurred_on<DATE '2026-01-01'),0) "
         "-COALESCE((SELECT SUM(CAST(i.units AS HUGEINT)) FROM issues i WHERE i.warehouse=w.warehouse AND i.status='posted' "
         "AND i.occurred_on>=DATE '2025-01-01' AND i.occurred_on<DATE '2026-01-01'),0) AS net_units FROM warehouses w ORDER BY w.warehouse")]


def _last(sql: str, old: str, new: str) -> str:
    before, marker, after = sql.rpartition(old)
    if not marker:
        raise ValueError("source-bound inventory reference changed")
    return before+new+after


def failures(reference: str) -> dict[str, str]:
    year = "EXTRACT(YEAR FROM occurred_on)=2025"
    return {
        "issues_added": reference.replace("-CAST(units AS HUGEINT)", "CAST(units AS HUGEINT)"),
        "receipts_subtracted": reference.replace("CAST(units AS HUGEINT) AS units", "-CAST(units AS HUGEINT) AS units",1),
        "receipt_status_ignored": reference.replace("status='posted'", "TRUE",1),
        "issue_status_ignored": _last(reference,"status='posted'","TRUE"),
        "failed_only": reference.replace("status='posted'", "status='failed'"),
        "receipt_year_ignored": reference.replace(year,"TRUE",1),
        "issue_year_ignored": _last(reference,year,"TRUE"),
        "prior_year_only": reference.replace(year,"EXTRACT(YEAR FROM occurred_on)=2024"),
        "jan_first_excluded": reference.replace(year,year+" AND occurred_on>DATE '2025-01-01'"),
        "last_day_excluded": reference.replace(year,year+" AND occurred_on<DATE '2025-12-31'"),
        "next_jan_included": reference.replace(year,"("+year+" OR occurred_on=DATE '2026-01-01')"),
        "union_collapse": reference.replace("UNION ALL","UNION"),
        "sum_distinct": reference.replace("SUM(units)","SUM(DISTINCT units)"),
        "inner_join": alternatives(reference)[1].replace("FULL OUTER JOIN","INNER JOIN"),
        "zero_net_omitted": reference.replace("ORDER BY warehouse ASC","HAVING SUM(units)<>0 ORDER BY warehouse ASC"),
        "negative_net_omitted": reference.replace("ORDER BY warehouse ASC","HAVING SUM(units)>=0 ORDER BY warehouse ASC"),
        "count_instead_units": reference.replace("SUM(units)","CAST(COUNT(*) AS HUGEINT)"),
        "absolute_units": reference.replace("SUM(units)","SUM(ABS(units))"),
        "net_plus_one": reference.replace("SUM(units)","SUM(units)+1"),
        "net_doubled": reference.replace("SUM(units)","SUM(units)*2"),
        "net_zeroed": reference.replace("SUM(units)","SUM(units)*0"),
        "id_instead_units": reference.replace("CAST(units AS HUGEINT)","CAST(movement_id AS HUGEINT)"),
        "wrong_output_name": reference.replace("AS net_units","AS wrong_units"),
        "text_units": reference.replace("SUM(units)","CAST(SUM(units) AS VARCHAR)"),
        "reverse_order": reference.replace("ORDER BY warehouse ASC","ORDER BY warehouse DESC"),
        "first_only": reference+" LIMIT 1",
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "issues_added", "year": "receipt_year_ignored", "status_filter": "receipt_status_ignored",
            "top_tie_break": "first_only", "unmatched_behavior": "inner_join", "count_semantics": "union_collapse",
            "signed_units": "absolute_units", "empty_group_behavior": "zero_net_omitted", "output_columns": "text_units",
            "order_by": "reverse_order", "issue_scope": "issue_status_ignored", "window_end": "next_jan_included"}
    return {key: {"witness": rich_fixture(), "wrong_sql": wrong[label], "outcome": "UNEXECUTED_RULE_SPEC"}
            for key, label in keys.items()}


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(sql,rich_fixture()) for sql in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str,str,Tables]]:
    baseline = {"receipts": [movement(1)], "issues": []}
    wrong = failures(reference)
    return [("INVENTORY_RECEIPT_REPEAT",wrong["union_collapse"],baseline),
            ("INVENTORY_UNPOSTED_ISSUE",wrong["issue_status_ignored"],baseline)]


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"inventory-row-bag:2:{seed}:{index}")
    tables = rich_fixture()
    for rows in tables.values():
        rows.extend(movement(rng.randrange(5), rng.choice(["A","B","C","zero","balanced"]),
            rng.choice([-2147483648,-12,0,3,9,2147483647]),
            day=rng.choice(["2024-12-31","2025-01-01","2025-06-01","2025-12-31","2026-01-01"]),
            status=rng.choice(["posted","failed","pending"])) for _ in range(rng.randint(1,(8,30,80)[index%3])))
        rng.shuffle(rows)
    return tables


def observed(tables: Tables) -> tuple[str,tuple[str,...],set[str]]:
    found: set[str] = set()
    eligible = {name: [row for row in tables[name] if row["status"] == "posted" and str(row["occurred_on"])[:4] == "2025"]
                for name in ("receipts","issues")}
    warehouses = {name: {row["warehouse"] for row in rows} for name,rows in eligible.items()}
    if eligible["receipts"]:
        found.add("receipt")
    if eligible["issues"]:
        found.add("issue")
    if warehouses["receipts"]-warehouses["issues"]:
        found.add("receipt_only")
    if warehouses["issues"]-warehouses["receipts"]:
        found.add("issue_only")
    all_warehouses = warehouses["receipts"] | warehouses["issues"]
    if len(all_warehouses)>1:
        found.add("multiple_warehouses")
    for warehouse in all_warehouses:
        if sum(row["units"] for row in eligible["receipts"] if row["warehouse"] == warehouse) == sum(row["units"] for row in eligible["issues"] if row["warehouse"] == warehouse):
            found.add("zero_net")
    for name,rows in tables.items():
        if any(count>1 for count in Counter(tuple(sorted(row.items())) for row in rows).values()):
            found.add("duplicate_payload")
        if any(count>1 for count in Counter(row["movement_id"] for row in rows).values()):
            found.add("repeated_id")
        for row in rows:
            day = str(row["occurred_on"])
            if day[:4]<"2025":
                found.add("prior_year")
            if day[:4]>"2025":
                found.add("next_year")
            if row["status"] != "posted":
                found.add("unposted")
            if row not in eligible[name]:
                continue
            if row["units"]<0:
                found.add("negative_units")
            if row["units"] == 0:
                found.add("zero_units")
            if row["units"] == -2147483648:
                found.add("minimum_integer")
            if row["units"] == 2147483647:
                found.add("maximum_integer")
            if day == "2025-01-01":
                found.add("jan_first")
            if day == "2025-12-31":
                found.add("last_day")
    return "inventory-net-flow-observed-v2",BEHAVIORS,found
