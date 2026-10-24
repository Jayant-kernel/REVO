"""Strict factory authority and publication failures are fail-closed."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from verified_data_factory.products.errors import ProductConfigError
from verified_data_factory.products.isolation import (
    schema_role_fingerprint,
    sql_structure_fingerprint,
)
from verified_data_factory.products.staging import isolation_authority, staged_release


def test_registry_path_change_cannot_create_a_second_authority(tmp_path):
    first = isolation_authority(tmp_path, tmp_path / "roles.json")
    assert first == isolation_authority(tmp_path, tmp_path / "roles.json")
    with pytest.raises(ProductConfigError, match="registry path cannot change"):
        isolation_authority(tmp_path, tmp_path / "other/roles.json")


def test_failed_private_build_has_no_finalized_path(tmp_path):
    registry = tmp_path / "roles.json"
    isolation_authority(tmp_path, registry)
    config = SimpleNamespace(acceptance_profile="ENGINEERING_STRICT", engineering_evidence_root=str(tmp_path),
                             engineering_role_registry=str(registry))

    @staged_release
    def failing(**values):
        stage = values["out_dir"]
        stage.mkdir()
        (stage / "partial.json").write_text("{}")
        raise ProductConfigError("injected late validation failure")

    final = tmp_path / "release"
    with pytest.raises(ProductConfigError, match="late validation failure"):
        failing(config=config, out_dir=final)
    assert not final.exists()
    assert len(list(tmp_path.glob(".release.staging-*/partial.json"))) == 1


def test_declared_schema_key_roles_are_retained_without_names():
    schema = [{"name": "a", "columns": [{"name": "x", "type": "INTEGER", "nullable": False, "key_role": "PRIMARY"}]}]
    renamed = [{"name": "b", "columns": [{"name": "y", "type": "INTEGER", "nullable": False, "key_role": "PRIMARY"}]}]
    ordinary = [{"name": "a", "columns": [{"name": "x", "type": "INTEGER", "nullable": False}]}]
    assert schema_role_fingerprint(schema) == schema_role_fingerprint(renamed)
    assert schema_role_fingerprint(schema) != schema_role_fingerprint(ordinary)


def test_renamed_join_aliases_and_ctes_share_structural_screen():
    first = "WITH scoped AS (SELECT a.id FROM alpha a JOIN beta b ON a.id=b.id) SELECT id FROM scoped"
    renamed = "WITH changed AS (SELECT x.code FROM renamed_a x JOIN renamed_b y ON x.code=y.code) SELECT code FROM changed"
    assert sql_structure_fingerprint(first) == sql_structure_fingerprint(renamed)


def test_concurrent_processes_do_not_lose_role_conflicts(tmp_path):
    registry = tmp_path / "roles.json"
    root = Path(__file__).resolve().parents[1]
    workers = [subprocess.Popen([sys.executable, "tests/stage4_role_worker.py", "--registry", str(registry),
                                 "--role", role], cwd=root) for role in ("TRAIN", "EVAL")]
    try:
        codes = [worker.wait(timeout=30) for worker in workers]
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.terminate()
                worker.wait(timeout=10)
    assert sorted(codes) == [0, 2]
    assert len(set(json.loads(registry.read_text()).values())) == 1


def test_historical_consumed_json_is_opaque_not_a_live_dependency_recipe(tmp_path):
    from verified_data_factory.products.acceptance import retain_replay_inputs
    from verified_data_factory.verification.receipt_validation import digest

    source = tmp_path / "source"
    evidence = source / "scratch/funnel_experiment/evidence"
    evidence.mkdir(parents=True)
    (evidence / "events.jsonl").write_text("")
    (evidence / "index.json").write_text(json.dumps({"entries": [], "event_count": 0}))
    (source / "manifests").mkdir()
    (source / "manifests/package-a-contract-quarantine.json").write_text(json.dumps({"version": 1, "quarantines": []}))
    historical = source / "historical.json"
    historical.write_text(json.dumps({"source_hashes": {"missing-old-source.py": "0" * 64}}))
    target = tmp_path / "delivered"
    retain_replay_inputs(source, target, {"historical.json": digest(historical)}, [])
    assert (target / "historical.json").read_bytes() == historical.read_bytes()
    assert not (target / "missing-old-source.py").exists()


def test_replay_inputs_support_long_windows_delivery_paths(tmp_path):
    from verified_data_factory.local_paths import io_path
    from verified_data_factory.products.acceptance import retain_replay_inputs
    from verified_data_factory.verification.receipt_validation import digest

    source = tmp_path / "source"
    evidence = source / "scratch/funnel_experiment/evidence"
    evidence.mkdir(parents=True)
    (evidence / "events.jsonl").write_text("")
    (evidence / "index.json").write_text(json.dumps({"entries": [], "event_count": 0}))
    (source / "manifests").mkdir()
    (source / "manifests/package-a-contract-quarantine.json").write_text(json.dumps({"version": 1, "quarantines": []}))
    (source / "input.json").write_text("{}")
    delivered = tmp_path / ("a" * 90) / ("b" * 90) / "replay_root"
    retain_replay_inputs(source, delivered, {"input.json": digest(source / "input.json")}, [])
    assert io_path(delivered / "input.json").read_text() == "{}"
