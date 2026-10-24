"""Executed candidate-derived transforms for three source-bound alternative shapes."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import duckdb

from .sla_candidate_transforms import parse, signature


def _nodes(value: Any) -> Any:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from _nodes(item)


def _column(node: dict[str, Any], name: str) -> bool:
    return node.get("class") == "COLUMN_REF" and node.get("column_names", [""])[-1].casefold() == name


def _first(tree: Any, predicate: Any) -> dict[str, Any]:
    return next(node for node in _nodes(tree) if predicate(node))


def _replace(node: dict[str, Any], value: dict[str, Any]) -> None:
    node.clear()
    node.update(deepcopy(value))


def _expression(connection: Any, sql: str) -> dict[str, Any]:
    expression: dict[str, Any] = parse("SELECT "+sql, connection)["statements"][0]["node"]["select_list"][0]
    return expression


def _render(connection: Any, tree: dict[str, Any]) -> str:
    row = connection.execute("SELECT json_deserialize_sql(?)", [json.dumps(tree)]).fetchone()
    if row is None or not isinstance(row[0], str):
        raise ValueError("AST serialization unavailable")
    return str(row[0]).rstrip("; ")


def _comparison(tree: Any, column: str) -> dict[str, Any]:
    return _first(tree, lambda node: node.get("class") == "COMPARISON" and _column(node.get("left", {}), column))


def candidate_proofs(contract: str, version: int, sql: str, reference: str,
                     public: dict[str, Any]) -> dict[str, Any] | None:
    pair = contract, version
    if pair == ("sql.cte.order_line_reconciliation", 1):
        from .reconciliation_profile import alternatives

        prototype = alternatives(reference)[1]
        family = "reconciliation"
    elif pair == ("sql.joins.saas_paid_invoices", 1):
        from .paid_invoices_profile import alternatives

        prototype = alternatives(reference)[2]
        family = "paid"
    elif pair == ("sql.temporal.clinic_weekly_visits", 1):
        from .weekly_visits_profile import alternatives

        prototype = alternatives(reference)[1]
        family = "weekly"
    else:
        return None
    connection = duckdb.connect()
    try:
        tree = parse(sql, connection)
        if signature(tree) != signature(parse(prototype, connection)):
            return None
        true = _expression(connection, "TRUE")
        result = {}
        for key, specification in public.items():
            if "wrong_sql" not in specification:
                result[key] = deepcopy(specification)
                continue
            changed = deepcopy(tree)
            root = changed["statements"][0]["node"]
            suffix = ""
            if family == "reconciliation":
                if key == "objective":
                    _comparison(changed, "header_total_cents")["type"] = "COMPARE_EQUAL"
                elif key == "product":
                    _first(changed, lambda node: node.get("function_name") == "*")["function_name"] = "+"
                elif key == "year":
                    _replace(_first(changed, lambda node: node.get("class") == "BETWEEN"), true)
                elif key == "status_filter":
                    _replace(_comparison(changed, "order_status"), true)
                elif key in {"top_tie_break", "order_by"}:
                    root["modifiers"][0]["orders"][0]["type"] = "DESCENDING"
                elif key == "unmatched_behavior":
                    coalesce = _first(changed, lambda node: node.get("type") == "OPERATOR_COALESCE")
                    coalesce["children"][1] = _expression(connection, "1")
                elif key == "output_columns":
                    root["select_list"][0] = _expression(connection, "CAST(order_id AS VARCHAR) AS order_id")
                elif key == "bag":
                    root["modifiers"].insert(0, {"type": "DISTINCT_MODIFIER", "distinct_on_targets": []})
                elif key == "line_bag":
                    _first(changed, lambda node: node.get("function_name") == "sum")["distinct"] = True
                else:
                    return None
            elif family == "paid":
                if key == "objective":
                    _replace(_comparison(changed, "account_id"), true)
                elif key in {"status_filter", "account_status_filter"}:
                    _replace(_comparison(changed, "invoice_status" if key == "status_filter" else "account_status"), true)
                elif key == "year":
                    _replace(_first(changed, lambda node: node.get("class") == "BETWEEN"), true)
                elif key == "join_type":
                    _first(changed, lambda node: node.get("type") == "JOIN")["join_type"] = "LEFT"
                elif key == "unmatched_behavior":
                    # Add the otherwise omitted account-row image to the actual query.
                    suffix = (" UNION ALL SELECT CAST(NULL AS INTEGER) AS invoice_id,a.account_name,"
                              "CAST(NULL AS INTEGER) AS amount_cents FROM accounts a WHERE account_status='active' "
                              "AND NOT EXISTS (SELECT 1 FROM invoices i WHERE i.account_id=a.account_id) ORDER BY invoice_id")
                elif key == "output_columns":
                    root["select_list"][0] = _expression(connection, "CAST(i.invoice_id AS VARCHAR) AS invoice_id")
                elif key == "order_by":
                    root["modifiers"][0]["orders"][0]["type"] = "DESCENDING"
                elif key == "multiplicity":
                    root["modifiers"].insert(0, {"type": "DISTINCT_MODIFIER", "distinct_on_targets": []})
                elif key == "minor_units":
                    root["select_list"][2] = _expression(connection, "i.amount_cents/100.0 AS amount_cents")
                else:
                    return None
            else:
                if key == "objective":
                    _replace(_first(changed, lambda node: node.get("function_name") == "count_star"),
                             _expression(connection, "COUNT(DISTINCT week_start) AS visit_count"))
                elif key in {"year", "window_start", "window_end", "boundary_policy"}:
                    comparisons = [node for node in _nodes(changed) if node.get("class") == "COMPARISON"
                                   and _column(node.get("left", {}), "started_at")]
                    selected = comparisons if key == "year" else [node for node in comparisons if node["type"] == (
                        "COMPARE_LESSTHAN" if key == "window_end" else "COMPARE_GREATERTHANOREQUALTO")]
                    for node in selected:
                        if key == "boundary_policy":
                            node["type"] = "COMPARE_GREATERTHAN"
                        else:
                            _replace(node, true)
                elif key in {"month_definition", "prior_year_monday"}:
                    week = _first(changed, lambda node: node.get("alias", "").casefold() == "week_start")
                    if key == "month_definition":
                        _replace(week, _expression(connection, "CAST(day AS DATE) AS week_start"))
                    else:
                        greatest = _expression(connection, "GREATEST(day,DATE '2025-01-01') AS week_start")
                        greatest["children"][0] = deepcopy(week)
                        greatest["children"][0]["alias"] = ""
                        _replace(week, greatest)
                elif key == "output_columns":
                    root["select_list"][1] = _expression(connection, "CAST(week_start AS VARCHAR) AS week_start")
                elif key == "order_by":
                    root["modifiers"][0]["orders"][1]["type"] = "DESCENDING"
                elif key in {"completed", "omit_empty"}:
                    _replace(_comparison(changed, "status"), true)
                elif key == "null_start":
                    suffix = (" UNION ALL SELECT clinic,CAST(NULL AS DATE) AS week_start,COUNT(*) AS visit_count "
                              "FROM visits WHERE status='completed' AND started_at IS NULL GROUP BY clinic "
                              "ORDER BY clinic,week_start")
                else:
                    return None
            wrong = _render(connection, changed)
            if suffix:
                wrong = "WITH __candidate_body AS ("+wrong+") SELECT * FROM __candidate_body"+suffix
            result[key] = {**deepcopy(specification), "wrong_sql": wrong,
                           "outcome": "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"}
        return result
    except (ValueError, KeyError, TypeError, IndexError, StopIteration, duckdb.Error):
        return None
    finally:
        connection.close()
