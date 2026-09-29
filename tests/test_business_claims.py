"""Claim validation and maturity tests (§7, §45–§46, §64)."""

from tests.business_fixtures import FIXTURE_NOTE, baseline_outcomes, treatment_outcomes
from verified_data_factory.business import (
    BusinessClaim,
    build_comparison,
    derive_maturity,
    record_evidence,
    score_outcomes,
    validate_claims,
)


def _comparison():
    return build_comparison(
        experiment_id="exp-1",
        baseline=score_outcomes(baseline_outcomes()),
        treatment=score_outcomes(treatment_outcomes()),
    )


def _measured_evidence():
    return record_evidence(
        evidence_id="ev-m",
        evidence_type="benchmark_score",
        claim="treatment beats baseline by 25pp",
        value=0.25,
        unit="percentage-points",
        source="fixture harness",
        experiment_id="exp-1",
        status="MEASURED",
        notes=FIXTURE_NOTE,
    )


def test_supported_claim_passes_with_matching_numbers():
    claim = BusinessClaim(
        claim_id="c-1",
        statement="Treatment beats baseline by 25pp on exp-1.",
        claim_type="PERFORMANCE",
        evidence_ids=["ev-m"],
        status="MEASURED",
        metric="execution_accuracy",
        asserted_delta_pp=25.0,
    )
    verdicts = validate_claims([claim], [_measured_evidence()], [_comparison()])
    assert verdicts["c-1"][0] == "CLAIM_SUPPORTED"


def test_numeric_mismatch_rejected():
    claim = BusinessClaim(
        claim_id="c-2",
        statement="Treatment beats baseline by 12pp.",
        claim_type="PERFORMANCE",
        evidence_ids=["ev-m"],
        status="MEASURED",
        metric="execution_accuracy",
        asserted_delta_pp=12.0,
    )
    verdict, reasons = validate_claims([claim], [_measured_evidence()], [_comparison()])["c-2"]
    assert verdict == "CLAIM_UNSUPPORTED"
    assert any("12" in reason for reason in reasons)


def test_measured_status_needs_measured_evidence():
    assumed = record_evidence(
        evidence_id="ev-a",
        evidence_type="opinion",
        claim="it feels faster",
        source="guess",
        status="ASSUMED",
        notes="",
    )
    claim = BusinessClaim(
        claim_id="c-3",
        statement="It is faster.",
        claim_type="PERFORMANCE",
        evidence_ids=["ev-a"],
        status="MEASURED",
    )
    assert validate_claims([claim], [assumed], [])["c-3"][0] == "CLAIM_UNSUPPORTED"


def test_missing_evidence_detected():
    claim = BusinessClaim(
        claim_id="c-4",
        statement="Something.",
        claim_type="MARKET",
        evidence_ids=["ghost"],
        status="HYPOTHESIS",
    )
    verdict, reasons = validate_claims([claim], [], [])["c-4"]
    assert verdict == "CLAIM_UNSUPPORTED"
    assert any("ghost" in reason for reason in reasons)


def test_fixture_evidence_cannot_support_production_claims():
    fixture = record_evidence(
        evidence_id="ev-f",
        evidence_type="benchmark_score",
        claim="fixture claim",
        source="fixture",
        status="TEST_FIXTURE",
        notes=FIXTURE_NOTE,
    )
    claim = BusinessClaim(
        claim_id="c-5",
        statement="Fixture-proven.",
        claim_type="PERFORMANCE",
        evidence_ids=["ev-f"],
        status="MEASURED",
    )
    assert validate_claims([claim], [fixture], [])["c-5"][0] == "CLAIM_UNSUPPORTED"


def test_customer_validation_needs_user_reported():
    claim = BusinessClaim(
        claim_id="c-6",
        statement="Customers love it.",
        claim_type="CUSTOMER",
        evidence_ids=["ev-m"],
        status="CUSTOMER_VALIDATED",
    )
    assert validate_claims([claim], [_measured_evidence()], [])["c-6"][0] == "CLAIM_UNSUPPORTED"


def test_maturity_derivation():
    assert derive_maturity([]) == "HYPOTHESIS"
    assert derive_maturity([_measured_evidence()]) == "MEASURED"
    user = record_evidence(
        evidence_id="ev-u",
        evidence_type="interview",
        claim="useful",
        source="pilot",
        status="USER_REPORTED",
        notes="",
    )
    assert derive_maturity([_measured_evidence(), user]) == "CUSTOMER_VALIDATED"
