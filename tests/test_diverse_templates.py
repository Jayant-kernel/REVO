"""New domains must have real fixture boundaries and independent oracle agreement."""

from __future__ import annotations

from datetime import datetime

import pytest

from verified_data_factory.quality.task_quality import assess_task_quality, known_edge_cases
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.task_engine.validation import validate_task
from verified_data_factory.verification.adversarial import independent_adversarial_tables
from verified_data_factory.verification.metamorphic import TEMPLATE_RELATION_OVERRIDES
from verified_data_factory.verification.mutations import applicable_operators
from verified_data_factory.verification.oracle_registry import get_oracle

SAAS_SQL = """
SELECT i.invoice_id, a.account_name, i.amount_cents
FROM invoices AS i INNER JOIN accounts AS a ON i.account_id = a.account_id
WHERE i.invoice_status = 'paid' AND a.account_status = 'active'
  AND i.issued_on >= DATE '2025-01-01' AND i.issued_on < DATE '2026-01-01'
ORDER BY i.invoice_id ASC
"""

PAYMENTS_SQL = """
SELECT merchant_id, SUM(amount_cents) AS net_settled_cents
FROM payment_entries
WHERE entry_status = 'posted' AND entry_kind IN ('settlement', 'reversal')
  AND posted_on >= DATE '2025-01-01' AND posted_on < DATE '2026-01-01'
GROUP BY merchant_id ORDER BY merchant_id ASC
"""

SUPPORT_SQL = """
SELECT team, priority, COUNT(*) AS breach_count
FROM support_tickets
WHERE opened_at >= TIMESTAMP '2025-01-01 00:00:00'
  AND opened_at < TIMESTAMP '2026-01-01 00:00:00'
  AND resolved_at IS NOT NULL AND resolved_at > due_at
GROUP BY team, priority
ORDER BY team ASC, priority ASC
"""

EDUCATION_SQL = """
SELECT student_id, course_id, grade, recorded_at, revision_id
FROM grade_revisions
WHERE revision_status = 'valid'
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY student_id, course_id
  ORDER BY recorded_at DESC, revision_id DESC
) = 1
ORDER BY student_id ASC, course_id ASC
"""


@pytest.mark.parametrize(
    ("template_id", "sql"),
    [
        ("sql.joins.saas_paid_invoices", SAAS_SQL),
        ("sql.aggregation.payment_net_settled", PAYMENTS_SQL),
        ("sql.aggregation.support_sla_breaches", SUPPORT_SQL),
        ("sql.dedup.education_grade_revisions", EDUCATION_SQL),
    ],
)
@pytest.mark.parametrize("seed", [1, 94001, 99999])
def test_generated_domains_match_independent_oracles(template_id, sql, seed):
    template = load_builtin_registry().get(template_id)
    task = generate_task(template, seed)
    assert set(task.edge_cases) == set(template.edge_cases)
    expected = get_oracle(template_id, 1).fn(task.requirements, task.tables)
    con = materialize_duckdb(task.schema_, task.tables)
    try:
        actual = [list(row) for row in con.execute(sql).fetchall()]
    finally:
        con.close()
    assert len(actual) == len(expected.rows)
    for got, wanted in zip(actual, expected.rows, strict=True):
        actual = [str(value) if isinstance(value, datetime) else value for value in got]
        assert actual == pytest.approx(wanted)


def test_saas_adversarial_fixture_excludes_inactive_unpaid_and_other_years():
    task = generate_task(load_builtin_registry().get("sql.joins.saas_paid_invoices"), 7)
    tables = {
        "accounts": [
            {"account_id": 1, "account_name": "Active", "account_status": "active"},
            {"account_id": 2, "account_name": "Suspended", "account_status": "suspended"},
            {"account_id": 3, "account_name": "No invoice", "account_status": "active"},
        ],
        "invoices": [
            {
                "invoice_id": 1,
                "account_id": 1,
                "issued_on": "2025-01-01",
                "amount_cents": 0,
                "invoice_status": "paid",
            },
            {
                "invoice_id": 2,
                "account_id": 2,
                "issued_on": "2025-02-01",
                "amount_cents": 90_000,
                "invoice_status": "paid",
            },
            {
                "invoice_id": 3,
                "account_id": 1,
                "issued_on": "2025-02-02",
                "amount_cents": 80_000,
                "invoice_status": "open",
            },
            {
                "invoice_id": 4,
                "account_id": 1,
                "issued_on": "2024-12-31",
                "amount_cents": 70_000,
                "invoice_status": "paid",
            },
            {
                "invoice_id": 5,
                "account_id": 1,
                "issued_on": "2026-01-01",
                "amount_cents": 60_000,
                "invoice_status": "paid",
            },
        ],
    }
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
    assert expected.rows == [[1, "Active", 0]]
    con = materialize_duckdb(task.schema_, tables)
    try:
        assert [list(row) for row in con.execute(SAAS_SQL).fetchall()] == expected.rows
        wrong = "SELECT i.invoice_id FROM invoices i WHERE i.invoice_status = 'paid' ORDER BY 1"
        assert len(con.execute(wrong).fetchall()) > len(expected.rows)
    finally:
        con.close()


def test_payments_adversarial_fixture_catches_missing_reversal_and_status_filters():
    task = generate_task(load_builtin_registry().get("sql.aggregation.payment_net_settled"), 11)
    tables = {
        "payment_entries": [
            {
                "entry_id": 1,
                "merchant_id": 1,
                "posted_on": "2025-01-01",
                "entry_kind": "settlement",
                "entry_status": "posted",
                "amount_cents": 10_000,
            },
            {
                "entry_id": 2,
                "merchant_id": 1,
                "posted_on": "2025-01-02",
                "entry_kind": "reversal",
                "entry_status": "posted",
                "amount_cents": -10_000,
            },
            {
                "entry_id": 3,
                "merchant_id": 2,
                "posted_on": "2025-07-01",
                "entry_kind": "settlement",
                "entry_status": "failed",
                "amount_cents": 50_000,
            },
            {
                "entry_id": 4,
                "merchant_id": 2,
                "posted_on": "2024-12-31",
                "entry_kind": "settlement",
                "entry_status": "posted",
                "amount_cents": 70_000,
            },
            {
                "entry_id": 5,
                "merchant_id": 3,
                "posted_on": "2025-07-02",
                "entry_kind": "adjustment",
                "entry_status": "posted",
                "amount_cents": 30_000,
            },
        ]
    }
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
    assert expected.rows == [[1, 0]]
    con = materialize_duckdb(task.schema_, tables)
    try:
        assert [list(row) for row in con.execute(PAYMENTS_SQL).fetchall()] == expected.rows
        wrong = "SELECT merchant_id, SUM(amount_cents) FROM payment_entries WHERE entry_kind = 'settlement' GROUP BY merchant_id"
        assert con.execute(wrong).fetchall() != [(1, 0)]
    finally:
        con.close()


def test_support_adversarial_fixture_catches_deadline_and_year_errors():
    task = generate_task(load_builtin_registry().get("sql.aggregation.support_sla_breaches"), 17)
    tables = independent_adversarial_tables(task)
    assert tables is not None
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
    assert expected.rows == [["Accounts", "high", 2], ["Payments", "normal", 1]]
    con = materialize_duckdb(task.schema_, tables)
    try:
        assert [list(row) for row in con.execute(SUPPORT_SQL).fetchall()] == expected.rows
        wrong_deadline = SUPPORT_SQL.replace("resolved_at > due_at", "resolved_at >= due_at")
        wrong_year = SUPPORT_SQL.replace(
            "opened_at >= TIMESTAMP '2025-01-01 00:00:00'",
            "opened_at >= TIMESTAMP '2024-01-01 00:00:00'",
        )
        assert [list(row) for row in con.execute(wrong_deadline).fetchall()] != expected.rows
        assert [list(row) for row in con.execute(wrong_year).fetchall()] != expected.rows
    finally:
        con.close()


def test_education_adversarial_fixture_catches_cancellation_and_ties():
    task = generate_task(load_builtin_registry().get("sql.dedup.education_grade_revisions"), 17)
    tables = independent_adversarial_tables(task)
    assert tables is not None
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
    assert expected.rows == [
        [1, 10, "A+", "2025-02-01 10:00:00", 4],
        [1, 20, "B+", "2025-05-01 10:00:00", 6],
        [3, 30, "C", "2025-06-01 10:00:00", 7],
    ]
    con = materialize_duckdb(task.schema_, tables)
    try:
        actual = [
            [str(value) if isinstance(value, datetime) else value for value in row]
            for row in con.execute(EDUCATION_SQL).fetchall()
        ]
        assert actual == expected.rows
        for wrong_sql in (
            EDUCATION_SQL.replace("WHERE revision_status = 'valid'", ""),
            EDUCATION_SQL.replace("recorded_at DESC", "recorded_at ASC"),
            EDUCATION_SQL.replace("revision_id DESC", "revision_id ASC"),
        ):
            wrong = con.execute(wrong_sql).fetchall()
            assert wrong != con.execute(EDUCATION_SQL).fetchall()
    finally:
        con.close()


def test_saas_fk_validation_and_metamorphic_override():
    task = generate_task(load_builtin_registry().get("sql.joins.saas_paid_invoices"), 17)
    changed = task.model_copy(deep=True)
    changed.tables["invoices"][0]["account_id"] = 999999
    with pytest.raises(Exception, match="has no account"):
        validate_task(changed)
    names = [fn.__name__ for fn in TEMPLATE_RELATION_OVERRIDES[task.template_id]]
    assert names == ["relate_row_permutation", "relate_add_irrelevant_account"]


def test_release_edge_taxonomy_remains_frozen_with_new_domain_checks():
    registry = load_builtin_registry()
    assert len(known_edge_cases()) == 17
    saas = generate_task(registry.get("sql.joins.saas_paid_invoices"), 17)
    payments = generate_task(registry.get("sql.aggregation.payment_net_settled"), 17)
    saas_evidence = assess_task_quality(saas)
    payment_evidence = assess_task_quality(payments)
    assert "missing_relationships" in saas_evidence.edge_cases_present
    assert "negative_values" in payment_evidence.edge_cases_present
    assert "account_without_invoices" not in saas_evidence.edge_cases_present
    assert "payment_reversal" not in payment_evidence.edge_cases_present
    assert 0 <= saas_evidence.edge_case_coverage_rate <= 1
    assert 0 <= payment_evidence.edge_case_coverage_rate <= 1


@pytest.mark.parametrize(
    ("template_id", "sql"),
    [
        ("sql.joins.saas_paid_invoices", SAAS_SQL),
        ("sql.aggregation.payment_net_settled", PAYMENTS_SQL),
        ("sql.aggregation.support_sla_breaches", SUPPORT_SQL),
        ("sql.dedup.education_grade_revisions", EDUCATION_SQL),
    ],
)
def test_generated_fixtures_kill_applicable_sql_mutants(template_id, sql):
    task = generate_task(load_builtin_registry().get(template_id), 94001)
    operators = applicable_operators(task, sql, 20)
    assert len(operators) >= 3
    con = materialize_duckdb(task.schema_, task.tables)
    try:
        correct = con.execute(sql).fetchall()
        for operator in operators:
            mutated = operator.apply(task, sql)
            assert mutated is not None
            mutant_rows = con.execute(mutated).fetchall()
            assert mutant_rows != correct, operator.name
    finally:
        con.close()
