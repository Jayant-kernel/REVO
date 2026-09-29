"""Economics tests: costs, unit economics, scenarios, unknowns (§27–§29)."""

import pytest

from verified_data_factory.business import (
    build_cost_model,
    compute_economics,
    scenario_table,
    unit_economics,
)
from verified_data_factory.business.errors import BusinessConfigError


def test_measured_costs_roll_up():
    model = build_cost_model(
        variable_costs={"inference": 120.0, "execution_cpu": 30.0},
        fixed_costs={"storage": 50.0},
        assumptions=["fixture prices"],
        measured=True,
    )
    units = compute_economics(model, 100)
    assert units.total_cost == 200.0
    assert units.cost_per_golden == 2.0
    assert units.cost_per_1000_golden == 2000.0
    assert units.cost_per_million_golden == 2_000_000.0
    assert units.unknown_inputs == []
    assert units.basis == "MEASURED"


def test_unknown_costs_stay_unknown():
    model = build_cost_model(
        variable_costs={"inference": 120.0, "human_audit": None},
        fixed_costs={},
        measured=False,
    )
    units = unit_economics(model, 100)
    assert units.total_cost == 120.0
    assert units.unknown_inputs == ["human_audit"]
    assert units.basis == "ASSUMED"


def test_all_unknown_total_is_none():
    model = build_cost_model(variable_costs={"inference": None})
    units = unit_economics(model, 10)
    assert units.total_cost is None
    assert units.cost_per_golden is None


def test_negative_cost_rejected():
    with pytest.raises(BusinessConfigError):
        build_cost_model(variable_costs={"inference": -5.0})


def test_zero_golden_rejected():
    with pytest.raises(BusinessConfigError):
        unit_economics(build_cost_model(variable_costs={"a": 1.0}), 0)


def test_scenario_table_scales():
    scenarios = scenario_table(0.5, 100.0, ["fixture"])
    assert [s.scale_records for s in scenarios] == [1_000, 10_000, 100_000, 1_000_000]
    assert all(s.label == "SCENARIO" for s in scenarios)
    first = scenarios[0]
    assert first.total_cost == 0.5 * 1_000 + 100.0
    assert first.cost_per_golden == (0.5 * 1_000 + 100.0) / 1_000
