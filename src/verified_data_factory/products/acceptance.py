"""Content-bound strict acceptance and bundled source/qualification replay inputs."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from verified_data_factory.local_paths import io_path
from verified_data_factory.quality.models import GoldenRecord
from verified_data_factory.verification.receipt_models import ArtifactRef
from verified_data_factory.verification.receipt_validation import artifact, digest

from .errors import ProductConfigError
from .isolation import isolation_keys


def retain_replay_inputs(source: Path, destination: Path, dependencies: dict[str, str], records: list[dict[str, Any]]) -> None:
    copied: set[str] = set()

    def copy(relative: str, checksum: str, *, inspect_receipt: bool = False) -> None:
        if relative in copied:
            return
        path = artifact(source, ArtifactRef(path=relative, sha256=checksum))
        target = io_path(destination / relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if digest(target) != checksum:
            raise ProductConfigError("replay input changed during copy")
        copied.add(relative)
        if inspect_receipt and path.suffix == ".json":
            data = json.loads(path.read_text())
            if isinstance(data, dict) and data.get("schema_version") == 2 and "details" in data and "task" in data:
                walk(data)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if set(value) == {"path", "sha256"}:
                copy(value["path"], value["sha256"], inspect_receipt=True)
            for relative, checksum in value.get("source_hashes", {}).items():
                copy(relative, checksum)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for relative, checksum in dependencies.items():
        copy(relative, checksum)
    for record in records:
        walk(record)
    identities = {(record["contract_id"], record["contract_version"]) for record in records}
    index = json.loads((source / "scratch/funnel_experiment/evidence/index.json").read_text())
    for entry in index["entries"]:
        if (entry["status"] == "ACTIVE" and entry.get("category") == "rules" and entry.get("bundle")
                and (entry["contract_id"], entry["contract_version"]) in identities):
            walk(entry["bundle"])
    for relative in ("scratch/funnel_experiment/evidence/events.jsonl", "scratch/funnel_experiment/evidence/index.json",
                     "manifests/package-a-contract-quarantine.json"):
        copy(relative, digest(source / relative))


def acceptance_payload(snapshot: Any, goldens: list[Any], qualities: dict[str, Any],
                       product_records: list[dict[str, Any]], authority: dict[str, Any], role: str) -> dict[str, Any]:
    from .isolation import digest as content_digest

    return {"version": 1, "scope": "automated engineering acceptance; human/rights/utility not measured",
            "snapshot": snapshot.model_dump(mode="json"), "registry_id": authority["registry_id"],
            "role": role, "members": [{"golden": g.model_dump(mode="json", by_alias=True),
            "quality": qualities[g.candidate_id], "isolation_keys": sorted(isolation_keys(g))} for g in goldens],
            "record_bindings": {row["golden_record_id"]: content_digest(row) for row in product_records}}


def validate_acceptance(root: Path, manifest: Any, records: list[dict[str, Any]]) -> list[str]:
    from verified_data_factory.provenance.models import DatasetSnapshot

    from .engineering import check_source
    from .isolation import digest as content_digest
    from .release import _snapshot_member

    try:
        payload = json.loads((root / "engineering_acceptance.json").read_text())
        snapshot = DatasetSnapshot.model_validate(payload["snapshot"])
        if payload["version"] != 1 or snapshot.dataset_snapshot_id != manifest.dataset_snapshot_id:
            return ["engineering acceptance snapshot binding differs"]
        if payload["record_bindings"] != {row["golden_record_id"]: content_digest(row) for row in records}:
            return ["engineering acceptance record content differs"]
        source = root / "replay_root"
        role = "TRAIN" if manifest.product_type in {"TRAIN", "SAMPLE"} else "EVAL"
        registry = json.loads((root / "engineering_isolation.json").read_text())
        if payload["registry_id"] != registry["registry_id"] or payload["role"] != role:
            return ["engineering isolation authority binding differs"]
        members = {entry["golden"]["record_id"]: entry for entry in payload["members"]}
        if len(members) != len(payload["members"]) or set(members) != {row["golden_record_id"] for row in records}:
            return ["engineering acceptance membership differs"]
        shipped = [GoldenRecord.model_validate(entry["golden"]) for entry in members.values()]
        exclusions = payload.get("exclusions", {})
        if any(not _snapshot_member(golden, set(snapshot.golden_record_ids)) for golden in shipped):
            return ["engineering accepted member absent from snapshot"]
        missing = {member for member in snapshot.golden_record_ids if not any(_snapshot_member(g, {member}) for g in shipped)}
        if missing != set(exclusions) or any(not reason for reason in exclusions.values()):
            return ["engineering exclusions do not account for snapshot membership"]
        for row in records:
            entry = members[row["golden_record_id"]]
            golden = GoldenRecord.model_validate(entry["golden"])
            keys = sorted(isolation_keys(golden))
            if entry["isolation_keys"] != keys or any(registry["roles"].get(key) != role for key in keys):
                return ["engineering role reservation missing or conflicting"]
            if row.get("sql", golden.candidate_solution) != golden.candidate_solution:
                return ["engineering SQL differs from accepted source"]
            check_source(golden, entry["quality"], source)
        return []
    except (OSError, ValueError, KeyError, TypeError, ProductConfigError) as exc:
        return [f"engineering acceptance unavailable or replay failed: {type(exc).__name__}: {exc}"]
