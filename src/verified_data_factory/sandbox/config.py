"""Sandbox configuration (Phase 3).

Single source of defaults; nothing is hardcoded through the implementation.
Conceptual YAML::

    sandbox:
      image: verified-data-factory-sandbox:1.0
      timeout_seconds: 10
      memory_mb: 512
      cpus: 1.0
      pids_limit: 64
      max_result_rows: 10000
      max_result_bytes: 1048576
      max_stdout_bytes: 65536
      max_stderr_bytes: 65536
      network: none
      read_only_root: true
      non_root: true
      cap_drop_all: true
      no_new_privileges: true
      single_statement_only: true
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .errors import SandboxConfigError
from .models import SANDBOX_CONFIG_VERSION, ResourceLimits

DEFAULT_IMAGE = "verified-data-factory-sandbox:1.0"


class SandboxConfig(BaseModel):
    model_config = {"frozen": True}

    image: str = Field(default=DEFAULT_IMAGE, min_length=1)
    image_digest: str | None = None
    timeout_seconds: float = Field(default=10.0, gt=0, le=600)
    memory_mb: int = Field(default=512, ge=64, le=16384)
    cpus: float = Field(default=1.0, gt=0, le=32)
    pids_limit: int = Field(default=64, ge=16, le=4096)
    max_result_rows: int = Field(default=10000, ge=1, le=1000000)
    max_result_bytes: int = Field(default=1048576, ge=1024)
    max_stdout_bytes: int = Field(default=65536, ge=1024)
    max_stderr_bytes: int = Field(default=65536, ge=1024)
    network: str = Field(default="none")
    read_only_root: bool = True
    non_root: bool = True
    cap_drop_all: bool = True
    no_new_privileges: bool = True
    single_statement_only: bool = True
    config_version: str = Field(default=SANDBOX_CONFIG_VERSION, min_length=1)

    def resource_limits(self) -> ResourceLimits:
        return ResourceLimits(
            timeout_seconds=self.timeout_seconds,
            memory_mb=self.memory_mb,
            cpus=self.cpus,
            pids_limit=self.pids_limit,
            max_result_rows=self.max_result_rows,
            max_result_bytes=self.max_result_bytes,
            max_stdout_bytes=self.max_stdout_bytes,
            max_stderr_bytes=self.max_stderr_bytes,
        )


def config_from_dict(data: dict[str, Any]) -> SandboxConfig:
    try:
        return SandboxConfig.model_validate(data)
    except Exception as exc:
        raise SandboxConfigError(f"invalid sandbox config: {exc}") from exc


def load_config(path: str | Path) -> SandboxConfig:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise SandboxConfigError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SandboxConfigError(f"config {path} must be a YAML mapping")
    return config_from_dict(data.get("sandbox", data))
