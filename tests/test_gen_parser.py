"""Parser tests: extraction matrix + deterministic ambiguity policy."""

from verified_data_factory.generation import extract_candidate_sql


def test_plain_sql():
    parsed = extract_candidate_sql("SELECT customer_id FROM customers;")
    assert parsed.status == "success"
    assert parsed.sql == "SELECT customer_id FROM customers"


def test_fenced_sql():
    parsed = extract_candidate_sql("```sql\nSELECT 1;\n```")
    assert parsed.status == "success"
    assert parsed.sql == "SELECT 1"


def test_fenced_sql_no_language_tag():
    parsed = extract_candidate_sql("```\nSELECT a FROM t\n```")
    assert parsed.status == "success"
    assert parsed.sql == "SELECT a FROM t"


def test_prose_plus_sql():
    parsed = extract_candidate_sql("Here is the query:\n\nSELECT a, b FROM t WHERE x > 1;")
    assert parsed.status == "success"
    assert parsed.sql == "SELECT a, b FROM t WHERE x > 1"


def test_leading_trailing_whitespace_and_case():
    parsed = extract_candidate_sql("  \n  with cte AS (SELECT 1 AS a) SELECT * FROM cte;  \n")
    assert parsed.status == "success"
    assert parsed.sql == "with cte AS (SELECT 1 AS a) SELECT * FROM cte"


def test_empty_response_fails():
    for raw in ("", "   ", "\n"):
        parsed = extract_candidate_sql(raw)
        assert parsed.status == "failed"
        assert parsed.sql is None
        assert parsed.failure_reason == "empty_response"


def test_non_sql_response_fails():
    parsed = extract_candidate_sql("I cannot answer that question.")
    assert parsed.status == "failed"
    assert parsed.sql is None


def test_multiple_blocks_fail_without_guessing():
    raw = "```sql\nSELECT 1;\n```\n\nAlternatively:\n\n```sql\nSELECT 2;\n```"
    parsed = extract_candidate_sql(raw)
    assert parsed.status == "failed"
    assert parsed.failure_reason == "ambiguous_multiple_blocks"
    assert parsed.sql is None


def test_fenced_non_sql_fails():
    parsed = extract_candidate_sql("```sql\nhello world\n```")
    assert parsed.status == "failed"
