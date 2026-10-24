"""Record + task quality tests: valid, invalid, ambiguous, incomplete."""

from tests.quality_dataset import build_fixture_dataset
from verified_data_factory.quality import analyze_record, assess_task_quality
from verified_data_factory.task_engine import generate_task, load_builtin_registry


def _records():
    return {r.candidate.candidate_id: r for r in build_fixture_dataset()}


def test_valid_task_quality():
    records = _records()
    rec = next(
        r
        for r in records.values()
        if r.task.family == "simple_joins" and r.verification.verdict == "PASS"
    )
    quality = analyze_record(rec)
    assert quality.task_quality.valid
    assert quality.task_quality.semantic_completeness_rate == 1.0
    assert quality.task_quality.schema_consistent
    assert quality.task_quality.instruction_spec_consistent
    assert quality.difficulty == rec.task.difficulty
    assert quality.family == rec.task.family
    assert quality.seed == rec.task.seed


def test_invalid_task_detected():
    records = _records()
    rec = next(r for r in records.values() if r.task.family == "window_functions")
    quality = analyze_record(rec)
    assert not quality.task_quality.valid
    assert quality.task_quality.validation_errors
    assert not quality.task_quality.schema_consistent


def test_ambiguous_task_flagged():
    registry = load_builtin_registry()
    task = generate_task(registry.get("sql.dedup.latest"), 801)
    hedged = task.model_copy(
        update={"instruction": task.instruction + " Use appropriate handling as needed, etc."}
    )
    evidence = assess_task_quality(hedged)
    assert any(f.startswith("hedge-word:") for f in evidence.ambiguity_flags)


def test_incomplete_semantics_detected():
    registry = load_builtin_registry()
    task = generate_task(registry.get("sql.retention.30_day"), 901)
    stripped = task.model_copy(update={"requirements": {"objective": "x"}})
    evidence = assess_task_quality(stripped)
    assert evidence.semantic_completeness_rate < 1.0
    assert "boundary_policy" not in evidence.semantic_present


def test_thin_edge_coverage_measured():
    records = _records()
    rec = next(r for r in records.values() if r.task.family == "funnel")
    quality = analyze_record(rec)
    assert quality.task_quality.edge_cases_expected
    assert quality.task_quality.edge_case_coverage_rate == 0.0


def test_verification_summary_mapping():
    from tests.verify_sql_samples import CORRECT_SQL
    from tests.verify_testkit import make_candidate, make_execution, make_task, oracle_rows
    from verified_data_factory.quality import summarize_verification
    from verified_data_factory.quality.models import VerifiedRecord

    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    from tests.verify_testkit import SimBackend
    from verified_data_factory.verification import VerificationConfig, verify_candidate
    from verified_data_factory.verification.mutations import applicable_operators

    labels = {
        f"mutation:{op.name}"
        for op in applicable_operators(task, CORRECT_SQL["sql.joins.simple"], 20)
    }
    verification = verify_candidate(
        task, candidate, execution, VerificationConfig(), SimBackend(perturb_labels=labels)
    )
    summary = summarize_verification(
        VerifiedRecord(
            task=task, candidate=candidate, execution=execution, verification=verification
        )
    )
    assert summary.verdict == "PASS"
    assert summary.verification_strength == "UNKNOWN"
    assert not verification.mutation.coverage_complete
    assert summary.original_execution_pass
    assert summary.hidden_tests_pass
    assert summary.mutation_status == "SCORED"
    assert summary.mutation_score == 1.0


def test_mutation_not_applicable_not_scored():
    from tests.verify_testkit import (
        SimBackend,
        make_candidate,
        make_execution,
        make_task,
        oracle_rows,
    )
    from verified_data_factory.quality import summarize_verification
    from verified_data_factory.quality.models import VerifiedRecord
    from verified_data_factory.verification import VerificationConfig, verify_candidate

    task = make_task("sql.dedup.latest")
    candidate = make_candidate(task, "SELECT customer_id FROM events;")
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    verification = verify_candidate(task, candidate, execution, VerificationConfig(), SimBackend())
    summary = summarize_verification(
        VerifiedRecord(
            task=task, candidate=candidate, execution=execution, verification=verification
        )
    )
    assert summary.mutation_status == "NOT_APPLICABLE"
    assert summary.mutation_score is None
