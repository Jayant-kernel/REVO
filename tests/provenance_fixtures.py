"""End-to-end provenance fixture (Phase 6, §44).

Self-contained: real Phase 1 tasks + simulated execution + real Phase 4
verification + real Phase 5 quality, then Phase 6 lineage over the top.
Covers: complete Golden record(s), excluded and inconclusive records,
audit result(s), configurations, environment snapshot, and artifacts.
No Docker, no models, no network.
"""

from __future__ import annotations

from typing import Any

from tests.quality_dataset import build_fixture_dataset
from verified_data_factory import __version__ as FACTORY_VERSION
from verified_data_factory.quality import QualityConfig, analyze_dataset, golden_record_for
from verified_data_factory.verification.models import VerificationConfig


def build_provenance_fixture() -> dict[str, Any]:
    """Build records → qualities → golden → audit in one deterministic pass."""
    records = build_fixture_dataset()
    quality_config = QualityConfig(audit_rate=1.0)
    # Baseline (no audits) to find a record that legitimately goes GOLDEN.
    baseline = analyze_dataset(records, QualityConfig(audit_rate=0.0))
    golden_ids = [q.candidate_id for q in baseline.qualities if q.decision == "GOLDEN"]
    assert golden_ids, "fixture dataset must yield at least one GOLDEN record"
    target = min(golden_ids)
    # A second sampled record that will carry an audit FAIL.
    others = sorted(
        q.candidate_id
        for q in baseline.qualities
        if q.candidate_id != target and q.verification.verdict == "PASS"
    )
    assert others, "fixture dataset needs a second PASS record for audit FAIL"
    failing = others[0]

    analysis = analyze_dataset(
        records, quality_config, audit_overrides={target: "PASS", failing: "FAIL"}
    )

    golden_qualities = [q for q in analysis.qualities if q.decision == "GOLDEN"]
    assert golden_qualities, "expected at least one GOLDEN record after audit"
    by_record = {r.candidate.candidate_id: r for r in records}
    golden_records = [golden_record_for(q, by_record[q.candidate_id]) for q in golden_qualities]

    return {
        "records": records,
        "qualities": analysis.qualities,
        "golden_records": golden_records,
        "audit_sample": analysis.audit_sample,
        "quality_config": quality_config.model_dump(mode="json"),
        "verification_config": VerificationConfig().model_dump(mode="json"),
        "factory_version": FACTORY_VERSION,
    }


def golden_record_dicts() -> list[dict[str, Any]]:
    """Golden records as plain dicts (bundle/CLI shape)."""
    fixture = build_provenance_fixture()
    return [g.model_dump(mode="json", by_alias=True) for g in fixture["golden_records"]]
