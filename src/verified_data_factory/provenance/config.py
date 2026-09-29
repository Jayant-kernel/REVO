"""Provenance layer configuration (versioned, YAML-loadable)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import ProvenanceConfigError
from .models import ProvenanceConfig


def config_from_dict(data: dict[str, Any]) -> ProvenanceConfig:
    section = data.get("provenance", data)
    if not isinstance(section, dict):
        raise ProvenanceConfigError("provenance config must be a mapping")
    try:
        return ProvenanceConfig.model_validate(section)
    except Exception as exc:
        raise ProvenanceConfigError(f"invalid provenance config: {exc}") from exc


def load_provenance_config(path: str | Path) -> ProvenanceConfig:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ProvenanceConfigError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProvenanceConfigError(f"config {path} must be a YAML mapping")
    return config_from_dict(data)
