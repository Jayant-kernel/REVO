"""Qwen candidate provider (Phase 2).

Model: ``mdq100/Qwen3-Coder-30B-A3B-Instruct:30b`` served from a self-hosted
OpenAI-compatible endpoint. Interchangeable with any other provider.
License/provenance review for commercial use is tracked per
``docs/licensing.md`` and is NOT established by this adapter existing.
"""

from __future__ import annotations

import httpx

from ..provider import OpenAICompatibleProvider

MODEL_ID = "mdq100/Qwen3-Coder-30B-A3B-Instruct:30b"


class QwenProvider(OpenAICompatibleProvider):
    """Qwen3-Coder adapter."""

    provider_name = "qwen"

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        model_id: str = MODEL_ID,
        model_revision: str = "unspecified",
        timeout_s: float = 120.0,
        max_retries: int = 2,
        retry_backoff_s: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            model_id=model_id,
            base_url=base_url,
            api_key=api_key,
            model_revision=model_revision,
            timeout_s=timeout_s,
            max_retries=max_retries,
            retry_backoff_s=retry_backoff_s,
            client=client,
        )
