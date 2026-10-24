"""Mutation tests: operators fire, scoring is honest, threshold gates."""

import pytest

from tests.test_business_tasks import SQL as BUSINESS_SQL
from tests.verify_sql_samples import CORRECT_SQL
from tests.verify_testkit import SimBackend, make_candidate, make_execution, make_task, oracle_rows
from verified_data_factory.task_engine import load_builtin_registry
from verified_data_factory.verification import VerificationConfig, verify_candidate
from verified_data_factory.verification.models import ComparisonPolicy
from verified_data_factory.verification.qualification import (
    language_titles_profile,
    lowest_quote_profile,
    pareto_shipping_profile,
    queue_batches_profile,
    renewal_coverage_profile,
)
from verified_data_factory.verification.mutations import (
    MutationContext,
    applicable_operators,
    run_mutation_checks,
)


PROFILE_SQL = {
    "sql.dedup.lowest_quote": lowest_quote_profile.REFERENCE,
    "sql.joins.requested_language_titles": language_titles_profile.REFERENCE,
    "sql.subqueries.pareto_shipping": pareto_shipping_profile.REFERENCE,
    "sql.retention.renewal_coverage": renewal_coverage_profile.REFERENCE,
    "sql.windows.queue_batches": queue_batches_profile.REFERENCE,
}


def _mutation_ctx(template_id, backend):
    from verified_data_factory.verification import get_oracle

    task = make_task(template_id)
    entry = get_oracle(task.template_id, task.template_version)
    expected = entry.fn(dict(task.requirements), task.tables)
    return MutationContext(
        task, CORRECT_SQL[template_id], task.tables, expected, backend, ComparisonPolicy()
    )


def test_operators_fire_on_realistic_sql():
    registry = load_builtin_registry()
    assert {template.template_id for template in registry.list()} == set(CORRECT_SQL) | set(BUSINESS_SQL) | set(PROFILE_SQL) | {
        "sql.joins.saas_paid_invoices",
        "sql.aggregation.payment_net_settled",
        "sql.aggregation.support_sla_breaches",
        "sql.dedup.education_grade_revisions",
    }
    for template_id, sql in PROFILE_SQL.items():
        task = make_task(template_id, seed=94001)
        candidate = make_candidate(task, sql)
        assert isinstance(candidate.candidate_sql, str) and candidate.candidate_sql == sql
    for template_id, sql in CORRECT_SQL.items():
        assert registry.get(template_id)
        task = make_task(template_id)
        operators = applicable_operators(task, sql, 20)
        assert operators, f"no applicable mutation for {template_id}"
        for operator in operators:
            mutated = operator.apply(task, sql)
            assert mutated is not None and mutated != sql


def _mutant_labels(task, sql, max_mutations=20):
    from verified_data_factory.verification.mutations import applicable_operators

    return {f"mutation:{op.name}" for op in applicable_operators(task, sql, max_mutations)}


def test_mutation_scoring_all_caught():
    task = make_task("sql.joins.simple")
    labels = _mutant_labels(task, CORRECT_SQL["sql.joins.simple"])
    assert len(labels) >= 3
    ctx = _mutation_ctx("sql.joins.simple", SimBackend(perturb_labels=labels))
    result = run_mutation_checks(ctx, max_mutations=20, min_score=0.9)
    assert result.applicable == len(labels)
    assert (result.caught, result.survived, result.inconclusive) == (len(labels), 0, 0)
    assert result.mutation_score == 1.0


def test_mutation_survivors_reported_not_hidden():
    ctx = _mutation_ctx("sql.joins.simple", SimBackend())
    result = run_mutation_checks(ctx, max_mutations=20, min_score=0.9)
    # SimBackend returns oracle rows for mutants: all survive -> weak suite.
    assert result.survived == result.applicable > 0
    assert result.mutation_score == 0.0
    assert all(not d.caught for d in result.details)


def test_mutation_threshold_gates_pass_to_inconclusive():
    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    # All mutants survive -> score 0 < 0.9 -> INCONCLUSIVE, never FAIL.
    result = verify_candidate(task, candidate, execution, VerificationConfig(), SimBackend())
    assert result.verdict == "INCONCLUSIVE"
    assert result.failure_code == "WEAK_SUITE"
    assert result.verification_strength == "WEAK"
    assert result.mutation is not None and result.mutation.mutation_score == 0.0


def test_generic_kills_preserve_pass_but_do_not_prove_public_rule_coverage():
    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    backend = SimBackend(perturb_labels=_mutant_labels(task, CORRECT_SQL["sql.joins.simple"]))
    result = verify_candidate(task, candidate, execution, VerificationConfig(), backend)
    assert result.verdict == "PASS", result.summary
    assert result.verification_strength == "UNKNOWN"
    assert result.mutation is not None and result.mutation.mutation_score == 1.0
    assert result.mutation.semantic_kills >= 3
    assert result.mutation.required_rules
    assert not result.mutation.covered_rules
    assert not result.mutation.coverage_complete


@pytest.mark.parametrize("template_id", list(CORRECT_SQL))
def test_full_default_config_pass_all_families(template_id):
    """Every family reaches PASS under the default config (simulated execution)."""
    task = make_task(template_id)
    candidate = make_candidate(task, CORRECT_SQL[template_id])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    backend = SimBackend(perturb_labels=_mutant_labels(task, CORRECT_SQL[template_id]))
    result = verify_candidate(task, candidate, execution, VerificationConfig(), backend)
    assert result.verdict == "PASS", (template_id, result.summary, result.failure_code)
    assert result.verification_strength in ("STRONG", "UNKNOWN")


def test_no_applicable_mutations_is_not_applicable():
    task = make_task("sql.dedup.latest")
    columns, rows = oracle_rows(task)
    # Candidate without any operator trigger text: SQL has no ASC/DESC/threshold.
    plain = make_candidate(task, "SELECT customer_id FROM events;")
    plain_execution = make_execution(task, plain, rows, columns)
    backend = SimBackend()
    result = verify_candidate(task, plain, plain_execution, VerificationConfig(), backend)
    assert result.mutation is not None
    assert result.mutation.applicable == 0
    assert result.mutation.mutation_score is None
    assert result.verdict == "PASS"
    assert result.verification_strength == "UNKNOWN"


def test_max_mutations_cap_respected():
    ctx = _mutation_ctx("sql.joins.simple", SimBackend())
    result = run_mutation_checks(ctx, max_mutations=1, min_score=0.9)
    assert result.run == 1
    assert len(result.details) == 1


def test_inconclusive_mutants_excluded_from_score():
    ctx = _mutation_ctx("sql.joins.simple", SimBackend(fail_labels={"mutation:order-flip"}))
    operators = applicable_operators(ctx.task, ctx.candidate_sql, 20)
    names = [o.name for o in operators]
    assert "order-flip" in names
    result = run_mutation_checks(ctx, max_mutations=20, min_score=0.0)
    assert result.inconclusive == 1
    decided = result.caught + result.survived
    assert decided == result.applicable - 1


def test_non_executing_mutant_is_invalid_and_never_raises_score():
    class InvalidMutantBackend(SimBackend):
        def run(self, task, candidate, tables, label):
            if label == "mutation:order-flip":
                columns, rows = oracle_rows(task, tables)
                return make_execution(task, candidate, rows, columns, status="EXECUTION_ERROR")
            return super().run(task, candidate, tables, label)

    ctx = _mutation_ctx("sql.joins.simple", InvalidMutantBackend())
    result = run_mutation_checks(ctx, max_mutations=20, min_score=0.0)
    assert result.invalid == 1
    assert result.semantic_kills == result.caught == 0
    assert result.mutation_score == 0.0
    invalid = next(d for d in result.details if d.operator == "order-flip")
    assert invalid.classification == "INVALID_MUTANT"
    assert invalid.caught is False


def test_drop_where_respects_parenthesis_scope():
    from verified_data_factory.verification.mutations import _op_drop_where

    task = make_task("sql.cte.monthly")
    cte = (
        "WITH t AS (SELECT customer_id FROM orders "
        "WHERE order_date >= DATE '2025-01-01') "
        "SELECT customer_id FROM t ORDER BY customer_id"
    )
    mutated = _op_drop_where(task, cte)
    assert mutated is not None
    assert "WHERE" not in mutated.upper()
    assert mutated.count("(") == mutated.count(")")
    assert mutated.upper().rstrip().endswith("ORDER BY CUSTOMER_ID")
    subquery = (
        "SELECT customer_id FROM (SELECT customer_id FROM orders WHERE amount > 5) x "
        "ORDER BY customer_id"
    )
    sub_mutated = _op_drop_where(task, subquery)
    assert sub_mutated is not None
    assert sub_mutated.count("(") == sub_mutated.count(")")
