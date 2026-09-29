import json
from pathlib import Path

import pytest

from verified_data_factory.production import (
    ProductionConfigError,
    assert_resume_config,
    config_id,
    load_config,
    plan,
    report,
    status,
)
from verified_data_factory.production.runner import run_authorized
from verified_data_factory.production.runner import _pause_reason


CONFIG = Path("configs/production/production_sql_v1.yaml")


def test_production_config_is_pinned_and_has_stable_identity() -> None:
    production = load_config(CONFIG)
    assert production.model.model_id.startswith("alibilge/")
    assert production.model.model_revision.startswith("ollama-digest:")
    assert production.model.prompt_version == "sql-v2"
    assert config_id(production) == config_id(load_config(CONFIG))


def test_material_model_change_changes_configuration_identity() -> None:
    production = load_config(CONFIG)
    changed = production.model_copy(update={"model": production.model.model_copy(update={"top_p": 0.9})})
    assert config_id(changed) != config_id(production)


def test_invalid_production_config_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("production: {target_golden_records: 0}\n", encoding="utf-8")
    with pytest.raises(ProductionConfigError):
        load_config(path)


def test_plan_is_dry_and_has_no_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    production = load_config(CONFIG)
    monkeypatch.setattr("verified_data_factory.production.api.requests_made", lambda: (_ for _ in ()).throw(AssertionError("network")))
    result = plan(production)
    assert result["dry_run"] is True
    assert result["model_calls"] == 0
    assert result["docker_executions"] == 0
    assert result["candidates_generated"] == 0
    assert result["initial_candidates"] == 1500


def test_status_counts_existing_artifacts_without_generation(tmp_path: Path) -> None:
    run = tmp_path / "prepared-run"
    (run / "candidates").mkdir(parents=True)
    (run / "tasks").mkdir()
    (run / "execution").mkdir()
    (run / "verification").mkdir()
    (run / "quality/export").mkdir(parents=True)
    (run / "tasks/tasks.jsonl").write_text('{"task_id":"a"}\n', encoding="utf-8")
    (run / "candidates/candidates.jsonl").write_text('{"task_id":"a"}\n', encoding="utf-8")
    (run / "execution/triples.jsonl").write_text('{"candidate":{"candidate_id":"c"}}\n', encoding="utf-8")
    (run / "verification/verification.jsonl").write_text('{"candidate_id":"c"}\n', encoding="utf-8")
    (run / "quality/export/golden.jsonl").write_text('{}\n', encoding="utf-8")
    assert status(run)["golden"] == 1
    assert report(run)["golden"] == 1


def test_historical_run_path_is_rejected() -> None:
    production = load_config(CONFIG)
    assert "production-001" not in production.output_dir


def test_resume_requires_identical_content_defined_config(tmp_path: Path) -> None:
    production = load_config(CONFIG)
    manifest = tmp_path / "run-manifest.json"
    manifest.write_text(json.dumps({"production_config_id": config_id(production)}), encoding="utf-8")
    assert_resume_config(production, manifest)
    changed = production.model_copy(update={"model": production.model.model_copy(update={"temperature": 0.5})})
    with pytest.raises(ProductionConfigError):
        assert_resume_config(changed, manifest)


def test_runner_requires_explicit_execution_authorization(tmp_path: Path) -> None:
    with pytest.raises(ProductionConfigError):
        run_authorized(load_config(CONFIG), tmp_path, execute=False)


def test_runner_pause_conditions_are_enforced() -> None:
    from types import SimpleNamespace

    production = load_config(CONFIG)
    succeeded = SimpleNamespace(
        execution=SimpleNamespace(status="SUCCEEDED"),
        verification=SimpleNamespace(verdict="PASS"),
    )
    failed = SimpleNamespace(
        execution=SimpleNamespace(status="EXECUTION_ERROR"),
        verification=SimpleNamespace(verdict="INCONCLUSIVE"),
    )
    golden = SimpleNamespace(decision="GOLDEN", semantic_duplicate_group=None)
    duplicate = SimpleNamespace(decision="EXCLUDED", semantic_duplicate_group="sem-1")
    excluded = SimpleNamespace(decision="EXCLUDED", semantic_duplicate_group=None)
    assert _pause_reason(production, [succeeded] * 10, [golden] * 10) is None
    assert "execution_error_rate" in _pause_reason(
        production, [failed] * 6 + [succeeded] * 4, [golden] * 10
    )
    assert "semantic_duplicate_rate" in _pause_reason(
        production, [succeeded] * 10, [duplicate] * 9 + [golden]
    )
    assert "zero Golden" in _pause_reason(
        production, [succeeded] * 60, [excluded] * 60
    )
