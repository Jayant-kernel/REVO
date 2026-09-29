"""Diversity analysis (Phase 5).

Distributions with counts, percentages, and entropy — never a single
arbitrary diversity score. SQL structure comes from deterministic
token scans (shared with duplicate detection's operator signature).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .duplicate_detection import _operator_signature, schema_fingerprint
from .models import DiversityReport, FamilyDistribution, RecordQuality


def _distribution(values: list[str]) -> tuple[dict[str, int], dict[str, float], float]:
    counts = dict(sorted(Counter(values).items()))
    total = sum(counts.values())
    percentages = {k: (v / total if total else 0.0) for k, v in counts.items()}
    entropy = -sum(p * math.log2(p) for p in percentages.values() if p > 0)
    return counts, percentages, entropy


def sql_features(sql: str) -> dict[str, Any]:
    """Deterministic structural features of one candidate query."""
    upper = sql.upper()
    depth, max_depth = 0, 0
    in_string: str | None = None
    i = 0
    while i < len(sql):
        ch = sql[i]
        if in_string:
            if ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"'):
            in_string = ch
        elif ch == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch == ")":
            depth = max(0, depth - 1)
        i += 1
    selects = len(re.findall(r"\bSELECT\b", upper))
    return {
        "join_count": len(re.findall(r"\bJOIN\b", upper)),
        "select_count": selects,
        "subquery_count": max(0, selects - 1),
        "has_cte": bool(re.search(r"\bWITH\b", upper)),
        "has_window": bool(
            re.search(r"\bOVER\b|\bRANK\s*\(|\bROW_NUMBER\s*\(|\bLAG\s*\(|\bLEAD\s*\(", upper)
        ),
        "agg_count": len(re.findall(r"\b(SUM|AVG|COUNT|MIN|MAX)\s*\(", upper)),
        "predicate_count": len(re.findall(r"\b(WHERE|AND|OR|HAVING)\b", upper)),
        "nesting_depth": max_depth,
        "has_case": bool(re.search(r"\bCASE\b", upper)),
        "has_exists": bool(re.search(r"\bEXISTS\b", upper)),
        "operators": sorted(_operator_signature(sql)),
    }


def compute_diversity(
    qualities: list[RecordQuality],
    candidate_sql: dict[str, str],
    schemas: dict[str, list[dict[str, Any]]],
) -> tuple[DiversityReport, dict[str, dict[str, Any]]]:
    """Distributions plus per-record diversity features (returned for storage)."""
    counts, percentages, entropy = _distribution([q.family for q in qualities])
    constructs: Counter[str] = Counter()
    operators: Counter[str] = Counter()
    schema_fps: Counter[str] = Counter()
    edges: Counter[str] = Counter()
    features: dict[str, dict[str, Any]] = {}
    for quality in qualities:
        sql = candidate_sql[quality.candidate_id]
        feats = sql_features(sql)
        features[quality.candidate_id] = feats
        for operator in feats["operators"]:
            operators[operator] += 1
            constructs[operator] += 1
        schema_fps[schema_fingerprint(schemas[quality.candidate_id])] += 1
        for edge in quality.task_quality.edge_cases_present:
            edges[edge] += 1
    report = DiversityReport(
        family=FamilyDistribution(counts=counts, percentages=percentages, entropy=entropy),
        sql_constructs=dict(sorted(constructs.items())),
        schema_fingerprints=dict(sorted(schema_fps.items())),
        edge_cases=dict(sorted(edges.items())),
        operator_categories=dict(sorted(operators.items())),
    )
    return report, features
