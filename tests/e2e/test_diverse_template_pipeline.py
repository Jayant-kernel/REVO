"""New domain templates traverse the real sandbox and full verifier."""

import pytest

from tests.integration.sandbox.test_docker_available import requires_docker
from tests.test_diverse_templates import EDUCATION_SQL, PAYMENTS_SQL, SAAS_SQL, SUPPORT_SQL
from tests.verify_testkit import make_candidate
from verified_data_factory.sandbox import DockerRunner, SandboxConfig, SandboxExecutor
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import VerificationConfig, verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend

pytestmark = [pytest.mark.integration, pytest.mark.e2e]


@requires_docker
@pytest.mark.parametrize(
    ("template_id", "sql"),
    [
        ("sql.joins.saas_paid_invoices", SAAS_SQL),
        ("sql.aggregation.payment_net_settled", PAYMENTS_SQL),
        ("sql.aggregation.support_sla_breaches", SUPPORT_SQL),
        ("sql.dedup.education_grade_revisions", EDUCATION_SQL),
    ],
)
def test_new_domain_full_verification(template_id, sql):
    task = generate_task(load_builtin_registry().get(template_id), 94001)
    candidate = make_candidate(task, sql)
    sandbox = SandboxConfig(timeout_seconds=60)
    execution = SandboxExecutor(sandbox, DockerRunner(sandbox)).execute(task, candidate)
    result = verify_candidate(
        task, candidate, execution, VerificationConfig(), DerivedTaskBackend(sandbox)
    )
    assert result.verdict == "PASS", (result.verdict, result.failure_code, result.summary)
    assert result.verification_strength == "STRONG"
    assert result.mutation is not None and result.mutation.mutation_score == 1.0
    assert result.hidden is not None and result.hidden.failed == 0
    assert result.hidden.total == 4
    assert sum(
        case.source == "INDEPENDENT_ADVERSARIAL" and case.status == "PASS"
        for case in result.hidden.cases
    ) == 1
    assert result.properties is not None and result.properties.failed == 0
    assert result.metamorphic is not None and result.metamorphic.failed == 0
