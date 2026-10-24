"""Content-measured random campaigns for exact paid@1 and EXISTS@2 profiles."""
from __future__ import annotations

from collections import Counter
from random import Random
from typing import Any

from . import exists_profile as exists
from . import paid_invoices_profile as paid

Tables = dict[str, list[dict[str, Any]]]
PAID_BEHAVIORS = ("qualifying", "inactive", "unpaid", "prior_year", "next_year",
                  "jan_first", "dec_last", "orphan", "orderless_account",
                  "multiple_invoices", "duplicate_account", "duplicate_invoice", "zero_amount", "negative_amount")
EXISTS_BEHAVIORS = ("qualifying", "threshold_equal", "threshold_below", "wrong_status",
                    "prior_year", "next_year", "jan_first", "dec_last", "orphan",
                    "orderless_customer", "nonqualifying_customer", "multiple_qualifying",
                    "duplicate_customer", "nullable_country")


def fixture(contract: str, version: int, seed: int, index: int) -> Tables:
    rng = Random(f"selection:{contract}:{version}:{seed}:{index}")
    if (contract, version) == (paid.CONTRACT, 1):
        tables = paid.rich_fixture()
        tables["invoices"].extend(paid.invoice(identifier, rng.choice([1, 2, 3, 99]),
            day=rng.choice(["2024-12-31", "2025-01-01", "2025-06-15", "2025-12-31", "2026-01-01"]),
            status=rng.choice(["paid", "open", "void"]), amount=rng.randint(-10000, 10000))
            for identifier in range(200, rng.randint(201, 241)))
    elif (contract, version) == (exists.CONTRACT, 2):
        tables = exists.rich_fixture()
        tables["orders"].extend(exists.order(identifier, rng.choice([1, 2, 3, 6, 7, 8, 99]),
            day=rng.choice(["2024-12-31", "2025-01-01", "2025-06-15", "2025-12-31", "2026-01-01"]),
            status=rng.choice(["completed", "pending", "cancelled"]),
            amount=rng.choice([0, 499.5, 500, 500.5, rng.uniform(-100, 1200)]))
            for identifier in range(200, rng.randint(201, 241)))
    else:
        raise ValueError("unsupported selection observation contract/version")
    for rows in tables.values():
        rng.shuffle(rows)
    return tables


def repeated(rows: list[dict[str, Any]]) -> bool:
    return any(count > 1 for count in Counter(tuple(sorted(row.items())) for row in rows).values())


def observed(contract: str, version: int, tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    found: set[str] = set()
    if (contract, version) == (paid.CONTRACT, 1):
        accounts, invoices = tables["accounts"], tables["invoices"]
        owners = {account["account_id"] for account in accounts}
        active = {account["account_id"] for account in accounts if account["account_status"] == "active"}
        for row in invoices:
            day = str(row["issued_on"])
            if row["account_id"] not in owners:
                found.add("orphan")
            if row["account_id"] in owners - active:
                found.add("inactive")
            if row["invoice_status"] != "paid":
                found.add("unpaid")
            if row["amount_cents"] == 0:
                found.add("zero_amount")
            if row["amount_cents"] < 0:
                found.add("negative_amount")
            if row["account_id"] in active and row["invoice_status"] == "paid" and day[:4] == "2025":
                found.add("qualifying")
            date_behaviors(day, found)
        if owners - {row["account_id"] for row in invoices}:
            found.add("orderless_account")
        if any(count > 1 for count in Counter(row["account_id"] for row in invoices).values()):
            found.add("multiple_invoices")
        if repeated(accounts):
            found.add("duplicate_account")
        if repeated(invoices):
            found.add("duplicate_invoice")
        return "paid-invoices-observed-v1", PAID_BEHAVIORS, found
    if (contract, version) == (exists.CONTRACT, 2):
        customers, orders = tables["customers"], tables["orders"]
        owners = {customer["customer_id"] for customer in customers}
        qualifying: Counter[int] = Counter()
        for row in orders:
            day = str(row["order_date"])
            if row["customer_id"] not in owners:
                found.add("orphan")
            if row["amount"] == 500:
                found.add("threshold_equal")
            if row["amount"] < 500:
                found.add("threshold_below")
            if row["status"] != "completed":
                found.add("wrong_status")
            if row["customer_id"] in owners and row["status"] == "completed" and day[:4] == "2025" and row["amount"] > 500:
                qualifying[row["customer_id"]] += 1
                found.add("qualifying")
            date_behaviors(day, found)
        if owners - {row["customer_id"] for row in orders}:
            found.add("orderless_customer")
        if owners - qualifying.keys():
            found.add("nonqualifying_customer")
        if any(count > 1 for count in qualifying.values()):
            found.add("multiple_qualifying")
        if repeated(customers):
            found.add("duplicate_customer")
        if any(row["country"] is None for row in customers):
            found.add("nullable_country")
        return "exists-observed-v1", EXISTS_BEHAVIORS, found
    raise ValueError("unsupported selection observation contract/version")


def date_behaviors(day: str, found: set[str]) -> None:
    if day[:4] < "2025":
        found.add("prior_year")
    elif day[:4] > "2025":
        found.add("next_year")
    if day == "2025-01-01":
        found.add("jan_first")
    elif day == "2025-12-31":
        found.add("dec_last")
