"""Chronological rules refer to timestamp values, not their text spellings."""
import pytest

from verified_data_factory.verification.business_oracles import saas_activation_payment

REQ = {"year": 2025, "funnel_steps": ["signup", "trial", "activation", "payment"]}


def row(i, status, timestamp, sequence):
    return {"record_id": i, "entity_id": 1, "group_key": "a", "status": status,
            "occurred_at": timestamp, "sequence": sequence, "amount": 7}


def test_saas_chronology_is_independent_of_iso_timestamp_separator():
    rows = [row(1, "signup", "2025-01-01T09:00:00", 1),
            row(2, "trial", "2025-01-01 10:00:00", 2),
            row(3, "activation", "2025-01-01 11:00:00", 3),
            row(4, "payment", "2025-01-01 12:00:00", 4)]
    assert saas_activation_payment(REQ, {"account_funnel": rows}).rows == [["a", 7]]


def test_duplicate_timestamp_values_are_rejected_despite_different_serialization():
    rows = [row(1, "signup", "2025-01-01 09:00:00", 1),
            row(2, "trial", "2025-01-01T09:00:00", 1)]
    with pytest.raises(ValueError, match="unique occurred_at and sequence"):
        saas_activation_payment(REQ, {"account_funnel": rows})
