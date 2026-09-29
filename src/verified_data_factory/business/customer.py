"""Customer validation records with honesty guardrails (§32–§33, §43).

Willingness signals are observed actions on a fixed ladder — interest
never auto-escalates to purchase. Purchase-level signals require an
explicit evidence reference. No personal names or contact details are
stored by design; exports support redaction of free-text feedback.
"""

from __future__ import annotations

from typing import Any

from .errors import BusinessConfigError, BusinessValidationError
from .models import (
    PURCHASE_LEVEL_SIGNALS,
    WILLINGNESS_ORDER,
    CustomerValidation,
    WillingnessSignal,
)


def record_customer_validation(**fields: object) -> CustomerValidation:
    """Record one interaction; purchase signals need evidence (§43)."""
    try:
        record = CustomerValidation.model_validate(fields)
    except Exception as exc:
        raise BusinessConfigError(f"invalid customer validation: {exc}") from exc
    signal = record.willingness_signal
    if signal in PURCHASE_LEVEL_SIGNALS and not record.evidence_reference:
        raise BusinessConfigError(f"willingness signal {signal} requires an evidence_reference")
    if record.purchase_signal and signal not in PURCHASE_LEVEL_SIGNALS:
        raise BusinessConfigError(
            "purchase_signal=true requires a purchase-level willingness signal"
        )
    return record


def willingness_rank(signal: WillingnessSignal | None) -> int:
    """Ladder position (-1 for no signal); for ordering, never scoring."""
    if signal is None:
        return -1
    return WILLINGNESS_ORDER.index(signal)


def escalate_willingness(
    record: CustomerValidation, new_signal: WillingnessSignal, *, evidence_reference: str = ""
) -> CustomerValidation:
    """Move a signal only upward with explicit new observation (§43)."""
    if willingness_rank(new_signal) <= willingness_rank(record.willingness_signal):
        raise BusinessConfigError("willingness signals only move upward on new observation")
    update: dict[str, Any] = {"willingness_signal": new_signal}
    if evidence_reference:
        update["evidence_reference"] = evidence_reference
    try:
        return record.model_copy(update=update)
    except Exception as exc:
        raise BusinessConfigError(f"cannot escalate willingness: {exc}") from exc


def redact_validation(
    record: CustomerValidation, *, include_feedback_text: bool = False
) -> dict[str, Any]:
    """Export-safe view: free text and confidential fields dropped by default (§51)."""
    payload = record.model_dump(mode="json")
    if not include_feedback_text:
        payload.pop("feedback_text", None)
    return payload


def validations_from_list(data: list[Any]) -> list[CustomerValidation]:
    try:
        return [CustomerValidation.model_validate(row) for row in data]
    except Exception as exc:
        raise BusinessValidationError(f"invalid customer validations: {exc}") from exc


def feedback_counts(records: list[CustomerValidation]) -> dict[str, int]:
    """Feedback-class histogram; observations about feedback, not scores."""
    counts: dict[str, int] = {}
    for record in records:
        counts[record.feedback] = counts.get(record.feedback, 0) + 1
    return counts


def purchase_signals(records: list[CustomerValidation]) -> list[CustomerValidation]:
    """Only records with an explicit purchase-level signal and reference."""
    return [
        record
        for record in records
        if record.willingness_signal in PURCHASE_LEVEL_SIGNALS and record.evidence_reference
    ]


def feedback_class_values() -> tuple[str, ...]:
    """The ten feedback classes (§33)."""
    return (
        "PROBLEM_CONFIRMED",
        "PROBLEM_NOT_CONFIRMED",
        "PRODUCT_USEFUL",
        "PRODUCT_NOT_USEFUL",
        "QUALITY_CONCERN",
        "PRICE_CONCERN",
        "INTEGRATION_CONCERN",
        "FORMAT_CONCERN",
        "COMPLIANCE_CONCERN",
        "NO_DECISION",
    )
