"""Frozen blind-review package with content-bound, append-only decisions.

Reviewer identity is a supplied identifier, not authenticated identity. The
operator must control access and verify that the named humans made decisions.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .export import build_golden_record_id
from .models import GoldenRecord


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def freeze_review_package(
    golden_jsonl: str | Path, out_dir: str | Path, *, premium: bool = False
) -> dict[str, Any]:
    """Create a diagnostic or pre-screened premium package without replacement."""
    source = Path(golden_jsonl)
    root = Path(out_dir)
    if root.exists():
        raise ValueError(f"review package destination already exists: {root}")
    if premium:
        from .premium_candidate import assess_premium_candidate

        assessment = assess_premium_candidate(source)
        if not assessment["automated_pre_review_gates_pass"]:
            failed = [name for name, gate in assessment["gates"].items() if not gate["passed"]]
            raise ValueError(f"premium pre-review gates failed: {', '.join(failed)}")
    rows = _read_jsonl(source)
    if not rows:
        raise ValueError("review package source contains no Golden rows")
    items: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda value: value["record_id"]):
        GoldenRecord.model_validate(row)
        bound_id = build_golden_record_id(
            task=row["task"],
            instruction=row["instruction"],
            schema=row["schema"],
            candidate_solution=row["candidate_solution"],
            record_schema_version=row.get("record_schema_version", "2.0"),
        )
        if row["record_id"] != bound_id:
            raise ValueError(f"Golden record identity is not content-bound: {row['record_id']}")
        verification = row["verification"]
        if (
            verification.get("verdict") != "PASS"
            or verification.get("verification_strength") != "STRONG"
            or verification.get("mutation", {}).get("mutation_score") != 1.0
            or row["quality"].get("decision") != "GOLDEN"
        ):
            raise ValueError(f"record lacks premium automated qualification: {row['record_id']}")
        item = {
            "record_id": row["record_id"],
            "candidate_id": row["candidate_id"],
            "instruction": row["instruction"],
            "schema": row["schema"],
            "candidate_sql": row["candidate_solution"],
            "expected_result": verification["oracle"]["expected"],
            "edge_cases": row["fixture"].get("edge_cases", []),
            "verification_summary": {
                "verdict": verification["verdict"],
                "strength": verification.get("verification_strength"),
                "hidden_passed": verification.get("hidden", {}).get("passed"),
                "property_passed": verification.get("properties", {}).get("passed"),
                "metamorphic_passed": verification.get("metamorphic", {}).get("passed"),
                "mutation": verification.get("mutation"),
            },
            "family": row["quality"]["family"],
            "difficulty": row["quality"].get("difficulty"),
            "source_row_hash": _digest(row),
        }
        item["item_hash"] = _digest(item)
        items.append(item)
    ids = [item["record_id"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate record identity in review package")
    source_hash = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    manifest: dict[str, Any] = {
        "format": "verified-data-factory/review/1.0",
        "label": (
            "Internal verified release candidate — human review pending"
            if premium
            else "Internal verified diagnostic review package — human review pending"
        ),
        "candidate_class": "PREMIUM_PRE_REVIEW" if premium else "DIAGNOSTIC",
        "source_sha256": source_hash,
        "item_count": len(items),
        "item_hashes": {item["record_id"]: item["item_hash"] for item in items},
    }
    manifest["package_id"] = _digest(manifest)
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (root / "items.jsonl").open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    return manifest


def _load_package(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    package_id = manifest.pop("package_id")
    if _digest(manifest) != package_id:
        raise ValueError("review manifest hash mismatch")
    manifest["package_id"] = package_id
    item_rows = _read_jsonl(root / "items.jsonl")
    items = {item["record_id"]: item for item in item_rows}
    if len(item_rows) != len(items):
        raise ValueError("duplicate review item identity")
    if len(items) != manifest["item_count"] or set(items) != set(manifest["item_hashes"]):
        raise ValueError("review package membership changed")
    for record_id, item in items.items():
        item_hash = item.pop("item_hash")
        if _digest(item) != item_hash or manifest["item_hashes"][record_id] != item_hash:
            raise ValueError(f"review item changed: {record_id}")
        item["item_hash"] = item_hash
    return manifest, items


def _journal(
    root: Path, manifest: dict[str, Any], items: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    path = root / "decisions.jsonl"
    if not path.exists():
        return []
    entries = _read_jsonl(path)
    previous = None
    prior_by_record: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        entry_hash = entry.pop("entry_hash")
        if (
            _digest(entry) != entry_hash
            or entry["previous_hash"] != previous
            or entry["package_id"] != manifest["package_id"]
            or entry["record_id"] not in items
            or entry["item_hash"] != items[entry["record_id"]]["item_hash"]
        ):
            raise ValueError("review journal identity or hash chain mismatch")
        prior = prior_by_record.setdefault(entry["record_id"], [])
        if (
            entry["slot"] not in ("first", "second", "adjudicator")
            or entry["verdict"] not in ("PASS", "FAIL", "UNCLEAR")
            or any(old["slot"] == entry["slot"] for old in prior)
            or any(old["reviewer_id"] == entry["reviewer_id"] for old in prior)
            or (entry["slot"] == "second" and not any(old["slot"] == "first" for old in prior))
            or (entry["slot"] == "adjudicator" and _record_status(prior) != "ADJUDICATION_REQUIRED")
        ):
            raise ValueError("review journal violates independent decision sequence")
        prior.append(entry)
        entry["entry_hash"] = entry_hash
        previous = entry_hash
    return entries


def _record_status(entries: list[dict[str, Any]]) -> str:
    first = next((e for e in entries if e["slot"] == "first"), None)
    second = next((e for e in entries if e["slot"] == "second"), None)
    adjudicator = next((e for e in entries if e["slot"] == "adjudicator"), None)
    if not first or not second:
        return "PENDING"
    if first["verdict"] == second["verdict"] and first["verdict"] != "UNCLEAR":
        return str(first["verdict"])
    return str(adjudicator["verdict"]) if adjudicator else "ADJUDICATION_REQUIRED"


def review_status(out_dir: str | Path) -> dict[str, Any]:
    root = Path(out_dir)
    manifest, items = _load_package(root)
    entries = _journal(root, manifest, items)
    by_record: dict[str, list[dict[str, Any]]] = {record_id: [] for record_id in items}
    for entry in entries:
        by_record[entry["record_id"]].append(entry)
    return {
        "package_id": manifest["package_id"],
        "candidate_class": manifest["candidate_class"],
        "item_count": len(items),
        "decisions": len(entries),
        "status_by_record": {
            record_id: _record_status(by_record[record_id]) for record_id in sorted(items)
        },
    }


def reviewed_items(out_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Return content-verified frozen items for downstream content binding."""
    _manifest, items = _load_package(Path(out_dir))
    return items


def append_review_decision(
    out_dir: str | Path,
    *,
    record_id: str,
    reviewer_id: str,
    slot: str,
    verdict: str,
    reason: str,
    rubric_version: str,
) -> dict[str, Any]:
    reviewer_id = reviewer_id.strip()
    root = Path(out_dir)
    manifest, items = _load_package(root)
    entries = _journal(root, manifest, items)
    if record_id not in items:
        raise ValueError(f"record not in package: {record_id}")
    if not reviewer_id.strip() or not reason.strip() or not rubric_version.strip():
        raise ValueError("reviewer identity, reason, and rubric version are required")
    if slot not in ("first", "second", "adjudicator") or verdict not in ("PASS", "FAIL", "UNCLEAR"):
        raise ValueError("invalid review slot or verdict")
    prior = [entry for entry in entries if entry["record_id"] == record_id]
    if any(entry["slot"] == slot for entry in prior):
        raise ValueError("review slot already has a decision; corrections need a new package")
    if reviewer_id in {entry["reviewer_id"] for entry in prior}:
        raise ValueError("independent review requires distinct reviewer identities")
    if slot == "second" and not any(entry["slot"] == "first" for entry in prior):
        raise ValueError("first review is missing")
    if slot == "adjudicator" and _record_status(prior) != "ADJUDICATION_REQUIRED":
        raise ValueError("adjudication is only allowed after disagreement")
    entry = {
        "package_id": manifest["package_id"],
        "record_id": record_id,
        "item_hash": items[record_id]["item_hash"],
        "reviewer_id": reviewer_id,
        "slot": slot,
        "verdict": verdict,
        "reason": reason,
        "rubric_version": rubric_version,
        "recorded_at": datetime.now(UTC).isoformat(),
        "previous_hash": entries[-1]["entry_hash"] if entries else None,
    }
    entry["entry_hash"] = _digest(entry)
    path = root / "decisions.jsonl"
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(descriptor, _canonical(entry) + b"\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return entry


def export_review_evidence(
    out_dir: str | Path, golden_jsonl: str | Path, evidence_dir: str | Path
) -> dict[str, Any]:
    """Build derived review evidence only when every frozen row passed."""
    root = Path(out_dir)
    manifest, items = _load_package(root)
    entries = _journal(root, manifest, items)
    status = review_status(root)
    if any(verdict != "PASS" for verdict in status["status_by_record"].values()):
        raise ValueError("every frozen review row needs final PASS")
    source = Path(golden_jsonl)
    if "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest() != manifest["source_sha256"]:
        raise ValueError("source Golden JSONL changed since review package freeze")
    rows = _read_jsonl(source)
    if len(rows) != len(items):
        raise ValueError("source Golden membership changed")
    qualities = []
    for row in rows:
        item = items.get(row["record_id"])
        if item is None or _digest(row) != item["source_row_hash"]:
            raise ValueError("source Golden row changed")
        quality = dict(row["quality"])
        quality["auditor_result"] = "PASS"
        quality["audit_status"] = "PASS"
        quality["review_package_id"] = manifest["package_id"]
        qualities.append(quality)
    target = Path(evidence_dir)
    if target.exists():
        raise ValueError(f"derived review evidence destination already exists: {target}")
    target.mkdir(parents=True)
    (target / "qualities.json").write_text(
        json.dumps(qualities, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "review_package_id": manifest["package_id"],
        "source_sha256": manifest["source_sha256"],
        "row_count": len(items),
        "decisions": entries,
        "final_status_by_record": status["status_by_record"],
        "journal_tip": entries[-1]["entry_hash"] if entries else None,
    }
    (target / "review-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
