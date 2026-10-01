"""Release safety-gate tests (§9 remediation)."""

import json

import pytest

from tests.product_fixtures import build_product_fixture
from verified_data_factory.products import (
    ProductConfig,
    build_release,
    validate_release,
)
from verified_data_factory.products.errors import ProductConfigError, ProductIOError


def _release(tmp_path, name="g", **kwargs):
    goldens, quality_by_id, snapshot = build_product_fixture()
    return (
        build_release(
            snapshot=snapshot,
            golden_records=goldens,
            quality_by_id=quality_by_id,
            config=ProductConfig(product_name=name, product_type="TRAIN", visibility="INTERNAL"),
            out_dir=tmp_path / name,
            factory_version="0.7.0",
            provenance_version="1.0",
            **kwargs,
        ),
        goldens,
        quality_by_id,
        snapshot,
    )


def test_quarantined_member_refuses_build(tmp_path):
    goldens, quality_by_id, snapshot = build_product_fixture()
    with pytest.raises(ProductConfigError, match="quarantined"):
        build_release(
            snapshot=snapshot,
            golden_records=goldens,
            quality_by_id=quality_by_id,
            config=ProductConfig(product_name="q", product_type="TRAIN", visibility="INTERNAL"),
            out_dir=tmp_path / "q",
            factory_version="0.7.0",
            provenance_version="1.0",
            quarantined_ids={goldens[0].candidate_id},
        )


def test_validate_rejects_quarantined_shipment(tmp_path):
    _built, _, _, _ = _release(tmp_path, name="v")
    with open(tmp_path / "v" / "data" / "shard-00000.jsonl", encoding="utf-8") as _fh:
        record_id = json.loads(_fh.readline())["golden_record_id"]
    report = validate_release(tmp_path / "v", quarantined_ids={record_id})
    assert report.status == "INVALID"
    assert any(e.check == "release.quarantine" for e in report.errors)


def test_validate_mutation_evidence_gate(tmp_path):
    _built, goldens, quality_by_id, _ = _release(tmp_path, name="m")
    tampered = {
        cid: (
            {
                **q,
                "verification": {
                    **q["verification"],
                    "mutation_applicable": 0,
                    "mutation_status": "NOT_APPLICABLE",
                    "mutation_score": None,
                },
            }
            if q.get("verification")
            else q
        )
        for cid, q in quality_by_id.items()
    }
    by_record_id = {g.record_id: tampered[g.candidate_id] for g in goldens}
    report = validate_release(tmp_path / "m", qualities_by_id=by_record_id)
    assert report.status == "INVALID"
    assert any(e.check == "release.mutation_evidence" for e in report.errors)
    justified = {g.record_id: "auditor reason" for g in goldens}
    report2 = validate_release(
        tmp_path / "m", qualities_by_id=by_record_id, justifications=justified
    )
    assert all(e.check != "release.mutation_evidence" for e in report2.errors)


def test_validate_commercial_clearance_gate(tmp_path):
    _release(tmp_path, name="c")
    blocked = {
        "governance_status": "REVIEW_REQUIRED",
        "commercially_cleared": False,
        "clearance_reasons": ["not APPROVED"],
    }
    report = validate_release(tmp_path / "c", supply_chain=blocked)
    assert report.status == "INVALID"
    assert any(e.check == "release.commercial_clearance" for e in report.errors)
    cleared = {
        "governance_status": "APPROVED",
        "commercially_cleared": True,
        "clearance_reasons": [],
    }
    report2 = validate_release(tmp_path / "c", supply_chain=cleared)
    assert all(e.check != "release.commercial_clearance" for e in report2.errors)


def test_validate_without_audit_inputs_warns_not_fails(tmp_path):
    _release(tmp_path, name="w")
    report = validate_release(tmp_path / "w")
    assert report.status == "VALID"
    assert any(w.check == "release.quality.unchecked" for w in report.warnings)


def test_public_build_refuses_missing_governance_evidence(tmp_path):
    goldens, quality_by_id, snapshot = build_product_fixture()
    with pytest.raises(ProductIOError, match="two-reviewer package"):
        build_release(
            snapshot=snapshot,
            golden_records=goldens,
            quality_by_id=quality_by_id,
            config=ProductConfig(
                product_name="public-blocked", product_type="SAMPLE", visibility="PUBLIC"
            ),
            out_dir=tmp_path / "public-blocked",
            factory_version="0.8.0",
            provenance_version="1.0",
            quarantined_ids=set(),
        )
