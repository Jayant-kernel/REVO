"""Filtered playback histories, composite partitions and deterministic public order@1."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from random import Random
from typing import Any

CONTRACT = "sql.windows.media_previous_play"
Tables = dict[str, list[dict[str, Any]]]
BEHAVIORS = ("completed", "partial", "prior_year", "next_year", "jan_first", "last_instant",
             "timestamp_tie", "out_of_order", "single_history", "multiple_viewers", "multiple_titles",
             "duplicate_play", "repeated_play_id")


def play(identifier: int, viewer: int = 1, title: int = 1,
         at: str = "2025-01-01 00:00:00", status: str = "completed") -> dict[str, Any]:
    return {"play_id": identifier, "viewer_id": viewer, "title_id": title, "played_at": at, "status": status}


def rich_fixture() -> Tables:
    repeated = play(7, at="2025-01-02 00:00:00")
    return {"plays": [play(1), play(3), play(2, at="2025-01-01 12:00:00", status="partial"),
        play(9, at="2024-12-31 23:59:59"), play(8, at="2026-01-01 00:00:00"),
        repeated, dict(repeated), play(11, at="2025-12-31 23:59:59.999999"),
        play(5, viewer=2), play(7, viewer=3), play(6, title=2),
        play(10, title=2, at="2025-01-02 00:00:00"), play(12, at="2025-01-01 06:00:00")]}


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("WITH numbered AS (SELECT play_id,viewer_id,title_id,ROW_NUMBER() OVER "
         "(PARTITION BY viewer_id,title_id ORDER BY played_at,play_id) AS position "
         "FROM plays WHERE status='completed' AND played_at>=TIMESTAMP '2025-01-01' "
         "AND played_at<TIMESTAMP '2026-01-01') "
         "SELECT n.play_id,p.play_id AS previous_play_id FROM numbered n LEFT JOIN numbered p "
         "ON n.viewer_id=p.viewer_id AND n.title_id=p.title_id AND p.position=n.position-1 ORDER BY n.play_id"),
        ("SELECT play_id,LAST_VALUE(play_id) OVER (PARTITION BY viewer_id,title_id ORDER BY played_at,play_id "
         "ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING) AS previous_play_id "
         "FROM plays WHERE status='completed' AND EXTRACT(YEAR FROM played_at)=2025 ORDER BY play_id")]


def failures(reference: str) -> dict[str, str]:
    return {
        "all_statuses": reference.replace("status='completed'", "TRUE"),
        "partial_only": reference.replace("status='completed'", "status='partial'"),
        "all_years": reference.replace("EXTRACT(YEAR FROM played_at)=2025", "TRUE"),
        "prior_year": reference.replace("EXTRACT(YEAR FROM played_at)=2025", "EXTRACT(YEAR FROM played_at)=2024"),
        "next_jan_included": reference.replace("EXTRACT(YEAR FROM played_at)=2025", "played_at>=TIMESTAMP '2025-01-01' AND played_at<=TIMESTAMP '2026-01-01'"),
        "jan_first_excluded": reference.replace("EXTRACT(YEAR FROM played_at)=2025", "played_at>TIMESTAMP '2025-01-01' AND played_at<TIMESTAMP '2026-01-01'"),
        "last_fraction_excluded": reference.replace("EXTRACT(YEAR FROM played_at)=2025", "played_at>=TIMESTAMP '2025-01-01' AND played_at<=TIMESTAMP '2025-12-31 23:59:59'"),
        "viewer_only": reference.replace("PARTITION BY viewer_id,title_id", "PARTITION BY viewer_id"),
        "title_only": reference.replace("PARTITION BY viewer_id,title_id", "PARTITION BY title_id"),
        "global_history": reference.replace("PARTITION BY viewer_id,title_id", ""),
        "id_history": reference.replace("ORDER BY played_at,play_id", "ORDER BY play_id"),
        "reverse_time": reference.replace("ORDER BY played_at,play_id", "ORDER BY played_at DESC,play_id DESC"),
        "reverse_tie": reference.replace("ORDER BY played_at,play_id", "ORDER BY played_at,play_id DESC"),
        "next_play": reference.replace("LAG(play_id)", "LEAD(play_id)"),
        "two_plays_back": reference.replace("LAG(play_id)", "LAG(play_id,2)"),
        "current_play": reference.replace("LAG(play_id)", "LAG(play_id,0)"),
        "default_zero": reference.replace("LAG(play_id)", "LAG(play_id,1,0)"),
        "first_not_previous": reference.replace("LAG(play_id)", "FIRST_VALUE(play_id)"),
        "viewer_as_previous": reference.replace("LAG(play_id)", "LAG(viewer_id)"),
        "title_as_previous": reference.replace("LAG(play_id)", "LAG(title_id)"),
        "lost_input_bag": reference.replace("FROM plays WHERE", "FROM (SELECT DISTINCT * FROM plays) plays WHERE"),
        "id_as_text": reference.replace("SELECT play_id,", "SELECT CAST(play_id AS VARCHAR) AS play_id,"),
        "reverse_output": reference.replace("ORDER BY play_id", "ORDER BY play_id DESC"),
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "next_play", "year": "all_years", "status_filter": "all_statuses",
            "partition_by": "viewer_only", "title": "title_only", "rank_order": "extra_rank",
            "running_order": "id_history", "tie_policy": "reverse_tie", "null_ordering": "default_zero",
            "output_columns": "id_as_text", "order_by": "reverse_output", "bag": "lost_input_bag"}
    wrong["extra_rank"] = reference.replace("SELECT play_id,", "SELECT play_id,CAST(1 AS BIGINT) AS rank,")
    return {key: {"witness": rich_fixture(), "wrong_sql": wrong[label], "outcome": "UNEXECUTED_RULE_SPEC"}
            for key, label in keys.items()}


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(wrong, rich_fixture()) for wrong in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"plays": [play(1), play(3, at="2025-01-02 00:00:00")]}
    wrong = failures(reference)
    return [("PREVIOUS_PLAY_PARTIAL", wrong["all_statuses"], baseline),
            ("PREVIOUS_PLAY_OTHER_VIEWER", wrong["title_only"], baseline)]


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"previous-play:1:{seed}:{index}")
    tables = rich_fixture()
    start = datetime.fromisoformat("2024-12-25 00:00:00")
    tables["plays"].extend(play(identifier, rng.randrange(10, 20), rng.randrange(4),
        (start+timedelta(days=rng.randrange(400), seconds=rng.choice([0, 30, 60]))).isoformat(sep=" "),
        rng.choice(["completed", "partial", "cancelled"])) for identifier in range(200, rng.randint(201, 281)))
    rng.shuffle(tables["plays"])
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    found: set[str] = set()
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in tables["plays"]:
        at = datetime.fromisoformat(str(row["played_at"]))
        if row["status"] == "partial":
            found.add("partial")
        if at.year < 2025:
            found.add("prior_year")
        elif at.year > 2025:
            found.add("next_year")
        if at == datetime.fromisoformat("2025-01-01 00:00:00"):
            found.add("jan_first")
        if at == datetime.fromisoformat("2025-12-31 23:59:59.999999"):
            found.add("last_instant")
        if row["status"] == "completed" and at.year == 2025:
            found.add("completed")
            groups.setdefault((row["viewer_id"], row["title_id"]), []).append(row)
    if len({viewer for viewer, _ in groups}) > 1:
        found.add("multiple_viewers")
    if len({title for _, title in groups}) > 1:
        found.add("multiple_titles")
    for rows in groups.values():
        times = [str(row["played_at"]) for row in rows]
        if len(rows) == 1:
            found.add("single_history")
        if len(set(times)) < len(times):
            found.add("timestamp_tie")
        if times != sorted(times):
            found.add("out_of_order")
    if any(count > 1 for count in Counter(row["play_id"] for row in tables["plays"]).values()):
        found.add("repeated_play_id")
    if any(count > 1 for count in Counter(tuple(sorted(row.items())) for row in tables["plays"]).values()):
        found.add("duplicate_play")
    return "previous-play-observed-v1", BEHAVIORS, found
