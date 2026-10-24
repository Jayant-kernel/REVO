"""Python business semantics with no fixture generator or SQL execution.

SaaS SQL/oracle agreement is differential verification; independent authorship is
not established.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from itertools import pairwise
from typing import Any

from .models import ExpectedResult, OrderSpec


def expansion_total(req: Any, tables: Any) -> ExpectedResult:
    """Independent event-ledger reconciliation used by expansion contracts."""
    rows = next(iter(tables.values()))
    totals: dict[str, int] = defaultdict(int)
    for row in rows:
        if row["status"] == "eligible" and str(row["occurred_at"])[:4] == str(req["year"]):
            totals[row["group_key"]] += row["amount"]
    return ExpectedResult(columns=["group_key", "total_amount"], column_types=["VARCHAR", "HUGEINT"], rows=[[key, totals[key]] for key in sorted(totals)], order=OrderSpec(type="ordered", keys=[("group_key", "asc")]))


def saas_activation_payment(req: Any, tables: Any) -> ExpectedResult:
    """Evaluate the ordered, entity-lifetime SaaS activation funnel."""
    steps = list(req["funnel_steps"])
    in_scope = set(steps)
    all_entities: dict[int, list[Any]] = defaultdict(list)
    entities: dict[int, list[Any]] = defaultdict(list)
    for row in tables["account_funnel"]:
        all_entities[int(row["entity_id"])].append(row)
        if str(row["occurred_at"])[:4] == str(req["year"]) and row["status"] in in_scope:
            entities[int(row["entity_id"])].append(row)

    for rows in all_entities.values():
        if len({str(row["group_key"]) for row in rows}) != 1:
            raise ValueError("each SaaS entity must have exactly one group_key")
        order_keys = [(_timestamp(row["occurred_at"]), row["sequence"]) for row in rows]
        if len(order_keys) != len(set(order_keys)):
            raise ValueError("SaaS entity rows must have unique occurred_at and sequence")

    totals: dict[str, int] = {}
    for rows in entities.values():
        # record_id makes output deterministic only if a caller violates the
        # public uniqueness guarantee; it is not a semantic ordering rule.
        ordered = sorted(rows, key=lambda row: (_timestamp(row["occurred_at"]), row["sequence"], row["record_id"]))
        progress = 0
        payment_amount = 0
        for row in ordered:
            if progress < len(steps) and row["status"] == steps[progress]:
                if progress == len(steps) - 1:
                    payment_amount = int(row["amount"])
                progress += 1
        group = str(ordered[0]["group_key"])
        totals.setdefault(group, 0)
        if progress == len(steps):
            totals[group] += payment_amount
    return ExpectedResult(columns=["group_key", "total_amount"], column_types=["VARCHAR", "HUGEINT"], rows=[[key, totals[key]] for key in sorted(totals)], order=OrderSpec(type="ordered", keys=[("group_key", "asc")]))


def logistics_parcel_delivery(req: Any, tables: Any) -> ExpectedResult:
    """Evaluate the ordered, entity-lifetime parcel delivery funnel."""
    steps = list(req["funnel_steps"])
    in_scope = set(steps)
    entities: dict[int, list[Any]] = defaultdict(list)
    for row in tables["parcel_scans"]:
        if str(row["occurred_at"])[:4] == str(req["year"]) and row["status"] in in_scope:
            entities[int(row["entity_id"])].append(row)

    totals: dict[str, int] = {}
    for rows in entities.values():
        ordered = sorted(rows, key=lambda row: (_timestamp(row["occurred_at"]), row["sequence"], row["record_id"]))
        progress = 0
        delivered_amount = 0
        for row in ordered:
            if progress < len(steps) and row["status"] == steps[progress]:
                if progress == len(steps) - 1:
                    delivered_amount = int(row["amount"])
                progress += 1
        depot = str(ordered[0]["group_key"])
        totals.setdefault(depot, 0)
        if progress == len(steps):
            totals[depot] += delivered_amount
    return ExpectedResult(columns=["group_key", "total_amount"], column_types=["VARCHAR", "HUGEINT"], rows=[[key, totals[key]] for key in sorted(totals)], order=OrderSpec(type="ordered", keys=[("group_key", "asc")]))


def logistics_parcel_delivery_v2(req: Any, tables: Any) -> ExpectedResult:
    """Evaluate the bounded, consecutive parcel-scan contract."""
    steps = list(req["funnel_steps"])
    in_scope = set(steps)
    max_gap = timedelta(minutes=int(req["max_consecutive_gap_minutes"]))
    all_entities: dict[int, list[Any]] = defaultdict(list)
    scoped: dict[int, list[Any]] = defaultdict(list)
    for row in tables["parcel_scans"]:
        all_entities[int(row["entity_id"])].append(row)
        if str(row["occurred_at"])[:4] == str(req["year"]) and row["status"] in in_scope:
            scoped[int(row["entity_id"])].append(row)

    for rows in all_entities.values():
        if len({str(row["group_key"]) for row in rows}) != 1:
            raise ValueError("each parcel must have exactly one group_key")
        order_keys = [(_timestamp(row["occurred_at"]), row["sequence"]) for row in rows]
        if len(order_keys) != len(set(order_keys)):
            raise ValueError("parcel rows must have unique occurred_at and sequence")

    totals: dict[str, int] = {}
    for rows in scoped.values():
        ordered = sorted(rows, key=lambda row: (_timestamp(row["occurred_at"]), row["sequence"], row["record_id"]))
        group = str(ordered[0]["group_key"])
        totals.setdefault(group, 0)
        for index in range(len(ordered) - len(steps) + 1):
            chain = ordered[index : index + len(steps)]
            if [row["status"] for row in chain] != steps:
                continue
            times = [_timestamp(row["occurred_at"]) for row in chain]
            if all(right - left <= max_gap for left, right in pairwise(times)):
                totals[group] += int(chain[-1]["amount"])
                break
    return ExpectedResult(columns=["group_key", "total_amount"], column_types=["VARCHAR", "HUGEINT"], rows=[[key, totals[key]] for key in sorted(totals)], order=OrderSpec(type="ordered", keys=[("group_key", "asc")]))


def final_leg(req: Any, tables: Any) -> ExpectedResult:
    legs: dict[int, list[Any]] = defaultdict(list)
    carriers: dict[int, list[Any]] = defaultdict(list)
    for row in tables["legs"]:
        legs[row["leg_id"]].append(row)
    for row in tables["carriers"]:
        carriers[row["carrier_id"]].append(row)
    rows = []
    for shipment in tables["shipments"]:
        delivered = shipment["delivered_on"]
        if delivered is None or str(delivered)[:4] != str(req["year"]):
            continue
        for leg in legs.get(shipment["final_leg_id"], []):
            for carrier in carriers.get(leg["carrier_id"], []):
                rows.append([shipment["shipment_id"], leg["depot"], carrier["carrier_name"]])
    return ExpectedResult(columns=["shipment_id", "depot", "carrier_name"], column_types=["INTEGER", "VARCHAR", "VARCHAR"], rows=sorted(rows), order=OrderSpec(type="ordered", keys=[("shipment_id", "asc")]))


def net_flow(req: Any, tables: Any) -> ExpectedResult:
    net: dict[str, int] = defaultdict(int)
    for table, sign in (("receipts", 1), ("issues", -1)):
        for movement in tables[table]:
            if movement["status"] == "posted" and str(movement["occurred_on"])[:4] == str(req["year"]):
                net[movement["warehouse"]] += sign * movement["units"]
    return ExpectedResult(columns=["warehouse", "net_units"], column_types=["VARCHAR", "HUGEINT"], rows=[[k, net[k]] for k in sorted(net)], order=OrderSpec(type="ordered", keys=[("warehouse", "asc")]))


def all_required(req: Any, tables: Any) -> ExpectedResult:
    required: dict[int, set[int]] = defaultdict(set)
    passed: dict[int, set[int]] = defaultdict(set)
    for row in tables["required_courses"]:
        required[row["program_id"]].add(row["course_id"])
    for row in tables["attempts"]:
        if row["score"] is not None and row["score"] >= req["passing_score"]:
            passed[row["student_id"]].add(row["course_id"])
    rows = [[s["student_id"]] for s in tables["students"]
            if required[s["program_id"]] and required[s["program_id"]] <= passed[s["student_id"]]]
    return ExpectedResult(columns=["student_id"], column_types=["INTEGER"], rows=sorted(rows), order=OrderSpec(type="ordered", keys=[("student_id", "asc")]))


def previous_play(req: Any, tables: Any) -> ExpectedResult:
    groups: dict[tuple[int, int], list[Any]] = defaultdict(list)
    for row in tables["plays"]:
        if row["status"] == "completed" and str(row["played_at"])[:4] == str(req["year"]):
            groups[row["viewer_id"], row["title_id"]].append(row)
    rows = []
    for group in groups.values():
        prior = None
        for row in sorted(group, key=lambda r: (r["played_at"], r["play_id"])):
            rows.append([row["play_id"], prior])
            prior = row["play_id"]
    return ExpectedResult(columns=["play_id", "previous_play_id"], column_types=["INTEGER", "INTEGER"], rows=sorted(rows, key=lambda row: row[0]), order=OrderSpec(type="ordered", keys=[("play_id", "asc")]))


def weekly_visits(req: Any, tables: Any) -> ExpectedResult:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in tables["visits"]:
        if row["status"] != "completed" or row["started_at"] is None:
            continue
        day = datetime.fromisoformat(str(row["started_at"])).date()
        if day.year == req["year"]:
            monday = day - timedelta(days=day.weekday())
            counts[row["clinic"], monday.isoformat()] += 1
    return ExpectedResult(columns=["clinic", "week_start", "visit_count"], column_types=["VARCHAR", "DATE", "BIGINT"],
                           rows=[[c, w, counts[c, w]] for c, w in sorted(counts)], order=OrderSpec(type="ordered", keys=[("clinic", "asc"), ("week_start", "asc")]))


def first_full_week_viewers(req: Any, tables: Any) -> ExpectedResult:
    completed: dict[int, set[date]] = defaultdict(set)
    for row in tables["viewing_events"]:
        watched = _timestamp(row["watched_at"])
        if row["playback_status"] == "completed" and watched.year == int(req["year"]):
            completed[int(row["viewer_id"])].add(watched.date())
    rows = []
    for viewer_id, days in completed.items():
        first = min(days)
        if all(first + timedelta(days=offset) in days for offset in range(7)):
            rows.append([viewer_id, first.isoformat()])
    return ExpectedResult(columns=["viewer_id", "first_completed_on"], column_types=["INTEGER", "DATE"], rows=sorted(rows), order=OrderSpec(type="ordered", keys=[("viewer_id", "asc")]))


def manufacturing_shift_downtime(req: Any, tables: Any) -> ExpectedResult:
    totals: dict[tuple[str, str], int] = defaultdict(int)
    for row in tables["downtime_events"]:
        if row["event_status"] != "closed" or row["ended_at"] is None:
            continue
        started, ended = _timestamp(row["started_at"]), _timestamp(row["ended_at"])
        if started.year == int(req["year"]):
            totals[str(row["line_code"]), str(row["shift_name"])] += int((ended - started).total_seconds() // 60)
    return ExpectedResult(columns=["line_code", "shift_name", "downtime_minutes"], column_types=["VARCHAR", "VARCHAR", "BIGINT"], rows=[[line, shift, totals[line, shift]] for line, shift in sorted(totals)], order=OrderSpec(type="ordered", keys=[("line_code", "asc"), ("shift_name", "asc")]))


def logistics_service_level_as_of(req: Any, tables: Any) -> ExpectedResult:
    cutoff = _timestamp(req["as_of_timestamp"])
    events: dict[int, list[Any]] = defaultdict(list)
    for row in tables["tracking_events"]:
        if _timestamp(row["event_at"]) <= cutoff:
            events[int(row["shipment_id"])].append(row)
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for shipment in tables["shipments"]:
        if _timestamp(shipment["accepted_at"]).year != int(req["year"]):
            continue
        depot = str(shipment["depot"])
        totals[depot][0] += 1
        history = events[int(shipment["shipment_id"])]
        if history:
            latest = max(history, key=lambda row: (_timestamp(row["event_at"]), int(row["event_id"])))
            if latest["tracking_state"] == "delivered" and _timestamp(latest["event_at"]) <= _timestamp(shipment["promised_at"]):
                totals[depot][1] += 1
    return ExpectedResult(columns=["depot", "shipments_in_scope", "delivered_on_time"], column_types=["VARCHAR", "BIGINT", "BIGINT"], rows=[[depot, *totals[depot]] for depot in sorted(totals)], order=OrderSpec(type="ordered", keys=[("depot", "asc")]))


def saas_account_snapshot(req: Any, tables: Any) -> ExpectedResult:
    cutoff = _timestamp(req["as_of_timestamp"])
    latest: dict[int, Any] = {}
    for row in tables["subscription_revisions"]:
        effective = _timestamp(row["effective_at"])
        account_id = int(row["account_id"])
        if effective <= cutoff and (account_id not in latest or (effective, int(row["revision_id"])) > (_timestamp(latest[account_id]["effective_at"]), int(latest[account_id]["revision_id"]))):
            latest[account_id] = row
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in latest.values():
        if row["subscription_status"] == "active":
            totals[str(row["plan_name"])][0] += 1
            totals[str(row["plan_name"])][1] += int(row["mrr_cents"])
    return ExpectedResult(columns=["plan_name", "active_accounts", "total_mrr_cents"], column_types=["VARCHAR", "BIGINT", "HUGEINT"], rows=[[plan, *totals[plan]] for plan in sorted(totals)], order=OrderSpec(type="ordered", keys=[("plan_name", "asc")]))


def repeat_payment(req: Any, tables: Any) -> ExpectedResult:
    dates: dict[int, set[date]] = defaultdict(set)
    for row in tables["billing"]:
        if row["status"] == "paid" and row["paid_on"] is not None:
            dates[row["account_id"]].add(date.fromisoformat(str(row["paid_on"])))
    rows = []
    for account, days in dates.items():
        first = min(days)
        if first.year == req["year"] and any(0 < (d - first).days <= req["retention_window_days"] for d in days):
            rows.append([account])
    return ExpectedResult(columns=["account_id"], column_types=["INTEGER"], rows=sorted(rows), order=OrderSpec(type="ordered", keys=[("account_id", "asc")]))


def resolution_chain(req: Any, tables: Any) -> ExpectedResult:
    events: dict[int, list[Any]] = defaultdict(list)
    for row in tables["ticket_events"]:
        if str(row["event_time"])[:4] == str(req["year"]):
            events[row["ticket_id"]].append(row)
    rows = []
    steps = req["funnel_steps"]
    for ticket, history in events.items():
        progress = 0
        for row in sorted(history, key=lambda r: (r["event_time"], r["event_id"])):
            if progress < len(steps) and row["state"] == steps[progress]:
                progress += 1
        if progress == len(steps):
            rows.append([ticket])
    return ExpectedResult(columns=["ticket_id"], column_types=["INTEGER"], rows=sorted(rows), order=OrderSpec(type="ordered", keys=[("ticket_id", "asc")]))


def warehouse_throughput(req: Any, tables: Any) -> ExpectedResult:
    """Per-warehouse posted units, keeping only groups at/above a HAVING threshold."""
    totals: dict[str, int] = defaultdict(int)
    for row in tables["warehouse_loads"]:
        if row["status"] == req["status_filter"] and str(row["loaded_on"])[:4] == str(req["year"]):
            totals[row["warehouse"]] += row["units"]
    threshold = req["min_total_units"]
    rows = [[warehouse, totals[warehouse]] for warehouse in sorted(totals) if totals[warehouse] >= threshold]
    return ExpectedResult(columns=["warehouse", "total_units"], column_types=["VARCHAR", "HUGEINT"], rows=rows, order=OrderSpec(type="ordered", keys=[("warehouse", "asc")]))


def fulfillment_sla_dashboard(req: Any, tables: Any) -> ExpectedResult:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in tables["fulfillments"]:
        if row["fulfillment_status"] != req["status_filter"] or row["delivered_at"] is None or _timestamp(row["shipped_at"]).year != int(req["year"]):
            continue
        total = totals[str(row["warehouse"])]
        total[0] += 1
        if _timestamp(row["delivered_at"]) <= _timestamp(row["promised_at"]):
            total[1] += 1
    return ExpectedResult(columns=["warehouse", "delivered_fulfillments", "on_time_fulfillments"], column_types=["VARCHAR", "BIGINT", "BIGINT"], rows=[[warehouse, *totals[warehouse]] for warehouse in sorted(totals)], order=OrderSpec(type="ordered", keys=[("warehouse", "asc")]))


def product_unique_conversion(req: Any, tables: Any) -> ExpectedResult:
    viewers: dict[int, set[int]] = defaultdict(set)
    buyers: dict[int, set[int]] = defaultdict(set)
    for row in tables["product_events"]:
        if _timestamp(row["occurred_at"]).year != int(req["year"]):
            continue
        if row["event_name"] == "view":
            viewers[int(row["product_id"])].add(int(row["visitor_id"]))
        elif row["event_name"] == req["status_filter"]:
            buyers[int(row["product_id"])].add(int(row["visitor_id"]))
    return ExpectedResult(columns=["product_id", "unique_viewers", "unique_buyers"], column_types=["INTEGER", "BIGINT", "BIGINT"], rows=[[product_id, len(viewers[product_id]), len(buyers[product_id])] for product_id in sorted(viewers)], order=OrderSpec(type="ordered", keys=[("product_id", "asc")]))


def order_line_reconciliation(req: Any, tables: Any) -> ExpectedResult:
    line_totals: dict[int, int] = defaultdict(int)
    for line in tables["order_lines"]:
        line_totals[int(line["order_id"])] += int(line["quantity"]) * int(line["unit_price_cents"])
    rows = [[int(order["order_id"]), int(order["header_total_cents"]), line_totals[int(order["order_id"])] ] for order in tables["orders"] if order["order_status"] == req["status_filter"] and str(order["ordered_on"])[:4] == str(req["year"]) and int(order["header_total_cents"]) != line_totals[int(order["order_id"])]]
    return ExpectedResult(columns=["order_id", "header_total_cents", "line_total_cents"], column_types=["INTEGER", "BIGINT", "HUGEINT"], rows=sorted(rows), order=OrderSpec(type="ordered", keys=[("order_id", "asc")]))


def category_descendant_sales(req: Any, tables: Any) -> ExpectedResult:
    children: dict[int | None, list[int]] = defaultdict(list)
    names: dict[int, str] = {}
    for category in tables["categories"]:
        category_id = int(category["category_id"])
        names[category_id] = str(category["category_name"])
        children[category["parent_category_id"]].append(category_id)
    direct: dict[int, int] = defaultdict(int)
    for sale in tables["category_orders"]:
        if sale["sale_status"] == req["status_filter"] and str(sale["sold_on"])[:4] == str(req["year"]):
            direct[int(sale["category_id"])] += int(sale["amount_cents"])
    def total(category_id: int) -> int:
        return direct[category_id] + sum(total(child) for child in children[category_id])
    return ExpectedResult(columns=["category_id", "category_name", "descendant_sales_cents"], column_types=["INTEGER", "VARCHAR", "HUGEINT"], rows=[[category_id, names[category_id], total(category_id)] for category_id in sorted(names)], order=OrderSpec(type="ordered", keys=[("category_id", "asc")]))


def session_funnel_completion(req: Any, tables: Any) -> ExpectedResult:
    events: dict[int, list[Any]] = defaultdict(list)
    for event in tables["session_events"]:
        events[int(event["session_id"])].append(event)
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for session in tables["sessions"]:
        if _timestamp(session["started_at"]).year != int(req["year"]):
            continue
        channel = str(session["channel"])
        totals[channel][0] += 1
        progress = 0
        for event in sorted(events[int(session["session_id"])], key=lambda row: (_timestamp(row["occurred_at"]), int(row["event_id"]))):
            if progress < len(req["funnel_steps"]) and event["event_name"] == req["funnel_steps"][progress]:
                progress += 1
        if progress == len(req["funnel_steps"]):
            totals[channel][1] += 1
    return ExpectedResult(columns=["channel", "started_sessions", "completed_sessions"], column_types=["VARCHAR", "BIGINT", "BIGINT"], rows=[[channel, *totals[channel]] for channel in sorted(totals)], order=OrderSpec(type="ordered", keys=[("channel", "asc")]))


def customer_first_month_repeat(req: Any, tables: Any) -> ExpectedResult:
    completed: dict[int, list[Any]] = defaultdict(list)
    for order in tables["customer_orders"]:
        if order["order_status"] == req["status_filter"]:
            completed[int(order["customer_id"])].append(order)
    rows = []
    for customer_id, orders in completed.items():
        ordered = sorted(orders, key=lambda row: (_timestamp(row["ordered_at"]), int(row["order_id"])))
        first = ordered[0]
        first_at = _timestamp(first["ordered_at"])
        if first_at.year == int(req["year"]) and any((_timestamp(order["ordered_at"]), int(order["order_id"])) > (first_at, int(first["order_id"])) and _timestamp(order["ordered_at"]).strftime("%Y-%m") == first_at.strftime("%Y-%m") for order in ordered[1:]):
            rows.append([customer_id, first_at.strftime("%Y-%m")])
    return ExpectedResult(columns=["customer_id", "first_purchase_month"], column_types=["INTEGER", "VARCHAR"], rows=sorted(rows), order=OrderSpec(type="ordered", keys=[("customer_id", "asc")]))


def top_category_sales(req: Any, tables: Any) -> ExpectedResult:
    """Top-K categories by completed in-year revenue, deterministic tie-break."""
    totals: dict[str, int] = defaultdict(int)
    for row in tables["category_sales"]:
        if row["status"] == req["status_filter"] and str(row["sold_on"])[:4] == str(req["year"]):
            totals[row["category"]] += row["amount"]
    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    rows = [[category, value] for category, value in ranked[: int(req["top_k"])]]
    return ExpectedResult(columns=["category", "total_sales"], column_types=["VARCHAR", "HUGEINT"], rows=rows, order=OrderSpec(type="ordered", keys=[("total_sales", "desc"), ("category", "asc")]))


def customer_outreach(req: Any, tables: Any) -> ExpectedResult:
    """Distinct customers reached by any qualifying channel (UNION semantics)."""
    channels = {str(channel) for channel in req["channels"]}
    reached: set[int] = set()
    for row in tables["outreach_activity"]:
        if (
            row["status"] == req["status_filter"]
            and str(row["contacted_on"])[:4] == str(req["year"])
            and row["channel"] in channels
        ):
            reached.add(int(row["customer_id"]))
    rows = [[customer_id] for customer_id in sorted(reached)]
    return ExpectedResult(columns=["customer_id"], column_types=["INTEGER"], rows=rows, order=OrderSpec(type="ordered", keys=[("customer_id", "asc")]))


def _timestamp(value: Any) -> datetime:
    return datetime.fromisoformat(str(value))


def checkout_paid_session(req: Any, tables: Any) -> ExpectedResult:
    """Channel conversion from a session-local event chain and captured payment."""
    steps = list(req["funnel_steps"])
    events: dict[int, list[Any]] = defaultdict(list)
    payments: dict[int, list[Any]] = defaultdict(list)
    for row in tables["session_events"]:
        events[int(row["session_id"])].append(row)
    for row in tables["payments"]:
        payments[int(row["session_id"])].append(row)
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for session in tables["sessions"]:
        if _timestamp(session["started_at"]).year != int(req["year"]):
            continue
        channel = str(session["channel"])
        totals[channel][0] += 1
        progress = 0
        checkout_at: datetime | None = None
        for event in sorted(events[int(session["session_id"])], key=lambda row: (_timestamp(row["occurred_at"]), row["event_id"])):
            occurred_at = _timestamp(event["occurred_at"])
            if occurred_at < _timestamp(session["started_at"]):
                continue
            if progress < len(steps) and event["event_name"] == steps[progress]:
                progress += 1
                if progress == len(steps):
                    checkout_at = occurred_at
        if checkout_at is not None and any(
            payment["payment_status"] == req["payment_status"]
            and checkout_at <= _timestamp(payment["captured_at"]) <= _timestamp(session["expires_at"])
            for payment in payments[int(session["session_id"])]
        ):
            totals[channel][1] += 1
    return ExpectedResult(columns=["channel", "started_sessions", "paid_checkouts"], column_types=["VARCHAR", "BIGINT", "BIGINT"], rows=[[channel, *totals[channel]] for channel in sorted(totals)], order=OrderSpec(type="ordered", keys=[("channel", "asc")]))


def kyc_document_approval(req: Any, tables: Any) -> ExpectedResult:
    """Application-local KYC gates, using the latest review of each required document."""
    required: dict[str, set[str]] = defaultdict(set)
    checks: dict[int, list[Any]] = defaultdict(list)
    reviews: dict[int, list[Any]] = defaultdict(list)
    decisions: dict[int, list[Any]] = defaultdict(list)
    for row in tables["country_document_requirements"]:
        required[str(row["country"])].add(str(row["document_type"]))
    for row in tables["identity_checks"]:
        checks[int(row["application_id"])].append(row)
    for row in tables["document_reviews"]:
        reviews[int(row["application_id"])].append(row)
    for row in tables["approval_decisions"]:
        decisions[int(row["application_id"])].append(row)
    accepted: list[list[int]] = []
    for application in tables["applications"]:
        submitted = _timestamp(application["submitted_at"])
        if submitted.year != int(req["year"]):
            continue
        passed = [row for row in checks[int(application["application_id"])] if row["result"] == "passed" and _timestamp(row["checked_at"]) >= submitted]
        if not passed:
            continue
        identity_at = min(_timestamp(row["checked_at"]) for row in passed)
        latest: dict[str, Any] = {}
        for review in reviews[int(application["application_id"])]:
            document = str(review["document_type"])
            if (
                document in required[str(application["country"])]
                and _timestamp(review["reviewed_at"]) >= identity_at
                and (
                    document not in latest
                    or (_timestamp(review["reviewed_at"]), review["review_id"])
                    > (_timestamp(latest[document]["reviewed_at"]), latest[document]["review_id"])
                )
            ):
                latest[document] = review
        if set(latest) != required[str(application["country"])] or any(row["result"] != "approved" for row in latest.values()):
            continue
        documents_at = max(_timestamp(row["reviewed_at"]) for row in latest.values())
        deadline = submitted + timedelta(days=int(req["approval_window_days"]))
        if any(
            decision["result"] == "approved"
            and documents_at <= _timestamp(decision["decided_at"]) <= deadline
            for decision in decisions[int(application["application_id"])]
        ):
            accepted.append([int(application["application_id"])])
    return ExpectedResult(columns=["application_id"], column_types=["INTEGER"], rows=sorted(accepted), order=OrderSpec(type="ordered", keys=[("application_id", "asc")]))


def parcel_exception_recovery(req: Any, tables: Any) -> ExpectedResult:
    """Aggregate deliveries that recover after each parcel's latest exception."""
    scans: dict[int, list[Any]] = defaultdict(list)
    for row in tables["parcel_scans"]:
        scans[int(row["parcel_id"])].append(row)
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for parcel in tables["parcels"]:
        if _timestamp(parcel["accepted_at"]).year != int(req["year"]):
            continue
        history = sorted(scans[int(parcel["parcel_id"])], key=lambda row: (_timestamp(row["scanned_at"]), row["scan_id"]))
        exceptions = [row for row in history if row["scan_state"] == "exception"]
        if not exceptions:
            continue
        exception = exceptions[-1]
        exception_key = (_timestamp(exception["scanned_at"]), exception["scan_id"])
        recovered = next((row for row in history if row["scan_state"] == "recovered" and (_timestamp(row["scanned_at"]), row["scan_id"]) > exception_key), None)
        if recovered is None:
            continue
        recovered_key = (_timestamp(recovered["scanned_at"]), recovered["scan_id"])
        delivered = next((row for row in history if row["scan_state"] == "delivered" and (_timestamp(row["scanned_at"]), row["scan_id"]) > recovered_key), None)
        if delivered is None:
            continue
        minutes = int((_timestamp(delivered["scanned_at"]) - _timestamp(exception["scanned_at"])).total_seconds() // 60)
        if minutes <= int(req["recovery_sla_hours"]) * 60:
            totals[str(parcel["depot"])][0] += 1
            totals[str(parcel["depot"])][1] += minutes
    return ExpectedResult(columns=["depot", "recovered_parcels", "total_exception_to_delivery_minutes"], column_types=["VARCHAR", "BIGINT", "HUGEINT"], rows=[[depot, *totals[depot]] for depot in sorted(totals)], order=OrderSpec(type="ordered", keys=[("depot", "asc")]))


def curriculum_gate_completion(req: Any, tables: Any) -> ExpectedResult:
    """Distinct learners whose complete module gates progress in strict stage order."""
    modules: dict[int, list[Any]] = defaultdict(list)
    lessons: dict[int, set[int]] = defaultdict(set)
    attempts: dict[int, list[Any]] = defaultdict(list)
    for row in tables["program_modules"]:
        modules[int(row["program_id"])].append(row)
    for row in tables["module_lessons"]:
        lessons[int(row["module_id"])].add(int(row["lesson_id"]))
    for row in tables["lesson_attempts"]:
        attempts[int(row["enrollment_id"])].append(row)
    cohort_learners: dict[str, set[int]] = defaultdict(set)
    cohorts: set[str] = set()
    for enrollment in tables["enrollments"]:
        enrolled = _timestamp(enrollment["enrolled_at"])
        if enrolled.year != int(req["year"]):
            continue
        cohort = str(enrollment["cohort"])
        cohorts.add(cohort)
        passed: dict[int, Any] = {}
        for attempt in attempts[int(enrollment["enrollment_id"])]:
            lesson_id = int(attempt["lesson_id"])
            if attempt["result"] == "passed" and _timestamp(attempt["completed_at"]) >= enrolled and (lesson_id not in passed or (_timestamp(attempt["completed_at"]), attempt["attempt_id"]) < (_timestamp(passed[lesson_id]["completed_at"]), passed[lesson_id]["attempt_id"])):
                passed[lesson_id] = attempt
        completion_keys: list[tuple[int, datetime, int]] = []
        for module in modules[int(enrollment["program_id"])]:
            required_lessons = lessons[int(module["module_id"])]
            if not required_lessons or not required_lessons <= set(passed):
                break
            final_attempt = max((passed[lesson] for lesson in required_lessons), key=lambda row: (_timestamp(row["completed_at"]), row["attempt_id"]))
            completion_keys.append((int(module["stage_number"]), _timestamp(final_attempt["completed_at"]), int(final_attempt["attempt_id"])))
        else:
            ordered = sorted(completion_keys)
            if all(left[1:] < right[1:] for left, right in pairwise(ordered)):
                cohort_learners[cohort].add(int(enrollment["learner_id"]))
    return ExpectedResult(columns=["cohort", "learners_completed_program"], column_types=["VARCHAR", "BIGINT"], rows=[[cohort, len(cohort_learners[cohort])] for cohort in sorted(cohorts)], order=OrderSpec(type="ordered", keys=[("cohort", "asc")]))
