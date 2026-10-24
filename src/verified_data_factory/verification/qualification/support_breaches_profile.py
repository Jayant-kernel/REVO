"""Resolved-ticket SLA counts, strict deadline and opened-year population@1."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from random import Random
from typing import Any

CONTRACT = "sql.aggregation.support_sla_breaches"
Tables = dict[str, list[dict[str, Any]]]
BEHAVIORS = ("breach", "equal_deadline", "early_resolution", "unresolved", "prior_year", "next_year",
             "jan_first", "last_instant", "cross_year_resolution", "duplicate_ticket",
             "multiple_teams", "multiple_priorities", "empty_breach_group")


def ticket(identifier: int, team: str = "A", priority: str = "high", *,
           opened: str = "2025-01-01 00:00:00", due: str = "2025-01-02 00:00:00",
           resolved: str | None = "2025-01-02 00:00:01") -> dict[str, Any]:
    return {"ticket_id": identifier, "team": team, "priority": priority, "opened_at": opened,
            "due_at": due, "resolved_at": resolved}


def rich_fixture() -> Tables:
    first = ticket(1)
    return {"support_tickets": [first, dict(first), ticket(2, resolved="2025-01-02 00:00:00"),
        ticket(3, priority="normal"), ticket(4, "B", resolved=None),
        ticket(5, "B", "normal", opened="2025-12-31 23:59:59.999999", due="2026-01-01 00:00:00", resolved="2026-01-01 00:00:01"),
        ticket(6, "old", opened="2024-12-31 23:59:59"),
        ticket(7, "future", opened="2026-01-01 00:00:00", due="2026-01-02 00:00:00", resolved="2026-01-02 00:00:01"),
        ticket(8, resolved="2025-01-01 23:59:59"),
        ticket(9, "NoBreach", "low", resolved="2025-01-02 00:00:00")]}


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("WITH late AS (SELECT team,priority FROM support_tickets WHERE EXTRACT(YEAR FROM opened_at)=2025 "
         "AND resolved_at>due_at) SELECT team,priority,COUNT(*) AS breach_count FROM late "
         "GROUP BY team,priority ORDER BY team,priority"),
        ("SELECT DISTINCT team,priority,COUNT(*) OVER (PARTITION BY team,priority) AS breach_count "
         "FROM support_tickets WHERE opened_at>=TIMESTAMP '2025-01-01' AND opened_at<TIMESTAMP '2026-01-01' "
         "AND resolved_at>due_at ORDER BY team,priority")]


def failures(reference: str) -> dict[str, str]:
    return {
        "all_resolved": reference.replace("resolved_at > due_at", "TRUE"),
        "on_time_only": reference.replace("resolved_at > due_at", "resolved_at <= due_at"),
        "equal_is_breach": reference.replace("resolved_at > due_at", "resolved_at >= due_at"),
        "equal_only": reference.replace("resolved_at > due_at", "resolved_at = due_at"),
        "opened_not_deadline": reference.replace("resolved_at > due_at", "resolved_at > opened_at"),
        "unresolved_included": reference.replace("resolved_at IS NOT NULL", "TRUE").replace("resolved_at > due_at", "(resolved_at > due_at OR resolved_at IS NULL)"),
        "lower_unbounded": reference.replace("opened_at >= TIMESTAMP '2025-01-01 00:00:00'", "TRUE"),
        "upper_unbounded": reference.replace("opened_at < TIMESTAMP '2026-01-01 00:00:00'", "TRUE"),
        "jan_first_excluded": reference.replace(">= TIMESTAMP '2025-01-01 00:00:00'", "> TIMESTAMP '2025-01-01 00:00:00'"),
        "next_jan_included": reference.replace("< TIMESTAMP '2026-01-01 00:00:00'", "<= TIMESTAMP '2026-01-01 00:00:00'"),
        "last_fraction_excluded": reference.replace("< TIMESTAMP '2026-01-01 00:00:00'", "<= TIMESTAMP '2025-12-31 23:59:59'"),
        "resolution_year": reference.replace("opened_at >=", "resolved_at >=").replace("opened_at <", "resolved_at <"),
        "distinct_id": reference.replace("COUNT(*)", "COUNT(DISTINCT ticket_id)"),
        "distinct_team": reference.replace("COUNT(*)", "COUNT(DISTINCT team)"),
        "id_sum": reference.replace("COUNT(*)", "SUM(ticket_id)"),
        "count_plus_one": reference.replace("COUNT(*)", "COUNT(*)+1"),
        "count_minus_one": reference.replace("COUNT(*)", "COUNT(*)-1"),
        "count_doubled": reference.replace("COUNT(*)", "COUNT(*)*2"),
        "count_zero": reference.replace("COUNT(*)", "COUNT(*)*0"),
        "priority_collapsed": reference.replace("SELECT team, priority,", "SELECT team, MIN(priority) AS priority,").replace("GROUP BY team, priority", "GROUP BY team"),
        "wrong_count_name": reference.replace("AS breach_count", "AS wrong_count"),
        "text_count": reference.replace("COUNT(*)", "CAST(COUNT(*) AS VARCHAR)"),
        "reverse_priority": reference.replace("priority ASC", "priority DESC"),
        "reverse_team": reference.replace("team ASC", "team DESC"),
        "truncated_groups": reference+" LIMIT 1",
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "all_resolved", "year": "lower_unbounded", "group_by": "priority_collapsed",
            "null_handling": "unresolved_included", "count_semantics": "distinct_id",
            "empty_group_behavior": "equal_is_breach", "boundary_policy": "equal_is_breach",
            "output_columns": "wrong_count_name", "order_by": "reverse_priority"}
    return {key: {"witness": rich_fixture(), "wrong_sql": wrong[label], "outcome": "UNEXECUTED_RULE_SPEC"}
            for key, label in keys.items()}


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(wrong, rich_fixture()) for wrong in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"support_tickets": [ticket(1)]}
    wrong = failures(reference)
    return [("SUPPORT_BREACH_DUPLICATE", wrong["distinct_id"], baseline),
            ("SUPPORT_ON_TIME_ROW", wrong["equal_is_breach"], baseline)]


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"support-breaches:1:{seed}:{index}")
    tables = rich_fixture()
    for identifier in range(200, rng.randint(201, 281)):
        opened = datetime.fromisoformat(f"{rng.choice([2024,2025,2026])}-01-01 00:00:00")+timedelta(days=rng.randrange(365))
        due = opened+timedelta(days=rng.randrange(1, 8))
        resolved = None if rng.randrange(5) == 0 else due+timedelta(seconds=rng.choice([-1,0,1,86400]))
        tables["support_tickets"].append(ticket(identifier, rng.choice(["A","B","C"]), rng.choice(["high","normal","low"]),
            opened=opened.isoformat(sep=" "), due=due.isoformat(sep=" "),
            resolved=resolved.isoformat(sep=" ") if resolved is not None else None))
    rng.shuffle(tables["support_tickets"])
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    found: set[str] = set()
    groups: set[tuple[str, str]] = set()
    breached: set[tuple[str, str]] = set()
    for row in tables["support_tickets"]:
        at = datetime.fromisoformat(str(row["opened_at"]))
        groups.add((row["team"],row["priority"]))
        if at.year < 2025:
            found.add("prior_year")
        elif at.year > 2025:
            found.add("next_year")
        if at == datetime.fromisoformat("2025-01-01 00:00:00"):
            found.add("jan_first")
        if at == datetime.fromisoformat("2025-12-31 23:59:59.999999"):
            found.add("last_instant")
        if row["resolved_at"] is None:
            found.add("unresolved")
            continue
        resolved = datetime.fromisoformat(str(row["resolved_at"]))
        due = datetime.fromisoformat(str(row["due_at"]))
        if at.year == 2025:
            found.add("breach" if resolved>due else "equal_deadline" if resolved==due else "early_resolution")
            if resolved>due:
                breached.add((row["team"],row["priority"]))
                if resolved.year != at.year:
                    found.add("cross_year_resolution")
    if groups-breached:
        found.add("empty_breach_group")
    if len({team for team,_ in groups})>1:
        found.add("multiple_teams")
    if len({priority for _,priority in groups})>1:
        found.add("multiple_priorities")
    if any(count>1 for count in Counter(tuple(sorted(row.items())) for row in tables["support_tickets"]).values()):
        found.add("duplicate_ticket")
    return "support-breaches-observed-v1", BEHAVIORS, found
