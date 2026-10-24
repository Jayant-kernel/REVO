"""Approved throughput@2 semantic, domain and separate HAVING structure evidence."""
from __future__ import annotations

from collections import Counter
from random import Random
from typing import Any

CONTRACT = "sql.aggregation.warehouse_throughput"
Tables = dict[str, list[dict[str, Any]]]
BEHAVIORS = ("threshold_equal", "below_threshold", "above_threshold", "zero", "negative_units",
             "negative_total", "duplicate_load", "unposted", "prior_year", "next_year",
             "jan_first", "dec_last", "split_threshold", "large_total")


def load(identifier: int, warehouse: str = "Threshold", units: int = 40,
         day: str = "2025-01-01", status: str = "posted") -> dict[str, Any]:
    return {"load_id": identifier, "warehouse": warehouse, "units": units, "loaded_on": day, "status": status}


def rich_fixture() -> Tables:
    repeated = load(5, "Bag", 20)
    return {"warehouse_loads": [load(1, units=22), load(2, units=18), load(3,"Over",50), load(4,"Over",-10),
        repeated, dict(repeated), load(6,"Below",39), load(7,"Zero",0), load(8,"Neg",40),load(9,"Neg",-100),
        load(10,"Old",100,"2024-12-31"), load(11,"Future",100,"2026-01-01"),load(12,"Failed",100,status="failed"),
        load(13,"January",40), load(14,"December",40,"2025-12-31"),
        load(15,"Large",2147483647), load(16,"Large",2147483647)]}


def alternatives(reference: str) -> list[str]:
    condition = "status='posted' AND EXTRACT(YEAR FROM loaded_on)=2025"
    return [reference,
        ("WITH scoped AS (SELECT warehouse,units FROM warehouse_loads WHERE "+condition+
         ") SELECT warehouse,SUM(units) AS total_units FROM scoped GROUP BY warehouse HAVING SUM(units)>=40 ORDER BY warehouse"),
        ("SELECT warehouse,SUM(CASE WHEN "+condition+" THEN CAST(units AS HUGEINT) ELSE 0 END) AS total_units "
         "FROM warehouse_loads GROUP BY warehouse HAVING SUM(CASE WHEN "+condition+
         " THEN CAST(units AS HUGEINT) ELSE 0 END)>=40 ORDER BY warehouse")]


def equivalent_without_having() -> str:
    return ("WITH totals AS (SELECT warehouse,SUM(units) AS total_units FROM warehouse_loads "
            "WHERE status='posted' AND EXTRACT(YEAR FROM loaded_on)=2025 GROUP BY warehouse) "
            "SELECT warehouse,total_units FROM totals WHERE total_units>=40 ORDER BY warehouse")


def failures(reference: str) -> dict[str, str]:
    return {
        "absolute_units": reference.replace("SUM(units)","SUM(ABS(units))"),
        "average_not_sum": reference.replace("SUM(units)","AVG(units)"),
        "count_not_units": reference.replace("SUM(units)","COUNT(*)"),
        "max_not_sum": reference.replace("SUM(units)","MAX(units)"),
        "min_not_sum": reference.replace("SUM(units)","MIN(units)"),
        "distinct_loses_bag": reference.replace("SUM(units)","SUM(DISTINCT units)"),
        "equal_excluded": reference.replace(">= 40","> 40"),
        "below_included": reference.replace(">= 40",">= 39"),
        "zero_included": reference.replace(">= 40",">= 0"),
        "negative_group_included": reference.replace(">= 40",">= -100"),
        "only_exact_threshold": reference.replace(">= 40","= 40"),
        "wrong_direction": reference.replace(">= 40","<= 40"),
        "having_dropped": reference.replace("HAVING SUM(units) >= 40", ""),
        "row_filter_instead": reference.replace("WHERE status", "WHERE units>=40 AND status"),
        "all_statuses": reference.replace("status='posted'", "TRUE"),
        "failed_only": reference.replace("status='posted'", "status='failed'"),
        "all_years": reference.replace("EXTRACT(YEAR FROM loaded_on)=2025", "TRUE"),
        "prior_year_only": reference.replace("=2025", "=2024"),
        "jan_excluded": reference.replace("EXTRACT(YEAR FROM loaded_on)=2025", "loaded_on>DATE '2025-01-01' AND loaded_on<DATE '2026-01-01'"),
        "next_jan_included": reference.replace("EXTRACT(YEAR FROM loaded_on)=2025", "loaded_on>=DATE '2025-01-01' AND loaded_on<=DATE '2026-01-01'"),
        "last_day_excluded": reference.replace("EXTRACT(YEAR FROM loaded_on)=2025", "loaded_on>=DATE '2025-01-01' AND loaded_on<DATE '2025-12-31'"),
        "wrong_units_name": reference.replace("AS total_units", "AS wrong_total"),
        "text_units": reference.replace("SELECT warehouse, SUM(units)", "SELECT warehouse, CAST(SUM(units) AS VARCHAR)"),
        "reverse_order": reference.replace("ORDER BY warehouse ASC", "ORDER BY warehouse DESC"),
        "truncated_warehouses": reference+" LIMIT 1",
        "first_letter_groups": reference.replace("SELECT warehouse,", "SELECT substr(warehouse,1,1) AS warehouse,").replace("GROUP BY warehouse", "GROUP BY substr(warehouse,1,1)"),
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective":"absolute_units","year":"all_years","status_filter":"all_statuses","group_by":"first_letter_groups",
            "count_semantics":"distinct_loses_bag","empty_group_behavior":"all_statuses",
            "aggregation_filter":"row_filter_instead","min_total_units":"equal_excluded",
            "output_columns":"wrong_units_name","order_by":"reverse_order","zero_negative":"zero_included"}
    result = {key:{"witness":rich_fixture(),"wrong_sql":wrong[label],"outcome":"UNEXECUTED_RULE_SPEC"} for key,label in keys.items()}
    result["null_handling"] = {"witness":{"warehouse_loads":[{**load(1),"units":None}]},"outcome":"UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    result["having_structure"] = {"witness":rich_fixture(),"wrong_sql":equivalent_without_having(),"outcome":"UNEXECUTED_RULE_SPEC"}
    return result


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(wrong,rich_fixture()) for wrong in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str,str,Tables]]:
    baseline = {"warehouse_loads":[load(1,units=40)]}
    wrong = failures(reference)
    return [("THROUGHPUT_POSTED_DUPLICATE",wrong["distinct_loses_bag"],baseline),
            ("THROUGHPUT_FAILED_ROW",wrong["all_statuses"],baseline)]


def fixture(seed: int,index: int) -> Tables:
    rng = Random(f"throughput:2:{seed}:{index}")
    tables = rich_fixture()
    tables["warehouse_loads"].extend(load(identifier,f"Random-{rng.randrange(5)}",rng.randint(-100,100),
        rng.choice(["2024-12-31","2025-01-01","2025-06-15","2025-12-31","2026-01-01"]),
        rng.choice(["posted","failed","pending"])) for identifier in range(200,rng.randint(201,261)))
    rng.shuffle(tables["warehouse_loads"])
    return tables


def observed(tables: Tables) -> tuple[str,tuple[str,...],set[str]]:
    found: set[str] = set()
    totals: dict[str,int] = {}
    eligible: dict[str,list[int]] = {}
    for row in tables["warehouse_loads"]:
        day = str(row["loaded_on"])
        if row["status"] != "posted":
            found.add("unposted")
        if day[:4]<"2025":
            found.add("prior_year")
        elif day[:4]>"2025":
            found.add("next_year")
        if day=="2025-01-01":
            found.add("jan_first")
        if day=="2025-12-31":
            found.add("dec_last")
        if row["units"]==0:
            found.add("zero")
        if row["units"]<0:
            found.add("negative_units")
        if row["status"]=="posted" and day[:4]=="2025":
            totals[row["warehouse"]] = totals.get(row["warehouse"],0)+row["units"]
            eligible.setdefault(row["warehouse"],[]).append(row["units"])
    for name,total in totals.items():
        found.add("threshold_equal" if total==40 else "above_threshold" if total>40 else "below_threshold")
        if total<0:
            found.add("negative_total")
        if total>2147483647:
            found.add("large_total")
        if total>=40 and all(units<40 for units in eligible[name]):
            found.add("split_threshold")
    if any(count>1 for count in Counter(tuple(sorted(row.items())) for row in tables["warehouse_loads"]).values()):
        found.add("duplicate_load")
    return "throughput-observed-v2",BEHAVIORS,found
