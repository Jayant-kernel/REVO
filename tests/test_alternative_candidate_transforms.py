"""The three previously abstaining shapes earn their own executed clause coverage."""
import pytest

from scripts.phase3_diagnostic import _reference_sql
from tests.test_stage5_sla_profile import matches
from tests.verify_testkit import make_candidate
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.sandbox.policy import check_policy
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.public_rule_proofs import public_proofs
from verified_data_factory.verification.qualification.alternative_candidate_transforms import (
    candidate_proofs,
)
from verified_data_factory.verification.qualification.paid_invoices_profile import (
    alternatives as paid,
)
from verified_data_factory.verification.qualification.reconciliation_profile import (
    alternatives as reconciled,
)
from verified_data_factory.verification.qualification.weekly_visits_profile import (
    alternatives as weekly,
)

CASES = [("sql.cte.order_line_reconciliation", reconciled, 1),
         ("sql.joins.saas_paid_invoices", paid, 2), ("sql.temporal.clinic_weekly_visits", weekly, 1)]


@pytest.mark.parametrize("contract,forms,index", CASES)
def test_all_candidate_derived_discriminators_execute_for_each_public_clause(contract, forms, index):
    task = generate_task(load_builtin_registry().get(contract, 1), 314159)
    reference, public = public_proofs(task)
    sql = forms(reference)[index]
    proofs = candidate_proofs(contract, 1, sql, reference, public)
    assert proofs is not None and proofs.keys() == public.keys()
    for key, proof in proofs.items():
        if "wrong_sql" in proof:
            assert check_policy(proof["wrong_sql"]).allowed, key
            assert matches(task, sql, proof["witness"]), key
            assert not matches(task, proof["wrong_sql"], proof["witness"]), key
    assert candidate_proofs(contract, 2, sql, reference, public) is None
    assert candidate_proofs(contract, 1, sql+" LIMIT 1", reference, public) is None


@pytest.mark.parametrize("contract,forms,index", CASES)
def test_real_alternative_runtime_gets_strong_without_canonical_sql_substitution(contract, forms, index, tmp_path):
    task = generate_task(load_builtin_registry().get(contract, 1), 314159)
    candidate = make_candidate(task, forms(_reference_sql()[contract])[index])
    config = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config))
    (tmp_path / "alternative-runtime.json").write_text(result.model_dump_json(indent=2))
    assert result.verdict == "PASS", result.summary
    assert result.verification_strength == "STRONG"
    assert result.mutation.coverage_complete and result.mutation.mutation_score == 1.0
    assert all(detail.candidate_execution_id and detail.retained_executions for detail in result.mutation.details)
