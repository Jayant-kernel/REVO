"""Source-bound query-structure obligations, separate from semantic mutant kills."""
from __future__ import annotations

from typing import Any

import duckdb

from verified_data_factory.task_engine.models import TaskInstance

from .sla_candidate_transforms import parse


def _nodes(value: Any) -> Any:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from _nodes(item)


def _sum_units(expression: Any) -> bool:
    return any(node.get("function_name") == "sum" and any(
        child.get("class") == "COLUMN_REF" and child.get("column_names", [""])[-1].casefold() == "units"
        for child in _nodes(node.get("children", []))) for node in _nodes(expression))


def _threshold(expression: dict[str, Any], aliases: set[str], minimum: int) -> bool:
    if expression.get("type") == "CONJUNCTION_AND":
        return any(_threshold(child, aliases, minimum) for child in expression["children"])
    if expression.get("type") == "CONJUNCTION_OR":
        return bool(expression["children"]) and all(_threshold(child, aliases, minimum) for child in expression["children"])
    if expression.get("class") != "COMPARISON":
        return False
    left, right = expression.get("left", {}), expression.get("right", {})

    def aggregate(value: dict[str, Any]) -> bool:
        return _sum_units(value) or (value.get("class") == "COLUMN_REF"
            and value.get("column_names", [""])[-1].casefold() in aliases)

    def constant(value: dict[str, Any]) -> Any:
        return value.get("value", {}).get("value") if value.get("class") == "CONSTANT" else None

    kind = expression["type"]
    return (aggregate(left) and ((kind == "COMPARE_GREATERTHANOREQUALTO" and constant(right) == minimum)
            or (kind == "COMPARE_GREATERTHAN" and constant(right) == minimum-1))) or (
            aggregate(right) and ((kind == "COMPARE_LESSTHANOREQUALTO" and constant(left) == minimum)
            or (kind == "COMPARE_LESSTHAN" and constant(left) == minimum-1)))


def _reconciliation_cte(sql: str) -> dict[str, Any]:
    """Recognized output-consuming CTE forms, not a general SQL lineage proof.

    Reachability alone is insufficient: a joined aggregate can be decorative.
    PASS requires a whole parsed shape with a multiplied line SUM in the CTE
    and that result in the reconciliation output. Other bindings stay unknown.
    """
    from .reconciliation_profile import alternatives
    from .sla_candidate_transforms import signature

    result: dict[str, Any] = {
        "status": "INCONCLUSIVE", "rule_id": "instruction:reconciliation_cte",
        "parser_version": duckdb.__version__,
        "scope": "bounded parsed reconciliation forms with output-consuming per-order product SUM CTE",
    }
    connection = duckdb.connect()
    try:
        tree = parse(sql, connection)
        root = tree["statements"][0]["node"]
        if root.get("type") != "SELECT_NODE":
            return {**result, "reason": "unsupported_query_node"}
        entries = root["cte_map"]["map"]
        body = {key: value for key, value in root.items() if key != "cte_map"}
        definitions = {entry["key"].casefold(): entry["value"]["query"]["node"]
                       for entry in entries}
        if len(definitions) != len(entries):
            return {**result, "reason": "duplicate_cte_names"}
        for node in _nodes([body, *definitions.values()]):
            kind = node.get("type", "")
            if isinstance(kind, str) and kind.endswith("_NODE") and kind != "SELECT_NODE":
                return {**result, "reason": "unsupported_query_node"}
            if node.get("cte_map", {}).get("map"):
                return {**result, "reason": "nested_cte_scope_unsupported"}

        def tables(value: Any) -> set[str]:
            return {node["table_name"].casefold() for node in _nodes(value)
                    if node.get("type") == "BASE_TABLE"
                    and not node.get("schema_name") and not node.get("catalog_name")}

        def reachable(names: set[str]) -> set[str]:
            found: set[str] = set()
            pending = names & definitions.keys()
            while pending:
                name = pending.pop()
                if name not in found:
                    found.add(name)
                    pending.update((tables(definitions[name]) & definitions.keys()) - found)
            return found

        participating = reachable(tables(body))
        if not participating:
            return {**result, "status": "FAIL", "reason": "no_participating_cte",
                    "participating_ctes": []}
        # Fixed public-contract prototypes, never derived from candidate SQL.
        # Whole-shape matching retains multiplication, grouping, correlation,
        # projection and joins, so an unused aggregate cannot borrow a PASS.
        reference = (
            "WITH line_totals AS (SELECT order_id, "
            "SUM(CAST(quantity AS HUGEINT) * unit_price_cents) AS line_total_cents "
            "FROM order_lines GROUP BY order_id) "
            "SELECT o.order_id,o.header_total_cents,COALESCE(l.line_total_cents,0) "
            "AS line_total_cents FROM orders o LEFT JOIN line_totals l ON l.order_id=o.order_id "
            "WHERE o.order_status='completed' AND EXTRACT(YEAR FROM o.ordered_on)=2025 "
            "AND o.header_total_cents<>COALESCE(l.line_total_cents,0) ORDER BY o.order_id ASC"
        )
        supported = list(zip(
            ("grouped_left_join", "correlated_cte", "lateral_cte"),
            ("line_totals", "reconciled", "reconciled"), alternatives(reference), strict=True))
        sourced = reference.replace(
            "WITH line_totals AS (",
            "WITH source AS (SELECT * FROM order_lines), Line_Totals AS (")
        supported.append(("source_then_grouped_left_join", "line_totals",
                          sourced.replace("FROM order_lines GROUP", "FROM source GROUP")))
        actual = signature(tree)
        for form, sum_cte, prototype in supported:
            if actual == signature(parse(prototype, connection)):
                return {**result, "status": "PASS", "reason": "recognized_output_consuming_cte",
                        "participating_ctes": sorted(participating), "sum_cte": sum_cte,
                        "supported_form": form}
        return {**result, "reason": "output_consuming_cte_shape_unsupported",
                "participating_ctes": sorted(participating)}
    except (ValueError, KeyError, TypeError, IndexError, duckdb.Error) as exc:
        return {**result, "error_type": type(exc).__name__}
    finally:
        connection.close()


def structural_checks(task: TaskInstance, sql: str) -> dict[str, Any] | None:
    from .delivery_profiles import get_profile

    if (task.template_id, task.template_version) == ("sql.cte.order_line_reconciliation", 1):
        return _reconciliation_cte(sql)
    profile = get_profile(task.template_id, task.template_version)
    if profile is not None:
        result: dict[str, Any] | None = profile.structural_checks(task, sql) if profile.STRUCTURAL_KEYS else None
        return result
    if (task.template_id, task.template_version) != ("sql.aggregation.warehouse_throughput", 2):
        return None
    connection = duckdb.connect()
    try:
        tree = parse(sql, connection)
        qualifying = 0
        for node in _nodes(tree):
            if node.get("type") != "SELECT_NODE" or not node.get("having"):
                continue
            having = node["having"]
            aliases = {expression.get("alias", "").casefold() for expression in node.get("select_list", [])
                       if expression.get("alias") and _sum_units(expression)}
            aggregate_condition = _threshold(having, aliases, int(task.requirements["min_total_units"]))
            if node.get("group_expressions") and aggregate_condition:
                qualifying += 1
        return {"status": "PASS" if qualifying else "FAIL", "rule_id": "instruction:aggregate_having",
                "qualifying_having_blocks": qualifying, "parser_version": duckdb.__version__,
                "scope": "required aggregate HAVING structure; threshold semantics checked separately"}
    except (ValueError, KeyError, TypeError, IndexError, duckdb.Error) as exc:
        return {"status": "INCONCLUSIVE", "rule_id": "instruction:aggregate_having", "error_type": type(exc).__name__}
    finally:
        connection.close()
