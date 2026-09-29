"""Trusted harness test (host-side, no Docker).

Runs the REAL in-container harness entrypoint against FIXED, hardcoded
inputs only — never arbitrary model-generated SQL, never candidate data.
Validates harness file I/O, the DuckDB lockdown ordering, and probe
reporting on the project's DuckDB version. The execute path (candidate
SQL) is covered exclusively inside containers by integration tests.
"""

import json
from pathlib import Path

HARNESS = (
    Path(__file__).resolve().parents[1] / "src" / "verified_data_factory" / "sandbox" / "harness"
)


def _load_harness(monkeypatch, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("harness_run", HARNESS / "run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    monkeypatch.setenv("VDF_INPUT_DIR", str(input_dir))
    monkeypatch.setenv("VDF_OUTPUT_DIR", str(output_dir))
    spec.loader.exec_module(module)
    return module, input_dir, output_dir


def test_harness_probe_reports_lockdown(monkeypatch, tmp_path):
    module, input_dir, output_dir = _load_harness(monkeypatch, tmp_path)
    (input_dir / "fixture.json").write_text('{"schema": [], "tables": {}}', encoding="utf-8")
    (input_dir / "query.sql").write_text("SELECT 1;", encoding="utf-8")
    (input_dir / "run.json").write_text(
        json.dumps(
            {
                "action": "probe",
                "checks": {
                    "paths": [str(tmp_path / "definitely_absent")],
                    "duckdb_lockdown": {
                        "read_csv": "SELECT * FROM read_csv('/etc/passwd')",
                        "install": "INSTALL httpfs",
                        "load": "LOAD spatial",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    assert module.main() == 0
    payload = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["paths"] == {str(tmp_path / "definitely_absent"): False}
    for label, outcome in payload["duckdb_lockdown"].items():
        assert outcome.startswith("blocked"), (label, outcome)


def test_harness_structures_sql_errors(monkeypatch, tmp_path):
    module, input_dir, output_dir = _load_harness(monkeypatch, tmp_path)
    (input_dir / "fixture.json").write_text('{"schema": [], "tables": {}}', encoding="utf-8")
    (input_dir / "query.sql").write_text("SELECT * FROM missing_table;", encoding="utf-8")
    # NOTE: execute path on host is exercised ONLY with this fixed trusted
    # statement (no candidate/model input may ever reach this test).
    (input_dir / "run.json").write_text('{"max_result_rows": 10}', encoding="utf-8")
    assert module.main() == 0
    payload = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["status"] == "error"
    assert payload["error"]["message"]
