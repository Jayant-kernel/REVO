"""Generation configuration loading (Phase 2).

YAML shape (conceptual)::

    provider:
      name: qwen
      base_url: http://localhost:8000/v1
      api_key_env: VDF_API_KEY      # never inline secrets; env only
      model_revision: unspecified
      timeout_s: 120
      max_retries: 2
      retry_backoff_s: 1.0
    sampling:
      temperature: 0.4
      top_p: 0.95
      max_tokens: 2048
      seed: 123
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .errors import ProviderConfigurationError
from .models import GenerationConfig


class ProviderEndpoint(BaseModel):
    """Endpoint settings. Secrets come from env, never from files."""

    model_config = {"frozen": True}

    name: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key_env: str | None = None
    model_revision: str = "unspecified"
    timeout_s: float = Field(default=120.0, gt=0)
    max_retries: int = Field(default=2, ge=0)
    retry_backoff_s: float = Field(default=1.0, ge=0)

    def resolve_api_key(self) -> str | None:
        if self.api_key_env is None:
            return None
        return os.environ.get(self.api_key_env)


class GenerationSettings(BaseModel):
    model_config = {"frozen": True}

    provider: ProviderEndpoint
    sampling: GenerationConfig = GenerationConfig()


def settings_from_dict(data: dict[str, Any]) -> GenerationSettings:
    try:
        provider = ProviderEndpoint.model_validate(data["provider"])
    except KeyError as exc:
        raise ProviderConfigurationError(f"missing generation section: {exc}") from exc
    sampling = GenerationConfig.model_validate(data.get("sampling", {}))
    return GenerationSettings(provider=provider, sampling=sampling)


def load_settings(path: str | Path) -> GenerationSettings:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ProviderConfigurationError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProviderConfigurationError(f"settings {path} must be a YAML mapping")
    return settings_from_dict(data)
