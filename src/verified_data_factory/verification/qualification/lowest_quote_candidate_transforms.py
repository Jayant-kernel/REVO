"""Bounded AST recognition and actual-candidate mutations for explicit quote shapes.

Aliases/formatting may vary; literals, predicates and structure may not. Unsupported
shapes abstain. Wrappers operate on the candidate output, never on reference SQL.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import duckdb

from .alternative_candidate_transforms import (
    _column,
    _expression,
    _first,
    _nodes,
    _render,
    _replace,
)
from .lowest_quote_profile import REFERENCE, alternatives
from .sla_candidate_transforms import parse


def prototypes() -> list[str]:
    return [*alternatives(REFERENCE),
        ("SELECT part,supplier,price_cents FROM (SELECT *,ROW_NUMBER() OVER "
          "(PARTITION BY part ORDER BY price_cents,supplier) AS rn FROM quotes "
          "WHERE price_cents IS NOT NULL) ranked WHERE rn=1 ORDER BY part"),
        ("SELECT part,supplier,MIN(price_cents) OVER (PARTITION BY part) AS price_cents "
         "FROM quotes WHERE price_cents IS NOT NULL QUALIFY ROW_NUMBER() OVER "
         "(PARTITION BY part ORDER BY price_cents ASC,supplier ASC)=1 ORDER BY part ASC")]


def _signature(tree: dict[str, Any]) -> Any:
    bindings: dict[str, str] = {}
    for node in _nodes(tree):
        if node.get("type") in ("BASE_TABLE", "SUBQUERY") and node.get("alias"):
            alias = node["alias"].casefold()
            bindings.setdefault(alias, f"binding{len(bindings)}")
        if node.get("type") == "WINDOW_ROW_NUMBER" and node.get("alias"):
            bindings[node["alias"].casefold()] = "window_rank"

    def normalize(value: Any) -> Any:
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: normalize(item) for key, item in value.items() if key != "query_location"}
        for key in ("alias", "table_name", "function_name"):
            if isinstance(result.get(key), str):
                text = result[key].casefold()
                result[key] = bindings.get(text, text)
        if result.get("class") == "COLUMN_REF":
            result["column_names"] = [bindings.get(name.casefold(), name.casefold()) for name in result["column_names"]]
        if result.get("type") == "ORDER_DEFAULT" and "expression" in result:
            result["type"] = "ASCENDING"
        return result

    return normalize(tree)


def candidate_proofs(sql: str, reference: str, public: dict[str, Any]) -> dict[str, Any] | None:
    con = duckdb.connect()
    try:
        tree = parse(sql, con)
        if _signature(tree) not in [_signature(parse(query, con)) for query in [reference, *prototypes()]]:
            return None
        result = {}
        window_shape = any(node.get("type") == "WINDOW_ROW_NUMBER" for node in _nodes(tree))
        exists_shape = any(node.get("type") == "SUBQUERY" and node.get("subquery_type") == "EXISTS" for node in _nodes(tree))
        for key, spec in public.items():
            if "wrong_sql" not in spec:
                result[key] = deepcopy(spec)
                continue
            changed = deepcopy(tree)
            root = changed["statements"][0]["node"]
            wrapper = ""
            if key in {"objective", "winner_rule", "tie_break", "binary_text"}:
                column = "price_cents" if key in {"objective", "winner_rule"} else "supplier"
                if window_shape:
                    window = _first(changed, lambda n: n.get("type") == "WINDOW_ROW_NUMBER")
                    order = next(o for o in window["orders"] if _column(o["expression"], column))
                    if key == "binary_text":
                        order["expression"] = _expression(con, "LOWER(" + ".".join(order["expression"]["column_names"]) + ")")
                    else:
                        order["type"] = "DESCENDING"
                elif exists_shape:
                    comparison = _first(changed, lambda n, column=column: n.get("type") == "COMPARE_LESSTHAN" and _column(n.get("left", {}), column))
                    if key == "binary_text":
                        for side in ("left", "right"):
                            comparison[side] = _expression(con, "LOWER(" + ".".join(comparison[side]["column_names"]) + ")")
                    else:
                        comparison["type"] = "COMPARE_GREATERTHAN"
                else:
                    minimum = _first(changed, lambda n, column=column: n.get("function_name") == "min" and _column(n["children"][0], column))
                    if key == "binary_text":
                        minimum["children"][0] = _expression(con, "LOWER(" + ".".join(minimum["children"][0]["column_names"]) + ")")
                    else:
                        minimum["function_name"] = "max"
            elif key == "duplicate_key":
                if window_shape:
                    _first(changed, lambda n: n.get("type") == "WINDOW_ROW_NUMBER")["partitions"] = []
                else:
                    # The inner MIN join can stay equivalent after dropping its key.
                    scope = changed if exists_shape else root["from_table"]["condition"]
                    _replace(_first(scope, lambda n: n.get("type") == "COMPARE_EQUAL" and _column(n.get("left", {}), "part")), _expression(con, "TRUE"))
            elif key == "exact_repeats":
                if window_shape:
                    window = _first(changed, lambda n: n.get("type") == "WINDOW_ROW_NUMBER")
                    window["type"], window["function_name"] = "WINDOW_RANK", "rank"
                else:
                    root["modifiers"] = [m for m in root["modifiers"] if m["type"] != "DISTINCT_MODIFIER"]
            elif key == "order_by":
                ordering = next(m for m in root["modifiers"] if m["type"] == "ORDER_MODIFIER")
                ordering["orders"][0]["type"] = "DESCENDING"
            elif key == "output_columns":
                replacement = deepcopy(root["select_list"][0])
                replacement["alias"] = "supplier"
                root["select_list"][1] = replacement
            elif key == "output_types":
                wrapper = "SELECT part,supplier,CAST(price_cents AS VARCHAR) AS price_cents FROM ({sql}) candidate ORDER BY part"
            elif key in {"zero_values", "empty_text", "no_scope", "timestamp_tie_policy"}:
                predicate = "price_cents > 0" if key == "zero_values" else "part <> ''"
                wrapper = "SELECT * FROM ({sql}) candidate WHERE " + predicate + " ORDER BY part"
            elif key == "null_prices":
                # Inject unknown row images from the candidate's actual base table.
                table = _first(changed, lambda n: n.get("type") == "BASE_TABLE" and n.get("table_name", "").casefold() == "quotes")["table_name"]
                wrapper = "SELECT * FROM ({sql}) candidate UNION ALL SELECT part,supplier,price_cents FROM " + table + " WHERE price_cents IS NULL ORDER BY part"
            elif key == "empty_result":
                wrapper = "SELECT * FROM ({sql}) candidate UNION ALL SELECT CAST('' AS VARCHAR),CAST('' AS VARCHAR),CAST(0 AS INTEGER) ORDER BY part"
            else:
                return None
            actual = _render(con, changed)
            mutant = wrapper.format(sql=actual) if wrapper else actual
            result[key] = {**deepcopy(spec), "wrong_sql": mutant,
                           "outcome": "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"}
        return result
    except (ValueError, KeyError, TypeError, IndexError, StopIteration, duckdb.Error):
        return None
    finally:
        con.close()
