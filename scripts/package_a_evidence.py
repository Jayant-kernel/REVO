"""Maintain Package A's append-only evidence journal and generated index."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from verified_data_factory.local_lock import exclusive_lock

VALID_STATUSES = {"ACTIVE", "SUPERSEDED", "INFORMATIONAL", "UNPROVEN", "INVALID"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True, encoding="utf-8").strip()


def source_tree_identity(root: Path) -> dict[str, str]:
    tracked_diff = subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=root)
    untracked = git_output(root, "ls-files", "--others", "--exclude-standard")
    manifest = "\n".join(sorted(filter(None, untracked.splitlines()))) + "\n"
    source_prefixes = ("configs/", "docs/", "manifests/", "scripts/", "src/", "templates/", "tests/")
    content_entries = []
    for relative_path in sorted(filter(None, untracked.splitlines())):
        normalized = relative_path.replace("\\", "/")
        if normalized.startswith(source_prefixes):
            content_entries.append(f"{normalized}  {sha256_file(root / normalized)}")
    tracked_or_untracked_root_files = sorted(path for path in root.iterdir() if path.is_file())
    for path in tracked_or_untracked_root_files:
        content_entries.append(f"{path.name}  {sha256_file(path)}")
    content_manifest = "\n".join(content_entries) + "\n"
    return {
        "git_head": git_output(root, "rev-parse", "HEAD"),
        "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "untracked_manifest_sha256": hashlib.sha256(manifest.encode()).hexdigest(),
        "untracked_source_content_manifest_sha256": hashlib.sha256(
            content_manifest.encode()
        ).hexdigest(),
    }


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line:
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL event at line {line_number}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"event at line {line_number} is not an object")
            events.append(event)
    return events


def validate_event(event: dict[str, Any]) -> None:
    required = {
        "evidence_id",
        "event_type",
        "artifact_path",
        "sha256",
        "status",
        "supersedes",
        "superseded_by",
        "producer_script",
        "producer_command",
        "source_tree_identity",
        "created_at",
        "contract_id",
        "contract_version",
        "phase",
        "notes",
    }
    missing = sorted(required - event.keys())
    if missing:
        raise ValueError(f"missing event fields: {', '.join(missing)}")
    digest = event["sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or set(digest) - set("0123456789abcdef"):
        raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
    if event["status"] not in VALID_STATUSES:
        raise ValueError(f"invalid status: {event['status']}")
    if not isinstance(event["source_tree_identity"], dict):
        raise TypeError("source_tree_identity must be an object")


def materialize(events: list[dict[str, Any]]) -> dict[str, Any]:
    ids: set[str] = set()
    current: dict[str, dict[str, Any]] = {}
    expanded = []
    for event in events:
        validate_event(event)
        if event["event_type"] == "qualification_bundle_commit":
            members = event.get("members")
            required = {"rules", "named_tests", "relations", "mutation", "challenge", "fixture_diversity", "fuzz"}
            if (not isinstance(members, list) or len(members) != len(required)
                    or {m.get("category") for m in members if isinstance(m, dict)} != required):
                raise ValueError("incomplete qualification bundle transaction")
            for member in members:
                validate_event(member)
                if (member["status"] != "ACTIVE" or member["contract_id"] != event["contract_id"]
                        or member["contract_version"] != event["contract_version"]):
                    raise ValueError("misbound qualification bundle transaction")
            expanded.extend(members)
        else:
            expanded.append(event)
    for event in expanded:
        validate_event(event)
        evidence_id = event["evidence_id"]
        if evidence_id in ids:
            raise ValueError(f"duplicate evidence_id: {evidence_id}")
        ids.add(evidence_id)
        if event["supersedes"]:
            prior = current.get(event["supersedes"])
            if prior is None:
                raise ValueError(f"unknown superseded evidence: {event['supersedes']}")
            prior["status"] = "SUPERSEDED"
            prior["superseded_by"] = evidence_id
        current[evidence_id] = dict(event)
    return {
        "event_count": len(events),
        "entries": [current[evidence_id] for evidence_id in sorted(current)],
    }


def rebuild(root: Path) -> None:
    with exclusive_lock(root / "scratch/funnel_experiment/evidence/authority.lock"):
        _rebuild_locked(root)


def _rebuild_locked(root: Path) -> None:
    evidence_dir = root / "scratch" / "funnel_experiment" / "evidence"
    events_path = evidence_dir / "events.jsonl"
    index_path = evidence_dir / "index.json"
    temporary = evidence_dir / f"index-{uuid4().hex}.pending"
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(materialize(load_events(events_path)), indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(index_path)


def validate(root: Path, output: Path) -> int:
    """Verify every indexed artifact still resolves to its recorded digest."""
    events_path = root / "scratch" / "funnel_experiment" / "evidence" / "events.jsonl"
    effective_statuses = {
        entry["evidence_id"]: entry["status"]
        for entry in materialize(load_events(events_path))["entries"]
    }
    findings: list[dict[str, str]] = []
    for event in load_events(events_path):
        validate_event(event)
        artifact = root / event["artifact_path"]
        if not artifact.is_file():
            findings.append(
                {
                    "evidence_id": event["evidence_id"],
                    "artifact_status": "MISSING",
                    "evidence_status": effective_statuses[event["evidence_id"]],
                }
            )
        elif sha256_file(artifact) != event["sha256"]:
            findings.append(
                {
                    "evidence_id": event["evidence_id"],
                    "artifact_status": "STALE",
                    "evidence_status": effective_statuses[event["evidence_id"]],
                }
            )
    active_findings = [finding for finding in findings if finding["evidence_status"] == "ACTIVE"]
    report = {
        "active_findings": active_findings,
        "findings": findings,
        "status": "PASS" if not active_findings else "FAIL",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if not findings else 1


def record(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    artifact = root / args.artifact_path
    if not artifact.is_file():
        raise FileNotFoundError(f"artifact does not exist: {args.artifact_path}")
    event = {
        "evidence_id": args.evidence_id,
        "event_type": args.event_type,
        "artifact_path": args.artifact_path.replace("\\", "/"),
        "sha256": sha256_file(artifact),
        "status": args.status,
        "supersedes": args.supersedes,
        "superseded_by": None,
        "producer_script": args.producer_script,
        "producer_command": args.producer_command,
        "source_tree_identity": source_tree_identity(root),
        "created_at": datetime.now(UTC).isoformat(),
        "contract_id": args.contract_id,
        "contract_version": args.contract_version,
        "phase": args.phase,
        "notes": args.notes,
    }
    validate_event(event)
    evidence_dir = root / "scratch" / "funnel_experiment" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    events_path = evidence_dir / "events.jsonl"
    with exclusive_lock(evidence_dir / "authority.lock"):
        existing = load_events(events_path)
        materialize([*existing, event])
        with events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _rebuild_locked(root)
    print(event["evidence_id"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(required=True)
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--evidence-id", required=True)
    record_parser.add_argument("--event-type", required=True)
    record_parser.add_argument("--artifact-path", required=True)
    record_parser.add_argument("--status", choices=sorted(VALID_STATUSES), default="ACTIVE")
    record_parser.add_argument("--supersedes")
    record_parser.add_argument("--producer-script", required=True)
    record_parser.add_argument("--producer-command", required=True)
    record_parser.add_argument("--contract-id")
    record_parser.add_argument("--contract-version", type=int)
    record_parser.add_argument("--phase", required=True)
    record_parser.add_argument("--notes", required=True)
    record_parser.set_defaults(func=record)
    rebuild_parser = subparsers.add_parser("rebuild")
    rebuild_parser.set_defaults(func=lambda args: rebuild(args.root.resolve()))
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--output", type=Path, required=True)
    validate_parser.set_defaults(func=lambda args: validate(args.root.resolve(), args.output))
    args = parser.parse_args()
    result = args.func(args)
    return 0 if result is None else result


if __name__ == "__main__":
    raise SystemExit(main())
