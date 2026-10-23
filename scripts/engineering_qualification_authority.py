"""Commit all seven validated categories in one durable authoritative event."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.package_a_evidence import load_events, materialize, source_tree_identity
from verified_data_factory.local_lock import exclusive_lock
from verified_data_factory.local_paths import io_path
from verified_data_factory.verification.readiness import REQUIRED, effective_quarantine, receipt
from verified_data_factory.verification.receipt_models import ArtifactRef
from verified_data_factory.verification.receipt_validation import artifact, digest


def promote(root: Path, manifest: ArtifactRef, *, resolve_absent_evidence: bool = False) -> dict[str, Any]:
    record = json.loads(artifact(root, manifest).read_text())
    contract, version = record["contract_id"], record["contract_version"]
    if set(record["evidence"]) != set(REQUIRED):
        raise ValueError("incomplete qualification bundle")
    directory = root / "scratch/funnel_experiment/evidence"
    with exclusive_lock(io_path(directory / "authority.lock")):
        resolutions = []
        quarantined = effective_quarantine(root, contract, version)
        quarantines = json.loads((root / "manifests/package-a-contract-quarantine.json").read_text())["quarantines"]
        matching = [entry for entry in quarantines if (entry["contract_id"], entry["contract_version"]) == (contract, version)]
        allowed_reason = "complete requirement-specific counterexample evidence is absent; do not infer intent or proof from registration"
        if matching:
            if (quarantined and not resolve_absent_evidence) or any(entry["reason"] != allowed_reason for entry in matching):
                raise ValueError("active authoritative quarantine; only proven absent-evidence resolutions are supported")
            # Renew the resolution with its new fully replayed supporting members.
            resolutions = [entry["evidence_id"] for entry in matching]
        elif quarantined:
            raise ValueError("active authoritative quarantine has no matching manifest entry")
        journal = io_path(directory / "events.jsonl")
        events = load_events(journal)
        prior_entries = materialize(events)["entries"]
        members = []
        for category in REQUIRED:
            reference = record["evidence"][category]
            data, reason = receipt(root, reference, contract, version, category)
            if data is None:
                raise ValueError(f"{category}: {reason}")
            prior = [entry for entry in prior_entries if entry["status"] == "ACTIVE"
                     and entry.get("category") == category and entry["contract_id"] == contract
                     and entry["contract_version"] == version]
            if len(prior) > 1:
                raise ValueError("ambiguous active category authority; resolve supersession explicitly")
            members.append({
                "evidence_id": data["evidence_id"], "event_type": "qualification_category",
                "artifact_path": reference["path"], "sha256": reference["sha256"], "status": "ACTIVE",
                "supersedes": prior[0]["evidence_id"] if prior else None,
                "superseded_by": None, "producer_script": data["producer"],
                "producer_command": "python -m scripts.engineering_qualification_receipts",
                "created_at": datetime.now(UTC).isoformat(),
                "contract_id": contract, "contract_version": version, "category": category,
                "phase": "stage2", "notes": "differential verification; independent authorship unproven",
                "bundle": manifest.model_dump(),
            })
        # One transaction publishes all members; capture its source after replay.
        source = source_tree_identity(root)
        for member in members:
            member["source_tree_identity"] = source
        event = {**members[0], "evidence_id": "bundle-" + manifest.sha256,
                 "event_type": "qualification_bundle_commit", "artifact_path": manifest.path,
                 "sha256": manifest.sha256, "members": members,
                 "resolves_absent_evidence_quarantines": resolutions}
        index = materialize([*events, event])
        # Source/input changes during replay deny publication.
        for category in REQUIRED:
            data = json.loads(artifact(root, ArtifactRef.model_validate(record["evidence"][category])).read_text())
            for relative, expected in data["source_hashes"].items():
                artifact(root, ArtifactRef(path=relative, sha256=expected))
        if digest(artifact(root, manifest)) != manifest.sha256:
            raise ValueError("bundle changed during replay")
        # One JSONL event contains all categories. A torn write denies journal parsing;
        # a crash before index replacement denies the journal/index consistency check.
        with journal.open("ab") as handle:
            handle.write((json.dumps(event, sort_keys=True) + "\n").encode())
            handle.flush()
            os.fsync(handle.fileno())
        temporary = io_path(directory / ("index-" + manifest.sha256 + ".pending"))
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(index, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(io_path(directory / "index.json"))
        return event
