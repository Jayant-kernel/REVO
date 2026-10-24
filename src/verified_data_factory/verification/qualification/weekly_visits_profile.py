"""Monday calendar-week counting for synthetic clinic visits@1."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from random import Random
from typing import Any

CONTRACT = "sql.temporal.clinic_weekly_visits"
Tables = dict[str, list[dict[str, Any]]]
BEHAVIORS = ("qualifying", "noncompleted", "null_start", "prior_year", "next_year",
             "jan_first", "last_instant", "monday", "sunday", "prior_year_monday",
             "multiple_clinics", "multiple_weeks", "duplicate_visit", "same_day")


def visit(identifier: int, at: str | None = "2025-01-01 00:00:00",
          clinic: str = "A", status: str = "completed") -> dict[str, Any]:
    return {"visit_id": identifier, "started_at": at, "clinic": clinic, "status": status}


def rich_fixture() -> Tables:
    first = visit(1)
    return {"visits": [first, dict(first), visit(2, "2025-01-05 23:59:59"),
        visit(3, "2025-01-06 00:00:00"), visit(4, "2025-01-06 12:00:00"),
        visit(5, "2025-12-31 23:59:59.999999"), visit(6, "2024-12-31 23:59:59"),
        visit(7, "2026-01-01 00:00:00"), visit(8, None), visit(9, status="cancelled"),
        visit(10, clinic="B"), visit(11, clinic="Empty", status="scheduled")]}


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("WITH scoped AS (SELECT clinic, CAST(started_at AS DATE) AS day FROM visits "
         "WHERE status='completed' AND started_at>=TIMESTAMP '2025-01-01' "
         "AND started_at<TIMESTAMP '2026-01-01'), weeks AS (SELECT clinic, "
         "CAST(day - (CAST(EXTRACT(ISODOW FROM day) AS INTEGER)-1) AS DATE) AS week_start FROM scoped) "
         "SELECT clinic, week_start, COUNT(*) AS visit_count FROM weeks "
         "GROUP BY clinic,week_start ORDER BY clinic,week_start"),
        ("SELECT DISTINCT clinic, CAST(time_bucket(INTERVAL '7 days', started_at, "
         "TIMESTAMP '2000-01-03') AS DATE) AS week_start, COUNT(*) OVER (PARTITION BY clinic, "
         "time_bucket(INTERVAL '7 days', started_at, TIMESTAMP '2000-01-03')) AS visit_count "
         "FROM visits WHERE status='completed' AND EXTRACT(YEAR FROM started_at)=2025 "
         "ORDER BY clinic,week_start")]


def failures(reference: str) -> dict[str, str]:
    bucket = "CAST(date_trunc('week',started_at) AS DATE)"
    return {
        "all_statuses": reference.replace("status='completed'", "TRUE"),
        "wrong_status": reference.replace("status='completed'", "status='cancelled'"),
        "null_start_included": reference.replace("EXTRACT(YEAR FROM started_at)=2025", "(EXTRACT(YEAR FROM started_at)=2025 OR started_at IS NULL)"),
        "all_years": reference.replace("EXTRACT(YEAR FROM started_at)=2025", "TRUE"),
        "prior_year": reference.replace("EXTRACT(YEAR FROM started_at)=2025", "EXTRACT(YEAR FROM started_at)=2024"),
        "next_year_included": reference.replace("EXTRACT(YEAR FROM started_at)=2025", "started_at>=TIMESTAMP '2025-01-01' AND started_at<=TIMESTAMP '2026-01-01'"),
        "jan_first_excluded": reference.replace("EXTRACT(YEAR FROM started_at)=2025", "started_at>TIMESTAMP '2025-01-01' AND started_at<TIMESTAMP '2026-01-01'"),
        "last_day_excluded": reference.replace("EXTRACT(YEAR FROM started_at)=2025", "started_at>=TIMESTAMP '2025-01-01' AND started_at<TIMESTAMP '2025-12-31'"),
        "last_fraction_excluded": reference.replace("EXTRACT(YEAR FROM started_at)=2025", "started_at>=TIMESTAMP '2025-01-01' AND started_at<=TIMESTAMP '2025-12-31 23:59:59'"),
        "day_bucket": reference.replace("date_trunc('week'", "date_trunc('day'"),
        "month_bucket": reference.replace("date_trunc('week'", "date_trunc('month'"),
        "sunday_week": reference.replace(bucket, "CAST(date_trunc('week',started_at + INTERVAL 1 DAY) - INTERVAL 1 DAY AS DATE)"),
        "clipped_monday": reference.replace(bucket, f"GREATEST({bucket},DATE '2025-01-01')"),
        "shifted_week": reference.replace(bucket, "CAST(date_trunc('week',started_at) + INTERVAL 7 DAY AS DATE)"),
        "timestamp_not_date": reference.replace(bucket, "date_trunc('week',started_at)"),
        "text_not_date": reference.replace(bucket, "CAST(date_trunc('week',started_at) AS VARCHAR)"),
        "distinct_ids": reference.replace("COUNT(*)", "COUNT(DISTINCT visit_id)"),
        "distinct_days": reference.replace("COUNT(*)", "COUNT(DISTINCT CAST(started_at AS DATE))"),
        "one_per_group": reference.replace("COUNT(*)", "CAST(1 AS BIGINT)"),
        "clinic_collapsed": reference.replace("SELECT clinic,", "SELECT 'all' AS clinic,").replace("GROUP BY clinic,week_start", "GROUP BY week_start"),
        "reverse_clinic": reference.replace("ORDER BY clinic,week_start", "ORDER BY clinic DESC,week_start"),
        "reverse_week": reference.replace("ORDER BY clinic,week_start", "ORDER BY clinic,week_start DESC"),
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "distinct_ids", "year": "all_years", "window_start": "jan_first_excluded",
            "window_end": "next_year_included", "boundary_policy": "last_fraction_excluded",
            "month_definition": "sunday_week", "output_columns": "timestamp_not_date",
            "order_by": "reverse_week", "completed": "all_statuses", "null_start": "null_start_included",
            "prior_year_monday": "clipped_monday", "omit_empty": "all_statuses"}
    return {key: {"witness": rich_fixture(), "wrong_sql": wrong[label], "outcome": "UNEXECUTED_RULE_SPEC"}
            for key, label in keys.items()}


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(wrong, rich_fixture()) for wrong in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"visits": [visit(1)]}
    wrong = failures(reference)
    return [("WEEKLY_VISIT_DUPLICATE", wrong["distinct_ids"], baseline),
            ("WEEKLY_VISIT_CANCELLED", wrong["all_statuses"], baseline)]


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"weekly-visits:1:{seed}:{index}")
    tables = rich_fixture()
    start = datetime.fromisoformat("2024-12-25 00:00:00")
    tables["visits"].extend(visit(identifier,
        None if rng.randrange(8) == 0 else (start + timedelta(days=rng.randrange(400), seconds=rng.randrange(86400))).isoformat(sep=" "),
        rng.choice(["A", "B", "C", "D"]), rng.choice(["completed", "cancelled", "scheduled"]))
        for identifier in range(200, rng.randint(201, 261)))
    rng.shuffle(tables["visits"])
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    found: set[str] = set()
    eligible = []
    for row in tables["visits"]:
        if row["status"] != "completed":
            found.add("noncompleted")
        if row["started_at"] is None:
            found.add("null_start")
            continue
        at = datetime.fromisoformat(str(row["started_at"]))
        if at.year < 2025:
            found.add("prior_year")
        elif at.year > 2025:
            found.add("next_year")
        if at == datetime.fromisoformat("2025-01-01 00:00:00"):
            found.add("jan_first")
        if at == datetime.fromisoformat("2025-12-31 23:59:59.999999"):
            found.add("last_instant")
        if at.year != 2025 or row["status"] != "completed":
            continue
        eligible.append((row, at))
        found.add("qualifying")
        if at.weekday() == 0:
            found.add("monday")
        if at.weekday() == 6:
            found.add("sunday")
        if (at - timedelta(days=at.weekday())).year < 2025:
            found.add("prior_year_monday")
    if len({row["clinic"] for row, _ in eligible}) > 1:
        found.add("multiple_clinics")
    if len({(at.date()-timedelta(days=at.weekday())) for _, at in eligible}) > 1:
        found.add("multiple_weeks")
    if any(count > 1 for count in Counter((row["clinic"], at.date()) for row, at in eligible).values()):
        found.add("same_day")
    if any(count > 1 for count in Counter(tuple(sorted(row.items())) for row in tables["visits"]).values()):
        found.add("duplicate_visit")
    return "weekly-visits-observed-v1", BEHAVIORS, found
