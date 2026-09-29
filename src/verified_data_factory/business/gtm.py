"""GTM evidence: funnel, offers, pricing, commercial tests, pilot packages (§41–§44, §54).

This module records commercial evidence; it is not a CRM, payment
system, or sales pipeline. Pricing scenarios are ASSUMED until customer
behavior validates them. Pilot packages never expose private benchmark
answers unless explicitly configured to do so.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import BusinessConfigError, BusinessIOError
from .models import (
    FUNNEL_STAGES,
    CommercialExperiment,
    CommercialFunnel,
    CommercialStatus,
    OfferStatus,
    PricingScenario,
    PricingUnit,
    ProductOffer,
    ValueBasis,
)


def empty_funnel() -> CommercialFunnel:
    """A funnel with zeroed known stages; counts are added by observation."""
    return CommercialFunnel(counts={stage: 0 for stage in FUNNEL_STAGES})


def record_funnel_stage(funnel: CommercialFunnel, stage: str, count: int) -> CommercialFunnel:
    """Set an observed stage count (§44). Stages outside the model fail."""
    if stage not in FUNNEL_STAGES:
        raise BusinessConfigError(f"unknown funnel stage: {stage!r}")
    if count < 0:
        raise BusinessConfigError("funnel counts cannot be negative")
    return funnel.model_copy(update={"counts": {**funnel.counts, stage: count}})


def funnel_conversion(funnel: CommercialFunnel, from_stage: str, to_stage: str) -> float | None:
    """Observed conversion rate; None when the base count is zero."""
    base = funnel.counts.get(from_stage, 0)
    if base <= 0:
        return None
    return funnel.counts.get(to_stage, 0) / base


def create_offer(
    *,
    offer_id: str,
    product_release_id: str,
    target_segment: str,
    use_case: str = "",
    delivery_format: str = "",
    support_level: str = "",
    commercial_status: OfferStatus = "EXPERIMENTAL",
) -> ProductOffer:
    """Describe a commercial offer without claiming readiness (§41)."""
    return ProductOffer(
        offer_id=offer_id,
        product_release_id=product_release_id,
        target_segment=target_segment,
        use_case=use_case,
        delivery_format=delivery_format,
        support_level=support_level,
        commercial_status=commercial_status,
    )


def create_pricing_scenario(
    *,
    scenario_id: str,
    assumed_price: float,
    pricing_unit: PricingUnit = "DATASET",
    product_release_id: str | None = None,
    cost_basis: float | None = None,
    target_margin: float | None = None,
    assumptions: list[str] | None = None,
    basis: ValueBasis = "ASSUMED",
    evidence_ids: list[str] | None = None,
) -> PricingScenario:
    """A price hypothesis; MEASURED requires linked customer evidence (§42)."""
    if basis == "MEASURED" and not evidence_ids:
        raise BusinessConfigError("MEASURED pricing requires customer evidence ids")
    return PricingScenario(
        scenario_id=scenario_id,
        product_release_id=product_release_id,
        assumed_price=assumed_price,
        pricing_unit=pricing_unit,
        cost_basis=cost_basis,
        target_margin=target_margin,
        assumptions=list(assumptions or []),
        basis=basis,
        evidence_ids=list(evidence_ids or []),
    )


def create_commercial_experiment(
    *,
    experiment_id: str,
    hypothesis: str,
    variant: str,
    population: str = "",
    measurement: str = "",
) -> CommercialExperiment:
    """Plan a pricing/format/offer test (§54)."""
    return CommercialExperiment(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        variant=variant,
        population=population,
        measurement=measurement,
    )


def complete_commercial_experiment(
    experiment: CommercialExperiment, *, result: str
) -> CommercialExperiment:
    """Record an observed result; results are text, never revenue claims."""
    return experiment.model_copy(update={"result": result, "status": "COMPLETED"})


def set_commercial_status(
    experiment: CommercialExperiment, status: CommercialStatus
) -> CommercialExperiment:
    return experiment.model_copy(update={"status": status})


def export_pilot_package(
    *,
    out_dir: str | Path,
    readme: str,
    product_files: dict[str, bytes],
    benchmark_public: dict[str, Any],
    evaluation: dict[str, Any] | None = None,
    results: dict[str, Any] | None = None,
    provenance_refs: dict[str, Any] | None = None,
    include_private_answers: bool = False,
    private_answers: dict[str, Any] | None = None,
) -> list[str]:
    """Write the pilot/ layout; private answers need explicit opt-in (§40, §51).

    ``benchmark_public`` must already exclude expected answers — this
    exporter double-checks for an ``expected_sql`` key and refuses to
    write it unless ``include_private_answers`` is set.
    """
    root = Path(out_dir)
    written: list[str] = []
    try:
        (root / "product").mkdir(parents=True, exist_ok=True)
        (root / "benchmark").mkdir(parents=True, exist_ok=True)
        (root / "evaluation").mkdir(parents=True, exist_ok=True)
        (root / "results").mkdir(parents=True, exist_ok=True)
        (root / "provenance").mkdir(parents=True, exist_ok=True)
        (root / "README.md").write_text(readme, encoding="utf-8")
        written.append("README.md")
        for name, content in product_files.items():
            target = root / "product" / name
            target.write_bytes(content)
            written.append(f"product/{name}")
        _write_json(root / "benchmark" / "benchmark_public.json", benchmark_public)
        written.append("benchmark/benchmark_public.json")
        if _contains_answers(benchmark_public) and not include_private_answers:
            raise BusinessConfigError(
                "benchmark payload contains private answers; redaction required"
            )
        if include_private_answers:
            if not private_answers:
                raise BusinessConfigError("include_private_answers needs private_answers payload")
            _write_json(root / "benchmark" / "answers_private.json", private_answers)
            written.append("benchmark/answers_private.json")
        _write_json(root / "evaluation" / "evaluation.json", evaluation or {})
        written.append("evaluation/evaluation.json")
        _write_json(root / "results" / "results.json", results or {})
        written.append("results/results.json")
        _write_json(root / "provenance" / "provenance_refs.json", provenance_refs or {})
        written.append("provenance/provenance_refs.json")
    except BusinessConfigError:
        raise
    except OSError as exc:
        raise BusinessIOError(f"cannot write pilot package: {exc}") from exc
    return written


def _contains_answers(payload: dict[str, Any]) -> bool:
    text = json.dumps(payload)
    return "expected_sql" in text


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
