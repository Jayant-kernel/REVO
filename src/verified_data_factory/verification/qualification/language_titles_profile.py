"""Requested-language titles@1: strict raw schema and SQL-free bag semantics."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from random import Random
from typing import Any

from ..models import ExpectedResult, OrderSpec

CONTRACT = "sql.joins.requested_language_titles"
REFERENCE = ("SELECT r.request_id, t.title FROM requests r LEFT JOIN translations t "
             "ON r.item_id = t.item_id AND r.language = t.language")
Tables = dict[str, list[dict[str, Any]]]
SCHEMA = {"requests": {"request_id": "INTEGER", "item_id": "INTEGER", "language": "VARCHAR"},
          "translations": {"item_id": "INTEGER", "language": "VARCHAR", "title": "VARCHAR"}}
BEHAVIORS = ("matched", "unmatched", "null_item", "null_language", "both_null",
             "matched_null_title", "duplicate_requests", "duplicate_translations",
             "multiple_matches", "duplicate_product", "case_sensitive", "empty_language",
             "empty_title", "literal_language", "orphan", "min_integer", "max_integer",
             "negative_integer", "empty_input")
CLAUSES = {
    "composite_key": ("composite_key", "on both item_id"),
    "case_sensitive": ("case_sensitive", "exact case-sensitive language equality"),
    "request_bag": ("request_bag", "Each request row emits one row per"),
    "translation_bag": ("translation_bag", "matching translation row"),
    "unmatched": ("unmatched_behavior", "exactly one row with NULL title if none matches"),
    "null_keys": ("null_semantics", "Any NULL key component prevents matching, including NULL to NULL"),
    "null_title": ("null_title", "NULL title remains NULL; it is not replaced"),
    "no_fallback": ("no_fallback", "No language fallback"),
    "no_filter": ("no_filter", "status/year filter or deduplication"),
    "orphan": ("orphan", "Translation-only rows emit nothing"),
    "nonunique": ("nonunique", "request_id/item_id/language are not unique"),
    "bag": ("bag", "unordered bag with all multiplicities"),
    "no_winner": ("no_winner", "no tie/winner selection"),
    "text": ("text", "Units are categorical text"),
    "integer": ("integer", "JSON INTEGER is bounded signed32 integer excluding bool/string"),
    "varchar": ("varchar", "VARCHAR is text"),
    "nullable": ("nullable", "NULL only nullable columns"),
    "exact_schema": ("exact_schema", "Exact declared table/column sets required"),
    "no_domain": ("input_domain_rules", "no other domain restrictions"),
}
DOMAIN_KEYS = {f"raw:{table}.{column}" for table, columns in SCHEMA.items() for column in columns}
DOMAIN_KEYS.update({"integer", "varchar", "nullable", "exact_schema"})
STRUCTURAL_KEYS: set[str] = set()
EDGE_PROOFS = {"duplicates": "bag", "null_values": "null_semantics",
               "missing_relationships": "unmatched_behavior", "multiple_matching_rows": "translation_bag"}


def request(identifier: int = 1, item: int | None = 10,
            language: str | None = "en") -> dict[str, Any]:
    return {"request_id": identifier, "item_id": item, "language": language}


def translation(item: int | None = 10, language: str | None = "en",
                title: str | None = "Book") -> dict[str, Any]:
    return {"item_id": item, "language": language, "title": title}


def validate_rows(tables: Mapping[str, list[dict[str, Any]]], *,
                  allow_required_null: bool = False) -> None:
    if set(tables) != set(SCHEMA):
        raise ValueError("language_titles requires exactly requests and translations")
    for table, columns in SCHEMA.items():
        if type(tables[table]) is not list:
            raise ValueError(f"{table} must be a row list")
        for row in tables[table]:
            if not isinstance(row, dict) or set(row) != set(columns):
                raise ValueError(f"{table} requires exactly {tuple(columns)}")
            for column, kind in columns.items():
                value = row[column]
                if value is None:
                    if (table, column) == ("requests", "request_id") and not allow_required_null:
                        raise ValueError("requests.request_id must be nonnull")
                elif kind == "INTEGER":
                    if type(value) is not int or not -2147483648 <= value <= 2147483647:
                        raise ValueError(f"{table}.{column} must be raw signed32 integer, not bool/string")
                elif type(value) is not str:
                    raise ValueError(f"{table}.{column} must be raw text")


def _matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(left[key] is not None and right[key] is not None and left[key] == right[key]
               for key in ("item_id", "language"))


def expected(requirements: Mapping[str, Any],
             tables: Mapping[str, list[dict[str, Any]]]) -> ExpectedResult:
    validate_rows(tables)
    rows = []
    for left in tables["requests"]:
        matched = [right for right in tables["translations"] if _matches(left, right)]
        rows.extend([[left["request_id"], right["title"]] for right in matched]
                    if matched else [[left["request_id"], None]])
    return ExpectedResult(columns=["request_id", "title"], column_types=["INTEGER", "VARCHAR"],
                          rows=rows, order=OrderSpec(type="unordered"))


def rich_fixture() -> Tables:
    return {"requests": [request(), request(), request(2, 10, "fr"), request(3, None),
        request(4, 10, None), request(5, 10, "EN"), request(6, 11), request(7, 12, ""),
        request(-2147483648, -2147483648), request(2147483647, 2147483647),
        request(-1, -1, " en "), request(8, None, None), request(1, 13, "en")],
        "translations": [translation(), translation(), translation(title="Volume"),
        translation(None, title="null item"), translation(10, None, "null language"),
        translation(None, None, "both null"), translation(11, title=None),
        translation(12, "", ""), translation(-2147483648, title="minimum"),
        translation(2147483647, title="maximum"), translation(-1, "en", "trim trap"),
        translation(-1, " en ", "literal"), translation(13, "en", "Other"),
        translation(99, "de", "orphan")]}


def alternatives(reference: str) -> list[str]:
    return [reference.rstrip("; "),
        ("SELECT r.request_id,t.title FROM requests r LEFT JOIN LATERAL "
         "(SELECT title FROM translations x WHERE x.item_id=r.item_id AND x.language=r.language) t ON TRUE"),
        ("SELECT r.request_id,t.title FROM requests r JOIN translations t "
        "ON r.item_id=t.item_id AND r.language=t.language UNION ALL "
        "SELECT r.request_id,CAST(NULL AS VARCHAR) AS title FROM requests r WHERE NOT EXISTS "
         "(SELECT 1 FROM translations t WHERE t.item_id=r.item_id AND t.language=r.language)")]


def failures(reference: str) -> dict[str, str]:
    base = reference.rstrip("; ")
    predicate = "r.item_id = t.item_id AND r.language = t.language"
    def on(value: str) -> str:
        return base.replace(predicate, value)
    return {
        "inner": base.replace("LEFT JOIN", "JOIN"),
        "full": base.replace("LEFT JOIN", "FULL JOIN"),
        "right": base.replace("LEFT JOIN", "RIGHT JOIN"),
        "item_only": on("r.item_id = t.item_id"),
        "language_only": on("r.language = t.language"),
        "or_keys": on("r.item_id = t.item_id OR r.language = t.language"),
        "null_item_equal": on("r.item_id IS NOT DISTINCT FROM t.item_id AND r.language = t.language"),
        "null_language_equal": on("r.item_id = t.item_id AND r.language IS NOT DISTINCT FROM t.language"),
        "null_both_equal": on("r.item_id IS NOT DISTINCT FROM t.item_id AND r.language IS NOT DISTINCT FROM t.language"),
        "casefold": on("r.item_id = t.item_id AND LOWER(r.language) = LOWER(t.language)"),
        "trim": on("r.item_id = t.item_id AND TRIM(r.language) = TRIM(t.language)"),
        "distinct": base.replace("SELECT r.", "SELECT DISTINCT r."),
        "request_dedup": base.replace("requests r", "(SELECT DISTINCT * FROM requests) r"),
        "translation_dedup": base.replace("translations t", "(SELECT DISTINCT * FROM translations) t"),
        "winner": base + " QUALIFY ROW_NUMBER() OVER (PARTITION BY r.request_id ORDER BY t.title)=1",
        "fallback": base.replace("t.title FROM", "COALESCE(t.title,'fallback') AS title FROM"),
        "null_filter": base + " WHERE t.title IS NOT NULL",
        "nonnegative": base + " WHERE r.request_id >= 0",
        "positive_item": base + " WHERE r.item_id > 0",
        "no_empty": base + " WHERE r.language <> ''",
        "only_en": base + " WHERE r.language = 'en'",
        "wrong_id": base.replace("r.request_id,", "r.item_id AS request_id,"),
        "text_id": base.replace("r.request_id,", "CAST(r.request_id AS VARCHAR) AS request_id,"),
        "wrong_title": base.replace("t.title FROM", "t.language AS title FROM"),
        "limit": base + " LIMIT 1",
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "item_only", "year": "nonnegative", "status_filter": "only_en",
        "join_type": "inner", "unmatched_behavior": "inner", "null_semantics": "null_both_equal",
        "output_columns": "wrong_id", "output_types": "text_id", "input_domain_rules": "nonnegative",
        "composite_key": "item_only", "case_sensitive": "casefold", "request_bag": "request_dedup",
        "translation_bag": "translation_dedup", "null_title": "fallback", "no_fallback": "item_only",
        "no_filter": "only_en", "orphan": "full", "nonunique": "winner", "bag": "distinct",
        "no_winner": "winner", "text": "trim", "empty_text": "no_empty",
        "duplicates": "distinct", "null_values": "null_both_equal",
        "missing_relationships": "inner", "multiple_matching_rows": "translation_dedup"}
    result: dict[str, Any] = {key: {"witness": rich_fixture(), "wrong_sql": wrong[label],
        "outcome": "UNEXECUTED_RULE_SPEC"} for key, label in keys.items()}
    for table, columns in SCHEMA.items():
        for column, kind in columns.items():
            tables = rich_fixture()
            tables[table][0][column] = True if kind == "INTEGER" else 42
            result[f"raw:{table}.{column}"] = {"witness": tables,
                "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    for key, table, column, value in (("integer", "requests", "item_id", "10"),
                                    ("varchar", "translations", "title", False),
                                    ("nullable", "requests", "request_id", None)):
        tables = rich_fixture()
        tables[table][0][column] = value
        result[key] = {"witness": tables, "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    tables = rich_fixture()
    tables["requests"][0]["extra"] = 1
    result["exact_schema"] = {"witness": tables, "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    return result


def schema_checks(task: Any, table: str, column: str) -> dict[str, Any]:
    kind = SCHEMA[table][column]
    nullable = (table, column) != ("requests", "request_id")
    invalid = ([True, False, "10", 1.5, -2147483649, 2147483648] if kind == "INTEGER"
               else [42, True, 1.5, [], {}]) + ([] if nullable else [None])
    valid = ([-2147483648, -1, 0, 2147483647] if kind == "INTEGER"
             else ["", "EN", "en", "é", " en "]) + ([None] if nullable else [])
    rejections = []
    conformances = []
    for value in invalid:
        tables = rich_fixture()
        tables[table][0][column] = value
        try:
            validate_rows(tables)
        except ValueError as exc:
            rejections.append({"value": value, "reason": str(exc), "tables": tables})
        else:
            raise ValueError("raw schema probe was not rejected")
    for value in valid:
        tables = rich_fixture()
        tables[table][0][column] = value
        validate_rows(tables)
        conformances.append({"value": value, "tables": tables})
    return {"declared_type": kind, "domain_reason": "Raw declared type/nullability only; no additional restrictions.",
            "raw_rejections": rejections, "raw_conformance": conformances}


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(sql, rich_fixture()) for sql in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    baseline = {"requests": [request(), request(2, None, None)], "translations": [translation()]}
    wrong = failures(reference)
    return [("LANGUAGE_ORPHAN", wrong["full"], deepcopy(baseline)),
            ("LANGUAGE_NULL_KEYS", wrong["null_both_equal"], deepcopy(baseline))]


def transform(tables: Tables, relation_id: str) -> tuple[Tables | None, str]:
    validate_rows(tables)
    after = deepcopy(tables)
    if relation_id == "LANGUAGE_ORPHAN":
        used = {row["item_id"] for row in tables["requests"]}
        item = next((i for i in range(len(used) + 1) if i not in used), None)
        if item is None:
            return None, "no unused signed32 item"
        after["translations"].append(translation(item, "orphan", "added orphan"))
    elif relation_id == "LANGUAGE_NULL_KEYS":
        if not any(row["item_id"] is None and row["language"] is None for row in tables["requests"]):
            return None, "requires a request with both NULL key components"
        after["translations"].append(translation(None, None, "must not match"))
    else:
        return None, "unsupported relation"
    return after, "valid output-invariant translation insertion"


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"language-titles:1:{seed}:{index}")
    if index % 13 == 12:
        return {"requests": [], "translations": []}
    tables = rich_fixture()
    for number in range(rng.randint(2, 12)):
        item = 1000 + number
        language = f"frame:{seed}:{index}:{number}:{rng.choice(['é', '', 'EN', 'en'])}"
        tables["requests"].extend([request(rng.randrange(-2147483648, 2147483648), item, language)
                                   for _ in range(rng.randint(1, 3))])
        tables["translations"].extend([translation(item, language, rng.choice([None, "", "Title", language]))
                                       for _ in range(rng.randint(0, 4))])
    rng.shuffle(tables["requests"])
    rng.shuffle(tables["translations"])
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    validate_rows(tables)
    found: set[str] = set()
    requests, translations = tables["requests"], tables["translations"]
    if not requests and not translations:
        found.add("empty_input")
    left_counts = Counter(tuple(row[key] for key in SCHEMA["requests"]) for row in requests)
    right_counts = Counter(tuple(row[key] for key in SCHEMA["translations"]) for row in translations)
    if max(left_counts.values(), default=0) > 1:
        found.add("duplicate_requests")
    if max(right_counts.values(), default=0) > 1:
        found.add("duplicate_translations")
    for row in requests:
        matches = [right for right in translations if _matches(row, right)]
        found.add("matched" if matches else "unmatched")
        if row["item_id"] is None:
            found.add("null_item")
        if row["language"] is None:
            found.add("null_language")
        if row["item_id"] is None and row["language"] is None:
            found.add("both_null")
        if any(right["title"] is None for right in matches):
            found.add("matched_null_title")
        if any(right["title"] == "" for right in matches):
            found.add("empty_title")
        if row["language"] == "" and matches:
            found.add("empty_language")
        if len(matches) > 1:
            found.add("multiple_matches")
        if (left_counts[tuple(row[key] for key in SCHEMA["requests"])] > 1
                and any(right_counts[tuple(t[key] for key in SCHEMA["translations"])] > 1 for t in matches)):
            found.add("duplicate_product")
        for value in (row["request_id"], row["item_id"]):
            if value == -2147483648:
                found.add("min_integer")
            if value == 2147483647:
                found.add("max_integer")
            if value is not None and value < 0:
                found.add("negative_integer")
        for right in translations:
            left_lang, right_lang = row["language"], right["language"]
            if (row["item_id"] is not None and row["item_id"] == right["item_id"]
                    and isinstance(left_lang, str) and isinstance(right_lang, str) and left_lang != right_lang):
                if left_lang.lower() == right_lang.lower():
                    found.add("case_sensitive")
                if left_lang.strip() == right_lang.strip():
                    found.add("literal_language")
    if any(not any(_matches(left, right) for left in requests) for right in translations):
        found.add("orphan")
    return "language-titles-observed-v1", BEHAVIORS, found
