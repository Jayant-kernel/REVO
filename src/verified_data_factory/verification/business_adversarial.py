"""Separately authored counterexamples, not derived from seeded fixtures.

Authored by the engineering agent; independent of generation code, NOT human
reviewed. Explicit expected results live in test_business_tasks.py.
"""
from typing import Any

_EXPANSION_TABLES = {
    "sql.joins.payments_country_transfer": "transfers", "sql.joins.clinic_scheduled_clinician": "appointments",
    "sql.joins.manufacturing_approved_supplier": "part_usage", "sql.joins.education_completed_enrollment": "enrollments",
    "sql.aggregation.manufacturing_line_scrap": "production_runs", "sql.cte.saas_mrr_changes": "plan_changes",
    "sql.cte.logistics_depot_delay": "shipment_stops", "sql.subqueries.payments_no_settlement": "merchant_events",
    "sql.subqueries.support_unresolved_reopen": "agent_events", "sql.windows.payments_risk_rank": "merchant_settlements",
    "sql.windows.logistics_previous_stop": "parcel_stops", "sql.temporal.saas_trial_activation": "account_events",
    "sql.temporal.inventory_daily_stock": "stock_events", "sql.dedup.refund_prefer_approved": "refund_requests",
    "sql.dedup.payments_latest_profile": "profile_revisions", "sql.retention.media_week_two_return": "viewer_plays",
    "sql.retention.clinic_followup_window": "patient_visits",
    "sql.funnel.logistics_parcel_delivery": "parcel_scans",
}


def business_adversarial(template_id: str, template_version: int = 1) -> dict[str, list[dict[str, Any]]] | None:
    if template_id == "sql.funnel.logistics_parcel_delivery" and template_version == 2:
        return {"parcel_scans": [
            {"record_id": 1, "entity_id": 1, "group_key": "north", "occurred_at": "2025-01-01 00:00:00", "status": "accepted", "amount": 0, "sequence": 1},
            {"record_id": 2, "entity_id": 1, "group_key": "north", "occurred_at": "2025-01-01 00:10:00", "status": "sorted", "amount": 0, "sequence": 2},
            {"record_id": 3, "entity_id": 1, "group_key": "north", "occurred_at": "2025-01-01 00:20:00", "status": "dispatched", "amount": 0, "sequence": 3},
            {"record_id": 4, "entity_id": 1, "group_key": "north", "occurred_at": "2025-01-01 00:30:00", "status": "delivered", "amount": 7, "sequence": 4},
            {"record_id": 5, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:00:00", "status": "accepted", "amount": 0, "sequence": 1},
            {"record_id": 6, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:10:00", "status": "sorted", "amount": 0, "sequence": 2},
            {"record_id": 7, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:20:00", "status": "accepted", "amount": 0, "sequence": 3},
            {"record_id": 8, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:30:00", "status": "sorted", "amount": 0, "sequence": 4},
            {"record_id": 9, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:40:00", "status": "dispatched", "amount": 0, "sequence": 5},
            {"record_id": 10, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:50:00", "status": "delivered", "amount": 11, "sequence": 6},
            {"record_id": 11, "entity_id": 3, "group_key": "south", "occurred_at": "2025-03-01 00:00:00", "status": "accepted", "amount": 0, "sequence": 1},
            {"record_id": 12, "entity_id": 3, "group_key": "south", "occurred_at": "2025-03-01 01:01:00", "status": "sorted", "amount": 0, "sequence": 2},
            {"record_id": 13, "entity_id": 3, "group_key": "south", "occurred_at": "2025-03-01 01:10:00", "status": "dispatched", "amount": 0, "sequence": 3},
            {"record_id": 14, "entity_id": 3, "group_key": "south", "occurred_at": "2025-03-01 01:20:00", "status": "delivered", "amount": 99, "sequence": 4},
        ]}
    if template_id == "sql.funnel.logistics_parcel_delivery":
        return {"parcel_scans": [
            {"record_id": 1, "entity_id": 1, "group_key": "north", "occurred_at": "2025-01-01 00:00:00", "status": "sorted", "amount": 2, "sequence": 1},
            {"record_id": 2, "entity_id": 1, "group_key": "north", "occurred_at": "2025-01-01 00:00:00", "status": "accepted", "amount": 1, "sequence": 2},
            {"record_id": 3, "entity_id": 1, "group_key": "north", "occurred_at": "2025-01-01 00:01:00", "status": "sorted", "amount": 2, "sequence": 3},
            {"record_id": 4, "entity_id": 1, "group_key": "north", "occurred_at": "2025-01-01 00:02:00", "status": "dispatched", "amount": 3, "sequence": 4},
            {"record_id": 5, "entity_id": 1, "group_key": "north", "occurred_at": "2025-01-01 00:03:00", "status": "delivered", "amount": 7, "sequence": 5},
            {"record_id": 6, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:00:00", "status": "accepted", "amount": 1, "sequence": 1},
            {"record_id": 7, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:01:00", "status": "delivered", "amount": 99, "sequence": 2},
            {"record_id": 8, "entity_id": 3, "group_key": "south", "occurred_at": "2025-03-01 00:00:00", "status": "accepted", "amount": 1, "sequence": 1},
            {"record_id": 9, "entity_id": 3, "group_key": "south", "occurred_at": "2025-03-01 00:01:00", "status": "sorted", "amount": 2, "sequence": 2},
        ]}
    if template_id == "sql.funnel.saas_activation_payment":
        return {"account_funnel": [
            {"record_id": 1, "entity_id": 1, "group_key": "west", "occurred_at": "2025-01-01 00:00:00", "status": "signup", "amount": 1, "sequence": 1},
            {"record_id": 2, "entity_id": 1, "group_key": "west", "occurred_at": "2025-01-01 00:00:00", "status": "trial", "amount": 2, "sequence": 2},
            {"record_id": 3, "entity_id": 1, "group_key": "west", "occurred_at": "2025-01-01 00:00:00", "status": "activation", "amount": 3, "sequence": 3},
            {"record_id": 4, "entity_id": 1, "group_key": "west", "occurred_at": "2025-01-01 00:00:00", "status": "payment", "amount": 7, "sequence": 4},
            {"record_id": 5, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:00:00", "status": "signup", "amount": 1, "sequence": 1},
            {"record_id": 6, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:01:00", "status": "payment", "amount": 99, "sequence": 2},
            {"record_id": 7, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:02:00", "status": "trial", "amount": 2, "sequence": 3},
            {"record_id": 8, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:03:00", "status": "activation", "amount": 3, "sequence": 4},
            {"record_id": 9, "entity_id": 2, "group_key": "east", "occurred_at": "2025-02-01 00:04:00", "status": "payment", "amount": 11, "sequence": 5},
            {"record_id": 10, "entity_id": 3, "group_key": "north", "occurred_at": "2025-01-01 00:00:00", "status": "signup", "amount": 1, "sequence": 1},
            {"record_id": 11, "entity_id": 3, "group_key": "north", "occurred_at": "2025-01-01 00:00:00", "status": "trial", "amount": 2, "sequence": 2},
            {"record_id": 12, "entity_id": 3, "group_key": "north", "occurred_at": "2025-01-01 00:00:00", "status": "activation", "amount": 3, "sequence": 3},
            {"record_id": 13, "entity_id": 4, "group_key": "zero", "occurred_at": "2025-01-01 00:00:00", "status": "signup", "amount": 1, "sequence": 1},
            {"record_id": 14, "entity_id": 4, "group_key": "zero", "occurred_at": "2025-01-01 00:00:00", "status": "trial", "amount": 2, "sequence": 2},
            {"record_id": 15, "entity_id": 5, "group_key": "ignored", "occurred_at": "2025-01-01 00:00:00", "status": "cancelled", "amount": 100, "sequence": 1},
        ]}
    if template_id in _EXPANSION_TABLES:
        table = _EXPANSION_TABLES[template_id]
        return {table: [
            {"record_id": 90, "entity_id": 1, "group_key": "west", "occurred_at": "2025-12-31 23:59:59", "status": "eligible", "amount": 0, "sequence": 2},
            {"record_id": 91, "entity_id": 1, "group_key": "west", "occurred_at": "2025-01-01 00:00:00", "status": "eligible", "amount": 7, "sequence": 1},
            {"record_id": 92, "entity_id": 2, "group_key": "east", "occurred_at": "2025-06-01 00:00:00", "status": "ineligible", "amount": 100, "sequence": 1},
            {"record_id": 93, "entity_id": 3, "group_key": "east", "occurred_at": "2024-12-31 00:00:00", "status": "eligible", "amount": 100, "sequence": 1},
        ]}
    if template_id == "sql.aggregation.warehouse_throughput":
        return {"warehouse_loads": [
            {"load_id": 1, "warehouse": "A", "loaded_on": "2025-01-01", "units": 60, "status": "posted"},
            {"load_id": 2, "warehouse": "B", "loaded_on": "2025-01-01", "units": 99, "status": "posted"},
            {"load_id": 3, "warehouse": "C", "loaded_on": "2025-01-01", "units": 1, "status": "posted"},
            {"load_id": 4, "warehouse": "A", "loaded_on": "2025-01-02", "units": 40, "status": "posted"},
            {"load_id": 5, "warehouse": "D", "loaded_on": "2024-12-31", "units": 999, "status": "posted"},
            {"load_id": 6, "warehouse": "E", "loaded_on": "2025-01-01", "units": 999, "status": "draft"},
        ]}
    if template_id == "sql.aggregation.top_category_sales":
        return {"category_sales": [
            {"sale_id": 1, "category": "apparel", "sold_on": "2025-01-01", "amount": 100, "status": "completed"},
            {"sale_id": 2, "category": "electronics", "sold_on": "2025-01-01", "amount": 100, "status": "completed"},
            {"sale_id": 3, "category": "books", "sold_on": "2025-01-01", "amount": 100, "status": "completed"},
            {"sale_id": 4, "category": "toys", "sold_on": "2024-12-31", "amount": 999, "status": "completed"},
            {"sale_id": 5, "category": "games", "sold_on": "2025-01-01", "amount": 999, "status": "cancelled"},
        ]}
    if template_id == "sql.aggregation.fulfillment_sla_dashboard":
        return {"fulfillments": [
            {"fulfillment_id": 1, "warehouse": "east", "shipped_at": "2025-01-01 00:00:00", "promised_at": "2025-01-02 00:00:00", "delivered_at": "2025-01-02 00:00:00", "fulfillment_status": "delivered"},
            {"fulfillment_id": 2, "warehouse": "east", "shipped_at": "2025-01-01 00:00:00", "promised_at": "2025-01-02 00:00:00", "delivered_at": "2025-01-02 00:00:01", "fulfillment_status": "delivered"},
            {"fulfillment_id": 3, "warehouse": "west", "shipped_at": "2025-01-01 00:00:00", "promised_at": "2025-01-02 00:00:00", "delivered_at": None, "fulfillment_status": "delivered"},
            {"fulfillment_id": 4, "warehouse": "west", "shipped_at": "2024-12-31 23:59:59", "promised_at": "2025-01-02 00:00:00", "delivered_at": "2025-01-01 00:00:00", "fulfillment_status": "delivered"},
        ]}
    if template_id == "sql.aggregation.product_unique_conversion":
        return {"product_events": [
            {"event_id": 1, "product_id": 1, "visitor_id": 7, "occurred_at": "2025-01-01 00:00:00", "event_name": "view"},
            {"event_id": 2, "product_id": 1, "visitor_id": 7, "occurred_at": "2025-01-01 00:01:00", "event_name": "view"},
            {"event_id": 3, "product_id": 1, "visitor_id": 7, "occurred_at": "2025-01-01 00:02:00", "event_name": "purchase"},
            {"event_id": 4, "product_id": 1, "visitor_id": 8, "occurred_at": "2025-01-01 00:03:00", "event_name": "purchase"},
            {"event_id": 5, "product_id": 2, "visitor_id": 9, "occurred_at": "2024-12-31 23:59:59", "event_name": "view"},
        ]}
    if template_id == "sql.cte.order_line_reconciliation":
        return {"orders": [
            {"order_id": 1, "ordered_on": "2025-01-01", "header_total_cents": 100, "order_status": "completed"},
            {"order_id": 2, "ordered_on": "2025-01-01", "header_total_cents": 0, "order_status": "completed"},
            {"order_id": 3, "ordered_on": "2025-01-01", "header_total_cents": 999, "order_status": "cancelled"},
        ], "order_lines": [{"line_id": 1, "order_id": 1, "quantity": 1, "unit_price_cents": 99}, {"line_id": 2, "order_id": 3, "quantity": 1, "unit_price_cents": 1}]}
    if template_id == "sql.cte.category_descendant_sales":
        return {"categories": [
            {"category_id": 1, "parent_category_id": None, "category_name": "Root"},
            {"category_id": 2, "parent_category_id": 1, "category_name": "Child"},
            {"category_id": 3, "parent_category_id": None, "category_name": "Empty"},
        ], "category_orders": [{"sale_id": 1, "category_id": 2, "sold_on": "2025-01-01", "amount_cents": 10, "sale_status": "completed"}, {"sale_id": 2, "category_id": 1, "sold_on": "2025-01-01", "amount_cents": 5, "sale_status": "completed"}, {"sale_id": 3, "category_id": 2, "sold_on": "2025-01-02", "amount_cents": 99, "sale_status": "cancelled"}]}
    if template_id == "sql.cte.session_funnel_completion":
        return {"sessions": [{"session_id": 1, "channel": "email", "started_at": "2025-01-01 00:00:00"}, {"session_id": 2, "channel": "search", "started_at": "2025-01-01 00:00:00"}], "session_events": [{"event_id": 1, "session_id": 1, "occurred_at": "2025-01-01 00:01:00", "event_name": "view"}, {"event_id": 2, "session_id": 1, "occurred_at": "2025-01-01 00:01:00", "event_name": "add_to_cart"}, {"event_id": 3, "session_id": 1, "occurred_at": "2025-01-01 00:01:00", "event_name": "checkout"}, {"event_id": 4, "session_id": 2, "occurred_at": "2025-01-01 00:01:00", "event_name": "checkout"}, {"event_id": 5, "session_id": 2, "occurred_at": "2025-01-01 00:02:00", "event_name": "add_to_cart"}, {"event_id": 6, "session_id": 2, "occurred_at": "2025-01-01 00:03:00", "event_name": "view"}]}
    if template_id == "sql.cte.customer_first_month_repeat":
        return {"customer_orders": [{"order_id": 1, "customer_id": 1, "ordered_at": "2025-01-31 23:00:00", "order_status": "completed"}, {"order_id": 2, "customer_id": 1, "ordered_at": "2025-02-01 00:00:00", "order_status": "completed"}, {"order_id": 3, "customer_id": 2, "ordered_at": "2025-02-01 00:00:00", "order_status": "completed"}, {"order_id": 4, "customer_id": 2, "ordered_at": "2025-02-01 00:00:00", "order_status": "completed"}, {"order_id": 5, "customer_id": 3, "ordered_at": "2024-12-31 00:00:00", "order_status": "completed"}]}
    if template_id == "sql.subqueries.customer_outreach":
        return {"outreach_activity": [
            {"activity_id": 1, "customer_id": 1, "contacted_on": "2025-01-01", "channel": "email", "status": "completed"},
            {"activity_id": 2, "customer_id": 1, "contacted_on": "2025-01-02", "channel": "email", "status": "completed"},
            {"activity_id": 3, "customer_id": 2, "contacted_on": "2025-01-01", "channel": "phone", "status": "completed"},
            {"activity_id": 4, "customer_id": 2, "contacted_on": "2025-01-02", "channel": "email", "status": "completed"},
            {"activity_id": 5, "customer_id": 3, "contacted_on": "2024-12-31", "channel": "email", "status": "completed"},
            {"activity_id": 6, "customer_id": 4, "contacted_on": "2025-01-01", "channel": "email", "status": "pending"},
        ]}
    if template_id == "sql.joins.logistics_final_leg":
        return {
            "shipments": [{"shipment_id": 71, "delivered_on": "2025-12-31", "final_leg_id": 3},
                          {"shipment_id": 72, "delivered_on": "2025-01-01", "final_leg_id": None}],
            "legs": [{"leg_id": 3, "carrier_id": 8, "depot": "West"},
                     {"leg_id": 4, "carrier_id": 9, "depot": "Decoy"}],
            "carriers": [{"carrier_id": 8, "carrier_name": "Road"},
                         {"carrier_id": 9, "carrier_name": "Air"}],
        }
    if (template_id, template_version) == ("sql.cte.inventory_net_flow", 2):
        # Separately authored input bags: identical rows count twice; widen before negation.
        receipt = {"movement_id": 71, "warehouse": "bag", "occurred_on": "2025-01-01", "units": 9, "status": "posted"}
        return {
            "receipts": [receipt, dict(receipt),
                         {"movement_id": 71, "warehouse": "bag", "occurred_on": "2025-12-31", "units": -4, "status": "posted"},
                         {"movement_id": 72, "warehouse": "excluded", "occurred_on": "2024-12-31", "units": 50, "status": "posted"}],
            "issues": [{"movement_id": 71, "warehouse": "bag", "occurred_on": "2025-12-31", "units": 14, "status": "posted"},
                       {"movement_id": 72, "warehouse": "minimum", "occurred_on": "2025-01-01", "units": -2147483648, "status": "posted"},
                       {"movement_id": 73, "warehouse": "excluded", "occurred_on": "2025-01-01", "units": 50, "status": "pending"},
                       {"movement_id": 74, "warehouse": "excluded", "occurred_on": "2026-01-01", "units": 50, "status": "posted"}],
        }
    if template_id == "sql.cte.inventory_net_flow":
        return {
            "receipts": [{"movement_id": 1, "warehouse": "X", "occurred_on": "2025-03-01", "units": 7, "status": "posted"},
                         {"movement_id": 2, "warehouse": "X", "occurred_on": "2025-03-01", "units": 7, "status": "posted"}],
            "issues": [{"movement_id": 1, "warehouse": "X", "occurred_on": "2025-03-02", "units": 14, "status": "posted"},
                       {"movement_id": 2, "warehouse": "Y", "occurred_on": "2025-03-02", "units": -2, "status": "posted"}],
        }
    if template_id == "sql.subqueries.education_all_required":
        return {
            "students": [{"student_id": 7, "program_id": 1}, {"student_id": 8, "program_id": 2}, {"student_id": 9, "program_id": 1}],
            "required_courses": [{"program_id": 1, "course_id": 11}, {"program_id": 1, "course_id": 12}],
            "attempts": [{"attempt_id": 1, "student_id": 7, "course_id": 11, "score": 50},
                         {"attempt_id": 2, "student_id": 7, "course_id": 12, "score": 50},
                         {"attempt_id": 3, "student_id": 9, "course_id": 11, "score": 100},
                         {"attempt_id": 4, "student_id": 9, "course_id": 12, "score": 49}],
        }
    if template_id == "sql.windows.media_previous_play":
        return {"plays": [
            {"play_id": 20, "viewer_id": 9, "title_id": 2, "played_at": "2025-08-01 00:00:00", "status": "completed"},
            {"play_id": 10, "viewer_id": 9, "title_id": 2, "played_at": "2025-08-01 00:00:00", "status": "completed"},
            {"play_id": 15, "viewer_id": 9, "title_id": 3, "played_at": "2025-08-01 00:00:00", "status": "completed"},
        ]}
    if template_id == "sql.temporal.clinic_weekly_visits":
        return {"visits": [
            {"visit_id": 1, "clinic": "West", "started_at": "2025-06-01 23:59:59", "status": "completed"},
            {"visit_id": 2, "clinic": "West", "started_at": "2025-06-02 00:00:00", "status": "completed"},
            {"visit_id": 3, "clinic": "West", "started_at": "2025-06-02 01:00:00", "status": "cancelled"},
        ]}
    if template_id == "sql.temporal.media_first_full_week_viewers":
        return {"viewing_events": [
            {"event_id": 1, "viewer_id": 8, "watched_at": "2025-05-01 10:00:00", "playback_status": "completed"},
            {"event_id": 2, "viewer_id": 8, "watched_at": "2025-05-02 10:00:00", "playback_status": "completed"},
            {"event_id": 3, "viewer_id": 8, "watched_at": "2025-05-03 10:00:00", "playback_status": "completed"},
            {"event_id": 4, "viewer_id": 8, "watched_at": "2025-05-04 10:00:00", "playback_status": "completed"},
            {"event_id": 5, "viewer_id": 8, "watched_at": "2025-05-05 10:00:00", "playback_status": "completed"},
            {"event_id": 6, "viewer_id": 8, "watched_at": "2025-05-06 10:00:00", "playback_status": "partial"},
            {"event_id": 7, "viewer_id": 8, "watched_at": "2025-05-07 10:00:00", "playback_status": "completed"},
            {"event_id": 8, "viewer_id": 9, "watched_at": "2025-12-25 10:00:00", "playback_status": "completed"},
            {"event_id": 9, "viewer_id": 9, "watched_at": "2025-12-26 10:00:00", "playback_status": "completed"},
            {"event_id": 10, "viewer_id": 9, "watched_at": "2025-12-27 10:00:00", "playback_status": "completed"},
            {"event_id": 11, "viewer_id": 9, "watched_at": "2025-12-28 10:00:00", "playback_status": "completed"},
            {"event_id": 12, "viewer_id": 9, "watched_at": "2025-12-29 10:00:00", "playback_status": "completed"},
            {"event_id": 13, "viewer_id": 9, "watched_at": "2025-12-30 10:00:00", "playback_status": "completed"},
            {"event_id": 14, "viewer_id": 9, "watched_at": "2025-12-31 10:00:00", "playback_status": "completed"},
        ]}
    if template_id == "sql.temporal.manufacturing_shift_downtime":
        return {"downtime_events": [
            {"event_id": 1, "line_code": "A", "shift_name": "day", "started_at": "2025-05-01 08:00:00", "ended_at": "2025-05-01 09:00:00", "event_status": "closed"},
            {"event_id": 2, "line_code": "A", "shift_name": "day", "started_at": "2025-05-01 10:00:00", "ended_at": "2025-05-01 10:30:00", "event_status": "closed"},
            {"event_id": 3, "line_code": "B", "shift_name": "night", "started_at": "2025-05-01 22:00:00", "ended_at": None, "event_status": "open"},
            {"event_id": 4, "line_code": "C", "shift_name": "day", "started_at": "2024-12-31 23:00:00", "ended_at": "2025-01-01 00:00:00", "event_status": "closed"},
        ]}
    if template_id == "sql.temporal.logistics_service_level_as_of":
        return {
            "shipments": [
                {"shipment_id": 8, "depot": "east", "accepted_at": "2025-06-01 00:00:00", "promised_at": "2025-06-02 00:00:00"},
                {"shipment_id": 9, "depot": "east", "accepted_at": "2025-06-01 00:00:00", "promised_at": "2025-06-02 00:00:00"},
            ],
            "tracking_events": [
                {"event_id": 1, "shipment_id": 8, "event_at": "2025-06-02 00:00:00", "tracking_state": "delivered"},
                {"event_id": 2, "shipment_id": 8, "event_at": "2025-06-30 23:59:59", "tracking_state": "returned"},
                {"event_id": 3, "shipment_id": 9, "event_at": "2025-06-02 00:00:01", "tracking_state": "delivered"},
                {"event_id": 4, "shipment_id": 9, "event_at": "2025-07-01 00:00:00", "tracking_state": "delivered"},
            ],
        }
    if template_id == "sql.temporal.saas_account_snapshot":
        return {"subscription_revisions": [
            {"revision_id": 1, "account_id": 8, "effective_at": "2025-06-01 00:00:00", "plan_name": "starter", "subscription_status": "active", "mrr_cents": 1000},
            {"revision_id": 2, "account_id": 8, "effective_at": "2025-07-01 00:00:00", "plan_name": "growth", "subscription_status": "active", "mrr_cents": 3000},
            {"revision_id": 3, "account_id": 9, "effective_at": "2025-06-01 00:00:00", "plan_name": "growth", "subscription_status": "active", "mrr_cents": 5000},
            {"revision_id": 4, "account_id": 9, "effective_at": "2025-06-01 00:00:00", "plan_name": "enterprise", "subscription_status": "active", "mrr_cents": 9000},
            {"revision_id": 5, "account_id": 10, "effective_at": "2025-06-01 00:00:00", "plan_name": "starter", "subscription_status": "cancelled", "mrr_cents": 0},
        ]}
    if template_id == "sql.retention.saas_repeat_payment":
        return {"billing": [
            {"invoice_id": 1, "account_id": 9, "paid_on": "2025-12-15", "status": "paid"},
            {"invoice_id": 2, "account_id": 9, "paid_on": "2026-01-14", "status": "paid"},
            {"invoice_id": 3, "account_id": 8, "paid_on": "2025-12-15", "status": "paid"},
            {"invoice_id": 4, "account_id": 8, "paid_on": "2026-01-15", "status": "paid"},
        ]}
    if template_id == "sql.funnel.support_resolution_chain":
        return {"ticket_events": [
            {"event_id": 1, "ticket_id": 9, "event_time": "2025-02-01 00:00:00", "state": "opened"},
            {"event_id": 2, "ticket_id": 9, "event_time": "2025-02-01 00:00:00", "state": "assigned"},
            {"event_id": 3, "ticket_id": 9, "event_time": "2025-02-01 00:00:00", "state": "reopened"},
            {"event_id": 4, "ticket_id": 9, "event_time": "2025-02-01 00:00:00", "state": "resolved"},
            {"event_id": 5, "ticket_id": 8, "event_time": "2025-02-01 00:00:00", "state": "resolved"},
            {"event_id": 6, "ticket_id": 8, "event_time": "2025-02-01 00:00:00", "state": "opened"},
            {"event_id": 7, "ticket_id": 8, "event_time": "2025-02-01 00:00:00", "state": "assigned"},
        ]}
    if template_id == "sql.funnel.checkout_paid_session":
        return {
            "sessions": [
                {"session_id": 10, "visitor_id": 1, "channel": "expiry-boundary", "started_at": "2025-02-01 09:00:00", "expires_at": "2025-02-01 10:00:00"},
                {"session_id": 11, "visitor_id": 2, "channel": "cross-session", "started_at": "2025-02-01 09:00:00", "expires_at": "2025-02-01 10:00:00"},
                {"session_id": 13, "visitor_id": 3, "channel": "pre-checkout", "started_at": "2025-02-01 09:00:00", "expires_at": "2025-02-01 10:00:00"},
                {"session_id": 14, "visitor_id": 4, "channel": "no-events", "started_at": "2025-02-01 09:00:00", "expires_at": "2025-02-01 10:00:00"},
            ],
            "session_events": [
                {"event_id": 1, "session_id": 10, "occurred_at": "2025-02-01 09:10:00", "event_name": "product_view"},
                {"event_id": 2, "session_id": 10, "occurred_at": "2025-02-01 09:10:00", "event_name": "add_to_cart"},
                {"event_id": 3, "session_id": 10, "occurred_at": "2025-02-01 09:10:00", "event_name": "checkout_started"},
                {"event_id": 4, "session_id": 11, "occurred_at": "2025-02-01 09:10:00", "event_name": "product_view"},
                {"event_id": 5, "session_id": 11, "occurred_at": "2025-02-01 09:20:00", "event_name": "add_to_cart"},
                {"event_id": 6, "session_id": 11, "occurred_at": "2025-02-01 09:30:00", "event_name": "checkout_started"},
                {"event_id": 7, "session_id": 13, "occurred_at": "2025-02-01 09:10:00", "event_name": "product_view"},
                {"event_id": 8, "session_id": 13, "occurred_at": "2025-02-01 09:20:00", "event_name": "add_to_cart"},
                {"event_id": 9, "session_id": 13, "occurred_at": "2025-02-01 09:30:00", "event_name": "checkout_started"},
            ],
            "payments": [
                {"payment_id": 1, "session_id": 10, "captured_at": "2025-02-01 10:00:00", "payment_status": "captured"},
                {"payment_id": 2, "session_id": 14, "captured_at": "2025-02-01 09:40:00", "payment_status": "captured"},
                {"payment_id": 3, "session_id": 13, "captured_at": "2025-02-01 09:25:00", "payment_status": "captured"},
            ],
        }
    if template_id == "sql.funnel.kyc_document_approval":
        return {
            "applications": [{"application_id": 10, "applicant_id": 1, "country": "US", "submitted_at": "2025-02-01 00:00:00"}, {"application_id": 11, "applicant_id": 2, "country": "US", "submitted_at": "2025-02-01 00:00:00"}],
            "country_document_requirements": [{"country": "US", "document_type": "passport"}, {"country": "US", "document_type": "proof_of_address"}],
            "identity_checks": [{"check_id": 1, "application_id": 10, "checked_at": "2025-02-01 01:00:00", "result": "passed"}, {"check_id": 2, "application_id": 11, "checked_at": "2025-02-01 01:00:00", "result": "passed"}],
            "document_reviews": [{"review_id": 1, "application_id": 10, "document_type": "passport", "reviewed_at": "2025-02-01 02:00:00", "result": "approved"}, {"review_id": 2, "application_id": 10, "document_type": "proof_of_address", "reviewed_at": "2025-02-01 03:00:00", "result": "approved"}, {"review_id": 3, "application_id": 11, "document_type": "passport", "reviewed_at": "2025-02-01 02:00:00", "result": "approved"}, {"review_id": 4, "application_id": 11, "document_type": "passport", "reviewed_at": "2025-02-01 03:00:00", "result": "rejected"}, {"review_id": 5, "application_id": 11, "document_type": "proof_of_address", "reviewed_at": "2025-02-01 03:00:00", "result": "approved"}],
            "approval_decisions": [{"decision_id": 1, "application_id": 10, "decided_at": "2025-02-02 00:00:00", "result": "approved"}, {"decision_id": 2, "application_id": 11, "decided_at": "2025-02-02 00:00:00", "result": "approved"}],
        }
    if template_id == "sql.funnel.parcel_exception_recovery":
        return {
            "parcels": [{"parcel_id": 10, "depot": "north", "accepted_at": "2025-02-01 00:00:00"}, {"parcel_id": 11, "depot": "south", "accepted_at": "2025-02-01 00:00:00"}],
            "parcel_scans": [{"scan_id": 1, "parcel_id": 10, "scanned_at": "2025-02-01 01:00:00", "scan_state": "exception"}, {"scan_id": 2, "parcel_id": 10, "scanned_at": "2025-02-01 01:10:00", "scan_state": "recovered"}, {"scan_id": 3, "parcel_id": 10, "scanned_at": "2025-02-01 01:30:00", "scan_state": "delivered"}, {"scan_id": 4, "parcel_id": 11, "scanned_at": "2025-02-01 01:00:00", "scan_state": "exception"}, {"scan_id": 5, "parcel_id": 11, "scanned_at": "2025-02-04 01:00:00", "scan_state": "recovered"}, {"scan_id": 6, "parcel_id": 11, "scanned_at": "2025-02-04 01:00:00", "scan_state": "delivered"}],
        }
    if template_id == "sql.funnel.curriculum_gate_completion":
        return {
            "enrollments": [{"enrollment_id": 10, "learner_id": 1, "cohort": "blue", "program_id": 1, "enrolled_at": "2025-02-01 00:00:00"}, {"enrollment_id": 11, "learner_id": 2, "cohort": "red", "program_id": 1, "enrolled_at": "2025-02-01 00:00:00"}],
            "program_modules": [{"program_id": 1, "module_id": 10, "stage_number": 1}, {"program_id": 1, "module_id": 20, "stage_number": 2}],
            "module_lessons": [{"module_id": 10, "lesson_id": 100}, {"module_id": 20, "lesson_id": 200}],
            "lesson_attempts": [{"attempt_id": 2, "enrollment_id": 10, "lesson_id": 100, "completed_at": "2025-02-01 01:00:00", "result": "passed"}, {"attempt_id": 1, "enrollment_id": 10, "lesson_id": 200, "completed_at": "2025-02-01 01:00:00", "result": "passed"}, {"attempt_id": 3, "enrollment_id": 11, "lesson_id": 100, "completed_at": "2025-02-01 01:00:00", "result": "passed"}, {"attempt_id": 4, "enrollment_id": 11, "lesson_id": 200, "completed_at": "2025-02-01 02:00:00", "result": "passed"}],
        }
    return None
