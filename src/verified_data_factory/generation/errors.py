"""Domain exceptions for Candidate Generation (Phase 2).

Two failure classes are kept strictly separate:

- provider/network failures (transient vs permanent) -> may be retried
- unusable model output (parse failures) -> NEVER retried as provider work
"""

from __future__ import annotations


class GenerationError(Exception):
    """Base error for all Generation layer failures."""


class ProviderError(GenerationError):
    """Base error for model-provider call failures."""


class TransientProviderError(ProviderError):
    """Retryable: timeouts, connection errors, 429, 5xx."""


class PermanentProviderError(ProviderError):
    """Non-retryable: auth errors, 400-class errors, malformed responses."""


class ProviderTimeoutError(TransientProviderError):
    """The provider call exceeded the configured timeout."""


class ProviderConfigurationError(GenerationError):
    """Bad endpoint/config (missing base URL, unknown provider name, ...)."""
