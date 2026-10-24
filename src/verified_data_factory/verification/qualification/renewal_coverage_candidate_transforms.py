"""Bounded DuckDB AST recognition and actual-candidate mutation; unknown stays unknown."""
from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from typing import Any

import duckdb

from .alternative_candidate_transforms import _expression, _nodes, _render
from .renewal_coverage_profile import REFERENCE, alternatives
from .sla_candidate_transforms import parse


def _signature(tree: Any) -> Any:
    bindings = {}
    for n in _nodes(tree):
        if n.get("type") == "BASE_TABLE":
            bindings[(n.get("alias") or n["table_name"]).casefold()] = n["table_name"].casefold()

    def visit(v: Any) -> Any:
        if isinstance(v, list):
            return [visit(x) for x in v]
        if not isinstance(v, dict):
            return v
        n = {k: visit(x) for k, x in v.items() if k != "query_location"}
        if n.get("type") == "BASE_TABLE":
            n["alias"] = ""
            n["table_name"] = n["table_name"].casefold()
        if n.get("class") == "COLUMN_REF":
            n["column_names"] = [bindings.get(x.casefold(), x.casefold()) for x in n["column_names"]]
            if n.get("alias", "").casefold() == n["column_names"][-1]:
                n["alias"] = ""
        if n.get("type") == "CONJUNCTION_AND":
            n["children"] = sorted(n["children"], key=lambda x: json.dumps(x, sort_keys=True))
        if n.get("type") == "COMPARE_EQUAL":
            n["left"], n["right"] = sorted([n["left"], n["right"]], key=lambda x: json.dumps(x, sort_keys=True))
        if n.get("type") == "ORDER_DEFAULT" and "expression" in n:
            n["type"] = "ASCENDING"
        return n
    return visit(tree)


@lru_cache(maxsize=1)
def _prototypes() -> list[Any]:
    con = duckdb.connect(config={"enable_external_access": "false"})
    try:
        shapes = alternatives(REFERENCE)
        # CASE wrappers are recognized only for a genuine boolean expression.
        shapes.append(REFERENCE.replace("EXISTS (", "CASE WHEN EXISTS (").replace(
            ") AS covered FROM", ") THEN TRUE ELSE FALSE END AS covered FROM"))
        cohort = "e.expires_at>=TIMESTAMP '2025-01-01' AND e.expires_at<TIMESTAMP '2026-01-01'"
        return [_signature(parse(shape.replace(cohort, year).replace("INTERVAL '14 days'", interval), con))
                for shape in shapes for year in [cohort, "YEAR(e.expires_at)=2025",
                    "EXTRACT(YEAR FROM e.expires_at)=2025",
                    "e.expires_at>=DATE '2025-01-01' AND e.expires_at<DATE '2026-01-01'"]
                for interval in ["INTERVAL '14 days'", "INTERVAL 14 DAY", "INTERVAL '336 hours'", "INTERVAL '2 weeks'"]]
    finally:
        con.close()


def candidate_proofs(sql: str, reference: str, public: dict[str, Any]) -> dict[str, Any] | None:
    con = duckdb.connect(config={"enable_external_access": "false"})
    try:
        tree = parse(sql, con)
        if _signature(tree) not in _prototypes():
            return None
        bindings = {n["table_name"]: n.get("alias") or n["table_name"]
                    for n in _nodes(tree) if n.get("type") == "BASE_TABLE"}
        e, r = ("\"" + bindings[t].replace('"', '""') + "\"" for t in ("episodes", "renewals"))
        result = {}
        for key, spec in public.items():
            if "wrong_sql" not in spec:
                result[key] = deepcopy(spec)
                continue
            changed = deepcopy(tree)
            root = changed["statements"][0]["node"]
            mutation = spec["mutation"]
            wrapper = None

            def replace_comparison(column: str, expression: str, tree: dict[str, Any] = changed) -> None:
                target = next(n for n in _nodes(tree) if n.get("class") == "COMPARISON"
                              and n.get("left", {}).get("class") == "COLUMN_REF"
                              and n["left"]["column_names"][-1] == column)
                target.clear()
                target.update(_expression(con, expression))

            if mutation == "member":
                replace_comparison("member_id", "TRUE")
            elif mutation in {"status", "pending"}:
                replace_comparison("status", "TRUE" if mutation == "status" else f"{r}.status='pending'")
            elif mutation in {"strict_begin", "round_begin"}:
                expr = (f"{r}.begins_at<{e}.expires_at" if mutation == "strict_begin" else
                        f"CAST({r}.begins_at AS DATE)<=CAST({e}.expires_at AS DATE)")
                replace_comparison("begins_at", expr)
            elif mutation == "round_end":
                replace_comparison("ends_at", f"CAST({r}.ends_at AS DATE)>=CAST({e}.expires_at AS DATE)+INTERVAL '14 days'")
            elif mutation == "stitch":
                # Collapse the actual renewal source into a fabricated interval union.
                # This also stays executable for a LEFT JOIN (no correlated ON subquery).
                target = next(n for n in _nodes(changed) if n.get("type") == "BASE_TABLE"
                              and n["table_name"].casefold() == "renewals")
                collapsed = parse("SELECT * FROM (SELECT member_id, MIN(begins_at) AS begins_at, "
                    "MAX(ends_at) AS ends_at, 'confirmed' AS status FROM renewals "
                    f"WHERE status='confirmed' GROUP BY member_id) {r}", con)
                target.clear()
                target.update(collapsed["statements"][0]["node"]["from_table"])
            elif mutation in {"day13", "strict_end"}:
                expr = (f"{r}.ends_at>={e}.expires_at+INTERVAL '13 days'" if mutation == "day13" else
                        f"{r}.ends_at>{e}.expires_at+INTERVAL '14 days'")
                replace_comparison("ends_at", expr)
            elif mutation == "cohort":
                root["where_clause"] = _expression(con, "TRUE")
            elif mutation == "renewal_year":
                replace_comparison("status", f"{r}.status='confirmed' AND YEAR({r}.begins_at)=2025")
            elif mutation in {"wrong_id", "text_id"}:
                # A result-level transform also applies to GROUP BY candidates without invalid SQL.
                expr = ("CASE WHEN episode_id=1 THEN 0 ELSE episode_id END" if mutation == "wrong_id"
                        else "CAST(episode_id AS VARCHAR)")
                wrapper = f"SELECT {expr} AS episode_id,covered FROM ({{sql}}) actual_candidate ORDER BY episode_id"
            elif mutation == "repeat":
                wrapper = "SELECT * FROM ({sql}) actual_candidate UNION ALL SELECT * FROM ({sql}) second_copy ORDER BY episode_id"
            elif mutation == "empty":
                wrapper = "SELECT * FROM ({sql}) actual_candidate UNION ALL SELECT 0,FALSE ORDER BY episode_id"
            elif mutation == "single_episode":
                wrapper = "SELECT * FROM ({sql}) actual_candidate WHERE episode_id<>11 ORDER BY episode_id"
            elif mutation == "reverse":
                wrapper = "SELECT * FROM ({sql}) actual_candidate ORDER BY episode_id DESC"
            elif mutation == "true":
                wrapper = "SELECT episode_id,TRUE AS covered FROM ({sql}) actual_candidate ORDER BY episode_id"
            else:
                return None
            mutant = _render(con, changed)
            result[key] = {**deepcopy(spec), "wrong_sql": wrapper.format(sql=mutant) if wrapper else mutant,
                           "outcome": "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"}
        return result
    except (ValueError, KeyError, TypeError, IndexError, StopIteration, duckdb.Error):
        return None
    finally:
        con.close()
