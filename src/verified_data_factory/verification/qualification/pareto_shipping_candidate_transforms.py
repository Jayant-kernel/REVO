"""Fail-closed recognition and mutations of actual Pareto NOT EXISTS ASTs."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import duckdb

from .alternative_candidate_transforms import _expression, _nodes, _render, _replace
from .pareto_shipping_profile import CONTRACT, REFERENCE, alternatives
from .sla_candidate_transforms import parse


def _observed_forms() -> list[str]:
    # v30 attempt-000/001: qualification differs only in the outer NULL checks.
    # Keep inner qualification intact: unqualified inner names bind locally.
    return [
        "SELECT option_id, lane, cost_cents, duration_minutes FROM options o "
        f"WHERE {prefix}cost_cents IS NOT NULL AND {prefix}duration_minutes IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM options o2 WHERE o2.lane = o.lane "
        "AND o2.cost_cents <= o.cost_cents AND o2.duration_minutes <= o.duration_minutes "
        "AND (o2.cost_cents < o.cost_cents OR o2.duration_minutes < o.duration_minutes) "
        "AND o2.option_id != o.option_id) ORDER BY option_id"
        for prefix in ("", "o.")
    ]


def _signature(tree: dict[str, Any]) -> Any:
    bindings: dict[str, str] = {}
    for node in _nodes(tree):
        if node.get("type") == "BASE_TABLE" and node.get("alias"):
            bindings.setdefault(node["alias"].casefold(), f"binding{len(bindings)}")

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
            result["column_names"] = [bindings.get(n.casefold(), n.casefold()) for n in result["column_names"]]
        if result.get("type") == "ORDER_DEFAULT" and "expression" in result:
            result["type"] = "ASCENDING"
        if result.get("type") == "CONJUNCTION_AND":
            children: list[Any] = []
            for child in result["children"]:
                children.extend(child["children"] if child.get("type") == "CONJUNCTION_AND" else [child])
            result["children"] = sorted(children, key=lambda item: json.dumps(item, sort_keys=True))
        return result

    return normalize(tree)


def _recognized(tree: dict[str, Any], connection: Any) -> bool:
    return _signature(tree) in [
        _signature(parse(sql, connection))
        for sql in [*alternatives(REFERENCE), *_observed_forms()]
    ]


def structural_checks(task: Any, sql: str) -> dict[str, Any] | None:
    if (task.template_id, task.template_version) != (CONTRACT, 1):
        return None
    connection = duckdb.connect(config={"enable_external_access": "false"})
    try:
        tree = parse(sql, connection)
        # Recognition includes actual outer and competitor bindings, lane equality,
        # both weak comparisons, strict improvement, and completeness on both sides.
        recognized = _recognized(tree, connection)
        root = tree["statements"][0]["node"]
        outer_table = root.get("from_table", {})
        outer = outer_table.get("alias") or outer_table.get("table_name", "")
        correlated = False
        for node in _nodes([root.get("where_clause"), root.get("having")]):
            if node.get("type") != "OPERATOR_NOT" or len(node.get("children", [])) != 1:
                continue
            child = node["children"][0]
            if child.get("subquery_type") != "EXISTS":
                continue
            subquery = child["subquery"]["node"]
            conditions = [subquery.get("where_clause"), subquery.get("having")]
            referenced = {tuple(n.get("column_names", [])[-2:]) for n in _nodes(conditions)
                          if n.get("class") == "COLUMN_REF"}
            correlated |= bool(outer) and all((outer, column) in referenced
                                             for column in ("lane", "cost_cents", "duration_minutes"))
        return {"status": "PASS" if recognized else "INCONCLUSIVE" if correlated else "FAIL",
                "rule_id": "instruction:not_exists_structure", "qualifying_not_exists_blocks": int(recognized),
                "parser_version": duckdb.__version__,
                "scope": "Actual correlated dominance NOT EXISTS; semantic mutants checked separately"}
    except (ValueError, KeyError, TypeError, IndexError, duckdb.Error) as exc:
        return {"status": "INCONCLUSIVE", "rule_id": "instruction:not_exists_structure",
                "error_type": type(exc).__name__}
    finally:
        connection.close()


def candidate_proofs(sql: str, reference: str, public: dict[str, Any]) -> dict[str, Any] | None:
    connection = duckdb.connect(config={"enable_external_access": "false"})
    try:
        tree = parse(sql, connection)
        if not _recognized(tree, connection):
            return None
        result = {}
        for key, spec in public.items():
            if "wrong_sql" not in spec:
                result[key] = deepcopy(spec)
                if key == "not_exists_structure":
                    control = deepcopy(tree)
                    negation = next(n for n in _nodes(control) if n.get("type") == "OPERATOR_NOT")
                    scalar = deepcopy(negation["children"][0])
                    scalar["subquery_type"] = "SCALAR"
                    scalar["subquery"]["node"]["select_list"] = [_expression(connection, "COUNT(*)")]
                    comparison = _expression(connection, "(SELECT COUNT(*) FROM options) = 0")
                    comparison["left"] = scalar
                    _replace(negation, comparison)
                    result[key]["structural_sql"] = _render(connection, control)
                    result[key]["outcome"] = "UNEXECUTED_CANDIDATE_AST_STRUCTURAL_SPEC"
                continue
            changed = deepcopy(tree)
            root = changed["statements"][0]["node"]
            outer = root["from_table"]["alias"]
            exists = next(n for n in _nodes(root["where_clause"]) if n.get("subquery_type") == "EXISTS")
            competitor = exists["subquery"]["node"]["from_table"]["alias"]
            mutation = spec["mutation"]
            wrapper = ""
            if mutation in {"strict_both", "weak_only"}:
                strict = next(n for n in _nodes(exists) if n.get("type") == "CONJUNCTION_OR")
                if mutation == "strict_both":
                    strict["type"] = "CONJUNCTION_AND"
                else:
                    _replace(strict, _expression(connection, "TRUE"))
                    # The recorded candidates exclude self redundantly. Remove that
                    # guard too, or this cannot witness the self-dominance defect.
                    for node in list(_nodes(exists)):
                        if node.get("type") == "COMPARE_NOTEQUAL" and all(
                            node.get(side, {}).get("column_names", [])[-1:] == ["option_id"]
                            for side in ("left", "right")
                        ):
                            _replace(node, _expression(connection, "TRUE"))
            elif mutation in {"global", "casefold"}:
                comparison = next(n for n in _nodes(exists) if n.get("type") == "COMPARE_EQUAL"
                                  and n.get("left", {}).get("column_names", [])[-1:] == ["lane"])
                if mutation == "global":
                    _replace(comparison, _expression(connection, "TRUE"))
                else:
                    for side in ("left", "right"):
                        comparison[side] = _expression(connection, "LOWER(" + ".".join(comparison[side]["column_names"]) + ")")
            elif mutation == "coalesce":
                cte = root["from_table"]["table_name"] != "options"
                for node in list(_nodes(changed)):
                    if node.get("type") == "OPERATOR_IS_NOT_NULL":
                        names = node["children"][0].get("column_names", [])
                        if cte or names[:1] == [competitor]:
                            _replace(node, _expression(connection, "TRUE"))
                for node in list(_nodes(exists)):
                    names = node.get("column_names", [])
                    if node.get("class") == "COLUMN_REF" and names[:1] == [competitor] and names[-1] in {"cost_cents", "duration_minutes"}:
                        _replace(node, _expression(connection, "COALESCE(" + ".".join(names) + ",0)"))
                if cte:
                    root["where_clause"] = {"class": "CONJUNCTION", "type": "CONJUNCTION_AND",
                        "children": [root["where_clause"], _expression(connection, f"{outer}.cost_cents IS NOT NULL AND {outer}.duration_minutes IS NOT NULL")]}
            elif mutation == "reverse":
                order = next(m for m in root["modifiers"] if m["type"] == "ORDER_MODIFIER")
                order["orders"][0]["type"] = "DESCENDING"
            elif mutation == "wrong_lane":
                root["select_list"][1] = _expression(connection, "CAST('wrong' AS VARCHAR) AS lane")
            elif mutation == "text_id":
                wrapper = "SELECT CAST(option_id AS VARCHAR) AS option_id,lane,cost_cents,duration_minutes FROM ({sql}) x ORDER BY CAST(option_id AS INTEGER)"
            elif mutation in {"scope", "no_zero", "no_max", "no_empty_lane", "positive_ids"}:
                predicate = {"scope": "lane='A'", "no_zero": "cost_cents>0 AND duration_minutes>0",
                             "no_max": "cost_cents<2147483647 AND duration_minutes<2147483647",
                             "no_empty_lane": "lane<>''", "positive_ids": "option_id>0"}[mutation]
                wrapper = "SELECT * FROM ({sql}) x WHERE " + predicate + " ORDER BY option_id"
            elif mutation == "single_tie":
                wrapper = "SELECT * FROM ({sql}) x QUALIFY ROW_NUMBER() OVER (PARTITION BY lane,cost_cents,duration_minutes ORDER BY option_id)=1 ORDER BY option_id"
            elif mutation == "repeat":
                wrapper = "SELECT * FROM ({sql}) x UNION ALL SELECT * FROM ({sql}) y ORDER BY option_id"
            elif mutation == "invent_empty":
                wrapper = "SELECT * FROM ({sql}) x UNION ALL SELECT CAST(1 AS INTEGER),'invented',CAST(0 AS INTEGER),CAST(0 AS INTEGER) ORDER BY option_id"
            else:
                return None
            actual = _render(connection, changed)
            result[key] = {**deepcopy(spec), "wrong_sql": wrapper.format(sql=actual) if wrapper else actual,
                           "outcome": "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"}
        return result
    except (ValueError, KeyError, TypeError, IndexError, StopIteration, duckdb.Error):
        return None
    finally:
        connection.close()
