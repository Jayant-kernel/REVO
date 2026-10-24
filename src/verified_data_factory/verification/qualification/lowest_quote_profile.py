"""Explicit lowest-quote@1 domain, SQL-free selection and executable witnesses."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from random import Random
from typing import Any

from ..models import ExpectedResult, OrderSpec

CONTRACT = "sql.dedup.lowest_quote"
Tables = dict[str, list[dict[str, Any]]]
REFERENCE = ("SELECT part, supplier, price_cents FROM quotes WHERE price_cents IS NOT NULL "
             "QUALIFY ROW_NUMBER() OVER (PARTITION BY part ORDER BY price_cents ASC, supplier ASC) = 1 "
             "ORDER BY part ASC")
BEHAVIORS = ("known", "null_price", "price_tie", "winning_repeat", "all_null_part",
             "multiple_parts", "binary_text", "empty_text", "zero", "max_integer", "empty_input")


def quote(part: str = "p", supplier: str = "s", price: int | None = 10) -> dict[str, Any]:
    return {"part": part, "supplier": supplier, "price_cents": price}


def validate_rows(tables: Mapping[str, list[dict[str, Any]]], *, allow_text_null: bool = False) -> None:
    if set(tables) != {"quotes"}:
        raise ValueError("lowest_quote requires exactly quotes")
    for row in tables["quotes"]:
        if set(row) != {"part", "supplier", "price_cents"}:
            raise ValueError("quotes requires part, supplier, price_cents")
        for column in ("part", "supplier"):
            value = row[column]
            if allow_text_null and value is None:
                continue  # DDL retains the NOT NULL rejection and its column attribution.
            if type(value) is not str:
                raise ValueError(f"quotes.{column} must be nonnull text (empty text allowed)")
        price = row["price_cents"]
        if price is not None and (type(price) is not int or not 0 <= price <= 2147483647):
            raise ValueError("quotes.price_cents must be NULL or integer cents in [0,2147483647]; no coercion")


def expected(requirements: Mapping[str, Any], tables: Mapping[str, list[dict[str, Any]]]) -> ExpectedResult:
    validate_rows(tables)
    winners: dict[str, tuple[int, str]] = {}
    for row in tables["quotes"]:
        price = row["price_cents"]
        if price is None:
            continue
        candidate = (price, row["supplier"])
        part = row["part"]
        if part not in winners or candidate < winners[part]:
            winners[part] = candidate
    return ExpectedResult(columns=["part", "supplier", "price_cents"],
                          column_types=["VARCHAR", "VARCHAR", "INTEGER"],
                          rows=[[part, winners[part][1], winners[part][0]] for part in sorted(winners)],
                          order=OrderSpec(type="ordered", keys=[("part", "asc")]))


def rich_fixture() -> Tables:
    return {"quotes": [quote("p", "A", 20), quote("p", "z", 10), quote("p", "B", 10),
        quote("p", "B", 10), quote("p", "", None), quote("null", "s", None),
        quote("", "", 0), quote("max", "s", 2147483647), quote("case", "a", 8),
        quote("case", "Z", 8), quote("unicode", "é", 7), quote("unicode", "z", 7),
        quote("p ", " s ", 11), quote("P", "s", 12)]}


def alternatives(reference: str) -> list[str]:
    return [reference,
        ("SELECT DISTINCT q.part,q.supplier,q.price_cents FROM quotes q WHERE q.price_cents IS NOT NULL "
         "AND NOT EXISTS (SELECT 1 FROM quotes b WHERE b.part=q.part AND b.price_cents IS NOT NULL "
         "AND (b.price_cents<q.price_cents OR (b.price_cents=q.price_cents AND b.supplier<q.supplier))) ORDER BY q.part"),
        ("WITH prices AS (SELECT part,MIN(price_cents) AS price_cents FROM quotes GROUP BY part), "
         "suppliers AS (SELECT q.part,q.price_cents,MIN(q.supplier) AS supplier FROM quotes q JOIN prices p "
         "ON q.part=p.part AND q.price_cents=p.price_cents GROUP BY q.part,q.price_cents) "
         "SELECT DISTINCT q.part,q.supplier,q.price_cents FROM quotes q JOIN suppliers s "
         "ON q.part=s.part AND q.price_cents=s.price_cents AND q.supplier=s.supplier ORDER BY q.part")]


def failures(reference: str) -> dict[str, str]:
    return {
        "highest": reference.replace("price_cents ASC", "price_cents DESC"),
        "last_supplier": reference.replace("supplier ASC", "supplier DESC"),
        "supplier_first": reference.replace("price_cents ASC, supplier ASC", "supplier ASC, price_cents ASC"),
        "supplier_partition": reference.replace("PARTITION BY part", "PARTITION BY supplier"),
        "global": reference.replace("PARTITION BY part", ""),
        "part_supplier": reference.replace("PARTITION BY part", "PARTITION BY part, supplier"),
        "part_price": reference.replace("PARTITION BY part", "PARTITION BY part, price_cents"),
        "second": reference.replace(") = 1", ") = 2"),
        "two": reference.replace(") = 1", ") <= 2"),
        "all": reference.replace(") = 1", ") >= 1"),
        "rank": reference.replace("ROW_NUMBER()", "RANK()"),
        "dense_rank": reference.replace("ROW_NUMBER()", "DENSE_RANK()"),
        "unknown": reference.replace("price_cents IS NOT NULL", "TRUE").replace("price_cents ASC", "price_cents ASC NULLS FIRST"),
        "only_unknown": reference.replace("price_cents IS NOT NULL", "price_cents IS NULL"),
        "no_zero": reference.replace("price_cents IS NOT NULL", "price_cents > 0"),
        "no_max": reference.replace("price_cents IS NOT NULL", "price_cents < 2147483647"),
        "no_empty_part": reference.replace("price_cents IS NOT NULL", "price_cents IS NOT NULL AND part <> ''"),
        "no_empty_supplier": reference.replace("price_cents IS NOT NULL", "price_cents IS NOT NULL AND supplier <> ''"),
        "casefold": reference.replace("supplier ASC", "LOWER(supplier) ASC"),
        "reverse": reference.replace("ORDER BY part ASC", "ORDER BY part DESC"),
        "text_price": reference.replace("SELECT part, supplier, price_cents", "SELECT part, supplier, CAST(price_cents AS VARCHAR) AS price_cents"),
        "wrong_supplier": reference.replace("SELECT part, supplier,", "SELECT part, part AS supplier,"),
        "wrong_part": reference.replace("SELECT part, supplier,", "SELECT supplier AS part, supplier,"),
        "truncated": reference + " LIMIT 1",
        "invented_scope": reference.replace("price_cents IS NOT NULL", "price_cents IS NOT NULL AND part='p'"),
    }


def proofs(reference: str) -> dict[str, Any]:
    wrong = failures(reference)
    keys = {"objective": "highest", "duplicate_key": "global", "winner_rule": "highest",
            "tie_break": "last_supplier", "timestamp_tie_policy": "invented_scope",
            "output_columns": "wrong_supplier", "output_types": "text_price", "order_by": "reverse",
            "null_prices": "unknown", "exact_repeats": "rank", "zero_values": "no_zero",
            "empty_text": "no_empty_part", "binary_text": "casefold", "no_scope": "invented_scope"}
    result: dict[str, Any] = {key: {"witness": rich_fixture(), "wrong_sql": wrong[label],
                    "outcome": "UNEXECUTED_RULE_SPEC"} for key, label in keys.items()}
    result["duplicate_key"]["witness"]["quotes"].append(quote("cross-part", "A", 20))
    result["empty_result"] = {"witness": {"quotes": []},
        "wrong_sql": "SELECT * FROM (" + reference + ") candidate UNION ALL SELECT 'invented','supplier',0 ORDER BY part",
        "outcome": "UNEXECUTED_RULE_SPEC"}
    for key, column, value in (("input_domain_rules", "price_cents", -1),
                               ("price_type", "price_cents", "10"),
                               ("part_type", "part", 42), ("supplier_type", "supplier", False)):
        row = quote()
        row[column] = value
        result[key] = {"witness": {"quotes": [row]}, "outcome": "UNEXECUTED_DOMAIN_REJECTION_SPEC"}
    return result


def challenge_specs(reference: str) -> list[tuple[str, Tables]]:
    return [(sql, rich_fixture()) for sql in failures(reference).values()]


def relation_specs(reference: str) -> list[tuple[str, str, Tables]]:
    wrong = failures(reference)
    baseline = {"quotes": [quote("p", "s", 10)]}
    return [("QUOTE_WINNER_REPEAT", wrong["rank"], baseline),
            ("QUOTE_UNKNOWN", wrong["unknown"], baseline)]


def fixture(seed: int, index: int) -> Tables:
    rng = Random(f"lowest-quote:1:{seed}:{index}")
    if index % 13 == 12:
        return {"quotes": []}
    tables = rich_fixture()
    for number in range(rng.randint(2, 16)):
        part = f"frame:{seed}:{index}:{number}:{rng.choice(['A','a','é',' '])}"
        for _ in range(rng.randint(1, 9)):
            tables["quotes"].append(quote(part, rng.choice(["", "A", "a", "Z", "é", " s "]),
                rng.choice([None, 0, 2147483647, rng.randrange(2147483648)])))
    rng.shuffle(tables["quotes"])
    return tables


def observed(tables: Tables) -> tuple[str, tuple[str, ...], set[str]]:
    validate_rows(tables)
    rows = tables["quotes"]
    found: set[str] = set()
    if not rows:
        found.add("empty_input")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row["part"], []).append(row)
        found.add("null_price" if row["price_cents"] is None else "known")
        if row["price_cents"] == 0:
            found.add("zero")
        if row["price_cents"] == 2147483647:
            found.add("max_integer")
        if row["part"] == "" or row["supplier"] == "":
            found.add("empty_text")
    if len(groups) > 1:
        found.add("multiple_parts")
    for group in groups.values():
        known = [row for row in group if row["price_cents"] is not None]
        if not known:
            found.add("all_null_part")
            continue
        minimum = min(row["price_cents"] for row in known)
        tied = [row for row in known if row["price_cents"] == minimum]
        suppliers = {row["supplier"] for row in tied}
        if len(suppliers) > 1:
            found.add("price_tie")
            if min(suppliers) != min(suppliers, key=lambda s: (s.lower(), s)):
                found.add("binary_text")
        winner = min(suppliers)
        if Counter(row["supplier"] for row in tied)[winner] > 1:
            found.add("winning_repeat")
    return "lowest-quote-observed-v1", BEHAVIORS, found
