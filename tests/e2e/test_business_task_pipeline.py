import pytest

from tests.integration.sandbox.test_docker_available import requires_docker
from tests.test_business_tasks import SQL, SQL_TEMPLATE_VERSIONS
from tests.verify_testkit import make_candidate
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend

pytestmark = [pytest.mark.integration, pytest.mark.e2e]


@requires_docker
@pytest.mark.parametrize("template_id", SQL)
def test_business_task_pinned_full_verification(template_id, tmp_path):
    task = generate_task(load_builtin_registry().get(template_id, SQL_TEMPLATE_VERSIONS.get(template_id)), 94001)
    candidate = make_candidate(task, SQL[template_id])
    sandbox = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(sandbox).execute(task, candidate)
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(sandbox))
    (tmp_path / "initial-execution.json").write_text(execution.model_dump_json(indent=2))
    (tmp_path / "full-verification.json").write_text(result.model_dump_json(indent=2))
    assert result.verdict == "PASS", result.model_dump(mode="json")
    if result.mutation.coverage_complete:
        assert result.verification_strength == "STRONG"
    else:
        assert result.verification_strength == "UNKNOWN"
        assert not result.mutation.covered_rules
    assert result.mutation.mutation_score == 1.0 and result.mutation.semantic_kills >= 2
    assert any(case.source == "INDEPENDENT_ADVERSARIAL" and case.status == "PASS" for case in result.hidden.cases)
