"""Synthetic domain fixtures; no oracle or candidate SQL dependencies.

Boundary rows are always present; seeds vary scale and input order.
This is fixture variety, not independent business-question variety.
"""
from __future__ import annotations

import random
from typing import Any

# Phase 4 library expansion contracts use a small, deliberately irregular event
# ledger.  The table name is contract-specific so schemas remain isolated even
# where the reconciliation shape is shared.
_EXPANSION_TABLES = {
    "payments_country_transfer": "transfers", "clinic_scheduled_clinician": "appointments",
    "manufacturing_approved_supplier": "part_usage", "education_completed_enrollment": "enrollments",
    "manufacturing_line_scrap": "production_runs", "saas_mrr_changes": "plan_changes",
    "logistics_depot_delay": "shipment_stops", "payments_no_settlement": "merchant_events",
    "support_unresolved_reopen": "agent_events", "payments_risk_rank": "merchant_settlements",
    "logistics_previous_stop": "parcel_stops", "saas_trial_activation": "account_events",
    "inventory_daily_stock": "stock_events", "refund_prefer_approved": "refund_requests",
    "payments_latest_profile": "profile_revisions", "media_week_two_return": "viewer_plays",
    "clinic_followup_window": "patient_visits", "saas_activation_payment": "account_funnel",
    "logistics_parcel_delivery": "parcel_scans",
}


def business_tables(name: str, seed: int) -> dict[str, list[dict[str, Any]]]:
    if name in {"language_titles", "pareto_shipping", "renewal_coverage", "queue_batches"}:
        from ..verification.qualification.delivery_profiles import PROFILE_MODULES, get_profile

        pair = next(pair for pair, module in PROFILE_MODULES.items() if module == name + "_profile")
        profile = get_profile(*pair)
        assert profile is not None
        result: dict[str, list[dict[str, Any]]] = profile.fixture(seed, 0)
        return result
    if name == "lowest_quote_v1":
        from ..verification.qualification.lowest_quote_profile import fixture

        return fixture(seed, 0)
    rng = random.Random(seed)
    scale = rng.randint(1, 9)
    tables: dict[str, list[tuple[Any, ...]]]
    if name == "saas_activation_payment":
        # Contract-specific funnel rows: state, ordering, and completion value
        # are observable without changing the shared ledger fixture path.
        tables = {"account_funnel": [
            (1, 1, "north", "2025-01-01 09:00:00", "signup", 1, 1),
            (2, 1, "north", "2025-01-01 09:00:00", "trial", 2, 2),
            (3, 1, "north", "2025-01-01 09:00:00", "activation", 3, 3),
            (4, 1, "north", "2025-01-01 09:00:00", "payment", 40, 4),
            (5, 2, "north", "2025-02-01 09:00:00", "trial", 2, 1),
            (6, 2, "north", "2025-02-01 10:00:00", "signup", 1, 2),
            (7, 2, "north", "2025-02-01 10:30:00", "trial", 2, 3),
            (8, 2, "north", "2025-02-01 11:00:00", "activation", 3, 4),
            (9, 2, "north", "2025-02-01 12:00:00", "payment", 50, 5),
            (10, 2, "north", "2025-02-01 13:00:00", "payment", 500, 6),
            (11, 3, "south", "2025-03-01 09:00:00", "signup", 1, 1),
            (12, 3, "south", "2025-03-01 10:00:00", "signup", 9, 2),
            (13, 3, "south", "2025-03-01 11:00:00", "trial", 2, 3),
            (14, 3, "south", "2025-03-01 12:00:00", "activation", 3, 4),
            (15, 4, "south", "2025-04-01 09:00:00", "signup", 1, 1),
            (16, 4, "south", "2025-04-01 10:00:00", "trial", 2, 2),
            (17, 5, "west", "2024-12-31 23:59:00", "signup", 99, 1),
            (18, 5, "west", "2025-01-01 01:00:00", "cancelled", 99, 2),
            (19, 6, "north", "2025-05-01 09:00:00", "signup", 1, 1),
            (20, 6, "north", "2025-05-01 10:00:00", "activation", 3, 2),
            (21, 6, "north", "2025-05-01 11:00:00", "payment", 60, 3),
            (22, 7, "north", "2025-06-01 09:00:00", "signup", 1, 1),
            (23, 7, "north", "2025-06-01 10:00:00", "trial", 2, 2),
            (24, 7, "north", "2025-06-01 11:00:00", "payment", 700, 3),
            (25, 7, "north", "2025-06-01 12:00:00", "activation", 3, 4),
            (26, 7, "north", "2025-06-01 13:00:00", "payment", 70, 5),
            (27, 8, "south", "2024-12-31 23:00:00", "signup", 1, 1),
            (28, 8, "south", "2025-01-01 09:00:00", "trial", 2, 2),
            (29, 8, "south", "2025-01-01 10:00:00", "activation", 3, 3),
            (30, 8, "south", "2025-01-01 11:00:00", "payment", 80, 4),
        ]}
        columns = {"account_funnel": "record_id entity_id group_key occurred_at status amount sequence"}
    elif name == "logistics_parcel_delivery":
        # Parcel scans use the same ledger shape as SaaS, but deliberately have
        # logistics-specific steps and depot outcomes.
        tables = {"parcel_scans": [
            (1, 1, "north", "2025-01-01 09:00:00", "accepted", 1, 1),
            (2, 1, "north", "2025-01-01 09:00:00", "sorted", 2, 2),
            (3, 1, "north", "2025-01-01 10:00:00", "dispatched", 3, 3),
            (4, 1, "north", "2025-01-01 11:00:00", "delivered", 40, 4),
            (5, 2, "north", "2025-02-01 08:00:00", "sorted", 2, 1),
            (6, 2, "north", "2025-02-01 09:00:00", "accepted", 1, 2),
            (7, 2, "north", "2025-02-01 10:00:00", "sorted", 2, 3),
            (8, 2, "north", "2025-02-01 11:00:00", "dispatched", 3, 4),
            (9, 2, "north", "2025-02-01 12:00:00", "delivered", 50, 5),
            (10, 3, "south", "2025-03-01 09:00:00", "accepted", 1, 1),
            (11, 3, "south", "2025-03-01 10:00:00", "dispatched", 3, 2),
            (12, 3, "south", "2025-03-01 11:00:00", "delivered", 60, 3),
            (13, 4, "west", "2025-04-01 09:00:00", "accepted", 1, 1),
            (14, 4, "west", "2025-04-01 10:00:00", "sorted", 2, 2),
            (15, 5, "east", "2025-05-01 09:00:00", "accepted", 1, 1),
            (16, 5, "east", "2025-05-01 09:00:00", "sorted", 2, 2),
            (17, 5, "east", "2025-05-01 09:00:00", "dispatched", 3, 3),
            (18, 5, "east", "2025-05-01 09:00:00", "delivered", 60, 4),
            (19, 6, "east", "2024-12-31 23:00:00", "accepted", 1, 1),
            (20, 6, "east", "2025-01-01 01:00:00", "delivered", 99, 2),
            (21, 7, "central", "2025-06-01 09:00:00", "exception", 999, 1),
        ]}
        columns = {"parcel_scans": "record_id entity_id group_key occurred_at status amount sequence"}
    elif name == "logistics_parcel_delivery_v2":
        tables = {"parcel_scans": [
            (1, 1, "north", "2025-01-01 09:00:00", "accepted", 0, 1),
            (2, 1, "north", "2025-01-01 09:10:00", "sorted", 0, 2),
            (3, 1, "north", "2025-01-01 09:20:00", "dispatched", 0, 3),
            (4, 1, "north", "2025-01-01 09:30:00", "delivered", 40, 4),
            (5, 2, "north", "2025-02-01 09:00:00", "accepted", 0, 1),
            (6, 2, "north", "2025-02-01 09:10:00", "sorted", 0, 2),
            (7, 2, "north", "2025-02-01 09:20:00", "accepted", 0, 3),
            (8, 2, "north", "2025-02-01 09:30:00", "sorted", 0, 4),
            (9, 2, "north", "2025-02-01 09:40:00", "dispatched", 0, 5),
            (10, 2, "north", "2025-02-01 09:50:00", "delivered", 50, 6),
            (11, 3, "south", "2025-03-01 09:00:00", "accepted", 0, 1),
            (12, 3, "south", "2025-03-01 10:01:00", "sorted", 0, 2),
            (13, 3, "south", "2025-03-01 10:10:00", "dispatched", 0, 3),
            (14, 3, "south", "2025-03-01 10:20:00", "delivered", 60, 4),
            (15, 4, "east", "2025-04-01 09:00:00", "accepted", 0, 1),
            (16, 4, "east", "2025-04-01 09:10:00", "sorted", 0, 2),
            (17, 4, "east", "2025-04-01 09:20:00", "dispatched", 0, 3),
            (18, 4, "east", "2025-04-01 10:20:00", "delivered", 70, 4),
            (19, 5, "west", "2024-12-31 23:59:00", "accepted", 0, 1),
            (20, 5, "west", "2025-01-01 00:00:00", "sorted", 0, 2),
        ]}
        columns = {"parcel_scans": "record_id entity_id group_key occurred_at status amount sequence"}
    elif name in _EXPANSION_TABLES:
        table = _EXPANSION_TABLES[name]
        # The fixed boundary rows make predicate, aggregation, ordering, and
        # sequence mistakes observable; scale keeps normal fixtures seed-varied.
        rows = [
            (1, 1, "north", "2025-01-01 00:00:00", "eligible", 10 * scale, 1),
            (2, 1, "north", "2025-01-02 00:00:00", "eligible", 20 * scale, 2),
            (3, 2, "south", "2025-01-31 00:00:00", "eligible", 5 * scale, 1),
            (4, 2, "south", "2025-02-01 00:00:00", "ineligible", 999, 2),
            (5, 3, "north", "2024-12-31 00:00:00", "eligible", 700, 1),
            (6, 3, "east", "2026-01-01 00:00:00", "eligible", -3 * scale, 2),
            (7, 4, "east", "2025-06-01 00:00:00", "eligible", 0, 1),
            (8, 1, "north", "2025-01-02 00:00:00", "eligible", 20 * scale, 3),
        ]
        columns = {table: "record_id entity_id group_key occurred_at status amount sequence"}
        tables = {table: rows}
    elif name == "logistics_final_leg":
        tables = {
            "shipments": [(1, "2025-01-01", 10), (2, "2025-12-31", 20),
                          (3, None, 10), (4, "2026-01-01", 10),
                          (5, "2025-06-01", 99), (6, "2025-06-01", 30),
                          (7, "2024-12-31", 10)],
            "legs": [(10, 1, "North"), (20, 2, "South"), (30, 99, "East"),
                     (40, 1, "Unused")],
            "carriers": [(1, "Local"), (2, "Express"), (3, "Unused")],
        }
        columns = {"shipments": "shipment_id delivered_on final_leg_id",
                   "legs": "leg_id carrier_id depot", "carriers": "carrier_id carrier_name"}
    elif name == "inventory_net_flow":
        tables = {
            "receipts": [(1, "A", "2025-01-01", 10 * scale, "posted"),
                         (2, "A", "2025-01-01", 10 * scale, "posted"),
                         (3, "B", "2025-06-01", 0, "posted"),
                         (4, "C", "2024-12-31", 100, "posted"),
                         (5, "B", "2025-06-01", 500, "draft"),
                         (6, "D", "2025-12-31", -scale, "posted")],
            "issues": [(1, "A", "2025-06-01", 5 * scale, "posted"),
                       (2, "E", "2025-06-01", 3 * scale, "posted"),
                       (3, "A", "2026-01-01", 900, "posted")],
        }
        columns = {t: "movement_id warehouse occurred_on units status" for t in tables}
    elif name == "education_all_required":
        tables = {"students": [(1, 10), (2, 10), (3, 10), (4, 20), (5, 30)],
                  "required_courses": [(10, 100), (10, 101), (10, 101), (20, 200)],
                  "attempts": [(1, 1, 100, 50), (2, 1, 101, 90), (3, 1, 100, 10),
                               (4, 2, 100, 99), (5, 2, 999, 99), (6, 3, 100, 60),
                               (7, 3, 101, None), (8, 4, 200, 49), (9, 1, 101, 90)]}
        columns = {"students": "student_id program_id", "required_courses": "program_id course_id",
                   "attempts": "attempt_id student_id course_id score"}
    elif name == "media_previous_play":
        tables = {"plays": [(1, 1, 10, "2025-01-01 00:00:00", "completed"),
                            (2, 1, 10, "2025-01-01 00:00:00", "completed"),
                            (3, 1, 20, "2025-01-02 00:00:00", "completed"),
                            (4, 2, 10, "2025-01-02 00:00:00", "completed"),
                            (5, 1, 10, "2025-01-03 00:00:00", "partial"),
                            (6, 1, 10, "2025-01-04 00:00:00", "completed"),
                            (7, 1, 10, "2024-12-31 00:00:00", "completed")]}
        columns = {"plays": "play_id viewer_id title_id played_at status"}
    elif name == "clinic_weekly_visits":
        tables = {"visits": [(1, "A", "2025-01-01 00:00:00", "completed"),
                             (2, "A", "2025-01-05 23:59:59", "completed"),
                             (3, "A", "2025-01-06 00:00:00", "completed"),
                             (4, "B", "2025-12-31 23:59:59", "completed"),
                             (5, "A", "2026-01-01 00:00:00", "completed"),
                             (6, "A", None, "completed"),
                             (7, "B", "2025-06-01 00:00:00", "cancelled"),
                             (8, "A", "2025-01-01 01:00:00", "completed")]}
        columns = {"visits": "visit_id clinic started_at status"}
    elif name == "media_first_full_week_viewers":
        tables = {"viewing_events": [
            (1, 1, "2025-01-01 10:00:00", "completed"), (2, 1, "2025-01-02 10:00:00", "completed"),
            (3, 1, "2025-01-03 10:00:00", "completed"), (4, 1, "2025-01-04 10:00:00", "completed"),
            (5, 1, "2025-01-05 10:00:00", "completed"), (6, 1, "2025-01-06 10:00:00", "completed"),
            (7, 1, "2025-01-07 10:00:00", "completed"), (8, 1, "2025-01-07 11:00:00", "completed"),
            (9, 2, "2025-02-01 10:00:00", "completed"), (10, 2, "2025-02-02 10:00:00", "completed"),
            (11, 2, "2025-02-03 10:00:00", "completed"), (12, 2, "2025-02-04 10:00:00", "completed"),
            (13, 2, "2025-02-06 10:00:00", "completed"), (14, 3, "2024-12-31 23:00:00", "completed"),
            (15, 3, "2025-01-01 10:00:00", "partial"), (16, 4, "2025-12-31 10:00:00", "completed"),
        ]}
        columns = {"viewing_events": "event_id viewer_id watched_at playback_status"}
    elif name == "manufacturing_shift_downtime":
        tables = {"downtime_events": [
            (1, "A", "day", "2025-01-01 08:00:00", "2025-01-01 08:30:00", "closed"),
            (2, "A", "day", "2025-01-01 09:00:00", "2025-01-01 09:45:00", "closed"),
            (3, "A", "night", "2025-01-02 22:00:00", "2025-01-03 00:00:00", "closed"),
            (4, "B", "day", "2025-06-01 08:00:00", None, "open"),
            (5, "B", "day", "2025-06-01 09:00:00", "2025-06-01 08:55:00", "closed"),
            (6, "B", "night", "2024-12-31 23:00:00", "2025-01-01 00:00:00", "closed"),
            (7, "C", "day", "2025-02-01 08:00:00", "2025-02-01 08:10:00", "maintenance"),
        ]}
        columns = {"downtime_events": "event_id line_code shift_name started_at ended_at event_status"}
    elif name == "logistics_service_level_as_of":
        tables = {
            "shipments": [(1, "north", "2025-01-01 00:00:00", "2025-01-03 00:00:00"), (2, "north", "2025-01-02 00:00:00", "2025-01-03 00:00:00"), (3, "south", "2025-03-01 00:00:00", "2025-03-02 00:00:00"), (4, "south", "2025-04-01 00:00:00", "2025-04-03 00:00:00"), (5, "legacy", "2024-12-31 00:00:00", "2025-01-02 00:00:00")],
            "tracking_events": [(1, 1, "2025-01-02 12:00:00", "in_transit"), (2, 1, "2025-01-03 00:00:00", "delivered"), (3, 2, "2025-01-03 00:00:01", "delivered"), (4, 3, "2025-03-01 12:00:00", "in_transit"), (5, 3, "2025-03-02 00:00:00", "delivered"), (6, 4, "2025-04-02 00:00:00", "delivered"), (7, 4, "2025-07-01 00:00:00", "returned"), (8, 5, "2025-01-01 00:00:00", "delivered")],
        }
        columns = {"shipments": "shipment_id depot accepted_at promised_at", "tracking_events": "event_id shipment_id event_at tracking_state"}
    elif name == "saas_account_snapshot":
        tables = {"subscription_revisions": [
            (1, 1, "2025-01-01 00:00:00", "starter", "active", 1000), (2, 1, "2025-06-01 00:00:00", "growth", "active", 3000),
            (3, 2, "2025-02-01 00:00:00", "starter", "active", 1000), (4, 2, "2025-06-15 00:00:00", "starter", "cancelled", 0),
            (5, 3, "2025-03-01 00:00:00", "growth", "active", 5000), (6, 3, "2025-03-01 00:00:00", "enterprise", "active", 9000),
            (7, 4, "2025-08-01 00:00:00", "starter", "active", 1000), (8, 5, "2024-12-31 00:00:00", "legacy", "active", 700),
            (9, 6, "2025-04-01 00:00:00", "growth", "active", -500),
        ]}
        columns = {"subscription_revisions": "revision_id account_id effective_at plan_name subscription_status mrr_cents"}
    elif name == "saas_repeat_payment":
        tables = {"billing": [(1, 1, "2025-01-01", "paid"), (2, 1, "2025-01-31", "paid"),
                              (3, 2, "2025-01-01", "paid"), (4, 2, "2025-02-01", "paid"),
                              (5, 3, "2024-12-31", "paid"), (6, 3, "2025-01-01", "paid"),
                              (7, 4, "2025-01-01", "paid"), (8, 4, "2025-01-01", "paid"),
                              (9, 5, None, "paid"), (10, 5, "2025-01-01", "open"),
                              (11, 1, "2025-01-02", "open"),
                              (12, 6, "2025-05-01", "paid"),
                              (13, 6, "2025-05-02", "paid")]}
        columns = {"billing": "invoice_id account_id paid_on status"}
    elif name == "support_resolution_chain":
        tables = {"ticket_events": [(1, 1, "2025-01-01 00:00:00", "resolved"),
                                    (2, 1, "2025-01-02 00:00:00", "opened"),
                                    (3, 1, "2025-01-03 00:00:00", "assigned"),
                                    (4, 2, "2025-01-01 00:00:00", "opened"),
                                    (5, 2, "2025-01-01 00:00:00", "assigned"),
                                    (6, 2, "2025-01-01 00:00:00", "resolved"),
                                    (7, 3, "2025-01-01 00:00:00", "opened"),
                                    (8, 3, "2025-01-01 00:00:00", "opened"),
                                    (9, 3, "2025-01-02 00:00:00", "resolved"),
                                    (10, 4, "2024-12-31 00:00:00", "opened"),
                                    (11, 4, "2025-01-01 00:00:00", "assigned"),
                                    (12, 4, "2025-01-02 00:00:00", "resolved"),
                                    (13, 5, "2025-02-01 00:00:00", "opened"),
                                    (14, 5, "2025-02-02 00:00:00", "assigned"),
                                    (15, 5, "2025-02-02 01:00:00", "assigned"),
                                    (16, 5, "2025-02-03 00:00:00", "resolved")]}
        columns = {"ticket_events": "event_id ticket_id event_time state"}
    elif name == "checkout_paid_session":
        tables = {
            "sessions": [
                (1, 101, "email", "2025-01-01 09:00:00", "2025-01-01 10:00:00"),
                (2, 102, "search", "2025-01-02 09:00:00", "2025-01-02 10:00:00"),
                (3, 103, "social", "2025-01-03 09:00:00", "2025-01-03 10:00:00"),
                (4, 104, "referral", "2025-01-04 09:00:00", "2025-01-04 10:00:00"),
                (5, 105, "email", "2025-01-05 09:00:00", "2025-01-05 10:00:00"),
                (6, 106, "legacy", "2024-12-31 09:00:00", "2024-12-31 10:00:00"),
            ],
            "session_events": [
                (1, 1, "2025-01-01 09:10:00", "product_view"),
                (2, 1, "2025-01-01 09:10:00", "add_to_cart"),
                (3, 1, "2025-01-01 09:10:00", "checkout_started"),
                (4, 2, "2025-01-02 09:10:00", "product_view"),
                (5, 3, "2025-01-03 09:20:00", "checkout_started"),
                (6, 3, "2025-01-03 09:30:00", "add_to_cart"),
                (7, 3, "2025-01-03 09:40:00", "product_view"),
                (8, 4, "2025-01-04 09:20:00", "add_to_cart"),
                (9, 4, "2025-01-04 09:10:00", "product_view"),
                (10, 4, "2025-01-04 09:30:00", "checkout_started"),
                (11, 5, "2025-01-05 09:10:00", "product_view"),
                (12, 5, "2025-01-05 09:20:00", "add_to_cart"),
                (13, 5, "2025-01-05 09:30:00", "checkout_started"),
                (14, 6, "2024-12-31 09:10:00", "product_view"),
            ],
            "payments": [
                (1, 1, "2025-01-01 10:00:00", "captured"),
                (2, 2, "2025-01-02 09:30:00", "captured"),
                (3, 3, "2025-01-03 09:10:00", "captured"),
                (4, 4, "2025-01-04 09:45:00", "captured"),
                (5, 5, "2025-01-05 10:00:01", "captured"),
                (6, 1, "2025-01-01 09:50:00", "failed"),
                (7, 6, "2024-12-31 09:30:00", "captured"),
            ],
        }
        columns = {
            "sessions": "session_id visitor_id channel started_at expires_at",
            "session_events": "event_id session_id occurred_at event_name",
            "payments": "payment_id session_id captured_at payment_status",
        }
    elif name == "kyc_document_approval":
        tables = {
            "applications": [(1, 11, "US", "2025-01-01 00:00:00"), (2, 12, "US", "2025-01-02 00:00:00"), (3, 13, "IN", "2025-01-03 00:00:00"), (4, 14, "DE", "2025-01-04 00:00:00"), (5, 15, "US", "2025-01-05 00:00:00"), (6, 16, "US", "2024-12-31 00:00:00")],
            "country_document_requirements": [("US", "passport"), ("US", "proof_of_address"), ("IN", "pan"), ("DE", "id_card")],
            "identity_checks": [(1, 1, "2025-01-01 01:00:00", "passed"), (2, 2, "2025-01-02 01:00:00", "passed"), (3, 3, "2025-01-03 01:00:00", "passed"), (4, 4, "2025-01-04 01:00:00", "passed"), (5, 5, "2025-01-05 01:00:00", "failed"), (6, 6, "2024-12-31 01:00:00", "passed")],
            "document_reviews": [(1, 1, "passport", "2025-01-01 02:00:00", "approved"), (2, 1, "proof_of_address", "2025-01-01 03:00:00", "approved"), (3, 2, "passport", "2025-01-02 02:00:00", "approved"), (4, 2, "passport", "2025-01-02 03:00:00", "rejected"), (5, 2, "proof_of_address", "2025-01-02 04:00:00", "approved"), (6, 3, "pan", "2025-01-03 03:00:00", "approved"), (7, 4, "id_card", "2025-01-18 00:00:00", "approved"), (8, 6, "passport", "2024-12-31 02:00:00", "approved"), (9, 6, "proof_of_address", "2024-12-31 03:00:00", "approved")],
            "approval_decisions": [(1, 1, "2025-01-02 00:00:00", "approved"), (2, 2, "2025-01-03 00:00:00", "approved"), (3, 3, "2025-01-03 02:00:00", "approved"), (4, 4, "2025-01-18 00:00:00", "approved"), (5, 5, "2025-01-06 00:00:00", "approved"), (6, 6, "2025-01-01 00:00:00", "approved")],
        }
        columns = {"applications": "application_id applicant_id country submitted_at", "country_document_requirements": "country document_type", "identity_checks": "check_id application_id checked_at result", "document_reviews": "review_id application_id document_type reviewed_at result", "approval_decisions": "decision_id application_id decided_at result"}
    elif name == "parcel_exception_recovery":
        tables = {
            "parcels": [(1, "north", "2025-01-01 00:00:00"), (2, "north", "2025-01-02 00:00:00"), (3, "north", "2025-01-03 00:00:00"), (4, "south", "2025-01-04 00:00:00"), (5, "south", "2025-01-05 00:00:00"), (6, "legacy", "2024-12-31 00:00:00")],
            "parcel_scans": [(1, 1, "2025-01-01 01:00:00", "exception"), (2, 1, "2025-01-01 01:30:00", "recovered"), (3, 1, "2025-01-01 02:00:00", "delivered"), (4, 2, "2025-01-02 01:00:00", "exception"), (5, 2, "2025-01-02 01:30:00", "recovered"), (6, 2, "2025-01-02 02:00:00", "exception"), (7, 2, "2025-01-02 02:30:00", "recovered"), (8, 2, "2025-01-02 03:00:00", "delivered"), (9, 3, "2025-01-03 01:00:00", "exception"), (10, 3, "2025-01-03 02:00:00", "delivered"), (11, 4, "2025-01-04 01:00:00", "exception"), (12, 4, "2025-01-07 01:00:00", "recovered"), (13, 4, "2025-01-07 01:00:00", "delivered"), (14, 5, "2025-01-05 01:00:00", "exception"), (15, 5, "2025-01-08 01:01:00", "recovered"), (16, 5, "2025-01-08 01:02:00", "delivered"), (17, 6, "2024-12-31 01:00:00", "exception")],
        }
        columns = {"parcels": "parcel_id depot accepted_at", "parcel_scans": "scan_id parcel_id scanned_at scan_state"}
    elif name == "curriculum_gate_completion":
        tables = {
            "enrollments": [(1, 101, "alpha", 1, "2025-01-01 00:00:00"), (2, 102, "alpha", 1, "2025-01-01 00:00:00"), (3, 103, "beta", 2, "2025-01-01 00:00:00"), (4, 104, "gamma", 2, "2025-01-01 00:00:00"), (5, 105, "legacy", 1, "2024-12-31 00:00:00")],
            "program_modules": [(1, 10, 1), (1, 20, 2), (2, 30, 1)],
            "module_lessons": [(10, 1001), (10, 1002), (20, 2001), (30, 3001)],
            "lesson_attempts": [(1, 1, 1001, "2025-01-01 01:00:00", "passed"), (2, 1, 1002, "2025-01-01 02:00:00", "passed"), (3, 1, 2001, "2025-01-01 03:00:00", "passed"), (4, 2, 1001, "2025-01-01 01:00:00", "passed"), (5, 2, 1002, "2025-01-01 02:00:00", "failed"), (6, 2, 2001, "2025-01-01 03:00:00", "passed"), (7, 3, 3001, "2025-01-01 01:00:00", "passed"), (8, 4, 3001, "2025-01-01 01:00:00", "failed"), (9, 5, 1001, "2024-12-31 01:00:00", "passed"), (10, 5, 1002, "2024-12-31 02:00:00", "passed"), (11, 5, 2001, "2024-12-31 03:00:00", "passed")],
        }
        columns = {"enrollments": "enrollment_id learner_id cohort program_id enrolled_at", "program_modules": "program_id module_id stage_number", "module_lessons": "module_id lesson_id", "lesson_attempts": "attempt_id enrollment_id lesson_id completed_at result"}
    elif name == "warehouse_throughput":
        tables = {"warehouse_loads": [
            (1, "A", "2025-01-01", 60, "posted"),
            (2, "A", "2025-02-01", 50, "posted"),
            (3, "B", "2025-01-15", 30, "posted"),
            (4, "B", "2025-03-01", 20, "posted"),
            (5, "C", "2025-01-01", 0, "posted"),
            (6, "D", "2025-01-01", 500, "draft"),
            (7, "E", "2024-12-31", 900, "posted"),
            (8, "A", "2025-12-31", 40, "posted"),
            (9, "F", "2025-05-01", -200, "posted"),
        ]}
        columns = {"warehouse_loads": "load_id warehouse loaded_on units status"}
    elif name == "fulfillment_sla_dashboard":
        tables = {"fulfillments": [
            (1, "east", "2025-01-01 08:00:00", "2025-01-03 08:00:00", "2025-01-03 08:00:00", "delivered"),
            (2, "east", "2025-01-02 08:00:00", "2025-01-03 08:00:00", "2025-01-03 08:00:01", "delivered"),
            (3, "west", "2025-02-01 08:00:00", "2025-02-02 08:00:00", None, "in_transit"),
            (4, "west", "2025-02-02 08:00:00", "2025-02-03 08:00:00", "2025-02-02 12:00:00", "delivered"),
            (5, "north", "2024-12-31 23:59:59", "2025-01-02 00:00:00", "2025-01-01 00:00:00", "delivered"),
            (6, "north", "2025-06-01 08:00:00", "2025-06-02 08:00:00", "2025-06-01 10:00:00", "cancelled"),
            (7, "east", "2025-12-31 08:00:00", "2026-01-01 08:00:00", "2026-01-01 08:00:00", "delivered"),
        ]}
        columns = {"fulfillments": "fulfillment_id warehouse shipped_at promised_at delivered_at fulfillment_status"}
    elif name == "product_unique_conversion":
        tables = {"product_events": [
            (1, 10, 1, "2025-01-01 09:00:00", "view"), (2, 10, 1, "2025-01-01 09:01:00", "view"),
            (3, 10, 1, "2025-01-01 09:02:00", "purchase"), (4, 10, 2, "2025-01-02 09:00:00", "view"),
            (5, 20, 3, "2025-02-01 09:00:00", "purchase"), (6, 20, 4, "2025-02-01 09:01:00", "view"),
            (7, 30, 5, "2024-12-31 23:59:59", "view"), (8, 30, 5, "2025-01-01 00:00:00", "cart"),
            (9, 40, 6, "2025-03-01 09:00:00", "view"),
        ]}
        columns = {"product_events": "event_id product_id visitor_id occurred_at event_name"}
    elif name == "order_line_reconciliation":
        tables = {
            "orders": [(1, "2025-01-01", 300, "completed"), (2, "2025-01-02", 200, "completed"), (3, "2025-01-03", 5, "completed"), (4, "2025-01-04", 100, "cancelled"), (5, "2024-12-31", 500, "completed")],
            "order_lines": [(1, 1, 1, 100), (2, 1, 2, 100), (3, 2, 1, 150), (4, 2, 1, 25), (5, 4, 1, 100), (6, 5, 1, 500)],
        }
        columns = {"orders": "order_id ordered_on header_total_cents order_status", "order_lines": "line_id order_id quantity unit_price_cents"}
    elif name == "category_descendant_sales":
        tables = {
            "categories": [(1, None, "Root"), (2, 1, "Hardware"), (3, 2, "Laptops"), (4, 1, "Books"), (5, None, "Empty")],
            "category_orders": [(1, 3, "2025-01-01", 100, "completed"), (2, 2, "2025-01-02", 50, "completed"), (3, 4, "2025-01-03", 75, "completed"), (4, 3, "2025-01-04", 999, "cancelled"), (5, 3, "2024-12-31", 900, "completed"), (6, 5, "2025-01-01", 0, "completed")],
        }
        columns = {"categories": "category_id parent_category_id category_name", "category_orders": "sale_id category_id sold_on amount_cents sale_status"}
    elif name == "session_funnel_completion":
        tables = {
            "sessions": [(1, "email", "2025-01-01 09:00:00"), (2, "search", "2025-01-02 09:00:00"), (3, "email", "2025-01-03 09:00:00"), (4, "social", "2025-01-04 09:00:00"), (5, "legacy", "2024-12-31 09:00:00")],
            "session_events": [(1, 1, "2025-01-01 09:01:00", "view"), (2, 1, "2025-01-01 09:01:00", "add_to_cart"), (3, 1, "2025-01-01 09:01:00", "checkout"), (4, 2, "2025-01-02 09:03:00", "checkout"), (5, 2, "2025-01-02 09:02:00", "add_to_cart"), (6, 2, "2025-01-02 09:01:00", "view"), (7, 3, "2025-01-03 09:01:00", "view"), (8, 3, "2025-01-03 09:02:00", "add_to_cart"), (9, 4, "2025-01-04 09:01:00", "view"), (10, 5, "2024-12-31 09:01:00", "view")],
        }
        columns = {"sessions": "session_id channel started_at", "session_events": "event_id session_id occurred_at event_name"}
    elif name == "customer_first_month_repeat":
        tables = {"customer_orders": [
            (1, 1, "2025-01-01 09:00:00", "completed"), (2, 1, "2025-01-31 23:59:00", "completed"),
            (3, 2, "2025-01-31 09:00:00", "completed"), (4, 2, "2025-02-01 09:00:00", "completed"),
            (5, 3, "2025-02-01 09:00:00", "completed"), (6, 3, "2025-02-01 09:00:00", "completed"),
            (7, 4, "2024-12-31 09:00:00", "completed"), (8, 4, "2025-01-01 09:00:00", "completed"),
            (9, 5, "2025-03-01 09:00:00", "cancelled"), (10, 5, "2025-03-02 09:00:00", "completed"),
        ]}
        columns = {"customer_orders": "order_id customer_id ordered_at order_status"}
    elif name == "top_category_sales":
        tables = {"category_sales": [
            (1, "electronics", "2025-01-01", 100, "completed"),
            (2, "electronics", "2025-02-01", 150, "completed"),
            (3, "apparel", "2025-01-01", 200, "completed"),
            (4, "apparel", "2025-02-01", 50, "completed"),
            (5, "books", "2025-01-01", 100, "completed"),
            (6, "books", "2025-01-01", 999, "cancelled"),
            (7, "toys", "2024-12-31", 999, "completed"),
            (8, "groceries", "2025-03-01", 0, "completed"),
        ]}
        columns = {"category_sales": "sale_id category sold_on amount status"}
    elif name == "customer_outreach":
        tables = {"outreach_activity": [
            (1, 1, "2025-01-01", "email", "completed"),
            (2, 1, "2025-01-02", "email", "completed"),
            (3, 2, "2025-01-01", "phone", "completed"),
            (4, 3, "2025-01-01", "email", "pending"),
            (5, 4, "2024-12-31", "email", "completed"),
            (6, 5, "2025-01-01", "sms", "completed"),
            (7, 2, "2025-01-02", "email", "completed"),
        ]}
        columns = {"outreach_activity": "activity_id customer_id contacted_on channel status"}
    else:
        raise ValueError(f"unknown business fixture {name!r}")
    result = {}
    for table, rows in tables.items():
        result[table] = [dict(zip(columns[table].split(), row, strict=True)) for row in rows]
        rng.shuffle(result[table])
    if name == "saas_activation_payment":
        groups = {row["entity_id"]: row["group_key"] for row in result["account_funnel"]}
        assert all(groups[row["entity_id"]] == row["group_key"] for row in result["account_funnel"])
        order_keys = [(row["entity_id"], row["occurred_at"], row["sequence"]) for row in result["account_funnel"]]
        assert len(order_keys) == len(set(order_keys))
    return result
