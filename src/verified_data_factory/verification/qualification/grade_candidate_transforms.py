"""Bounded grade@2 row-number AST transforms of actual candidate nodes."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import duckdb

from .alternative_candidate_transforms import _column, _expression, _first, _render, _replace
from .sla_candidate_transforms import parse

COLUMNS = "student_id,course_id,grade,recorded_at,revision_id"
WINDOW = "ROW_NUMBER() OVER (PARTITION BY student_id,course_id ORDER BY recorded_at DESC,revision_id DESC) AS rn"


def prototypes() -> list[str]:
    result = [f"SELECT {COLUMNS} FROM (SELECT {projection},{WINDOW} FROM grade_revisions "
              f"WHERE revision_status='valid'){alias} WHERE rn=1 ORDER BY student_id,course_id"
              for projection in ("*", COLUMNS) for alias in ("", " AS ranked")]
    result.extend(f"SELECT {COLUMNS} FROM (SELECT *,{WINDOW} FROM (SELECT *,CASE WHEN "
                  "revision_status='valid' THEN 1 ELSE 0 END AS is_valid FROM grade_revisions) "
                  f"WHERE is_valid=1){alias} WHERE rn=1 ORDER BY student_id,course_id"
                  for alias in ("", " AS ranked"))
    return result


def _signature(value: Any) -> Any:
    """Normalize presentation only; retain aliases, constants, types and structure."""
    if isinstance(value, list):
        return [_signature(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _signature(item) for key, item in value.items() if key != "query_location"}
    for key in ("alias", "table_name", "function_name"):
        if isinstance(result.get(key), str):
            result[key] = result[key].casefold()
    if result.get("class") == "COLUMN_REF":
        result["column_names"] = [name.casefold() for name in result["column_names"]]
    if result.get("type") == "ORDER_DEFAULT" and "expression" in result:
        result["type"] = "ASCENDING"
    return result


def candidate_proofs(sql: str, reference: str, public: dict[str, Any]) -> dict[str, Any] | None:
    connection = duckdb.connect()
    try:
        tree = parse(sql, connection)
        allowed = [_signature(parse(prototype, connection)) for prototype in [reference, *prototypes()]]
        if _signature(tree) not in allowed:
            return None
        result = {}
        for key, specification in public.items():
            if "wrong_sql" not in specification:
                result[key] = deepcopy(specification)
                continue
            changed = deepcopy(tree)
            root = changed["statements"][0]["node"]
            window = _first(changed, lambda node: node.get("type") == "WINDOW_ROW_NUMBER")
            if key in {"objective", "canceled_policy", "no_valid_policy"}:
                status = _first(changed, lambda node: node.get("class") == "COMPARISON"
                                and _column(node.get("left", {}), "revision_status"))
                if key == "no_valid_policy":
                    status["right"]["value"]["value"] = "cancelled"
                else:
                    _replace(status, _expression(connection, "TRUE"))
            elif key == "duplicate_key":
                window["partitions"] = window["partitions"][:1]
            elif key == "winner_rule":
                window["orders"][0]["type"] = "ASCENDING"
            elif key in {"tie_break", "timestamp_tie_policy"}:
                window["orders"][1]["type"] = "ASCENDING"
            elif key == "exact_repeats":
                window["type"], window["function_name"] = "WINDOW_RANK", "rank"
            elif key == "output_columns":
                root["select_list"][4] = _expression(connection, "CAST(revision_id AS VARCHAR) AS revision_id")
            elif key == "order_by":
                ordering = next(modifier for modifier in root["modifiers"] if modifier["type"] == "ORDER_MODIFIER")
                ordering["orders"][1]["type"] = "DESCENDING"
            else:
                return None
            result[key] = {**deepcopy(specification), "wrong_sql": _render(connection, changed),
                           "outcome": "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"}
        return result
    except (ValueError, KeyError, TypeError, IndexError, StopIteration, duckdb.Error):
        return None
    finally:
        connection.close()
