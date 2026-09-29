"""Provider registry (Phase 2).

Adding a future model = new adapter module + one line here.
No other code changes required.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from ..errors import ProviderConfigurationError
from ..provider import OpenAICompatibleProvider, Provider
from .devstral import DevstralProvider
from .qwen import QwenProvider

PROVIDERS: dict[str, Callable[..., OpenAICompatibleProvider]] = {
    "qwen": QwenProvider,
    "devstral": DevstralProvider,
}

__all__ = ["PROVIDERS", "DevstralProvider", "QwenProvider", "create_provider"]


def create_provider(
    name: str,
    base_url: str,
    api_key: str | None = None,
    model_revision: str = "unspecified",
    timeout_s: float = 120.0,
    max_retries: int = 2,
    retry_backoff_s: float = 1.0,
    client: httpx.Client | None = None,
) -> Provider:
    """Instantiate a named provider. Unknown names raise, never default."""
    try:
        cls = PROVIDERS[name]
    except KeyError as exc:
        raise ProviderConfigurationError(
            f"unknown provider {name!r} (known: {sorted(PROVIDERS)})"
        ) from exc
    return cls(
        base_url=base_url,
        api_key=api_key,
        model_revision=model_revision,
        timeout_s=timeout_s,
        max_retries=max_retries,
        retry_backoff_s=retry_backoff_s,
        client=client,
    )
