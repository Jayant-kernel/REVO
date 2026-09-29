"""Visibility enforcement tests (Phase 7, §40).

The policy is enforced by code: PUBLIC releases reject restricted
records with explicit reasons instead of trusting the operator.
"""

from tests.product_fixtures import build_product_fixture
from verified_data_factory.products import check_record_dict_visible, select_visible_records


def test_public_rejects_private_eval_and_hard_contamination():
    goldens, quality_by_id, _ = _fixture_setup()
    allowed, rejected = select_visible_records(goldens, quality_by_id, "PUBLIC")
    rejected_ids = {candidate_id for candidate_id, _ in rejected}
    assert "cand-010" in rejected_ids  # PRIVATE_EVAL role
    assert "cand-011" in rejected_ids  # hard contamination flag
    assert "cand-010" not in {g.candidate_id for g in allowed}
    assert "cand-011" not in {g.candidate_id for g in allowed}
    for _, reasons in rejected:
        assert reasons  # every rejection carries explicit reasons


def test_internal_allows_everything():
    goldens, quality_by_id, _ = _fixture_setup()
    allowed, rejected = select_visible_records(goldens, quality_by_id, "INTERNAL")
    assert rejected == []
    assert len(allowed) == len(goldens)


def test_restricted_allows_everything():
    goldens, quality_by_id, _ = _fixture_setup()
    allowed, rejected = select_visible_records(goldens, quality_by_id, "RESTRICTED")
    assert rejected == []
    assert len(allowed) == len(goldens)


def test_soft_flags_do_not_block_public():
    assert check_record_dict_visible({"role": "TRAIN", "contamination_flags": []}, "PUBLIC") == []


def test_public_eval_role_rejected_in_public():
    reasons = check_record_dict_visible(
        {"role": "PRIVATE_EVAL", "contamination_flags": []}, "PUBLIC"
    )
    assert any("PRIVATE_EVAL" in reason for reason in reasons)


def _fixture_setup():
    return build_product_fixture()
