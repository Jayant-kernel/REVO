"""Quality configuration (Phase 5).

Single source of policy values; nothing hardcoded across modules.
Conceptual YAML::

    quality:
      mutation_min_score: 0.9
      require_strong_verification: true
      family_quotas: {simple_joins: 100}
      max_family_share: null
      audit_rate: 0.2
      audit_seed: 42
      risk_threshold_high: 5
      risk_threshold_medium: 2
      rare_family_threshold: 0.05
      contamination_block_exact_private_eval: true
      contamination_block_known_source: true
      known_source_hashes: []
      selection_seed: 42
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .errors import QualityConfigError
from .models import QUALITY_CONFIG_VERSION

DEFAULT_RISK_WEIGHTS = {
    "ambiguity": 2,
    "weak_verification": 3,
    "mutation_survived": 2,
    "contamination_soft": 3,
    "rare_family": 2,
    "rare_edge_case": 1,
    "duplicate_non_representative": 1,
    "first_of_template": 1,
}


class QualityConfig(BaseModel):
    model_config = {"frozen": True}

    mutation_min_score: float = Field(default=0.9, ge=0, le=1)
    require_strong_verification: bool = True
    family_quotas: dict[str, int] = Field(default_factory=dict)
    max_family_share: float | None = Field(default=None, gt=0, le=1)
    audit_rate: float = Field(default=0.2, ge=0, le=1)
    audit_seed: int = 42
    risk_weights: dict[str, int] = Field(default_factory=lambda: dict(DEFAULT_RISK_WEIGHTS))
    risk_threshold_high: int = Field(default=5, ge=0)
    risk_threshold_medium: int = Field(default=2, ge=0)
    rare_family_threshold: float = Field(default=0.05, ge=0, le=1)
    contamination_block_exact_private_eval: bool = True
    contamination_block_known_source: bool = True
    known_source_hashes: list[str] = Field(default_factory=list)
    selection_seed: int = 42
    config_version: str = Field(default=QUALITY_CONFIG_VERSION, min_length=1)


def config_from_dict(data: dict[str, Any]) -> QualityConfig:
    section = data.get("quality", data)
    if not isinstance(section, dict):
        raise QualityConfigError("quality config must be a mapping")
    try:
        return QualityConfig.model_validate(section)
    except Exception as exc:
        raise QualityConfigError(f"invalid quality config: {exc}") from exc


def load_quality_config(path: str | Path) -> QualityConfig:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise QualityConfigError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise QualityConfigError(f"config {path} must be a YAML mapping")
    return config_from_dict(data)
