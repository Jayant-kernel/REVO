"""Bounded native-window AST attestation; unknown valid forms remain inconclusive."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import duckdb

from .alternative_candidate_transforms import _expression, _nodes, _render, _replace
from .pareto_shipping_candidate_transforms import _signature
from .queue_batches_profile import CONTRACT, REFERENCE, alternatives, arithmetic_expression
from .sla_candidate_transforms import parse


def _projection_signature(tree: dict[str, Any]) -> Any:
    shape = deepcopy(tree)
    root = shape["statements"][0]["node"]
    source = root.get("from_table", {})
    if source.get("type") == "SUBQUERY" and source.get("alias"):
        alias = source["alias"]
        source["alias"] = "derived_queue"
        # Only outer references bind to this alias; never rewrite the inner scope.
        for node in _nodes([root.get("select_list"), root.get("modifiers")]):
            names = node.get("column_names", [])
            if len(names) == 2 and names[0] == alias:
                node["column_names"] = ["derived_queue", names[1]]
    return _signature(shape)


def _recognized(tree: dict[str, Any], connection: Any) -> bool:
    observed = ("SELECT submission_id, batch_number FROM ("
                + REFERENCE.removesuffix(" ORDER BY submission_id")
                + ") sub ORDER BY submission_id ASC")
    return _projection_signature(tree) in [
        _projection_signature(parse(sql, connection))
        for sql in [*alternatives(REFERENCE), observed]
    ]


def _structural_shape(tree: dict[str, Any]) -> dict[str, Any]:
    shape = deepcopy(tree)
    for node in list(_nodes(shape)):
        if (node.get("type") == "OPERATOR_CAST" and not node.get("try_cast")
                and node.get("child", {}).get("type") == "WINDOW_NTILE"):
            child = deepcopy(node["child"])
            child["alias"] = node["alias"]
            _replace(node, child)
    return shape


def _has_participating_native(node: dict[str, Any]) -> bool:
    # Unused CTE windows cannot establish participation in the output query.
    body = {key: value for key, value in node.items() if key != "cte_map"}
    if any(n.get("type") == "WINDOW_NTILE" for n in _nodes(body)):
        return True
    tables = {n.get("table_name") for n in _nodes(body) if n.get("type") == "BASE_TABLE"}
    return any(entry["key"] in tables and _has_participating_native(entry["value"]["query"]["node"])
               for entry in node.get("cte_map", {}).get("map", []))


def structural_checks(task: Any, sql: str) -> dict[str, Any] | None:
    if (task.template_id, task.template_version) != (CONTRACT, 1):
        return None
    connection = duckdb.connect(config={"enable_external_access": "false"})
    try:
        tree = parse(sql, connection)
        native = _has_participating_native(tree["statements"][0]["node"])
        recognized = _recognized(_structural_shape(tree), connection)
        return {"status": "PASS" if recognized else "INCONCLUSIVE" if native else "FAIL",
                "rule_id": "instruction:ntile_structure", "qualifying_ntile_blocks": int(recognized),
                "parser_version": duckdb.__version__,
                "scope": "Bound output lineage, queue partition, ASC NULLS LAST/id ASC and argument 3; "
                         "unsupported native forms are not attested"}
    except (ValueError, KeyError, TypeError, IndexError, duckdb.Error) as exc:
        return {"status": "INCONCLUSIVE", "rule_id": "instruction:ntile_structure",
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
            if "wrong_sql" not in spec and key != "ntile_structure":
                result[key] = deepcopy(spec)
                continue
            changed = deepcopy(tree)
            window = next(n for n in _nodes(changed) if n.get("type") == "WINDOW_NTILE")
            alias = window["alias"]
            names = window["partitions"][0]["column_names"]
            prefix = ".".join(names[:-1])
            prefix = prefix + "." if prefix else ""
            mutation = spec.get("mutation")
            wrapper = ""
            if key == "ntile_structure":
                replacement = _expression(connection, arithmetic_expression(prefix))
                replacement["alias"] = alias
                _replace(window, replacement)
                result[key] = {**deepcopy(spec), "structural_sql": _render(connection, changed),
                               "outcome": "UNEXECUTED_CANDIDATE_AST_STRUCTURAL_SPEC"}
                continue
            if mutation in {"ntile2", "ntile4"}:
                window["children"] = [_expression(connection, "2" if mutation == "ntile2" else "4")]
            elif mutation == "rank":
                window.update(type="WINDOW_RANK", function_name="rank", children=[])
            elif mutation == "global":
                window["partitions"] = []
            elif mutation == "reverse_time":
                window["orders"][0]["type"] = "DESCENDING"
            elif mutation == "reverse_id":
                window["orders"][1]["type"] = "DESCENDING"
            elif mutation == "nulls_first":
                window["orders"][0]["null_order"] = "NULLS FIRST"
            elif mutation == "casefold":
                window["partitions"] = [_expression(connection, f"LOWER({prefix}queue)")]
            elif mutation == "floor_proportional":
                expression = (f"CAST(1+((ROW_NUMBER() OVER (PARTITION BY {prefix}queue ORDER BY "
                    f"{prefix}submitted_at ASC NULLS LAST,{prefix}submission_id))*3) // "
                    f"COUNT(*) OVER (PARTITION BY {prefix}queue) AS BIGINT)")
                replacement = _expression(connection, expression)
                replacement["alias"] = alias
                _replace(window, replacement)
            elif mutation == "constant":
                replacement = _expression(connection, "CAST(1 AS BIGINT)")
                replacement["alias"] = alias
                _replace(window, replacement)
            elif mutation == "int_batch":
                wrapper = "SELECT submission_id,CAST(batch_number AS INTEGER) AS batch_number FROM ({sql}) x ORDER BY submission_id"
            elif mutation == "text_id":
                wrapper = "SELECT CAST(submission_id AS VARCHAR) AS submission_id,batch_number FROM ({sql}) x ORDER BY CAST(submission_id AS INTEGER)"
            elif mutation == "offset":
                wrapper = "SELECT submission_id,batch_number+1 AS batch_number FROM ({sql}) x ORDER BY submission_id"
            elif mutation == "reverse_output":
                root = changed["statements"][0]["node"]
                next(m for m in root["modifiers"] if m["type"] == "ORDER_MODIFIER")["orders"][0]["type"] = "DESCENDING"
            elif mutation == "invent_empty":
                wrapper = "SELECT * FROM ({sql}) x UNION ALL SELECT CAST(0 AS INTEGER),CAST(1 AS BIGINT) ORDER BY submission_id"
            elif mutation in {"year", "no_null", "positive_id", "dedup_payload"}:
                leaf = next(n for n in _nodes(changed) if n.get("type") == "SELECT_NODE"
                            and n.get("from_table", {}).get("table_name") == "submissions")
                if mutation == "dedup_payload":
                    leaf["qualify"] = _expression(connection,
                        f"ROW_NUMBER() OVER (PARTITION BY {prefix}queue,{prefix}submitted_at "
                        f"ORDER BY {prefix}submission_id)=1")
                else:
                    predicate = {"year": f"YEAR({prefix}submitted_at)=2025",
                                 "no_null": f"{prefix}submitted_at IS NOT NULL",
                                 "positive_id": f"{prefix}submission_id>0"}[mutation]
                    leaf["where_clause"] = _expression(connection, predicate)
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
