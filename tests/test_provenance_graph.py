"""Graph tests: nodes, edges, store, immutability, validation (Phase 6, §6+§11+§31-33)."""

import pytest

from verified_data_factory.provenance import (
    ProvenanceStore,
    find_cycles,
    make_edge,
    make_node,
    orphans,
    validate_edge_types,
    validate_graph,
)
from verified_data_factory.provenance.errors import StoreError


def _node(node_type="TASK_INSTANCE", payload=None):
    return make_node(node_type, payload or {"task_id": "t1"})


def test_valid_node_edge_construction():
    task = _node("TASK_INSTANCE", {"task_id": "t1"})
    run = _node("GENERATION_RUN", {"task_id": "t1"})
    assert task.node_id.startswith("sha256:")
    edge = make_edge(task.node_id, "GENERATED_BY", run.node_id)
    assert edge.edge_id.startswith("sha256:")
    problems = validate_graph({task.node_id: task, run.node_id: run}, [edge])
    assert problems == []


def test_missing_node_detection():
    task = _node()
    edge = make_edge(task.node_id, "GENERATED_BY", "sha256:missing")
    problems = validate_graph({task.node_id: task}, [edge])
    assert any("missing" in problem for problem in problems)


def test_invalid_relationship_detection():
    with pytest.raises(StoreError):
        make_edge("sha256:a", "NOT_A_RELATION", "sha256:b")


def test_invalid_direction_detection():
    candidate = _node("CANDIDATE_SOLUTION", {"candidate_id": "c1"})
    task = _node("TASK_INSTANCE", {"task_id": "t1"})
    # Backwards: candidates do not generate tasks.
    edge = make_edge(candidate.node_id, "GENERATED_BY", task.node_id)
    problems = validate_edge_types([edge], {candidate.node_id: candidate, task.node_id: task})
    assert len(problems) == 1 and "GENERATED_BY" in problems[0]


def test_duplicate_id_conflict_detection():
    first = make_node("TASK_INSTANCE", {"task_id": "t1"})
    assert first.node_id == make_node("TASK_INSTANCE", {"task_id": "t1"}).node_id
    # Same content under a different type is a different id (no conflict).
    other = make_node("CANDIDATE_SOLUTION", {"task_id": "t1"})
    assert other.node_id != first.node_id


def test_orphan_detection():
    connected = _node("TASK_INSTANCE", {"task_id": "t1"})
    run = _node("GENERATION_RUN", {"task_id": "t1"})
    edge = make_edge(connected.node_id, "GENERATED_BY", run.node_id)
    lonely = _node("GOLDEN_RECORD", {"candidate_id": "c9"})
    nodes = {n.node_id: n for n in (connected, run, lonely)}
    assert orphans(nodes, [edge]) == [lonely.node_id]


def test_cycle_detection():
    a = _node("TASK_INSTANCE", {"task_id": "a"})
    b = _node("GENERATION_RUN", {"task_id": "a"})
    forward = make_edge(a.node_id, "GENERATED_BY", b.node_id)
    assert find_cycles([forward]) == []
    back = make_edge(b.node_id, "DERIVED_FROM", a.node_id)
    cycles = find_cycles([forward, back])
    assert len(cycles) == 1 and set(cycles[0]) == {a.node_id, b.node_id}


def test_store_append_get_query_validate(tmp_path):
    store = ProvenanceStore(tmp_path / "store")
    task = _node("TASK_INSTANCE", {"task_id": "t1"})
    run = _node("GENERATION_RUN", {"task_id": "t1"})
    store.append_node(task)
    store.append_node(run)
    edge = make_edge(task.node_id, "GENERATED_BY", run.node_id)
    store.append_edge(edge)
    assert store.get_node(task.node_id) == task
    assert store.get_node("sha256:nope") is None
    assert store.validate_references() == []
    lineage = store.lineage(task.node_id)
    assert run.node_id in lineage["down"]
    assert store.lineage(run.node_id)["up"] == [task.node_id]
    with pytest.raises(StoreError):
        store.lineage(task.node_id, direction="sideways")
    assert store.counts() == {"nodes": 2, "edges": 1, "activities": 0}


def test_store_immutability(tmp_path):
    store = ProvenanceStore(tmp_path / "store")
    node = _node("TASK_INSTANCE", {"task_id": "t1"})
    store.append_node(node)
    # Identical re-append is idempotent.
    store.append_node(_node("TASK_INSTANCE", {"task_id": "t1"}))
    assert store.counts()["nodes"] == 1
    # Same id + different payload is rejected (crafted via model_copy).
    tampered = node.model_copy(update={"payload": {"task_id": "t1", "extra": True}})
    assert tampered.node_id == node.node_id
    with pytest.raises(StoreError):
        store.append_node(tampered)
    # Reloading from disk preserves history (append-only persistence).
    reopened = ProvenanceStore(tmp_path / "store")
    assert reopened.counts()["nodes"] == 1
    assert reopened.get_node(node.node_id) == node


def test_store_rejects_dangling_edges(tmp_path):
    store = ProvenanceStore(tmp_path / "store")
    task = _node()
    store.append_node(task)
    with pytest.raises(StoreError):
        store.append_edge(make_edge(task.node_id, "GENERATED_BY", "sha256:ghost"))


def test_store_export_graph_sorted(tmp_path):
    store = ProvenanceStore(tmp_path / "store")
    for suffix in ("b", "a"):
        store.append_node(_node("TASK_INSTANCE", {"task_id": suffix}))
    exported = store.export_graph()
    ids = [n["node_id"] for n in exported["nodes"]]
    assert ids == sorted(ids)
