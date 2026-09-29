"""SQL extraction from raw model responses (Phase 2).

The parser extracts; it never improves, rewrites, or judges SQL.
Deterministic ambiguity policy:

- exactly one fenced block      -> use it
- multiple fenced blocks        -> failed (ambiguous, never guess)
- no fence                      -> strip leading non-SQL prose, take the
  statement; must start with SELECT/WITH (case-insensitive)
- empty / non-SQL               -> failed
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from .models import ParseStatus

_FENCE_RE = re.compile(r"```(?:sql)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
_SQL_START_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


class ParsedSQL(BaseModel):
    model_config = {"frozen": True}

    status: ParseStatus
    sql: str | None = None
    failure_reason: str | None = None


def _normalize(candidate: str) -> str | None:
    text = candidate.strip().rstrip(";").strip()
    if not text or not _SQL_START_RE.match(text):
        return None
    return text


def extract_candidate_sql(raw_response: str) -> ParsedSQL:
    """Extract normalized SQL from a raw model response."""
    if not raw_response or not raw_response.strip():
        return ParsedSQL(status="failed", failure_reason="empty_response")
    fences = [m.group(1) for m in _FENCE_RE.finditer(raw_response)]
    if len(fences) > 1:
        return ParsedSQL(status="failed", failure_reason="ambiguous_multiple_blocks")
    if len(fences) == 1:
        sql = _normalize(fences[0])
        if sql is None:
            return ParsedSQL(status="failed", failure_reason="fenced_block_not_sql")
        return ParsedSQL(status="success", sql=sql)
    # No fence: drop leading prose lines until the SQL statement starts.
    lines = raw_response.strip().splitlines()
    start = next((i for i, line in enumerate(lines) if _SQL_START_RE.match(line)), None)
    if start is None:
        return ParsedSQL(status="failed", failure_reason="no_sql_found")
    sql = _normalize("\n".join(lines[start:]))
    if sql is None:
        return ParsedSQL(status="failed", failure_reason="no_sql_found")
    return ParsedSQL(status="success", sql=sql)
