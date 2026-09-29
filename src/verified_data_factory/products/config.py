"""Product configuration loading and content identities (Phase 7, §41).

``ProductConfig`` and ``SplitPolicy`` are content-addressed with the
Phase 6 hash/canonicalization standards: ``config_id`` covers the
canonical payload only — file paths and timestamps never enter it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from verified_data_factory.provenance import canonical_bytes, content_id, hash_bytes

from .errors import ProductConfigError
from .models import PRODUCT_SCHEMA_VERSION, ProductConfig, SplitPolicy


def product_config_id(config: ProductConfig) -> str:
    """Deterministic content identity for a product configuration."""
    return content_id("PRODUCT_CONFIG", PRODUCT_SCHEMA_VERSION, config.model_dump(mode="json"))


def split_policy_id(policy: SplitPolicy) -> str:
    """Deterministic content identity for a split policy."""
    return content_id("SPLIT_POLICY", PRODUCT_SCHEMA_VERSION, policy.model_dump(mode="json"))


def config_from_dict(data: dict[str, Any]) -> ProductConfig:
    section = data.get("product", data)
    if not isinstance(section, dict):
        raise ProductConfigError("product config must be a mapping")
    if "split_policy" in section and isinstance(section["split_policy"], dict):
        try:
            section = {
                **section,
                "split_policy": SplitPolicy.model_validate(section["split_policy"]),
            }
        except Exception as exc:
            raise ProductConfigError(f"invalid split_policy: {exc}") from exc
    try:
        return ProductConfig.model_validate(section)
    except Exception as exc:
        raise ProductConfigError(f"invalid product config: {exc}") from exc


def load_product_config(path: str | Path) -> ProductConfig:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ProductConfigError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProductConfigError(f"config {path} must be a YAML mapping")
    return config_from_dict(data)


def content_bytes_hash(data: bytes) -> str:
    """Streaming-friendly SHA-256 helper re-export for release files."""
    return hash_bytes(data)


def canonical_product_bytes(value: Any) -> bytes:
    """Canonical bytes for release-identity payloads (Phase 6 standard)."""
    return canonical_bytes(value)
