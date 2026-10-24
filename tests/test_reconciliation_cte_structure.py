"""Public CTE compliance is structural evidence, never a semantic mutant kill."""
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from scripts.phase3_diagnostic import _reference_sql
from tests.verify_testkit import SimBackend, make_candidate, make_execution
from verified_data_factory.task_engine import load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.qualification import reconciliation_profile as profile
from verified_data_factory.verification.qualification.structural import structural_checks

REFERENCE = _reference_sql()[profile.CONTRACT]
ALTERNATIVES = profile.alternatives(REFERENCE)
TASK = SimpleNamespace(template_id=profile.CONTRACT, template_version=1)
NO_CTE = """SELECT o.order_id,o.header_total_cents,
    COALESCE(l.line_total_cents,0) AS line_total_cents FROM orders o
    LEFT JOIN (SELECT order_id,SUM(CAST(quantity AS HUGEINT)*unit_price_cents)
      AS line_total_cents FROM order_lines GROUP BY order_id) l ON l.order_id=o.order_id
    WHERE o.order_status='completed' AND EXTRACT(YEAR FROM o.ordered_on)=2025
      AND o.header_total_cents<>COALESCE(l.line_total_cents,0) ORDER BY o.order_id ASC"""
UNUSED_CTE = ("WITH unused AS (SELECT order_id,SUM(CAST(quantity AS HUGEINT)*unit_price_cents) "
              "AS total FROM order_lines GROUP BY order_id) " + NO_CTE)
WRONG_SUM_DECORATION = (
    "WITH decoration AS (SELECT SUM(CAST(quantity AS HUGEINT)+unit_price_cents) wrong "
    "FROM order_lines) " + NO_CTE.replace(
        "WHERE o.order_status", "CROSS JOIN decoration WHERE o.order_status"))
GLOBAL_PRODUCT_DECORATION = WRONG_SUM_DECORATION.replace(
    "SUM(CAST(quantity AS HUGEINT)+unit_price_cents)",
    "SUM(CAST(quantity AS HUGEINT)*unit_price_cents)")
PER_ORDER_UNUSED_OUTPUT = (
    "WITH decoration AS (SELECT order_id,SUM(CAST(quantity AS HUGEINT)*unit_price_cents) "
    "unused_total FROM order_lines GROUP BY order_id) " + NO_CTE.replace(
        "WHERE o.order_status",
        "LEFT JOIN decoration d ON d.order_id=o.order_id WHERE o.order_status"))


def execute(sql):
    template = load_builtin_registry().get(profile.CONTRACT, 1)
    connection = materialize_duckdb(template.schema_definition, profile.rich_fixture())
    try:
        cursor = connection.execute(sql)
        return ([item[0] for item in cursor.description],
                [[str(value) if isinstance(value, (date, datetime)) else value for value in row]
                 for row in cursor.fetchall()])
    finally:
        connection.close()


@pytest.mark.parametrize("sql", [REFERENCE, *ALTERNATIVES], ids=["reference", "alt0", "alt1", "alt2"])
def test_existing_correct_forms_have_participating_cte(sql):
    assert execute(sql) == execute(REFERENCE)
    result = structural_checks(TASK, sql)
    assert result["status"] == "PASS"
    assert result["rule_id"] == "instruction:reconciliation_cte"
    assert result["sum_cte"] in result["participating_ctes"]


@pytest.mark.parametrize("sql", [NO_CTE, UNUSED_CTE], ids=["equivalent_no_cte", "unused_cte"])
def test_equal_results_do_not_replace_public_cte_structure(sql):
    assert execute(sql) == execute(REFERENCE)  # Not a semantic kill.
    result = structural_checks(TASK, sql)
    assert result["status"] == "FAIL"
    assert result["reason"] == "no_participating_cte"


@pytest.mark.parametrize("sql,verdict,code", [
    (NO_CTE, "FAIL", "STRUCTURAL_REQUIREMENT_FAILED"),
    (UNUSED_CTE, "FAIL", "STRUCTURAL_REQUIREMENT_FAILED"),
    (WRONG_SUM_DECORATION, "INCONCLUSIVE", "STRUCTURAL_CHECK_ERROR"),
    (GLOBAL_PRODUCT_DECORATION, "INCONCLUSIVE", "STRUCTURAL_CHECK_ERROR"),
    (PER_ORDER_UNUSED_OUTPUT, "INCONCLUSIVE", "STRUCTURAL_CHECK_ERROR"),
])
def test_verifier_rejects_structure_before_semantic_scoring(sql, verdict, code):
    task = SimpleNamespace(template_id=profile.CONTRACT, template_version=1,
                           task_id="reconciliation-cte-local-test")
    columns, rows = execute(sql)
    candidate = make_candidate(task, sql)  # Explicit unit-test object, no model output.
    execution = make_execution(task, candidate, rows, columns,
                               column_types=["INTEGER", "INTEGER", "HUGEINT"])
    backend = SimBackend()
    result = verify_candidate(task, candidate, execution, backend=backend)
    assert result.verdict == verdict
    assert result.failure_code == code
    assert result.evidence["structural_requirements"]["rule_id"] == "instruction:reconciliation_cte"
    assert result.mutation is None
    assert result.oracle is None
    assert backend.calls == []


@pytest.mark.parametrize("sql", [WRONG_SUM_DECORATION, GLOBAL_PRODUCT_DECORATION,
                                 PER_ORDER_UNUSED_OUTPUT],
                         ids=["sum_addition_cross_join", "global_product_cross_join",
                              "per_order_product_unused_output"])
def test_equivalent_decorative_aggregates_cannot_borrow_inline_output(sql):
    assert execute(sql) == execute(REFERENCE)  # Real local equality, not a semantic kill.
    result = structural_checks(TASK, sql)
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "output_consuming_cte_shape_unsupported"


def test_transitive_cte_dependency_and_case_insensitive_name():
    sql = REFERENCE.replace("WITH line_totals AS (", "WITH source AS (SELECT * FROM order_lines), Line_Totals AS (")
    sql = sql.replace("FROM order_lines GROUP", "FROM source GROUP")
    assert execute(sql) == execute(REFERENCE)
    assert structural_checks(TASK, sql)["status"] == "PASS"


@pytest.mark.parametrize("sql", [
    "WITH totals AS (SELECT SUM(CAST(quantity AS HUGEINT)*unit_price_cents) n FROM order_lines) SELECT * FROM totals UNION ALL SELECT * FROM totals WHERE FALSE",
    "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r WHERE n<2) SELECT * FROM r",
    "SELECT * FROM (WITH totals AS (SELECT SUM(CAST(quantity AS HUGEINT)*unit_price_cents) n FROM order_lines) SELECT * FROM totals) t",
    "WITH lines AS (SELECT order_id,CAST(quantity AS HUGEINT)*unit_price_cents AS product FROM order_lines), totals AS (SELECT order_id,SUM(product) total FROM lines GROUP BY order_id) SELECT * FROM totals",
], ids=["set_operation", "recursive", "nested_scope", "product_alias"])
def test_unsupported_valid_forms_are_inconclusive(sql):
    execute(sql)
    assert structural_checks(TASK, sql)["status"] == "INCONCLUSIVE"


def test_equivalent_product_alias_form_is_inconclusive_not_false_failure():
    sql = REFERENCE.replace(
        "WITH line_totals AS (",
        "WITH products AS (SELECT order_id,CAST(quantity AS HUGEINT)*unit_price_cents "
        "AS product FROM order_lines), line_totals AS (")
    sql = sql.replace("SUM(CAST(quantity AS HUGEINT) * unit_price_cents)", "SUM(product)")
    sql = sql.replace("FROM order_lines GROUP", "FROM products GROUP")
    assert execute(sql) == execute(REFERENCE)
    result = structural_checks(TASK, sql)
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "output_consuming_cte_shape_unsupported"


@pytest.mark.parametrize("sql", ["WITH broken AS (", "SELECT FROM", "SELECT 1; SELECT 2"])
def test_malformed_or_multiple_statements_are_inconclusive(sql):
    assert structural_checks(TASK, sql)["status"] == "INCONCLUSIVE"


def test_exact_contract_version_and_text_not_a_cte():
    for task in (SimpleNamespace(template_id=profile.CONTRACT, template_version=2),
                 SimpleNamespace(template_id="sql.temporal.clinic_weekly_visits", template_version=1)):
        assert structural_checks(task, REFERENCE) is None
    assert structural_checks(TASK, "SELECT 'WITH totals AS (SELECT 1)' AS note")["status"] == "FAIL"


def test_existing_throughput_and_delivery_routes_unchanged():
    task = SimpleNamespace(template_id="sql.aggregation.warehouse_throughput", template_version=2,
                           requirements={"min_total_units": 40})
    result = structural_checks(task, "SELECT warehouse,SUM(units) total_units FROM warehouse_loads GROUP BY warehouse HAVING SUM(units)>=40")
    assert result["status"] == "PASS"
    assert result["rule_id"] == "instruction:aggregate_having"
    from verified_data_factory.verification.qualification.delivery_profiles import get_profile

    task = SimpleNamespace(template_id="sql.joins.requested_language_titles", template_version=1)
    assert not get_profile(task.template_id, task.template_version).STRUCTURAL_KEYS
    assert structural_checks(task, "SELECT 1") is None
