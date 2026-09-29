"""Devstral candidate provider (Phase 2).

Model: ``alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest`` served from a
self-hosted OpenAI-compatible endpoint. Interchangeable with any other
provider. License/provenance review for commercial use is tracked per
``docs/licensing.md`` and is NOT established by this adapter existing.
"""

from __future__ import annotations

import httpx

from ..provider import OpenAICompatibleProvider

MODEL_ID = "alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest"


class DevstralProvider(OpenAICompatibleProvider):
    """Devstral-Small adapter."""

    provider_name = "devstral"

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        model_revision: str = "unspecified",
        timeout_s: float = 120.0,
        max_retries: int = 2,
        retry_backoff_s: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            model_id=MODEL_ID,
            base_url=base_url,
            api_key=api_key,
            model_revision=model_revision,
            timeout_s=timeout_s,
            max_retries=max_retries,
            retry_backoff_s=retry_backoff_s,
            client=client,
        )
