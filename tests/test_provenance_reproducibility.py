"""Reproducibility tests: levels, statuses, snapshots, diffs (Phase 6, §26–§29, §47–48)."""

import pytest

from tests.provenance_fixtures import build_provenance_fixture
from verified_data_factory.provenance import (
    assess_dataset,
    assess_execution,
    assess_generation,
    assess_quality,
    assess_reproducibility,
    assess_task,
    assess_verification,
    build_dataset_snapshot,
    build_provenance,
    recompute_snapshot_id,
    worst_status,
)


@pytest.fixture(scope="module")
def fx():
    return build_provenance_fixture()


@pytest.fixture(scope="module")
def built(fx):
    return build_provenance(
        fx["records"],
        fx["qualities"],
        fx["golden_records"],
        fx["audit_sample"],
        fx["quality_config"],
        fx["verification_config"],
        fx["factory_version"],
    )


def _first_golden(fx, built):
    golden_nodes = [n for n in built.nodes.values() if n.node_type == "GOLDEN_RECORD"]
    assert golden_nodes
    return golden_nodes[0]


def _node_by_type_and_candidate(built, node_type, candidate_id):
    from verified_data_factory.provenance import roles_for_candidate

    roles = roles_for_candidate(built.nodes, candidate_id, built.edges)
    assert node_type in roles, f"no {node_type} node for {candidate_id}"
    return roles[node_type]


def test_task_layer_verified(fx, built):
    golden = _first_golden(fx, built)
    candidate_id = golden.payload["candidate_id"]
    task_node = _node_by_type_and_candidate(built, "TASK_INSTANCE", candidate_id)
    assessment = assess_task(task_node.payload)
    assert assessment.status == "VERIFIED"


def test_task_layer_unknown_when_incomplete():
    assert assess_task({}).status == "UNKNOWN"
    assert "task.seed" in assess_task({"template_id": "t"}).missing_evidence


def test_generation_conditional_not_deterministic(fx, built):
    golden = _first_golden(fx, built)
    candidate_id = golden.payload["candidate_id"]
    candidate_node = _node_by_type_and_candidate(built, "CANDIDATE_SOLUTION", candidate_id)
    model_nodes = [n for n in built.nodes.values() if n.node_type == "MODEL_SNAPSHOT"]
    assert model_nodes
    assessment = assess_generation(
        candidate_node.payload, model_nodes[0].payload, raw_artifact_present=True
    )
    assert assessment.status == "CONDITIONAL"
    assert any("regeneration" in reason for reason in assessment.reasons)


def test_generation_non_replayable_without_artifact(fx, built):
    golden = _first_golden(fx, built)
    candidate_id = golden.payload["candidate_id"]
    candidate_node = _node_by_type_and_candidate(built, "CANDIDATE_SOLUTION", candidate_id)
    assessment = assess_generation(candidate_node.payload, None, raw_artifact_present=False)
    assert assessment.status == "NON_REPLAYABLE"


def test_execution_conditional_with_digest(fx, built):
    golden = _first_golden(fx, built)
    candidate_id = golden.payload["candidate_id"]
    execution_node = _node_by_type_and_candidate(built, "EXECUTION_RESULT", candidate_id)
    payload = dict(execution_node.payload, sandbox_image_digest="sha256:pinned-for-test")
    assessment = assess_execution(payload, environment_present=False)
    assert assessment.status == "CONDITIONAL"
    assert any("host" in reason or "daemon" in reason for reason in assessment.reasons)


def test_execution_not_verified_without_digest(fx, built):
    golden = _first_golden(fx, built)
    candidate_id = golden.payload["candidate_id"]
    execution_node = _node_by_type_and_candidate(built, "EXECUTION_RESULT", candidate_id)
    payload = dict(execution_node.payload, sandbox_image_digest=None)
    assessment = assess_execution(payload, environment_present=False)
    assert assessment.status == "NOT_VERIFIED"
    assert "execution.sandbox_image_digest" in assessment.missing_evidence


def test_verification_and_quality_layers(fx, built):
    golden = _first_golden(fx, built)
    candidate_id = golden.payload["candidate_id"]
    verification_node = _node_by_type_and_candidate(built, "VERIFICATION_RESULT", candidate_id)
    quality_node = _node_by_type_and_candidate(built, "RECORD_QUALITY", candidate_id)
    assert assess_verification(verification_node.payload, True).status == "VERIFIED"
    assert assess_verification({}, False).status == "NOT_VERIFIED"
    assert assess_quality(quality_node.payload, True).status == "VERIFIED"
    assert assess_quality({}, False).status == "NOT_VERIFIED"


def test_dataset_layer_recomputes(fx, built):
    golden_nodes = [n for n in built.nodes.values() if n.node_type == "GOLDEN_RECORD"]
    content_ids = sorted(n.payload["golden_content_hash"] for n in golden_nodes)
    snapshot = build_dataset_snapshot(content_ids, "test-set", "1.0", "sha256:sel", "1.0")
    assert (
        assess_dataset(snapshot.dataset_snapshot_id, recompute_snapshot_id(snapshot)).status
        == "VERIFIED"
    )
    tampered = snapshot.dataset_snapshot_id[:-1] + (
        "0" if snapshot.dataset_snapshot_id[-1] != "0" else "1"
    )
    assert assess_dataset(tampered, recompute_snapshot_id(snapshot)).status == "NOT_VERIFIED"
    assert assess_dataset(None, None).status == "UNKNOWN"


def test_worst_status_ordering():
    assert worst_status(["VERIFIED", "CONDITIONAL"]) == "CONDITIONAL"
    assert worst_status(["VERIFIED", "UNKNOWN"]) == "UNKNOWN"
    assert worst_status(["NOT_VERIFIED", "NON_REPLAYABLE"]) == "NON_REPLAYABLE"
    assert worst_status(["VERIFIED"]) == "VERIFIED"


def test_full_report_honest_statuses(fx, built):
    golden = _first_golden(fx, built)
    candidate_id = golden.payload["candidate_id"]
    task_node = _node_by_type_and_candidate(built, "TASK_INSTANCE", candidate_id)
    candidate_node = _node_by_type_and_candidate(built, "CANDIDATE_SOLUTION", candidate_id)
    execution_node = _node_by_type_and_candidate(built, "EXECUTION_RESULT", candidate_id)
    verification_node = _node_by_type_and_candidate(built, "VERIFICATION_RESULT", candidate_id)
    quality_node = _node_by_type_and_candidate(built, "RECORD_QUALITY", candidate_id)
    model_nodes = [n for n in built.nodes.values() if n.node_type == "MODEL_SNAPSHOT"]
    snapshot = build_dataset_snapshot(
        sorted(
            n.payload["golden_content_hash"]
            for n in built.nodes.values()
            if n.node_type == "GOLDEN_RECORD"
        ),
        "test-set",
        "1.0",
        "sha256:sel",
        "1.0",
    )
    report = assess_reproducibility(
        task_payload=task_node.payload,
        candidate_payload=candidate_node.payload,
        model_payload=model_nodes[0].payload,
        raw_artifact_present=True,
        execution_payload=execution_node.payload,
        environment_present=False,
        verification_payload=verification_node.payload,
        verification_config_present=True,
        quality_payload=quality_node.payload,
        quality_config_present=True,
        snapshot_id=snapshot.dataset_snapshot_id,
        recomputed_snapshot_id=recompute_snapshot_id(snapshot),
    )
    # Fixture executions carry no image digest -> execution NOT_VERIFIED;
    # everything else is pinned, so overall is NOT_VERIFIED (honest, not PASS).
    assert report.overall_status == "NOT_VERIFIED"
    assert report.task_reproducibility.status == "VERIFIED"
    assert report.dataset_reproducibility.status == "VERIFIED"
    assert report.generation_reproducibility.status == "CONDITIONAL"
    assert "execution.sandbox_image_digest" in report.missing_evidence


def test_incomplete_provenance_never_verified():
    report = assess_reproducibility(
        task_payload={},
        candidate_payload={},
        model_payload=None,
        raw_artifact_present=False,
        execution_payload={},
        environment_present=False,
        verification_payload={},
        verification_config_present=False,
        quality_payload={},
        quality_config_present=False,
        snapshot_id=None,
        recomputed_snapshot_id=None,
    )
    assert report.overall_status == "UNKNOWN"
    assert report.missing_evidence
