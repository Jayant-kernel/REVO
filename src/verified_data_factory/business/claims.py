"""Claim/evidence validation and maturity (§45–§46).

A document number is just text until it matches measured evidence:
numerical claims must agree with experiment comparisons within
tolerance, MEASURED status needs MEASURED evidence, and anything
without support is CLAIM_UNSUPPORTED. Maturity is derived, never
declared.
"""

from __future__ import annotations

from .errors import BusinessConfigError
from .models import (
    BusinessClaim,
    BusinessEvidence,
    ClaimVerdict,
    ExperimentComparison,
    Maturity,
)

NUMERIC_TOLERANCE_PP = 0.05


def validate_claim(
    claim: BusinessClaim,
    evidence_by_id: dict[str, BusinessEvidence],
    comparisons_by_experiment: dict[str, ExperimentComparison] | None = None,
) -> tuple[ClaimVerdict, list[str]]:
    """Check one claim; returns (verdict, reasons). Never raises on content."""
    comparisons = comparisons_by_experiment or {}
    reasons: list[str] = []
    missing = [eid for eid in claim.evidence_ids if eid not in evidence_by_id]
    if missing:
        return "CLAIM_UNSUPPORTED", [f"missing evidence: {sorted(missing)}"]
    linked = [evidence_by_id[eid] for eid in claim.evidence_ids]
    if any(ev.status == "TEST_FIXTURE" for ev in linked):
        return "CLAIM_UNSUPPORTED", ["fixture evidence cannot support production claims"]
    if claim.status in ("MEASURED", "REPLICATED", "CUSTOMER_VALIDATED", "COMMERCIALIZED"):
        measured = [ev for ev in linked if ev.status == "MEASURED"]
        if not measured:
            return "CLAIM_UNSUPPORTED", ["MEASURED status needs MEASURED evidence"]
    if claim.status in ("CUSTOMER_VALIDATED", "COMMERCIALIZED"):
        customer = [ev for ev in linked if ev.status == "USER_REPORTED"]
        if not customer:
            return "CLAIM_UNSUPPORTED", ["customer validation needs USER_REPORTED evidence"]
    numeric_problems = _check_numerics(claim, linked, comparisons)
    reasons.extend(numeric_problems)
    if reasons:
        return "CLAIM_UNSUPPORTED", reasons
    if not linked:
        return "CLAIM_UNSUPPORTED", ["claim has no linked evidence"]
    return "CLAIM_SUPPORTED", [f"supported by {len(linked)} evidence record(s)"]


def _check_numerics(
    claim: BusinessClaim,
    linked: list[BusinessEvidence],
    comparisons: dict[str, ExperimentComparison],
) -> list[str]:
    problems: list[str] = []
    experiment_ids = {ev.experiment_id for ev in linked if ev.experiment_id}
    for experiment_id in sorted(experiment_ids):
        comparison = comparisons.get(experiment_id)
        if comparison is None:
            problems.append(f"no comparison available for experiment {experiment_id}")
            continue
        if claim.metric:
            row = next((m for m in comparison.metrics if m["metric"] == claim.metric), None)
            if row is None:
                problems.append(f"metric {claim.metric} not in experiment {experiment_id}")
                continue
            if (
                claim.asserted_delta_pp is not None
                and abs(row["absolute_pp"] - claim.asserted_delta_pp) > NUMERIC_TOLERANCE_PP
            ):
                problems.append(
                    f"asserted delta {claim.asserted_delta_pp}pp != "
                    f"measured {row['absolute_pp']:.2f}pp in {experiment_id}"
                )
            if (
                claim.asserted_baseline is not None
                and abs(row["baseline"] - claim.asserted_baseline) > NUMERIC_TOLERANCE_PP / 100.0
            ):
                problems.append(f"asserted baseline != measured baseline in {experiment_id}")
            if (
                claim.asserted_treatment is not None
                and abs(row["treatment"] - claim.asserted_treatment) > NUMERIC_TOLERANCE_PP / 100.0
            ):
                problems.append(f"asserted treatment != measured treatment in {experiment_id}")
    return problems


def validate_claims(
    claims: list[BusinessClaim],
    evidence: list[BusinessEvidence],
    comparisons: list[ExperimentComparison] | None = None,
) -> dict[str, tuple[ClaimVerdict, list[str]]]:
    """Validate many claims; every claim gets a verdict (§45)."""
    evidence_by_id = {ev.evidence_id: ev for ev in evidence}
    comparisons_by_experiment = {c.experiment_id: c for c in comparisons or []}
    return {
        claim.claim_id: validate_claim(claim, evidence_by_id, comparisons_by_experiment)
        for claim in claims
    }


def derive_maturity(linked: list[BusinessEvidence]) -> Maturity:
    """Highest maturity the linked evidence actually supports (§46)."""
    statuses = {ev.status for ev in linked}
    if "TEST_FIXTURE" in statuses and len(statuses) == 1:
        return "HYPOTHESIS"
    if not linked:
        return "HYPOTHESIS"
    if any(ev.status == "ASSUMED" for ev in linked) and len(linked) == 1:
        return "HYPOTHESIS"
    if "MEASURED" in statuses and "USER_REPORTED" in statuses:
        return "CUSTOMER_VALIDATED"
    if "MEASURED" in statuses:
        return "MEASURED"
    if "USER_REPORTED" in statuses or "OBSERVED" in statuses:
        return "OBSERVED"
    return "HYPOTHESIS"


def maturity_counts(claims: list[BusinessClaim]) -> dict[str, int]:
    """Claim counts per maturity state for the report (§73)."""
    counts: dict[str, int] = {}
    for claim in claims:
        counts[claim.status] = counts.get(claim.status, 0) + 1
    return counts


def check_claim_shape(claim: BusinessClaim) -> None:
    """Structural guardrails: marketing language has no field here."""
    if not claim.statement.strip():
        raise BusinessConfigError("claim statement must be non-empty")
    if claim.status != "HYPOTHESIS" and not claim.evidence_ids:
        raise BusinessConfigError("non-hypothesis claims need evidence ids")
