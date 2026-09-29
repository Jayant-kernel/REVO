"""Product CLI tests (Phase 7): build → validate → diff → load via `factory product`."""

import json

import yaml

from tests.product_fixtures import build_product_fixture
from verified_data_factory.cli import build_parser


def _write_inputs(tmp_path):
    goldens, quality_by_id, snapshot = build_product_fixture()
    golden_path = tmp_path / "golden.jsonl"
    with open(golden_path, "w", encoding="utf-8") as fh:
        fh.writelines(
            json.dumps(golden.model_dump(mode="json", by_alias=True), sort_keys=True) + "\n"
            for golden in goldens
        )
    quality_path = tmp_path / "qualities.json"
    quality_path.write_text(
        json.dumps(list(quality_by_id.values()), indent=2, sort_keys=True), encoding="utf-8"
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8"
    )
    config_path = tmp_path / "product.yaml"
    config_path.write_text(
        yaml.safe_dump({"product": {"product_name": "cli", "product_type": "TRAIN"}}),
        encoding="utf-8",
    )
    return golden_path, quality_path, snapshot_path, config_path


def _run(argv):
    return build_parser().parse_args(argv).func(build_parser().parse_args(argv))


def test_cli_build_validate_load_diff(tmp_path, capsys):
    golden_path, quality_path, snapshot_path, config_path = _write_inputs(tmp_path)
    out = tmp_path / "release"
    assert (
        _run(
            [
                "product",
                "build",
                "--golden",
                str(golden_path),
                "--quality",
                str(quality_path),
                "--snapshot",
                str(snapshot_path),
                "--config",
                str(config_path),
                "--out-dir",
                str(out),
            ]
        )
        == 0
    )
    assert (out / "manifest.json").exists()
    assert _run(["product", "validate", "--release-dir", str(out)]) == 0
    assert _run(["product", "load", "--release-dir", str(out)]) == 0
    assert _run(["product", "diff", "--a", str(out), "--b", str(out)]) == 0
    assert (
        _run(
            [
                "product",
                "splits",
                "--golden",
                str(golden_path),
                "--quality",
                str(quality_path),
                "--seed",
                "7",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "release=" in captured.out


def test_cli_validate_missing_release(tmp_path):
    assert _run(["product", "validate", "--release-dir", str(tmp_path / "nope")]) == 1
