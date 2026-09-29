"""Deterministic duplicate detection (Phase 5).

Three staged levels — cheap fingerprints first, never O(n^2), never
embeddings as the basis. Duplicates are RECORDED with group ids and a
deterministic representative (smallest candidate_id); nothing is deleted.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .models import DuplicateGroup, DuplicateReport, DuplicateType, RecordQuality

_SQL_KEYWORDS = (
    "SELECT",
    "FROM",
    "WHERE",
    "GROUP",
    "BY",
    "HAVING",
    "ORDER",
    "LIMIT",
    "OFFSET",
    "JOIN",
    "INNER",
    "LEFT",
    "RIGHT",
    "FULL",
    "OUTER",
    "CROSS",
    "ON",
    "USING",
    "WITH",
    "RECURSIVE",
    "AS",
    "UNION",
    "ALL",
    "DISTINCT",
    "EXISTS",
    "IN",
    "BETWEEN",
    "LIKE",
    "AND",
    "OR",
    "NOT",
    "NULL",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "ASC",
    "DESC",
    "OVER",
    "PARTITION",
    "ROWS",
    "RANGE",
    "UNBOUNDED",
    "PRECEDING",
    "FOLLOWING",
    "CURRENT",
    "ROW",
    "VALUES",
    "TABLE",
    "SUM",
    "AVG",
    "COUNT",
    "MIN",
    "MAX",
    "DATE",
    "INTERVAL",
    "STRFTIME",
    "DATE_TRUNC",
    "EXTRACT",
    "ROW_NUMBER",
    "RANK",
    "LAG",
    "LEAD",
    "FIRST",
    "LAST",
    "COALESCE",
    "CAST",
    "TRIM",
    "UPPER",
    "LOWER",
    "LENGTH",
    "ROUND",
    "ABS",
)


def normalize_sql(sql: str) -> str:
    """Canonical SQL form: comments/strings/numbers abstracted, case folded.

    Keywords fold even when glued to punctuation (``sum(`` vs ``SUM(``);
    a token lookup would miss those. Identifiers, literals, and numbers
    keep their shape apart from abstraction.
    """
    text = re.sub(r"--[^\n]*", " ", sql)
    text = re.sub(r"/\*[\s\S]*?\*/", " ", text)
    text = re.sub(r"'(?:[^'\\]|\\.)*'", "'?'", text)
    text = re.sub(r"\b\d+(\.\d+)?\b", "#", text)
    for keyword in sorted(_SQL_KEYWORDS, key=len, reverse=True):
        text = re.sub(rf"\b{keyword}\b", keyword, text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip().rstrip(";").strip()


def sql_fingerprint(sql: str) -> str:
    return hashlib.sha256(normalize_sql(sql).encode()).hexdigest()[:16]


def task_fingerprint(task_id: str, canonical_task_json: str) -> str:
    return hashlib.sha256(f"{task_id}\n{canonical_task_json}".encode()).hexdigest()[:16]


def schema_fingerprint(schema: list[dict[str, Any]]) -> str:
    parts = []
    for table in sorted(schema, key=lambda t: t.get("name", "")):
        cols = ",".join(
            f"{c.get('name')}:{c.get('type')}"
            for c in sorted(table.get("columns", []), key=lambda c: c.get("name", ""))
        )
        parts.append(f"{table.get('name')}({cols})")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def semantic_key(
    family: str, schema_fp: str, sql: str, fixture_counts: str, edge_cases: str
) -> str:
    operators = ",".join(sorted(_operator_signature(sql)))
    raw = f"{family}|{schema_fp}|{operators}|{fixture_counts}|{edge_cases}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _operator_signature(sql: str) -> set[str]:
    normalized = f" {normalize_sql(sql)} "
    signatures = {
        "select": r"\bSELECT\b",
        "join": r"\bJOIN\b",
        "group-by": r"\bGROUP\s+BY\b",
        "having": r"\bHAVING\b",
        "cte": r"\bWITH\b",
        "subquery": r"\(\s*SELECT\b",
        "window": r"\bOVER\b|\bRANK\s*\(|\bROW_NUMBER\s*\(|\bLAG\s*\(|\bLEAD\s*\(",
        "case": r"\bCASE\b",
        "exists": r"\bEXISTS\b",
        "date-fn": r"\bDATE\s*\(|STRFTIME|INTERVAL|DATE_TRUNC",
        "aggregation": r"\bSUM\s*\(|\bAVG\s*\(|\bCOUNT\s*\(|\bMIN\s*\(|\bMAX\s*\(",
        "order-by": r"\bORDER\s+BY\b",
        "distinct": r"\bDISTINCT\b",
        "union": r"\bUNION\b",
        "limit": r"\bLIMIT\b",
    }
    return {name for name, pattern in signatures.items() if re.search(pattern, normalized)}


def _group_ids(members: list[str], level: str) -> str:
    digest = hashlib.sha256("\n".join(sorted(members)).encode()).hexdigest()[:12]
    return f"dup-{level}-{digest}"


def detect_duplicates(
    qualities: list[RecordQuality],
    candidate_sql: dict[str, str],
    canonical_tasks: dict[str, str],
    schemas: dict[str, list[dict[str, Any]]],
    fixture_counts: dict[str, str],
) -> DuplicateReport:
    """Group records at exact/structural/semantic levels (hash-indexed).

    Side inputs keyed by candidate_id: raw SQL, canonical task JSON, schema,
    and fixture row counts. Returns groups; representatives are the
    smallest candidate_id per group.
    """
    groups: list[DuplicateGroup] = []
    levels: list[tuple[DuplicateType, Any]] = [
        (
            "EXACT",
            lambda q: (
                task_fingerprint(q.task_id, canonical_tasks[q.candidate_id])
                + "|"
                + (candidate_sql[q.candidate_id].strip())
            ),
        ),
        (
            "STRUCTURAL",
            lambda q: (
                task_fingerprint(q.task_id, canonical_tasks[q.candidate_id])
                + "|"
                + sql_fingerprint(candidate_sql[q.candidate_id])
            ),
        ),
        (
            "SEMANTIC",
            lambda q: semantic_key(
                q.family,
                schema_fingerprint(schemas[q.candidate_id]),
                candidate_sql[q.candidate_id],
                fixture_counts[q.candidate_id],
                ",".join(sorted(_edge_cases_of(q))),
            ),
        ),
    ]
    for level, key_fn in levels:
        buckets: dict[str, list[str]] = {}
        for quality in qualities:
            buckets.setdefault(key_fn(quality), []).append(quality.candidate_id)
        for members in buckets.values():
            if len(members) > 1:
                groups.append(
                    DuplicateGroup(
                        group_id=_group_ids(members, level.lower()),
                        duplicate_type=level,
                        member_ids=sorted(members),
                        representative_id=min(members),
                    )
                )
    groups.sort(key=lambda g: g.group_id)
    return DuplicateReport(groups=groups)


def _edge_cases_of(quality: RecordQuality) -> list[str]:
    return list(quality.task_quality.edge_cases_present)
