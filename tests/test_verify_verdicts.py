"""Verdict tests: known-correct -> PASS, known-incorrect -> FAIL (§57.1-9).

Correctness here means behavior simulated from the oracle (SimBackend);
hand-perturbed rows stand in for genuinely wrong candidates. Real SQL
execution of these scenarios lives in Docker integration tests.
"""

import pytest

from tests.verify_sql_samples import CORRECT_SQL
from tests.verify_testkit import SimBackend, make_candidate, make_execution, make_task, oracle_rows
from verified_data_factory.task_engine import canonical_json
from verified_data_factory.verification import VerificationConfig, verify_candidate
from verified_data_factory.verification.models import OracleOutcome


def _correct_triple(template_id, backend=None):
    task = make_task(template_id)
    candidate = make_candidate(task, CORRECT_SQL[template_id])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    return task, candidate, execution


def _verify(template_id, perturb_original=False, backend=None, config=None):
    task, candidate, execution = _correct_triple(template_id)
    if perturb_original:
        columns, rows = oracle_rows(task)
        bad = [list(r) for r in rows]
        if bad:
            bad[0] = list(bad[0])
            bad[0][-1] = "WRONG"
        else:
            bad = [["WRONG"]]
        execution = make_execution(task, candidate, bad, columns)
    backend = backend or SimBackend()
    return verify_candidate(task, candidate, execution, config, backend), backend


@pytest.mark.parametrize("template_id", list(CORRECT_SQL))
def test_correct_candidates_pass_without_mutation_stage(template_id):
    config = VerificationConfig(mutation_enabled=False)
    result, _backend = _verify(template_id, config=config)
    assert result.verdict == "PASS", (template_id, result.summary)
    assert result.failure_code is None
    assert result.verification_strength in ("STRONG", "UNKNOWN")
    assert result.hidden is not None and result.hidden.failed == 0
    assert result.properties is not None and result.properties.failed == 0
    assert result.metamorphic is not None and result.metamorphic.failed == 0


@pytest.mark.parametrize("template_id", list(CORRECT_SQL))
def test_incorrect_candidates_fail_on_original(template_id):
    result, backend = _verify(
        template_id, perturb_original=True, config=VerificationConfig(mutation_enabled=False)
    )
    assert result.verdict == "FAIL"
    assert result.failure_code == "RESULT_MISMATCH"
    assert backend.labels("hidden:") == []  # early exit: no wasted hidden runs
    assert result.hidden is None


def test_wrong_null_behavior_fails():
    task = make_task("sql.aggregation.grouped")
    candidate = make_candidate(task, "SELECT 1;")
    columns, rows = oracle_rows(task)
    bad = []
    for r in rows:
        r = list(r)
        if r[2] is None or r[3] is None:
            r[2], r[3] = 0.0, 0.0  # NULL-blind candidate: zeros instead of NULLs
        bad.append(r)
    execution = make_execution(task, candidate, bad, columns)
    result = verify_candidate(
        task, candidate, execution, VerificationConfig(mutation_enabled=False), SimBackend()
    )
    if bad != [list(r) for r in rows]:
        assert result.verdict == "FAIL"
        assert result.failure_code == "RESULT_MISMATCH"


def test_execution_faults_are_candidate_fails():
    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    for status, code in [
        ("TIMEOUT", "EXECUTION_FAILED"),
        ("RESOURCE_LIMIT", "EXECUTION_FAILED"),
        ("EXECUTION_ERROR", "EXECUTION_FAILED"),
        ("POLICY_REJECTED", "POLICY_REJECTED"),
    ]:
        execution = make_execution(task, candidate, rows, columns, status=status)
        result = verify_candidate(task, candidate, execution, VerificationConfig(), SimBackend())
        assert result.verdict == "FAIL", status
        assert result.failure_code == code, status


def test_infra_outcomes_are_inconclusive_not_blame():
    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns, status="SANDBOX_ERROR")
    result = verify_candidate(task, candidate, execution, VerificationConfig(), SimBackend())
    assert result.verdict == "INCONCLUSIVE"
    assert result.failure_code == "SANDBOX_INFRA_ERROR"
    truncated = make_execution(task, candidate, rows, columns, truncated=True)
    result = verify_candidate(task, candidate, truncated, VerificationConfig(), SimBackend())
    assert result.verdict == "INCONCLUSIVE"
    assert result.failure_code == "TRUNCATED_RESULT"


def test_binding_mismatch_is_invalid_input():
    task = make_task("sql.joins.simple")
    other = make_task("sql.joins.simple", seed=102)
    candidate = make_candidate(other, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    result = verify_candidate(task, candidate, execution, VerificationConfig(), SimBackend())
    assert result.verdict == "FAIL"
    assert result.failure_code == "INVALID_INPUT"


def test_oracle_unknown_is_inconclusive():
    # Binding keys on task_id, so a renamed template with matching binding
    # reaches the oracle gate: unregistered -> INCONCLUSIVE, never FAIL.
    task = make_task("sql.joins.simple")
    columns, rows = oracle_rows(task)
    ghost = task.model_copy(update={"template_id": "sql.ghost.unknown"})
    ghost_candidate = make_candidate(ghost, CORRECT_SQL["sql.joins.simple"])
    ghost_execution = make_execution(ghost, ghost_candidate, rows, columns,
                                     column_types=["INTEGER", "DOUBLE"])
    result = verify_candidate(
        ghost, ghost_candidate, ghost_execution, VerificationConfig(), SimBackend()
    )
    assert result.verdict == "INCONCLUSIVE"
    assert result.failure_code == "ORACLE_UNKNOWN"


def test_oracle_crash_is_inconclusive(monkeypatch):
    import verified_data_factory.verification.verifier as verifier_mod

    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)

    def boom(*args, **kwargs):
        raise RuntimeError("oracle exploded")

    monkeypatch.setattr(
        verifier_mod,
        "compute_oracle",
        lambda task: OracleOutcome(ok=False, error="RuntimeError: oracle exploded"),
    )
    result = verify_candidate(task, candidate, execution, VerificationConfig(), SimBackend())
    assert result.verdict == "INCONCLUSIVE"
    assert result.failure_code == "ORACLE_ERROR"


def test_overfit_candidate_caught_by_hidden():
    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    backend = SimBackend(perturb_labels={"hidden:0", "hidden:1", "hidden:2"})
    result = verify_candidate(
        task,
        candidate,
        execution,
        VerificationConfig(hidden_cases=3, mutation_enabled=False),
        backend,
    )
    assert result.verdict == "FAIL"
    assert result.failure_code == "HIDDEN_MISMATCH"
    assert result.hidden is not None and result.hidden.failed == 3


def test_inputs_never_mutated():
    task = make_task("sql.retention.30_day")
    candidate = make_candidate(task, CORRECT_SQL["sql.retention.30_day"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    before = (canonical_json(task), candidate.model_dump_json(), execution.model_dump_json())
    verify_candidate(task, candidate, execution, VerificationConfig(), SimBackend())
    assert (
        canonical_json(task),
        candidate.model_dump_json(),
        execution.model_dump_json(),
    ) == before


def test_verification_reproducible():
    task = make_task("sql.funnel.completion")
    candidate = make_candidate(task, CORRECT_SQL["sql.funnel.completion"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    config = VerificationConfig(mutation_enabled=False)
    first = verify_candidate(task, candidate, execution, config, SimBackend())
    second = verify_candidate(task, candidate, execution, config, SimBackend())
    assert first.verdict == second.verdict == "PASS"
    assert first.verification_id == second.verification_id
    assert first.hidden == second.hidden
    assert first.comparison == second.comparison
