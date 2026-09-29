"""Property + metamorphic tests: valid behavior passes, broken fails."""

import pytest

from tests.verify_sql_samples import CORRECT_SQL
from tests.verify_testkit import SimBackend, make_candidate, make_execution, make_task, oracle_rows
from verified_data_factory.verification import VerificationConfig, get_oracle, verify_candidate
from verified_data_factory.verification.errors import OracleError
from verified_data_factory.verification.metamorphic import relations_for_family
from verified_data_factory.verification.models import ComparisonPolicy
from verified_data_factory.verification.properties import PropertyContext, properties_for_family


def _ctx(template_id, backend=None):
    task = make_task(template_id)
    candidate = make_candidate(task, CORRECT_SQL[template_id])
    entry = get_oracle(task.template_id, task.template_version)
    backend = backend if backend is not None else SimBackend()
    return PropertyContext(
        task, candidate, task.tables, entry.fn, backend, ComparisonPolicy(), task.seed
    )


@pytest.mark.parametrize(
    "template_id",
    list(CORRECT_SQL),
)
def test_row_order_invariance_passes(template_id):
    from verified_data_factory.verification.properties import check_row_order_invariance

    outcome = check_row_order_invariance(_ctx(template_id))
    assert outcome.applicable and outcome.passed, (template_id, outcome.detail)


def test_duplicate_invariance_dedup_and_funnel():
    from verified_data_factory.verification.properties import check_duplicate_invariance

    for template_id in ("sql.dedup.latest", "sql.funnel.completion"):
        outcome = check_duplicate_invariance(_ctx(template_id))
        assert outcome.applicable and outcome.passed, (template_id, outcome.detail)


def test_irrelevant_event_retention():
    from verified_data_factory.verification.properties import check_irrelevant_nonqualifying_event

    outcome = check_irrelevant_nonqualifying_event(_ctx("sql.retention.30_day"))
    assert outcome.applicable and outcome.passed, outcome.detail


def test_property_failure_paths():
    from verified_data_factory.verification.properties import run_property_checks

    ctx = _ctx("sql.dedup.latest", SimBackend(perturb_labels={"property:duplicate_invariance"}))
    result = run_property_checks(ctx)
    assert result.failed == 1
    assert result.outcomes[1].property_id == "DUPLICATE_INVARIANCE"


def test_unknown_family_properties_raise():
    with pytest.raises(OracleError):
        properties_for_family("nope")
    with pytest.raises(OracleError):
        relations_for_family("nope")


def test_metamorphic_relations_pass_for_correct_behavior():
    from verified_data_factory.verification.metamorphic import MetamorphicContext

    for template_id in ("sql.joins.simple", "sql.dedup.latest", "sql.retention.30_day"):
        task = make_task(template_id)
        candidate = make_candidate(task, CORRECT_SQL[template_id])
        columns, rows = oracle_rows(task)
        entry = get_oracle(task.template_id, task.template_version)
        expected = entry.fn(dict(task.requirements), task.tables)
        backend = SimBackend()
        ctx = MetamorphicContext(
            task,
            candidate,
            task.tables,
            columns,
            rows,
            expected.order,
            backend,
            ComparisonPolicy(),
            task.seed,
        )
        for fn in relations_for_family(task.family):
            outcome = fn(ctx)
            assert outcome.applicable and outcome.passed, (
                template_id,
                outcome.relation_id,
                outcome.detail,
            )


def test_metamorphic_failure_detected():
    from verified_data_factory.verification.metamorphic import (
        MetamorphicContext,
        run_metamorphic_checks,
    )

    task = make_task("sql.dedup.latest")
    candidate = make_candidate(task, CORRECT_SQL["sql.dedup.latest"])
    columns, rows = oracle_rows(task)
    entry = get_oracle(task.template_id, task.template_version)
    expected = entry.fn(dict(task.requirements), task.tables)
    backend = SimBackend(perturb_labels={"metamorphic:add_duplicate_event"})
    ctx = MetamorphicContext(
        task,
        candidate,
        task.tables,
        columns,
        rows,
        expected.order,
        backend,
        ComparisonPolicy(),
        task.seed,
    )
    result = run_metamorphic_checks(ctx)
    assert result.failed == 1
    assert result.outcomes[1].relation_id == "ADD_DUPLICATE_EVENT"


def test_metamorphic_failure_verdict():
    task = make_task("sql.dedup.latest")
    candidate = make_candidate(task, CORRECT_SQL["sql.dedup.latest"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    backend = SimBackend(perturb_labels={"metamorphic:add_duplicate_event"})
    result = verify_candidate(
        task, candidate, execution, VerificationConfig(mutation_enabled=False), backend
    )
    assert result.verdict == "FAIL"
    assert result.failure_code == "METAMORPHIC_FAILED"
