"""Provenance CLI commands (Phase 6). Thin wrappers over provenance.api.

Input conventions (shared with the quality CLI):
- ``--records``: JSONL of ``{"task","candidate","execution","verification"}``
  bundles (same file ``factory quality`` consumes).
- ``--qualities``: JSONL list output of ``factory quality record`` or the
  per-line ``RecordQuality`` objects.
- ``--golden``: ``golden.jsonl`` from the quality export (GoldenRecord dicts).
- ``--audit``: audit sample JSON (``{"items": [...]}`` or a bare list).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_jsonl(path: str | Path) -> list[Any]:
    with open(path, encoding="utf-8-sig") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    from verified_data_factory.generation import candidate_from_dict
    from verified_data_factory.quality.models import (
        AuditSample,
        GoldenRecord,
        RecordQuality,
        VerifiedRecord,
    )
    from verified_data_factory.sandbox.models import ExecutionResult
    from verified_data_factory.task_engine import task_from_dict
    from verified_data_factory.verification import verification_from_dict

    records = []
    for bundle in _load_jsonl(args.records):
        records.append(
            VerifiedRecord(
                task=task_from_dict(bundle["task"]),
                candidate=candidate_from_dict(bundle["candidate"]),
                execution=ExecutionResult.model_validate(bundle["execution"]),
                verification=verification_from_dict(bundle["verification"]),
                role=bundle.get("role", "UNKNOWN"),
            )
        )
    qualities = [RecordQuality.model_validate(q) for q in _load_jsonl(args.qualities)]
    golden = [GoldenRecord.model_validate(g) for g in _load_jsonl(args.golden)]
    audit = None
    if getattr(args, "audit", None):
        from verified_data_factory.quality.models import AuditItem

        raw = json.loads(Path(args.audit).read_text(encoding="utf-8-sig"))
        items_raw = raw.get("items", raw) if isinstance(raw, dict) else raw
        items = [AuditItem.model_validate(i) for i in items_raw]
        audit = AuditSample(
            items=items,
            selection_seed=int(raw.get("selection_seed", 0)) if isinstance(raw, dict) else 0,
            sampled_count=len(items),
        )
    return {"records": records, "qualities": qualities, "golden": golden, "audit": audit}


def _configs(args: argparse.Namespace) -> dict[str, Any]:
    from verified_data_factory.provenance import load_provenance_config

    quality_config: dict[str, Any] = {}
    if getattr(args, "quality_config", None):
        from verified_data_factory.quality import load_quality_config

        quality_config = load_quality_config(args.quality_config).model_dump(mode="json")
    verification_config: dict[str, Any] | None = None
    if getattr(args, "verification_config", None):
        import yaml

        from verified_data_factory.verification import VerificationConfig

        raw = yaml.safe_load(Path(args.verification_config).read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise SystemExit(f"{args.verification_config}: must be a YAML mapping")
        section = raw.get("verification", raw)
        verification_config = VerificationConfig.model_validate(section).model_dump(mode="json")
    provenance_config = (
        load_provenance_config(args.provenance_config)
        if getattr(args, "provenance_config", None)
        else None
    )
    return {
        "quality": quality_config,
        "verification": verification_config,
        "provenance": provenance_config,
    }


def _build_all(args: argparse.Namespace) -> dict[str, Any]:
    import verified_data_factory
    from verified_data_factory.provenance import build_bundle

    inputs = _load_inputs(args)
    cfgs = _configs(args)
    provenance = cfgs["provenance"]
    bundle = build_bundle(
        inputs["records"],
        inputs["qualities"],
        inputs["golden"],
        inputs["audit"],
        cfgs["quality"],
        cfgs["verification"],
        verified_data_factory.__version__,
        args.name,
        repo_root=Path.cwd(),
        source_scope=provenance.source_scope if provenance else None,
    )
    bundle["inputs"] = inputs
    return bundle


def cmd_provenance_record(args: argparse.Namespace) -> int:
    """Build the full graph + snapshot; print the snapshot identity."""
    from verified_data_factory.provenance import export_provenance_bundle

    ctx = _build_all(args)
    print(f"snapshot={ctx['snapshot'].dataset_snapshot_id}")
    print(
        f"records={len(ctx['inputs']['records'])} nodes={len(ctx['nodes'])} edges={len(ctx['edges'])}"
    )
    if args.out:
        export_provenance_bundle(
            args.out,
            ctx["manifest"],
            ctx["reproduction"].model_dump(mode="json"),
            ctx["snapshot"],
            list(ctx["nodes"].values()),
            ctx["edges"],
            ctx["activities"],
            ctx["artifacts"],
            ctx["golden"],
            ctx["reproducibility"],
            ctx["completeness"],
            ctx["artifact_payloads"],
        )
        print(f"bundle -> {args.out}")
    return 0


def cmd_provenance_run(args: argparse.Namespace) -> int:
    """Emit a fresh operational RunManifest for the current source/env."""
    import verified_data_factory
    from verified_data_factory.provenance import (
        build_run_manifest,
        capture_environment_snapshot,
        capture_source_snapshot,
        finish_activity,
        start_activity,
        utc_now_iso,
    )

    started = utc_now_iso()
    activity = start_activity("PROVENANCE_RUN", "1.0")
    source = capture_source_snapshot(
        Path.cwd(), ["src/verified_data_factory", "pyproject.toml", "configs/"]
    )
    environment = capture_environment_snapshot(Path.cwd())
    manifest = build_run_manifest(
        activity.run_id,
        verified_data_factory.__version__,
        "provenance",
        {"provenance": "1.0"},
        source.source_snapshot_id,
        environment.dependency_lock_hash,
        environment.environment_snapshot_id,
        started,
        utc_now_iso(),
    )
    finished = finish_activity(activity, "SUCCEEDED")
    payload = {
        "manifest": manifest.model_dump(mode="json"),
        "activity": finished.model_dump(mode="json"),
    }
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def cmd_provenance_lineage(args: argparse.Namespace) -> int:
    """Print the ordered lineage chain for one Golden record."""
    from verified_data_factory.provenance import read_bundle, trace_golden_record
    from verified_data_factory.provenance.models import ProvenanceEdge, ProvenanceNode

    bundle = read_bundle(args.bundle)
    nodes = {n["node_id"]: ProvenanceNode.model_validate(n) for n in bundle["nodes.jsonl"]}
    edges = [ProvenanceEdge.model_validate(e) for e in bundle["edges.jsonl"]]
    chain = trace_golden_record(nodes, edges, args.golden_record)
    for node_id in chain:
        node = nodes[node_id]
        print(f"{node.node_type:20s} {node_id}")
    return 0


def cmd_provenance_validate(args: argparse.Namespace) -> int:
    """Completeness + graph validation over a bundle (exit 1 if incomplete)."""
    from verified_data_factory.provenance import (
        read_bundle,
        roles_for_candidate,
        validate_graph,
    )
    from verified_data_factory.provenance.completeness import validate_golden_chain
    from verified_data_factory.provenance.models import ProvenanceEdge, ProvenanceNode

    bundle = read_bundle(args.bundle)
    nodes = {n["node_id"]: ProvenanceNode.model_validate(n) for n in bundle["nodes.jsonl"]}
    edges = [ProvenanceEdge.model_validate(e) for e in bundle["edges.jsonl"]]
    problems = validate_graph(nodes, edges)
    golden_nodes = [n for n in nodes.values() if n.node_type == "GOLDEN_RECORD"]
    snapshot_node = next((n for n in nodes.values() if n.node_type == "DATASET_SNAPSHOT"), None)
    incomplete = 0
    for golden in golden_nodes:
        roles = roles_for_candidate(nodes, golden.payload["candidate_id"], edges)
        report = validate_golden_chain(
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
        if not report.complete:
            incomplete += 1
            for issue in report.errors:
                print(f"{golden.payload['candidate_id']}: {issue.code} {issue.detail}")
    for problem in problems:
        print(f"graph: {problem}")
    print(f"golden={len(golden_nodes)} incomplete={incomplete} graph_problems={len(problems)}")
    return 1 if incomplete or problems else 0


def cmd_provenance_reproducibility(args: argparse.Namespace) -> int:
    """Assess reproducibility layers for one Golden record (or the snapshot)."""
    from verified_data_factory.provenance import (
        assess_reproducibility,
        read_bundle,
        recompute_snapshot_id,
        roles_for_candidate,
    )
    from verified_data_factory.provenance.models import (
        DatasetSnapshot,
        ProvenanceEdge,
        ProvenanceNode,
    )

    bundle = read_bundle(args.bundle)
    nodes = {n["node_id"]: ProvenanceNode.model_validate(n) for n in bundle["nodes.jsonl"]}
    edges = [ProvenanceEdge.model_validate(e) for e in bundle["edges.jsonl"]]
    snapshot = DatasetSnapshot.model_validate(bundle["snapshot.json"])
    golden_nodes = [n for n in nodes.values() if n.node_type == "GOLDEN_RECORD"]
    if args.golden_record:
        golden_nodes = [n for n in golden_nodes if n.node_id == args.golden_record]
        if not golden_nodes:
            print(f"unknown golden record: {args.golden_record}", file=sys.stderr)
            return 2
    for golden in sorted(golden_nodes, key=lambda n: n.node_id):
        candidate_id = golden.payload["candidate_id"]
        roles = roles_for_candidate(nodes, candidate_id, edges)
        report = assess_reproducibility(
            task_payload=_role_payload(roles, "TASK_INSTANCE"),
            candidate_payload=_role_payload(roles, "CANDIDATE_SOLUTION"),
            model_payload=_model_payload_for(nodes, _role_payload(roles, "CANDIDATE_SOLUTION")),
            raw_artifact_present=_artifact_present(bundle, candidate_id, ".raw.txt"),
            execution_payload=_role_payload(roles, "EXECUTION_RESULT"),
            environment_present=any(n.node_type == "ENVIRONMENT_SNAPSHOT" for n in nodes.values()),
            verification_payload=_role_payload(roles, "VERIFICATION_RESULT"),
            verification_config_present=_config_present(nodes, "verification"),
            quality_payload=_role_payload(roles, "RECORD_QUALITY"),
            quality_config_present=_config_present(nodes, "quality"),
            snapshot_id=snapshot.dataset_snapshot_id,
            recomputed_snapshot_id=recompute_snapshot_id(snapshot),
        )
        print(f"{candidate_id}: {report.overall_status}")
        for name in ("task", "generation", "execution", "verification", "quality", "dataset"):
            layer = getattr(report, f"{name}_reproducibility")
            print(f"  {name}: {layer.status} {'; '.join(layer.reasons)}")
    return 0


def _role_payload(roles: dict[str, Any], node_type: str) -> dict[str, Any]:
    node = roles.get(node_type)
    return dict(node.payload) if node is not None else {}


def _payload_for(nodes: dict[str, Any], node_type: str, candidate_id: str) -> dict[str, Any]:
    for node in nodes.values():
        if node.node_type == node_type and node.payload.get("candidate_id") == candidate_id:
            return dict(node.payload)
    # Fall back to task linkage via edges is out of scope for the CLI;
    # an empty payload yields an honest UNKNOWN assessment.
    return {}


def _model_payload_for(
    nodes: dict[str, Any], candidate_payload: dict[str, Any]
) -> dict[str, Any] | None:
    """Match the MODEL_SNAPSHOT for this candidate's model (snapshots are shared)."""
    wanted = candidate_payload.get("model")
    for node in nodes.values():
        if node.node_type == "MODEL_SNAPSHOT" and (
            wanted is None or node.payload.get("model_name") == wanted
        ):
            return dict(node.payload)
    return None


def _artifact_present(bundle: dict[str, Any], candidate_id: str, suffix: str) -> bool:
    return any(
        a.get("logical_name", "") == f"{candidate_id}{suffix}" for a in bundle["artifacts.jsonl"]
    )


def _config_present(nodes: dict[str, Any], name: str) -> bool:
    return any(
        n.node_type == "CONFIGURATION" and name in str(n.payload.get("config_name", ""))
        for n in nodes.values()
    )


def cmd_provenance_snapshot(args: argparse.Namespace) -> int:
    """Build a dataset snapshot id from a golden.jsonl file."""
    from verified_data_factory.provenance import build_dataset_snapshot, load_provenance_config
    from verified_data_factory.quality.models import GoldenRecord

    golden = [GoldenRecord.model_validate(g) for g in _load_jsonl(args.golden)]
    provenance_config = (
        load_provenance_config(args.provenance_config) if args.provenance_config else None
    )
    _ = provenance_config
    quality_config_id = "sha256:unknown"
    if args.quality_config:
        from verified_data_factory.provenance.activities import snapshot_config
        from verified_data_factory.quality import load_quality_config

        quality = load_quality_config(args.quality_config)
        quality_config_id = snapshot_config(
            "quality", quality.model_dump(mode="json"), quality.config_version
        ).configuration_id
    # Snapshot identity covers record *content*, not candidate ids alone.
    content_ids = sorted(g.record_id for g in golden)
    snapshot = build_dataset_snapshot(content_ids, args.name, "1.0", quality_config_id, "1.0")
    payload = snapshot.model_dump(mode="json")
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"snapshot={snapshot.dataset_snapshot_id}", file=sys.stderr)
    return 0


def cmd_provenance_export(args: argparse.Namespace) -> int:
    """Normalized rewrite of a bundle (read-back round-trip proof)."""
    from verified_data_factory.provenance import (
        export_provenance_bundle,
        read_bundle,
    )
    from verified_data_factory.provenance.models import (
        ArtifactRef,
        DatasetSnapshot,
        ProvenanceActivity,
        ProvenanceCompletenessReport,
        ProvenanceEdge,
        ProvenanceNode,
        ReproducibilityReport,
        RunManifest,
    )

    bundle = read_bundle(args.bundle)
    out = args.out
    export_provenance_bundle(
        out,
        RunManifest.model_validate(bundle["manifest.json"]),
        bundle["reproduction.json"],
        DatasetSnapshot.model_validate(bundle["snapshot.json"]),
        [ProvenanceNode.model_validate(n) for n in bundle["nodes.jsonl"]],
        [ProvenanceEdge.model_validate(e) for e in bundle["edges.jsonl"]],
        [ProvenanceActivity.model_validate(a) for a in bundle["activities.jsonl"]],
        [ArtifactRef.model_validate(a) for a in bundle["artifacts.jsonl"]],
        bundle["golden_records.jsonl"],
        {
            k: ReproducibilityReport.model_validate(v)
            for k, v in bundle["reproducibility.json"].items()
        },
        [ProvenanceCompletenessReport.model_validate(c) for c in bundle["completeness.json"]],
    )
    print(f"export -> {out}")
    return 0


def register_provenance_commands(subparsers: argparse._SubParsersAction[Any]) -> None:
    """Attach `factory provenance ...` to the root parser (called by cli.py)."""
    provenance = subparsers.add_parser("provenance", help="Provenance & Reproducibility commands")
    psub = provenance.add_subparsers(dest="provenance_command", required=True)

    def _bundle(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--bundle", required=True, help="provenance bundle directory")

    p_record = psub.add_parser("record", help="Build lineage + snapshot from records")
    p_record.add_argument("--records", required=True)
    p_record.add_argument("--qualities", required=True)
    p_record.add_argument("--golden", required=True)
    p_record.add_argument("--audit", default=None)
    p_record.add_argument("--quality-config", default=None)
    p_record.add_argument("--verification-config", default=None)
    p_record.add_argument("--provenance-config", default=None)
    p_record.add_argument("--name", required=True)
    p_record.add_argument("--out", default=None, help="store directory for the graph")
    p_record.set_defaults(func=cmd_provenance_record)

    p_run = psub.add_parser("run", help="Emit a fresh operational RunManifest")
    p_run.add_argument("--output", default=None)
    p_run.set_defaults(func=cmd_provenance_run)

    p_lineage = psub.add_parser("lineage", help="Trace one Golden record's chain")
    _bundle(p_lineage)
    p_lineage.add_argument("--golden-record", required=True, help="GOLDEN_RECORD node id")
    p_lineage.set_defaults(func=cmd_provenance_lineage)

    p_validate = psub.add_parser("validate", help="Completeness + graph validation")
    _bundle(p_validate)
    p_validate.set_defaults(func=cmd_provenance_validate)

    p_repro = psub.add_parser("reproducibility", help="Assess reproducibility layers")
    _bundle(p_repro)
    p_repro.add_argument("--golden-record", default=None)
    p_repro.set_defaults(func=cmd_provenance_reproducibility)

    p_snap = psub.add_parser("snapshot", help="Dataset snapshot id from golden.jsonl")
    p_snap.add_argument("--golden", required=True)
    p_snap.add_argument("--quality-config", default=None)
    p_snap.add_argument("--provenance-config", default=None)
    p_snap.add_argument("--name", required=True)
    p_snap.add_argument("--output", default=None)
    p_snap.set_defaults(func=cmd_provenance_snapshot)

    p_export = psub.add_parser("export", help="Normalized bundle rewrite (round-trip)")
    _bundle(p_export)
    p_export.add_argument("--out", required=True)
    p_export.set_defaults(func=cmd_provenance_export)
