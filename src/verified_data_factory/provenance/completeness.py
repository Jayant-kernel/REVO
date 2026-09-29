"""Provenance completeness validation (Phase 6, §30).

Every Golden record must resolve the full chain
TaskInstance → CandidateSolution → ExecutionResult → VerificationResult
→ RecordQuality → GoldenDecision → GoldenRecord → DatasetSnapshot, plus
required configuration/environment references. Missing links yield
structured MISSING_* codes — never silent acceptance.
"""

from __future__ import annotations

from typing import Any

from .models import (
    CompletenessCode,
    CompletenessIssue,
    ProvenanceCompletenessReport,
    ProvenanceNode,
)


def _payload(node: ProvenanceNode | None) -> dict[str, Any]:
    return node.payload if node is not None else {}


def validate_golden_chain(
    chain: dict[str, ProvenanceNode | None],
    has_selection_config: bool = True,
    has_environment: bool = True,
    has_artifacts: bool = True,
) -> ProvenanceCompletenessReport:
    """Validate one Golden record's lineage chain.

    ``chain`` maps role names (``task``, ``candidate``, ``execution``,
    ``verification``, ``quality``, ``selection``, ``golden``, ``snapshot``)
    to nodes (None when absent).
    """
    errors: list[CompletenessIssue] = []
    required: list[tuple[str, CompletenessCode, str]] = [
        ("task", "MISSING_TASK", "chain role 'task' has no node"),
        ("candidate", "MISSING_CANDIDATE", "chain role 'candidate' has no node"),
        ("execution", "MISSING_EXECUTION", "chain role 'execution' has no node"),
        ("verification", "MISSING_VERIFICATION", "chain role 'verification' has no node"),
        ("quality", "MISSING_QUALITY", "chain role 'quality' has no node"),
        ("selection", "MISSING_SELECTION", "chain role 'selection' has no node"),
        ("golden", "MISSING_ARTIFACT", "golden record artifact absent"),
        ("snapshot", "MISSING_ARTIFACT", "dataset snapshot artifact absent"),
    ]
    for role, code, detail in required:
        if chain.get(role) is None:
            errors.append(CompletenessIssue(code=code, detail=detail))

    quality = chain.get("quality")
    if quality is not None and _payload(quality).get("decision") != "GOLDEN":
        errors.append(
            CompletenessIssue(code="MISSING_SELECTION", detail="quality decision is not GOLDEN")
        )
    if not has_selection_config:
        errors.append(
            CompletenessIssue(code="MISSING_CONFIGURATION", detail="selection configuration absent")
        )
    if not has_environment:
        errors.append(
            CompletenessIssue(code="MISSING_ENVIRONMENT", detail="environment snapshot absent")
        )
    if not has_artifacts:
        errors.append(
            CompletenessIssue(code="MISSING_ARTIFACT", detail="referenced artifacts absent")
        )

    from .models import PROVENANCE_SCHEMA_VERSION

    return ProvenanceCompletenessReport(
        complete=not errors,
        errors=errors,
        checked_records=1 if chain.get("golden") is not None else 0,
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )
