"""SQL/fixture discriminators for the exact paid-invoice inner-join contract@1."""
from __future__ import annotations

from typing import Any

CONTRACT = "sql.joins.saas_paid_invoices"
Tables = dict[str, list[dict[str, Any]]]


def account(identifier: int, status: str = "active", name: str | None = None) -> dict[str, Any]:
    return {"account_id": identifier, "account_name": name or f"account-{identifier}",
            "account_status": status}


def invoice(identifier: int, owner: int = 1, *, day: str = "2025-06-15",
            status: str = "paid", amount: int = 1701) -> dict[str, Any]:
    return {"invoice_id": identifier, "account_id": owner, "issued_on": day,
            "invoice_status": status, "amount_cents": amount}


def rich_fixture() -> Tables:
    repeated = invoice(19, amount=-301)
    return {"accounts": [account(1), account(1), account(2, "suspended"), account(3), account(4)],
            "invoices": [invoice(11, day="2025-01-01", amount=0),
                invoice(12, day="2025-12-31", amount=999), repeated, dict(repeated),
                invoice(21, 2), invoice(31, 3, status="open"), invoice(32, 3, status="void"),
                invoice(41, day="2024-12-31"), invoice(42, day="2026-01-01"), invoice(51, 99)]}


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("WITH eligible_invoices AS (SELECT * FROM invoices WHERE invoice_status='paid' "
         "AND EXTRACT(YEAR FROM issued_on)=2025), active_accounts AS "
         "(SELECT * FROM accounts WHERE account_status='active') "
         "SELECT i.invoice_id, a.account_name, i.amount_cents FROM eligible_invoices i "
         "INNER JOIN active_accounts a USING (account_id) ORDER BY i.invoice_id"),
        ("SELECT i.invoice_id, a.account_name, i.amount_cents FROM invoices i "
         "INNER JOIN LATERAL (SELECT account_name FROM accounts a WHERE a.account_id=i.account_id "
         "AND a.account_status='active') a ON TRUE WHERE i.invoice_status='paid' "
         "AND i.issued_on BETWEEN DATE '2025-01-01' AND DATE '2025-12-31' ORDER BY i.invoice_id")]


def failures(reference: str) -> dict[str, str]:
    """Each label is a different business, bag, boundary or output failure mode."""
    return {
        "uncorrelated_join": reference.replace("i.account_id = a.account_id", "TRUE"),
        "wrong_join_key": reference.replace("i.account_id = a.account_id", "i.invoice_id = a.account_id"),
        "unpaid_inclusion": reference.replace("i.invoice_status = 'paid'", "TRUE"),
        "wrong_invoice_status": reference.replace("i.invoice_status = 'paid'", "i.invoice_status = 'open'"),
        "inactive_inclusion": reference.replace("a.account_status = 'active'", "TRUE"),
        "wrong_current_status": reference.replace("a.account_status = 'active'", "a.account_status = 'suspended'"),
        "lower_year_unbounded": reference.replace("i.issued_on >= DATE '2025-01-01'", "TRUE"),
        "upper_year_unbounded": reference.replace("i.issued_on < DATE '2026-01-01'", "TRUE"),
        "jan_first_excluded": reference.replace(">= DATE '2025-01-01'", "> DATE '2025-01-01'"),
        "next_jan_included": reference.replace("< DATE '2026-01-01'", "<= DATE '2026-01-01'"),
        "last_day_excluded": reference.replace("< DATE '2026-01-01'", "< DATE '2025-12-31'"),
        "distinct_loses_bag": reference.replace("SELECT i.invoice_id", "SELECT DISTINCT i.invoice_id"),
        "amount_in_major_units": reference.replace("i.amount_cents\n", "i.amount_cents / 100.0 AS amount_cents\n"),
        "negative_amount_clipped": reference.replace("i.amount_cents\n", "ABS(i.amount_cents) AS amount_cents\n"),
        "account_id_projection": reference.replace("SELECT i.invoice_id", "SELECT i.account_id AS invoice_id"),
        "status_as_name": reference.replace("SELECT i.invoice_id, a.account_name,", "SELECT i.invoice_id, a.account_status AS account_name,"),
        "numeric_id_as_text": reference.replace("SELECT i.invoice_id", "SELECT CAST(i.invoice_id AS VARCHAR) AS invoice_id"),
        "reverse_order": reference.replace("ORDER BY i.invoice_id ASC", "ORDER BY i.invoice_id DESC"),
        "amount_order": reference.replace("ORDER BY i.invoice_id ASC", "ORDER BY i.amount_cents DESC"),
        "zero_amount_omitted": reference.replace("WHERE i.invoice_status", "WHERE i.amount_cents <> 0 AND i.invoice_status"),
        "orphan_invoice_included": reference.replace("INNER JOIN", "LEFT JOIN").replace(
            "a.account_status = 'active'", "(a.account_status = 'active' OR a.account_id IS NULL)"),
        "account_without_invoice_included": reference.replace("INNER JOIN", "RIGHT JOIN").replace(
            "i.invoice_status = 'paid'", "(i.invoice_status = 'paid' OR i.invoice_id IS NULL)").replace(
            "i.issued_on >= DATE '2025-01-01'", "(i.issued_on >= DATE '2025-01-01' OR i.invoice_id IS NULL)").replace(
            "i.issued_on < DATE '2026-01-01'", "(i.issued_on < DATE '2026-01-01' OR i.invoice_id IS NULL)"),
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "uncorrelated_join", "year": "lower_year_unbounded",
            "status_filter": "unpaid_inclusion", "account_status_filter": "inactive_inclusion",
            "join_type": "orphan_invoice_included", "unmatched_behavior": "account_without_invoice_included",
            "output_columns": "numeric_id_as_text", "order_by": "reverse_order",
            "multiplicity": "distinct_loses_bag", "minor_units": "amount_in_major_units"}
    result = {key: {"witness": rich_fixture(), "wrong_sql": wrong[label],
                    "outcome": "UNEXECUTED_RULE_SPEC"} for key, label in keys.items()}
    result["null_handling"] = {"witness": {"accounts": [account(1)],
        "invoices": [{**invoice(1), "account_id": None}]}, "outcome": "UNEXECUTED_RULE_SPEC"}
    return result


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(wrong, rich_fixture()) for wrong in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"accounts": [account(1)], "invoices": [invoice(11)]}
    wrong = failures(reference)
    return [("PAID_INVOICE_DUPLICATE", wrong["distinct_loses_bag"], baseline),
            ("PAID_INACTIVE_ACCOUNT", wrong["inactive_inclusion"], baseline)]
