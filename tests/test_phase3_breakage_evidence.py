"""Phase 3 evidence must mutate the active oracle and name failing tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "engineering_oracle_breakages.py"


def test_phase3_breakage_evidence_uses_source_derived_mutants(tmp_path: Path) -> None:
    output = tmp_path / "breakage_table.json"
    subprocess.run([sys.executable, str(SCRIPT), "--contract", "saas", "--output", str(output)], cwd=ROOT, check=True)
    rows = json.loads(output.read_text(encoding="utf-8"))
    assert len(rows) == 6
    assert {row["classification"] for row in rows} == {"KILLED_WRONG_ANSWER"}
    assert all(row["pytest_exit_code"] == 1 for row in rows)
    assert all(row["named_failing_test"].startswith("tests/test_saas_funnel_oracle.py::") for row in rows)
    assert all(row["oracle_source_sha256"] != row["mutant_source_sha256"] for row in rows)
