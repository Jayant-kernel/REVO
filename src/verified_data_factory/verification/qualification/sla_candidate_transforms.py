"""Bounded SLA@1 AST mutations of actual candidates, not canonical-proof aliases.

Only pure, single-table grouped COUNT/SUM-CASE or COUNT-FILTER shapes and exact
2025 calendar predicates are supported. Every derived mutant still executes on
its attributed public fixture through the supplied sandbox backend.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import duckdb


def parse(sql: str, connection: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(connection.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()[0])
    if not isinstance(data, dict) or data.get("error") or len(data.get("statements", [])) != 1:
        raise ValueError("unsupported SLA statement")
    return data


def signature(value: Any) -> Any:
    """Ignore source locations/output aliases, not literals, types or query structure."""
    if isinstance(value, list):
        return [signature(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: signature(item) for key, item in value.items() if key not in {"query_location", "alias"}}
    if result.get("class") == "COLUMN_REF":
        result["column_names"] = [name.casefold() for name in result["column_names"]]
    if result.get("type") == "BASE_TABLE":
        result["table_name"] = result["table_name"].casefold()
    if result.get("type") == "CONJUNCTION_AND":
        result["children"] = sorted(result["children"], key=lambda item: json.dumps(item, sort_keys=True))
    if result.get("type") == "ORDER_DEFAULT" and "expression" in result:
        result["type"] = "ASCENDING"
    return result


def _column(node: dict[str, Any], name: str) -> bool:
    return node.get("class") == "COLUMN_REF" and [value.casefold() for value in node["column_names"]] == [name]


def candidate_proofs(sql: str, public: dict[str, Any]) -> dict[str, Any] | None:
    connection = duckdb.connect()
    try:
        tree = parse(sql, connection)
        select = tree["statements"][0]["node"]["select_list"]
        if (len(select) != 3 or select[0].get("alias", "").casefold() not in {"", "warehouse"}
                or select[1].get("alias", "").casefold() != "delivered_fulfillments"
                or select[2].get("alias", "").casefold() != "on_time_fulfillments"):
            return None
        predicates = ("EXTRACT(YEAR FROM shipped_at)=2025",
                      "shipped_at >= DATE '2025-01-01' AND shipped_at < DATE '2026-01-01'")
        measures = ("SUM(CASE WHEN delivered_at <= promised_at THEN 1 ELSE 0 END)",
                    "COUNT(*) FILTER (WHERE delivered_at <= promised_at)")
        prototypes = [parse(
            "SELECT warehouse, COUNT(*) AS delivered_fulfillments, "+measure+
            " AS on_time_fulfillments FROM fulfillments WHERE fulfillment_status='delivered' "
            "AND delivered_at IS NOT NULL AND "+predicate+
            " GROUP BY warehouse ORDER BY warehouse ASC", connection)
            for predicate in predicates for measure in measures]
        if signature(tree) not in [signature(item) for item in prototypes]:
            return None
        true = parse("SELECT TRUE", connection)["statements"][0]["node"]["select_list"][0]
        distinct_count = parse("SELECT COUNT(DISTINCT warehouse)", connection)["statements"][0]["node"]["select_list"][0]
        minimum = parse("SELECT MIN(warehouse) AS warehouse", connection)["statements"][0]["node"]["select_list"][0]
        mutants = {}
        for key, specification in public.items():
            changed = deepcopy(tree)
            node = changed["statements"][0]["node"]
            terms = node["where_clause"]["children"]
            if key in {"status_filter", "empty_group_behavior", "null_handling", "year"}:
                selected = []
                for index, term in enumerate(terms):
                    status_term = key in {"status_filter", "empty_group_behavior"} and _column(term.get("left", {}), "fulfillment_status")
                    null_term = key == "null_handling" and term.get("type") == "OPERATOR_IS_NOT_NULL"
                    year_term = key == "year" and (
                        _column(term.get("left", {}), "shipped_at") or
                        term.get("type") == "COMPARE_EQUAL" and term.get("left", {}).get("function_name") in {"extract", "date_part"}
                    )
                    if status_term or null_term or year_term:
                        selected.append(index)
                if not selected:
                    return None
                for index in selected:
                    terms[index] = deepcopy(true)
            elif key in {"objective", "deadline_inclusive"}:
                measure = node["select_list"][2]
                condition = (measure["children"][0]["case_checks"][0]["when_expr"]
                             if measure["function_name"] == "sum" else measure["filter"])
                condition["type"] = "COMPARE_GREATERTHAN" if key == "objective" else "COMPARE_LESSTHAN"
            elif key == "group_by":
                node["select_list"][0] = deepcopy(minimum)
                node["group_expressions"], node["group_sets"] = [], []
            elif key == "count_semantics":
                alias = node["select_list"][1]["alias"]
                node["select_list"][1] = deepcopy(distinct_count)
                node["select_list"][1]["alias"] = alias
            elif key == "output_columns":
                node["select_list"][1]["alias"] = "wrong_count"
            elif key == "order_by":
                node["modifiers"][0]["orders"][0]["type"] = "DESCENDING"
            else:
                return None
            serialized = connection.execute("SELECT json_deserialize_sql(?)", [json.dumps(changed)]).fetchone()
            if serialized is None or not isinstance(serialized[0], str):
                return None
            wrong = serialized[0]
            if wrong == sql:
                return None
            mutants[key] = {**deepcopy(specification), "wrong_sql": wrong,
                            "outcome": "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"}
        return mutants
    except (ValueError, KeyError, TypeError, IndexError, duckdb.Error):
        # Unsupported parse/shape never receives public coverage.
        return None
    finally:
        connection.close()
