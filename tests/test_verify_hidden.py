"""Hidden-fixture tests: determinism, distinctness, and check outcomes."""

from tests.verify_testkit import SimBackend, make_candidate, make_execution, make_task, oracle_rows
from verified_data_factory.verification import VerificationConfig, get_oracle, verify_candidate
from verified_data_factory.verification.hidden import derive_hidden_seed, run_hidden_checks


def test_hidden_seeds_deterministic_distinct_and_fresh():
    task = make_task("sql.joins.simple")
    seeds = [derive_hidden_seed(task.seed, "1.0", i) for i in range(5)]
    assert len(set(seeds)) == 5
    assert task.seed not in seeds
    assert seeds == [derive_hidden_seed(task.seed, "1.0", i) for i in range(5)]
    assert derive_hidden_seed(task.seed, "2.0", 0) != seeds[0]  # version-sensitive


def test_hidden_checks_pass_for_correct_behavior():
    from tests.verify_sql_samples import CORRECT_SQL

    task = make_task("sql.retention.30_day")
    candidate = make_candidate(task, CORRECT_SQL["sql.retention.30_day"])
    entry = get_oracle(task.template_id, task.template_version)
    backend = SimBackend()
    seeds = [derive_hidden_seed(task.seed, "1.0", i) for i in range(3)]
    result = run_hidden_checks(
        task, candidate, entry.fn, backend, seeds, VerificationConfig().comparison
    )
    assert (result.total, result.passed, result.failed, result.inconclusive) == (3, 3, 0, 0)
    assert result.seeds == seeds  # seeds recorded, never fixture contents
    assert all(c.status == "PASS" for c in result.cases)


def test_hidden_checks_catch_overfit():
    from tests.verify_sql_samples import CORRECT_SQL

    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    entry = get_oracle(task.template_id, task.template_version)
    backend = SimBackend(perturb_labels={"hidden:1"})
    seeds = [derive_hidden_seed(task.seed, "1.0", i) for i in range(3)]
    result = run_hidden_checks(
        task, candidate, entry.fn, backend, seeds, VerificationConfig().comparison
    )
    assert (result.passed, result.failed, result.inconclusive) == (2, 1, 0)
    assert result.cases[1].status == "FAIL"
    assert result.cases[1].failure_code == "HIDDEN_MISMATCH"


def test_hidden_infra_faults_are_inconclusive():
    from tests.verify_sql_samples import CORRECT_SQL

    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    entry = get_oracle(task.template_id, task.template_version)
    backend = SimBackend(fail_labels={"hidden:0"})
    seeds = [derive_hidden_seed(task.seed, "1.0", i) for i in range(2)]
    result = run_hidden_checks(
        task, candidate, entry.fn, backend, seeds, VerificationConfig().comparison
    )
    assert (result.passed, result.failed, result.inconclusive) == (1, 0, 1)
    assert result.cases[0].status == "INCONCLUSIVE"
    assert result.cases[1].status == "PASS"


def test_hidden_zero_cases_config():
    from tests.verify_sql_samples import CORRECT_SQL

    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    config = VerificationConfig(hidden_cases=0, mutation_enabled=False)
    result = verify_candidate(task, candidate, execution, config, SimBackend())
    assert result.verdict == "PASS"
    assert result.hidden is not None and result.hidden.total == 0
