"""Regression evidence for production identity and resource boundaries."""
import json
from pathlib import Path

import pytest

from verified_data_factory.production import ProductionConfigError, load_config
from verified_data_factory.production.api import (
    _matches_ollama_digest,
    contract_readiness_from_manifest,
    implementation_id,
    preflight,
)
from verified_data_factory.production.runner import (
    _assert_checkpoint_integrity,
    _check_budget,
    _checkpoint,
    _reserve_attempts,
    run_authorized,
)


def test_nonempty_unmanifested_destination_is_not_adopted(tmp_path, monkeypatch):
    run = tmp_path / "historical"
    run.mkdir()
    marker = run / "evidence.json"
    marker.write_text("original", encoding="utf-8")
    config = load_config("configs/production/smoke_qualification_001.yaml").model_copy(
        update={"output_dir": str(run)}
    )
    monkeypatch.setattr(
        "verified_data_factory.production.api.preflight", lambda _, **kwargs: {"ok": True}
    )
    with pytest.raises(ProductionConfigError, match="nonempty"):
        run_authorized(config, run, execute=True)
    assert marker.read_text(encoding="utf-8") == "original"
    assert not (run / "manifests").exists()


def test_budget_includes_previous_authorizations(tmp_path, monkeypatch):
    config = load_config("configs/production/smoke_qualification_001.yaml")
    monkeypatch.setattr("verified_data_factory.production.runner.time.monotonic", lambda: 101.0)
    assert _check_budget(tmp_path, 100, 0, config)
    assert not _check_budget(tmp_path, 100, config.budget.max_wall_time_minutes * 60, config)
    state = json.loads((tmp_path / "manifests/run-state.json").read_text())
    assert state["status"] == "PAUSED"
    assert state["reason"] == "wall-time budget reached"


def test_source_identity_is_stable_and_content_bound(monkeypatch, tmp_path):
    assert implementation_id() == implementation_id()
    package = tmp_path / "package"
    module = package / "production/api.py"
    module.parent.mkdir(parents=True)
    module.write_text("first")
    monkeypatch.setattr("verified_data_factory.production.api.__file__", str(module))
    before = implementation_id()
    module.write_text("second")
    assert implementation_id() != before


def test_model_revision_requires_exact_namespace(monkeypatch):
    from types import SimpleNamespace
    config = load_config("configs/production/smoke_qualification_001.yaml")
    digest = config.model.model_revision.removeprefix("ollama-digest:")
    monkeypatch.setattr("verified_data_factory.production.api.httpx.get", lambda *a, **k:
        SimpleNamespace(json=lambda: {"models": [{"name": config.model.model_id, "digest": digest}]}))
    monkeypatch.setattr("verified_data_factory.production.api._docker", lambda _: (False, "unavailable"))
    changed = config.model_copy(update={"model": config.model.model_copy(
        update={"model_revision": "unverified-prefix:" + digest})})
    assert not preflight(changed)["checks"]["model"]["ok"]


def test_model_digest_allows_explicit_observation_namespaces_only():
    digest = "a" * 64
    assert _matches_ollama_digest("ollama-digest:" + digest, digest)
    assert _matches_ollama_digest("ollama-manifest:" + digest, digest)
    assert not _matches_ollama_digest("unverified-prefix:" + digest, digest)
    assert not _matches_ollama_digest("ollama-digest:" + digest, digest + "x")


def test_checkpoint_rejects_changed_evidence(tmp_path):
    tasks = tmp_path / "tasks/tasks.jsonl"
    tasks.parent.mkdir()
    tasks.write_text('{"task_id":"original"}\n', encoding="utf-8")
    _checkpoint(tmp_path, {"status": "RUNNING"})
    state = json.loads((tmp_path / "manifests/run-state.json").read_text())
    _assert_checkpoint_integrity(tmp_path, state)
    tasks.write_text('{"task_id":"changed"}\n', encoding="utf-8")
    with pytest.raises(ProductionConfigError, match="checkpoint artifacts"):
        _assert_checkpoint_integrity(tmp_path, state)


def test_production_verifier_uses_same_pinned_sandbox(tmp_path, monkeypatch):
    from verified_data_factory.production import runner
    run = tmp_path / "new-run"
    config = load_config("configs/production/smoke_qualification_001.yaml").model_copy(
        update={"output_dir": str(run)})
    monkeypatch.setattr(
        "verified_data_factory.production.api.preflight", lambda _, **kwargs: {"ok": True}
    )
    monkeypatch.setattr(runner, "create_provider", lambda *a, **kw: object())
    captured = []
    monkeypatch.setattr(runner, "SandboxExecutor", lambda sandbox: captured.append(sandbox))
    monkeypatch.setattr(runner, "DerivedTaskBackend", lambda sandbox: captured.append(sandbox))
    monkeypatch.setattr(runner, "generate_candidates", lambda *a: (_ for _ in ()).throw(RuntimeError("stop before generation")))
    with pytest.raises(RuntimeError, match="stop before generation"):
        run_authorized(config, run, execute=True)
    assert len(captured) == 2 and captured[0] is captured[1]
    assert captured[1].image_digest == "sha256:6ee6badb20867c6426abb0b2ced747a126178f0a99b5bf4d94e65a62c236f7ac"


def test_interrupted_generation_reservations_consume_attempt_budget(tmp_path):
    config = load_config("configs/production/smoke_qualification_001.yaml")
    # No candidate response is checkpointed, simulating interruption. Repeated
    # authorizations still cannot silently exceed the frozen attempt budget.
    for _ in range(10):
        assert _reserve_attempts(tmp_path, "interrupted-task", config)
    assert not _reserve_attempts(tmp_path, "interrupted-task", config)
    assert not (tmp_path / "candidates/candidates.jsonl").exists()
    assert len((tmp_path / "candidates/attempt-reservations.jsonl").read_text().splitlines()) == 10


def test_readiness_manifest_respects_package_a_quarantine(tmp_path):
    manifest = Path("manifests/phase3-contract-readiness.json")
    quarantine = manifest.parent / "package-a-contract-quarantine.json"
    target_manifest = tmp_path / manifest.name
    target_manifest.write_text(manifest.read_text(encoding="utf-8"), encoding="utf-8")
    target_quarantine = tmp_path / quarantine.name
    target_quarantine.write_text(quarantine.read_text(encoding="utf-8"), encoding="utf-8")
    readiness = contract_readiness_from_manifest(target_manifest)
    # Rule evidence alone cannot qualify a contract without fresh challenge,
    # fuzz and mutation category receipts under engineering-3.0.
    assert not readiness("sql.funnel.saas_activation_payment")
    assert not readiness("sql.funnel.logistics_parcel_delivery")
    assert not readiness("sql.funnel.checkout_paid_session")
