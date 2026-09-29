"""Test-only fake provider (Phase 2).

``FakeProvider`` returns scripted outputs without any model, server, or
network — the entire Phase 2 suite runs offline. NEVER used in production
paths; the CLI exposes it only via an explicit ``--provider fake`` flag
for smoke tests.
"""

from __future__ import annotations

import time
from typing import Any

from .errors import PermanentProviderError, ProviderError
from .models import GenerationConfig, GenerationResponse, TokenUsage
from .provider import Provider

ScriptItem = str | Exception | dict[str, Any]


class FakeProvider(Provider):
    """Scripted provider: pop items from ``script`` per call."""

    provider_name = "fake"

    def __init__(
        self,
        model_id: str = "fake/test-model",
        model_revision: str = "fake-rev-0",
        script: list[ScriptItem] | None = None,
        default_text: str = "SELECT 1;",
        latency_ms: int = 0,
    ) -> None:
        self.model_id = model_id
        self._model_revision = model_revision
        self._script: list[ScriptItem] = list(script) if script else []
        self._default_text = default_text
        self._latency_ms = latency_ms
        self.calls: list[dict[str, Any]] = []

    def generate(self, prompt: str, generation_config: GenerationConfig) -> GenerationResponse:
        self.calls.append({"prompt": prompt, "config": generation_config})
        if self._latency_ms:
            time.sleep(self._latency_ms / 1000)
        item: ScriptItem = self._script.pop(0) if self._script else self._default_text
        if isinstance(item, Exception):
            if isinstance(item, ProviderError):
                raise item
            raise PermanentProviderError(f"fake failure: {item}") from item
        if isinstance(item, dict):
            raise PermanentProviderError(f"malformed fake item: {item!r}")
        return GenerationResponse(
            raw_text=item,
            model=self.model_id,
            model_revision=self._model_revision,
            finish_reason="stop",
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            generation_time_ms=self._latency_ms,
            provider_metadata={"fake": True},
        )
