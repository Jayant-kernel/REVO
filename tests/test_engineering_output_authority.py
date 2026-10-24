"""Oracle schemas are authoritative over candidate output metadata."""
from datetime import date, time
from decimal import Decimal

import pytest

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.business_oracles import (
    expansion_total,
    saas_activation_payment,
)
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.models import ComparisonPolicy, ExpectedResult, OrderSpec
from verified_data_factory.verification.oracle_registry import RETIRED_VERSIONS, get_oracle


@pytest.mark.parametrize("oracle,requirements,status", [
    (saas_activation_payment, {"year": 2025, "funnel_steps": ["signup", "trial", "activation", "payment"]}, "signup"),
    (expansion_total, {"year": 2025}, "eligible"),
])
def test_candidate_cannot_cast_numeric_looking_segment_to_integer(oracle, requirements, status):
    tables = {"account_funnel": [{"record_id": 1, "entity_id": 1, "group_key": "001",
                                 "occurred_at": "2025-01-01 00:00:00", "sequence": 1,
                                 "status": status, "amount": 0}]}
    expected = oracle(requirements, tables)
    result = compare(expected, ["group_key", "total_amount"], [[1, 0]], column_types=["INTEGER", "HUGEINT"])
    assert not result.match


def test_empty_oracle_output_still_declares_column_types():
    expected = saas_activation_payment({"year": 2025, "funnel_steps": ["signup", "trial", "activation", "payment"]}, {"account_funnel": []})
    assert expected.column_types == ["VARCHAR", "HUGEINT"]
    assert not compare(expected, expected.columns, [], column_types=["INTEGER", "HUGEINT"]).match


def test_every_current_builtin_oracle_declares_a_complete_schema_even_when_empty():
    for template in load_builtin_registry().list():
        key = (template.template_id, template.version)
        assert key not in RETIRED_VERSIONS
        task = generate_task(template, 94001)
        entry = get_oracle(*key)
        populated = entry.fn(dict(task.requirements), task.tables)
        empty = entry.fn(dict(task.requirements), {name: [] for name in task.tables})
        assert len(populated.column_types) == len(populated.columns), key
        assert len(empty.column_types) == len(empty.columns), key
        assert populated.column_types == empty.column_types, key
        if key == ("sql.joins.requested_language_titles", 1):
            assert "order_by" not in task.requirements
            assert populated.order == empty.order == OrderSpec(type="unordered")
            continue
        public_keys = [name.rsplit(".", 1)[-1] for name in task.requirements["order_by"]]
        assert populated.order.type == "ordered", key
        # ranked@1 must retain its unprojected key and refuse unsupported proof.
        missing = set(public_keys) - set(populated.columns)
        assert not missing or (key == ("sql.windows.ranked", 1) and missing == {"order_date"}), key
        assert [name for name, _ in populated.order.keys][:len(public_keys)] == public_keys, key
        if missing:
            assert not compare(populated, populated.columns, populated.rows,
                               column_types=populated.column_types).match, key
        assert populated.order == empty.order, key


def test_current_oracles_are_advanced_while_retired_versions_stay_replayable():
    current = {(template.template_id, template.version) for template in load_builtin_registry().list()}
    initial = {
        ("sql.dedup.lowest_quote", 1),
        ("sql.joins.requested_language_titles", 1),
        ("sql.retention.renewal_coverage", 1),
        ("sql.subqueries.pareto_shipping", 1),
        ("sql.windows.queue_batches", 1),
    }
    assert initial <= current
    assert all(get_oracle(*key).oracle_version == 1 for key in initial)
    assert all(get_oracle(*key).oracle_version >= 2 for key in current - initial)
    assert all(get_oracle(*key).oracle_version == 2 for key in RETIRED_VERSIONS)


@pytest.mark.parametrize(
    ("dtype", "value"),
    [
        ("BIGINT", -(2**63)),
        ("UBIGINT", 2**64 - 1),
        ("DECIMAL(38, 18)", Decimal("99999999999999999999.123456789012345678")),
        ("DOUBLE", 1.25),
        ("VARCHAR(12)", "001"),
        ("BOOLEAN", True),
        ("DATE", date(2025, 1, 2)),
        ("TIMESTAMP", "2025-01-02 03:04:05"),
        ("TIME", time(3, 4, 5)),
    ],
)
def test_mandatory_scalar_families_are_supported(dtype, value):
    expected = ExpectedResult(columns=["value"], column_types=[dtype], rows=[[value]])
    assert compare(expected, ["value"], [[value]], column_types=[dtype]).match


@pytest.mark.parametrize(
    "dtype", ["JSON", "INTEGER[]", "DECIMAL(nope)", "DECIMAL(2,3)", "TIMESTAMP WITH TIME ZONE"]
)
def test_unsupported_or_malformed_types_fail_closed(dtype):
    expected = ExpectedResult(columns=["value"], column_types=[dtype], rows=[["x"]])
    result = compare(expected, ["value"], [["x"]], column_types=[dtype])
    assert not result.match
    assert result.notes


def test_candidate_metadata_is_checked_but_never_drives_expected_coercion():
    expected = ExpectedResult(columns=["value"], column_types=["VARCHAR"], rows=[["001"]])
    assert not compare(expected, ["value"], [[1]], column_types=["INTEGER"]).match
    assert not compare(expected, ["value"], [[1]], column_types=["VARCHAR"]).match


def test_exact_numeric_temporal_null_and_bag_contracts():
    policy = ComparisonPolicy(float_abs_tol=1.0, float_rel_tol=1.0)
    exact = ExpectedResult(
        columns=["integer", "decimal"],
        column_types=["HUGEINT", "DECIMAL(38,18)"],
        rows=[[2**63 + 1, Decimal("1.000000000000000001")]],
    )
    assert not compare(exact, exact.columns, [[2**63, "1.000000000000000002"]], policy).match
    unsigned = ExpectedResult(columns=["value"], column_types=["UBIGINT"], rows=[[0]])
    assert not compare(unsigned, ["value"], [[-1]]).match

    temporal = ExpectedResult(
        columns=["day", "stamp", "clock"],
        column_types=["DATE", "TIMESTAMP", "TIME"],
        rows=[[date(2025, 1, 2), "2025-01-02 03:04:05", time(3, 4, 5)]],
    )
    assert compare(temporal, temporal.columns, [["2025-01-02", "2025-01-02T03:04:05", "03:04:05"]]).match

    bag = ExpectedResult(columns=["value"], column_types=["INTEGER"], rows=[[None], [1], [1]])
    assert compare(bag, ["value"], [[1], [None], [1]]).match
    assert not compare(bag, ["value"], [[1], [None], [2]]).match


def test_order_contract_checks_null_placement_then_expected_bag():
    expected = ExpectedResult(
        columns=["value"],
        column_types=["INTEGER"],
        rows=[[1], [None]],
        order=OrderSpec(type="ordered", keys=[("value", "asc")], nulls={"value": "first"}),
    )
    assert compare(expected, ["value"], [[None], [1]]).match
    assert not compare(expected, ["value"], [[1], [None]]).match
