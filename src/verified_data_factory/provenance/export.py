"""Provenance bundle export (Phase 6, §36–§37).

Deterministic layout (stable ordering, canonical JSON, UTF-8, LF):

    manifest.json            RunManifest
    reproduction.json        ReproductionManifest
    snapshot.json            DatasetSnapshot
    nodes.jsonl              ProvenanceNode records (node_id order)
    edges.jsonl              ProvenanceEdge records (edge_id order)
    activities.jsonl         ProvenanceActivity records (run_id order)
    artifacts.jsonl          ArtifactRef records (artifact_id order)
    golden_records.jsonl     GoldenRecord dicts (candidate_id order)
    reproducibility.json     ReproducibilityReport (per golden record)
    completeness.json        ProvenanceCompletenessReport list

``export_provenance_bundle`` writes from in-memory objects; ``read_bundle``
reads a directory back for round-trip validation; ``build_bundle`` runs
the whole assembly (graph → snapshot → manifests → reports) in one
deterministic pass. No absolute host paths enter identity fields —
artifact locators are relative logical paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .activities import build_run_manifest, finish_activity, start_activity, utc_now_iso
from .completeness import validate_golden_chain
from .dataset_snapshot import build_dataset_snapshot, recompute_snapshot_id
from .edges import make_edge
from .environment import capture_environment_snapshot
from .lineage import build_provenance, roles_for_candidate
from .manifests import build_reproduction_manifest
from .models import (
    ArtifactRef,
    DatasetSnapshot,
    ProvenanceActivity,
    ProvenanceCompletenessReport,
    ProvenanceEdge,
    ProvenanceNode,
    ReproducibilityReport,
    RunManifest,
)
from .reproducibility import assess_reproducibility
from .source import capture_source_snapshot

BUNDLE_FILES = (
    "manifest.json",
    "reproduction.json",
    "snapshot.json",
    "nodes.jsonl",
    "edges.jsonl",
    "activities.jsonl",
    "artifacts.jsonl",
    "golden_records.jsonl",
    "reproducibility.json",
    "completeness.json",
)


def _write_json(path: Path, payload: Any) -> None:
    from .canonical import canonical_json

    path.write_text(canonical_json(payload) + "\n", encoding="utf-8", newline="\n")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    from .canonical import canonical_json

    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(canonical_json(record) + "\n" for record in records)


def export_provenance_bundle(
    out_dir: str | Path,
    manifest: RunManifest,
    reproduction: dict[str, Any],
    snapshot: DatasetSnapshot,
    nodes: list[ProvenanceNode],
    edges: list[ProvenanceEdge],
    activities: list[ProvenanceActivity],
    artifacts: list[ArtifactRef],
    golden_records: list[dict[str, Any]],
    reproducibility: dict[str, ReproducibilityReport],
    completeness: list[ProvenanceCompletenessReport],
    artifact_payloads: dict[str, bytes] | None = None,
) -> dict[str, str]:
    """Write the full bundle; returns logical-name → path mapping."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_json(out / "manifest.json", manifest.model_dump(mode="json"))
    _write_json(out / "reproduction.json", reproduction)
    _write_json(out / "snapshot.json", snapshot.model_dump(mode="json"))
    _write_jsonl(
        out / "nodes.jsonl",
        [n.model_dump(mode="json") for n in sorted(nodes, key=lambda n: n.node_id)],
    )
    _write_jsonl(
        out / "edges.jsonl",
        [e.model_dump(mode="json") for e in sorted(edges, key=lambda e: e.edge_id)],
    )
    _write_jsonl(
        out / "activities.jsonl",
        [a.model_dump(mode="json") for a in sorted(activities, key=lambda a: a.run_id)],
    )
    _write_jsonl(
        out / "artifacts.jsonl",
        [a.model_dump(mode="json") for a in sorted(artifacts, key=lambda a: a.artifact_id)],
    )
    _write_jsonl(
        out / "golden_records.jsonl",
        sorted(golden_records, key=lambda g: g.get("candidate_id", "")),
    )
    _write_json(
        out / "reproducibility.json",
        {k: v.model_dump(mode="json") for k, v in sorted(reproducibility.items())},
    )
    # Completeness is one JSON array (not JSONL): a single valid document
    # regardless of golden count, so read-back is unambiguous.
    _write_json(out / "completeness.json", [c.model_dump(mode="json") for c in completeness])
    if artifact_payloads is not None:
        from .hashing import hash_bytes

        by_locator = {artifact.relative_locator: artifact for artifact in artifacts}
        missing = sorted(set(by_locator) - set(artifact_payloads))
        if missing:
            raise ValueError(f"artifact payloads missing for locators: {missing}")
        for locator, artifact in sorted(by_locator.items()):
            data = artifact_payloads[locator]
            if len(data) != artifact.size_bytes or hash_bytes(data) != artifact.content_hash:
                raise ValueError(f"artifact payload does not match reference: {locator}")
            destination = out / locator
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    return {name: str(out / name) for name in BUNDLE_FILES}


def build_bundle(
    records: Any,
    qualities: Any,
    golden_records: Any,
    audit_sample: Any,
    quality_config: dict[str, Any],
    verification_config: dict[str, Any] | None,
    factory_version: str,
    dataset_name: str,
    repo_root: str | Path = ".",
    source_scope: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble every bundle part deterministically (graph → snapshot → reports).

    Returns a dict with ``nodes``, ``edges``, ``activities``,
    ``artifacts``, ``golden`` (dicts), ``snapshot``, ``manifest``,
    ``reproduction``, ``reproducibility`` (per golden candidate_id),
    ``    completeness`` (per golden), ``source``, and ``environment``.
    """
    started = utc_now_iso()
    activity = start_activity("PROVENANCE_RUN", "1.0")
    source = capture_source_snapshot(
        repo_root, source_scope or ["src/verified_data_factory", "pyproject.toml", "configs/"]
    )
    environment = capture_environment_snapshot(repo_root)
    built = build_provenance(
        records,
        qualities,
        golden_records,
        audit_sample,
        quality_config,
        verification_config,
        factory_version,
        source=source,
        environment=environment,
    )

    content_ids = sorted(g.record_id for g in golden_records)
    quality_version = str(quality_config.get("quality_engine_version", "1.0"))
    selection_id = next(
        (n.node_id for n in built.nodes.values() if n.node_type == "GOLDEN_SELECTION"),
        "sha256:missing",
    )
    snapshot = build_dataset_snapshot(
        content_ids, dataset_name, "1.0", selection_id, quality_version
    )
    snapshot_node = _snapshot_carrier(snapshot)
    built.nodes[snapshot_node.node_id] = snapshot_node
    for golden in [n for n in built.nodes.values() if n.node_type == "GOLDEN_RECORD"]:
        edge = _included_in_edge(golden.node_id, snapshot_node.node_id)
        if edge.edge_id not in {e.edge_id for e in built.edges}:
            built.edges.append(edge)

    manifest = build_run_manifest(
        activity.run_id,
        factory_version,
        "provenance",
        {"provenance": "1.0", "quality": quality_version},
        source.source_snapshot_id,
        environment.dependency_lock_hash,
        environment.environment_snapshot_id,
        started,
        utc_now_iso(),
    )
    model_payloads = [n.payload for n in built.nodes.values() if n.node_type == "MODEL_SNAPSHOT"]
    config_payloads = [n.payload for n in built.nodes.values() if n.node_type == "CONFIGURATION"]
    reproduction = build_reproduction_manifest(
        snapshot.dataset_snapshot_id,
        factory_version,
        source.model_dump(mode="json"),
        {"dependency_lock_hash": environment.dependency_lock_hash},
        environment.model_dump(mode="json"),
        model_payloads,
        config_payloads,
        sorted({r.task.task_id for r in records}),
        sorted({r.candidate.candidate_id for r in records}),
        sorted({r.verification.verification_id for r in records}),
        sorted({q.candidate_id for q in qualities}),
        content_ids,
        [a.model_dump(mode="json") for a in built.artifacts],
        {},
    )

    reproducibility = {}
    completeness = []
    for golden in [n for n in built.nodes.values() if n.node_type == "GOLDEN_RECORD"]:
        candidate_id = golden.payload["candidate_id"]
        roles = roles_for_candidate(built.nodes, candidate_id, built.edges)
        completeness.append(
            validate_golden_chain(
                {
                    "task": roles.get("TASK_INSTANCE"),
                    "candidate": roles.get("CANDIDATE_SOLUTION"),
                    "execution": roles.get("EXECUTION_RESULT"),
                    "verification": roles.get("VERIFICATION_RESULT"),
                    "quality": roles.get("RECORD_QUALITY"),
                    "selection": roles.get("GOLDEN_SELECTION"),
                    "golden": golden,
                    "snapshot": snapshot_node,
                }
            )
        )
        reproducibility[candidate_id] = assess_reproducibility(
            task_payload=_role_payload(roles, "TASK_INSTANCE"),
            candidate_payload=_role_payload(roles, "CANDIDATE_SOLUTION"),
            model_payload=_first_model_payload(built),
            raw_artifact_present=_has_artifact(built, candidate_id, ".raw.txt"),
            execution_payload=_role_payload(roles, "EXECUTION_RESULT"),
            environment_present=True,
            verification_payload=_role_payload(roles, "VERIFICATION_RESULT"),
            verification_config_present=_has_config(built, "verification"),
            quality_payload=_role_payload(roles, "RECORD_QUALITY"),
            quality_config_present=_has_config(built, "quality"),
            snapshot_id=snapshot.dataset_snapshot_id,
            recomputed_snapshot_id=recompute_snapshot_id(snapshot),
        )

    finished_activity = finish_activity(activity, "SUCCEEDED")
    return {
        "nodes": built.nodes,
        "edges": built.edges,
        "activities": [*built.activities, finished_activity],
        "artifacts": built.artifacts,
        "golden": [g.model_dump(mode="json", by_alias=True) for g in golden_records],
        "snapshot": snapshot,
        "snapshot_node": snapshot_node,
        "manifest": manifest,
        "reproduction": reproduction,
        "reproducibility": reproducibility,
        "completeness": completeness,
        "source": source,
        "environment": environment,
        "selection_id": selection_id,
        "artifact_payloads": _artifact_payloads(records, golden_records),
    }


def _artifact_payloads(records: Any, golden_records: Any) -> dict[str, bytes]:
    """Materialize every relative artifact reference for a self-contained bundle."""
    payloads: dict[str, bytes] = {}
    for record in records:
        candidate_id = record.candidate.candidate_id
        payloads[f"artifacts/{candidate_id}.raw.txt"] = record.candidate.raw_response.encode("utf-8")
        payloads[f"artifacts/{candidate_id}.sql"] = (record.candidate.candidate_sql or "").encode(
            "utf-8"
        )
    for golden in golden_records:
        payloads[f"golden_records/{golden.candidate_id}.golden.json"] = golden.model_dump_json(
            by_alias=True
        ).encode("utf-8")
    return payloads


def _role_payload(roles: dict[str, Any], node_type: str) -> dict[str, Any]:
    node = roles.get(node_type)
    return dict(node.payload) if node is not None else {}


def _first_model_payload(built: Any) -> dict[str, Any] | None:
    for node in built.nodes.values():
        if node.node_type == "MODEL_SNAPSHOT":
            return dict(node.payload)
    return None


def _has_artifact(built: Any, candidate_id: str, suffix: str) -> bool:
    return any(a.logical_name == f"{candidate_id}{suffix}" for a in built.artifacts)


def _has_config(built: Any, name: str) -> bool:
    return any(
        n.node_type == "CONFIGURATION" and name in str(n.payload.get("config_name", ""))
        for n in built.nodes.values()
    )


def _snapshot_carrier(snapshot: Any) -> ProvenanceNode:
    return ProvenanceNode(
        node_id=snapshot.dataset_snapshot_id,
        node_type="DATASET_SNAPSHOT",
        schema_version=snapshot.schema_version,
        payload={
            "dataset_snapshot_id": snapshot.dataset_snapshot_id,
            "golden_record_ids": list(snapshot.golden_record_ids),
            "record_count": snapshot.record_count,
            "selection_config_id": snapshot.selection_config_id,
        },
    )


def _included_in_edge(golden_id: str, snapshot_id: str) -> ProvenanceEdge:
    return make_edge(golden_id, "INCLUDED_IN", snapshot_id)


def read_bundle(bundle_dir: str | Path) -> dict[str, Any]:
    """Read a bundle directory back into plain data (round-trip support)."""
    root = Path(bundle_dir)
    missing = [name for name in BUNDLE_FILES if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"bundle incomplete, missing: {missing}")

    def load_json(name: str) -> Any:
        return json.loads((root / name).read_text(encoding="utf-8"))

    def load_jsonl(name: str) -> list[Any]:
        with open(root / name, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    return {
        name: (load_jsonl(name) if name.endswith(".jsonl") else load_json(name))
        for name in BUNDLE_FILES
    }
