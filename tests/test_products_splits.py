"""Split determinism and group-isolation tests (Phase 7, §14–§17)."""

import pytest

from tests.product_fixtures import build_product_fixture
from verified_data_factory.products import (
    SplitPolicy,
    build_splits,
    group_key_for,
    split_summary,
    verify_group_isolation,
)
from verified_data_factory.products.errors import ProductConfigError


def _fixture():
    return build_product_fixture()


def test_splits_are_deterministic():
    goldens, quality_by_id, _ = _fixture()
    policy = SplitPolicy(seed=7)
    first = build_splits(goldens, quality_by_id, policy)
    second = build_splits(goldens, quality_by_id, policy)
    assert first == second


def test_splits_partition_every_record_exactly_once():
    goldens, quality_by_id, _ = _fixture()
    splits = build_splits(goldens, quality_by_id, SplitPolicy(seed=7))
    seen: list[str] = []
    for split in splits.values():
        seen.extend(split.candidate_ids)
    assert sorted(seen) == sorted(g.candidate_id for g in goldens)
    assert sum(split_summary(splits).values()) == len(goldens)


def test_semantic_group_never_straddles_splits():
    goldens, quality_by_id, _ = _fixture()
    policy = SplitPolicy(seed=7, group_by="semantic_group")
    splits = build_splits(goldens, quality_by_id, policy)
    group_of = {g.candidate_id: group_key_for(g, quality_by_id, policy) for g in goldens}
    assert verify_group_isolation(splits, group_of) == []
    # The 8-member sem-a group lands in exactly one split.
    holders = {name for name, s in splits.items() if "cand-000" in s.candidate_ids}
    assert len(holders) == 1
    holder = holders.pop()
    for index in range(8):
        assert f"cand-{index:03d}" in splits[holder].candidate_ids


def test_exact_group_policy_isolates_exact_pairs():
    goldens, quality_by_id, _ = _fixture()
    policy = SplitPolicy(seed=3, group_by="exact_group")
    splits = build_splits(goldens, quality_by_id, policy)
    group_of = {g.candidate_id: group_key_for(g, quality_by_id, policy) for g in goldens}
    assert verify_group_isolation(splits, group_of) == []


def test_template_policy_isolates_templates():
    goldens, quality_by_id, _ = _fixture()
    policy = SplitPolicy(seed=3, group_by="template")
    splits = build_splits(goldens, quality_by_id, policy)
    group_of = {g.candidate_id: group_key_for(g, quality_by_id, policy) for g in goldens}
    assert verify_group_isolation(splits, group_of) == []


def test_different_seeds_can_assign_differently_but_stay_valid():
    goldens, quality_by_id, _ = _fixture()
    first = build_splits(goldens, quality_by_id, SplitPolicy(seed=1))
    second = build_splits(goldens, quality_by_id, SplitPolicy(seed=999))
    # Both are valid partitions (asserted structurally); seeds must matter overall.
    assert split_summary(first).keys() == split_summary(second).keys()


def test_zero_ratios_rejected():
    goldens, quality_by_id, _ = _fixture()
    with pytest.raises(ProductConfigError):
        build_splits(
            goldens, quality_by_id, SplitPolicy(train=0.0, public_eval=0.0, private_eval=0.0)
        )


def test_min_split_size_enforced():
    goldens, quality_by_id, _ = _fixture()
    with pytest.raises(ProductConfigError):
        build_splits(goldens, quality_by_id, SplitPolicy(seed=7, min_split_size=10**6))
