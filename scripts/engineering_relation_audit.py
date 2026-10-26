"""Execute qualified-contract relations and their private wrong-query witnesses."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, ROOT, safety, stamp, write_new
from engineering_score import digest
from phase3_diagnostic import _reference_sql

from tests.verify_testkit import make_candidate
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.metamorphic import (
    MetamorphicContext,
    run_metamorphic_checks,
)
from verified_data_factory.verification.models import ComparisonPolicy
from verified_data_factory.verification.oracle_registry import get_oracle


def execute_relations(task: Any, sql: str) -> dict[str, Any]:
    config = load_config(ROOT / "configs/sandbox_production.yaml")
    candidate = make_candidate(task, sql)
    execution = SandboxExecutor(config).execute(task, candidate)
    if execution.status != "SUCCEEDED" or execution.result_data is None:
        return {"classification": "EXECUTION_ERROR", "status": execution.status}
    data = execution.result_data
    oracle = get_oracle(task.template_id, task.template_version).fn(task.requirements, task.tables)
    context = MetamorphicContext(task, candidate, task.tables, [c.name for c in data.columns], data.rows,
                                 oracle.order, DerivedTaskBackend(config), ComparisonPolicy(), task.seed,
                                 candidate_types=[c.type for c in data.columns])
    return {"classification": "EXECUTED", "execution_id": execution.execution_id,
            "relations": run_metamorphic_checks(context).model_dump(mode="json")}


def main() -> None:
    safety()
    rule_records = json.loads((OUT / "phase4-rules-r1.json").read_text())["contracts"]
    references = _reference_sql()
    records = []
    for record in rule_records:
        contract = record["contract_id"]
        if record["status"] != "RULES_EXECUTED":
            records.append({"contract_id": contract, "contract_version": record["contract_version"],
                            "status": "BLOCKED_BY_RULE_QUALIFICATION", "reason": record["reason"]})
            continue
        task = generate_task(load_builtin_registry().get(contract, record["contract_version"]), 94001)
        reference = references[contract]
        correct = execute_relations(task, reference)
        if contract == "sql.funnel.saas_activation_payment":
            wrong_queries = {
                "SAAS_LATER_PAYMENT": "SELECT group_key, SUM(amount) AS total_amount FROM account_funnel WHERE status='payment' AND EXTRACT(YEAR FROM occurred_at)=2025 GROUP BY group_key ORDER BY group_key",
                "SAAS_INCOMPLETE_ENTITY": "SELECT group_key, SUM(amount) AS total_amount FROM account_funnel WHERE EXTRACT(YEAR FROM occurred_at)=2025 GROUP BY group_key ORDER BY group_key",
                "SAAS_EXCLUDED_GROUP": reference.replace("SELECT DISTINCT group_key FROM scoped", "SELECT DISTINCT group_key FROM account_funnel"),
            }
        else:
            wrong_queries = {"SCRAP_ADDITIVITY": reference.replace("SUM(amount)", "COUNT(amount)"),
                             "SCRAP_EXCLUDED_ROW": reference.replace("status='eligible' AND ", "")}
        witnesses = []
        for relation, query in wrong_queries.items():
            observed = execute_relations(task, query)
            outcome = next((o for o in observed.get("relations", {}).get("outcomes", []) if o["relation_id"] == relation), None)
            witnesses.append({"relation_id": relation, "wrong_sql": query, "observed": observed,
                              "caught": outcome is not None and outcome["applicable"] and not outcome["passed"]})
        passed = correct.get("relations", {}).get("failed") == 0 and sum(w["caught"] for w in witnesses) >= 2
        records.append({"contract_id": contract, "contract_version": task.template_version,
                        "correct": correct, "wrong_query_witnesses": witnesses,
                        "discriminating_relations": sum(w["caught"] for w in witnesses),
                        "status": "PASS" if passed else "FAIL"})
    report = {"created_at": stamp(), "model_calls": 0, "contracts": records,
              "independence": "differential verification",
              "source_hashes": {p: digest(ROOT / p) for p in (
                  "scripts/engineering_relation_audit.py", "src/verified_data_factory/verification/metamorphic.py",
                  "src/verified_data_factory/verification/properties.py", "src/verified_data_factory/verification/models.py",
                  "src/verified_data_factory/verification/business_oracles.py", "src/verified_data_factory/verification/oracle_registry.py",
                  "tests/test_business_tasks.py", "configs/sandbox_production.yaml")}}
    write_new(OUT / "phase5-relations.json", report)
    print(json.dumps({"passed_contracts": [r["contract_id"] for r in records if r["status"] == "PASS"],
                      "blocked_contracts": sum(r["status"] == "BLOCKED_BY_RULE_QUALIFICATION" for r in records),
                      "failed_contracts": sum(r["status"] == "FAIL" for r in records)}, indent=2))


if __name__ == "__main__":
    main()
