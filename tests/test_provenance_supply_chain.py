"""Model supply-chain governance tests (§3 remediation)."""

from verified_data_factory.provenance import (
    ModelSupplyChain,
    assess_supply_chain,
    commercial_clearance_decision,
    require_explicit_revision,
    supply_chain_report_payload,
)
from verified_data_factory.provenance.errors import ProvenanceConfigError


def test_unverified_by_default():
    report = assess_supply_chain(model_name="some-model", model_revision="rev-1")
    assert report.governance_status == "REVIEW_REQUIRED"
    assert report.claimed_license is None
    allowed, reasons = commercial_clearance_decision(report)
    assert allowed is False
    assert reasons


def test_abliterated_forces_review():
    report = assess_supply_chain(
        model_name="third-party-quant",
        evidence={"modifications": ["abliterated safety removal"], "claimed_license": "Apache-2.0"},
    )
    assert report.abliterated_or_modified is True
    assert report.governance_status == "REVIEW_REQUIRED"
    allowed, _ = commercial_clearance_decision(report)
    assert allowed is False


def test_documented_license_without_approval_still_blocked():
    report = assess_supply_chain(
        model_name="official-model",
        evidence={
            "claimed_license": "Apache-2.0",
            "license_source": "vendor docs",
            "governance_status": "DOCUMENTED",
        },
    )
    assert report.governance_status == "DOCUMENTED"
    allowed, reasons = commercial_clearance_decision(report)
    assert allowed is False
    assert any("not APPROVED" in r for r in reasons)


def test_approved_with_signoff_clears():
    report = assess_supply_chain(
        model_name="official-model",
        evidence={
            "claimed_license": "Apache-2.0",
            "license_source": "vendor docs",
            "governance_status": "APPROVED",
            "approval_signoff": "counsel 2026-09-26",
        },
    )
    allowed, _ = commercial_clearance_decision(report)
    assert allowed is True


def test_approved_without_signoff_blocked():
    report = assess_supply_chain(
        model_name="official-model",
        evidence={"claimed_license": "Apache-2.0", "governance_status": "APPROVED"},
    )
    allowed, reasons = commercial_clearance_decision(report)
    assert allowed is False
    assert any("sign-off" in r for r in reasons)


def test_report_payload_is_machine_readable():
    report = assess_supply_chain(model_name="m")
    payload = supply_chain_report_payload(report)
    assert payload["commercially_cleared"] is False
    assert isinstance(payload["clearance_reasons"], list) and payload["clearance_reasons"]
    assert isinstance(report, ModelSupplyChain)
    assert report.model_dump(mode="json")["governance_status"] == "REVIEW_REQUIRED"


def test_hypothetical_approved_checkpoint_ingests_cleanly():
    """Fixture-only validation path for a future approved checkpoint (§2)."""
    report = assess_supply_chain(
        model_name="vendor/official-model:2.0",
        model_revision="sha256:abc123",
        evidence={
            "source_provider": "vendor registry",
            "upstream_repository": "https://example.invalid/vendor/official-model",
            "claimed_license": "Apache-2.0",
            "license_source": "vendor license page",
            "license_reference": "https://example.invalid/vendor/license",
            "checkpoint_format": "safetensors",
            "quantization": "none",
            "modifications": [],
            "parent_checkpoint": "vendor/official-model:1.0",
            "commercial_use": "permitted per license",
            "redistribution": "permitted per license",
            "evidence_paths": ["fixture-only"],
            "governance_status": "APPROVED",
            "approval_signoff": "counsel-fixture 2026-09-26",
            "model_snapshot_id": "sha256:fixture-snapshot",
        },
    )
    assert report.model_name == "vendor/official-model:2.0"
    assert report.model_revision == "sha256:abc123"
    assert report.upstream_repository is not None
    assert report.claimed_license == "Apache-2.0"
    assert report.license_source == "vendor license page"
    assert report.abliterated_or_modified is False
    assert report.parent_checkpoint == "vendor/official-model:1.0"
    assert report.quantization == "none"
    assert report.checkpoint_format == "safetensors"
    assert report.commercial_use is not None and report.redistribution is not None
    assert report.governance_status == "APPROVED"
    allowed, _ = commercial_clearance_decision(report)
    assert allowed is True


def test_production_001_report_stays_unresolved():
    """The Production-001 checkpoint must remain REVIEW_REQUIRED / not cleared."""
    import json
    from pathlib import Path

    payload = json.loads(Path("runs/production-001/supply-chain.json").read_text(encoding="utf-8"))
    assert payload["governance_status"] == "REVIEW_REQUIRED"
    assert payload["commercially_cleared"] is False
    assert "abliterat" in " ".join(payload["modifications"]).lower()
    assert payload["claimed_license"] is None


def test_explicit_revision_required_for_future_runs():
    import pytest

    assert require_explicit_revision("vendor/model:2.0", "sha256:abc123") == "sha256:abc123"
    for ambiguous in ("", "unspecified", "UNSPECIFIED", "UNKNOWN", "latest"):
        with pytest.raises(ProvenanceConfigError):
            require_explicit_revision("vendor/model:2.0", ambiguous)


def test_production_001_identity_refused_as_ambiguous():
    import pytest

    with pytest.raises(ProvenanceConfigError):
        require_explicit_revision(
            "alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest",
            "unspecified",
        )


def test_generation_run_ids_unique():
    from verified_data_factory.provenance import new_run_id

    assert new_run_id() != new_run_id()
