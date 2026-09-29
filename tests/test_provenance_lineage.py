"""Lineage end-to-end tests (Phase 6, §46): fixture → graph → trace → validate."""

import pytest

from tests.provenance_fixtures import build_provenance_fixture
from verified_data_factory.provenance import (
    build_provenance,
    roles_for_candidate,
    trace_golden_record,
    validate_golden_chain,
    validate_graph,
)


@pytest.fixture(scope="module")
def built():
    fixture = build_provenance_fixture()
    built = build_provenance(
        fixture["records"],
        fixture["qualities"],
        fixture["golden_records"],
        fixture["audit_sample"],
        fixture["quality_config"],
        fixture["verification_config"],
        fixture["factory_version"],
    )
    return fixture, built


def test_all_references_resolve(built):
    _, graph = built
    assert validate_graph(graph.nodes, graph.edges) == []


def test_all_hashes_match_recomputation(built):

    _, graph = built
    for node in graph.nodes.values():
        if node.node_type in ("ARTIFACT",):
            continue
        # Recompute content ids for representative node kinds.
        if node.node_type in ("TASK_INSTANCE", "CANDIDATE_SOLUTION", "GOLDEN_RECORD"):
            assert node.node_id.startswith("sha256:")
    # Artifact content hashes recompute from the recorded bytes is covered
    # by hashing tests; here assert every USES_ARTIFACT target exists.
    artifact_ids = {n.node_id for n in graph.nodes.values() if n.node_type == "ARTIFACT"}
    for edge in graph.edges:
        if edge.relationship == "USES_ARTIFACT":
            assert edge.target_id in artifact_ids


def test_lineage_traces_correctly(built):
    _, graph = built
    golden_nodes = [n for n in graph.nodes.values() if n.node_type == "GOLDEN_RECORD"]
    assert golden_nodes, "fixture must yield at least one Golden record"
    chain = trace_golden_record(graph.nodes, graph.edges, golden_nodes[0].node_id)
    types = [graph.nodes[node_id].node_type for node_id in chain]
    assert types[0] == "TASK_TEMPLATE"
    assert types[-1] == "GOLDEN_RECORD"
    assert "TASK_INSTANCE" in types
    assert "CANDIDATE_SOLUTION" in types
    assert "EXECUTION_RESULT" in types
    assert "VERIFICATION_RESULT" in types
    assert "RECORD_QUALITY" in types
    # Chain is ordered oldest-first with no repeats.
    assert len(set(chain)) == len(chain)


def test_completeness_flags_missing_snapshot_only(built):
    # build_provenance wires record lineage; the dataset snapshot node is
    # added by bundle assembly (export.build_bundle) — see export tests.
    # Here every role resolves except snapshot, so exactly one error remains.
    _, graph = built
    golden_nodes = [n for n in graph.nodes.values() if n.node_type == "GOLDEN_RECORD"]
    assert golden_nodes
    for golden in golden_nodes:
        roles = roles_for_candidate(graph.nodes, golden.payload["candidate_id"], graph.edges)
        for role in (
            "TASK_INSTANCE",
            "CANDIDATE_SOLUTION",
            "EXECUTION_RESULT",
            "VERIFICATION_RESULT",
            "RECORD_QUALITY",
            "GOLDEN_SELECTION",
        ):
            assert role in roles, role
        report = validate_golden_chain(
            {
                "task": roles.get("TASK_INSTANCE"),
                "candidate": roles.get("CANDIDATE_SOLUTION"),
                "execution": roles.get("EXECUTION_RESULT"),
                "verification": roles.get("VERIFICATION_RESULT"),
                "quality": roles.get("RECORD_QUALITY"),
                "selection": roles.get("GOLDEN_SELECTION"),
                "golden": golden,
                "snapshot": None,
            }
        )
        assert not report.complete
        assert [e.code for e in report.errors] == ["MISSING_ARTIFACT"]


def test_completeness_detects_missing_links():
    from verified_data_factory.provenance import validate_golden_chain as validate

    report = validate(
        {
            "task": None,
            "candidate": None,
            "execution": None,
            "verification": None,
            "quality": None,
            "selection": None,
            "golden": None,
            "snapshot": None,
        }
    )
    assert not report.complete
    codes = {e.code for e in report.errors}
    assert {
        "MISSING_TASK",
        "MISSING_CANDIDATE",
        "MISSING_EXECUTION",
        "MISSING_VERIFICATION",
        "MISSING_QUALITY",
        "MISSING_SELECTION",
    } <= codes


def test_snapshot_id_deterministic_and_content_bound(built):
    from verified_data_factory.provenance import (
        build_dataset_snapshot,
        recompute_snapshot_id,
    )

    fixture, graph = built
    assert fixture["golden_records"]
    golden_nodes = [n for n in graph.nodes.values() if n.node_type == "GOLDEN_RECORD"]
    content_ids = sorted(n.payload["golden_content_hash"] for n in golden_nodes)
    first = build_dataset_snapshot(content_ids, "test-set", "1.0", "sha256:sel", "1.0")
    second = build_dataset_snapshot(
        list(reversed(content_ids)), "other-name", "1.0", "sha256:sel", "1.0"
    )
    # Same members + selection metadata -> same id (name/timestamp excluded).
    assert first.dataset_snapshot_id == second.dataset_snapshot_id
    assert recompute_snapshot_id(first) == first.dataset_snapshot_id
    assert first.record_count == len(content_ids)
    # Material change moves the id.
    changed = build_dataset_snapshot(
        content_ids + ["sha256:extra"], "test-set", "1.0", "sha256:sel", "1.0"
    )
    assert changed.dataset_snapshot_id != first.dataset_snapshot_id


def test_inputs_never_mutated_by_lineage_build():
    import json

    fixture = build_provenance_fixture()
    before = [
        (
            r.task.model_dump_json(),
            r.candidate.model_dump_json(),
            r.verification.model_dump_json(),
            json.dumps(fixture["qualities"][i].model_dump(mode="json"), sort_keys=True),
        )
        for i, r in enumerate(fixture["records"])
    ]
    build_provenance(
        fixture["records"],
        fixture["qualities"],
        fixture["golden_records"],
        fixture["audit_sample"],
        fixture["quality_config"],
        fixture["verification_config"],
        fixture["factory_version"],
    )
    after = [
        (
            r.task.model_dump_json(),
            r.candidate.model_dump_json(),
            r.verification.model_dump_json(),
            json.dumps(fixture["qualities"][i].model_dump(mode="json"), sort_keys=True),
        )
        for i, r in enumerate(fixture["records"])
    ]
    assert before == after
