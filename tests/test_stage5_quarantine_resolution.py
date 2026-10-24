"""Resolution admission uses actual complete SLA proofs, preserving quarantine history."""
import json
import shutil
from pathlib import Path

import pytest

from scripts.engineering_qualification_authority import promote
from scripts.engineering_qualification_receipts import INPUTS, collect
from scripts.package_a_evidence import load_events, materialize, source_tree_identity
from verified_data_factory.verification.readiness import effective_quarantine, qualify
from verified_data_factory.verification.receipt_models import ArtifactRef
from verified_data_factory.verification.receipt_validation import digest

pytest_plugins = ["tests.test_stage2_receipt_producer"]
CONTRACT = "sql.aggregation.fulfillment_sla_dashboard"
REASON = "complete requirement-specific counterexample evidence is absent; do not infer intent or proof from registration"


def test_authentic_resolution_renewal_and_tamper_denial(producer_root, monkeypatch):
    live = Path(__file__).resolve().parents[1]
    # The copied proof fixture has no Git checkout; retain its actual parent identity.
    parent_identity = source_tree_identity(live)
    monkeypatch.setattr("scripts.engineering_qualification_authority.source_tree_identity",
                        lambda root: parent_identity)
    for relative in INPUTS:
        target = producer_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(live / relative, target)
    manifest = producer_root / "manifests/package-a-contract-quarantine.json"
    manifest.parent.mkdir(exist_ok=True)
    authority = {"version": 1, "quarantines": [{"contract_id": CONTRACT,
        "contract_version": 1, "evidence_id": "historical-missing-proof",
        "reason": REASON, "scope": ["qualification"]}]}
    manifest.write_text(json.dumps(authority))
    original = manifest.read_bytes()
    record = collect(producer_root, "authentic-sla-first", CONTRACT, 1)
    bundle = producer_root / "authentic-sla-first/bundle.json"
    ref = ArtifactRef(path="authentic-sla-first/bundle.json", sha256=digest(bundle))
    assert effective_quarantine(producer_root, CONTRACT, 1)
    with pytest.raises(ValueError, match="active authoritative quarantine"):
        promote(producer_root, ref)
    journal = producer_root / "scratch/funnel_experiment/evidence/events.jsonl"
    assert not journal.exists()

    # A genuine bundle cannot clear an unrelated semantic quarantine.
    authority["quarantines"][0]["reason"] = "unresolved semantic survivor"
    manifest.write_text(json.dumps(authority))
    with pytest.raises(ValueError, match="active authoritative quarantine"):
        promote(producer_root, ref, resolve_absent_evidence=True)
    manifest.write_bytes(original)
    first = promote(producer_root, ref, resolve_absent_evidence=True)
    assert first["resolves_absent_evidence_quarantines"] == ["historical-missing-proof"]
    assert qualify(producer_root, record)["eligible"]
    assert manifest.read_bytes() == original

    renewed = collect(producer_root, "authentic-sla-renewed", CONTRACT, 1)
    renewed_bundle = producer_root / "authentic-sla-renewed/bundle.json"
    second = promote(producer_root, ArtifactRef(path="authentic-sla-renewed/bundle.json",
                                              sha256=digest(renewed_bundle)))
    assert second["resolves_absent_evidence_quarantines"] == first["resolves_absent_evidence_quarantines"]
    assert qualify(producer_root, renewed)["eligible"]
    assert not qualify(producer_root, record)["eligible"]
    assert manifest.read_bytes() == original
    events = load_events(journal)
    assert len(events) == 2
    assert sum(entry["status"] == "ACTIVE" for entry in materialize(events)["entries"]) == 7

    # A journal/index discrepancy cannot continue to clear the quarantine.
    index = journal.with_name("index.json")
    original_index = index.read_bytes()
    index.write_text("{}")
    assert not qualify(producer_root, renewed)["eligible"]
    index.write_bytes(original_index)
    # Even checksum-valid category metadata needs current, executable dependencies.
    source = producer_root / "scripts/engineering_qualification_authority.py"
    source.write_text(source.read_text() + "\n# changed after proof\n")
    assert effective_quarantine(producer_root, CONTRACT, 1)
    assert not qualify(producer_root, renewed)["eligible"]
