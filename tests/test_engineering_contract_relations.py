"""Real execution must exercise >=2 relations on each rule-qualified contract."""
import pytest

from scripts.phase3_diagnostic import _reference_sql
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


@pytest.mark.parametrize("contract", ["sql.funnel.saas_activation_payment", "sql.aggregation.manufacturing_line_scrap"])
def test_rule_qualified_contract_has_two_executed_relations(contract):
    task = generate_task(load_builtin_registry().get(contract), 94001)
    candidate = make_candidate(task, _reference_sql()[contract])
    config = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    assert execution.status == "SUCCEEDED"
    data = execution.result_data
    assert data is not None
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, task.tables)
    context = MetamorphicContext(task, candidate, task.tables, [c.name for c in data.columns], data.rows,
                                 expected.order, DerivedTaskBackend(config), ComparisonPolicy(), task.seed,
                                 candidate_types=[c.type for c in data.columns])
    result = run_metamorphic_checks(context)
    assert result.applicable >= 2
    assert result.failed == 0
    assert result.passed == result.applicable


@pytest.mark.parametrize("contract,relation", [
    ("sql.funnel.saas_activation_payment", "SAAS_LATER_PAYMENT"),
    ("sql.funnel.saas_activation_payment", "SAAS_INCOMPLETE_ENTITY"),
    ("sql.funnel.saas_activation_payment", "SAAS_EXCLUDED_GROUP"),
    ("sql.aggregation.manufacturing_line_scrap", "SCRAP_ADDITIVITY"),
    ("sql.aggregation.manufacturing_line_scrap", "SCRAP_EXCLUDED_ROW"),
])
def test_each_new_relation_rejects_an_executed_wrong_query(contract, relation):
    task = generate_task(load_builtin_registry().get(contract), 94001)
    sql = _reference_sql()[contract]
    if relation == "SAAS_LATER_PAYMENT":
        sql = "SELECT group_key, SUM(amount) AS total_amount FROM account_funnel WHERE status='payment' AND EXTRACT(YEAR FROM occurred_at)=2025 GROUP BY group_key ORDER BY group_key"
    elif relation == "SAAS_INCOMPLETE_ENTITY":
        sql = "SELECT group_key, SUM(amount) AS total_amount FROM account_funnel WHERE EXTRACT(YEAR FROM occurred_at)=2025 GROUP BY group_key ORDER BY group_key"
    elif relation == "SAAS_EXCLUDED_GROUP":
        sql = sql.replace("SELECT DISTINCT group_key FROM scoped", "SELECT DISTINCT group_key FROM account_funnel")
    elif relation == "SCRAP_ADDITIVITY":
        sql = sql.replace("SUM(amount)", "COUNT(amount)")
    else:
        sql = sql.replace("status='eligible' AND ", "")
    candidate = make_candidate(task, sql)
    config = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    assert execution.status == "SUCCEEDED", execution.failure
    data = execution.result_data
    assert data is not None
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, task.tables)
    context = MetamorphicContext(task, candidate, task.tables, [c.name for c in data.columns], data.rows,
                                 expected.order, DerivedTaskBackend(config), ComparisonPolicy(), task.seed,
                                 candidate_types=[c.type for c in data.columns])
    results = run_metamorphic_checks(context)
    outcome = next(o for o in results.outcomes if o.relation_id == relation)
    assert outcome.applicable
    assert not outcome.passed
