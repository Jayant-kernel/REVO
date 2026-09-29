"""Difficulty analysis (Phase 5).

Two layers: declared difficulty (Phase 1 metadata, always available) and
empirical signals. Solve-rate empirics are explicitly UNAVAILABLE for
single-attempt records — never manufactured. Structural complexity
features are computed deterministically as advisory input.
"""

from __future__ import annotations

from .diversity import sql_features
from .models import DifficultyReport, RecordQuality


def complexity_features(sql: str, family: str) -> dict[str, float]:
    """Deterministic structural complexity signals (advisory, not truth)."""
    feats = sql_features(sql)
    return {
        "joins": float(feats["join_count"]),
        "nesting_depth": float(feats["nesting_depth"]),
        "subqueries": float(feats["subquery_count"]),
        "has_cte": 1.0 if feats["has_cte"] else 0.0,
        "has_window": 1.0 if feats["has_window"] else 0.0,
        "aggregations": float(feats["agg_count"]),
        "predicates": float(feats["predicate_count"]),
        "family_difficulty_prior": float(
            {
                "simple_joins": 1,
                "aggregation": 2,
                "temporal": 2,
                "deduplication": 2,
                "multi_joins": 2,
                "cte": 3,
                "subqueries": 3,
                "window_functions": 3,
                "retention": 3,
                "funnel": 4,
            }.get(family, 2)
        ),
    }


def analyze_difficulty(
    qualities: list[RecordQuality], candidate_sql: dict[str, str]
) -> tuple[DifficultyReport, dict[str, dict[str, float]]]:
    """Declared distribution + per-record complexity; empirical unavailable."""
    declared: dict[str, int] = {}
    features: dict[str, dict[str, float]] = {}
    agg: dict[str, float] = {}
    for quality in qualities:
        band = str(quality.difficulty)
        declared[band] = declared.get(band, 0) + 1
        feats = complexity_features(candidate_sql[quality.candidate_id], quality.family)
        features[quality.candidate_id] = feats
        for key, value in feats.items():
            agg[key] = agg.get(key, 0.0) + value
    count = max(1, len(qualities))
    averages = {key: value / count for key, value in sorted(agg.items())}
    return (
        DifficultyReport(
            method="DECLARED",
            declared_distribution=dict(sorted(declared.items())),
            empirical_available=False,
            empirical_reason="single attempt per record; no solve-rate data",
            complexity_features=averages,
        ),
        features,
    )
