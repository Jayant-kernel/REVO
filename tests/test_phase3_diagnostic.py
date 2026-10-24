from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs" / "premium-qualification-080"
SCRIPT = ROOT / "scripts" / "phase3_diagnostic.py"


def _run_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(RUN.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(RUN).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_phase3_diagnostic_reconciles_and_preserves_run(tmp_path: Path) -> None:
    before = _run_hash()
    first = tmp_path / "first"
    second = tmp_path / "second"
    for output in (first, second):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--run", str(RUN), "--output-dir", str(output)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert '"run_files_unchanged": true' in result.stdout
    assert before == _run_hash()
    first_json = (first / "phase3-diagnostic-20261002.json").read_bytes()
    second_json = (second / "phase3-diagnostic-20261002.json").read_bytes()
    first_markdown = (first / "phase3-diagnostic-20261002.md").read_bytes()
    second_markdown = (second / "phase3-diagnostic-20261002.md").read_bytes()
    assert hashlib.sha256(first_json).digest() == hashlib.sha256(second_json).digest()
    assert hashlib.sha256(first_markdown).digest() == hashlib.sha256(second_markdown).digest()
    assert b'"all_expected_totals_match": true' in first_json
    report = json.loads(first_json)
    readiness = report["contract_readiness"]
    assert readiness["columns"] == [
        "template_validates",
        "fixture_generator",
        "independent_oracle",
        "registry_entry",
        "adversarial_case",
        "reference_sql_mapping",
        "mutation_applicability",
        "focused_test",
    ]
    assert readiness["unknown_reference_sql"] == []
    resolved = {
        "sql.aggregation.payment_net_settled",
        "sql.aggregation.support_sla_breaches",
        "sql.dedup.education_grade_revisions",
        "sql.joins.saas_paid_invoices",
    }
    assert all(
        row["fully_verified"]
        for row in readiness["rows"]
        if row["template_id"] in resolved
    )
    assert all(
        set(row["checks"]) == set(readiness["columns"])
        and all("source" in check for check in row["checks"].values())
        for row in readiness["rows"]
    )
    assert report["funnel_label_audit"]["representative_candidate_diffs"]
    assert len(report["funnel_label_audit"]["hidden_mismatch_inspections"]) == 2
    assert all(
        row["label"] == "unknown"
        for row in report["funnel_label_audit"]["hidden_mismatch_inspections"]
    )
    assert report["task_survival"]["by_family"]
    assert report["run_files_unchanged"]
    assert report["source_hashes_before"] == report["source_hashes_after"]
