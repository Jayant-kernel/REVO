"""Contamination analysis (Phase 5).

Deterministic overlap framework for train/eval separation: exact task
overlap, normalized (structural) overlap, template leakage across roles,
and a registry of known benchmark fingerprints. Hard flags block Golden
selection (configurable); soft flags route to audit. No internet
plagiarism detection — explicit and extensible only.
"""

from __future__ import annotations

import hashlib

from .config import QualityConfig
from .duplicate_detection import sql_fingerprint
from .models import ContaminationFlag, ContaminationReport, RecordQuality


def analyze_contamination(
    qualities: list[RecordQuality],
    canonical_tasks: dict[str, str],
    candidate_sql: dict[str, str],
    config: QualityConfig,
) -> tuple[dict[str, list[ContaminationFlag]], ContaminationReport]:
    """Flag records and summarize. Deterministic over sorted inputs."""
    flags: dict[str, list[ContaminationFlag]] = {q.candidate_id: [] for q in qualities}

    task_hash_to_ids: dict[str, list[str]] = {}
    for quality in qualities:
        digest = hashlib.sha256(canonical_tasks[quality.candidate_id].encode()).hexdigest()[:16]
        task_hash_to_ids.setdefault(digest, []).append(quality.candidate_id)

    norm_to_ids: dict[str, list[str]] = {}
    for quality in qualities:
        norm_to_ids.setdefault(sql_fingerprint(candidate_sql[quality.candidate_id]), []).append(
            quality.candidate_id
        )

    template_roles: dict[tuple[str, int], set[str]] = {}
    for quality in qualities:
        template_roles.setdefault((quality.template_id, quality.template_version), set()).add(
            quality.role
        )

    by_id = {q.candidate_id: q for q in qualities}
    known = set(config.known_source_hashes)
    for quality in sorted(qualities, key=lambda q: q.candidate_id):
        cid = quality.candidate_id
        # Exact task overlap with a PRIVATE_EVAL record.
        digest = hashlib.sha256(canonical_tasks[cid].encode()).hexdigest()[:16]
        others = [i for i in task_hash_to_ids[digest] if i != cid]
        private_others = [i for i in others if by_id[i].role == "PRIVATE_EVAL"]
        if private_others and quality.role != "PRIVATE_EVAL":
            flags[cid].append(
                ContaminationFlag(
                    flag_type="EXACT_OVERLAP_PRIVATE_EVAL",
                    detail=f"identical task in PRIVATE_EVAL: {sorted(private_others)[:3]}",
                    hard=config.contamination_block_exact_private_eval,
                )
            )
        elif others:
            flags[cid].append(
                ContaminationFlag(
                    flag_type="EXACT_OVERLAP",
                    detail=f"identical task shared with {len(others)} record(s)",
                    hard=False,
                )
            )
        # Normalized SQL overlap across roles.
        norm_others = [
            i
            for i in norm_to_ids[sql_fingerprint(candidate_sql[cid])]
            if i != cid and by_id[i].role != quality.role
        ]
        if norm_others:
            flags[cid].append(
                ContaminationFlag(
                    flag_type="NORMALIZED_OVERLAP",
                    detail=f"normalized SQL shared across roles: {sorted(norm_others)[:3]}",
                    hard=False,
                )
            )
        # Template leakage: same template in TRAIN and PRIVATE_EVAL.
        roles = template_roles[(quality.template_id, quality.template_version)]
        if "TRAIN" in roles and "PRIVATE_EVAL" in roles:
            flags[cid].append(
                ContaminationFlag(
                    flag_type="TEMPLATE_LEAKAGE",
                    detail=f"template {quality.template_id} v{quality.template_version} spans TRAIN/PRIVATE_EVAL",
                    hard=False,
                )
            )
        # Known-source registry hits.
        if digest in known or sql_fingerprint(candidate_sql[cid]) in known:
            flags[cid].append(
                ContaminationFlag(
                    flag_type="KNOWN_SOURCE",
                    detail="fingerprint matches the known-source registry",
                    hard=config.contamination_block_known_source,
                )
            )

    flagged = sum(1 for v in flags.values() if v)
    split_overlap = sum(
        1
        for v in flags.values()
        for f in v
        if f.flag_type in ("EXACT_OVERLAP_PRIVATE_EVAL", "TEMPLATE_LEAKAGE")
    )
    by_type: dict[str, int] = {}
    for v in flags.values():
        for flag in v:
            by_type[flag.flag_type] = by_type.get(flag.flag_type, 0) + 1
    total = max(1, len(qualities))
    return flags, ContaminationReport(
        flagged_count=flagged,
        contaminated_rate=flagged / total,
        split_overlap_count=split_overlap,
        flags_by_type=dict(sorted(by_type.items())),
    )
