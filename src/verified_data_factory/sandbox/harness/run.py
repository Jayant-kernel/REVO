"""In-container execution harness (Phase 3).

Runs INSIDE the disposable sandbox container as a non-root user. Reads
one JSON payload (never argv, never environment) and emits one bounded
result object. Only the Python standard library + DuckDB are used.

``--stdin`` mode (production): stdin carries
``{"fixture": {schema, tables}, "sql": ..., "run": {task_id,
max_result_rows, action?}}``; result JSON goes to stdout, the one-line
status ("OK"/"ERROR") to stderr.

File mode (default, dev/probe convenience): reads ``fixture.json``,
``query.sql``, ``run.json`` from the input dir and writes
``result.json``. Probe action (``{"action": "probe"}``) reports
environment facts without running candidates.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

INPUT_DIR = Path(os.environ.get("VDF_INPUT_DIR", "/work/input"))
OUTPUT_DIR = Path(os.environ.get("VDF_OUTPUT_DIR", "/work/output"))

LOCKDOWN_STATEMENTS = (
    "SET enable_external_access=false",
    "SET disabled_filesystems='LocalFileSystem'",
    "SET autoinstall_known_extensions=false",
    "SET autoload_known_extensions=false",
    "SET allow_unsigned_extensions=false",
)


def _duckdb() -> Any:
    import duckdb  # local import: keeps module importable without duckdb

    return duckdb


def _load_inputs() -> tuple[dict[str, Any], str, dict[str, Any]]:
    fixture = json.loads((INPUT_DIR / "fixture.json").read_text(encoding="utf-8"))
    sql = (INPUT_DIR / "query.sql").read_text(encoding="utf-8")
    run = json.loads((INPUT_DIR / "run.json").read_text(encoding="utf-8"))
    return fixture, sql, run


def _load_file_inputs() -> tuple[dict[str, Any], str, dict[str, Any]]:
    return _load_inputs()


def _connect() -> Any:
    con = _duckdb().connect(":memory:")
    for stmt in LOCKDOWN_STATEMENTS:
        con.execute(stmt)
    return con


def _create_tables(con: Any, fixture: dict[str, Any]) -> None:
    for table in fixture["schema"]:
        decls = []
        for c in table["columns"]:
            dtype = "DECIMAL(18, 2)" if c["type"] == "DECIMAL" else c["type"]
            decls.append(f'"{c["name"]}" {dtype}{"" if c.get("nullable", True) else " NOT NULL"}')
        con.execute(f'CREATE TABLE "{table["name"]}" ({", ".join(decls)})')
    for table in fixture["schema"]:
        rows = fixture["tables"][table["name"]]
        if not rows:
            continue
        names = [c["name"] for c in table["columns"]]
        placeholders = ", ".join(["?"] * len(names))
        col_list = ", ".join(f'"{c}"' for c in names)
        con.executemany(
            f'INSERT INTO "{table["name"]}" ({col_list}) VALUES ({placeholders})',
            [[r.get(c) for c in names] for r in rows],
        )


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def execute_candidate() -> dict[str, Any]:
    fixture, sql, run = _load_inputs()
    return execute_payload(fixture, sql, run)


def execute_payload(fixture: dict[str, Any], sql: str, run: dict[str, Any]) -> dict[str, Any]:
    con = _connect()
    _create_tables(con, fixture)
    limit = int(run.get("max_result_rows", 10000))
    cursor = con.execute(sql)
    columns = [{"name": d[0], "type": str(d[1])} for d in (cursor.description or [])]
    fetched = cursor.fetchmany(limit + 1)
    truncated = len(fetched) > limit
    rows = [[_to_jsonable(v) for v in row] for row in fetched[:limit]]
    con.close()
    return {
        "status": "ok",
        "duckdb_version": _duckdb().__version__,
        "columns": columns,
        "rows": rows,
        "rows_returned": len(rows),
        "truncated": truncated,
    }


def run_probe(checks: dict[str, Any]) -> dict[str, Any]:
    """Report isolation facts. Executes no candidate SQL."""
    paths = checks.get("paths", [])
    report: dict[str, Any] = {
        "status": "ok",
        "probe": True,
        "duckdb_version": _duckdb().__version__,
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "env_keys": sorted(os.environ.keys()),
        "paths": {p: Path(p).exists() for p in paths},
        "read_text": {},
    }
    for path, limit in (checks.get("read_text") or {}).items():
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            report["read_text"][path] = content[: int(limit)]
        except Exception as exc:  # noqa: BLE001 — unreadable probe files are data
            report["read_text"][path] = f"unreadable: {type(exc).__name__}"
    if checks.get("duckdb_lockdown"):
        con = _connect()
        findings: dict[str, str] = {}
        for label, sql in checks["duckdb_lockdown"].items():
            try:
                con.execute(sql)
                findings[label] = "ran"
            except Exception as exc:  # noqa: BLE001 — probe records the block, any kind
                findings[label] = f"blocked: {type(exc).__name__}"
        con.close()
        report["duckdb_lockdown"] = findings
    return report


def main() -> int:
    stdin_mode = "--stdin" in sys.argv[1:]
    try:
        if stdin_mode:
            envelope = json.loads(sys.stdin.read())
            fixture, sql, run = envelope["fixture"], envelope["sql"], envelope.get("run", {})
        else:
            fixture, sql, run = _load_file_inputs()
        if run.get("action") == "probe":
            payload = run_probe(run.get("checks", {}))
        else:
            payload = execute_payload(fixture, sql, run)
    except Exception as exc:  # noqa: BLE001 — SQL/input errors become structured data
        try:
            version = _duckdb().__version__
        except Exception:  # noqa: BLE001 — version best-effort only
            version = "unknown"
        payload = {
            "status": "error",
            "duckdb_version": version,
            "error": {"type": type(exc).__name__, "message": str(exc)[:2000]},
        }
    blob = json.dumps(payload, default=str)
    if stdin_mode:
        sys.stdout.write(blob)
        print("OK" if payload.get("status") == "ok" else "ERROR", file=sys.stderr)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "result.json").write_text(blob, encoding="utf-8")
        print("OK" if payload.get("status") == "ok" else "ERROR")
    return 0


if __name__ == "__main__":
    sys.exit(main())
