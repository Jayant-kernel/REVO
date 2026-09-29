"""Run-level economics instrumentation (native units, honest bases).

Collects what the run actually measures — wall-clock seconds, token
counts, execution counts, artifact bytes — and derives per-unit costs
in those native units. Money appears only with an explicit caller-
supplied price table (then ASSUMED unless stated otherwise); power
draw appears only from a trustworthy source. Everything unmeasurable
stays UNKNOWN, never zero.
"""

from __future__ import annotations

from typing import Any

from .models import PRODUCT_SCHEMA_VERSION, MetricValue, RunEconomics

__all__ = ["collect_run_economics", "economics_summary", "observed"]


def observed(value: float | None, unit: str, note: str = "") -> MetricValue:
    """An actually-measured metric (None stays UNKNOWN, never zero)."""
    if value is None:
        return MetricValue(value=None, basis="UNKNOWN", unit=unit, note=note or "not measured")
    return MetricValue(value=value, basis="OBSERVED", unit=unit, note=note)


def collect_run_economics(
    *,
    generation_wall_s: float | None = None,
    generation_candidates: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    model_calls: int | None = None,
    executions: int | None = None,
    verifications: int | None = None,
    mutation_runs: int | None = None,
    verification_wall_s: float | None = None,
    artifact_bytes: int | None = None,
    dataset_bytes: int | None = None,
    machine_identity: str = "",
    cpu_identity: str = "UNKNOWN",
    gpu_identity: str = "UNKNOWN",
    power_watts: float | None = None,
    power_source: str = "",
    passes: int | None = None,
    goldens: int | None = None,
    novel_goldens: int | None = None,
    price_table: dict[str, float] | None = None,
    price_basis_note: str = "caller-supplied rates; assumed unless stated",
) -> RunEconomics:
    """Assemble run economics from measured inputs plus explicit prices."""
    econ = RunEconomics(
        generation_wall_s=observed(generation_wall_s, "s", "client-observed generation time"),
        generation_candidates=observed(
            float(generation_candidates) if generation_candidates is not None else None,
            "candidates",
        ),
        prompt_tokens=observed(
            float(prompt_tokens) if prompt_tokens is not None else None, "tokens"
        ),
        completion_tokens=observed(
            float(completion_tokens) if completion_tokens is not None else None, "tokens"
        ),
        model_calls=observed(float(model_calls) if model_calls is not None else None, "calls"),
        executions=observed(float(executions) if executions is not None else None, "runs"),
        verifications=observed(float(verifications) if verifications is not None else None, "runs"),
        mutation_runs=observed(float(mutation_runs) if mutation_runs is not None else None, "runs"),
        verification_wall_s=observed(
            verification_wall_s, "s", "verification wall time if instrumented"
        ),
        artifact_bytes=observed(
            float(artifact_bytes) if artifact_bytes is not None else None, "bytes"
        ),
        dataset_bytes=observed(
            float(dataset_bytes) if dataset_bytes is not None else None, "bytes"
        ),
        machine_identity=machine_identity,
        cpu_identity=cpu_identity,
        gpu_identity=gpu_identity,
        power_watts=observed(power_watts, "W", power_source or "no trustworthy source"),
        schema_version=PRODUCT_SCHEMA_VERSION,
    )

    def _per(unit_total: MetricValue, count: int | None, note: str) -> MetricValue:
        if unit_total.value is None or not count:
            return MetricValue(value=None, basis="UNKNOWN", unit="s", note=note)
        return MetricValue(value=unit_total.value / count, basis="OBSERVED", unit="s", note=note)

    total_s = (generation_wall_s or 0.0) + (verification_wall_s or 0.0)
    total_observed = generation_wall_s is not None or verification_wall_s is not None
    econ = econ.model_copy(
        update={
            "per_candidate_s": _per(
                MetricValue(value=total_s if total_observed else None, basis="OBSERVED", unit="s"),
                generation_candidates,
                "wall seconds per candidate",
            ),
            "per_pass_s": _per(
                MetricValue(value=total_s if total_observed else None, basis="OBSERVED", unit="s"),
                passes,
                "wall seconds per PASS",
            ),
            "per_golden_s": _per(
                MetricValue(value=total_s if total_observed else None, basis="OBSERVED", unit="s"),
                goldens,
                "wall seconds per Golden",
            ),
            "per_novel_golden_s": _per(
                MetricValue(value=total_s if total_observed else None, basis="OBSERVED", unit="s"),
                novel_goldens,
                "wall seconds per novel Golden",
            ),
        }
    )
    per_golden = econ.per_golden_s.value
    projections: dict[str, MetricValue] = {}
    for label, target in (
        ("projected_s_for_1000_golden", 1000),
        ("projected_s_for_10000_golden", 10000),
    ):
        if per_golden is None:
            projections[label] = MetricValue(
                value=None, basis="UNKNOWN", unit="s", note="no observed per-golden cost"
            )
        else:
            projections[label] = MetricValue(
                value=per_golden * target,
                basis="PROJECTED",
                unit="s",
                note=f"linear projection from observed per-golden cost over {target} Golden",
            )
    econ = econ.model_copy(update=projections)

    monetary: dict[str, MetricValue] = {}
    if price_table:
        for key, rate in price_table.items():
            monetary[key] = MetricValue(
                value=rate, basis="ASSUMED", unit="price", note=price_basis_note
            )
    econ = econ.model_copy(update={"monetary": monetary})
    return econ


def economics_summary(econ: RunEconomics) -> dict[str, Any]:
    """JSON-ready economics payload for reports."""
    return econ.model_dump(mode="json")
