"""Evidence classification tests (Phase 8, §6)."""

import pytest

from tests.business_fixtures import FIXTURE_NOTE
from verified_data_factory.business import (
    evidence_summary,
    is_empirical,
    partition_evidence,
    record_evidence,
)
from verified_data_factory.business.errors import BusinessConfigError


def _evidence(status, evidence_id="e-1"):
    return record_evidence(
        evidence_id=evidence_id,
        evidence_type="benchmark_score",
        claim="treatment beats baseline",
        value=0.83,
        unit="accuracy",
        source="fixture harness",
        status=status,
        notes=FIXTURE_NOTE if status == "TEST_FIXTURE" else "",
    )


def test_all_statuses_recorded():
    for status in ("OBSERVED", "MEASURED", "USER_REPORTED", "ASSUMED", "UNKNOWN"):
        assert _evidence(status).status == status


def test_assumed_is_not_empirical():
    assert not is_empirical(_evidence("ASSUMED"))
    assert not is_empirical(_evidence("UNKNOWN"))
    assert is_empirical(_evidence("MEASURED"))
    assert is_empirical(_evidence("OBSERVED"))
    assert is_empirical(_evidence("USER_REPORTED"))


def test_fixture_must_declare_itself():
    with pytest.raises(BusinessConfigError):
        record_evidence(
            evidence_id="x",
            evidence_type="t",
            claim="c",
            source="s",
            status="TEST_FIXTURE",
            notes="no declaration",
        )


def test_fixture_quarantined_from_partitions():
    items = [_evidence("MEASURED", "m"), _evidence("TEST_FIXTURE", "f")]
    buckets = partition_evidence(items)
    assert buckets["measured"] == [items[0]]
    assert all(items[1] not in bucket for bucket in buckets.values())
    assert evidence_summary(items)["TEST_FIXTURE"] == 1


def test_partition_buckets():
    items = [
        _evidence("OBSERVED", "o"),
        _evidence("MEASURED", "m"),
        _evidence("USER_REPORTED", "u"),
        _evidence("ASSUMED", "a"),
        _evidence("UNKNOWN", "n"),
    ]
    buckets = partition_evidence(items)
    assert [i.evidence_id for i in buckets["known"]] == ["o"]
    assert [i.evidence_id for i in buckets["measured"]] == ["m"]
    assert [i.evidence_id for i in buckets["customer_said"]] == ["u"]
    assert [i.evidence_id for i in buckets["assumed"]] == ["a"]
    assert [i.evidence_id for i in buckets["unknown"]] == ["n"]
