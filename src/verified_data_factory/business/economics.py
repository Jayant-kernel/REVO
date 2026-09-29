"""Unit economics with explicit unknowns (Phase 8, §27–§29, §73).

Costs are measured where possible; where a cost is unavailable the
input stays None and surfaces in ``unknown_inputs`` — unknown inputs
never silently become zero. Scale scenarios are labeled SCENARIO and
are planning aids, never forecasts or price claims.
"""

from __future__ import annotations

from .errors import BusinessConfigError
from .models import CostModel, CostScenario, UnitEconomics, ValueBasis

SCENARIO_SCALES: tuple[int, ...] = (1_000, 10_000, 100_000, 1_000_000)


def build_cost_model(
    *,
    variable_costs: dict[str, float | None] | None = None,
    fixed_costs: dict[str, float | None] | None = None,
    assumptions: list[str] | None = None,
    measured: bool = False,
    currency: str = "USD",
) -> CostModel:
    """Assemble a cost model; variable and fixed costs stay separated (§28)."""
    for name, amount in {**(variable_costs or {}), **(fixed_costs or {})}.items():
        if amount is not None and amount < 0:
            raise BusinessConfigError(f"negative cost for {name!r}")
    return CostModel(
        currency=currency,
        variable_costs=dict(variable_costs or {}),
        fixed_costs=dict(fixed_costs or {}),
        assumptions=list(assumptions or []),
        measured=measured,
    )


def known_total(model: CostModel) -> tuple[float | None, list[str]]:
    """Sum of known cost inputs; unknowns listed, never zeroed."""
    unknown = [
        name
        for name, amount in {**model.variable_costs, **model.fixed_costs}.items()
        if amount is None
    ]
    known = [
        amount
        for amount in (*model.variable_costs.values(), *model.fixed_costs.values())
        if amount is not None
    ]
    if not known:
        return None, unknown
    return sum(known), unknown


def unit_economics(model: CostModel, golden_records: int) -> UnitEconomics:
    """Per-Golden economics; unknown totals propagate as unknown (§29)."""
    if golden_records <= 0:
        raise BusinessConfigError("golden_records must be positive")
    total, unknown = known_total(model)
    if total is None:
        return UnitEconomics(
            total_cost=None,
            golden_records=golden_records,
            unknown_inputs=unknown,
            basis="MEASURED" if model.measured else "ASSUMED",
        )
    return UnitEconomics(
        total_cost=total,
        golden_records=golden_records,
        cost_per_golden=total / golden_records,
        cost_per_1000_golden=total / golden_records * 1000,
        cost_per_million_golden=total / golden_records * 1_000_000,
        unknown_inputs=unknown,
        basis="MEASURED" if model.measured else "ASSUMED",
    )


def scenario_table(
    unit_variable: float | None,
    fixed: float | None,
    assumptions: list[str] | None = None,
    scales: tuple[int, ...] = SCENARIO_SCALES,
) -> list[CostScenario]:
    """Scale scenarios at explicit per-unit/fixed assumptions (§29)."""
    scenarios: list[CostScenario] = []
    for scale in scales:
        total = (
            None
            if unit_variable is None and fixed is None
            else (unit_variable or 0.0) * scale + (fixed or 0.0)
        )
        scenarios.append(
            CostScenario(
                scale_records=scale,
                total_cost=total,
                cost_per_golden=(total / scale) if total is not None else None,
                assumptions=list(assumptions or []),
            )
        )
    return scenarios


def economics_basis(model: CostModel) -> ValueBasis:
    """Measured costs are MEASURED; anything else is ASSUMED."""
    return "MEASURED" if model.measured else "ASSUMED"
