"""Model supply-chain provenance (governance layer, Phase 6).

Records what is evidenced about a generating checkpoint — never what
is inferred. License, commercial-use, and redistribution conclusions
are recorded only when source artifacts establish them; otherwise the
status stays unresolved and the sale gate refuses silent clearance.
Historical model snapshots are never modified.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .errors import ProvenanceConfigError

SupplyChainStatus = Literal["UNVERIFIED", "DOCUMENTED", "REVIEW_REQUIRED", "APPROVED", "BLOCKED"]

SUPPLY_CHAIN_SCHEMA_VERSION = "1.0"


class ModelSupplyChain(BaseModel):
    """First-class supply-chain record for one generating checkpoint."""

    model_config = {"frozen": True}

    model_name: str = Field(min_length=1)
    model_revision: str = Field(default="UNKNOWN")
    source_provider: str = ""
    upstream_repository: str | None = None
    claimed_license: str | None = None
    license_source: str | None = None
    license_reference: str | None = None
    checkpoint_format: str | None = None
    quantization: str | None = None
    modifications: list[str] = Field(default_factory=list)
    abliterated_or_modified: bool = False
    parent_checkpoint: str | None = None
    commercial_use: str | None = None
    redistribution: str | None = None
    evidence_paths: list[str] = Field(default_factory=list)
    governance_status: SupplyChainStatus = "UNVERIFIED"
    approval_signoff: str | None = None
    model_snapshot_id: str | None = None
    notes: list[str] = Field(default_factory=list)
    schema_version: str = Field(default=SUPPLY_CHAIN_SCHEMA_VERSION, min_length=1)


def assess_supply_chain(
    *,
    model_name: str,
    model_revision: str = "UNKNOWN",
    evidence: dict[str, Any] | None = None,
) -> ModelSupplyChain:
    """Assemble a supply-chain record from evidenced facts only.

    ``evidence`` carries caller-verified fields (source_provider,
    claimed_license with its source, quantization, modifications, ...).
    Anything not evidenced stays empty/UNVERIFIED — never inferred.
    """
    evidence = evidence or {}
    modifications = list(evidence.get("modifications", []))
    abliterated = bool(evidence.get("abliterated_or_modified", False)) or any(
        "abliterat" in str(m).lower() for m in modifications
    )
    status: SupplyChainStatus = "UNVERIFIED"
    if evidence.get("governance_status") in (
        "DOCUMENTED",
        "REVIEW_REQUIRED",
        "APPROVED",
        "BLOCKED",
    ):
        status = evidence["governance_status"]
    elif abliterated or evidence.get("claimed_license") is None:
        status = "REVIEW_REQUIRED"
    elif evidence.get("claimed_license") is not None:
        status = "DOCUMENTED"
    return ModelSupplyChain(
        model_name=model_name,
        model_revision=model_revision,
        source_provider=str(evidence.get("source_provider", "")),
        upstream_repository=evidence.get("upstream_repository"),
        claimed_license=evidence.get("claimed_license"),
        license_source=evidence.get("license_source"),
        license_reference=evidence.get("license_reference"),
        checkpoint_format=evidence.get("checkpoint_format"),
        quantization=evidence.get("quantization"),
        modifications=modifications,
        abliterated_or_modified=abliterated,
        parent_checkpoint=evidence.get("parent_checkpoint"),
        commercial_use=evidence.get("commercial_use"),
        redistribution=evidence.get("redistribution"),
        evidence_paths=list(evidence.get("evidence_paths", [])),
        governance_status=status,
        approval_signoff=evidence.get("approval_signoff"),
        model_snapshot_id=evidence.get("model_snapshot_id"),
        notes=list(evidence.get("notes", [])),
    )


def commercial_clearance_decision(report: ModelSupplyChain) -> tuple[bool, list[str]]:
    """Sale gate: only APPROVED checkpoints may be labeled commercially cleared."""
    if report.governance_status == "APPROVED" and report.approval_signoff:
        return True, ["supply chain APPROVED with recorded sign-off"]
    reasons = [f"governance_status is {report.governance_status}, not APPROVED"]
    if report.governance_status == "APPROVED" and not report.approval_signoff:
        reasons.append("APPROVED status carries no approval sign-off")
    if report.abliterated_or_modified:
        reasons.append("checkpoint is abliterated/modified; re-review required")
    if report.claimed_license is None:
        reasons.append("no evidenced license; commercial use undetermined")
    return False, reasons


def require_explicit_revision(model_name: str, model_revision: str) -> str:
    """Refuse ambiguous model identities for future production runs.

    Production-001 recorded revision "unspecified" against its model
    name; that combination must never be reused silently. Future runs
    pin an exact revision/digest. Returns the normalized revision.
    """
    revision = (model_revision or "").strip()
    if not revision or revision.upper() in ("UNSPECIFIED", "UNKNOWN", "LATEST"):
        raise ProvenanceConfigError(
            f"model {model_name!r} needs an exact pinned revision/digest, got {model_revision!r}"
        )
    return revision


def supply_chain_report_payload(report: ModelSupplyChain) -> dict[str, Any]:
    """Machine-readable report dict for artifacts and gates."""
    allowed, reasons = commercial_clearance_decision(report)
    payload = report.model_dump(mode="json")
    payload["commercially_cleared"] = allowed
    payload["clearance_reasons"] = reasons
    return payload
