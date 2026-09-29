"""Paired-binary statistics without third-party dependencies (§19).

Binary correctness outcomes on the same benchmark instances under both
conditions call for a paired comparison: the exact McNemar test on
discordant pairs, Wilson score intervals per arm, and a Wald interval
for the paired difference. No t-tests on binary data. Small samples
produce explicit warnings, never manufactured significance.
"""

from __future__ import annotations

import math

from .models import PredictionOutcome, RepeatedRunSummary, StatisticalEvidence

Z_95 = 1.959963984540054
SMALL_SAMPLE_N = 30
MIN_DISCORDANT = 10


def _comb(n: int, k: int) -> int:
    return math.comb(n, k)


def wilson_interval(hits: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n <= 0:
        return (0.0, 0.0)
    center = (hits + z * z / 2.0) / (n + z * z)
    half = z * math.sqrt(hits * (n - hits) / n + z * z / 4.0) / (n + z * z)
    return (max(0.0, center - half), min(1.0, center + half))


def mcnemar_exact_p(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value via the binomial tail.

    ``b`` = baseline-correct/treatment-wrong, ``c`` = baseline-wrong/
    treatment-correct. Under the null each discordant pair favors either
    arm with probability 1/2.
    """
    n = b + c
    if n == 0:
        return 1.0
    extreme = min(b, c)
    tail = sum(_comb(n, k) for k in range(extreme + 1))
    return min(1.0, 2.0 * tail / 2.0**n)


def paired_delta_ci(a: int, b: int, c: int, d: int, z: float = Z_95) -> tuple[float, float]:
    """Wald interval for the paired difference (c - b) / n.

    Uses the paired variance b + c - (c - b)^2 / n. Honest for reporting;
    the McNemar p-value remains the significance statement.
    """
    n = a + b + c + d
    if n == 0:
        return (0.0, 0.0)
    delta = (c - b) / n
    variance = (b + c - (c - b) ** 2 / n) / (n * n)
    half = z * math.sqrt(max(0.0, variance))
    return (delta - half, delta + half)


def compare_paired(
    baseline: list[PredictionOutcome], treatment: list[PredictionOutcome]
) -> StatisticalEvidence:
    """Paired comparison on shared benchmark instances (§19)."""
    base_by_id = {o.record_id: o.correct for o in baseline}
    treat_by_id = {o.record_id: o.correct for o in treatment}
    shared = sorted(set(base_by_id) & set(treat_by_id))
    warnings: list[str] = []
    if not shared:
        return StatisticalEvidence(
            method="INSUFFICIENT_DATA",
            n=0,
            warnings=["no shared benchmark instances between arms"],
            sufficient=False,
        )
    a = sum(1 for i in shared if base_by_id[i] and treat_by_id[i])
    b = sum(1 for i in shared if base_by_id[i] and not treat_by_id[i])
    c = sum(1 for i in shared if not base_by_id[i] and treat_by_id[i])
    d = sum(1 for i in shared if not base_by_id[i] and not treat_by_id[i])
    n = len(shared)
    base_rate = (a + b) / n
    treat_rate = (a + c) / n
    delta_pp = (treat_rate - base_rate) * 100.0
    ci_low, ci_high = paired_delta_ci(a, b, c, d)
    if n < SMALL_SAMPLE_N:
        warnings.append(f"small sample (n={n}): statistical power is limited")
    if b + c < MIN_DISCORDANT:
        warnings.append(f"only {b + c} discordant pairs: McNemar has little power")
    return StatisticalEvidence(
        method="MCNEMAR_EXACT",
        n=n,
        baseline=base_rate,
        treatment=treat_rate,
        delta_pp=delta_pp,
        ci_low_pp=ci_low * 100.0,
        ci_high_pp=ci_high * 100.0,
        baseline_ci=wilson_interval(a + b, n),
        treatment_ci=wilson_interval(a + c, n),
        p_value=mcnemar_exact_p(b, c),
        discordant_pairs=b + c,
        warnings=warnings,
        sufficient=n >= SMALL_SAMPLE_N and (b + c) >= MIN_DISCORDANT,
    )


def summarize_repeated(values: list[float]) -> RepeatedRunSummary:
    """Mean/std/min/max over repeated runs (§20). One run is reported, not hidden."""
    if not values:
        return RepeatedRunSummary(n=0)
    ordered = sorted(values)
    avg = sum(values) / len(values)
    variance = sum((v - avg) ** 2 for v in values) / len(values) if len(values) > 1 else 0.0
    return RepeatedRunSummary(
        n=len(values),
        mean=avg,
        std=math.sqrt(variance),
        minimum=ordered[0],
        maximum=ordered[-1],
        values=list(values),
    )
