"""Docker end-to-end verification tests (require a daemon).

Each test runs hand-authored candidate SQL through the REAL Phase 3
sandbox, then verifies with the REAL oracles: correct -> PASS,
characteristic faults -> FAIL, overfit -> hidden FAIL, mutants die.
Skipped with explicit reason when Docker is unavailable.
"""

import pytest

from tests.verify_sql_samples import CORRECT_SQL, WRONG_SQL
from tests.verify_testkit import make_candidate, make_task
from verified_data_factory.sandbox import DockerRunner, SandboxConfig, SandboxExecutor
from verified_data_factory.verification import VerificationConfig, verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend

pytestmark = pytest.mark.integration

from tests.integration.sandbox.test_docker_available import requires_docker


def _verify_end_to_end(template_id, sql, seed=None, config=None):

    task = make_task(template_id, seed)
    candidate = make_candidate(task, sql)
    sandbox_config = SandboxConfig(timeout_seconds=30)
    execution = SandboxExecutor(sandbox_config, DockerRunner(sandbox_config)).execute(
        task, candidate
    )
    backend = DerivedTaskBackend(sandbox_config)
    return verify_candidate(task, candidate, execution, config or VerificationConfig(), backend)


@requires_docker
@pytest.mark.parametrize("template_id", list(CORRECT_SQL))
def test_correct_sql_passes_end_to_end(template_id):
    result = _verify_end_to_end(template_id, CORRECT_SQL[template_id])
    assert result.verdict == "PASS", (template_id, result.summary, result.failure_code)


@requires_docker
@pytest.mark.parametrize("template_id", list(WRONG_SQL))
def test_wrong_sql_fails_end_to_end(template_id):
    result = _verify_end_to_end(template_id, WRONG_SQL[template_id])
    assert result.verdict == "FAIL", (template_id, result.verdict)


@requires_docker
def test_mutants_die_end_to_end():
    from verified_data_factory.verification import get_oracle
    from verified_data_factory.verification.models import ComparisonPolicy
    from verified_data_factory.verification.mutations import (
        MutationContext,
        run_mutation_checks,
    )

    task = make_task("sql.joins.simple")
    backend = DerivedTaskBackend(SandboxConfig(timeout_seconds=30))
    entry = get_oracle(task.template_id, task.template_version)
    expected = entry.fn(dict(task.requirements), task.tables)
    ctx = MutationContext(
        task,
        CORRECT_SQL["sql.joins.simple"],
        task.tables,
        expected,
        backend,
        ComparisonPolicy(),
    )
    result = run_mutation_checks(ctx, max_mutations=20, min_score=0.9)
    assert result.applicable > 0
    assert result.survived == 0, [d for d in result.details if not d.caught]
    assert result.mutation_score == 1.0


@requires_docker
def test_window_partition_swap_is_discriminated_end_to_end():
    """The former surviving partition mutant must now change observable output."""
    from verified_data_factory.verification import get_oracle
    from verified_data_factory.verification.models import ComparisonPolicy
    from verified_data_factory.verification.mutations import MutationContext, run_mutation_checks

    task = make_task("sql.windows.ranked", 601)
    backend = DerivedTaskBackend(SandboxConfig(timeout_seconds=30))
    entry = get_oracle(task.template_id, task.template_version)
    expected = entry.fn(dict(task.requirements), task.tables)
    result = run_mutation_checks(
        MutationContext(
            task,
            CORRECT_SQL["sql.windows.ranked"],
            task.tables,
            expected,
            backend,
            ComparisonPolicy(),
        ),
        max_mutations=20,
        min_score=0.9,
    )
    partition = next(d for d in result.details if d.operator == "partition-column-swap")
    assert partition.caught is True
    assert partition.reason == "result-mismatch"
    assert result.mutation_score == 1.0


@requires_docker
def test_cte_year_filter_drop_is_discriminated_end_to_end():
    """A mutation-only pre-year row prevents a vacuous CTE WHERE-drop check."""
    from verified_data_factory.verification import get_oracle
    from verified_data_factory.verification.models import ComparisonPolicy
    from verified_data_factory.verification.mutations import MutationContext, run_mutation_checks

    task = make_task("sql.cte.monthly", 401)
    backend = DerivedTaskBackend(SandboxConfig(timeout_seconds=30))
    entry = get_oracle(task.template_id, task.template_version)
    expected = entry.fn(dict(task.requirements), task.tables)
    result = run_mutation_checks(
        MutationContext(task, CORRECT_SQL["sql.cte.monthly"], task.tables, expected, backend, ComparisonPolicy()),
        max_mutations=20,
        min_score=0.9,
    )
    where_drop = next(d for d in result.details if d.operator == "where-clause-drop")
    assert where_drop.caught is True
    assert where_drop.reason == "result-mismatch"
    aggregate = next(d for d in result.details if d.operator == "agg-sum-to-avg")
    assert aggregate.caught is True
    assert aggregate.reason == "result-mismatch"
    assert result.mutation_score == 1.0


@requires_docker
def test_oracle_unknown_end_to_end_is_inconclusive(monkeypatch):
    from verified_data_factory.verification import oracle_registry

    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    sandbox_config = SandboxConfig(timeout_seconds=30)
    execution = SandboxExecutor(sandbox_config, DockerRunner(sandbox_config)).execute(
        task, candidate
    )
    assert execution.status == "SUCCEEDED"
    # Hide the oracle after real execution: verifier must not blame the candidate.
    monkeypatch.delitem(
        oracle_registry.ORACLES, (task.template_id, task.template_version), raising=False
    )
    backend = DerivedTaskBackend(sandbox_config)
    result = verify_candidate(task, candidate, execution, VerificationConfig(), backend)
    assert result.verdict == "INCONCLUSIVE"
    assert result.failure_code == "ORACLE_UNKNOWN"
