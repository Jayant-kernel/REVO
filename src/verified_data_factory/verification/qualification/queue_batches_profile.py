"""Queue batches@1; unregistered local profile with SQL-free integer allocation."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from random import Random
from typing import Any

from ..models import ExpectedResult, OrderSpec

CONTRACT = "sql.windows.queue_batches"
REFERENCE = ("SELECT submission_id, NTILE(3) OVER (PARTITION BY queue ORDER BY "
             "submitted_at ASC NULLS LAST, submission_id ASC) AS batch_number "
             "FROM submissions ORDER BY submission_id")
Tables = dict[str, list[dict[str, Any]]]
SCHEMA = {"submissions": {"submission_id": "INTEGER", "queue": "VARCHAR",
                           "submitted_at": "TIMESTAMP"}}
BEHAVIORS = ("empty_input", "size_1", "size_2", "size_3", "size_4", "size_5", "size_6",
             "size_7", "size_8", "large_queue", "skew", "timestamp_tie", "null_peers",
             "mixed_null", "out_of_order", "case_labels", "empty_label", "literal_label",
             "prior_year", "next_year", "microseconds", "min_integer", "max_integer",
             "negative_integer", "same_payload_distinct_ids", "remainder_1", "remainder_2")
CLAUSES = {
    "native_ntile": ("ntile_structure", "using NTILE(3)"),
    "not_rank": ("rank_order", "never value RANK, equal-time shared rank, or running amount totals"),
    "order": ("running_order", "submitted_at ascending NULLS LAST then submission_id ascending"),
    "ties": ("tie_policy", "including NULL peers"),
    "allocation": ("allocation", "first r batches have q+1 rows and the rest q rows"),
    "tiny": ("tiny_queues", "when N<3 use batches 1..N"),
    "types": ("output_types", "submission_id INTEGER and batch_number BIGINT"),
    "labels": ("queue_labels", "Queues are exact VARCHAR labels, no normalization"),
    "scope": ("scope", "No episodes/status/year exclusion"),
    "unique": ("input_domain_rules", "submission_id must be unique globally"),
    "payload": ("payload_bag", "equal payloads with different IDs are distinct submissions"),
    "timestamp": ("timestamp_domain", "naive timezone-free microsecond-resolution TIMESTAMP"),
    "nullable": ("nullable", "only nullable input"),
    "domain": ("no_extra_domain", "No other domain/foreign-key restriction"),
    "history": ("year", "All years and unknown-time submissions participate"),
    "empty": ("empty_input", "Empty input gives no output"),
    "units": ("units", "Batch number is a dimensionless integer"),
}
DOMAIN_KEYS = {"raw:submissions.submission_id", "raw:submissions.queue",
               "raw:submissions.submitted_at", "input_domain_rules", "timestamp_domain",
               "nullable", "exact_schema"}
STRUCTURAL_KEYS = {"ntile_structure"}
EDGE_PROOFS = {"ties": "tie_policy", "null_values": "null_ordering",
               "single_row_groups": "tiny_queues", "out_of_order_timestamps": "running_order"}


def timestamp(value: Any) -> datetime:
    if type(value) is datetime and value.tzinfo is None:
        return value
    if type(value) is not str or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?", value
    ):
        raise ValueError("TIMESTAMP must be naive ISO with at most six fractional digits")
    return datetime.fromisoformat(value)


def validate_rows(tables: Mapping[str, list[dict[str, Any]]], *,
                  allow_required_null: bool = False) -> None:
    if set(tables) != {"submissions"} or type(tables["submissions"]) is not list:
        raise ValueError("requires exactly submissions row list")
    ids = set()
    for row in tables["submissions"]:
        if type(row) is not dict or set(row) != set(SCHEMA["submissions"]):
            raise ValueError("requires exact submissions columns")
        for column, kind in SCHEMA["submissions"].items():
            value = row[column]
            if value is None:
                if column != "submitted_at" and not allow_required_null:
                    raise ValueError(f"{column} must be nonnull")
            elif kind == "INTEGER":
                if type(value) is not int or not -(2**31) <= value < 2**31:
                    raise ValueError("submission_id must be raw signed32 integer")
            elif kind == "VARCHAR":
                if type(value) is not str:
                    raise ValueError("queue must be raw text")
            else:
                timestamp(value)
        identifier = row["submission_id"]
        if identifier in ids:
            raise ValueError("submission_id must be unique globally")
        ids.add(identifier)


def _ordered(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["submitted_at"] is None,
                  timestamp(row["submitted_at"]) if row["submitted_at"] else timestamp("0001-01-01T00:00:00"),
                  row["submission_id"]))


def expected(requirements: Mapping[str, Any],
             tables: Mapping[str, list[dict[str, Any]]]) -> ExpectedResult:
    validate_rows(tables)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["submissions"]:
        groups[row["queue"]].append(row)
    output: list[list[Any]] = []
    for rows in groups.values():
        ordered = _ordered(rows)
        q, r = divmod(len(ordered), 3)
        offset = 0
        for bucket in range(1, 4):
            size = q + int(bucket <= r)
            output.extend([row["submission_id"], bucket] for row in ordered[offset:offset + size])
            offset += size
    return ExpectedResult(columns=["submission_id", "batch_number"],
                          column_types=["INTEGER", "BIGINT"], exact_column_types=True,
                          rows=sorted(output),
                          order=OrderSpec(type="ordered", keys=[("submission_id", "asc")]))


def submission(identifier: int, queue: str = "A", at: str | None = None) -> dict[str, Any]:
    return {"submission_id": identifier, "queue": queue, "submitted_at": at}


def boundary_rich_fixture() -> Tables:
    rows = []
    for size in range(1, 9):
        # Reverse physical tie order crosses bucket boundaries, including NULL peers.
        for i in reversed(range(size)):
            at = None if i >= size // 2 else f"2025-01-01T00:00:00.{i % 2:06d}"
            rows.append(submission(size * 100 + i, f"size{size}", at))
    rows.extend(submission(1000 + i, "large", None if i > 30 else
                f"{2024 + i % 3}-01-01T00:00:00.{(39-i):06d}") for i in reversed(range(40)))
    rows.extend([submission(-(2**31), "A", "0001-01-01T00:00:00"),
                 submission(2**31 - 1, "A", "9999-12-31T23:59:59.999999"),
                 submission(-1, "a"), submission(-2, ""), submission(-3, " A ")])
    return {"submissions": rows}


def rich_fixture() -> Tables:
    return boundary_rich_fixture()


def alternatives(reference: str) -> list[str]:
    inner = ("SELECT s.submission_id, NTILE(3) OVER (PARTITION BY s.queue ORDER BY "
             "s.submitted_at ASC NULLS LAST, s.submission_id ASC) AS bucket FROM submissions s")
    return [reference.rstrip("; "),
            (f"WITH allocated AS ({inner}) SELECT submission_id, bucket AS batch_number "
             "FROM allocated ORDER BY submission_id"),
            (f"SELECT d.submission_id, d.bucket AS batch_number FROM ({inner}) d "
             "ORDER BY d.submission_id")]


def arithmetic_expression(prefix: str = "") -> str:
    window = (f"PARTITION BY {prefix}queue ORDER BY {prefix}submitted_at ASC NULLS LAST, "
              f"{prefix}submission_id ASC")
    n = f"COUNT(*) OVER (PARTITION BY {prefix}queue)"
    p = f"ROW_NUMBER() OVER ({window}) - 1"
    q, r = f"({n} // 3)", f"({n} % 3)"
    return (f"CAST(CASE WHEN ({p}) < ({q}+1)*{r} THEN ({p}) // ({q}+1)+1 "
            f"ELSE {r}+(({p})-({q}+1)*{r}) // NULLIF({q},0)+1 END AS BIGINT)")


def structural_control() -> str:
    return (f"SELECT submission_id, {arithmetic_expression()} AS batch_number "
            "FROM submissions ORDER BY submission_id")


def failures(reference: str) -> dict[str, str]:
    base = reference.rstrip("; ")
    result = {name: base.replace("NTILE(3)", expression) for name, expression in {
        "rank": "RANK()", "dense_rank": "DENSE_RANK()", "row_number": "ROW_NUMBER()",
        "ntile2": "NTILE(2)", "ntile4": "NTILE(4)",
    }.items()}
    result.update({
        "constant": "SELECT submission_id,CAST(1 AS BIGINT) AS batch_number FROM submissions ORDER BY submission_id",
        "invent_empty": f"SELECT * FROM ({base}) x UNION ALL SELECT CAST(0 AS INTEGER),CAST(1 AS BIGINT) ORDER BY submission_id",
        "global": base.replace("PARTITION BY queue ", ""),
        "reverse_time": base.replace("submitted_at ASC", "submitted_at DESC"),
        "nulls_first": base.replace("NULLS LAST", "NULLS FIRST"),
        "reverse_id": base.replace("submission_id ASC", "submission_id DESC"),
        "missing_id": base.replace(", submission_id ASC", ""),
        "date_cast": base.replace("submitted_at ASC", "CAST(submitted_at AS DATE) ASC"),
        "id_order": base.replace("submitted_at ASC NULLS LAST, ", ""),
        "casefold": base.replace("PARTITION BY queue", "PARTITION BY LOWER(queue)"),
        "trim": base.replace("PARTITION BY queue", "PARTITION BY TRIM(queue)"),
        "year": base.replace("FROM submissions", "FROM submissions WHERE YEAR(submitted_at)=2025"),
        "no_null": base.replace("FROM submissions", "FROM submissions WHERE submitted_at IS NOT NULL"),
        "no_empty": base.replace("FROM submissions", "FROM submissions WHERE queue<>''"),
        "positive_id": base.replace("FROM submissions", "FROM submissions WHERE submission_id>0"),
        "dedup_payload": base.replace("FROM submissions", "FROM (SELECT * FROM submissions QUALIFY "
                                     "ROW_NUMBER() OVER (PARTITION BY queue,submitted_at "
                                     "ORDER BY submission_id)=1) submissions"),
        "reverse_output": base + " DESC",
        "text_id": base.replace("SELECT submission_id,", "SELECT CAST(submission_id AS VARCHAR) AS submission_id,"),
        "int_batch": base.replace("NTILE(3) OVER (PARTITION BY queue ORDER BY submitted_at ASC NULLS LAST, submission_id ASC)",
                                  "CAST(NTILE(3) OVER (PARTITION BY queue ORDER BY submitted_at ASC NULLS LAST, submission_id ASC) AS INTEGER)"),
        "offset": f"SELECT submission_id,batch_number+1 AS batch_number FROM ({base}) x ORDER BY submission_id",
        "floor_proportional": "SELECT submission_id,CAST(1+((ROW_NUMBER() OVER "
            "(PARTITION BY queue ORDER BY submitted_at ASC NULLS LAST,submission_id))*3) // "
            "COUNT(*) OVER (PARTITION BY queue) AS BIGINT) AS batch_number FROM submissions ORDER BY submission_id",
    })
    return result


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "ntile2", "year": "year", "status_filter": "no_null",
            "partition_by": "global", "rank_order": "rank", "running_order": "reverse_time",
            "tie_policy": "reverse_id", "null_ordering": "nulls_first", "allocation": "floor_proportional",
            "tiny_queues": "constant", "output_columns": "text_id", "output_types": "int_batch",
            "order_by": "reverse_output", "queue_labels": "casefold", "scope": "positive_id",
            "payload_bag": "dedup_payload", "no_extra_domain": "positive_id",
            "empty_input": "invent_empty", "units": "offset"}
    result: dict[str, Any] = {key: {"witness": rich_fixture(), "wrong_sql": wrong[label],
                                      "mutation": label, "outcome": "UNEXECUTED_RULE_SPEC"}
                              for key, label in keys.items()}
    result["empty_input"]["witness"] = {"submissions": []}
    for edge, key in EDGE_PROOFS.items():
        result[edge] = deepcopy(result[key])
    invalid = {"raw:submissions.submission_id": ("submission_id", True),
               "raw:submissions.queue": ("queue", 4),
               "raw:submissions.submitted_at": ("submitted_at", "2025-01-01"),
               "timestamp_domain": ("submitted_at", "2025-01-01T00:00:00.1234567"),
               "nullable": ("queue", None), "exact_schema": ("extra", 1)}
    for key, (column, value) in invalid.items():
        tables = rich_fixture()
        tables["submissions"][0][column] = value
        result[key] = {"witness": tables, "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    tables = rich_fixture()
    tables["submissions"].append(dict(tables["submissions"][0]))
    result["input_domain_rules"] = {"witness": tables, "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    result["ntile_structure"] = {"witness": rich_fixture(), "structural_sql": structural_control(),
                                "outcome": "UNEXECUTED_STRUCTURAL_SPEC"}
    return result


def raw_schema_checks(task: Any, table: str, column: str) -> dict[str, Any]:
    kind = SCHEMA[table][column]
    invalid_by_kind: dict[str, list[Any]] = {"INTEGER": [True, "1", 1.0, -(2**31)-1, 2**31, None],
               "VARCHAR": [1, False, [], None],
               "TIMESTAMP": [1, "2025-02-29T00:00:00", "2025-01-01", "2025-01-01T00:00:00Z",
                             "2025-01-01T00:00:00+01:00", "2025-01-01T00:00:00.0000001"]}
    valid_by_kind: dict[str, list[Any]] = {"INTEGER": [-(2**31), -1, 0, 2**31-1], "VARCHAR": ["", "A", "a", " A ", "é"],
             "TIMESTAMP": [None, "0001-01-01T00:00:00", "9999-12-31 23:59:59.999999",
                           "2025-01-01 00:00:00.1"]}
    rejected, conforming = [], []
    for value in invalid_by_kind[kind]:
        tables = {"submissions": [submission(1)]}
        tables["submissions"][0][column] = value
        try:
            validate_rows(tables)
        except ValueError as exc:
            rejected.append({"value": value, "reason": str(exc), "tables": tables})
        else:
            raise AssertionError("invalid raw schema probe accepted")
    for value in valid_by_kind[kind]:
        tables = {"submissions": [submission(1)]}
        tables["submissions"][0][column] = value
        validate_rows(tables)
        conforming.append({"value": value, "tables": tables})
    return {"declared_type": kind, "domain_reason": "Staged raw types, nullability and unique IDs.",
            "raw_rejections": rejected, "raw_conformance": conforming}


def schema_checks(task: Any, table: str, column: str) -> dict[str, Any]:
    return raw_schema_checks(task, table, column)


def structural_checks(task: Any, sql: str) -> dict[str, Any] | None:
    from .queue_batches_candidate_transforms import structural_checks as check

    return check(task, sql)


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(sql, rich_fixture()) for sql in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    # Physical public order makes missing_id correct before reversal, not after.
    peers = {"submissions": [submission(i, "A", "2025-01-01T00:00:00")
                              for i in range(1, 5)]}
    baseline = {"submissions": [submission(4, "A", "2025-01-01T00:00:00"),
                               submission(3, "A", "2025-01-02T00:00:00"),
                                submission(2, "A", "2025-01-03T00:00:00"), submission(1, "A"),
                                *(submission(i, "B", "2024-01-01T00:00:00") for i in (5, 6, 7))]}
    return [("QUEUE_REVERSE_INPUT", failures(reference)["missing_id"], peers),
            ("QUEUE_RELABEL", failures(reference)["casefold"], baseline)]


def transform(tables: Tables, relation_id: str) -> tuple[Tables | None, str]:
    validate_rows(tables)
    after = deepcopy(tables)
    if relation_id == "QUEUE_REVERSE_INPUT":
        if not any(count > 1 for count in Counter((r["queue"], r["submitted_at"])
                                                  for r in tables["submissions"]).values()):
            return None, "requires timestamp peers"
        after["submissions"].reverse()
    elif relation_id == "QUEUE_RELABEL":
        # Bijective relabeling preserves exact partitions, but LOWER merges A/a.
        if {r["queue"] for r in tables["submissions"]} != {"A", "B"}:
            return None, "requires exactly queues A and B"
        for row in after["submissions"]:
            if row["queue"] == "B":
                row["queue"] = "a"
    else:
        return None, "unsupported relation"
    validate_rows(after)
    assert expected({}, tables) == expected({}, after)
    return after, "whole output invariant under physical permutation or bijective queue relabeling"


def fixture(seed: int, index: int) -> Tables:
    if index % 13 == 12:
        return {"submissions": []}
    rng = Random(f"queue-batches:1:{seed}:{index}")
    tables = rich_fixture()
    tables["submissions"].extend(submission(2000+i, f"frame:{seed}:{index}",
        f"2025-02-01T00:00:00.{rng.randrange(1000000):06d}") for i in range(rng.randint(9, 50)))
    rng.shuffle(tables["submissions"])
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    validate_rows(tables)
    found: set[str] = set()
    rows = tables["submissions"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not rows:
        found.add("empty_input")
    for row in rows:
        groups[row["queue"]].append(row)
        identifier, at = row["submission_id"], row["submitted_at"]
        if identifier == -(2**31):
            found.add("min_integer")
        if identifier == 2**31-1:
            found.add("max_integer")
        if identifier < 0:
            found.add("negative_integer")
        if at is not None:
            parsed = timestamp(at)
            if parsed.year < 2025:
                found.add("prior_year")
            if parsed.year > 2025:
                found.add("next_year")
            if parsed.microsecond:
                found.add("microseconds")
    labels = set(groups)
    if "" in labels:
        found.add("empty_label")
    if any(a != b and a.lower() == b.lower() for a in labels for b in labels):
        found.add("case_labels")
    if any(a != b and a.strip() == b.strip() for a in labels for b in labels):
        found.add("literal_label")
    sizes = [len(group) for group in groups.values()]
    if sizes and max(sizes) >= 5 * min(sizes):
        found.add("skew")
    for group in groups.values():
        n = len(group)
        if n <= 8:
            found.add(f"size_{n}")
        if n >= 30:
            found.add("large_queue")
        if n > 3 and n % 3:
            found.add(f"remainder_{n % 3}")
        times = [r["submitted_at"] for r in group]
        parsed_times = [timestamp(t) for t in times if t is not None]
        if len(set(parsed_times)) < len(parsed_times):
            found.add("timestamp_tie")
        if times.count(None) >= 2:
            found.add("null_peers")
        if None in times and parsed_times:
            found.add("mixed_null")
        if group != _ordered(group):
            found.add("out_of_order")
        if len(set(times)) < n:
            found.add("same_payload_distinct_ids")
    return "queue-batches-observed-v1", BEHAVIORS, found
