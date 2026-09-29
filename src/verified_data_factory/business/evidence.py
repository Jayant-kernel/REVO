"""Evidence recording and classification (Phase 8, §6, §53).

Statuses are load-bearing: ASSUMED evidence can never support a
MEASURED claim, and TEST_FIXTURE data is quarantined from production
evidence by construction.
"""

from __future__ import annotations

from .errors import BusinessConfigError
from .models import BusinessEvidence, EvidenceStatus

# Statuses that count as empirical observations (not assumptions).
EMPIRICAL_STATUSES: frozenset[EvidenceStatus] = frozenset({"OBSERVED", "MEASURED", "USER_REPORTED"})


def record_evidence(**fields: object) -> BusinessEvidence:
    """Create one evidence record; TEST_FIXTURE must say so in notes."""
    try:
        evidence = BusinessEvidence.model_validate(fields)
    except Exception as exc:
        raise BusinessConfigError(f"invalid evidence record: {exc}") from exc
    if evidence.status == "TEST_FIXTURE" and "TEST_FIXTURE" not in evidence.notes:
        raise BusinessConfigError("TEST_FIXTURE evidence must declare so in notes")
    return evidence


def is_empirical(evidence: BusinessEvidence) -> bool:
    """True when the status represents an observation, not an assumption."""
    return evidence.status in EMPIRICAL_STATUSES


def partition_evidence(evidence: list[BusinessEvidence]) -> dict[str, list[BusinessEvidence]]:
    """Split evidence into the five reporting buckets (§53, §68)."""
    buckets: dict[str, list[BusinessEvidence]] = {
        "known": [],
        "measured": [],
        "customer_said": [],
        "assumed": [],
        "unknown": [],
    }
    for item in evidence:
        if item.status == "MEASURED":
            buckets["measured"].append(item)
        elif item.status == "USER_REPORTED":
            buckets["customer_said"].append(item)
        elif item.status == "ASSUMED":
            buckets["assumed"].append(item)
        elif item.status == "UNKNOWN":
            buckets["unknown"].append(item)
        elif item.status == "TEST_FIXTURE":
            continue  # quarantined: never production evidence
        else:
            buckets["known"].append(item)
    return buckets


def evidence_summary(evidence: list[BusinessEvidence]) -> dict[str, int]:
    """Counts per status, including quarantined fixtures (labeled as such)."""
    summary: dict[str, int] = {}
    for item in evidence:
        summary[item.status] = summary.get(item.status, 0) + 1
    return summary
