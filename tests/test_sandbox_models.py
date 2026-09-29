"""Sandbox model/config tests: execution-only schema, safe defaults."""

import pytest

from verified_data_factory.sandbox import (
    SANDBOX_CONFIG_VERSION,
    TERMINAL_STATUSES,
    SandboxConfig,
    config_from_dict,
    load_config,
)
from verified_data_factory.sandbox.errors import SandboxConfigError


def test_no_correctness_concepts_in_statuses():
    joined = " ".join(TERMINAL_STATUSES)
    for banned in ("CORRECT", "INCORRECT", "VERIFIED", "FAILED_VERIFICATION"):
        assert banned not in joined.split()


def test_lifecycle_states_never_terminal():
    assert "RUNNING" not in TERMINAL_STATUSES
    assert "NOT_STARTED" not in TERMINAL_STATUSES
    assert "SUCCEEDED" in TERMINAL_STATUSES


def test_config_version_namespaces_are_separate():
    """Four distinct version concepts (values may coincide; meanings differ)."""
    from verified_data_factory.generation import GENERATION_SCHEMA_VERSION, PROMPT_VERSION
    from verified_data_factory.task_engine import ENGINE_VERSION

    assert SANDBOX_CONFIG_VERSION == "1.0"  # execution/security behavior
    assert PROMPT_VERSION == "sql-v2"  # solver prompt behavior
    assert GENERATION_SCHEMA_VERSION == "1.0"  # candidate representation
    assert ENGINE_VERSION == "1.0.0"  # task generation behavior
    import verified_data_factory.generation.models as gen_models
    import verified_data_factory.sandbox.models as sandbox_models
    import verified_data_factory.task_engine.seed as engine_seed

    assert "SANDBOX_CONFIG_VERSION" in dir(sandbox_models)
    assert "GENERATION_SCHEMA_VERSION" in dir(gen_models)
    assert "ENGINE_VERSION" in dir(engine_seed)


def test_safe_defaults():
    cfg = SandboxConfig()
    assert cfg.network == "none"
    assert cfg.read_only_root and cfg.non_root and cfg.cap_drop_all and cfg.no_new_privileges
    assert cfg.single_statement_only
    assert cfg.timeout_seconds == 10.0
    assert cfg.memory_mb == 512
    assert cfg.pids_limit == 64


def test_invalid_config_rejected():
    for bad in [
        {"timeout_seconds": 0},
        {"timeout_seconds": -5},
        {"memory_mb": 8},
        {"cpus": 0},
        {"pids_limit": 1},
        {"max_result_rows": 0},
    ]:
        with pytest.raises(SandboxConfigError):
            config_from_dict(bad)


def test_load_config_yaml(tmp_path):
    path = tmp_path / "sandbox.yaml"
    path.write_text("sandbox:\n  timeout_seconds: 5\n  memory_mb: 256\n", encoding="utf-8")
    cfg = load_config(path)
    assert cfg.timeout_seconds == 5
    assert cfg.memory_mb == 256
    assert cfg.network == "none"


def test_load_config_malformed(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("{{{{", encoding="utf-8")
    with pytest.raises(SandboxConfigError):
        load_config(path)
