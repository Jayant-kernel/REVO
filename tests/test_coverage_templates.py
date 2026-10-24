"""Phase 2 coverage templates: HAVING, LIMIT, and UNION must be real."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tests.test_business_tasks import ADVERSARIAL_EXPECTED, SQL
from verified_data_factory.quality.coverage import detect_constructs
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.adversarial import independent_adversarial_tables
from verified_data_factory.verification.oracle_registry import get_oracle

NEW = {
    "sql.aggregation.warehouse_throughput": "having",
    "sql.aggregation.top_category_sales": "limit",
    "sql.aggregation.product_unique_conversion": "having",
    "sql.cte.category_descendant_sales": "cte",
    "sql.cte.order_line_reconciliation": "cte",
    "sql.cte.session_funnel_completion": "cte",
    "sql.cte.customer_first_month_repeat": "cte",
    "sql.subqueries.customer_outreach": "union",
}


def _execute(task, tables, sql):
    con = materialize_duckdb(task.schema_, tables)
    try:
        rows = [[v.isoformat() if isinstance(v, (date, datetime)) else v for v in r]
                for r in con.execute(sql).fetchall()]
        return rows
    finally:
        con.close()


@pytest.mark.parametrize("template_id,construct", NEW.items())
def test_new_template_contract_and_construct(template_id, construct):
    task = generate_task(load_builtin_registry().get(template_id), 7)
    expected = get_oracle(template_id, 1).fn(task.requirements, task.tables)
    assert _execute(task, task.tables, SQL[template_id]) == expected.rows
    assert construct in detect_constructs(SQL[template_id])
    tables = independent_adversarial_tables(task)
    assert tables is not None
    adv_expected = get_oracle(template_id, 1).fn(task.requirements, tables)
    assert adv_expected.rows == ADVERSARIAL_EXPECTED[template_id]
    assert _execute(task, tables, SQL[template_id]) == adv_expected.rows


def test_union_deduplicates_but_union_all_does_not():
    task = generate_task(load_builtin_registry().get("sql.subqueries.customer_outreach"), 7)
    plain = SQL["sql.subqueries.customer_outreach"]
    union_all = plain.replace("UNION", "UNION ALL")
    assert "UNION ALL" in union_all
    # No customer appears on both channels in the fixture, so metrics agree;
    # the adversarial fixture does place customer 2 on both channels.
    tables = independent_adversarial_tables(task)
    deduped = _execute(task, tables, plain)
    duplicated = _execute(task, tables, union_all)
    assert deduped == [[1], [2]]
    assert len(duplicated) > len(deduped)
