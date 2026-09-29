"""Structured SQL use cases (§31)."""

from __future__ import annotations

from .errors import BusinessConfigError
from .models import Maturity, UseCase

DEFAULT_USE_CASES: tuple[tuple[str, str, str], ...] = (
    (
        "Text-to-SQL fine-tuning",
        "Models hallucinate SQL without verified pairs",
        "Unverified scraped pairs",
    ),
    ("SQL agent post-training", "Agents fail on multi-step analytical tasks", "Hand-written demos"),
    ("SQL benchmark evaluation", "No independent benchmark for SQL agents", "Self-graded evals"),
    ("Data-agent robustness testing", "Edge cases escape testing", "Ad-hoc spot checks"),
    (
        "Regression testing for SQL agents",
        "Model updates regress SQL behavior",
        "No regression suite",
    ),
    ("Synthetic edge-case generation", "Rare cases missing from training", "Manual authoring"),
    ("Model evaluation datasets", "Eval sets leak into training", "Public benchmarks"),
)


def default_use_cases() -> list[UseCase]:
    """The seven SQL-focused use cases, all HYPOTHESIS until validated."""
    return [
        UseCase(use_case=name, problem=problem, current_alternative=alternative)
        for name, problem, alternative in DEFAULT_USE_CASES
    ]


def validate_use_case(
    use_case: UseCase, *, status: Maturity, evidence_ids: list[str] | None = None
) -> UseCase:
    """Advance a use case's status with linked evidence."""
    if status != "HYPOTHESIS" and not (evidence_ids or use_case.evidence_ids):
        raise BusinessConfigError("advancing a use case beyond HYPOTHESIS requires evidence ids")
    return use_case.model_copy(
        update={"status": status, "evidence_ids": list(evidence_ids or use_case.evidence_ids)}
    )
