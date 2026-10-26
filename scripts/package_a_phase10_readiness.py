"""Materialize Phase 10's authoritative contract readiness evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from package_a_evidence import load_events, materialize, sha256_file
from phase3_diagnostic import _contract_readiness

INDEX_VERSION = "1.0"
MANIFEST_VERSION = "2.0"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _key(contract_id: str, version: int) -> tuple[str, int]:
    return contract_id, version


def _load_quarantines(path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        _key(item["contract_id"], item["contract_version"]): item
        for item in payload["quarantines"]
    }


def _scheduler_check_status(name: str, check: dict[str, Any]) -> str:
    """Preserve differential-oracle evidence without mislabelling it independent."""
    strategy = check.get("source", {}).get("json_path", "")
    if name == "independent_oracle" and "strategy=differential_" in strategy:
        return "differential"
    return check["status"]


def _scheduler_ready(checks: dict[str, dict[str, Any]]) -> bool:
    return all(
        status == "yes" or (name == "independent_oracle" and status == "differential")
        for name, status in ((name, _scheduler_check_status(name, check)) for name, check in checks.items())
    )


def build_index(root: Path, generated_at: str) -> dict[str, Any]:
    """Build one record per current contract/version from reproducible inputs."""
    evidence_dir = root / "scratch" / "funnel_experiment" / "evidence"
    journal_path = evidence_dir / "events.jsonl"
    journal = materialize(load_events(journal_path))["entries"]
    by_contract: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for entry in journal:
        contract_id, version = entry["contract_id"], entry["contract_version"]
        if contract_id is not None and version is not None:
            by_contract.setdefault(_key(contract_id, version), []).append(entry)

    quarantine_path = root / "manifests" / "package-a-contract-quarantine.json"
    quarantines = _load_quarantines(quarantine_path)
    readiness = _contract_readiness()
    contracts: list[dict[str, Any]] = []
    for row in readiness["rows"]:
        contract_id = row["template_id"]
        version = row["template_version"]
        quarantine = quarantines.get(_key(contract_id, version))
        checks = {
            name: {**check, "status": _scheduler_check_status(name, check)}
            for name, check in row["checks"].items()
        }
        ready = _scheduler_ready(checks) and quarantine is None
        contracts.append(
            {
                "contract_id": contract_id,
                "contract_version": version,
                "family": row["family"],
                "readiness_checks": checks,
                "journal_evidence": sorted(
                    by_contract.get(_key(contract_id, version), []),
                    key=lambda entry: entry["evidence_id"],
                ),
                "quarantine": quarantine,
                "status": "FULLY_VERIFIED" if ready else "QUARANTINED" if quarantine else "NOT_READY",
            }
        )
    contracts.sort(key=lambda item: (item["contract_id"], item["contract_version"]))
    payload = {
        "index_version": INDEX_VERSION,
        "qualification_scope": "legacy scheduler diagnostics; not current source-bound receipt admission",
        "generated_at": generated_at,
        "readiness_columns": readiness["columns"],
        "sources": {
            "journal": {"path": journal_path.relative_to(root).as_posix(), "sha256": sha256_file(journal_path)},
            "quarantine": {"path": quarantine_path.relative_to(root).as_posix(), "sha256": sha256_file(quarantine_path)},
        },
        "contracts": contracts,
    }
    return {**payload, "index_hash": "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()}


def build_matrix(index: dict[str, Any]) -> dict[str, Any]:
    """Derive the human-readable matrix exclusively from the authority index."""
    rows = [
        {
            "contract_id": contract["contract_id"],
            "contract_version": contract["contract_version"],
            "family": contract["family"],
            "status": contract["status"],
            "checks": {name: contract["readiness_checks"][name]["status"] for name in index["readiness_columns"]},
            "journal_evidence_ids": [entry["evidence_id"] for entry in contract["journal_evidence"]],
            "quarantine_evidence_id": contract["quarantine"]["evidence_id"] if contract["quarantine"] else None,
        }
        for contract in index["contracts"]
    ]
    payload = {
        "matrix_version": "1.0",
        "evidence_index_hash": index["index_hash"],
        "readiness_columns": index["readiness_columns"],
        "rows": rows,
    }
    return {**payload, "matrix_hash": "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()}


def build_manifest(index: dict[str, Any], supersedes: dict[str, str] | None) -> dict[str, Any]:
    contracts = [
        {
            "contract_id": contract["contract_id"],
            "family": contract["family"],
            "template_version": contract["contract_version"],
            **{
                name: _scheduler_check_status(name, contract["readiness_checks"][name])
                for name in index["readiness_columns"]
            },
            "status": contract["status"],
        }
        for contract in index["contracts"]
    ]
    payload: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "evidence_index_hash": index["index_hash"],
        "readiness_columns": index["readiness_columns"],
        "contracts": contracts,
    }
    if supersedes is not None:
        payload["supersedes"] = supersedes
    return {**payload, "manifest_hash": "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()}


def _markdown(index: dict[str, Any], counts: dict[str, int], old_hash: str | None) -> str:
    funnel = counts["fully_verified_funnels"]
    lines = [
        "# Phase 10 Readiness Diagnostic",
        "",
        "## Authoritative Result",
        "",
        f"- Current contracts: {counts['contracts']}",
        f"- Fully verified: {counts['fully_verified']}",
        f"- Funnel contracts: {counts['funnels']}; fully verified funnels: {funnel}",
        f"- Quarantined: {counts['quarantined']}; not ready: {counts['not_ready']}",
        "- The prior `56 fully verified / all 7 funnels passed` claim is superseded.",
        "- This is a readiness record, not a model, release, rights, or historical-run claim.",
        "",
        "## Evidence Authority",
        "",
        "The contract evidence index is authoritative. The matrix and manifest are derived from it; the count report independently reads the index and matrix without importing this generator.",
        f"Index: `{index['index_hash']}`.",
    ]
    if old_hash:
        lines.append(f"Superseded manifest SHA-256: `{old_hash}`.")
    lines.extend(["", "## Contract Status", "", "| Contract | Version | Status | Journal evidence |", "| --- | ---: | --- | ---: |"])
    for contract in index["contracts"]:
        lines.append(
            f"| `{contract['contract_id']}` | {contract['contract_version']} | {contract['status']} | {len(contract['journal_evidence'])} |"
        )
    return "\n".join(lines) + "\n"


def _counts(index: dict[str, Any]) -> dict[str, int]:
    statuses = Counter(contract["status"] for contract in index["contracts"])
    funnels = [contract for contract in index["contracts"] if contract["family"] == "funnel"]
    return {
        "contracts": len(index["contracts"]),
        "fully_verified": statuses["FULLY_VERIFIED"],
        "quarantined": statuses["QUARANTINED"],
        "not_ready": statuses["NOT_READY"],
        "funnels": len(funnels),
        "fully_verified_funnels": sum(contract["status"] == "FULLY_VERIFIED" for contract in funnels),
    }


def write_phase10(root: Path, output_dir: Path, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(UTC).date().isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    index = build_index(root, generated_at)
    index_path = output_dir / "phase10-contract-evidence-index.json"
    matrix_path = output_dir / "phase10-contract-matrix.json"
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    matrix = build_matrix(index)
    matrix_path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_path = root / "manifests" / "phase3-contract-readiness.json"
    old_hash = sha256_file(manifest_path) if manifest_path.exists() else None
    archive_path = None
    if old_hash is not None:
        archive_path = manifest_path.with_name(f"phase3-contract-readiness.superseded-{old_hash[:12]}.json")
        if not archive_path.exists():
            shutil.copyfile(manifest_path, archive_path)
        elif sha256_file(archive_path) != old_hash:
            raise ValueError(f"existing archive does not match prior manifest: {archive_path}")
    supersedes = None if old_hash is None else {"path": archive_path.relative_to(root).as_posix(), "sha256": old_hash}
    manifest = build_manifest(index, supersedes)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    counts = _counts(index)
    diagnostic = {
        "diagnostic_version": "1.0",
        "generated_at": generated_at,
        "evidence_index": {"path": index_path.relative_to(root).as_posix(), "sha256": sha256_file(index_path), "index_hash": index["index_hash"]},
        "matrix": {"path": matrix_path.relative_to(root).as_posix(), "sha256": sha256_file(matrix_path), "matrix_hash": matrix["matrix_hash"]},
        "manifest": {"path": manifest_path.relative_to(root).as_posix(), "sha256": sha256_file(manifest_path), "manifest_hash": manifest["manifest_hash"], "supersedes": supersedes},
        "totals": counts,
        "superseded_claim": "56 fully verified / all 7 funnels passed",
        "status": "PASS",
    }
    diagnostic_path = output_dir / f"phase10-readiness-diagnostic-{generated_at.replace('-', '')}.json"
    diagnostic_path.write_text(json.dumps(diagnostic, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path = output_dir / f"phase10-readiness-diagnostic-{generated_at.replace('-', '')}.md"
    markdown_path.write_text(_markdown(index, counts, old_hash), encoding="utf-8")
    return {"index": index_path, "matrix": matrix_path, "diagnostic": diagnostic_path, "markdown": markdown_path, "manifest": manifest_path, "counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default="scratch/funnel_experiment/evidence")
    parser.add_argument("--date", help="UTC date in YYYY-MM-DD; defaults to today")
    args = parser.parse_args()
    root = args.root.resolve()
    result = write_phase10(root, root / args.output_dir, args.date)
    print(json.dumps({"counts": result["counts"], "manifest": str(result["manifest"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
