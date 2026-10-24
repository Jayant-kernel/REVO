"""Bounded nested LAG@1 transforms; actual candidate nodes retain rule attribution."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import duckdb

from .alternative_candidate_transforms import _column, _expression, _first, _render, _replace
from .grade_candidate_transforms import _signature
from .sla_candidate_transforms import parse


def prototypes() -> list[str]:
    return ["SELECT play_id,previous_play_id FROM (SELECT "
            f"{alias}.play_id,LAG({alias}.play_id,1) OVER (PARTITION BY {alias}.viewer_id,{alias}.title_id "
            f"ORDER BY {alias}.played_at,{alias}.play_id) AS previous_play_id FROM plays {alias} "
            f"WHERE {alias}.status='completed' AND EXTRACT(YEAR FROM {alias}.played_at)=2025) ORDER BY play_id"
            for alias in ("p1", "p")]


def candidate_proofs(sql: str, reference: str, public: dict[str, Any]) -> dict[str, Any] | None:
    connection = duckdb.connect()
    try:
        tree = parse(sql, connection)
        allowed = [_signature(parse(prototype, connection)) for prototype in [reference, *prototypes()]]
        if _signature(tree) not in allowed:
            return None
        result = {}
        for key, specification in public.items():
            changed = deepcopy(tree)
            root = changed["statements"][0]["node"]
            window = _first(changed, lambda node: node.get("type") == "WINDOW_LAG")
            if key == "objective":
                window["type"], window["function_name"] = "WINDOW_LEAD", "lead"
            elif key == "year":
                predicate = _first(changed, lambda node: node.get("class") == "COMPARISON"
                                   and node.get("left", {}).get("class") == "FUNCTION")
                _replace(predicate, _expression(connection, "TRUE"))
            elif key == "status_filter":
                predicate = _first(changed, lambda node: node.get("class") == "COMPARISON"
                                   and _column(node.get("left", {}), "status"))
                _replace(predicate, _expression(connection, "TRUE"))
            elif key == "partition_by":
                window["partitions"] = window["partitions"][:1]
            elif key == "title":
                window["partitions"] = window["partitions"][1:]
            elif key == "running_order":
                window["orders"] = window["orders"][1:]
            elif key == "tie_policy":
                window["orders"][1]["type"] = "DESCENDING"
            elif key == "null_ordering":
                window["default_expr"] = _expression(connection, "0")
            elif key == "output_columns":
                root["select_list"][0] = _expression(connection, "CAST(play_id AS VARCHAR) AS play_id")
            elif key == "rank_order":
                root["select_list"].append(_expression(connection, "CAST(1 AS BIGINT) AS rank"))
            elif key == "order_by":
                ordering = next(modifier for modifier in root["modifiers"] if modifier["type"] == "ORDER_MODIFIER")
                ordering["orders"][0]["type"] = "DESCENDING"
            elif key == "bag":
                table = _first(changed, lambda node: node.get("type") == "BASE_TABLE")
                alias = table.get("alias") or "plays"
                distinct = parse(f"SELECT * FROM (SELECT DISTINCT * FROM plays) {alias}", connection)
                _replace(table, distinct["statements"][0]["node"]["from_table"])
            else:
                return None
            result[key] = {**deepcopy(specification), "wrong_sql": _render(connection, changed),
                           "outcome": "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"}
        return result
    except (ValueError, KeyError, TypeError, IndexError, StopIteration, duckdb.Error):
        return None
    finally:
        connection.close()
