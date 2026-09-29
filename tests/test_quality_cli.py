"""CLI tests for `factory quality` (offline, fixture-backed)."""

import json


def _write_records(tmp_path):
    from tests.quality_dataset import build_fixture_dataset

    path = tmp_path / "records.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for record in build_fixture_dataset():
            fh.write(
                json.dumps(
                    {
                        "task": record.task.model_dump(mode="json", by_alias=True),
                        "candidate": record.candidate.model_dump(mode="json", by_alias=True),
                        "execution": record.execution.model_dump(mode="json", by_alias=True),
                        "verification": record.verification.model_dump(mode="json"),
                        "role": record.role,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    return path


def test_quality_dataset_and_golden_cli(tmp_path, capsys):
    from verified_data_factory.cli import main

    records = _write_records(tmp_path)
    assert main(["quality", "dataset", "--input", str(records)]) == 0
    out = tmp_path / "golden.txt"
    assert main(["quality", "golden", "--input", str(records), "--output", str(out)]) == 0
    golden = out.read_text(encoding="utf-8").strip().splitlines()
    assert golden, "fixture dataset must yield golden records"
    assert golden == sorted(golden)


def test_quality_duplicates_coverage_health_cli(tmp_path, capsys):
    from verified_data_factory.cli import main

    records = _write_records(tmp_path)
    assert main(["quality", "duplicates", "--input", str(records)]) == 0
    assert main(["quality", "coverage", "--input", str(records)]) == 0
    assert main(["quality", "health", "--input", str(records)]) == 0
    captured = capsys.readouterr().out
    assert "EXACT" in captured or "no duplicate groups" in captured


def test_quality_record_and_audit_cli(tmp_path):
    from verified_data_factory.cli import main

    records = _write_records(tmp_path)
    out = tmp_path / "qualities.json"
    assert main(["quality", "record", "--input", str(records), "--output", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload) == 13
    sample_out = tmp_path / "audit.json"
    assert main(["quality", "audit", "--input", str(records), "--output", str(sample_out)]) == 0
    sample = json.loads(sample_out.read_text(encoding="utf-8"))
    assert sample
    first_id = sample[0]["candidate_id"]
    assert (
        main(
            [
                "quality",
                "audit",
                "--input",
                str(records),
                "--output",
                str(sample_out),
                "--record-id",
                first_id,
                "--result",
                "PASS",
                "--note",
                "cli-test",
            ]
        )
        == 0
    )
    updated = json.loads(sample_out.read_text(encoding="utf-8"))
    assert next(i for i in updated if i["candidate_id"] == first_id)["result"] == "PASS"
