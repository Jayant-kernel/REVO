"""Customer segments as hypotheses with validation states (§30).

Segments are explicitly hypotheses until evidence says otherwise. No
ranking is produced unless the caller supplies decision criteria —
and then the ranking records the criteria used.
"""

from __future__ import annotations

from .errors import BusinessConfigError
from .models import CustomerSegment, Maturity

DEFAULT_SEGMENTS: tuple[tuple[str, str, str], ...] = (
    ("AI coding-agent startups", "Need reliable SQL training/eval data", "Text-to-SQL fine-tuning"),
    (
        "Text-to-SQL model teams",
        "Need verified benchmarks and training pairs",
        "SQL benchmark evaluation",
    ),
    (
        "Enterprise AI teams",
        "Need robust data agents with audit trails",
        "Data-agent robustness testing",
    ),
    ("AI evaluation companies", "Need independent eval datasets", "Model evaluation datasets"),
    (
        "Synthetic-data companies",
        "Need verified seed/edge-case data",
        "Synthetic edge-case generation",
    ),
    (
        "Developer-tool companies",
        "Need regression coverage for SQL features",
        "Regression testing for SQL agents",
    ),
    ("Data-platform companies", "Need agent post-training data", "SQL agent post-training"),
)


def default_segments() -> list[CustomerSegment]:
    """The seven hypothesized segments, all HYPOTHESIS until validated."""
    return [
        CustomerSegment(segment=name, problem=problem, use_case=use_case)
        for name, problem, use_case in DEFAULT_SEGMENTS
    ]


def validate_segment(
    segment: CustomerSegment, *, status: Maturity, evidence_ids: list[str] | None = None
) -> CustomerSegment:
    """Advance a segment's validation state with linked evidence."""
    if status != "HYPOTHESIS" and not (evidence_ids or segment.evidence_ids):
        raise BusinessConfigError("advancing a segment beyond HYPOTHESIS requires evidence ids")
    return segment.model_copy(
        update={
            "validation_status": status,
            "evidence_ids": list(evidence_ids or segment.evidence_ids),
        }
    )


def rank_segments(segments: list[CustomerSegment], *, criteria: str) -> list[CustomerSegment]:
    """Rank only with explicit, recorded decision criteria (§30)."""
    if not criteria:
        raise BusinessConfigError("ranking segments requires explicit decision criteria")
    return sorted(segments, key=lambda s: (s.validation_status, s.segment))
