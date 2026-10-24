"""Declared final-leg selection, full inner-join bags and calendar boundaries@1."""
from __future__ import annotations

from collections import Counter
from random import Random
from typing import Any

CONTRACT = "sql.joins.logistics_final_leg"
Tables = dict[str, list[dict[str, Any]]]
BEHAVIORS = ("qualifying", "jan_first", "dec_last", "prior_year", "next_year",
             "undelivered", "null_final_leg", "missing_leg", "null_carrier",
             "missing_carrier", "duplicate_shipment", "duplicate_leg",
             "duplicate_carrier", "declared_not_largest_leg")


def shipment(identifier: int, leg: int | None = 10, day: str | None = "2025-06-15") -> dict[str, Any]:
    return {"shipment_id": identifier, "final_leg_id": leg, "delivered_on": day}


def rich_fixture() -> Tables:
    first = shipment(1, day="2025-01-01")
    leg = {"leg_id": 10, "carrier_id": 20, "depot": "West"}
    carrier = {"carrier_id": 20, "carrier_name": "Road"}
    return {
        "shipments": [first, dict(first), shipment(2, day="2025-12-31"),
            shipment(3, day="2024-12-31"), shipment(4, day="2026-01-01"),
            shipment(5, day=None), shipment(6, None), shipment(7, 999),
            shipment(8, 11), shipment(9, 12), shipment(10, 13)],
        "legs": [leg, dict(leg), {"leg_id": 11, "carrier_id": None, "depot": "Null"},
            {"leg_id": 12, "carrier_id": 999, "depot": "Missing"},
            {"leg_id": 13, "carrier_id": 21, "depot": "East"},
            {"leg_id": 90, "carrier_id": 21, "depot": "Unused"}],
        "carriers": [carrier, dict(carrier), {"carrier_id": 21, "carrier_name": "Rail"}],
    }


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("WITH delivered AS (SELECT * FROM shipments WHERE EXTRACT(YEAR FROM delivered_on)=2025), "
         "responsibility AS (SELECT l.leg_id, l.depot, c.carrier_name FROM legs l "
         "INNER JOIN carriers c ON c.carrier_id=l.carrier_id) "
         "SELECT s.shipment_id, r.depot, r.carrier_name FROM delivered s "
         "INNER JOIN responsibility r ON r.leg_id=s.final_leg_id ORDER BY s.shipment_id"),
        ("SELECT s.shipment_id, r.depot, r.carrier_name FROM shipments s "
         "INNER JOIN LATERAL (SELECT l.depot, c.carrier_name FROM legs l "
         "INNER JOIN carriers c ON c.carrier_id=l.carrier_id WHERE l.leg_id=s.final_leg_id) r ON TRUE "
         "WHERE s.delivered_on BETWEEN DATE '2025-01-01' AND DATE '2025-12-31' ORDER BY s.shipment_id")]


def failures(reference: str) -> dict[str, str]:
    return {
        "uncorrelated_leg": reference.replace("s.final_leg_id=l.leg_id", "TRUE"),
        "shipment_as_leg": reference.replace("s.final_leg_id=l.leg_id", "s.shipment_id=l.leg_id"),
        "largest_leg": reference.replace("s.final_leg_id=l.leg_id", "l.leg_id=(SELECT MAX(leg_id) FROM legs)"),
        "uncorrelated_carrier": reference.replace("l.carrier_id=c.carrier_id", "TRUE"),
        "leg_as_carrier": reference.replace("l.carrier_id=c.carrier_id", "l.leg_id=c.carrier_id"),
        "shipment_as_carrier": reference.replace("l.carrier_id=c.carrier_id", "s.shipment_id=c.carrier_id"),
        "missing_leg_included": reference.replace("JOIN legs", "LEFT JOIN legs").replace("JOIN carriers", "LEFT JOIN carriers"),
        "missing_carrier_included": reference.replace("JOIN carriers", "LEFT JOIN carriers"),
        "prior_year_included": reference.replace("s.delivered_on >= DATE '2025-01-01'", "TRUE"),
        "next_year_included": reference.replace("s.delivered_on < DATE '2026-01-01'", "TRUE"),
        "jan_first_excluded": reference.replace(">= DATE '2025-01-01'", "> DATE '2025-01-01'"),
        "next_jan_included": reference.replace("< DATE '2026-01-01'", "<= DATE '2026-01-01'"),
        "last_day_excluded": reference.replace("< DATE '2026-01-01'", "< DATE '2025-12-31'"),
        "undelivered_included": reference.replace("WHERE s.delivered_on", "WHERE s.delivered_on IS NULL OR s.delivered_on"),
        "distinct_loses_bag": reference.replace("SELECT s.shipment_id", "SELECT DISTINCT s.shipment_id"),
        "leg_id_projection": reference.replace("SELECT s.shipment_id", "SELECT l.leg_id AS shipment_id"),
        "depot_as_carrier": reference.replace("l.depot, c.carrier_name", "l.depot, l.depot AS carrier_name"),
        "carrier_as_depot": reference.replace("l.depot, c.carrier_name", "c.carrier_name AS depot, c.carrier_name"),
        "id_as_text": reference.replace("SELECT s.shipment_id", "SELECT CAST(s.shipment_id AS VARCHAR) AS shipment_id"),
        "revenue_added": reference.replace("c.carrier_name FROM", "c.carrier_name, 0 AS revenue FROM"),
        "reverse_order": reference.replace("ORDER BY s.shipment_id", "ORDER BY s.shipment_id DESC"),
        "carrier_order": reference.replace("ORDER BY s.shipment_id", "ORDER BY c.carrier_name, s.shipment_id DESC"),
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "shipment_as_leg", "declared_leg": "largest_leg",
            "carrier_correlation": "uncorrelated_carrier", "year": "prior_year_included",
            "status_filter": "undelivered_included", "join_type": "missing_leg_included",
            "unmatched_behavior": "missing_carrier_included", "line_revenue_def": "revenue_added",
            "output_columns": "id_as_text", "order_by": "reverse_order",
            "bag": "distinct_loses_bag", "null_delivery": "undelivered_included"}
    return {key: {"witness": rich_fixture(), "wrong_sql": wrong[label],
                  "outcome": "UNEXECUTED_RULE_SPEC"} for key, label in keys.items()}


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(wrong, rich_fixture()) for wrong in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"shipments": [shipment(1)],
                "legs": [{"leg_id": 10, "carrier_id": 20, "depot": "West"}],
                "carriers": [{"carrier_id": 20, "carrier_name": "Road"}]}
    wrong = failures(reference)
    return [("FINAL_LEG_DUPLICATE", wrong["distinct_loses_bag"], baseline),
            ("FINAL_LEG_UNDELIVERED", wrong["undelivered_included"], baseline)]


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"final-leg:1:{seed}:{index}")
    tables = rich_fixture()
    tables["shipments"].extend(shipment(identifier, rng.choice([10, 11, 12, 13, 90, 999, None]),
        rng.choice(["2024-12-31", "2025-01-01", "2025-06-15", "2025-12-31", "2026-01-01", None]))
        for identifier in range(200, rng.randint(201, 261)))
    # Random fanout and different payloads, beyond the fixed boundary scaffold.
    for identifier in (10, 13):
        tables["legs"].extend({"leg_id": identifier, "carrier_id": rng.choice([20, 21, 999, None]),
            "depot": f"depot-{rng.randrange(5)}"} for _ in range(rng.randrange(5)))
    tables["carriers"].extend({"carrier_id": rng.choice([20, 21]), "carrier_name": f"carrier-{rng.randrange(5)}"}
                              for _ in range(rng.randrange(5)))
    for rows in tables.values():
        rng.shuffle(rows)
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    found: set[str] = set()
    legs, carriers = tables["legs"], tables["carriers"]
    for row in tables["shipments"]:
        day = str(row["delivered_on"])
        if row["delivered_on"] is None:
            found.add("undelivered")
        elif day[:4] < "2025":
            found.add("prior_year")
        elif day[:4] > "2025":
            found.add("next_year")
        if day == "2025-01-01":
            found.add("jan_first")
        if day == "2025-12-31":
            found.add("dec_last")
        matches = [leg for leg in legs if leg["leg_id"] == row["final_leg_id"]]
        if row["final_leg_id"] is None:
            found.add("null_final_leg")
        elif not matches:
            found.add("missing_leg")
        for leg in matches:
            matches_carrier = [carrier for carrier in carriers if carrier["carrier_id"] == leg["carrier_id"]]
            if leg["carrier_id"] is None:
                found.add("null_carrier")
            elif not matches_carrier:
                found.add("missing_carrier")
            if day[:4] == "2025" and matches_carrier:
                found.add("qualifying")
                if leg["leg_id"] != max(item["leg_id"] for item in legs):
                    found.add("declared_not_largest_leg")
    for name, label in (("shipments", "duplicate_shipment"), ("legs", "duplicate_leg"),
                        ("carriers", "duplicate_carrier")):
        if any(count > 1 for count in Counter(tuple(sorted(row.items())) for row in tables[name]).values()):
            found.add(label)
    return "final-leg-observed-v1", BEHAVIORS, found
