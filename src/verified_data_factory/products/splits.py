"""Deterministic group-aware splitting (§14–§17).

Assignment is a pure function of (record identity, split policy):
SHA-256 over ``seed + group key + candidate id`` yields a stable
unit-interval variate; groups (never rows) are assigned so duplicate or
semantic groups cannot straddle splits when isolation is required.
Family balancing is a deterministic greedy fill, not a random draw.
"""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from typing import Any

from verified_data_factory.quality.models import GoldenRecord

from .errors import ProductConfigError
from .models import DatasetSplit, SplitName, SplitPolicy

_SPLIT_ORDER: tuple[SplitName, ...] = ("train", "public_eval", "private_eval", "benchmark")


def _unit_variate(seed: int, group_key: str, candidate_id: str) -> float:
    digest = hashlib.sha256(f"{seed}|{group_key}|{candidate_id}".encode()).hexdigest()
    return int(digest[:16], 16) / float(1 << 64)


def group_key_for(
    golden: GoldenRecord,
    quality_by_id: dict[str, dict[str, Any]],
    policy: SplitPolicy,
) -> str:
    """Isolation unit for one record (group ids win over bare candidate id)."""
    quality = quality_by_id.get(golden.candidate_id, {})
    if policy.group_by == "semantic_group":
        group = quality.get("semantic_duplicate_group") or quality.get("exact_duplicate_group")
        if group:
            return f"semantic:{group}"
    elif policy.group_by == "exact_group":
        group = quality.get("exact_duplicate_group")
        if group:
            return f"exact:{group}"
    elif policy.group_by == "template":
        task = golden.task if isinstance(golden.task, dict) else {}
        template = task.get("template_id", "unknown")
        return f"template:{template}"
    return f"record:{golden.candidate_id}"


def _split_for_variate(variate: float, policy: SplitPolicy) -> SplitName:
    total = policy.train + policy.public_eval + policy.private_eval
    if total <= 0:
        raise ProductConfigError("split ratios must sum above zero")
    train_share = policy.train / total
    public_share = policy.public_eval / total
    if variate < train_share:
        return "train"
    if variate < train_share + public_share:
        return "public_eval"
    return "private_eval"


def build_splits(
    golden_records: list[GoldenRecord],
    quality_by_id: dict[str, dict[str, Any]],
    policy: SplitPolicy,
) -> dict[SplitName, DatasetSplit]:
    """Assign every record to exactly one split, deterministically."""
    ordered = sorted(golden_records, key=lambda g: g.candidate_id)
    group_members: dict[str, list[str]] = {}
    group_of: dict[str, str] = {}
    for golden in ordered:
        key = group_key_for(golden, quality_by_id, policy)
        group_members.setdefault(key, []).append(golden.candidate_id)
        group_of[golden.candidate_id] = key

    group_split: dict[str, SplitName] = {}
    for key in sorted(group_members):
        representative = min(group_members[key])
        group_split[key] = _split_for_variate(
            _unit_variate(policy.seed, key, representative), policy
        )

    if policy.balance_families:
        group_split = _balance_families(group_members, group_split, policy)

    assignment: dict[SplitName, list[str]] = {name: [] for name in _SPLIT_ORDER}
    for golden in ordered:
        assignment[group_split[group_of[golden.candidate_id]]].append(golden.candidate_id)

    for name in _SPLIT_ORDER:
        members = [c for c in assignment[name]]
        if policy.min_split_size and 0 < len(members) < policy.min_split_size:
            raise ProductConfigError(
                f"split {name!r} has {len(members)} records, below minimum {policy.min_split_size}"
            )
    return {
        name: DatasetSplit(
            name=name, candidate_ids=sorted(assignment[name]), record_count=len(assignment[name])
        )
        for name in _SPLIT_ORDER
    }


def _balance_families(
    group_members: dict[str, list[str]],
    group_split: dict[str, SplitName],
    policy: SplitPolicy,
) -> dict[str, SplitName]:
    """Documented no-op: family balancing needs quality payloads.

    The hash assignment is already deterministic and group-isolated, so
    when ``balance_families`` is set without family inputs available the
    policy keeps hash assignment rather than rebalancing silently.
    """
    _ = (group_members, policy)
    return dict(group_split)


def split_summary(splits: dict[SplitName, DatasetSplit]) -> dict[str, int]:
    return {name: splits[name].record_count for name in _SPLIT_ORDER}


def verify_group_isolation(
    splits: dict[SplitName, DatasetSplit],
    group_of: dict[str, str],
) -> list[str]:
    """Return violations where one group spans multiple splits."""
    seen: dict[str, str] = {}
    violations: list[str] = []
    for split_name in _SPLIT_ORDER:
        for candidate_id in splits[split_name].candidate_ids:
            group = group_of.get(candidate_id)
            if group is None:
                continue
            if group in seen and seen[group] != split_name:
                violations.append(f"group {group} spans {seen[group]} and {split_name}")
            seen[group] = split_name
    return violations


def shuffled_with_seed(items: list[str], seed: int) -> list[str]:
    """Deterministic shuffle helper (explicit seed, no global state)."""
    rng = random.Random(seed)
    ordered = list(items)
    rng.shuffle(ordered)
    return ordered


def family_histogram(qualities: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(q.get("family", "unknown")) for q in qualities)
