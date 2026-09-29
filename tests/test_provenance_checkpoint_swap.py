"""Checkpoint-swap identity tests (§4 remediation).

A replacement checkpoint must produce new model snapshots, new
configuration identity, and new generation-run identity — never an
ambiguous merge. No claim is made that swapped checkpoints generate
semantically identical data.
"""

from tests.quality_dataset import build_fixture_dataset
from verified_data_factory.generation.generator import build_candidate_id
from verified_data_factory.generation.models import GenerationConfig
from verified_data_factory.provenance import candidate_solution_node, capture_model_snapshot


def _candidate_with_model(model: str, revision: str):
    records = build_fixture_dataset()
    candidate = records[0].candidate
    return candidate.model_copy(update={"model": model, "model_revision": revision})


def test_checkpoint_swap_changes_snapshot_identity():
    old = _candidate_with_model("vendor/model-a:latest", "rev-a")
    new = _candidate_with_model("vendor/model-b:latest", "rev-b")
    assert (
        capture_model_snapshot(old).model_snapshot_id
        != capture_model_snapshot(new).model_snapshot_id
    )


def test_checkpoint_swap_changes_candidate_identity():
    config = GenerationConfig(temperature=0.4, top_p=0.95, max_tokens=2048)
    old_id = build_candidate_id("task-1", "vendor/model-a", "rev-a", "sql-v2", config, 0)
    new_id = build_candidate_id("task-1", "vendor/model-b", "rev-b", "sql-v2", config, 0)
    assert old_id != new_id


def test_candidates_link_explicitly_to_their_snapshot():
    candidate = _candidate_with_model("vendor/model-a:latest", "rev-a")
    snapshot = capture_model_snapshot(candidate)
    node = candidate_solution_node(candidate)
    assert node.payload["model"] == snapshot.model_name
    assert node.payload["model_revision"] == snapshot.model_revision
    assert node.payload["endpoint_id"] == snapshot.endpoint_identifier_hash


def test_same_checkpoint_reproduces_snapshot_identity():
    first = _candidate_with_model("vendor/model-a:latest", "rev-a")
    second = _candidate_with_model("vendor/model-a:latest", "rev-a")
    assert (
        capture_model_snapshot(first).model_snapshot_id
        == capture_model_snapshot(second).model_snapshot_id
    )
