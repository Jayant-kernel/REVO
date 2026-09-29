"""SQL policy tests: classification without brittle blacklists."""

from verified_data_factory.sandbox import check_policy, classify_statement, split_statements


def test_select_and_with_allowed():
    assert check_policy("SELECT a FROM t;").allowed
    assert check_policy("WITH x AS (SELECT 1) SELECT * FROM x").allowed


def test_multi_statement_rejected():
    decision = check_policy("SELECT 1; DROP TABLE t;")
    assert not decision.allowed
    assert decision.reason == "MULTIPLE_STATEMENTS"


def test_semicolon_inside_string_is_single_statement():
    assert check_policy("SELECT 'a;b' AS x;").allowed
    assert len(split_statements("SELECT 'a;b' AS x;")) == 1


def test_semicolon_inside_comment_is_single_statement():
    assert check_policy("SELECT 1 -- trailing; comment\n").allowed


def test_dangerous_single_statements_rejected():
    for sql, kind in [
        ("DROP TABLE t", "DROP"),
        ("INSTALL httpfs", "INSTALL"),
        ("LOAD spatial", "LOAD"),
        ("ATTACH 'f.db' AS x", "ATTACH"),
        ("COPY t TO 'f.csv'", "COPY"),
        ("PRAGMA memory_limit='1GB'", "PRAGMA"),
        ("INSERT INTO t VALUES (1)", "INSERT"),
        ("DELETE FROM t", "DELETE"),
        ("CREATE TABLE t (a INT)", "CREATE"),
    ]:
        decision = check_policy(sql)
        assert not decision.allowed, sql
        assert decision.reason == "DISALLOWED_STATEMENT", sql
        assert decision.statement_kind == kind, sql


def test_non_query_rejected():
    decision = check_policy("EXPLAIN SELECT 1")
    assert not decision.allowed
    assert decision.reason == "NON_QUERY_STATEMENT"


def test_empty_rejected():
    assert check_policy("").reason == "EMPTY_STATEMENT"
    assert check_policy("   ;  ").reason == "EMPTY_STATEMENT"


def test_quoted_keyword_not_misclassified():
    # 'install' inside a string literal must not change classification.
    decision = check_policy("SELECT 'install' AS note;")
    assert decision.allowed
    assert classify_statement("  select 1") == "SELECT"
