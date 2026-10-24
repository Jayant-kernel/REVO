import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verified_data_factory.cli import main
from verified_data_factory.production import (
    ProductionConfigError,
    assert_resume_config,
    config_id,
    load_config,
    plan,
    report,
    status,
)
from verified_data_factory.production.api import _template_diversity, policy_file_hashes
from verified_data_factory.production.runner import (
    _effective_audit_rate,
    _latest_templates_for_family,
    _pause_reason,
    _template_catalog_id,
    run_authorized,
)
from verified_data_factory.sandbox import load_config as load_sandbox_config

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


def test_premium_review_pool_mode_has_distinct_identity() -> None:
    premium = load_config("configs/production/premium_qualification_80.yaml")
    assert premium.review_pool_mode is True
    assert premium.config_version == "4.3-premium-93-diversity-gate"
    assert premium.min_distinct_templates_per_family == 4
    without_pool = premium.model_copy(update={"review_pool_mode": False})
    assert config_id(without_pool) != config_id(premium)
    assert _effective_audit_rate(premium, 240) == 0.0
    assert _effective_audit_rate(without_pool, 240) == 1.0


def test_premium_template_diversity_gate_is_honestly_blocked() -> None:
    from verified_data_factory.task_engine import load_builtin_registry

    premium = load_config("configs/production/premium_qualification_80.yaml")
    result = _template_diversity(premium, load_builtin_registry())
    assert result["ok"] is True
    assert result["required_per_family"] == 4
    assert result["available_per_family"]["simple_joins"] == 5
    assert result["available_per_family"]["aggregation"] == 8
    assert result["available_per_family"]["deduplication"] == 5
    assert result["available_per_family"]["funnel"] == 8
    assert plan(premium)["template_diversity"] == result


def test_family_rotation_uses_latest_version_of_each_distinct_template() -> None:
    class Registry:
        def list_by_family(self, family: str) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(template_id="sql.test.beta", version=1),
                SimpleNamespace(template_id="sql.test.alpha", version=1),
                SimpleNamespace(template_id="sql.test.alpha", version=2),
            ] if family == "test" else []

    selected = _latest_templates_for_family(Registry(), "test")
    assert [(item.template_id, item.version) for item in selected] == [
        ("sql.test.alpha", 2),
        ("sql.test.beta", 1),
    ]
    with pytest.raises(ProductionConfigError, match="no task templates"):
        _latest_templates_for_family(Registry(), "missing")


def test_catalog_identity_changes_when_template_changes() -> None:
    from verified_data_factory.task_engine import load_builtin_registry

    registry = load_builtin_registry()
    original = _template_catalog_id(registry)
    template = registry.get("sql.subqueries.exists", 2)
    registry._by_key[(template.template_id, 2)] = template.model_copy(
        update={"description": template.description + " revised"}
    )
    assert _template_catalog_id(registry) != original


def test_runner_refuses_changed_template_catalog_on_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = tmp_path / "frozen-run"
    (run / "manifests").mkdir(parents=True)
    production = load_config(CONFIG).model_copy(update={"output_dir": str(run)})
    (run / "manifests/run-manifest.json").write_text(
        json.dumps(
            {
                "production_config_id": config_id(production),
                "policy_file_hashes": policy_file_hashes(production),
                "template_catalog_id": "sha256:stale",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "verified_data_factory.production.api.preflight",
        lambda config, **kwargs: {"ok": True, "checks": {}},
    )
    with pytest.raises(ProductionConfigError, match="template catalog changed"):
        run_authorized(production, run, execute=True)


def test_invalid_production_config_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("production: {target_golden_records: 0}\n", encoding="utf-8")
    with pytest.raises(ProductionConfigError):
        load_config(path)


def test_unknown_production_provider_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unknown-provider.yaml"
    path.write_text(
        CONFIG.read_text(encoding="utf-8").replace("provider: devstral", "provider: unknown"),
        encoding="utf-8",
    )
    with pytest.raises(ProductionConfigError, match="provider"):
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
    assert result["batches_per_authorization"] == 1


def test_production_config_cannot_authorize_multiple_batches() -> None:
    production = load_config(CONFIG)
    with pytest.raises(ValueError, match="less than or equal to 1"):
        type(production).model_validate(
            {
                **production.model_dump(mode="python"),
                "batches_per_authorization": 2,
            }
        )


def test_status_counts_existing_artifacts_without_generation(tmp_path: Path) -> None:
    run = tmp_path / "prepared-run"
    (run / "candidates").mkdir(parents=True)
    (run / "tasks").mkdir()
    (run / "execution").mkdir()
    (run / "verification").mkdir()
    (run / "quality/export").mkdir(parents=True)
    (run / "tasks/tasks.jsonl").write_text('{"task_id":"a"}\n', encoding="utf-8")
    (run / "candidates/candidates.jsonl").write_text(
        json.dumps(
            {
                "task_id": "a",
                "results": [
                    {"generation_status": "SUCCEEDED", "candidate_solution": {"candidate_id": "c1"}},
                    {"generation_status": "SUCCEEDED", "candidate_solution": {"candidate_id": "c2"}},
                    {
                        "generation_status": "FAILED",
                        "candidate_solution": None,
                        "failure_reason": "provider error",
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "execution/triples.jsonl").write_text('{"candidate":{"candidate_id":"c"}}\n', encoding="utf-8")
    (run / "verification/verification.jsonl").write_text('{"candidate_id":"c"}\n', encoding="utf-8")
    (run / "quality/export/golden.jsonl").write_text('{}\n', encoding="utf-8")
    run_status = status(run)
    assert run_status["candidate_bundles"] == 1
    assert run_status["candidates"] == 3
    assert run_status["generation_successes"] == 2
    assert run_status["generation_failures"] == 1
    assert run_status["golden"] == 1
    assert report(run)["golden"] == 1


def test_historical_run_path_is_rejected() -> None:
    production = load_config(CONFIG)
    assert "production-001" not in production.output_dir


def test_resume_requires_identical_content_defined_config(tmp_path: Path) -> None:
    production = load_config(CONFIG)
    manifest = tmp_path / "run-manifest.json"
    manifest.write_text(
        json.dumps({
            "production_config_id": config_id(production),
            "policy_file_hashes": policy_file_hashes(production),
        }),
        encoding="utf-8",
    )
    assert_resume_config(production, manifest)
    changed = production.model_copy(update={"model": production.model.model_copy(update={"temperature": 0.5})})
    with pytest.raises(ProductionConfigError):
        assert_resume_config(changed, manifest)


def test_resume_rejects_changed_referenced_policy_contents(tmp_path: Path) -> None:
    original = load_config(CONFIG)
    quality_copy = tmp_path / "quality.yaml"
    quality_copy.write_bytes(Path(original.quality_config).read_bytes())
    production = original.model_copy(update={"quality_config": str(quality_copy)})
    manifest = tmp_path / "run-manifest.json"
    manifest.write_text(
        json.dumps({
            "production_config_id": config_id(production),
            "policy_file_hashes": policy_file_hashes(production),
        }),
        encoding="utf-8",
    )
    assert_resume_config(production, manifest)
    quality_copy.write_bytes(quality_copy.read_bytes() + b"\n# changed after freeze\n")
    with pytest.raises(ProductionConfigError, match="referenced policy content changed"):
        assert_resume_config(production, manifest)


def test_runner_requires_explicit_execution_authorization(tmp_path: Path) -> None:
    with pytest.raises(ProductionConfigError):
        run_authorized(load_config(CONFIG), tmp_path, execute=False)


def test_cli_run_rejects_destination_outside_frozen_config(tmp_path: Path) -> None:
    """The CLI must fail before creating anything at an unapproved run path."""
    config_path = tmp_path / "production.yaml"
    config_path.write_text(
        CONFIG.read_text(encoding="utf-8").replace(
            "initial_task_batch: 500", "initial_task_batch: 499"
        ),
        encoding="utf-8",
    )
    unapproved = tmp_path / "wrong-run"

    with pytest.raises(ProductionConfigError, match="frozen output_dir"):
        main(
            [
                "production",
                "run",
                "--config",
                str(config_path),
                "--run",
                str(unapproved),
                "--execute",
            ]
        )

    assert not unapproved.exists()


def test_cli_preflight_rejects_unexpected_sandbox_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sandbox_path = tmp_path / "sandbox.yaml"
    sandbox_path.write_text(
        "sandbox:\n"
        "  image: verified-data-factory-sandbox:1.0\n"
        "  image_digest: sha256:expected\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "production.yaml"
    config_path.write_text(
        CONFIG.read_text(encoding="utf-8").replace(
            "configs/sandbox_production.yaml", sandbox_path.as_posix()
        ),
        encoding="utf-8",
    )

    class Response:
        def json(self) -> dict[str, object]:
            return {
                "models": [
                    {
                        "name": "alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest",
                        "digest": "a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4",
                    }
                ]
            }

    monkeypatch.setattr(
        "verified_data_factory.production.api.httpx.get", lambda *args, **kwargs: Response()
    )

    def fake_docker(args: list[str]) -> tuple[bool, str]:
        if args[0] == "info":
            return True, "29.0"
        if args[:2] == ["image", "inspect"]:
            return True, "sha256:actual"
        return True, ""

    monkeypatch.setattr("verified_data_factory.production.api._docker", fake_docker)

    assert main(["production", "preflight", "--config", str(config_path)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]["sandbox"]["ok"] is False
    assert payload["checks"]["sandbox"]["expected_digest"] == "sha256:expected"
    assert payload["checks"]["sandbox"]["actual_digest"] == "sha256:actual"


def test_cli_preflight_rejects_stale_factory_containers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sandbox_path = tmp_path / "sandbox.yaml"
    sandbox_path.write_text(
        "sandbox:\n"
        "  image: verified-data-factory-sandbox:1.0\n"
        "  image_digest: sha256:expected\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "production.yaml"
    config_path.write_text(
        CONFIG.read_text(encoding="utf-8").replace(
            "configs/sandbox_production.yaml", sandbox_path.as_posix()
        ),
        encoding="utf-8",
    )

    class Response:
        def json(self) -> dict[str, object]:
            return {
                "models": [
                    {
                        "name": "alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest",
                        "digest": "a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4",
                    }
                ]
            }

    monkeypatch.setattr(
        "verified_data_factory.production.api.httpx.get", lambda *args, **kwargs: Response()
    )

    def fake_docker(args: list[str]) -> tuple[bool, str]:
        if args[0] == "info":
            return True, "29.0"
        if args[:2] == ["image", "inspect"]:
            return True, "sha256:expected"
        if args[:2] == ["ps", "-aq"]:
            return True, "stale-container-id"
        return True, ""

    monkeypatch.setattr("verified_data_factory.production.api._docker", fake_docker)

    assert main(["production", "preflight", "--config", str(config_path)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]["sandbox"]["ok"] is False
    assert payload["checks"]["sandbox"]["stale_vdf_containers"] == ["stale-container-id"]


def test_runner_refuses_failed_preflight_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = tmp_path / "new-production-run"
    production = load_config(CONFIG).model_copy(update={"output_dir": str(run)})
    monkeypatch.setattr(
        "verified_data_factory.production.api.preflight",
        lambda config, **kwargs: {"ok": False, "checks": {"sandbox": {"ok": False}}},
    )
    monkeypatch.setattr(
        "verified_data_factory.production.runner.load_builtin_registry",
        lambda: (_ for _ in ()).throw(AssertionError("execution started before preflight")),
    )

    with pytest.raises(ProductionConfigError, match="preflight"):
        run_authorized(production, run, execute=True)

    assert not run.exists()


def test_new_run_manifest_persists_exact_model_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = tmp_path / "new-production-run"
    production = load_config(CONFIG).model_copy(update={"output_dir": str(run)})
    monkeypatch.setattr(
        "verified_data_factory.production.api.preflight",
        lambda config, **kwargs: {"ok": True, "checks": {}},
    )
    monkeypatch.setattr(
        "verified_data_factory.production.runner.create_provider",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("stop after manifest")),
    )

    with pytest.raises(RuntimeError, match="stop after manifest"):
        run_authorized(production, run, execute=True)

    manifest = json.loads((run / "manifests/run-manifest.json").read_text(encoding="utf-8"))
    assert manifest["model_id"] == production.model.model_id
    assert manifest["model_revision"] == production.model.model_revision
    assert manifest["provider"] == production.model.provider
    assert manifest["governance_status"] == "REVIEW_REQUIRED_NON_COMMERCIAL"
    assert manifest["template_catalog_id"].startswith("sha256:")


def test_all_production_configs_pin_the_sandbox_image_digest() -> None:
    configs = sorted(Path("configs/production").glob("*.yaml"))
    assert configs
    for path in configs:
        production = load_config(path)
        assert production.sandbox_config == "configs/sandbox_production.yaml"
        sandbox = load_sandbox_config(production.sandbox_config)
        assert sandbox.image_digest == (
            "sha256:6ee6badb20867c6426abb0b2ced747a126178f0a99b5bf4d94e65a62c236f7ac"
        )


def test_runner_pause_conditions_are_enforced() -> None:
    production = load_config(CONFIG)
    succeeded = SimpleNamespace(
        execution=SimpleNamespace(status="SUCCEEDED"),
        verification=SimpleNamespace(verdict="PASS"),
    )
    failed = SimpleNamespace(
        execution=SimpleNamespace(status="EXECUTION_ERROR"),
        verification=SimpleNamespace(verdict="INCONCLUSIVE"),
    )
    golden = SimpleNamespace(decision="GOLDEN", task_id="golden", semantic_duplicate_group=None)
    duplicates = [
        SimpleNamespace(decision="EXCLUDED", task_id=f"task-{i}", semantic_duplicate_group="sem-1")
        for i in range(9)
    ]
    excluded = SimpleNamespace(decision="EXCLUDED", task_id="excluded", semantic_duplicate_group=None)
    assert _pause_reason(production, [succeeded] * 10, [golden] * 10) is None
    assert "execution_error_rate" in _pause_reason(
        production, [failed] * 6 + [succeeded] * 4, [golden] * 10
    )
    assert "semantic_duplicate_rate" in _pause_reason(
        production, [succeeded] * 10, duplicates + [golden]
    )
    assert "zero Golden" in _pause_reason(
        production, [succeeded] * 60, [excluded] * 60
    )


def test_sibling_candidates_do_not_trip_semantic_duplicate_stop() -> None:
    production = load_config(CONFIG)
    succeeded = SimpleNamespace(
        execution=SimpleNamespace(status="SUCCEEDED"),
        verification=SimpleNamespace(verdict="PASS"),
    )
    siblings = [
        SimpleNamespace(decision="GOLDEN", task_id=f"task-{i // 3}", semantic_duplicate_group=f"sem-{i // 3}")
        for i in range(30)
    ]
    assert _pause_reason(production, [succeeded] * 30, siblings) is None
