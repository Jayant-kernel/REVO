"""Snapshot tests: source, environment, model, configuration (Phase 6)."""

import json

from verified_data_factory.provenance import (
    capture_environment_snapshot,
    capture_model_snapshot,
    capture_source_snapshot,
    snapshot_config,
)


def test_git_metadata_captured_when_available():
    snapshot = capture_source_snapshot(".", ["pyproject.toml"])
    # This repository is a git checkout (may be dirty from development).
    assert snapshot.git_commit != "" and snapshot.source_fingerprint != ""
    assert isinstance(snapshot.working_tree_clean, bool)


def test_unavailable_git_handled_safely(tmp_path):
    snapshot = capture_source_snapshot(tmp_path, ["pyproject.toml"])
    assert snapshot.git_commit == "UNKNOWN"
    assert snapshot.git_branch == "UNKNOWN"
    assert snapshot.working_tree_clean is False


def test_dirty_state_captured_not_hidden(tmp_path, monkeypatch):
    import subprocess

    monkeypatch.setattr(subprocess, "run", _raise_oserror)
    snapshot = capture_source_snapshot(tmp_path, ["pyproject.toml"])
    assert snapshot.git_commit == "UNKNOWN"
    assert snapshot.working_tree_clean is False


def _raise_oserror(*args, **kwargs):
    raise OSError("no git here")


def test_source_scope_excludes_unscoped_files(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    generated = tmp_path / "huge_generated.jsonl"
    generated.write_text("x" * 100000, encoding="utf-8")
    scoped = capture_source_snapshot(tmp_path, ["pyproject.toml"])
    assert scoped.git_commit == "UNKNOWN"  # plain dir, no git
    # Fingerprint must not move with unscoped content.
    generated.write_text("y" * 100000, encoding="utf-8")
    again = capture_source_snapshot(tmp_path, ["pyproject.toml"])
    assert again.source_fingerprint == scoped.source_fingerprint


def test_docker_metadata_captured_or_honest():
    snapshot = capture_environment_snapshot(".")
    assert snapshot.python_version != "UNKNOWN"
    assert snapshot.platform != "UNKNOWN"
    assert snapshot.dependency_lock_hash != ""
    # Client/server versions are strings when Docker answers, else None.
    assert snapshot.docker_client_version is None or isinstance(snapshot.docker_client_version, str)
    assert snapshot.docker_server_version is None or isinstance(snapshot.docker_server_version, str)


def test_missing_digest_represented_honestly():
    snapshot = capture_environment_snapshot(".", container_image="factory-sandbox:1.0")
    assert snapshot.image_digest_status == "UNAVAILABLE"
    assert snapshot.container_image_digest is None
    pinned = capture_environment_snapshot(
        ".", container_image="factory-sandbox:1.0", container_image_digest="sha256:abc"
    )
    assert pinned.image_digest_status == "PINNED"


def test_secret_env_values_never_captured(monkeypatch):
    monkeypatch.setenv("TEST_SECRET_SENTINEL", "s3cr3t-value")
    monkeypatch.setenv("VDF_API_KEY", "key-123")
    snapshot = capture_environment_snapshot(".")
    blob = json.dumps(snapshot.model_dump(mode="json"))
    assert "s3cr3t-value" not in blob
    assert "key-123" not in blob
    assert "TEST_SECRET_SENTINEL" not in blob
    assert "VDF_API_KEY" not in blob


def test_model_snapshot_fields_and_versions():
    from tests.verify_testkit import make_candidate, make_task

    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, "SELECT 1;")
    snapshot = capture_model_snapshot(
        candidate, license_identifier="test-license", source_registry="test-registry"
    )
    assert snapshot.provider == candidate.provider
    assert snapshot.model_name == candidate.model
    assert snapshot.model_revision == candidate.model_revision
    assert snapshot.license_identifier == "test-license"
    assert snapshot.source_registry == "test-registry"
    assert snapshot.endpoint_identifier_hash == candidate.endpoint_id
    assert snapshot.generation_config["temperature"] == candidate.generation_config.temperature
    assert snapshot.prompt_version == candidate.prompt_version
    assert snapshot.deterministic_replay is False
    assert snapshot.model_snapshot_id.startswith("sha256:")


def test_model_nondeterminism_not_falsely_deterministic():
    from tests.verify_testkit import make_candidate, make_task

    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, "SELECT 1;")
    assert capture_model_snapshot(candidate).deterministic_replay is False
    assert capture_model_snapshot(candidate, deterministic_replay=True).deterministic_replay is True


def test_config_snapshot_ids():
    first = snapshot_config("quality", {"a": 1, "b": [1, 2]}, "1.0")
    assert (
        first.configuration_id
        == snapshot_config("quality", {"b": [1, 2], "a": 1}, "1.0").configuration_id
    )
    changed = snapshot_config("quality", {"a": 2, "b": [1, 2]}, "1.0")
    assert changed.configuration_id != first.configuration_id
    assert changed.content_hash != first.content_hash
