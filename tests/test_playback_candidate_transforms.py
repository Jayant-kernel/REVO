"""Exact nested playback candidates earn executed AST witnesses, not reference aliases."""
import pytest

from tests.test_stage5_sla_profile import matches
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.public_rule_proofs import public_proofs
from verified_data_factory.verification.qualification.playback_candidate_transforms import (
    candidate_proofs,
    prototypes,
)
from verified_data_factory.verification.qualification.previous_play_profile import CONTRACT


@pytest.mark.parametrize("sql", prototypes())
def test_each_actual_node_transform_discriminates_its_declared_rule(sql):
    task = generate_task(load_builtin_registry().get(CONTRACT, 1), 94001)
    reference, public = public_proofs(task)
    derived = candidate_proofs(sql, reference, public)
    assert derived is not None and set(derived) == set(public)
    for key, proof in derived.items():
        assert matches(task, sql, proof["witness"]), key
        assert not matches(task, proof["wrong_sql"], proof["witness"]), key


@pytest.mark.parametrize("change", [
    lambda sql: sql.replace("LAG(p1.play_id,1)", "LAG(p1.play_id,2)"),
    lambda sql: sql.replace("LAG(p1.play_id,1)", "LEAD(p1.play_id,1)"),
    lambda sql: sql.replace("p1.status='completed'", "TRUE"),
    lambda sql: sql.replace("=2025", "=2024"),
    lambda sql: sql.replace("PARTITION BY p1.viewer_id,p1.title_id", "PARTITION BY p1.viewer_id"),
    lambda sql: sql+" LIMIT 1",
])
def test_unsupported_shape_or_meaning_preserves_abstention(change):
    task = generate_task(load_builtin_registry().get(CONTRACT, 1), 94001)
    reference, public = public_proofs(task)
    assert candidate_proofs(change(prototypes()[0]), reference, public) is None
