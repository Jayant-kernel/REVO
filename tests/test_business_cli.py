"""Business CLI tests (Phase 8): benchmark → experiment → economics → customer → claims → report."""

import json

from tests.business_fixtures import (
    baseline_outcomes,
    benchmark_items,
    control_outcomes,
    treatment_outcomes,
)
from verified_data_factory.cli import build_parser


def _run(argv):
    return build_parser().parse_args(argv).func(build_parser().parse_args(argv))


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _outcome_dicts(outcomes):
    return [o.model_dump(mode="json") for o in outcomes]


def test_cli_benchmark_lifecycle(tmp_path, capsys):
    items_path = tmp_path / "items.jsonl"
    _write_jsonl(items_path, [i.model_dump(mode="json") for i in benchmark_items()])
    bench_path = tmp_path / "bench.json"
    assert (
        _run(
            [
                "business",
                "benchmark",
                "create",
                "--items",
                str(items_path),
                "--freeze",
                "--output",
                str(bench_path),
            ]
        )
        == 0
    )
    assert (
        _run(
            [
                "business",
                "benchmark",
                "validate",
                "--benchmark",
                str(bench_path),
                "--items",
                str(items_path),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "benchmark=sha256:" in out


def test_cli_experiment_run_compare(tmp_path):
    outcomes_dir = tmp_path / "outcomes"
    outcomes_dir.mkdir()
    for arm, outcomes in (
        ("baseline", baseline_outcomes()),
        ("control", control_outcomes()),
        ("treatment", treatment_outcomes()),
    ):
        _write_jsonl(outcomes_dir / f"{arm}.jsonl", _outcome_dicts(outcomes))
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "experiment_id": "exp-cli",
                "experiment_version": "1.0",
                "benchmark_id": "bench-cli",
                "baseline": {"model": "m", "adaptation_method": "NONE"},
                "treatment": {"model": "m", "adaptation_method": "SFT"},
                "seeds": [42],
                "scoring_method": "s",
            }
        ),
        encoding="utf-8",
    )
    result_path = tmp_path / "result.json"
    assert (
        _run(
            [
                "business",
                "experiment",
                "run",
                "--config",
                str(config_path),
                "--outcomes",
                str(outcomes_dir),
                "--run-id",
                "run-cli",
                "--output",
                str(result_path),
                "--threshold-pp",
                "5.0",
                "--min-n",
                "10",
            ]
        )
        == 0
    )
    assert (
        _run(
            [
                "business",
                "compare",
                "--result",
                str(result_path),
                "--threshold-pp",
                "5.0",
                "--min-n",
                "10",
            ]
        )
        == 0
    )


def test_cli_economics_customer_pilot_claims_report(tmp_path, capsys):
    costs_path = tmp_path / "costs.json"
    costs_path.write_text(
        json.dumps({"variable_costs": {"inference": 10.0}, "fixed_costs": {}, "measured": False}),
        encoding="utf-8",
    )
    assert (
        _run(["business", "economics", "--costs", str(costs_path), "--golden-records", "10"]) == 0
    )

    cust_in = tmp_path / "cust.json"
    cust_in.write_text(
        json.dumps(
            {
                "validation_id": "v-cli",
                "organization": "CLI Labs",
                "segment": "s",
                "feedback": "PRODUCT_USEFUL",
                "willingness_signal": "DATASET_TESTED",
                "evidence_type": "USER_REPORTED",
                "evidence_reference": "n/1",
            }
        ),
        encoding="utf-8",
    )
    cust_out = tmp_path / "cust-out.json"
    assert (
        _run(["business", "customer", "record", "--input", str(cust_in), "--output", str(cust_out)])
        == 0
    )

    pilot_in = tmp_path / "pilot.json"
    pilot_in.write_text(
        json.dumps(
            {
                "pilot_id": "p-cli",
                "product_release_id": "sha256:" + "ab" * 32,
                "customer_segment": "s",
            }
        ),
        encoding="utf-8",
    )
    pilot_out = tmp_path / "pilot-out.json"
    assert (
        _run(["business", "pilot", "create", "--input", str(pilot_in), "--output", str(pilot_out)])
        == 0
    )
    pilot_active = tmp_path / "pilot-active.json"
    assert (
        _run(
            [
                "business",
                "pilot",
                "transition",
                "--pilot",
                str(pilot_out),
                "--status",
                "ACTIVE",
                "--output",
                str(pilot_active),
            ]
        )
        == 0
    )

    claims_path = tmp_path / "claims.json"
    claims_path.write_text(
        json.dumps([{"claim_id": "c", "statement": "H.", "evidence_ids": []}]), encoding="utf-8"
    )
    evidence_path = tmp_path / "ev.json"
    evidence_path.write_text("[]", encoding="utf-8")
    # No linked evidence: unsupported.
    assert (
        _run(
            [
                "business",
                "claims",
                "validate",
                "--claims",
                str(claims_path),
                "--evidence",
                str(evidence_path),
            ]
        )
        == 1
    )


def test_cli_report_and_export(tmp_path):
    report_dir = tmp_path / "report"
    assert (
        _run(
            [
                "business",
                "report",
                "--report-id",
                "r-cli",
                "--out-dir",
                str(report_dir),
                "--hypothesis-verdict",
                "INSUFFICIENT_EVIDENCE",
                "--hypothesis-detail",
                "no experiments yet",
            ]
        )
        == 0
    )
    assert (report_dir / "business_report.json").exists()
    assert (report_dir / "business_report.csv").exists()
    export_dir = tmp_path / "export"
    report_md = tmp_path / "report.md"
    report_md.write_text("# r-cli\n", encoding="utf-8")
    assert (
        _run(
            [
                "business",
                "export",
                "--out-dir",
                str(export_dir),
                "--report-json",
                str(report_dir / "business_report.json"),
                "--report-markdown",
                str(report_md),
            ]
        )
        == 0
    )
    assert (export_dir / "report.json").exists()
