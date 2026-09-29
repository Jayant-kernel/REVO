"""Model provider abstraction (Phase 2).

``Provider`` is the only interface the rest of the system sees — whether
the candidate came from Qwen, Devstral, or a future model is invisible
downstream. ``OpenAICompatibleProvider`` speaks the ``/chat/completions``
protocol of self-hosted open-weight servers (vLLM-style) without assuming
vLLM is the only runtime: endpoint, model, timeouts, and retries are all
configurable. No proprietary APIs exist in this layer.
"""

from __future__ import annotations

import abc
import hashlib
import time
from typing import Any

import httpx

from .errors import (
    PermanentProviderError,
    ProviderConfigurationError,
    ProviderError,
    ProviderTimeoutError,
    TransientProviderError,
)
from .models import GenerationConfig, GenerationResponse, TokenUsage


class Provider(abc.ABC):
    """Abstract generation backend."""

    model_id: str = ""
    provider_name: str = ""

    @abc.abstractmethod
    def generate(self, prompt: str, generation_config: GenerationConfig) -> GenerationResponse:
        """Generate one completion for ``prompt``."""

    def endpoint_id(self) -> str:
        """Stable, secret-free identifier of this provider configuration."""
        digest = hashlib.sha256(f"{self.provider_name}|{self.model_id}".encode()).hexdigest()[:12]
        return f"{self.provider_name}:{digest}"


class OpenAICompatibleProvider(Provider):
    """Chat-completions client for self-hosted open-weight servers."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        model_id: str,
        base_url: str,
        api_key: str | None = None,
        model_revision: str = "unspecified",
        timeout_s: float = 120.0,
        max_retries: int = 2,
        retry_backoff_s: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url.strip():
            raise ProviderConfigurationError("base_url must be non-empty")
        if timeout_s <= 0:
            raise ProviderConfigurationError("timeout_s must be positive")
        if max_retries < 0:
            raise ProviderConfigurationError("max_retries must be non-negative")
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key  # never copied into candidate metadata
        self._model_revision = model_revision
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._backoff_s = retry_backoff_s
        self._client = client

    def endpoint_id(self) -> str:
        digest = hashlib.sha256(
            f"{self.provider_name}|{self.model_id}|{self.base_url}".encode()
        ).hexdigest()[:12]
        return f"{self.provider_name}:{digest}"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _payload(self, prompt: str, config: GenerationConfig) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_tokens,
        }
        if config.seed is not None:
            body["seed"] = config.seed
        return body

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        client = self._client or httpx.Client(timeout=self._timeout_s)
        close = self._client is None
        try:
            return client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
        finally:
            if close:
                client.close()

    def _parse_response(self, response: httpx.Response, elapsed_ms: int) -> GenerationResponse:
        try:
            data = response.json()
        except ValueError as exc:
            raise PermanentProviderError(f"non-JSON provider response: {exc}") from exc
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise PermanentProviderError(f"malformed provider response: {exc}") from exc
        if not isinstance(content, str):
            raise PermanentProviderError("provider content is not text")
        usage = None
        if isinstance(data.get("usage"), dict):
            u = data["usage"]
            try:
                usage = TokenUsage(
                    prompt_tokens=int(u.get("prompt_tokens", 0)),
                    completion_tokens=int(u.get("completion_tokens", 0)),
                    total_tokens=int(u.get("total_tokens", 0)),
                )
            except (TypeError, ValueError):
                usage = None
        return GenerationResponse(
            raw_text=content,
            model=str(data.get("model", self.model_id)),
            model_revision=self._model_revision,
            finish_reason=str(choice.get("finish_reason", "unknown")),
            token_usage=usage,
            generation_time_ms=elapsed_ms,
            provider_metadata={"base_url": self.base_url},
        )

    def generate(self, prompt: str, generation_config: GenerationConfig) -> GenerationResponse:
        payload = self._payload(prompt, generation_config)
        last_error: ProviderError | None = None
        for attempt in range(self._max_retries + 1):
            started = time.monotonic()
            try:
                response = self._post(payload)
            except httpx.TimeoutException as exc:
                last_error = ProviderTimeoutError(f"provider timed out: {exc}")
            except httpx.HTTPError as exc:
                last_error = TransientProviderError(f"provider transport error: {exc}")
            else:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = TransientProviderError(f"provider status {response.status_code}")
                elif response.status_code >= 400:
                    raise PermanentProviderError(f"provider status {response.status_code}")
                else:
                    return self._parse_response(response, elapsed_ms)
            if attempt < self._max_retries:
                time.sleep(self._backoff_s * (2**attempt))
        assert last_error is not None
        raise last_error
