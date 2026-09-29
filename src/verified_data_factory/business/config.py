"""Business configuration and content identities (Phase 8, §23–§24).

Experiment and benchmark identities cover material configuration only —
timestamps, run ids, durations, and machine-local paths never enter them,
following Phase 6 conventions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from verified_data_factory.provenance import content_id

from .errors import BusinessConfigError
from .models import BUSINESS_SCHEMA_VERSION, ArmSpec, ExperimentConfig

EXPERIMENT_NAMESPACE = "BUSINESS_EXPERIMENT"
BENCHMARK_NAMESPACE = "BUSINESS_BENCHMARK"


def experiment_id_for(payload: dict[str, Any]) -> str:
    """Deterministic identity over material experiment configuration."""
    material = {
        "benchmark_id": payload["benchmark_id"],
        "baseline": payload["baseline"],
        "control": payload.get("control"),
        "treatment": payload["treatment"],
        "evaluation_config": payload.get("evaluation_config", {}),
        "seeds": payload.get("seeds", []),
        "scoring_method": payload.get("scoring_method", ""),
        "prompt_version": payload.get("prompt_version", ""),
        "experiment_version": payload.get("experiment_version", ""),
    }
    return content_id(EXPERIMENT_NAMESPACE, BUSINESS_SCHEMA_VERSION, material)


def benchmark_id_for(
    *,
    record_ids: list[str],
    benchmark_version: str,
    evaluation_policy: str,
    scoring_policy: str,
) -> str:
    """Deterministic benchmark identity over membership + policies."""
    return content_id(
        BENCHMARK_NAMESPACE,
        BUSINESS_SCHEMA_VERSION,
        {
            "benchmark_version": benchmark_version,
            "evaluation_policy": evaluation_policy,
            "record_ids": sorted(set(record_ids)),
            "scoring_policy": scoring_policy,
        },
    )


def benchmark_fingerprint(record_ids: list[str]) -> str:
    """Membership fingerprint used to detect silent benchmark changes."""
    return content_id(
        BENCHMARK_NAMESPACE + "/MEMBERSHIP", BUSINESS_SCHEMA_VERSION, sorted(set(record_ids))
    )


def _arm_from_dict(data: dict[str, Any], name: str) -> ArmSpec:
    section = data.get(name)
    if not isinstance(section, dict):
        raise BusinessConfigError(f"experiment config needs a {name!r} mapping")
    try:
        return ArmSpec.model_validate(section)
    except Exception as exc:
        raise BusinessConfigError(f"invalid experiment arm {name!r}: {exc}") from exc


def experiment_config_from_dict(data: dict[str, Any]) -> ExperimentConfig:
    """Build an ExperimentConfig; the id is derived, never supplied."""
    section = data.get("experiment", data)
    if not isinstance(section, dict):
        raise BusinessConfigError("experiment config must be a mapping")
    for key in ("benchmark_id", "baseline", "treatment", "experiment_version", "scoring_method"):
        if key not in section:
            raise BusinessConfigError(f"experiment config missing {key!r}")
    arm_payload = {
        "benchmark_id": section["benchmark_id"],
        "baseline": _arm_from_dict(section, "baseline").model_dump(mode="json"),
        "treatment": _arm_from_dict(section, "treatment").model_dump(mode="json"),
        "evaluation_config": section.get("evaluation_config", {}),
        "seeds": section.get("seeds", []),
        "scoring_method": section.get("scoring_method", ""),
        "prompt_version": section.get("prompt_version", ""),
        "experiment_version": section.get("experiment_version", ""),
    }
    if section.get("control") is not None:
        arm_payload["control"] = _arm_from_dict(section, "control").model_dump(mode="json")
    try:
        return ExperimentConfig(
            experiment_id=experiment_id_for({**arm_payload, "control": arm_payload.get("control")}),
            experiment_version=str(section["experiment_version"]),
            benchmark_id=str(section["benchmark_id"]),
            baseline=_arm_from_dict(section, "baseline"),
            control=_arm_from_dict(section, "control") if section.get("control") else None,
            treatment=_arm_from_dict(section, "treatment"),
            evaluation_config=dict(section.get("evaluation_config", {})),
            seeds=list(section.get("seeds", [])),
            scoring_method=str(section.get("scoring_method", "")),
            prompt_version=str(section.get("prompt_version", "")),
            code_revision=section.get("code_revision"),
            environment=section.get("environment"),
        )
    except BusinessConfigError:
        raise
    except Exception as exc:
        raise BusinessConfigError(f"invalid experiment config: {exc}") from exc


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise BusinessConfigError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BusinessConfigError(f"config {path} must be a YAML mapping")
    return experiment_config_from_dict(data)
