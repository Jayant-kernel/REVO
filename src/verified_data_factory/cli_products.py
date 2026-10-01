"""Data-product CLI commands (Phase 7). Thin wrappers over products.api.

Golden input format (JSONL, one GoldenRecord per line — the Phase 5
``golden.jsonl`` export)::

    {"candidate_id": ..., "task": {...}, "instruction": ...,
     "schema": [...], "candidate_solution": ..., ...}

Quality input format (JSON, list of RecordQuality dicts — the
``factory quality record --output`` payload)::

    [{"candidate_id": ..., "role": ..., "contamination_flags": [...], ...}]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_golden(path: str | Path) -> list[Any]:
    from verified_data_factory.quality.models import GoldenRecord

    records = []
    with open(path, encoding="utf-8-sig") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                records.append(GoldenRecord.model_validate(json.loads(line)))
            except Exception as exc:
                raise SystemExit(f"{path}:{lineno}: invalid golden record: {exc}") from exc
    return records


def load_quality_map(path: str | Path) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise SystemExit(f"{path}: invalid quality JSON: {exc}") from exc
    items = payload if isinstance(payload, list) else payload.get("qualities", [])
    try:
        return {item["candidate_id"]: item for item in items}
    except Exception as exc:
        raise SystemExit(f"{path}: quality entries need candidate_id: {exc}") from exc


def load_snapshot(path: str | Path) -> Any:
    from verified_data_factory.provenance import DatasetSnapshot

    try:
        return DatasetSnapshot.model_validate(
            json.loads(Path(path).read_text(encoding="utf-8-sig"))
        )
    except Exception as exc:
        raise SystemExit(f"{path}: invalid dataset snapshot: {exc}") from exc


def _optional_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    return payload if isinstance(payload, dict) else {"items": payload}


def _read_json_payload(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc


def _read_string_map(path: str) -> dict[str, str]:
    payload = _read_json_payload(path)
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: expected a JSON object mapping ids to text")
    return {str(k): str(v) for k, v in payload.items()}


def _read_jsonl_rows(path: str) -> list[Any]:
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def _package_versions(args: argparse.Namespace) -> tuple[str, str]:
    from verified_data_factory import __version__ as factory_version
    from verified_data_factory.provenance import PROVENANCE_ENGINE_VERSION

    return (
        getattr(args, "factory_version", None) or factory_version,
        getattr(args, "provenance_version", None) or PROVENANCE_ENGINE_VERSION,
    )


def cmd_product_build(args: argparse.Namespace) -> int:
    from verified_data_factory.products import build_release, load_product_config
    from verified_data_factory.quality import load_quarantine, quarantined_ids

    config = load_product_config(args.config)
    factory_version, provenance_version = _package_versions(args)
    quarantined: set[str] | None = None
    if args.quarantine:
        quarantined = quarantined_ids(load_quarantine(args.quarantine))
    built = build_release(
        snapshot=load_snapshot(args.snapshot),
        golden_records=load_golden(args.golden),
        quality_by_id=load_quality_map(args.quality),
        config=config,
        out_dir=args.out_dir,
        factory_version=factory_version,
        provenance_version=provenance_version,
        health=_optional_json(args.health),
        coverage=_optional_json(args.coverage),
        duplicates=_optional_json(args.duplicates),
        verification_summary=_optional_json(args.verification_summary),
        audit_summary=_optional_json(args.audit),
        contamination=_optional_json(args.contamination),
        quarantined_ids=quarantined,
        justifications=_read_string_map(args.justifications) if args.justifications else None,
        supply_chain=_read_json_payload(args.supply_chain) if args.supply_chain else None,
        review_package=args.review_package,
    )
    print(f"release={built.manifest.release_id} records={built.manifest.record_count}")
    print(
        f"shards={built.manifest.shard_count} splits={json.dumps(built.manifest.split_counts, sort_keys=True)}"
    )
    if built.rejected:
        print(f"rejected={len(built.rejected)} by visibility policy", file=sys.stderr)
    print(f"release -> {args.out_dir}")
    return 0


def cmd_product_validate(args: argparse.Namespace) -> int:
    from verified_data_factory.products import validate_release
    from verified_data_factory.quality import load_quarantine, quarantined_ids

    quarantined: set[str] | None = None
    if args.quarantine:
        quarantined = quarantined_ids(load_quarantine(args.quarantine))
    qualities = load_quality_map(args.quality) if args.quality else None
    justifications = _read_string_map(args.justifications) if args.justifications else {}
    supply_chain = _read_json_payload(args.supply_chain) if args.supply_chain else None
    report = validate_release(
        args.release_dir,
        quarantined_ids=quarantined,
        qualities_by_id=qualities,
        justifications=justifications,
        supply_chain=supply_chain,
        review_package=args.review_package,
        mutation_min_score=args.mutation_min_score,
    )
    print(f"status={report.status} records={report.record_count} files={report.file_count}")
    print(
        f"manifest={report.manifest_status} checksums={report.checksum_status} "
        f"schema={report.schema_status} splits={report.split_status} "
        f"provenance={report.provenance_status}"
    )
    for error in report.errors:
        print(f"ERROR {error.check}: {error.detail}", file=sys.stderr)
    for warning in report.warnings:
        print(f"warning {warning.check}: {warning.detail}", file=sys.stderr)
    return 0 if report.status == "VALID" else 1


def cmd_product_diff(args: argparse.Namespace) -> int:
    from verified_data_factory.products import diff_releases

    diff = diff_releases(args.a, args.b)
    print(f"a={diff.release_a}")
    print(f"b={diff.release_b}")
    print(
        f"added={len(diff.records_added)} removed={len(diff.records_removed)} changed={len(diff.records_changed)}"
    )
    print(
        f"splits_changed={diff.splits_changed} schema_changed={diff.schema_changed} "
        f"config_changed={diff.config_changed} snapshot_changed={diff.snapshot_changed} "
        f"format_changed={diff.format_changed}"
    )
    return 0


def cmd_product_load(args: argparse.Namespace) -> int:
    from verified_data_factory.products import load_release, records_by_split

    loaded = load_release(args.release_dir)
    grouped = records_by_split(loaded)
    print(f"release={loaded.manifest.release_id} records={len(loaded)}")
    for split in sorted(grouped):
        print(f"split {split}: {len(grouped[split])}")
    if args.show_one:
        print(
            json.dumps(loaded.records[0], indent=2, sort_keys=True, default=str)
            if loaded.records
            else "empty"
        )
    return 0


def cmd_product_splits(args: argparse.Namespace) -> int:
    from verified_data_factory.products import SplitPolicy, build_splits

    goldens = load_golden(args.golden)
    quality_by_id = load_quality_map(args.quality)
    policy_kwargs: dict[str, Any] = {"seed": args.seed, "group_by": args.group_by}
    if args.train is not None:
        policy_kwargs["train"] = args.train
    if args.public_eval is not None:
        policy_kwargs["public_eval"] = args.public_eval
    if args.private_eval is not None:
        policy_kwargs["private_eval"] = args.private_eval
    splits = build_splits(goldens, quality_by_id, SplitPolicy(**policy_kwargs))
    for name in ("train", "public_eval", "private_eval", "benchmark"):
        print(f"{name}: {splits[name].record_count}")
    return 0


def cmd_product_manifest(args: argparse.Namespace) -> int:
    from verified_data_factory.products import (
        build_row_manifest,
        validate_row_manifest,
        write_row_manifest,
    )
    from verified_data_factory.quality import load_quarantine, quarantined_ids

    golden = load_golden(args.golden)
    golden_dicts = [g.model_dump(mode="json", by_alias=True) for g in golden]
    quality_by_id = load_quality_map(args.quality)
    candidates_by_id = {}
    if args.records:
        for row in _read_jsonl_rows(args.records):
            candidate = row.get("candidate", {})
            if isinstance(candidate, dict) and candidate.get("candidate_id"):
                candidates_by_id[candidate["candidate_id"]] = candidate
    snapshot = load_snapshot(args.snapshot)
    quarantined: set[str] = set()
    if args.quarantine:
        quarantined = quarantined_ids(load_quarantine(args.quarantine))
    rows = build_row_manifest(
        golden_records=golden_dicts,
        quality_by_id=quality_by_id,
        dataset_snapshot_id=snapshot.dataset_snapshot_id,
        release_id=args.release_id,
        generation_run_id=args.generation_run_id,
        candidates_by_id=candidates_by_id,
    )
    violations = validate_row_manifest(
        rows,
        require_snapshot=snapshot.dataset_snapshot_id,
        quarantined_ids=quarantined,
    )
    write_row_manifest(rows, args.output)
    for violation in violations:
        print(f"VIOLATION: {violation}", file=sys.stderr)
    print(f"rows={len(rows)} violations={len(violations)} -> {args.output}")
    return 0 if not violations else 1


def cmd_product_census(args: argparse.Namespace) -> int:
    from verified_data_factory.products import build_audit_report, build_census, write_json_payload
    from verified_data_factory.quality import load_quarantine, quarantined_ids

    golden = load_golden(args.golden)
    golden_dicts = [g.model_dump(mode="json", by_alias=True) for g in golden]
    quality_by_id = load_quality_map(args.quality)
    health = _read_json_payload(args.health) if args.health else {}
    duplicates = _read_json_payload(args.duplicates) if args.duplicates else {}
    justifications = _read_string_map(args.justifications) if args.justifications else {}
    quarantined: set[str] = set()
    if args.quarantine:
        quarantined = quarantined_ids(load_quarantine(args.quarantine))
    supply_chain = _read_json_payload(args.supply_chain) if args.supply_chain else {}
    row_manifest = None
    if args.row_manifest:
        from verified_data_factory.products import read_row_manifest

        row_manifest = read_row_manifest(args.row_manifest)
    census = build_census(
        golden_records=golden_dicts,
        quality_by_id=quality_by_id,
        health=health,
        duplicates=duplicates,
        quarantined_ids=quarantined,
        justifications=justifications,
        governance_unresolved_count=int(args.governance_unresolved),
        row_manifest=row_manifest,
    )
    payload = census.model_dump(mode="json")
    if args.audit_report:
        report = build_audit_report(
            census=census,
            supply_chain=supply_chain,
            quarantine_entries=[],
            release_manifest=_read_json_payload(args.release_manifest)
            if args.release_manifest
            else {},
        )
        from verified_data_factory.products import render_audit_markdown

        payload = {"census": payload, "audit_report": report.model_dump(mode="json")}
        Path(args.audit_report).write_text(render_audit_markdown(report), encoding="utf-8")
        print(f"audit report -> {args.audit_report}")
    write_json_payload(payload, args.output)
    print(
        f"records={census.record_count} all_strong={census.all_strong} "
        f"all_scored={census.all_scored_at_threshold} unjustified={census.unjustified_zero_applicable_count}"
    )
    return 0


def register_product_commands(subparsers: argparse._SubParsersAction[Any]) -> None:
    """Attach `factory product ...` to the root parser (called by cli.py)."""
    product = subparsers.add_parser("product", help="Data Product commands")
    psub = product.add_subparsers(dest="product_command", required=True)

    p_build = psub.add_parser("build", help="Build a validated release from a Golden snapshot")
    p_build.add_argument("--golden", required=True, help="golden.jsonl (Phase 5 export)")
    p_build.add_argument("--quality", required=True, help="record qualities JSON")
    p_build.add_argument("--snapshot", required=True, help="DatasetSnapshot JSON")
    p_build.add_argument("--config", required=True, help="product YAML config")
    p_build.add_argument("--out-dir", required=True, help="release output directory")
    p_build.add_argument("--health", default=None)
    p_build.add_argument("--coverage", default=None)
    p_build.add_argument("--duplicates", default=None)
    p_build.add_argument("--verification-summary", default=None)
    p_build.add_argument("--audit", default=None)
    p_build.add_argument("--review-package", default=None, help="frozen two-reviewer package (required for PUBLIC)")
    p_build.add_argument("--contamination", default=None)
    p_build.add_argument(
        "--justifications", default=None, help="record_id -> mutation justification JSON object"
    )
    p_build.add_argument(
        "--supply-chain", default=None, help="supply-chain report JSON (required for PUBLIC)"
    )
    p_build.add_argument("--factory-version", default=None)
    p_build.add_argument("--provenance-version", default=None)
    p_build.add_argument(
        "--quarantine", default=None, help="quarantine JSON (refuses quarantined builds)"
    )
    p_build.set_defaults(func=cmd_product_build)

    p_validate = psub.add_parser("validate", help="Validate a release directory")
    p_validate.add_argument("--release-dir", required=True)
    p_validate.add_argument(
        "--quarantine", default=None, help="quarantine JSON (rejects shipped rows)"
    )
    p_validate.add_argument(
        "--quality", default=None, help="record qualities JSON (mutation/contamination gates)"
    )
    p_validate.add_argument(
        "--justifications", default=None, help="candidate_id -> justification JSON object"
    )
    p_validate.add_argument(
        "--supply-chain", default=None, help="supply-chain report JSON (clearance gate)"
    )
    p_validate.add_argument("--mutation-min-score", type=float, default=0.9)
    p_validate.add_argument("--review-package", default=None, help="frozen two-reviewer package (required for PUBLIC)")
    p_validate.set_defaults(func=cmd_product_validate)

    p_diff = psub.add_parser("diff", help="Diff two releases")
    p_diff.add_argument("--a", required=True)
    p_diff.add_argument("--b", required=True)
    p_diff.set_defaults(func=cmd_product_diff)

    p_load = psub.add_parser("load", help="Load a release and show its splits")
    p_load.add_argument("--release-dir", required=True)
    p_load.add_argument("--show-one", action="store_true", help="print the first record")
    p_load.set_defaults(func=cmd_product_load)

    p_splits = psub.add_parser("splits", help="Show the deterministic split plan")
    p_splits.add_argument("--golden", required=True)
    p_splits.add_argument("--quality", required=True)
    p_splits.add_argument("--seed", type=int, default=42)
    p_splits.add_argument(
        "--group-by",
        default="semantic_group",
        choices=["semantic_group", "exact_group", "template", "none"],
    )
    p_splits.add_argument("--train", type=float, default=None)
    p_splits.add_argument("--public-eval", type=float, default=None)
    p_splits.add_argument("--private-eval", type=float, default=None)
    p_splits.set_defaults(func=cmd_product_splits)

    p_manifest = psub.add_parser(
        "manifest", help="Export a deterministic per-row provenance manifest"
    )
    p_manifest.add_argument("--golden", required=True, help="golden.jsonl (Phase 5 export)")
    p_manifest.add_argument("--quality", required=True, help="record qualities JSON")
    p_manifest.add_argument("--snapshot", required=True, help="DatasetSnapshot JSON")
    p_manifest.add_argument(
        "--records", default=None, help="records.jsonl (candidate/model origin)"
    )
    p_manifest.add_argument("--release-id", default=None)
    p_manifest.add_argument("--generation-run-id", default=None)
    p_manifest.add_argument("--quarantine", default=None, help="quarantine JSON")
    p_manifest.add_argument("--output", required=True)
    p_manifest.set_defaults(func=cmd_product_manifest)

    p_census = psub.add_parser("census", help="Reproducible corpus census from stored artifacts")
    p_census.add_argument("--golden", required=True)
    p_census.add_argument("--quality", required=True, help="record qualities JSON")
    p_census.add_argument("--health", default=None)
    p_census.add_argument("--duplicates", default=None)
    p_census.add_argument("--justifications", default=None)
    p_census.add_argument("--quarantine", default=None)
    p_census.add_argument("--supply-chain", default=None)
    p_census.add_argument(
        "--row-manifest", default=None, help="row-manifest.jsonl for provenance/model counts"
    )
    p_census.add_argument("--governance-unresolved", type=int, default=0)
    p_census.add_argument("--release-manifest", default=None)
    p_census.add_argument(
        "--audit-report", default=None, help="also write Markdown audit report here"
    )
    p_census.add_argument("--output", required=True)
    p_census.set_defaults(func=cmd_product_census)
