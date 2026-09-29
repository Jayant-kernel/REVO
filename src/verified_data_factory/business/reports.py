"""Business validation report assembly (§47–§48, §59, §68, §73).

Sections stay separate — product, model value, customer, economics,
GTM, maturity — and evidence is partitioned into WHAT WE KNOW /
MEASURED / CUSTOMER-SAID / ASSUMED / UNKNOWN. Machine-readable
``report.json`` plus optional ``report.csv`` power any future UI.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from verified_data_factory.provenance import content_id, utc_now_iso

from .claims import maturity_counts
from .customer import feedback_counts
from .evidence import partition_evidence
from .models import (
    BUSINESS_SCHEMA_VERSION,
    BusinessClaim,
    BusinessEvidence,
    BusinessValidationReport,
    CustomerValidation,
    ExperimentComparison,
    ExperimentResult,
    HypothesisVerdict,
    RoadmapEvidence,
    UnitEconomics,
)


def _lines(items: list[BusinessEvidence]) -> list[str]:
    return [f"[{item.status}] {item.evidence_type}: {item.claim}" for item in items]


def build_business_report(
    *,
    report_id: str,
    release_manifests: list[dict[str, Any]] | None = None,
    comparisons: list[ExperimentComparison] | None = None,
    results: list[ExperimentResult] | None = None,
    validations: list[CustomerValidation] | None = None,
    evidence: list[BusinessEvidence] | None = None,
    claims: list[BusinessClaim] | None = None,
    economics: UnitEconomics | None = None,
    funnel_counts: dict[str, int] | None = None,
    segments: list[dict[str, Any]] | None = None,
    use_cases: list[dict[str, Any]] | None = None,
    hypothesis_verdict: HypothesisVerdict = "INSUFFICIENT_EVIDENCE",
    hypothesis_detail: str = "",
) -> BusinessValidationReport:
    """Assemble the auditable business validation report (§47)."""
    manifests = release_manifests or []
    comparisons = comparisons or []
    evidence = evidence or []
    claims = claims or []
    validations = validations or []
    buckets = partition_evidence(evidence)
    product = {
        "released_products": len(manifests),
        "release_versions": sorted({m.get("release_id", "") for m in manifests}),
        "record_counts": {m.get("release_id", ""): m.get("record_count") for m in manifests},
        "families": sorted(
            {f for m in manifests for f in (m.get("families") or []) if isinstance(m, dict)}
        ),
        "formats": sorted({m.get("output_format", "") for m in manifests}),
    }
    model_value = {
        "experiments": len(results or []),
        "comparisons": len(comparisons),
        "metrics": [c.model_dump(mode="json") for c in comparisons],
    }
    customer = {
        "validations": len(validations),
        "feedback_themes": feedback_counts(validations),
        "purchase_signals": sum(1 for v in validations if v.purchase_signal),
    }
    economics_section: dict[str, Any] = (
        economics.model_dump(mode="json") if economics else {"status": "UNKNOWN"}
    )
    gtm = {
        "segments": segments or [],
        "use_cases": use_cases or [],
        "pipeline_counts": funnel_counts or {},
    }
    maturity = {
        "hypotheses": sum(1 for c in claims if c.status == "HYPOTHESIS"),
        "measured_claims": maturity_counts(claims).get("MEASURED", 0),
        "replicated_claims": maturity_counts(claims).get("REPLICATED", 0),
        "customer_validated_claims": maturity_counts(claims).get("CUSTOMER_VALIDATED", 0),
        "claim_counts": maturity_counts(claims),
    }
    return BusinessValidationReport(
        report_id=report_id,
        created_at=utc_now_iso(),
        product=product,
        model_value=model_value,
        customer=customer,
        economics=economics_section,
        gtm=gtm,
        maturity=maturity,
        known=_lines(buckets["known"]),
        measured=_lines(buckets["measured"]),
        customer_said=_lines(buckets["customer_said"]),
        assumed=_lines(buckets["assumed"]),
        unknown=_lines(buckets["unknown"]),
        hypothesis_verdict=hypothesis_verdict,
        hypothesis_detail=hypothesis_detail,
    )


def report_to_json(report: BusinessValidationReport) -> str:
    """Canonical JSON for ``business_report.json`` (§48)."""
    return json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def report_to_csv(report: BusinessValidationReport) -> str:
    """Flat section/key/value CSV for ``business_report.csv`` (§48)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["section", "key", "value"])
    for section in ("product", "model_value", "customer", "economics", "gtm", "maturity"):
        payload = getattr(report, section)
        for key in sorted(payload):
            writer.writerow([section, key, json.dumps(payload[key], sort_keys=True, default=str)])
    for bucket in ("known", "measured", "customer_said", "assumed", "unknown"):
        for line in getattr(report, bucket):
            writer.writerow([bucket, "evidence", line])
    writer.writerow(["verdict", "hypothesis_verdict", report.hypothesis_verdict])
    return buffer.getvalue()


def report_content_id(report: BusinessValidationReport) -> str:
    """Content identity excluding timestamps (determinism check, §75)."""
    payload = report.model_dump(mode="json")
    payload.pop("created_at", None)
    payload.pop("report_id", None)
    return content_id("BUSINESS_REPORT", BUSINESS_SCHEMA_VERSION, payload)


def build_roadmap_evidence(
    *,
    evidence: list[BusinessEvidence] | None = None,
    validations: list[CustomerValidation] | None = None,
    experiment_gaps: list[str] | None = None,
) -> RoadmapEvidence:
    """Structured roadmap inputs for human decisions (§59)."""
    evidence = evidence or []
    validations = validations or []
    return RoadmapEvidence(
        validated_needs=[
            item.claim for item in evidence if item.status in ("MEASURED", "USER_REPORTED")
        ],
        unvalidated_assumptions=[item.claim for item in evidence if item.status == "ASSUMED"],
        technical_gaps=list(experiment_gaps or []),
        product_gaps=[],
        customer_requests=[feature for v in validations for feature in v.requested_features],
        experiment_gaps=list(experiment_gaps or []),
    )
