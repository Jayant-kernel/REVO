from tests.test_verify_mutations import _mutation_ctx
from tests.verify_sql_samples import CORRECT_SQL
from tests.verify_testkit import SimBackend, make_candidate, make_execution, make_task, oracle_rows
from verified_data_factory.verification import VerificationConfig, verify_candidate
from verified_data_factory.verification.mutations import applicable_operators


def test_a_single_semantic_kill_cannot_establish_strong_verification():
    task = make_task("sql.joins.simple")
    sql = CORRECT_SQL[task.template_id]
    candidate = make_candidate(task, sql)
    columns, rows = oracle_rows(task)
    labels = {f"mutation:{o.name}" for o in applicable_operators(task, sql, 20)}
    outcome = verify_candidate(task, candidate, make_execution(task, candidate, rows, columns),
                               VerificationConfig(max_mutations=1), SimBackend(perturb_labels=labels))
    assert outcome.mutation is not None
    assert outcome.mutation.mutation_score == 1.0
    assert outcome.verification_strength != "STRONG"


def test_execution_alone_does_not_attribute_generic_mutants_to_public_rules():
    from verified_data_factory.verification.mutations import run_mutation_checks
    context = _mutation_ctx("sql.joins.simple", SimBackend())
    result = run_mutation_checks(context, 20, 1.0)
    assert result.run == len(result.details) > 0
    assert result.required_rules
    assert all(not detail.rule_ids for detail in result.details)
    assert result.covered_rules == []
    assert not result.coverage_complete


def test_where_drop_does_not_treat_exception_literal_as_except_clause():
    from verified_data_factory.verification.mutations import OPERATORS
    task = make_task("sql.joins.simple")
    sql = "WITH x AS (SELECT * FROM events WHERE event_type='exception') SELECT * FROM x"
    mutated = OPERATORS["where-clause-drop"].apply(task, sql)
    assert mutated is not None
    assert "exception" not in mutated
    assert "FROM events" in mutated
    assert mutated.count("(") == mutated.count(")")
