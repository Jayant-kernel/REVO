"""Fail-closed versioned qualification; historical receipts are not admission."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from verified_data_factory.task_engine.generator import generate_task
from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.task_engine.registry import load_builtin_registry
from verified_data_factory.task_engine.validation import validate_task

from .behavior_authority import public_behavior_map
from .models import COMPARISON_VERSION
from .oracle_registry import get_oracle
from .receipt_models import ArtifactRef, ReceiptV2
from .receipt_validation import (
    DetailValidator,
    artifact,
    confined,
    digest,
    encode,
    read_json,
    validate_sources,
)

REQUIRED = ("rules", "named_tests", "relations", "mutation", "challenge", "fixture_diversity", "fuzz")
LEGACY_DENIAL = "stale or unsupported legacy evidence"


def sha256(path: Path) -> str:
    return digest(path)


def public_contract(contract: str, version: int) -> None:
    if type(version) is not int or version < 1:
        raise ValueError("unknown public contract/version")
    try:
        load_builtin_registry().get(contract, version)
        get_oracle(contract, version)
    except Exception as exc:
        raise ValueError("unknown public contract/version") from exc


def effective_quarantine(root: Path, contract: str, version: int) -> bool:
    """Read the fixed root authority, never a caller's None/status/quarantine."""
    try:
        authority = json.loads(confined(root, "manifests/package-a-contract-quarantine.json").read_text(encoding="utf-8"))
        if type(authority.get("version")) is not int or authority["version"] != 1:
            raise ValueError("unknown quarantine schema")
        entries = authority["quarantines"]
        if not isinstance(entries, list):
            raise TypeError("quarantines must be a list")
        seen = set()
        quarantined = False
        matching_ids = set()
        for entry in entries:
            if (not isinstance(entry, dict) or not isinstance(entry.get("contract_id"), str)
                    or not entry["contract_id"] or type(entry.get("contract_version")) is not int
                    or entry["contract_version"] < 1 or not isinstance(entry.get("evidence_id"), str)
                    or not entry["evidence_id"] or not isinstance(entry.get("reason"), str)
                    or not entry["reason"] or not isinstance(entry.get("scope"), list)
                    or not entry["scope"] or not all(isinstance(s, str) and s for s in entry["scope"])):
                raise ValueError("invalid quarantine entry")
            identity = entry["contract_id"], entry["contract_version"], entry["evidence_id"]
            if identity in seen:
                raise ValueError("duplicate quarantine entry")
            seen.add(identity)
            if identity[:2] == (contract, version):
                quarantined = True
                matching_ids.add(entry["evidence_id"])
        if quarantined:
            from scripts.package_a_evidence import load_events, materialize

            directory = root / "scratch/funnel_experiment/evidence"
            if not (directory / "events.jsonl").is_file() or not (directory / "index.json").is_file():
                return True
            events = load_events(directory / "events.jsonl")
            index = materialize(events)
            if json.loads((directory / "index.json").read_text()) != index:
                raise ValueError("quarantine resolution index differs from journal")
            active = {entry["evidence_id"] for entry in index["entries"] if entry["status"] == "ACTIVE"}
            for event in reversed(events):
                if (event["event_type"] != "qualification_bundle_commit"
                        or (event["contract_id"], event["contract_version"]) != (contract, version)):
                    continue
                resolutions = set(event.get("resolves_absent_evidence_quarantines", []))
                if not resolutions or not matching_ids <= resolutions or not all(member["evidence_id"] in active for member in event["members"]):
                    continue
                original = [entry for entry in entries if entry["evidence_id"] in matching_ids
                            and (entry["contract_id"], entry["contract_version"]) == (contract, version)]
                reason = "complete requirement-specific counterexample evidence is absent; do not infer intent or proof from registration"
                if any(entry["reason"] != reason for entry in original):
                    continue
                bundle = json.loads(artifact(root, ArtifactRef(path=event["artifact_path"], sha256=event["sha256"])).read_text())
                effective_evidence(root, bundle)
                if all(receipt(root, bundle["evidence"][category], contract, version, category)[0] is not None for category in REQUIRED):
                    quarantined = False
                break
        return quarantined
    except Exception as exc:
        raise ValueError("missing or malformed quarantine authority") from exc


def receipt(
    root: Path, reference: Any, contract: str, version: int, category: str,
) -> tuple[dict[str, Any] | None, str]:
    try:
        path = artifact(root, ArtifactRef.model_validate(reference))
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 2:
            return None, LEGACY_DENIAL
        public_contract(contract, version)
        parsed = ReceiptV2.model_validate(data)
        if (parsed.contract_id, parsed.contract_version, parsed.category) != (contract, version, category):
            raise ValueError("contract/version/category binding mismatch")
        if parsed.unresolved_findings:
            raise ValueError("unresolved findings")
        oracle = get_oracle(contract, version)
        if parsed.oracle_version != oracle.oracle_version or parsed.comparison_version != COMPARISON_VERSION:
            raise ValueError("stale oracle/comparison identifier")
        thresholds = validate_sources(root, parsed)
        task = TaskInstance.model_validate(read_json(root, parsed.task))
        validate_task(task)
        if (task.template_id, task.template_version) != (contract, version):
            raise ValueError("task/contract/version binding mismatch")
        canonical = generate_task(load_builtin_registry().get(contract, version), task.seed,
                                  task.generation_metadata.config)
        if encode(task.model_dump(mode="json", by_alias=True)) != encode(canonical.model_dump(mode="json", by_alias=True)):
            raise ValueError("retained base task differs from canonical generation inputs")
        authority = public_behavior_map(task)
        if not authority.task_matches_public_contract:
            raise ValueError(authority.blocked_reason)
        if parsed.behavior_map_sha256 != authority.declaration_sha256:
            raise ValueError("stale public behavior authority")
        DetailValidator(root, task, authority, parsed.source_hashes, thresholds).validate(parsed)
        return data, "fresh executed evidence"
    except ValidationError:
        return None, "missing or malformed detailed evidence"
    except (OSError, KeyError, TypeError, AttributeError):
        return None, "missing or malformed evidence"
    except ValueError as exc:
        return None, str(exc)
    except Exception:  # noqa: BLE001 — recomputation faults never admit evidence
        return None, "detail recomputation failed; evidence not admitted"


def effective_evidence(root: Path, record: dict[str, Any]) -> None:
    """Read-only shared journal materialization; index must match the journal."""
    from scripts.package_a_evidence import load_events, materialize

    directory = "scratch/funnel_experiment/evidence/"
    journal = confined(root, directory + "events.jsonl")
    index = confined(root, directory + "index.json")
    if not journal.is_file() or not index.is_file():
        raise ValueError("missing effective evidence journal/index authority")
    expected = materialize(load_events(journal))
    actual = json.loads(index.read_text(encoding="utf-8"))
    if actual != expected:
        raise ValueError("effective evidence index differs from journal")
    entries = {entry["evidence_id"]: entry for entry in expected["entries"]}
    for category in REQUIRED:
        reference = record.get("evidence", {}).get(category)
        if not reference:
            raise ValueError("effective category evidence absent")
        data = json.loads(artifact(root, ArtifactRef.model_validate(reference)).read_text())
        event = entries.get(data.get("evidence_id"))
        if (event is None or event["status"] != "ACTIVE" or event["superseded_by"] is not None
                or event["contract_id"] != record.get("contract_id")
                or event["contract_version"] != record.get("contract_version")
                or event["artifact_path"] != reference["path"] or event["sha256"] != reference["sha256"]
                or event["producer_script"] != data.get("producer")
                or event.get("category") != category):
            raise ValueError("category evidence absent, superseded or misbound in authoritative journal")
        if event.get("bundle") is not None:
            bundle = json.loads(artifact(root, ArtifactRef.model_validate(event["bundle"])).read_text())
            if (bundle.get("contract_id"), bundle.get("contract_version"), bundle.get("evidence")) != (
                record.get("contract_id"), record.get("contract_version"), record.get("evidence"),
            ):
                raise ValueError("bundle authority binding differs")


def qualify(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    quarantined = False
    contract, version = record.get("contract_id", ""), record.get("contract_version", 0)
    try:
        public_contract(contract, version)
    except ValueError as exc:
        reasons.append(str(exc))
    try:
        quarantined = effective_quarantine(root, contract, version)
        if quarantined:
            reasons.append("active authoritative quarantine")
    except ValueError as exc:
        reasons.append(str(exc))
    if record.get("independence") not in {"differential verification", "independence established"}:
        reasons.append("unsupported independence claim")
    prerequisites = record.get("prerequisites")
    if not isinstance(prerequisites, dict) or not prerequisites or not all(v is True for v in prerequisites.values()):
        reasons.append("structural prerequisites incomplete")
    evidence = record.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    for category in REQUIRED:
        _, reason = receipt(root, evidence.get(category), contract, version, category)
        if reason != "fresh executed evidence":
            reasons.append(f"{category}: {reason}")
    try:
        effective_evidence(root, record)
    except Exception as exc:  # noqa: BLE001 — journal faults never admit evidence
        reasons.append(str(exc) if isinstance(exc, ValueError) else "missing or malformed effective evidence authority")
    return {"eligible": not reasons, "reasons": reasons,
            "status": "QUARANTINED" if quarantined else "NOT_READY" if reasons else "FULLY_VERIFIED"}


def authoritative_records(root: Path) -> list[dict[str, Any]]:
    """Discover committed bundles; freshness/admission still requires qualify()."""
    from scripts.package_a_evidence import load_events, materialize

    directory = root / "scratch/funnel_experiment/evidence"
    index = materialize(load_events(directory / "events.jsonl"))
    if json.loads((directory / "index.json").read_text()) != index:
        raise ValueError("effective evidence index differs from journal")
    records = []
    for entry in index["entries"]:
        if entry["status"] == "ACTIVE" and entry.get("category") == "rules" and entry.get("bundle"):
            record = json.loads(artifact(root, ArtifactRef.model_validate(entry["bundle"])).read_text())
            effective_evidence(root, record)
            records.append(record)
    return records
