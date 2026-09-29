"""Customer validation, willingness ladder, and redaction tests (§32–§33, §43, §51)."""

import pytest

from verified_data_factory.business import (
    escalate_willingness,
    feedback_counts,
    purchase_signals,
    record_customer_validation,
    redact_validation,
    willingness_rank,
)
from verified_data_factory.business.errors import BusinessConfigError


def _validation(**overrides):
    fields = {
        "validation_id": "v-1",
        "organization": "Fixture Labs",
        "segment": "AI evaluation companies",
        "contact_role": "eval lead",
        "use_case": "Model evaluation datasets",
        "feedback": "PRODUCT_USEFUL",
        "feedback_text": "Worked well on our suite.",
        "willingness_signal": "DATASET_TESTED",
        "evidence_type": "USER_REPORTED",
        "evidence_reference": "notes/v-1",
    }
    fields.update(overrides)
    return record_customer_validation(**fields)


def test_interest_recorded_without_purchase():
    record = _validation(
        willingness_signal="INTEREST", purchase_signal=False, evidence_reference=""
    )
    assert record.willingness_signal == "INTEREST"
    assert record.purchase_signal is False
    assert purchase_signals([record]) == []


def test_purchase_signal_needs_reference_and_level():
    with pytest.raises(BusinessConfigError):
        _validation(willingness_signal="PAID_PURCHASE", purchase_signal=True, evidence_reference="")
    with pytest.raises(BusinessConfigError):
        _validation(willingness_signal="INTEREST", purchase_signal=True, evidence_reference="x")
    paid = _validation(
        willingness_signal="PAID_PILOT", purchase_signal=True, evidence_reference="po/123"
    )
    assert purchase_signals([paid]) == [paid]


def test_willingness_only_escalates():
    record = _validation(willingness_signal="INTEREST", evidence_reference="")
    escalated = escalate_willingness(record, "PILOT_ACCEPTED", evidence_reference="email/1")
    assert willingness_rank(escalated.willingness_signal) > willingness_rank("INTEREST")
    with pytest.raises(BusinessConfigError):
        escalate_willingness(escalated, "INTEREST")
    with pytest.raises(BusinessConfigError):
        escalate_willingness(escalated, "PILOT_ACCEPTED")


def test_redaction_drops_free_text_by_default():
    record = _validation()
    redacted = redact_validation(record)
    assert "feedback_text" not in redacted
    assert redacted["organization"] == "Fixture Labs"
    assert redact_validation(record, include_feedback_text=True)["feedback_text"]


def test_no_personal_contact_fields_exist():
    from verified_data_factory.business import CustomerValidation

    for field in ("contact_name", "contact_email", "phone"):
        assert field not in CustomerValidation.model_fields


def test_feedback_counts():
    records = [_validation(), _validation(validation_id="v-2", feedback="PRICE_CONCERN")]
    assert feedback_counts(records) == {"PRODUCT_USEFUL": 1, "PRICE_CONCERN": 1}
