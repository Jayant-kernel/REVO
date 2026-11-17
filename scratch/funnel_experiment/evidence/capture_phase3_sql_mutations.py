"""Capture live mutation classifications for every hand-authored SQL contract."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.backend import SandboxBackend
from verified_data_factory.verification.models import ComparisonPolicy
from verified_data_factory.verification.mutations import (
    MutationContext,
    applicable_operators,
    run_mutation_checks,
)
from verified_data_factory.verification.oracle_registry import get_oracle

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
def main() -> None:
    from tests.test_business_tasks import SQL as business_sql
    from tests.verify_sql_samples import CORRECT_SQL

    sql_by_contract = {**CORRECT_SQL, **business_sql}
    registry = load_builtin_registry()
    backend = SandboxBackend()
    contracts = []
    for contract_id in sorted(sql_by_contract):
        template = registry.get(contract_id)
        task = generate_task(template, 1)
        sql = sql_by_contract[contract_id]
        expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, task.tables)
        result = run_mutation_checks(
            MutationContext(task, sql, task.tables, expected, backend, ComparisonPolicy()),
            max_mutations=20,
            min_score=0.0,
        )
        mutated_sql = {
            operator.name: operator.apply(task, sql)
            for operator in applicable_operators(task, sql, 20)
        }
        contracts.append(
            {
                "contract_id": contract_id,
                "sql_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
                "applicable": result.applicable,
                "caught": result.caught,
                "survived": result.survived,
                "invalid": result.invalid,
                "inconclusive": result.inconclusive,
                "mutation_score": result.mutation_score,
                "details": [
                    {
                        "operator": detail.operator,
                        "classification": detail.classification,
                        "reason": detail.reason,
                        "mutated_sql": mutated_sql[detail.operator],
                        "survivor_argument": (
                            "Mutant matched the independent oracle on this fixture; this is a recorded discrimination gap."
                            if detail.classification == "SURVIVED"
                            else None
                        ),
                    }
                    for detail in result.details
                ],
            }
        )
    payload = {
        "scope": "all hand-authored SQL contracts in tests.verify_sql_samples.CORRECT_SQL and tests.test_business_tasks.SQL",
        "contracts": contracts,
        "summary": {
            key: sum(contract[key] for contract in contracts)
            for key in ("applicable", "caught", "survived", "invalid", "inconclusive")
        },
        "saas_activation_payment": next(
            contract
            for contract in contracts
            if contract["contract_id"] == "sql.funnel.saas_activation_payment"
        ),
    }
    (ROOT / "phase3-sql-mutation-classifications.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
