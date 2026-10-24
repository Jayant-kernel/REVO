"""Bounded direct LEFT JOIN recognition; mutants edit the actual candidate AST.

Lateral/union alternatives remain unsupported for runtime attribution. Recognition
allows binding aliases, AND order and equality operand order, not added predicates.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import duckdb

from .alternative_candidate_transforms import _column, _expression, _render
from .language_titles_profile import REFERENCE
from .sla_candidate_transforms import parse


def _signature(tree: dict[str, Any]) -> Any:
    root = tree["statements"][0]["node"]
    join = root["from_table"]
    bindings = {}
    for side, name in (("left", "requests"), ("right", "translations")):
        table = join[side]
        bindings[(table.get("alias") or table["table_name"]).casefold()] = name

    def normalize(value: Any) -> Any:
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: normalize(item) for key, item in value.items() if key != "query_location"}
        if result.get("type") == "BASE_TABLE":
            result["alias"] = ""
            result["table_name"] = result["table_name"].casefold()
        if result.get("class") == "COLUMN_REF":
            result["column_names"] = [bindings.get(name.casefold(), name.casefold())
                                      for name in result["column_names"]]
            # Only exact output-name aliases are equivalent to implicit output names.
            if result.get("alias", "").casefold() == result["column_names"][-1]:
                result["alias"] = ""
        if result.get("type") == "CONJUNCTION_AND":
            result["children"] = sorted(result["children"], key=lambda item: json.dumps(item, sort_keys=True))
        if result.get("type") == "COMPARE_EQUAL":
            result["left"], result["right"] = sorted([result["left"], result["right"]],
                                                    key=lambda item: json.dumps(item, sort_keys=True))
        return result
    return normalize(tree)


def candidate_proofs(sql: str, reference: str,
                     public: dict[str, Any]) -> dict[str, Any] | None:
    con = duckdb.connect(config={"enable_external_access": "false"})
    try:
        tree = parse(sql, con)
        if _signature(tree) != _signature(parse(REFERENCE, con)):
            return None
        result = {}
        for proof_key, spec in public.items():
            if "wrong_sql" not in spec:
                result[proof_key] = deepcopy(spec)
                continue
            changed = deepcopy(tree)
            root = changed["statements"][0]["node"]
            join = root["from_table"]
            left = join["left"].get("alias") or join["left"]["table_name"]
            right = join["right"].get("alias") or join["right"]["table_name"]
            comparisons = join["condition"]["children"]
            wrapper = ""
            key = {"duplicates": "bag", "null_values": "null_semantics",
                   "missing_relationships": "unmatched_behavior",
                   "multiple_matching_rows": "translation_bag"}.get(proof_key, proof_key)
            if key in {"objective", "composite_key", "no_fallback"}:
                join["condition"] = next(term for term in comparisons if _column(term["left"], "item_id"))
            elif key in {"join_type", "unmatched_behavior"}:
                join["join_type"] = "INNER"
            elif key == "orphan":
                join["join_type"] = "FULL"
            elif key == "null_semantics":
                for term in comparisons:
                    term["type"] = "COMPARE_NOT_DISTINCT_FROM"
            elif key in {"case_sensitive", "text"}:
                term = next(term for term in comparisons if _column(term["left"], "language"))
                function = "LOWER" if key == "case_sensitive" else "TRIM"
                for side in ("left", "right"):
                    names = term[side]["column_names"]
                    term[side] = _expression(con, function + "(" + ".".join('"'+n+'"' for n in names) + ")")
            elif key in {"request_bag", "translation_bag"}:
                side = "left" if key == "request_bag" else "right"
                table = join[side]
                alias = table.get("alias") or table["table_name"]
                subquery = parse('SELECT * FROM (SELECT DISTINCT * FROM "'+table["table_name"]+'") "'+alias+'"', con)
                join[side] = subquery["statements"][0]["node"]["from_table"]
            elif key == "output_columns":
                root["select_list"][0] = _expression(con, f'"{left}".item_id AS request_id')
            elif key == "output_types":
                root["select_list"][0] = _expression(con, f'CAST("{left}".request_id AS VARCHAR) AS request_id')
            elif key == "null_title":
                root["select_list"][1] = _expression(con, f'COALESCE("{right}".title,\'fallback\') AS title')
            elif key in {"year", "input_domain_rules"}:
                wrapper = "SELECT * FROM ({sql}) actual_candidate WHERE request_id >= 0"
            elif key in {"status_filter", "no_filter", "empty_text"}:
                predicate = "= 'en'" if key != "empty_text" else "<> ''"
                root["where_clause"] = _expression(con, f'"{left}".language {predicate}')
            elif key == "bag":
                wrapper = "SELECT DISTINCT * FROM ({sql}) actual_candidate"
            elif key in {"nonunique", "no_winner"}:
                root["qualify"] = _expression(con, f'ROW_NUMBER() OVER (PARTITION BY "{left}".request_id ORDER BY "{right}".title)=1')
            else:
                return None
            mutant = _render(con, changed)
            result[proof_key] = {
                           **deepcopy(spec), "wrong_sql": wrapper.format(sql=mutant) if wrapper else mutant,
                           "outcome": "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"}
        return result
    except (ValueError, KeyError, TypeError, IndexError, StopIteration, duckdb.Error):
        return None
    finally:
        con.close()
