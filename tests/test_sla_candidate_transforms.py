"""Real observed model SQL gets candidate-derived, executed clause evidence."""
import pytest

from scripts.phase3_diagnostic import _reference_sql
from tests.test_stage5_sla_profile import matches
from tests.verify_testkit import make_candidate
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.models import VerificationConfig
from verified_data_factory.verification.public_rule_proofs import public_proofs
from verified_data_factory.verification.qualification.sla_candidate_transforms import (
    candidate_proofs,
)
from verified_data_factory.verification.qualification.sla_profile import CONTRACT, alternatives

# Copied verbatim in semantics from the retained real Qwen output; no inference in tests.
MODEL_SQL = """SELECT warehouse, COUNT(*) AS delivered_fulfillments,
SUM(CASE WHEN delivered_at <= promised_at THEN 1 ELSE 0 END) AS on_time_fulfillments
FROM fulfillments WHERE fulfillment_status = 'delivered'
AND shipped_at >= DATE '2025-01-01' AND shipped_at < DATE '2026-01-01'
AND delivered_at IS NOT NULL GROUP BY warehouse ORDER BY warehouse"""


@pytest.mark.parametrize("sql", [MODEL_SQL, alternatives(_reference_sql()[CONTRACT])[1]])
def test_actual_candidate_ast_mutants_discriminate_every_declared_clause(sql):
    task = generate_task(load_builtin_registry().get(CONTRACT, 1), 101010)
    _, public = public_proofs(task)
    proofs = candidate_proofs(sql, public)
    assert proofs is not None and set(proofs) == set(public)
    assert len({proof["wrong_sql"] for proof in proofs.values()}) >= 3
    for key, proof in proofs.items():
        assert proof["wrong_sql"] != sql
        assert matches(task, sql, proof["witness"]), key
        assert not matches(task, proof["wrong_sql"], proof["witness"]), key


@pytest.mark.parametrize("change", ["year", "column", "extra", "window", "or"])
def test_unsupported_or_wrong_structures_never_borrow_public_coverage(change):
    task = generate_task(load_builtin_registry().get(CONTRACT, 1), 101010)
    _, public = public_proofs(task)
    sql = {"year": MODEL_SQL.replace("2025-01-01", "2024-01-01"),
           "column": MODEL_SQL.replace("AS delivered_fulfillments", "AS wrong_name"),
           "extra": MODEL_SQL.replace("SELECT warehouse,", "SELECT warehouse, 1 AS extra,"),
           "window": alternatives(_reference_sql()[CONTRACT])[2],
           "or": MODEL_SQL.replace("AND delivered_at IS NOT NULL", "OR delivered_at IS NOT NULL")}[change]
    assert candidate_proofs(sql, public) is None


def test_real_model_formulation_earns_strong_via_sandbox_and_cap_stays_incomplete(tmp_path):
    task = generate_task(load_builtin_registry().get(CONTRACT, 1), 101010)
    candidate = make_candidate(task, MODEL_SQL)
    sandbox = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(sandbox).execute(task, candidate)
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(sandbox))
    (tmp_path / "model-shape-runtime.json").write_text(result.model_dump_json(indent=2))
    assert result.verdict == "PASS", result.summary
    assert result.verification_strength == "STRONG"
    assert result.mutation.coverage_complete and result.mutation.mutation_score == 1.0
    assert all(detail.candidate_sql_sha256 and detail.retained_executions for detail in result.mutation.details)
    capped = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(sandbox),
                              config=VerificationConfig(max_mutations=1))
    assert capped.verification_strength != "STRONG" and not capped.mutation.coverage_complete
