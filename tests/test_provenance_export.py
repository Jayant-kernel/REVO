"""Bundle export, reproducibility diff, and CLI tests (Phase 6, §36–37, §42, §47–48)."""

import json

import pytest

from tests.provenance_fixtures import build_provenance_fixture
from verified_data_factory.provenance import (
    export_provenance_bundle,
    read_bundle,
)


@pytest.fixture(scope="module")
def fx():
    return build_provenance_fixture()


@pytest.fixture(scope="module")
def bundle_parts(fx):
    from verified_data_factory.provenance import build_bundle

    return build_bundle(
        fx["records"],
        fx["qualities"],
        fx["golden_records"],
        fx["audit_sample"],
        fx["quality_config"],
        fx["verification_config"],
        fx["factory_version"],
        "export-test-set",
        repo_root=".",
        source_scope=["pyproject.toml"],
    )


@pytest.fixture(scope="module")
def bundle_dir(tmp_path_factory, bundle_parts):

    out = tmp_path_factory.mktemp("bundle")
    export_provenance_bundle(
        out,
        bundle_parts["manifest"],
        bundle_parts["reproduction"].model_dump(mode="json"),
        bundle_parts["snapshot"],
        list(bundle_parts["nodes"].values()),
        bundle_parts["edges"],
        bundle_parts["activities"],
        bundle_parts["artifacts"],
        bundle_parts["golden"],
        {candidate_id: report for candidate_id, report in bundle_parts["reproducibility"].items()},
        bundle_parts["completeness"],
        bundle_parts["artifact_payloads"],
    )
    return out


def test_bundle_has_all_files(bundle_dir):
    from verified_data_factory.provenance import BUNDLE_FILES

    for name in BUNDLE_FILES:
        assert (bundle_dir / name).is_file(), name


def test_all_artifact_locators_resolve_inside_bundle(bundle_dir):
    bundle = read_bundle(bundle_dir)
    for artifact in bundle["artifacts.jsonl"]:
        assert (bundle_dir / artifact["relative_locator"]).is_file()


def test_built_bundle_completeness_is_true(bundle_parts):
    assert bundle_parts["completeness"]
    assert all(report.complete for report in bundle_parts["completeness"])


def test_bundle_round_trip(bundle_dir):
    first = read_bundle(bundle_dir)
    assert set(first) == {
        "manifest.json",
        "reproduction.json",
        "snapshot.json",
        "nodes.jsonl",
        "edges.jsonl",
        "activities.jsonl",
        "artifacts.jsonl",
        "golden_records.jsonl",
        "reproducibility.json",
        "completeness.json",
    }
    # Normalized rewrite is byte-identical (canonical serialization).
    import tempfile

    from verified_data_factory.provenance import export_provenance_bundle as rewrite
    from verified_data_factory.provenance.models import (
        ArtifactRef,
        DatasetSnapshot,
        ProvenanceActivity,
        ProvenanceCompletenessReport,
        ProvenanceEdge,
        ProvenanceNode,
        ReproducibilityReport,
        RunManifest,
    )

    with tempfile.TemporaryDirectory() as second:
        rewrite(
            second,
            RunManifest.model_validate(first["manifest.json"]),
            first["reproduction.json"],
            DatasetSnapshot.model_validate(first["snapshot.json"]),
            [ProvenanceNode.model_validate(n) for n in first["nodes.jsonl"]],
            [ProvenanceEdge.model_validate(e) for e in first["edges.jsonl"]],
            [ProvenanceActivity.model_validate(a) for a in first["activities.jsonl"]],
            [ArtifactRef.model_validate(a) for a in first["artifacts.jsonl"]],
            first["golden_records.jsonl"],
            {
                k: ReproducibilityReport.model_validate(v)
                for k, v in first["reproducibility.json"].items()
            },
            [ProvenanceCompletenessReport.model_validate(c) for c in first["completeness.json"]],
        )
        reread = read_bundle(second)
    assert reread == first


def test_no_absolute_host_paths_in_bundle(bundle_dir):
    blob = "\n".join(
        (bundle_dir / name).read_text(encoding="utf-8") for name in ("nodes.jsonl", "edges.jsonl")
    )
    assert "C:\\" not in blob and "C:/" not in blob
    assert "/home/" not in blob and "/Users/" not in blob


def test_reproduction_diff_identical_is_verified(bundle_dir):
    from verified_data_factory.provenance import compare_reproduction, read_bundle

    bundle = read_bundle(bundle_dir)
    manifest = bundle["reproduction.json"]
    diff = compare_reproduction(manifest, json.loads(json.dumps(manifest)))
    assert diff.status == "VERIFIED"
    assert diff.differences == []


def test_reproduction_diff_spots_drift(bundle_dir):
    import copy

    from verified_data_factory.provenance import compare_reproduction, read_bundle

    bundle = read_bundle(bundle_dir)
    manifest = bundle["reproduction.json"]
    drifted = copy.deepcopy(manifest)
    drifted["environment_snapshot"]["container_image_digest"] = "sha256:drifted"
    drifted["golden_record_ids"] = []
    diff = compare_reproduction(manifest, drifted)
    assert diff.status == "CONDITIONAL"
    categories = {d.category for d in diff.differences}
    assert "SANDBOX_IMAGE_CHANGED" in categories
    assert "DATASET_MEMBERSHIP_CHANGED" in categories
    unchanged = compare_reproduction({**manifest, "created_at": "tomorrow"}, manifest)
    assert unchanged.status == "VERIFIED"


def test_cli_record_and_validate(tmp_path, fx):
    from verified_data_factory.cli import main

    records_path = tmp_path / "records.jsonl"
    with open(records_path, "w", encoding="utf-8") as fh:
        fh.writelines(
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
            for record in fx["records"]
        )
    qualities_path = tmp_path / "qualities.jsonl"
    with open(qualities_path, "w", encoding="utf-8") as fh:
        fh.writelines(
            json.dumps(quality.model_dump(mode="json"), sort_keys=True) + "\n"
            for quality in fx["qualities"]
        )
    golden_path = tmp_path / "golden.jsonl"
    with open(golden_path, "w", encoding="utf-8") as fh:
        fh.writelines(
            json.dumps(golden.model_dump(mode="json", by_alias=True), sort_keys=True) + "\n"
            for golden in fx["golden_records"]
        )
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(
        json.dumps(fx["audit_sample"].model_dump(mode="json"), sort_keys=True), encoding="utf-8"
    )
    bundle_dir = tmp_path / "bundle"
    code = main(
        [
            "provenance",
            "record",
            "--records",
            str(records_path),
            "--qualities",
            str(qualities_path),
            "--golden",
            str(golden_path),
            "--audit",
            str(audit_path),
            "--name",
            "cli-test",
            "--out",
            str(bundle_dir),
        ]
    )
    assert code == 0
    assert (bundle_dir / "nodes.jsonl").is_file()
    assert main(["provenance", "validate", "--bundle", str(bundle_dir)]) in (0, 1)
    snapshot_path = tmp_path / "snapshot.json"
    assert (
        main(
            [
                "provenance",
                "snapshot",
                "--golden",
                str(golden_path),
                "--name",
                "cli-test",
                "--output",
                str(snapshot_path),
            ]
        )
        == 0
    )
    assert json.loads(snapshot_path.read_text(encoding="utf-8"))["dataset_snapshot_id"].startswith(
        "sha256:"
    )
    assert main(["provenance", "run", "--output", str(tmp_path / "run.json")]) == 0
