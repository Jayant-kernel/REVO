"""Benchmark scoring by aggregation (Phase 8, §16–§17).

Phase 8 never judges correctness: ``PredictionOutcome`` records carry
per-item outcomes produced by the experiment owner's harness (ideally
Phase 3/4 infrastructure or equivalent). This module aggregates those
outcomes into primary and secondary metrics with explicit denominators.
"""

from __future__ import annotations

from collections import Counter
from statistics import mean

from .errors import BusinessConfigError
from .models import BenchmarkScores, PredictionOutcome


def _rate(hits: int, total: int) -> float:
    return hits / total if total else 0.0


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def score_outcomes(outcomes: list[PredictionOutcome]) -> BenchmarkScores:
    """Aggregate externally evaluated outcomes into benchmark scores."""
    if not outcomes:
        raise BusinessConfigError("cannot score an empty outcome set")
    correct = sum(1 for outcome in outcomes if outcome.correct)
    n = len(outcomes)
    accuracy = _rate(correct, n)

    family_hits: Counter[str] = Counter()
    family_totals: Counter[str] = Counter()
    edge_hits: Counter[str] = Counter()
    edge_totals: Counter[str] = Counter()
    latencies: list[float] = []
    error_kinds: Counter[str] = Counter()
    for outcome in outcomes:
        family_totals[outcome.family] += 1
        if outcome.correct:
            family_hits[outcome.family] += 1
        for edge in outcome.edge_cases:
            edge_totals[edge] += 1
            if outcome.correct:
                edge_hits[edge] += 1
        if outcome.latency_ms is not None:
            latencies.append(outcome.latency_ms)
        if not outcome.correct and outcome.error_type:
            error_kinds[outcome.error_type] += 1

    timeouts = error_kinds.get("timeout", 0)
    invalid = error_kinds.get("parse_error", 0) + error_kinds.get("invalid_sql", 0)
    executed = n - error_kinds.get("execution_error", 0) - error_kinds.get("parse_error", 0)
    return BenchmarkScores(
        n=n,
        execution_accuracy=accuracy,
        benchmark_pass_rate=accuracy,
        family_scores={
            family: _rate(family_hits[family], total) for family, total in family_totals.items()
        },
        family_counts=dict(family_totals),
        edge_scores={edge: _rate(edge_hits[edge], total) for edge, total in edge_totals.items()},
        edge_counts=dict(edge_totals),
        parse_rate=_rate(n - error_kinds.get("parse_error", 0), n),
        execution_success_rate=_rate(executed, n),
        invalid_sql_rate=_rate(invalid, n),
        timeout_rate=_rate(timeouts, n),
        avg_latency_ms=mean(latencies) if latencies else None,
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
    )


def outcomes_from_list(data: list[dict[str, object]]) -> list[PredictionOutcome]:
    """Strict outcome loading; malformed rows fail, never repaired."""
    from .errors import BusinessValidationError

    try:
        return [PredictionOutcome.model_validate(row) for row in data]
    except Exception as exc:
        raise BusinessValidationError(f"invalid prediction outcomes: {exc}") from exc


def latency_summary(outcomes: list[PredictionOutcome]) -> dict[str, float | None]:
    """Latency-only view; explicitly not a quality proxy (§17)."""
    latencies = [o.latency_ms for o in outcomes if o.latency_ms is not None]
    if not latencies:
        return {"n": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None}
    return {
        "n": len(latencies),
        "mean_ms": mean(latencies),
        "p50_ms": _percentile(latencies, 50),
        "p95_ms": _percentile(latencies, 95),
    }
