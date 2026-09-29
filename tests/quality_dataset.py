"""Deterministic Phase 5 fixture dataset (no Docker, no models).

Built from real Phase 1 tasks + real Phase 4 verification with the
oracle-simulating backend. Intentionally contains every pathology the
quality layer must handle: golden material, invalid tasks, FAIL and
INCONCLUSIVE verdicts, exact/structural/semantic duplicates, rare
families, thin edge coverage, contamination pairs, audit magnets, and a
spread of difficulties.
"""

from tests.verify_sql_samples import CORRECT_SQL
from tests.verify_testkit import SimBackend, make_candidate, make_execution, make_task, oracle_rows
from verified_data_factory.quality.models import VerifiedRecord
from verified_data_factory.verification import VerificationConfig, verify_candidate
from verified_data_factory.verification.models import VerificationResult
from verified_data_factory.verification.mutations import applicable_operators

_counter = 0


def _tag(candidate):
    """Give each record a unique candidate_id (suffix preserves grouping)."""
    global _counter
    _counter += 1
    return candidate.model_copy(update={"candidate_id": f"{candidate.candidate_id}-{_counter:02d}"})


def _strong_labels(task, sql):
    return {f"mutation:{op.name}" for op in applicable_operators(task, sql, 20)}


def _verify_pass_strong(task, sql):
    """Verify with a backend that kills every applicable mutant (STRONG)."""
    backend = SimBackend(perturb_labels=_strong_labels(task, sql))
    candidate = _tag(make_candidate(task, sql))
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    verification = verify_candidate(task, candidate, execution, VerificationConfig(), backend)
    return candidate, execution, verification


def _record(task, candidate, execution, verification, role="TRAIN"):
    return VerifiedRecord(
        task=task, candidate=candidate, execution=execution, verification=verification, role=role
    )


def build_fixture_dataset():
    """Return records covering every required pathology. Deterministic."""
    global _counter
    _counter = 0
    records = []

    # 1-3. Golden material: strong PASS across families/difficulties.
    for template_id in ("sql.joins.simple", "sql.aggregation.grouped", "sql.retention.30_day"):
        task = make_task(template_id)
        candidate, execution, verification = _verify_pass_strong(task, CORRECT_SQL[template_id])
        assert verification.verdict == "PASS", template_id
        records.append(_record(task, candidate, execution, verification))

    # 4. Exact duplicate of record 1 (same task, same SQL, distinct id).
    task = make_task("sql.joins.simple")
    sql = CORRECT_SQL["sql.joins.simple"]
    backend = SimBackend(perturb_labels=_strong_labels(task, sql))
    candidate = _tag(make_candidate(task, sql))
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    verification = verify_candidate(task, candidate, execution, VerificationConfig(), backend)
    records.append(_record(task, candidate, execution, verification))

    # 5. Structural duplicate: same task, formatting-only SQL difference.
    task = make_task("sql.joins.simple")
    funny_sql = CORRECT_SQL["sql.joins.simple"].lower().replace(";", " ;")
    candidate, execution, verification = _verify_pass_strong(task, funny_sql)
    records.append(_record(task, candidate, execution, verification))

    # 6. Semantic duplicate: same task, alias-only SQL difference.
    task = make_task("sql.joins.simple")
    alias_sql = CORRECT_SQL["sql.joins.simple"].replace("total_revenue", "rev")
    candidate, execution, verification = _verify_pass_strong(task, alias_sql)
    records.append(_record(task, candidate, execution, verification))

    # 7. FAIL record: perturbed original rows.
    task = make_task("sql.joins.multi")
    candidate = _tag(make_candidate(task, CORRECT_SQL["sql.joins.multi"]))
    columns, rows = oracle_rows(task)
    bad = [list(r) for r in rows]
    bad[0] = list(bad[0])
    bad[0][-1] = "WRONG"
    execution = make_execution(task, candidate, bad, columns)
    verification = verify_candidate(task, candidate, execution, VerificationConfig(), SimBackend())
    assert verification.verdict == "FAIL"
    records.append(_record(task, candidate, execution, verification))

    # 8. INCONCLUSIVE record: truncated execution.
    task = make_task("sql.cte.monthly")
    candidate = _tag(make_candidate(task, CORRECT_SQL["sql.cte.monthly"]))
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns, truncated=True)
    verification = verify_candidate(task, candidate, execution, VerificationConfig(), SimBackend())
    assert verification.verdict == "INCONCLUSIVE"
    records.append(_record(task, candidate, execution, verification))

    # 9. Invalid task: broken schema (fails Task Engine validation).
    task = make_task("sql.windows.ranked")
    broken_tables = {
        name: [{**row, "bogus_col": 1} for row in rows] for name, rows in task.tables.items()
    }
    broken = task.model_copy(update={"tables": broken_tables})
    candidate = _tag(make_candidate(broken, CORRECT_SQL["sql.windows.ranked"]))
    verification = VerificationResult(
        verification_id=f"{candidate.candidate_id}.verify-broken",
        task_id=broken.task_id,
        candidate_id=candidate.candidate_id,
        verdict="INCONCLUSIVE",
        failure_code="ORACLE_ERROR",
        verification_config_version="1.0",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:00+00:00",
    )
    execution = make_execution(broken, candidate, [], ["customer_id"])
    records.append(_record(broken, candidate, execution, verification))

    # 10. Rare family (funnel) + thin edge coverage.
    task = make_task("sql.funnel.completion")
    thin = task.model_copy(update={"edge_cases": []})
    candidate, execution, verification = _verify_pass_strong(
        thin, CORRECT_SQL["sql.funnel.completion"]
    )
    records.append(_record(thin, candidate, execution, verification))

    # 11. PASS with surviving mutants (audit magnet + threshold exclusion).
    task = make_task("sql.dedup.latest")
    candidate = _tag(make_candidate(task, CORRECT_SQL["sql.dedup.latest"]))
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    weak_config = VerificationConfig(mutation_min_score=0.0)
    verification = verify_candidate(task, candidate, execution, weak_config, SimBackend())
    assert verification.verdict == "PASS"
    records.append(_record(task, candidate, execution, verification))

    # 12-13. Contamination pair: identical task, TRAIN vs PRIVATE_EVAL.
    task = make_task("sql.temporal.monthly")
    candidate, execution, verification = _verify_pass_strong(
        task, CORRECT_SQL["sql.temporal.monthly"]
    )
    records.append(_record(task, candidate, execution, verification, role="TRAIN"))
    twin = make_candidate(task, CORRECT_SQL["sql.temporal.monthly"])
    twin = _tag(twin)
    columns, rows = oracle_rows(task)
    twin_execution = make_execution(task, twin, rows, columns)
    twin_verification = verify_candidate(
        task,
        twin,
        twin_execution,
        VerificationConfig(),
        SimBackend(perturb_labels=_strong_labels(task, CORRECT_SQL["sql.temporal.monthly"])),
    )
    records.append(_record(task, twin, twin_execution, twin_verification, role="PRIVATE_EVAL"))

    return records
