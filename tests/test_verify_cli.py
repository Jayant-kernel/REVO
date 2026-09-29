"""CLI tests for `factory verify` (offline FAIL paths need no Docker)."""

import json


def _write_triple(tmp_path, status="EXECUTION_ERROR"):
    from tests.verify_sql_samples import CORRECT_SQL
    from tests.verify_testkit import make_candidate, make_execution, make_task, oracle_rows

    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns, status=status)
    task_path = tmp_path / "task.json"
    candidate_path = tmp_path / "candidate.json"
    execution_path = tmp_path / "execution.json"
    task_path.write_text(task.model_dump_json(by_alias=True), encoding="utf-8")
    candidate_path.write_text(candidate.model_dump_json(by_alias=True), encoding="utf-8")
    execution_path.write_text(execution.model_dump_json(by_alias=True), encoding="utf-8")
    return task_path, candidate_path, execution_path


def test_verify_one_fail_path_offline(tmp_path, capsys):
    from verified_data_factory.cli import main

    task_path, candidate_path, execution_path = _write_triple(tmp_path)
    out_path = tmp_path / "verdict.json"
    code = main(
        [
            "verify",
            "one",
            "--task",
            str(task_path),
            "--candidate",
            str(candidate_path),
            "--execution",
            str(execution_path),
            "--output",
            str(out_path),
        ]
    )
    assert code == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["verdict"] == "FAIL"
    assert data["failure_code"] == "EXECUTION_FAILED"


def test_verify_batch_manifest_offline(tmp_path):
    from verified_data_factory.cli import main

    task_path, candidate_path, execution_path = _write_triple(tmp_path)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "task": json.loads(task_path.read_text(encoding="utf-8")),
                "candidate": json.loads(candidate_path.read_text(encoding="utf-8")),
                "execution": json.loads(execution_path.read_text(encoding="utf-8")),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "out.jsonl"
    code = main(["verify", "batch", "--manifest", str(manifest), "--output", str(out_path)])
    assert code == 0
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["verdict"] == "FAIL"
