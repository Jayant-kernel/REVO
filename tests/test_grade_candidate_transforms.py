"""Candidate-derived grade witnesses execute; nearby unsupported shapes abstain."""
import pytest

from scripts.phase3_diagnostic import _reference_sql
from tests.test_stage5_sla_profile import matches
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.public_rule_proofs import public_proofs
from verified_data_factory.verification.qualification.grade_candidate_transforms import (
    candidate_proofs,
    prototypes,
)
from verified_data_factory.verification.qualification.grade_revisions_profile import CONTRACT


@pytest.mark.parametrize("sql", prototypes())
def test_every_transformed_semantic_clause_is_a_real_wrong_answer(sql):
    task = generate_task(load_builtin_registry().get(CONTRACT, 2), 94001)
    reference, public = public_proofs(task)
    derived = candidate_proofs(sql, reference, public)
    assert derived is not None and set(derived) == set(public)
    for key, proof in derived.items():
        if "wrong_sql" in proof:
            assert proof["outcome"] == "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"
            assert matches(task, sql, proof["witness"]), key
            assert not matches(task, proof["wrong_sql"], proof["witness"]), key


@pytest.mark.parametrize("change", [
    lambda sql: sql.replace("revision_status='valid'", "revision_status='cancelled'"),
    lambda sql: sql.replace("recorded_at DESC,revision_id DESC", "revision_id DESC,recorded_at DESC"),
    lambda sql: sql.replace("PARTITION BY student_id,course_id", "PARTITION BY student_id"),
    lambda sql: sql.replace("WHERE rn=1", "WHERE rn<=2"),
    lambda sql: sql.replace("AS rn", "AS other_rank"),
    lambda sql: sql+" LIMIT 1",
])
def test_semantic_or_binding_changes_do_not_borrow_known_shape_proofs(change):
    task = generate_task(load_builtin_registry().get(CONTRACT, 2), 94001)
    reference, public = public_proofs(task)
    assert candidate_proofs(change(prototypes()[0]), reference, public) is None


def test_canonical_formatting_can_earn_its_own_ast_transformations():
    task = generate_task(load_builtin_registry().get(CONTRACT, 2), 94001)
    reference, public = public_proofs(task)
    formatted = _reference_sql()[CONTRACT].replace("SELECT", "select").replace(" FROM ", "\nFROM ")
    assert formatted != reference
    assert candidate_proofs(formatted, reference, public) is not None
