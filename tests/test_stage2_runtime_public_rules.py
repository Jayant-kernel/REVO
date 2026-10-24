"""Candidate-level public coverage is earned by actual sandbox executions."""
import pytest

from scripts.engineering_receipt_artifacts import SUPPORTED
from scripts.phase3_diagnostic import _reference_sql
from tests.verify_testkit import make_candidate
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.models import VerificationConfig


@pytest.mark.parametrize("contract,version", sorted(SUPPORTED))
def test_actual_candidate_gets_executed_public_coverage(contract, version, tmp_path):
    task = generate_task(load_builtin_registry().get(contract, version), 94001)
    candidate = make_candidate(task, _reference_sql()[contract])
    config = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    (tmp_path / "runtime-initial-execution.json").write_text(execution.model_dump_json(indent=2))
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config))
    (tmp_path / "runtime-public-coverage.json").write_text(result.model_dump_json(indent=2))
    assert result.verdict == "PASS", result.summary
    assert result.verification_strength == "STRONG"
    assert result.mutation.coverage_complete
    assert set(result.mutation.covered_rules) == set(public_behavior_map(task).semantic_rule_ids)
    assert all(detail.candidate_execution_id and detail.execution_id and detail.retained_executions
               for detail in result.mutation.details)
    capped = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config),
                              config=VerificationConfig(max_mutations=1))
    (tmp_path / "runtime-capped-coverage.json").write_text(capped.model_dump_json(indent=2))
    assert capped.verdict == "PASS", capped.model_dump_json()
    assert capped.mutation is not None
    assert capped.verification_strength != "STRONG"
    assert not capped.mutation.coverage_complete
