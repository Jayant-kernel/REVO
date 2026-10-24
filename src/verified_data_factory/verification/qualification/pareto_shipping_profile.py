"""Standalone Pareto Shipping@1 qualification; no dispatch or admission authority."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from random import Random
from typing import Any

from ..models import ExpectedResult, OrderSpec

CONTRACT = "sql.subqueries.pareto_shipping"
Tables = dict[str, list[dict[str, Any]]]
FIELDS = ("option_id", "lane", "cost_cents", "duration_minutes")
MAX = 2147483647
REFERENCE = (
    "SELECT o.option_id, o.lane, o.cost_cents, o.duration_minutes FROM options o "
    "WHERE o.cost_cents IS NOT NULL AND o.duration_minutes IS NOT NULL AND NOT EXISTS ("
    "SELECT 1 FROM options p WHERE p.lane = o.lane AND p.cost_cents IS NOT NULL "
    "AND p.duration_minutes IS NOT NULL AND p.cost_cents <= o.cost_cents "
    "AND p.duration_minutes <= o.duration_minutes "
    "AND (p.cost_cents < o.cost_cents OR p.duration_minutes < o.duration_minutes)) "
    "ORDER BY o.option_id ASC"
)
BEHAVIORS = ("complete", "null_cost", "null_duration", "both_null", "equal_pairs",
             "tradeoff", "strict_cost", "strict_duration", "strict_both", "lane_isolation",
             "empty_lane", "case_sensitive_lane", "zero", "max_integer", "signed_ids",
             "id_boundaries", "all_incomplete_lane", "empty_input")
STRUCTURAL_KEYS = {"not_exists_structure"}
DOMAIN_KEYS = {"input_domain_rules", "unique_option_id", "option_id_type", "lane_type",
               "cost_type", "duration_type", "cost_range", "duration_range"}
EDGE_PROOFS = {"null_values": "incomplete", "ties": "equal_pairs",
               "zero_values": "zero_values", "empty_result": "empty_result"}
CLAUSES = {
    "unique_proposals": ("unique_option_id", "Each row is one unique option_id shipping proposal"),
    "lane_domain": ("lane_type", "nonnull arbitrary text lane (empty text allowed)"),
    "cost_units": ("cost_type", "Cost is integer currency cents"),
    "duration_units": ("duration_type", "duration is whole elapsed minutes"),
    "metric_domain": ("input_domain_rules", "Both metrics are nullable and otherwise [0,2147483647]"),
    "incomplete": ("incomplete", "Incomplete options (either metric NULL) are excluded as both candidates and competitors"),
    "dominance": ("threshold_operator", "Retain complete options unless some same-lane complete competitor has cost <= candidate cost AND duration <= candidate duration AND at least one strict improvement"),
    "not_exists_structure": ("not_exists_structure", "Use a correlated NOT EXISTS subquery"),
    "equal_pairs": ("equal_pairs", "Equal metric pairs do not dominate each other and all their distinct option_ids survive; no single-winner tie-break"),
    "self": ("self", "Self cannot dominate itself"),
    "once": ("once", "Output once per surviving option"),
    "empty": ("empty_result", "Empty input or all incomplete options gives empty output"),
    "no_scope": ("year", "No date/status filter or missing-settlement history semantics"),
}


def option(identifier: int = 1, lane: str = "A", cost: int | None = 10,
           duration: int | None = 20) -> dict[str, Any]:
    return dict(zip(FIELDS, (identifier, lane, cost, duration), strict=True))


def validate_rows(tables: Mapping[str, list[dict[str, Any]]], *,
                  allow_required_null: bool = False) -> None:
    if set(tables) != {"options"} or type(tables["options"]) is not list:
        raise ValueError("pareto_shipping requires exactly options rows")
    ids: set[int] = set()
    for row in tables["options"]:
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise ValueError("options requires exactly option_id,lane,cost_cents,duration_minutes")
        identifier = row["option_id"]
        if not (allow_required_null and identifier is None):
            if type(identifier) is not int or not -2147483648 <= identifier <= MAX:
                raise ValueError("options.option_id requires raw signed32 integer")
            if identifier in ids:
                raise ValueError("options.option_id must be unique")
            ids.add(identifier)
        if not (allow_required_null and row["lane"] is None) and type(row["lane"]) is not str:
            raise ValueError("options.lane requires nonnull raw text; empty allowed")
        for field in FIELDS[2:]:
            value = row[field]
            if value is not None and (type(value) is not int or not 0 <= value <= MAX):
                raise ValueError(f"options.{field} requires NULL or raw integer in [0,2147483647]")


def expected(requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]) -> ExpectedResult:
    validate_rows(tables)
    complete = [r for r in tables["options"] if r["cost_cents"] is not None
                and r["duration_minutes"] is not None]
    survivors = []
    for candidate in complete:
        dominated = any(p["lane"] == candidate["lane"]
                        and p["cost_cents"] <= candidate["cost_cents"]
                        and p["duration_minutes"] <= candidate["duration_minutes"]
                        and (p["cost_cents"] < candidate["cost_cents"]
                             or p["duration_minutes"] < candidate["duration_minutes"])
                        for p in complete)
        if not dominated:
            survivors.append(candidate)
    return ExpectedResult(columns=list(FIELDS), column_types=["INTEGER", "VARCHAR", "INTEGER", "INTEGER"],
                          rows=[[r[f] for f in FIELDS] for r in sorted(survivors, key=lambda r: r["option_id"])],
                          order=OrderSpec(type="ordered", keys=[("option_id", "asc")]))


def schema_checks(task: Any, table: str, column: str) -> dict[str, Any]:
    if table != "options" or column not in FIELDS:
        raise ValueError("unknown Pareto schema field")
    invalid: list[Any] = [True, False, "10", 1.5]
    if column == "lane":
        invalid = [None, 42, True, 1.5]
        valid: list[Any] = ["", "A", "a", "é", " s "]
    elif column == "option_id":
        invalid += [None, -2147483649, MAX + 1]
        valid = [-2147483648, -1, 0, MAX]
    else:
        invalid += [-1, MAX + 1]
        valid = [None, 0, MAX]
    rejections = []
    for value in invalid:
        row = option()
        row[column] = value
        try:
            validate_rows({"options": [row]})
        except ValueError as exc:
            rejections.append({"value": value, "reason": str(exc)})
        else:
            raise ValueError("raw Pareto domain probe not rejected")
    for value in valid:
        row = option()
        row[column] = value
        validate_rows({"options": [row]})  # Isolated IDs cannot collide at a boundary.
    return {"domain_reason": "Exact non-coercing Pareto Shipping@1 raw domain",
            "raw_rejections": rejections, "raw_conformance": valid}


def rich_fixture() -> Tables:
    return {"options": [option(-2147483648, "", 0, 0), option(-1, "A", 10, 20),
        option(0, "A", 20, 10), option(1, "A", 20, 20), option(2, "A", 10, 20),
        option(3, "A", None, 0), option(4, "A", 0, None), option(5, "null", None, None),
        option(6, "B", MAX, MAX), option(7, "B", MAX, 5), option(8, "D", 7, 0),
        option(9, "D", 8, 0), option(10, "E", 5, 5), option(11, "E", 8, 8),
        option(12, "a", 1, 1), option(13, " A ", 9, 9), option(14, "é", 3, 4),
        option(MAX, "max", MAX, MAX)]}


def alternatives(reference: str) -> list[str]:
    split = reference.replace(
        "p.cost_cents <= o.cost_cents AND p.duration_minutes <= o.duration_minutes "
        "AND (p.cost_cents < o.cost_cents OR p.duration_minutes < o.duration_minutes)",
        "((p.cost_cents < o.cost_cents AND p.duration_minutes <= o.duration_minutes) "
        "OR (p.cost_cents <= o.cost_cents AND p.duration_minutes < o.duration_minutes))")
    cte = ("WITH complete AS (SELECT * FROM options WHERE cost_cents IS NOT NULL AND duration_minutes IS NOT NULL) "
           "SELECT o.option_id,o.lane,o.cost_cents,o.duration_minutes FROM complete o WHERE NOT EXISTS ("
           "SELECT 1 FROM complete p WHERE p.lane=o.lane AND p.cost_cents<=o.cost_cents "
           "AND p.duration_minutes<=o.duration_minutes "
           "AND (p.cost_cents<o.cost_cents OR p.duration_minutes<o.duration_minutes)) ORDER BY o.option_id")
    return [reference, split, cte]


def failures(reference: str) -> dict[str, str]:
    weak = "p.cost_cents <= o.cost_cents AND p.duration_minutes <= o.duration_minutes"
    strict = "(p.cost_cents < o.cost_cents OR p.duration_minutes < o.duration_minutes)"
    return {
        "global": reference.replace("p.lane = o.lane", "TRUE"),
        "casefold": reference.replace("p.lane = o.lane", "LOWER(p.lane) = LOWER(o.lane)"),
        "trim": reference.replace("p.lane = o.lane", "TRIM(p.lane) = TRIM(o.lane)"),
        "strict_both": reference.replace(strict, "(p.cost_cents < o.cost_cents AND p.duration_minutes < o.duration_minutes)"),
        "weak_only": reference.replace(strict, "TRUE"),
        "cost_only": reference.replace(weak, "p.cost_cents <= o.cost_cents").replace(strict, "p.cost_cents < o.cost_cents"),
        "duration_only": reference.replace(weak, "p.duration_minutes <= o.duration_minutes").replace(strict, "p.duration_minutes < o.duration_minutes"),
        "weak_or": reference.replace(weak, "(p.cost_cents <= o.cost_cents OR p.duration_minutes <= o.duration_minutes)"),
        "reverse_cost": reference.replace("p.cost_cents <= o.cost_cents", "p.cost_cents >= o.cost_cents"),
        "reverse_duration": reference.replace("p.duration_minutes <= o.duration_minutes", "p.duration_minutes >= o.duration_minutes"),
        "include_incomplete": reference.replace("o.cost_cents IS NOT NULL AND o.duration_minutes IS NOT NULL", "TRUE"),
        "coalesce": reference.replace("p.cost_cents IS NOT NULL AND p.duration_minutes IS NOT NULL", "TRUE")
            .replace("p.cost_cents", "COALESCE(p.cost_cents,0)").replace("p.duration_minutes", "COALESCE(p.duration_minutes,0)"),
        "no_zero": "SELECT * FROM (" + reference + ") x WHERE cost_cents > 0 AND duration_minutes > 0 ORDER BY option_id",
        "no_max": "SELECT * FROM (" + reference + ") x WHERE cost_cents < 2147483647 AND duration_minutes < 2147483647 ORDER BY option_id",
        "no_empty_lane": "SELECT * FROM (" + reference + ") x WHERE lane <> '' ORDER BY option_id",
        "positive_ids": "SELECT * FROM (" + reference + ") x WHERE option_id > 0 ORDER BY option_id",
        "scope": "SELECT * FROM (" + reference + ") x WHERE lane = 'A' ORDER BY option_id",
        "single_tie": "SELECT * FROM (" + reference + ") x QUALIFY ROW_NUMBER() OVER (PARTITION BY lane,cost_cents,duration_minutes ORDER BY option_id)=1 ORDER BY option_id",
        "repeat": "SELECT * FROM (" + reference + ") x UNION ALL SELECT * FROM (" + reference + ") y ORDER BY option_id",
        "reverse": reference.replace("ORDER BY o.option_id ASC", "ORDER BY o.option_id DESC"),
        "text_id": reference.replace("SELECT o.option_id,", "SELECT CAST(o.option_id AS VARCHAR) AS option_id,"),
        "wrong_lane": reference.replace("o.option_id, o.lane,", "o.option_id, CAST('wrong' AS VARCHAR) AS lane,"),
        "swapped": reference.replace("SELECT o.option_id, o.lane, o.cost_cents, o.duration_minutes", "SELECT o.option_id,o.lane,o.duration_minutes AS cost_cents,o.cost_cents AS duration_minutes"),
        "limit": reference + " LIMIT 1",
        "invent_empty": "SELECT * FROM (" + reference + ") x UNION ALL SELECT CAST(1 AS INTEGER),'invented',CAST(0 AS INTEGER),CAST(0 AS INTEGER) ORDER BY option_id",
    }


def structural_controls(reference: str = REFERENCE) -> dict[str, str]:
    count = reference.replace("NOT EXISTS (SELECT 1", "(SELECT COUNT(*)").replace(
        ")) ORDER BY", ")) = 0 ORDER BY")
    return {"count_dominator": count,
            "decorative": count.replace("ORDER BY o.option_id", "AND NOT EXISTS (SELECT 1 FROM options z WHERE FALSE) ORDER BY o.option_id")}


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    mapping = {"objective": "strict_both", "year": "scope", "status_filter": "scope",
        "threshold_operator": "strict_both", "exists_semantics": "global", "no_match_behavior": "weak_only",
        "output_columns": "wrong_lane", "output_types": "text_id", "order_by": "reverse",
        "incomplete": "coalesce", "equal_pairs": "single_tie", "self": "weak_only", "once": "repeat",
        "zero_values": "no_zero", "empty_lane": "no_empty_lane", "lane_local": "global",
        "case_sensitive_lane": "casefold", "max_integer": "no_max", "signed_ids": "positive_ids"}
    result = {key: {"witness": rich_fixture(), "wrong_sql": wrong[label], "mutation": label,
                    "outcome": "UNEXECUTED_RULE_SPEC"} for key, label in mapping.items()}
    result["empty_result"] = {"witness": {"options": []}, "wrong_sql": wrong["invent_empty"],
                              "mutation": "invent_empty", "outcome": "UNEXECUTED_RULE_SPEC"}
    for key, field, value in (("input_domain_rules", "cost_cents", -1),
        ("option_id_type", "option_id", True), ("lane_type", "lane", None),
        ("cost_type", "cost_cents", "10"), ("duration_type", "duration_minutes", 1.5),
        ("cost_range", "cost_cents", MAX + 1), ("duration_range", "duration_minutes", -1)):
        row = option()
        row[field] = value
        result[key] = {"witness": {"options": [row]}, "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    result["unique_option_id"] = {"witness": {"options": [option(), option(cost=5)]},
                                  "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    result["not_exists_structure"] = {"witness": rich_fixture(),
        "structural_sql": structural_controls(reference)["count_dominator"],
        "outcome": "UNEXECUTED_STRUCTURAL_SPEC"}
    return result


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(sql, rich_fixture()) for sql in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    wrong = failures(reference)
    return [("PARETO_INCOMPLETE_COMPETITOR", wrong["coalesce"], {"options": [option()]}),
            ("PARETO_EQUAL_DURATION_DOMINATED", wrong["strict_both"], {"options": [option()]})]


def transform(tables: Tables, identifier: str) -> tuple[Tables | None, str]:
    validate_rows(tables)
    rows = tables["options"]
    complete = [r for r in rows if r["cost_cents"] is not None and r["duration_minutes"] is not None]
    used = {r["option_id"] for r in rows}
    free = next((i for i in range(len(rows) + 1) if i not in used), None)
    if not complete or free is None or free > MAX:
        return None, "requires complete option and available signed32 ID"
    row = complete[0]
    if identifier == "PARETO_INCOMPLETE_COMPETITOR":
        added = option(free, row["lane"], None, 0)
    elif identifier == "PARETO_EQUAL_DURATION_DOMINATED" and row["cost_cents"] < MAX:
        added = option(free, row["lane"], row["cost_cents"] + 1, row["duration_minutes"])
    else:
        return None, "unknown relation or cost cannot increase in domain"
    after = deepcopy(tables)
    after["options"].append(added)
    validate_rows(after)
    return after, "valid fresh-ID proposal added"


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"pareto-shipping:1:{seed}:{index}")
    if index % 13 == 12:
        return {"options": []}
    tables = rich_fixture()
    for number in range(rng.randint(3, 18)):
        tables["options"].append(option(100 + number, f"frame:{seed}:{index}:{number % 3}",
            rng.choice([None, 0, MAX, rng.randrange(MAX + 1)]),
            rng.choice([None, 0, MAX, rng.randrange(MAX + 1)])))
    rng.shuffle(tables["options"])
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    validate_rows(tables)
    rows = tables["options"]
    found: set[str] = set()
    if not rows:
        found.add("empty_input")
    complete = [r for r in rows if r["cost_cents"] is not None and r["duration_minutes"] is not None]
    for r in rows:
        c, d = r["cost_cents"], r["duration_minutes"]
        if c is None:
            found.add("null_cost")
        if d is None:
            found.add("null_duration")
        if c is None and d is None:
            found.add("both_null")
        if c is not None and d is not None:
            found.add("complete")
        if c == 0 or d == 0:
            found.add("zero")
        if c == MAX or d == MAX:
            found.add("max_integer")
        if r["lane"] == "":
            found.add("empty_lane")
        if r["option_id"] < 0:
            found.add("signed_ids")
        if r["option_id"] in (-2147483648, MAX):
            found.add("id_boundaries")
        if not any(p["lane"] == r["lane"] for p in complete):
            found.add("all_incomplete_lane")
    for a in complete:
        for b in complete:
            if a["option_id"] == b["option_id"]:
                continue
            if a["lane"] != b["lane"]:
                if a["cost_cents"] < b["cost_cents"] and a["duration_minutes"] < b["duration_minutes"]:
                    found.add("lane_isolation")
                    if a["lane"].lower() == b["lane"].lower():
                        found.add("case_sensitive_lane")
                continue
            c, d = a["cost_cents"] - b["cost_cents"], a["duration_minutes"] - b["duration_minutes"]
            if c == d == 0:
                found.add("equal_pairs")
            if c * d < 0:
                found.add("tradeoff")
            if c < 0 and d == 0:
                found.add("strict_cost")
            if c == 0 and d < 0:
                found.add("strict_duration")
            if c < 0 and d < 0:
                found.add("strict_both")
    return "pareto-shipping-observed-v1", BEHAVIORS, found


def candidate_proofs(sql: str, reference: str, public: dict[str, Any]) -> dict[str, Any] | None:
    from .pareto_shipping_candidate_transforms import candidate_proofs as derive

    return derive(sql, reference, public)


def structural_checks(task: Any, sql: str) -> dict[str, Any] | None:
    from .pareto_shipping_candidate_transforms import structural_checks as check

    return check(task, sql)
