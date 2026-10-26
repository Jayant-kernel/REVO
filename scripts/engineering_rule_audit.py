"""Executed rule profiles or explicit quarantine; source presence earns no pass."""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, ROOT, safety, stamp, write_new
from engineering_rejudge import evaluate
from engineering_score import digest
from phase3_diagnostic import _reference_sql

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.errors import FixtureError
from verified_data_factory.task_engine.hidden_fixtures import fixture_fingerprint
from verified_data_factory.verification.oracle_registry import get_oracle


def ledger(statuses: list[str], *, group: str = "a", year: int = 2025) -> dict[str, list[dict[str, Any]]]:
    return {"account_funnel": [{"record_id": i, "entity_id": 1, "group_key": group,
                                "occurred_at": f"{year}-01-01 00:00:00", "sequence": i,
                                "status": status, "amount": 7 if status == "payment" else 11}
                               for i, status in enumerate(statuses, 1)]}


def saas_profile(task: Any, sql: str, *, execute: bool = True) -> dict[str, Any]:
    complete = ledger(["signup", "trial", "activation", "payment", "payment"])
    complete["account_funnel"][-1]["amount"] = 99
    baseline = task.tables
    nonadjacent = ledger(["signup", "trial", "payment", "activation", "payment"])
    no_trial = ledger(["signup", "activation", "activation", "payment"])
    gap = ledger(["signup", "trial", "activation", "payment"])
    for i, row in enumerate(gap["account_funnel"]):
        row["occurred_at"] = f"2025-01-0{i + 1} 00:00:00"
    adjacent = sql.replace("AND (a.occurred_at, a.sequence) > (t.occurred_at, t.sequence)",
                           "AND (a.occurred_at, a.sequence) > (t.occurred_at, t.sequence) AND NOT EXISTS (SELECT 1 FROM scoped x WHERE x.entity_id=t.entity_id AND (x.occurred_at,x.sequence)>(t.occurred_at,t.sequence) AND (x.occurred_at,x.sequence)<(a.occurred_at,a.sequence))")
    cases = {
        "objective": (no_trial, sql.replace("t.status = 'trial'", "t.status IN ('trial','activation')")),
        "year": (ledger(["signup", "trial", "activation", "payment"], year=2024), sql.replace("EXTRACT(YEAR FROM occurred_at)=2025", "TRUE")),
        "funnel_steps": (no_trial, sql.replace("t.status = 'trial'", "t.status IN ('trial','activation')")),
        "in_scope_statuses": (baseline, sql.replace("SELECT DISTINCT group_key FROM scoped", "SELECT DISTINCT group_key FROM account_funnel")),
        "session_gap_minutes": (gap, sql.replace("AND t.status = 'trial'", "AND t.status = 'trial' AND t.occurred_at <= s.occurred_at + INTERVAL 30 MINUTE")),
        "cross_session_policy": (baseline, sql.replace("p.entity_id = a.entity_id", "TRUE")),
        "consecutiveness": (nonadjacent, adjacent),
        "repeat_policy": (complete, sql.replace("ORDER BY p.occurred_at, p.sequence", "ORDER BY p.occurred_at DESC, p.sequence DESC")),
        "same_timestamp_policy": (complete, sql.replace("(t.occurred_at, t.sequence) > (s.occurred_at, s.sequence)", "t.occurred_at > s.occurred_at")),
        "completion_amount": (complete, sql.replace("SUM(p.amount)", "COUNT(p.amount)")),
        "output_columns": (complete, sql.replace("AS total_amount", "AS incorrect_amount")),
        "order_by": (baseline, sql.replace("ORDER BY s.group_key ASC", "ORDER BY s.group_key DESC")),
        "zero_incomplete": (no_trial, sql.replace("ORDER BY s.group_key ASC", "HAVING SUM(p.amount) IS NOT NULL ORDER BY s.group_key ASC")),
        "ordered_steps": (complete, sql.replace("(t.occurred_at, t.sequence) > (s.occurred_at, s.sequence)", "(t.occurred_at, t.sequence) < (s.occurred_at, s.sequence)")),
        "first_matching": (ledger(["signup", "trial", "activation", "trial", "payment"]), sql.replace("ORDER BY t.occurred_at, t.sequence", "ORDER BY t.occurred_at DESC, t.sequence DESC")),
        "group_by_segment": (baseline, sql.replace("SELECT s.group_key,", "SELECT MIN(s.group_key) AS group_key,").replace("GROUP BY s.group_key", "").replace("ORDER BY s.group_key ASC", "ORDER BY group_key ASC")),
    }
    proofs = {}
    for rule, (tables, wrong) in cases.items():
        if not execute:
            proofs[rule] = {"wrong_sql": wrong, "witness": tables, "outcome": "UNEXECUTED_RULE_SPEC"}
            continue
        correct = evaluate(task, tables, sql)
        incorrect = evaluate(task, tables, wrong)
        proofs[rule] = {"reference": correct, "wrong_query": incorrect, "wrong_sql": wrong,
                        "witness": tables, "outcome": "EXECUTED_RULE_PROOF" if correct["classification"] == "MATCH" and incorrect["classification"] == "KILLED_WRONG_ANSWER" else "OPEN"}
    invalid = ledger(["signup", "trial"])
    invalid["account_funnel"][1]["sequence"] = 1
    try:
        get_oracle(task.template_id, task.template_version).fn(task.requirements, invalid)
    except ValueError as exc:
        proofs["tie_uniqueness"] = {"outcome": "REJECTED_INVALID_INPUT", "reason": str(exc),
                                    "witness": invalid, "sql_mutant": "NOT_APPLICABLE: this rule defines the valid input domain"}
    else:
        proofs["tie_uniqueness"] = {"outcome": "OPEN"}
    invalid_group = ledger(["signup", "trial"])
    invalid_group["account_funnel"][1]["group_key"] = "other"
    try:
        get_oracle(task.template_id, task.template_version).fn(task.requirements, invalid_group)
    except ValueError as exc:
        proofs["entity_group"] = {"outcome": "REJECTED_INVALID_INPUT", "reason": str(exc), "witness": invalid_group}
    return proofs


def scrap_profile(task: Any, sql: str, *, execute: bool = True) -> dict[str, Any]:
    table = next(iter(task.tables))
    tables = {name: [dict(r) for r in rows] for name, rows in task.tables.items()}
    sample = dict(tables[table][0])
    sample.update(record_id=999, entity_id=999, group_key="unused", status="ineligible", amount=13)
    tables[table].append(sample)
    wrong = {
        "objective": sql.replace("SUM(amount)", "COUNT(amount)"),
        "year": sql.replace("EXTRACT(YEAR FROM occurred_at)=2025", "EXTRACT(YEAR FROM occurred_at)=2024"),
        "group_by": sql.replace("SELECT group_key, SUM(amount)", "SELECT MIN(group_key) AS group_key, SUM(amount)").replace("GROUP BY group_key", ""),
        "count_semantics": sql.replace("SUM(amount)", "SUM(DISTINCT amount)"),
        "empty_group_behavior": sql.replace("status='eligible'", "TRUE"),
        "output_columns": sql.replace("AS total_amount", "AS incorrect_amount"),
        "order_by": sql.replace("ORDER BY group_key ASC", "ORDER BY group_key DESC"),
        "zero_values": sql.replace("ORDER BY group_key ASC", "HAVING SUM(amount) <> 0 ORDER BY group_key ASC"),
    }
    tables[table].append({**sample, "record_id": 1000, "entity_id": 1000,
                          "group_key": "zero", "status": "eligible", "amount": 0})
    proofs = {}
    for rule, query in wrong.items():
        if not execute:
            proofs[rule] = {"wrong_sql": query, "witness": tables, "outcome": "UNEXECUTED_RULE_SPEC"}
            continue
        correct, incorrect = evaluate(task, tables, sql), evaluate(task, tables, query)
        proofs[rule] = {"reference": correct, "wrong_query": incorrect, "wrong_sql": query, "witness": tables,
                        "outcome": "EXECUTED_RULE_PROOF" if correct["classification"] == "MATCH" and incorrect["classification"] == "KILLED_WRONG_ANSWER" else "OPEN"}
    invalid = {table: [dict(row) for row in task.tables[table]]}
    invalid[table][0]["amount"] = None
    if not execute:
        proofs["null_handling"] = {"outcome": "UNEXECUTED_DOMAIN_SPEC", "witness": invalid}
        return proofs
    try:
        fixture_fingerprint(task, invalid)
    except FixtureError as exc:
        if not isinstance(exc.__cause__, duckdb.ConstraintException):
            raise
        proofs["null_handling"] = {"outcome": "REJECTED_INVALID_INPUT", "reason": str(exc), "witness": invalid,
                                   "sql_mutant": "NOT_APPLICABLE: declared NOT NULL input domain"}
    else:
        proofs["null_handling"] = {"outcome": "OPEN"}
    return proofs


def main() -> None:
    safety()
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="")
    args = parser.parse_args()
    if args.revision and not re.fullmatch(r"r[0-9]+", args.revision):
        raise ValueError("revision must be r followed by digits")
    references = _reference_sql()
    latest = {}
    for template in load_builtin_registry().list():
        if template.template_id not in latest or latest[template.template_id].version < template.version:
            latest[template.template_id] = template
    records = []
    for template_id, template in sorted(latest.items(), key=lambda item: (item[1].family, item[0])):
        task = generate_task(template, 94001)
        entry = get_oracle(template_id, template.version)
        reference = references.get(template_id)
        proofs = {}
        if template_id == "sql.funnel.saas_activation_payment":
            proofs = saas_profile(task, reference)
        elif template_id == "sql.aggregation.manufacturing_line_scrap":
            proofs = scrap_profile(task, reference)
        complete = all(proofs.get(key, {}).get("outcome") in {"EXECUTED_RULE_PROOF", "REJECTED_INVALID_INPUT"} for key in task.requirements)
        rule_map = {key: {"declared_value": value, "instruction": task.instruction,
                          "oracle": f"{entry.fn.__module__}.{entry.fn.__name__}",
                          "fixture": "builtin generated seed 94001 + explicit public-rule witnesses",
                          "reference_sql_available": reference is not None,
                          **proofs.get(key, {"outcome": "UNPROVEN_RULE_COVERAGE", "wrong_query": None})}
                    for key, value in task.requirements.items()}
        records.append({"contract_id": template_id, "contract_version": template.version, "family": template.family,
                        "rule_map": rule_map, "status": "RULES_EXECUTED" if complete else "QUARANTINED",
                        "shared_generic_oracle": entry.fn.__name__ == "expansion_total",
                        "oracle_function_sha256": hashlib.sha256(inspect.getsource(entry.fn).encode()).hexdigest(),
                        "reason": "all declared rules have executed counterexamples/domain rejection" if complete else "complete requirement-specific counterexample evidence is absent; do not infer intent or proof from registration",
                        "independence": "differential verification"})
    suffix = "-" + args.revision if args.revision else ""
    path = OUT / f"phase4-rules{suffix}.json"
    write_new(path, {"created_at": stamp(), "contracts": records, "scope": "Rule qualification, not full evidence readiness",
                     "sources": {p: digest(ROOT / p) for p in ("scripts/engineering_rule_audit.py", "src/verified_data_factory/verification/business_oracles.py", "src/verified_data_factory/verification/oracle_registry.py")}})
    quarantine_path = ROOT / "manifests/package-a-contract-quarantine.json"
    if args.revision:
        print(json.dumps({"statuses": dict(Counter(r["status"] for r in records)), "quarantine_not_regenerated": True}))
        return
    archive = OUT / "phase4-prior-quarantine.json"
    write_new(archive, json.loads(quarantine_path.read_text()))
    quarantine = json.loads(quarantine_path.read_text())
    existing = {(q["contract_id"], q["contract_version"]) for q in quarantine["quarantines"]}
    for record in records:
        key = record["contract_id"], record["contract_version"]
        if record["status"] == "QUARANTINED" and key not in existing:
            quarantine["quarantines"].append({"contract_id": key[0], "contract_version": key[1],
                                               "evidence_id": "engineering-4-rule-audit", "reason": record["reason"],
                                               "scope": ["production", "distinct_selection", "experiment"]})
    quarantine_path.write_text(json.dumps(quarantine, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"statuses": dict(Counter(r["status"] for r in records)),
                      "shared_generic_contracts": sum(r["shared_generic_oracle"] for r in records)}, indent=2))


if __name__ == "__main__":
    main()
