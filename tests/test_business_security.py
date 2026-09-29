"""Business-layer protection tests (§40, §51, §64).

Private benchmark answers, secrets, and confidential fields must not
leak through pilot packages or evidence exports. Release references
must be well-formed release ids; anything else is rejected.
"""

import pytest

from verified_data_factory.business import (
    contains_secret_markers,
    export_business_evidence,
    export_pilot_package,
    record_customer_validation,
    scrub_payload,
)
from verified_data_factory.business.errors import BusinessConfigError


def test_pilot_package_blocks_private_answers():
    with pytest.raises(BusinessConfigError):
        export_pilot_package(
            out_dir="/nonexistent-should-fail-first",
            readme="x",
            product_files={},
            benchmark_public={"items": [{"record_id": "b-1", "expected_sql": "SELECT 1;"}]},
        )


def test_pilot_package_explicit_opt_in(tmp_path):
    written = export_pilot_package(
        out_dir=tmp_path / "pilot",
        readme="# pilot",
        product_files={"card.md": b"# card"},
        benchmark_public={"items": [{"record_id": "b-1"}]},
        include_private_answers=True,
        private_answers={"b-1": "SELECT 1;"},
    )
    assert "benchmark/answers_private.json" in written
    assert (tmp_path / "pilot" / "product" / "card.md").exists()


def test_secrets_scrubbed_on_export():
    payload = {"endpoint": "https://x", "api_key": "sk-live-123"}
    assert contains_secret_markers(payload) is True
    cleaned, count = scrub_payload(payload)
    assert count >= 1
    assert "sk-live-123" not in str(cleaned)


def test_evidence_export_redacts_feedback(tmp_path):
    record = record_customer_validation(
        validation_id="v-9",
        organization="Fixture Labs",
        segment="s",
        feedback="PRODUCT_USEFUL",
        feedback_text="confidential detail",
        willingness_signal="DATASET_TESTED",
        evidence_type="USER_REPORTED",
        evidence_reference="n/9",
    )
    written = export_business_evidence(
        out_dir=tmp_path / "biz",
        report_json='{"report_id": "r"}',
        report_markdown="# r",
        validations=[record],
    )
    assert "customer-validation/validation-000.json" in written
    exported = (tmp_path / "biz" / "customer-validation" / "validation-000.json").read_text()
    assert "confidential detail" not in exported


def test_evidence_export_rejects_benchmark_answers(tmp_path):
    with pytest.raises(BusinessConfigError):
        export_business_evidence(
            out_dir=tmp_path / "biz",
            report_json="{}",
            report_markdown="# r",
            benchmarks=[{"items": [{"expected_sql": "SELECT 1;"}]}],
        )


def test_release_reference_shape():
    from verified_data_factory.business.errors import BusinessValidationError
    from verified_data_factory.business.releases import assert_exportable, reference_release

    good = {
        "release_id": "sha256:" + "ab" * 32,
        "dataset_snapshot_id": "sha256:" + "cd" * 32,
        "product_type": "TRAIN",
        "visibility": "INTERNAL",
        "record_count": 35,
    }
    ref = reference_release(good)
    assert_exportable(ref, public=True)
    with pytest.raises(BusinessValidationError):
        reference_release({**good, "release_id": "release-1"})
    private_eval = reference_release({**good, "product_type": "PRIVATE_EVAL"})
    with pytest.raises(BusinessConfigError):
        assert_exportable(private_eval, public=True)
    assert_exportable(private_eval, public=False)
    restricted = reference_release({**good, "visibility": "RESTRICTED"})
    with pytest.raises(BusinessConfigError):
        assert_exportable(restricted, public=True)
