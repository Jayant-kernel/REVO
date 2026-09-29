"""Verification configuration loading (Phase 4).

Conceptual YAML::

    verification:
      hidden_cases: 3
      properties:
        enabled: true
      metamorphic:
        enabled: true
      mutation:
        enabled: true
        max_mutations: 20
        min_score: 0.9
      performance:
        enabled: true
        warn_after_ms: null
      comparison:
        float_abs_tol: 1e-9
        float_rel_tol: 1e-7
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import VerificationConfigError
from .models import ComparisonPolicy, VerificationConfig


def config_from_dict(data: dict[str, Any]) -> VerificationConfig:
    section = data.get("verification", data)
    if not isinstance(section, dict):
        raise VerificationConfigError("verification config must be a mapping")
    try:
        kwargs: dict[str, Any] = {}
        if "hidden_cases" in section:
            kwargs["hidden_cases"] = section["hidden_cases"]
        props = section.get("properties", {})
        if isinstance(props, dict) and "enabled" in props:
            kwargs["properties_enabled"] = props["enabled"]
        meta = section.get("metamorphic", {})
        if isinstance(meta, dict) and "enabled" in meta:
            kwargs["metamorphic_enabled"] = meta["enabled"]
        mut = section.get("mutation", {})
        if isinstance(mut, dict):
            if "enabled" in mut:
                kwargs["mutation_enabled"] = mut["enabled"]
            if "max_mutations" in mut:
                kwargs["max_mutations"] = mut["max_mutations"]
            if "min_score" in mut:
                kwargs["mutation_min_score"] = mut["min_score"]
        perf = section.get("performance", {})
        if isinstance(perf, dict):
            if "enabled" in perf:
                kwargs["performance_enabled"] = perf["enabled"]
            if "warn_after_ms" in perf:
                kwargs["performance_warn_after_ms"] = perf["warn_after_ms"]
        comp = section.get("comparison", {})
        if isinstance(comp, dict) and comp:
            kwargs["comparison"] = ComparisonPolicy.model_validate(comp)
        return VerificationConfig(**kwargs)
    except VerificationConfigError:
        raise
    except Exception as exc:
        raise VerificationConfigError(f"invalid verification config: {exc}") from exc


def load_verification_config(path: str | Path) -> VerificationConfig:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise VerificationConfigError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise VerificationConfigError(f"config {path} must be a YAML mapping")
    return config_from_dict(data)
