"""Standalone Renewal Coverage@1 qualification. No dispatch/admission authority."""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from random import Random
from typing import Any

from pydantic import TypeAdapter

from ..models import ExpectedResult, OrderSpec

CONTRACT = "sql.retention.renewal_coverage"
Tables = dict[str, list[dict[str, Any]]]
SCHEMA = {"episodes": {"episode_id": "INTEGER", "member_id": "INTEGER", "expires_at": "TIMESTAMP"},
          "renewals": {"member_id": "INTEGER", "begins_at": "TIMESTAMP", "ends_at": "TIMESTAMP", "status": "VARCHAR"}}
REFERENCE = ("SELECT e.episode_id, EXISTS (SELECT 1 FROM renewals r WHERE r.member_id=e.member_id "
             "AND r.status='confirmed' AND r.begins_at<=e.expires_at "
             "AND r.ends_at>=e.expires_at+INTERVAL '14 days') AS covered FROM episodes e "
             "WHERE e.expires_at>=TIMESTAMP '2025-01-01' AND e.expires_at<TIMESTAMP '2026-01-01' "
             "ORDER BY e.episode_id")
STRUCTURAL_KEYS: set[str] = set()
DOMAIN_KEYS = {f"raw:{t}.{c}" for t, cs in SCHEMA.items() for c in cs} | {
    "input_domain_rules", "unique_episode", "duration", "nonnull", "exact_schema", "timestamp"}
EDGE_PROOFS = {"duplicates": "bag", "retention_boundaries": "boundary_policy",
               "year_boundary": "all_years", "missing_relationships": "no_renewal"}
CLAUSES = {
    "cohort": ("cohort_definition", "expiring in calendar 2025"),
    "types": ("output_types", "INTEGER and covered BOOLEAN"),
    "order": ("order_by", "ordered by episode_id ascending"),
    "status": ("status", "One confirmed renewal"),
    "member": ("member", "for that member must begin at or before expiry"),
    "begin_endpoint": ("begin_policy", "begin at or before expiry"),
    "end_endpoint": ("end_policy", "end at or after expiry plus"),
    "elapsed": ("retention_window_days", "elapsed 24-hour days"),
    "inclusive": ("boundary_policy", "inclusive even though no activity interval union is computed"),
    "stitch": ("no_stitch", "renewals cannot be stitched"),
    "years": ("all_years", "All renewal years participate; other statuses do not"),
    "episodes": ("episode_identity", "not the member's first purchase"),
    "independent": ("independent", "multiple episodes per member are independently tested"),
    "shared": ("shared", "multiple episodes. No renewal gives FALSE"),
    "bags": ("bag", "repeated and conflicting intervals are separate evidence and existence prevents"),
    "empty": ("empty", "Empty episodes produce no rows"),
    "precision": ("elapsed_precision", "microsecond-resolution timestamps; no calendar-date cast or rounding"),
    "null": ("nonnull", "columns are nonnull"),
    "unique": ("unique_episode", "episodes.episode_id must be unique"),
    "duration": ("duration", "must be >= begins_at"),
    "open_domain": ("open_domain", "No other uniqueness, foreign-key or status-enum restriction"),
    "orphan": ("orphan", "orphan renewals are ignored"),
    "ties": ("no_tie", "No tie selection or NULL ordering is applicable"),
}
BEHAVIORS = ("covered", "uncovered", "exact_begin", "exact_end", "late_begin_us", "early_end_us",
             "adjacent_no_stitch", "duplicate", "conflicting", "shared_member", "shared_interval",
             "cross_year", "prior_year_renewal", "excluded_year", "unknown_status", "orphan",
             "no_renewal", "microsecond", "signed_id", "empty_input")


def timestamp(value: Any) -> datetime:
    if type(value) is datetime and value.tzinfo is None:
        return value
    if type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?", value):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError("requires finite naive ISO microsecond timestamp")


def validate_rows(tables: Mapping[str, list[dict[str, Any]]], *, allow_required_null: bool = False) -> None:
    if set(tables) != set(SCHEMA):
        raise ValueError("exact episodes/renewals table set required")
    ids = set()
    for table, columns in SCHEMA.items():
        if type(tables[table]) is not list:
            raise ValueError(f"{table} requires row list")
        for row in tables[table]:
            if type(row) is not dict or set(row) != set(columns):
                raise ValueError(f"{table} requires exact columns")
            for col, kind in columns.items():
                v = row[col]
                if v is None and allow_required_null:
                    continue
                valid = (type(v) is int and -2147483648 <= v <= 2147483647 if kind == "INTEGER"
                         else type(v) is str if kind == "VARCHAR" else True)
                try:
                    if kind == "TIMESTAMP":
                        timestamp(v)
                    elif not valid:
                        raise ValueError("raw type/nonnullable violation")
                except ValueError as exc:
                    raise ValueError(f"{table}.{col}: {exc}") from exc
            if table == "episodes" and row["episode_id"] is not None:
                if row["episode_id"] in ids:
                    raise ValueError("episodes.episode_id must be unique")
                ids.add(row["episode_id"])
            if (table == "renewals" and row["begins_at"] is not None and row["ends_at"] is not None
                    and timestamp(row["ends_at"]) < timestamp(row["begins_at"])):
                raise ValueError("renewals.ends_at must be >= begins_at")


def expected(requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]) -> ExpectedResult:
    validate_rows(tables)
    rows = []
    for e in sorted(tables["episodes"], key=lambda r: r["episode_id"]):
        expiry = timestamp(e["expires_at"])
        if expiry.year != 2025:  # Filter before arithmetic: excluded year 9999 is valid input.
            continue
        end = expiry + timedelta(days=14)
        covered = any(r["member_id"] == e["member_id"] and r["status"] == "confirmed"
                      and timestamp(r["begins_at"]) <= expiry and timestamp(r["ends_at"]) >= end
                      for r in tables["renewals"])
        rows.append([e["episode_id"], covered])
    return ExpectedResult(columns=["episode_id", "covered"], column_types=["INTEGER", "BOOLEAN"],
                          rows=rows, order=OrderSpec(type="ordered", keys=[("episode_id", "asc")]))


def episode(i: int = 1, member: int = 1, expiry: str = "2025-01-01T00:00:00") -> dict[str, Any]:
    return {"episode_id": i, "member_id": member, "expires_at": expiry}


def renewal(member: int = 1, begin: str = "2025-01-01T00:00:00", end: str = "2025-01-15T00:00:00", status: str = "confirmed") -> dict[str, Any]:
    return {"member_id": member, "begins_at": begin, "ends_at": end, "status": status}


def rich_fixture() -> Tables:
    return {"episodes": [episode(i, i) for i in range(1, 9)] + [
        episode(10, 7, "2025-12-31T23:59:59.999999"), episode(11, 7, "2025-12-30T23:59:59.999999"),
        episode(12, 7, "2026-01-01T00:00:00"), episode(13, 7, "2024-12-31T23:59:59.999999"),
        episode(-2147483648, -1), episode(2147483647, 8),
        episode(9, 9, "2025-01-01T12:00:00.000001")],
        "renewals": [renewal(), renewal(), renewal(2, "2025-01-01T00:00:00.000001"),
        renewal(3, "2024-12-01T00:00:00", "2025-01-14T23:59:59.999999"),
        renewal(4, end="2025-01-08T00:00:00"), renewal(4, "2025-01-08T00:00:00", "2025-02-01T00:00:00"),
        renewal(5, status="unknown"), renewal(1, status="pending"),
        renewal(7, "2025-12-30T23:59:59.999999", "2026-01-14T23:59:59.999999"),
        renewal(8, "2024-12-01T00:00:00", "2025-01-15T00:00:00"),
        renewal(99, "2020-01-01T00:00:00", "2030-01-01T00:00:00"),
        renewal(9, "2025-01-01T00:00:00", "2025-01-15T12:00:00")]}


def alternatives(reference: str) -> list[str]:
    predicate = "r.member_id=e.member_id AND r.status='confirmed' AND r.begins_at<=e.expires_at AND r.ends_at>=e.expires_at+INTERVAL '14 days'"
    cohort = "e.expires_at>=TIMESTAMP '2025-01-01' AND e.expires_at<TIMESTAMP '2026-01-01'"
    return [reference.rstrip("; "),
        f"SELECT e.episode_id, COUNT(r.member_id)>0 AS covered FROM episodes e LEFT JOIN renewals r ON {predicate} WHERE {cohort} GROUP BY e.episode_id ORDER BY e.episode_id",
        f"SELECT e.episode_id, (SELECT COUNT(*) FROM renewals r WHERE {predicate})>0 AS covered FROM episodes e WHERE {cohort} ORDER BY e.episode_id"]


def failures(reference: str) -> dict[str, str]:
    b = reference.rstrip("; ")
    return {
        "member": b.replace("r.member_id=e.member_id", "TRUE"),
        "status": b.replace("r.status='confirmed'", "TRUE"),
        "pending": b.replace("'confirmed'", "'pending'"),
        "begin": b.replace("r.begins_at<=e.expires_at", "TRUE"),
        "strict_begin": b.replace("begins_at<=", "begins_at<"),
        "reverse_begin": b.replace("begins_at<=", "begins_at>="),
        "end": b.replace("r.ends_at>=e.expires_at+INTERVAL '14 days'", "TRUE"),
        "strict_end": b.replace("ends_at>=", "ends_at>"),
        "reverse_end": b.replace("ends_at>=", "ends_at<="),
        "day13": b.replace("14 days", "13 days"), "day15": b.replace("14 days", "15 days"),
        "round_begin": b.replace("r.begins_at<=e.expires_at", "CAST(r.begins_at AS DATE)<=CAST(e.expires_at AS DATE)"),
        "round_end": b.replace("r.ends_at>=e.expires_at+INTERVAL '14 days'", "CAST(r.ends_at AS DATE)>=CAST(e.expires_at AS DATE)+INTERVAL '14 days'"),
        "renewal_year": b.replace("r.status='confirmed'", "r.status='confirmed' AND YEAR(r.begins_at)=2025"),
        "end_year": b.replace("r.status='confirmed'", "r.status='confirmed' AND YEAR(r.ends_at)=2025"),
        "cohort": b.replace("e.expires_at>=TIMESTAMP '2025-01-01' AND e.expires_at<TIMESTAMP '2026-01-01'", "TRUE"),
        "reverse": b + " DESC", "limit": b + " LIMIT 1",
        "text_id": b.replace("SELECT e.episode_id,", "SELECT CAST(e.episode_id AS VARCHAR) AS episode_id,"),
        "wrong_id": b.replace("SELECT e.episode_id,", "SELECT e.member_id AS episode_id,"),
        "false": "SELECT episode_id,FALSE AS covered FROM (" + b + ") q ORDER BY episode_id",
        "true": "SELECT episode_id,TRUE AS covered FROM (" + b + ") q ORDER BY episode_id",
        "repeat": "SELECT * FROM (" + b + ") q UNION ALL SELECT * FROM (" + b + ") z ORDER BY episode_id",
        "single_episode": "SELECT * FROM (" + b + ") q WHERE episode_id<>11 ORDER BY episode_id",
        "empty": "SELECT * FROM (" + b + ") q UNION ALL SELECT 0,FALSE ORDER BY episode_id",
        "stitch": b.replace("r.ends_at>=e.expires_at+INTERVAL '14 days'", "(SELECT MAX(x.ends_at) FROM renewals x WHERE x.member_id=e.member_id)>=e.expires_at+INTERVAL '14 days'"),
    }


PROOF_MUTATIONS = {"objective": "member", "retention_window_days": "day13", "qualifying_event": "stitch",
    "cohort_definition": "cohort", "boundary_policy": "strict_end", "repeated_event_policy": "repeat",
    "output_columns": "wrong_id", "output_types": "text_id", "order_by": "reverse",
    "member": "member", "status": "status", "no_stitch": "stitch", "all_years": "renewal_year",
    "episode_identity": "single_episode", "independent": "single_episode", "shared": "single_episode",
    "bag": "repeat", "empty": "empty", "open_domain": "pending", "orphan": "member",
    "no_tie": "single_episode", "no_renewal": "true", "begin_policy": "strict_begin",
    "end_policy": "strict_end", "elapsed_precision": "round_end", "begin_precision": "round_begin"}


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    result = {k: {"witness": rich_fixture(), "wrong_sql": wrong[m], "mutation": m,
                  "outcome": "UNEXECUTED_RULE_SPEC"} for k, m in PROOF_MUTATIONS.items()}
    for edge, key in EDGE_PROOFS.items():
        result[edge] = deepcopy(result[key])
    for table, cols in SCHEMA.items():
        for col, kind in cols.items():
            t = rich_fixture()
            t[table][0][col] = True if kind == "INTEGER" else 42
            result[f"raw:{table}.{col}"] = {"witness": t, "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    for key in ("input_domain_rules", "unique_episode", "duration", "nonnull", "exact_schema", "timestamp"):
        t = rich_fixture()
        if key in {"input_domain_rules", "unique_episode"}:
            t["episodes"].append(deepcopy(t["episodes"][0]))
        elif key == "duration":
            t["renewals"][0]["ends_at"] = "2024-01-01T00:00:00"
        elif key == "nonnull":
            t["renewals"][0]["status"] = None
        elif key == "exact_schema":
            t["episodes"][0]["extra"] = 1
        else:
            t["episodes"][0]["expires_at"] = "2025-01-01T00:00:00.0000001"
        result[key] = {"witness": t, "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    return result


def schema_checks(task: Any, table: str, column: str) -> dict[str, Any]:
    kind = SCHEMA[table][column]
    invalid: list[Any] = [None, True, 42.5, [], {}]
    valid: list[Any] = []
    if kind == "INTEGER":
        invalid += ["1", -2147483649, 2147483648]
        valid = [-2147483648, -1, 0, 2147483647]
    elif kind == "VARCHAR":
        invalid += [42]
        valid = ["", "unknown", "CONFIRMED", "confirmed", "é"]
    else:
        invalid += ["infinity", "2025-02-30T00:00:00", "2025-01-01", "2025-01-01T00:00:00Z",
                    "2025-01-01T00:00:00.0000001", datetime(2025, 1, 1, tzinfo=UTC)]
        valid = ["0001-01-01T00:00:00", "9999-12-31 23:59:59.999999", "2025-01-01T00:00:00.1", datetime(2025, 1, 1)]  # noqa: DTZ001 -- public timestamps are naive.
    def probe(v: Any) -> Tables:
        t = {"episodes": [episode()], "renewals": [renewal()]}
        t[table][0][column] = v
        if kind == "TIMESTAMP" and table == "renewals":
            t[table][0]["ends_at" if column == "begins_at" else "begins_at"] = v
        return t
    rejected = []
    for v in invalid:
        t = probe(v)
        try:
            validate_rows(t)
        except ValueError as exc:
            rejected.append({"value": v, "tables": t, "reason": str(exc)})
        else:
            raise ValueError("domain probe not rejected")
    conform = [{"value": v, "tables": probe(v)} for v in valid]
    for item in conform:
        validate_rows(item["tables"])
    checks = {"declared_type": kind, "domain_reason": "Exact staged raw domain; unique episode IDs and nonnegative durations",
              "raw_rejections": rejected, "raw_conformance": conform}
    # Normalize evidence only, after testing the original raw Python values.
    wire = TypeAdapter(dict[str, Any])
    return wire.validate_json(wire.dump_json(checks))


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(s, rich_fixture()) for s in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    before = {"episodes": [episode()], "renewals": [renewal(end="2025-01-08T00:00:00")]}
    return [("RENEWAL_ADJACENT", failures(reference)["stitch"], deepcopy(before)),
            ("RENEWAL_ORPHAN", failures(reference)["member"], deepcopy(before))]


def transform(tables: Tables, relation_id: str) -> tuple[Tables | None, str]:
    validate_rows(tables)
    after = deepcopy(tables)
    if relation_id == "RENEWAL_ORPHAN":
        used = {e["member_id"] for e in tables["episodes"]}
        free = next((i for i in range(len(used) + 1) if i not in used), None)
        if free is None or free > 2147483647:
            return None, "no available member"
        after["renewals"].append(renewal(free, "0001-01-01T00:00:00", "9999-12-31T23:59:59.999999"))
    elif relation_id == "RENEWAL_ADJACENT":
        eligible = [e for e in tables["episodes"] if timestamp(e["expires_at"]).year == 2025]
        if not eligible:
            return None, "requires 2025 episode"
        e = eligible[0]
        expiry = timestamp(e["expires_at"])
        after["renewals"].append(renewal(e["member_id"], (expiry + timedelta(days=7)).isoformat(), (expiry + timedelta(days=14)).isoformat()))
    else:
        return None, "unsupported relation"
    validate_rows(after)
    if expected({}, tables) != expected({}, after):
        return None, "insertion would cover another supplied episode"
    return after, "valid output-invariant insertion"


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"renewal-coverage:1:{seed}:{index}")
    if index % 13 == 12:
        return {"episodes": [], "renewals": []}
    t = rich_fixture()
    for n in range(rng.randint(1, 10)):
        expiry = datetime(2025, 1, 1) + timedelta(microseconds=rng.randrange(365 * 86400 * 1000000))  # noqa: DTZ001 -- public timestamps are naive.
        member = 100 + n
        t["episodes"].append(episode(100 + n, member, expiry.isoformat()))
        t["renewals"].append(renewal(member, (expiry + timedelta(microseconds=rng.choice([-1, 0, 1]))).isoformat(),
            (expiry + timedelta(days=14, microseconds=rng.choice([-1, 0, 1]))).isoformat(), rng.choice(["confirmed", "pending", ""])))
    rng.shuffle(t["episodes"])
    rng.shuffle(t["renewals"])
    return t


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    validate_rows(tables)
    found = set()
    es, rs = tables["episodes"], tables["renewals"]
    if not es:
        found.add("empty_input")
    if any(v > 1 for v in Counter(tuple(r[c] for c in SCHEMA["renewals"]) for r in rs).values()):
        found.add("duplicate")
    if any(r["status"] not in {"confirmed", "pending"} for r in rs):
        found.add("unknown_status")
    if any(not any(e["member_id"] == r["member_id"] for e in es) for r in rs):
        found.add("orphan")
    if any(e["episode_id"] < 0 for e in es):
        found.add("signed_id")
    coverage = dict(expected({}, tables).rows)
    for e in es:
        x = timestamp(e["expires_at"])
        if x.year != 2025:
            found.add("excluded_year")
            continue
        end = x + timedelta(days=14)
        own = [r for r in rs if r["member_id"] == e["member_id"]]
        confirmed = [r for r in own if r["status"] == "confirmed"]
        found.add("covered" if coverage[e["episode_id"]] else "uncovered")
        if not own:
            found.add("no_renewal")
        if x.microsecond:
            found.add("microsecond")
        if end.year != x.year and coverage[e["episode_id"]]:
            found.add("cross_year")
        if sum(a["member_id"] == e["member_id"] for a in es) > 1:
            found.add("shared_member")
        if len({r["status"] for r in own}) > 1:
            found.add("conflicting")
        for r in confirmed:
            b, z = timestamp(r["begins_at"]), timestamp(r["ends_at"])
            if b == x:
                found.add("exact_begin")
            if z == end:
                found.add("exact_end")
            if b == x + timedelta(microseconds=1) and z >= end:
                found.add("late_begin_us")
            if z == end - timedelta(microseconds=1) and b <= x:
                found.add("early_end_us")
            if b.year < 2025 and b <= x and z >= end:
                found.add("prior_year_renewal")
            if sum(a["member_id"] == r["member_id"] and timestamp(a["expires_at"]).year == 2025
                   and b <= timestamp(a["expires_at"]) and z >= timestamp(a["expires_at"]) + timedelta(days=14) for a in es) > 1:
                found.add("shared_interval")
            if b <= x and z < end and not coverage[e["episode_id"]] and any(
                    timestamp(s["begins_at"]) == z and timestamp(s["ends_at"]) >= end for s in confirmed):
                found.add("adjacent_no_stitch")
    return "renewal-coverage-observed-v1", BEHAVIORS, found


def candidate_proofs(sql: str, reference: str, public: dict[str, Any]) -> dict[str, Any] | None:
    from .renewal_coverage_candidate_transforms import candidate_proofs as derive
    return derive(sql, reference, public)
