"""Explicit retained-fuzz observation policies for supported profiles.

These classify fixture content, not generator labels or qualification summaries.
The policy names are versioned independently from receipt schema versions.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from random import Random
from typing import Any

SAAS_BEHAVIORS = (
    "completed", "incomplete", "repeated_steps", "skipped_steps", "early_later_steps",
    "same_timestamp_ties", "cancelled", "year_boundaries", "zero_completion_groups",
    "out_of_scope_only_groups", "multiple_entities", "multiple_groups",
)
SCRAP_BEHAVIORS = (
    "multiple_groups", "negative_amounts", "zero_amounts", "excluded_status",
    "excluded_year", "eligible_rows",
)
SLA_BEHAVIORS = ("multiple_warehouses", "delivered", "cancelled", "unresolved", "excluded_year",
                 "deadline_equal", "on_time", "late")


def observation_fixture(
    contract: str, version: int, seed: int, index: int,
) -> dict[str, list[dict[str, Any]]]:
    """Source-bound deterministic recipes used by the existing profile campaigns."""
    from .qualification.delivery_profiles import get_profile

    profile = get_profile(contract, version)
    if profile is not None:
        result: dict[str, list[dict[str, Any]]] = profile.fixture(seed, index)
        return result
    if (contract, version) == ("sql.dedup.lowest_quote", 1):
        from .qualification.lowest_quote_profile import fixture as quote_fixture

        return quote_fixture(seed, index)
    if (contract, version) == ("sql.cte.inventory_net_flow", 2):
        from .qualification.inventory_flow_profile import fixture as inventory_fixture

        return inventory_fixture(seed, index)
    if (contract, version) == ("sql.subqueries.education_all_required", 1):
        from .qualification.required_courses_profile import fixture as required_fixture

        return required_fixture(seed, index)
    if (contract, version) == ("sql.aggregation.warehouse_throughput", 2):
        from .qualification.throughput_profile import fixture as throughput_fixture

        return throughput_fixture(seed, index)
    if (contract, version) == ("sql.dedup.education_grade_revisions", 2):
        from .qualification.grade_revisions_profile import fixture as grade_fixture

        return grade_fixture(seed, index)
    if (contract, version) == ("sql.aggregation.support_sla_breaches", 1):
        from .qualification.support_breaches_profile import fixture as support_fixture

        return support_fixture(seed, index)
    if (contract, version) == ("sql.windows.media_previous_play", 1):
        from .qualification.previous_play_profile import fixture as previous_fixture

        return previous_fixture(seed, index)
    if (contract, version) == ("sql.cte.order_line_reconciliation", 1):
        from .qualification.reconciliation_profile import fixture as reconciliation_fixture

        return reconciliation_fixture(seed, index)
    if (contract, version) == ("sql.retention.saas_repeat_payment", 1):
        from .qualification.repeat_payment_profile import fixture as retention_fixture

        return retention_fixture(seed, index)
    if (contract, version) == ("sql.temporal.clinic_weekly_visits", 1):
        from .qualification.weekly_visits_profile import fixture as weekly_fixture

        return weekly_fixture(seed, index)
    if (contract, version) == ("sql.joins.logistics_final_leg", 1):
        from .qualification.final_leg_profile import fixture as final_leg_fixture

        return final_leg_fixture(seed, index)
    if (contract, version) in {("sql.joins.saas_paid_invoices", 1), ("sql.subqueries.exists", 2)}:
        from .qualification.selection_observations import fixture

        return fixture(contract, version, seed, index)
    if (contract, version) == ("sql.aggregation.fulfillment_sla_dashboard", 1):
        rng = Random(f"sla:{seed}:{index}")
        sla_rows: list[dict[str, Any]] = []
        for identifier in range(1, rng.randint(25, 60)):
            year = rng.choice([2024, 2025, 2026])
            shipped = datetime.fromisoformat(f"{year}-01-01 12:00:00")
            promised = shipped + timedelta(days=1)
            delivered = promised + timedelta(hours=rng.choice([-1, 0, 1]))
            sla_rows.append({"fulfillment_id": identifier, "warehouse": f"w{rng.randrange(5)}",
                "shipped_at": shipped.isoformat(sep=" "), "promised_at": promised.isoformat(sep=" "),
                "delivered_at": None if rng.randrange(5) == 0 else delivered.isoformat(sep=" "),
                "fulfillment_status": rng.choice(["delivered", "cancelled"])})
        rng.shuffle(sla_rows)
        return {"fulfillments": sla_rows}
    if (contract, version) == ("sql.aggregation.manufacturing_line_scrap", 1):
        rng = Random(f"scrap:{seed}:{index}")
        return {"production_runs": [
            {"record_id": i + 1, "entity_id": rng.randint(1, 8),
             "group_key": f"g{rng.randrange(5)}",
             "occurred_at": f"{rng.choice([2024, 2025, 2026])}-01-01 00:00:00",
             "status": rng.choice(["eligible", "ineligible"]), "amount": rng.randint(-20, 20),
             "sequence": i + 1} for i in range(rng.randint(20, 60))
        ]}
    if (contract, version) != ("sql.funnel.saas_activation_payment", 2):
        raise ValueError("unsupported contract observation policy")
    rng = Random(f"{seed}:{index}")
    rows: list[dict[str, Any]] = []
    for entity in range(1, rng.randint(3, 12)):
        group = f"g{rng.randrange(4)}"
        statuses = [rng.choice(["signup", "trial", "activation", "payment", "cancelled"])
                    for _ in range(rng.randint(1, 18))]
        start = datetime.fromisoformat(rng.choice([
            "2024-12-31 23:59:00", "2025-06-15 00:00:00", "2025-12-31 23:59:00",
        ]))
        for sequence, status in enumerate(statuses, 1):
            at = start + timedelta(seconds=sequence * rng.choice([0, 1, 30]))
            rows.append({"record_id": len(rows) + 1, "entity_id": entity, "group_key": group,
                         "status": status, "occurred_at": at.isoformat(sep=" "),
                         "sequence": sequence, "amount": rng.randint(0, 1000)})
    rng.shuffle(rows)
    return {"account_funnel": rows}


def observed_behaviors(
    contract: str, version: int, tables: dict[str, list[dict[str, Any]]],
) -> tuple[str, tuple[str, ...], set[str]]:
    from .qualification.delivery_profiles import get_profile

    profile = get_profile(contract, version)
    if profile is not None:
        result: tuple[str, tuple[str, ...], set[str]] = profile.observed(tables)
        return result
    if (contract, version) == ("sql.dedup.lowest_quote", 1):
        from .qualification.lowest_quote_profile import observed as quote_observed

        return quote_observed(tables)
    if (contract, version) == ("sql.cte.inventory_net_flow", 2):
        from .qualification.inventory_flow_profile import observed as inventory_observed

        return inventory_observed(tables)
    if (contract, version) == ("sql.subqueries.education_all_required", 1):
        from .qualification.required_courses_profile import observed as required_observed

        return required_observed(tables)
    if (contract, version) == ("sql.aggregation.warehouse_throughput", 2):
        from .qualification.throughput_profile import observed as throughput_observed

        return throughput_observed(tables)
    if (contract, version) == ("sql.dedup.education_grade_revisions", 2):
        from .qualification.grade_revisions_profile import observed as grade_observed

        return grade_observed(tables)
    if (contract, version) == ("sql.aggregation.support_sla_breaches", 1):
        from .qualification.support_breaches_profile import observed as support_observed

        return support_observed(tables)
    if (contract, version) == ("sql.windows.media_previous_play", 1):
        from .qualification.previous_play_profile import observed as previous_observed

        return previous_observed(tables)
    if (contract, version) == ("sql.cte.order_line_reconciliation", 1):
        from .qualification.reconciliation_profile import observed as reconciliation_observed

        return reconciliation_observed(tables)
    if (contract, version) == ("sql.retention.saas_repeat_payment", 1):
        from .qualification.repeat_payment_profile import observed as retention_observed

        return retention_observed(tables)
    if (contract, version) == ("sql.temporal.clinic_weekly_visits", 1):
        from .qualification.weekly_visits_profile import observed as weekly_observed

        return weekly_observed(tables)
    if (contract, version) == ("sql.joins.logistics_final_leg", 1):
        from .qualification.final_leg_profile import observed as final_leg_observed

        return final_leg_observed(tables)
    if (contract, version) in {("sql.joins.saas_paid_invoices", 1), ("sql.subqueries.exists", 2)}:
        from .qualification.selection_observations import observed

        return observed(contract, version, tables)
    if (contract, version) == ("sql.aggregation.fulfillment_sla_dashboard", 1):
        rows = tables["fulfillments"]
        found = {"multiple_warehouses"} if len({row["warehouse"] for row in rows}) > 1 else set()
        for row in rows:
            shipped = datetime.fromisoformat(str(row["shipped_at"]))
            if shipped.year != 2025:
                found.add("excluded_year")
            if row["fulfillment_status"] == "cancelled":
                found.add("cancelled")
            if row["delivered_at"] is None:
                found.add("unresolved")
                continue
            if shipped.year != 2025 or row["fulfillment_status"] != "delivered":
                continue
            found.add("delivered")
            delivered = datetime.fromisoformat(str(row["delivered_at"]))
            promised = datetime.fromisoformat(str(row["promised_at"]))
            found.add("on_time" if delivered <= promised else "late")
            if delivered == promised:
                found.add("deadline_equal")
        return "sla-observed-v1", SLA_BEHAVIORS, found
    if (contract, version) == ("sql.aggregation.manufacturing_line_scrap", 1):
        rows = tables["production_runs"]
        found = {"multiple_groups"} if len({r["group_key"] for r in rows}) > 1 else set()
        for label, present in (
            ("negative_amounts", any(r["amount"] < 0 for r in rows)),
            ("zero_amounts", any(r["amount"] == 0 for r in rows)),
            ("excluded_status", any(r["status"] == "ineligible" for r in rows)),
            ("excluded_year", any(not str(r["occurred_at"]).startswith("2025") for r in rows)),
            ("eligible_rows", any(r["status"] == "eligible" and
                                  str(r["occurred_at"]).startswith("2025") for r in rows)),
        ):
            if present:
                found.add(label)
        return "scrap-observed-v1", SCRAP_BEHAVIORS, found
    if (contract, version) != ("sql.funnel.saas_activation_payment", 2):
        raise ValueError("unsupported contract observation policy")
    steps = ["signup", "trial", "activation", "payment"]
    entities: dict[int, list[dict[str, Any]]] = {}
    groups: dict[str, list[dict[str, Any]]] = {}
    found, complete_groups, scoped_groups = set(), set(), set()
    for row in tables["account_funnel"]:
        entities.setdefault(row["entity_id"], []).append(row)
        groups.setdefault(row["group_key"], []).append(row)
        at = datetime.fromisoformat(str(row["occurred_at"]))
        if row["status"] == "cancelled":
            found.add("cancelled")
        if (at.month, at.day) in {(12, 31), (1, 1)}:
            found.add("year_boundaries")
    for rows in entities.values():
        ordered = sorted(rows, key=lambda r: (datetime.fromisoformat(str(r["occurred_at"])),
                                             r["sequence"]))
        scoped = [r for r in ordered if datetime.fromisoformat(str(r["occurred_at"])).year
                  == 2025 and r["status"] in steps]
        if scoped:
            scoped_groups.add(scoped[0]["group_key"])
        statuses = [r["status"] for r in scoped]
        if any(count > 1 for count in Counter(statuses).values()):
            found.add("repeated_steps")
        if len({datetime.fromisoformat(str(r["occurred_at"])) for r in rows}) < len(rows):
            found.add("same_timestamp_ties")
        progress = 0
        for row in scoped:
            stage = steps.index(row["status"])
            if stage > progress:
                found.add("early_later_steps")
            if stage == progress:
                progress += 1
        if progress == 4:
            found.add("completed")
            complete_groups.add(scoped[0]["group_key"])
        elif scoped:
            found.add("incomplete")
        if "signup" in statuses and "payment" in statuses and any(
            step not in statuses for step in steps[1:3]
        ):
            found.add("skipped_steps")
    if scoped_groups - complete_groups:
        found.add("zero_completion_groups")
    if set(groups) - scoped_groups:
        found.add("out_of_scope_only_groups")
    if len(entities) > 1:
        found.add("multiple_entities")
    if len(groups) > 1:
        found.add("multiple_groups")
    return "saas-observed-v1", SAAS_BEHAVIORS, found
