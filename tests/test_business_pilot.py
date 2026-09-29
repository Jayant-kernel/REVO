"""Pilot lifecycle and success-criteria tests (§34–§36, §58)."""

import pytest

from verified_data_factory.business import (
    SuccessCriterion,
    attach_feedback,
    create_pilot,
    evaluate_pilot,
    pilot_summary,
    transition_pilot,
)
from verified_data_factory.business.errors import BusinessConfigError


def _pilot():
    return create_pilot(
        pilot_id="p-1",
        product_release_id="sha256:rel",
        customer_segment="AI evaluation companies",
        use_case="Model evaluation datasets",
        success_criteria=[
            SuccessCriterion(
                criterion_id="c-acc",
                description="Sufficient accuracy gain",
                metric="execution_accuracy",
                threshold=0.05,
            )
        ],
    )


def test_lifecycle_transitions():
    pilot = _pilot()
    assert pilot.status == "PLANNED"
    active = transition_pilot(pilot, "ACTIVE")
    paused = transition_pilot(active, "PAUSED")
    assert paused.status == "PAUSED"
    resumed = transition_pilot(paused, "ACTIVE")
    completed = transition_pilot(resumed, "COMPLETED")
    assert completed.status == "COMPLETED"
    with pytest.raises(BusinessConfigError):
        transition_pilot(completed, "ACTIVE")
    with pytest.raises(BusinessConfigError):
        transition_pilot(pilot, "COMPLETED")


def test_criteria_evaluation():
    met = evaluate_pilot(_pilot(), {"execution_accuracy": 0.08})
    assert met.success_criteria[0].outcome == "MET"
    unmet = evaluate_pilot(_pilot(), {"execution_accuracy": 0.01})
    assert unmet.success_criteria[0].outcome == "UNMET"
    missing = evaluate_pilot(_pilot(), {})
    assert missing.success_criteria[0].outcome == "UNEVALUATED"


def test_feedback_linkage_and_summary():
    pilot = attach_feedback(_pilot(), "v-1")
    assert attach_feedback(pilot, "v-1").feedback_ids == ["v-1"]
    summary = pilot_summary(pilot)
    assert summary["pilot_id"] == "p-1"
    assert summary["criteria"][0]["outcome"] == "UNEVALUATED"
