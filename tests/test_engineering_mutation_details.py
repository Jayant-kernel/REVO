from tests.test_verify_mutations import _mutation_ctx
from tests.verify_testkit import SimBackend
from verified_data_factory.verification.mutations import run_mutation_checks


def test_backend_exception_evidence_retains_the_actual_safe_reason():
    context = _mutation_ctx("sql.joins.simple", SimBackend())
    def fail(*args, **kwargs):
        raise RuntimeError("sandbox startup unavailable: test marker")
    context.backend.run = fail
    result = run_mutation_checks(context, 3, 1.0)
    assert result.semantic_kills == 0
    assert result.inconclusive == 3
    assert all("test marker" in detail.reason for detail in result.details)
