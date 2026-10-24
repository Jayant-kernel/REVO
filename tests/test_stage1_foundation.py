"""Stage 1 regression witnesses; no providers or frozen evidence."""
from decimal import Decimal, localcontext

import duckdb
import pytest

from tests.verify_testkit import SimBackend, make_candidate, make_execution, make_task
from verified_data_factory.verification.comparator import cells_equal, compare
from verified_data_factory.verification.models import (
    COMPARISON_VERSION,
    ComparisonPolicy,
    ExpectedResult,
)
from verified_data_factory.verification.oracle_registry import RETIRED_VERSIONS, get_oracle


@pytest.mark.parametrize("value", [2**63, -(2**200), 10**10000], ids=["bigint-overflow", "negative-huge", "ten-thousand-digits"])
def test_python_integer_reflexivity_is_unbounded(value):
    assert cells_equal(value, value, ComparisonPolicy())
    assert not cells_equal(value, value, ComparisonPolicy(), "BIGINT")
    assert not cells_equal(value, value + 1, ComparisonPolicy())


@pytest.mark.parametrize("dtype,value,valid", [
    ("DECIMAL(2,1)", "100.9", False),
    ("DECIMAL(2,1)", "9.9", True),
    ("DECIMAL(2,1)", "-9.9000", True),
    ("DECIMAL(2,1)", "0.01", False),
    ("DECIMAL(2,1)", "10", False),
    ("DECIMAL(38,18)", "99999999999999999999.123456789012345678", True),
    ("DECIMAL(38,18)", "100000000000000000000", False),
    ("DECIMAL(39,0)", "0", False),
    ("DECIMAL", "999999999999999.999", True),
    ("DECIMAL", "1000000000000000", False),
    ("DECIMAL", "0.0001", False),
    ("NUMERIC(2)", "99", True),
    ("NUMERIC(2)", "0.1", False),
])
def test_decimal_domain_without_rounding_or_context_dependence(dtype, value, valid):
    expected = ExpectedResult(columns=["v"], column_types=[dtype], rows=[[Decimal(value)]])
    with localcontext() as context:
        context.prec = 6
        assert compare(expected, ["v"], [[value]], column_types=[dtype]).match is valid


def test_actual_decimal_metadata_validates_its_own_domain():
    expected = ExpectedResult(columns=["v"], column_types=["DECIMAL(3,1)"], rows=[["10.0"]])
    assert not compare(expected, ["v"], [["10.0"]], column_types=["DECIMAL(2,1)"]).match
    assert compare(expected, ["v"], [["10.00"]], column_types=["DECIMAL(4,2)"]).match


def test_decimal_equality_beyond_context_precision_and_zero_scale():
    expected = ExpectedResult(columns=["v"], column_types=["DECIMAL(38,18)"],
                              rows=[["99999999999999999999.123456789012345678"]])
    with localcontext() as context:
        context.prec = 6
        assert not compare(expected, ["v"], [["99999999999999999999.123456789012345679"]]).match
    zero = ExpectedResult(columns=["v"], column_types=["DECIMAL(2,1)"], rows=[["0E-1000"]])
    assert compare(zero, ["v"], [["0.0"]]).match


@pytest.mark.parametrize("dtype,value", [("TIME", "03:04:05+01:00"),
                                       ("TIMESTAMP", "2025-01-01T03:04:05Z")])
def test_timezone_values_fail_closed(dtype, value):
    expected = ExpectedResult(columns=["v"], column_types=[dtype], rows=[[value]])
    assert not compare(expected, ["v"], [[value]], column_types=[dtype]).match


@pytest.mark.parametrize("template_id", ["sql.windows.ranked", "sql.dedup.latest"])
@pytest.mark.parametrize("empty", [False, True])
def test_simulated_temporal_metadata_survives_empty_and_null_outputs(template_id, empty):
    task = make_task(template_id)
    candidate = make_candidate(task, "SELECT 1")
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, task.tables)
    rows = [] if empty else [[None] * len(expected.columns)]
    execution = make_execution(task, candidate, rows, expected.columns)
    assert [c.type for c in execution.result_data.columns] == expected.column_types
    backend = SimBackend()
    result = backend.run(task, candidate, {name: [] for name in task.tables}, "empty")
    assert [c.type for c in result.result_data.columns] == expected.column_types


def test_scripted_metadata_is_independent_of_values():
    task = make_task("sql.dedup.latest")
    candidate = make_candidate(task, "SELECT 1")
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, task.tables)
    wrong = ["VARCHAR"] * len(expected.columns)
    execution = make_execution(task, candidate, expected.rows, expected.columns, column_types=wrong)
    assert not compare(expected, expected.columns, execution.result_data.rows, column_types=wrong).match
    result = SimBackend(column_types_by_label={"wrong": wrong}).run(task, candidate, task.tables, "wrong")
    assert [c.type for c in result.result_data.columns] == wrong


@pytest.mark.parametrize("k", [2, 3])
def test_top_category_tie_wrong_sql_and_k_boundary(k):
    tables = {"category_sales": [
        {"category": category, "amount": 10, "status": "completed", "sold_on": "2025-01-01"}
        for category in ["a", "b", "c"]
    ]}
    entry = get_oracle("sql.aggregation.top_category_sales", 1)
    expected = entry.fn({"year": 2025, "status_filter": "completed", "top_k": k}, tables)
    with duckdb.connect() as connection:
        connection.execute("CREATE TABLE category_sales(category VARCHAR, amount INTEGER)")
        connection.executemany("INSERT INTO category_sales VALUES (?, ?)", [(r["category"], r["amount"]) for r in tables["category_sales"]])
        for direction, valid in [("ASC", True), ("DESC", False)]:
            cursor = connection.execute(f"SELECT category, SUM(amount) AS total_sales FROM category_sales GROUP BY category ORDER BY total_sales DESC, category {direction} LIMIT {k}")
            types = [str(c[1]) for c in cursor.description]
            assert compare(expected, expected.columns, [list(r) for r in cursor.fetchall()], column_types=types).match is valid
    assert entry.oracle_version == 3


def test_semantic_identity_advances_including_shared_retired_implementations():
    assert COMPARISON_VERSION == "3.0-authoritative"
    assert all(get_oracle(*key).oracle_version >= 2 for key in RETIRED_VERSIONS)
