"""First-ever paid-date cohort and strictly later 30-day retention@1."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from random import Random
from typing import Any

CONTRACT = "sql.retention.saas_repeat_payment"
Tables = dict[str, list[dict[str, Any]]]
BEHAVIORS = ("retained", "day_30", "day_31", "same_day", "prior_cohort", "next_cohort",
             "year_crossing_return", "unpaid", "null_date", "no_return", "duplicate_invoice", "multiple_accounts")


def bill(identifier: int, account: int, day: str | None = "2025-01-01", status: str = "paid") -> dict[str, Any]:
    return {"invoice_id": identifier, "account_id": account, "paid_on": day, "status": status}


def rich_fixture() -> Tables:
    rows = [bill(1, 1), bill(2, 1, "2025-01-31"), bill(3, 1, "2025-01-15"),
        bill(4, 2), bill(5, 2, "2025-02-01"), bill(6, 3), bill(7, 3),
        bill(8, 4, "2024-12-31"), bill(9, 4, "2025-01-01"), bill(10, 4, "2025-01-02"),
        bill(11, 5, "2025-12-31"), bill(12, 5, "2026-01-30"),
        bill(13, 6, "2026-01-01"), bill(14, 6, "2026-01-02"),
        bill(15, 7), bill(16, 7, "2025-01-02", "open"), bill(17, 7, None),
        bill(18, 8, "2024-12-31", "open"), bill(19, 8), bill(20, 8, "2025-01-02"),
        bill(21, 9), bill(22, 10, None), bill(23, 11, "2025-01-01", "void"),
        bill(24, 12), bill(25, 12, "2025-01-31")]
    rows.append(dict(rows[1]))
    return {"billing": rows}


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("WITH paid AS (SELECT account_id,paid_on FROM billing WHERE status='paid' AND paid_on IS NOT NULL), "
         "firsts AS (SELECT account_id,MIN(paid_on) AS first_on FROM paid GROUP BY account_id) "
         "SELECT f.account_id FROM firsts f WHERE f.first_on BETWEEN DATE '2025-01-01' AND DATE '2025-12-31' "
         "AND EXISTS (SELECT 1 FROM paid p WHERE p.account_id=f.account_id AND p.paid_on>f.first_on "
         "AND date_diff('day',f.first_on,p.paid_on)<=30) ORDER BY f.account_id"),
        ("WITH history AS (SELECT account_id,paid_on,MIN(paid_on) OVER (PARTITION BY account_id) AS first_on "
         "FROM billing WHERE status='paid' AND paid_on IS NOT NULL) "
         "SELECT account_id FROM history GROUP BY account_id,first_on "
         "HAVING EXTRACT(YEAR FROM first_on)=2025 AND "
         "COUNT(*) FILTER (WHERE paid_on>first_on AND paid_on<=first_on+INTERVAL 30 DAY)>0 ORDER BY account_id")]


def failures(reference: str) -> dict[str, str]:
    return {
        "year_scoped_first": reference.replace("WHERE status='paid' AND paid_on IS NOT NULL", "WHERE status='paid' AND paid_on IS NOT NULL AND EXTRACT(YEAR FROM paid_on)=2025"),
        "latest_anchor": reference.replace("MIN(paid_on)", "MAX(paid_on)"),
        "unpaid_anchor": reference.replace("WHERE status='paid'", "WHERE TRUE"),
        "unpaid_return": reference.replace("b.status='paid'", "TRUE"),
        "wrong_return_status": reference.replace("b.status='paid'", "b.status='open'"),
        "same_day_return": reference.replace("b.paid_on > f.first_on", "b.paid_on >= f.first_on"),
        "day_30_excluded": reference.replace("b.paid_on <=", "b.paid_on <"),
        "day_31_included": reference.replace("INTERVAL 30 DAY", "INTERVAL 31 DAY"),
        "window_widened": reference.replace("INTERVAL 30 DAY", "INTERVAL 300 DAY"),
        "window_shortened": reference.replace("INTERVAL 30 DAY", "INTERVAL 1 DAY"),
        "exact_day_30_only": reference.replace("b.paid_on <=", "b.paid_on ="),
        "no_upper_window": reference.replace("b.paid_on <= f.first_on + INTERVAL 30 DAY", "TRUE"),
        "no_later_date": reference.replace("b.paid_on > f.first_on", "TRUE"),
        "all_cohorts": reference.replace("EXTRACT(YEAR FROM f.first_on)=2025", "TRUE"),
        "prior_cohort": reference.replace("EXTRACT(YEAR FROM f.first_on)=2025", "EXTRACT(YEAR FROM f.first_on)=2024"),
        "next_cohort": reference.replace("EXTRACT(YEAR FROM f.first_on)=2025", "EXTRACT(YEAR FROM f.first_on)=2026"),
        "return_year_restricted": reference.replace("b.status='paid'", "b.status='paid' AND EXTRACT(YEAR FROM b.paid_on)=2025"),
        "uncorrelated_return": reference.replace("b.account_id=f.account_id", "TRUE"),
        "invoice_as_account": reference.replace("b.account_id=f.account_id", "b.invoice_id=f.account_id"),
        "duplicate_accounts": reference.replace("SELECT DISTINCT", "SELECT"),
        "text_account": reference.replace("SELECT DISTINCT f.account_id", "SELECT DISTINCT CAST(f.account_id AS VARCHAR) AS account_id"),
        "reverse_order": reference.replace("ORDER BY f.account_id ASC", "ORDER BY f.account_id DESC"),
        "extra_anchor_column": reference.replace("SELECT DISTINCT f.account_id", "SELECT DISTINCT f.account_id,f.first_on"),
        "null_return_invented": reference.replace("b.paid_on >", "COALESCE(b.paid_on,f.first_on+INTERVAL 1 DAY) >").replace(
            "b.paid_on <=", "COALESCE(b.paid_on,f.first_on+INTERVAL 1 DAY) <="),
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "uncorrelated_return", "year": "all_cohorts",
            "retention_window_days": "day_31_included", "qualifying_event": "unpaid_return",
            "cohort_definition": "year_scoped_first", "boundary_policy": "day_30_excluded",
            "repeated_event_policy": "same_day_return", "output_columns": "text_account",
            "order_by": "reverse_order", "once": "duplicate_accounts", "null_date": "null_return_invented"}
    return {key: {"witness": rich_fixture(), "wrong_sql": wrong[label], "outcome": "UNEXECUTED_RULE_SPEC"}
            for key, label in keys.items()}


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(wrong, rich_fixture()) for wrong in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"billing": [bill(1, 1), bill(2, 1, "2025-01-02")]}
    wrong = failures(reference)
    return [("REPEAT_PAYMENT_DUPLICATE", wrong["duplicate_accounts"], baseline),
            ("REPEAT_PAYMENT_PRIOR_COHORT", wrong["year_scoped_first"], baseline)]


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"repeat-payment:1:{seed}:{index}")
    tables = rich_fixture()
    # Extra accounts keep the mandatory scaffold's histories intact.
    for account in range(100, rng.randint(101, 121)):
        first = date(2024, 12, 1) + timedelta(days=rng.randrange(430))
        for _ in range(rng.randrange(1, 8)):
            tables["billing"].append(bill(len(tables["billing"]) + 200, account,
                None if rng.randrange(8) == 0 else (first+timedelta(days=rng.randrange(65))).isoformat(),
                rng.choice(["paid", "open", "void"])))
    rng.shuffle(tables["billing"])
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    found: set[str] = set()
    groups: dict[int, list[date]] = {}
    for row in tables["billing"]:
        if row["status"] != "paid":
            found.add("unpaid")
        if row["paid_on"] is None:
            found.add("null_date")
        elif row["status"] == "paid":
            groups.setdefault(row["account_id"], []).append(date.fromisoformat(str(row["paid_on"])))
    for days in groups.values():
        first = min(days)
        deltas = [(day-first).days for day in days]
        if first.year < 2025:
            found.add("prior_cohort")
        elif first.year > 2025:
            found.add("next_cohort")
        if len(days) > len(set(days)):
            found.add("same_day")
        if first.year != 2025:
            continue
        if any(0 < delta <= 30 for delta in deltas):
            found.add("retained")
        else:
            found.add("no_return")
        if 30 in deltas:
            found.add("day_30")
        if 31 in deltas:
            found.add("day_31")
        if any(day.year > 2025 and 0 < (day-first).days <= 30 for day in days):
            found.add("year_crossing_return")
    if len(groups) > 1:
        found.add("multiple_accounts")
    if any(count > 1 for count in Counter(tuple(sorted(row.items())) for row in tables["billing"]).values()):
        found.add("duplicate_invoice")
    return "repeat-payment-observed-v1", BEHAVIORS, found
