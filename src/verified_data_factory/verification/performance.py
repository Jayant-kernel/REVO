"""Performance evidence (Phase 4).

Records candidate runtime from Phase 3 metadata against an optional
budget. Evidence only: exceeding a budget never flips correctness —
Phase 5 owns quality thresholds.
"""

from __future__ import annotations

from verified_data_factory.sandbox.models import ExecutionResult

from .models import PerformanceOutcome


def collect_performance(
    execution: ExecutionResult, enabled: bool, warn_after_ms: int | None
) -> PerformanceOutcome:
    """Collect runtime evidence without judging correctness."""
    if not enabled:
        return PerformanceOutcome(note="disabled")
    duration = execution.duration_ms
    if warn_after_ms is None:
        return PerformanceOutcome(duration_ms=duration, note="no budget configured")
    return PerformanceOutcome(
        duration_ms=duration,
        warn_after_ms=warn_after_ms,
        within_budget=duration <= warn_after_ms,
        note="budget exceeded" if duration > warn_after_ms else "within budget",
    )
