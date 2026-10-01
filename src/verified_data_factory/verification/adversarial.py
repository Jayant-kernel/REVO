"""Hand-designed hidden rows for specific template contracts.

These cases are independent of the seeded fixture generator. They are not a
claim that every template has an adversarial suite.
"""

from __future__ import annotations

from typing import Any

from verified_data_factory.task_engine.models import TaskInstance


def independent_adversarial_tables(
    task: TaskInstance,
) -> dict[str, list[dict[str, Any]]] | None:
    if task.template_id == "sql.joins.saas_paid_invoices" and task.template_version == 1:
        return {
            "accounts": [
                {"account_id": 1, "account_name": "Active", "account_status": "active"},
                {"account_id": 2, "account_name": "Suspended", "account_status": "suspended"},
                {"account_id": 3, "account_name": "No invoice", "account_status": "active"},
            ],
            "invoices": [
                {"invoice_id": 1, "account_id": 1, "issued_on": "2025-01-01", "amount_cents": 0, "invoice_status": "paid"},
                {"invoice_id": 2, "account_id": 2, "issued_on": "2025-02-01", "amount_cents": 90_000, "invoice_status": "paid"},
                {"invoice_id": 3, "account_id": 1, "issued_on": "2025-02-02", "amount_cents": 80_000, "invoice_status": "open"},
                {"invoice_id": 4, "account_id": 1, "issued_on": "2024-12-31", "amount_cents": 70_000, "invoice_status": "paid"},
                {"invoice_id": 5, "account_id": 1, "issued_on": "2026-01-01", "amount_cents": 60_000, "invoice_status": "paid"},
            ],
        }
    if task.template_id == "sql.aggregation.payment_net_settled" and task.template_version == 1:
        return {
            "payment_entries": [
                {"entry_id": 1, "merchant_id": 1, "posted_on": "2025-01-01", "entry_kind": "settlement", "entry_status": "posted", "amount_cents": 10_000},
                {"entry_id": 2, "merchant_id": 1, "posted_on": "2025-01-02", "entry_kind": "reversal", "entry_status": "posted", "amount_cents": -10_000},
                {"entry_id": 3, "merchant_id": 2, "posted_on": "2025-07-01", "entry_kind": "settlement", "entry_status": "failed", "amount_cents": 50_000},
                {"entry_id": 4, "merchant_id": 2, "posted_on": "2024-12-31", "entry_kind": "settlement", "entry_status": "posted", "amount_cents": 70_000},
                {"entry_id": 5, "merchant_id": 3, "posted_on": "2025-07-02", "entry_kind": "adjustment", "entry_status": "posted", "amount_cents": 30_000},
            ]
        }
    if task.template_id == "sql.aggregation.support_sla_breaches" and task.template_version == 1:
        return {
            "support_tickets": [
                {"ticket_id": 1, "team": "Accounts", "priority": "high", "opened_at": "2025-01-01 00:00:00", "due_at": "2025-01-02 00:00:00", "resolved_at": "2025-01-02 00:00:00"},
                {"ticket_id": 2, "team": "Accounts", "priority": "high", "opened_at": "2025-01-01 01:00:00", "due_at": "2025-01-02 01:00:00", "resolved_at": "2025-01-02 01:00:01"},
                {"ticket_id": 3, "team": "Accounts", "priority": "high", "opened_at": "2025-01-02 01:00:00", "due_at": "2025-01-03 01:00:00", "resolved_at": "2025-01-03 01:00:01"},
                {"ticket_id": 4, "team": "Payments", "priority": "normal", "opened_at": "2025-06-01 00:00:00", "due_at": "2025-06-02 00:00:00", "resolved_at": None},
                {"ticket_id": 5, "team": "Payments", "priority": "normal", "opened_at": "2024-12-31 23:59:59", "due_at": "2025-01-01 23:59:59", "resolved_at": "2025-01-02 00:00:00"},
                {"ticket_id": 6, "team": "Payments", "priority": "normal", "opened_at": "2025-12-31 23:59:59", "due_at": "2026-01-01 23:59:59", "resolved_at": "2026-01-02 00:00:00"},
            ]
        }
    if task.template_id == "sql.dedup.education_grade_revisions" and task.template_version == 1:
        return {
            "grade_revisions": [
                {"revision_id": 1, "student_id": 1, "course_id": 10, "recorded_at": "2025-01-01 10:00:00", "revision_status": "valid", "grade": "B"},
                {"revision_id": 2, "student_id": 1, "course_id": 10, "recorded_at": "2025-02-01 10:00:00", "revision_status": "valid", "grade": "A"},
                {"revision_id": 3, "student_id": 1, "course_id": 10, "recorded_at": "2025-03-01 10:00:00", "revision_status": "cancelled", "grade": "F"},
                {"revision_id": 4, "student_id": 1, "course_id": 10, "recorded_at": "2025-02-01 10:00:00", "revision_status": "valid", "grade": "A+"},
                {"revision_id": 5, "student_id": 2, "course_id": 20, "recorded_at": "2025-04-01 10:00:00", "revision_status": "cancelled", "grade": "C"},
                {"revision_id": 6, "student_id": 1, "course_id": 20, "recorded_at": "2025-05-01 10:00:00", "revision_status": "valid", "grade": "B+"},
                {"revision_id": 7, "student_id": 3, "course_id": 30, "recorded_at": "2025-06-01 10:00:00", "revision_status": "valid", "grade": "C"},
            ]
        }
    return None
