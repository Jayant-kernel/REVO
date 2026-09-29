"""Pilot lifecycle with explicit success criteria (§34–§36, §58).

Pilots track research evidence, not customers: statuses transition
through a fixed lifecycle, success criteria carry configurable
thresholds (never universal truths), and outcomes link back to
feedback and experiment evidence.
"""

from __future__ import annotations

from typing import Any

from .errors import BusinessConfigError
from .models import CriterionOutcome, Pilot, PilotStatus, SuccessCriterion

_ALLOWED_TRANSITIONS: dict[PilotStatus, frozenset[PilotStatus]] = {
    "PLANNED": frozenset({"ACTIVE", "CANCELLED"}),
    "ACTIVE": frozenset({"COMPLETED", "PAUSED", "CANCELLED"}),
    "PAUSED": frozenset({"ACTIVE", "CANCELLED"}),
    "COMPLETED": frozenset(),
    "CANCELLED": frozenset(),
}


def create_pilot(
    *,
    pilot_id: str,
    product_release_id: str,
    customer_segment: str,
    use_case: str = "",
    success_criteria: list[SuccessCriterion] | None = None,
    start_date: str | None = None,
) -> Pilot:
    """Create a PLANNED pilot; success criteria required to ever complete."""
    return Pilot(
        pilot_id=pilot_id,
        product_release_id=product_release_id,
        customer_segment=customer_segment,
        use_case=use_case,
        success_criteria=list(success_criteria or []),
        start_date=start_date,
    )


def transition_pilot(
    pilot: Pilot, new_status: PilotStatus, *, end_date: str | None = None
) -> Pilot:
    """Move a pilot through the lifecycle; terminal states are final."""
    if new_status not in _ALLOWED_TRANSITIONS[pilot.status]:
        raise BusinessConfigError(f"illegal pilot transition {pilot.status} -> {new_status}")
    update: dict[str, Any] = {"status": new_status}
    if end_date is not None:
        update["end_date"] = end_date
    return pilot.model_copy(update=update)


def evaluate_criterion(criterion: SuccessCriterion, observed: float | None) -> SuccessCriterion:
    """Judge one criterion against an observed metric value (§35)."""
    if observed is None:
        return criterion.model_copy(update={"outcome": "UNEVALUATED"})
    met = (
        observed >= criterion.threshold
        if criterion.comparison == "gte"
        else observed <= criterion.threshold
    )
    outcome: CriterionOutcome = "MET" if met else "UNMET"
    return criterion.model_copy(update={"outcome": outcome})


def evaluate_pilot(pilot: Pilot, observed_metrics: dict[str, float | None]) -> Pilot:
    """Evaluate every success criterion; UNEVALUATED stays visible (§35)."""
    evaluated = [
        evaluate_criterion(criterion, observed_metrics.get(criterion.metric))
        for criterion in pilot.success_criteria
    ]
    return pilot.model_copy(update={"success_criteria": evaluated})


def pilot_summary(pilot: Pilot) -> dict[str, Any]:
    """Status + criterion outcomes; concrete, never vague (§36)."""
    return {
        "pilot_id": pilot.pilot_id,
        "status": pilot.status,
        "criteria": [
            {"criterion_id": c.criterion_id, "metric": c.metric, "outcome": c.outcome}
            for c in pilot.success_criteria
        ],
        "results": dict(pilot.results),
        "feedback_ids": list(pilot.feedback_ids),
    }


def attach_feedback(pilot: Pilot, feedback_id: str) -> Pilot:
    """Link a feedback/validation id to a pilot (§58)."""
    if feedback_id in pilot.feedback_ids:
        return pilot
    return pilot.model_copy(update={"feedback_ids": [*pilot.feedback_ids, feedback_id]})
