"""SQL policy layer (Phase 3).

Defense in depth ONLY — never the primary boundary (that is the disposable
container plus DuckDB-level locks). No giant regex blacklist: input is
tokenized (strings/comments stripped) before classification, and anything
unrecognized is rejected.

Machine-readable rejection reasons: ``MULTIPLE_STATEMENTS``,
``NON_QUERY_STATEMENT``, ``DISALLOWED_STATEMENT``.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

QUERY_KINDS = frozenset({"SELECT", "WITH", "VALUES", "TABLE"})

DISALLOWED_KINDS = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "CREATE",
        "DROP",
        "ALTER",
        "ATTACH",
        "DETACH",
        "COPY",
        "INSTALL",
        "LOAD",
        "PRAGMA",
        "CALL",
        "EXECUTE",
        "GRANT",
        "REVOKE",
        "TRUNCATE",
        "VACUUM",
        "ANALYZE",
        "CHECKPOINT",
        "EXPORT",
        "IMPORT",
        "PIVOT",
        "UNPIVOT",
    }
)


class PolicyDecision(BaseModel):
    model_config = {"frozen": True}

    allowed: bool
    reason: str | None = None
    statement_kind: str = "UNKNOWN"


def _strip_strings_and_comments(sql: str) -> str:
    """Remove quoted literals/identifiers and comments for classification."""
    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":
            while i < n and sql[i] != "\n":
                i += 1
        elif ch == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2
        elif ch in ("'", '"', "`"):
            quote = ch
            i += 1
            while i < n and sql[i] != quote:
                if sql[i] == "\\":
                    i += 1
                i += 1
            i += 1
            out.append("?")  # placeholder keeps token positions sane
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def split_statements(sql: str) -> list[str]:
    """Split on semicolons outside strings/comments; trailing empties dropped."""
    cleaned = _strip_strings_and_comments(sql)
    parts = [part.strip() for part in cleaned.split(";")]
    return [part for part in parts if part]


def classify_statement(statement: str) -> str:
    """Leading keyword of one statement (strings/comments already stripped)."""
    match = re.match(r"\s*([A-Za-z]+)", statement)
    if not match:
        return "UNKNOWN"
    return match.group(1).upper()


def check_policy(sql: str, single_statement_only: bool = True) -> PolicyDecision:
    """Classify candidate SQL against the sandbox execution policy."""
    if not sql or not sql.strip():
        return PolicyDecision(allowed=False, reason="EMPTY_STATEMENT")
    statements = split_statements(sql)
    if not statements:
        return PolicyDecision(allowed=False, reason="EMPTY_STATEMENT")
    if single_statement_only and len(statements) > 1:
        return PolicyDecision(allowed=False, reason="MULTIPLE_STATEMENTS")
    kinds = [classify_statement(s) for s in statements]
    for kind in kinds:
        if kind in DISALLOWED_KINDS:
            return PolicyDecision(allowed=False, reason="DISALLOWED_STATEMENT", statement_kind=kind)
    if kinds[0] not in QUERY_KINDS:
        return PolicyDecision(allowed=False, reason="NON_QUERY_STATEMENT", statement_kind=kinds[0])
    return PolicyDecision(allowed=True, statement_kind=kinds[0])
