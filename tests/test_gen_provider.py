"""Provider tests via FakeProvider + httpx MockTransport (fully offline)."""

import httpx
import pytest

from verified_data_factory.generation import (
    PROVIDERS,
    FakeProvider,
    GenerationConfig,
    QwenProvider,
    create_provider,
)
from verified_data_factory.generation.errors import (
    PermanentProviderError,
    ProviderConfigurationError,
    ProviderTimeoutError,
    TransientProviderError,
)
from verified_data_factory.generation.provider import OpenAICompatibleProvider

CONFIG = GenerationConfig()


def _completion(text="SELECT 1;", usage=None):
    body = {
        "model": "test-model",
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
    }
    if usage is not None:
        body["usage"] = usage
    return body


def _client(handler, timeout=30.0):
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout)


def test_adapters_registered_and_interchangeable():
    assert set(PROVIDERS) == {"qwen", "devstral"}
    qwen = create_provider("qwen", base_url="http://localhost:8000/v1")
    devstral = create_provider("devstral", base_url="http://localhost:8000/v1")
    assert isinstance(qwen, QwenProvider)
    assert qwen.model_id == "mdq100/Qwen3-Coder-30B-A3B-Instruct:30b"
    assert (
        devstral.model_id == "alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest"
    )
    assert qwen.endpoint_id() != devstral.endpoint_id()
    with pytest.raises(ProviderConfigurationError):
        create_provider("gpt4", base_url="http://x/v1")


def test_no_proprietary_providers():
    import verified_data_factory.generation.providers as providers_pkg

    names = " ".join(PROVIDERS) + providers_pkg.__name__
    for banned in ("openai_api", "anthropic", "gemini"):
        assert banned not in names


def test_success_with_metadata():
    def handler(request):
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, json=_completion(usage={"a": 1}))

    provider = QwenProvider(base_url="http://t/v1", client=_client(handler))
    response = provider.generate("prompt", CONFIG)
    assert response.raw_text == "SELECT 1;"
    assert response.model_revision == "unspecified"
    assert response.finish_reason == "stop"
    assert response.token_usage is not None  # coerced with defaults
    assert response.provider_metadata["base_url"] == "http://t/v1"


def test_retry_then_success():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json=_completion())

    provider = QwenProvider(
        base_url="http://t/v1", client=_client(handler), max_retries=2, retry_backoff_s=0
    )
    assert provider.generate("prompt", CONFIG).raw_text == "SELECT 1;"
    assert len(calls) == 2


def test_retry_limit_exhausted():
    def handler(request):
        return httpx.Response(500, json={})

    provider = QwenProvider(
        base_url="http://t/v1", client=_client(handler), max_retries=2, retry_backoff_s=0
    )
    with pytest.raises(TransientProviderError):
        provider.generate("prompt", CONFIG)


def test_permanent_failure_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, json={})

    provider = QwenProvider(
        base_url="http://t/v1", client=_client(handler), max_retries=3, retry_backoff_s=0
    )
    with pytest.raises(PermanentProviderError):
        provider.generate("prompt", CONFIG)
    assert len(calls) == 1


def test_malformed_response_is_permanent():
    def handler(request):
        return httpx.Response(200, json={"nope": True})

    provider = QwenProvider(base_url="http://t/v1", client=_client(handler))
    with pytest.raises(PermanentProviderError):
        provider.generate("prompt", CONFIG)


def test_transport_timeout_maps_to_timeout_error(monkeypatch):
    provider = QwenProvider(
        base_url="http://t/v1",
        client=_client(lambda request: httpx.Response(200, json=_completion())),
        max_retries=1,
        retry_backoff_s=0,
    )

    def boom(payload):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(provider, "_post", boom)
    with pytest.raises(ProviderTimeoutError):
        provider.generate("prompt", CONFIG)


def test_transport_error_is_transient(monkeypatch):
    provider = QwenProvider(
        base_url="http://t/v1",
        client=_client(lambda request: httpx.Response(200, json=_completion())),
        max_retries=0,
    )
    monkeypatch.setattr(
        provider, "_post", lambda payload: (_ for _ in ()).throw(httpx.ConnectError("down"))
    )
    with pytest.raises(TransientProviderError):
        provider.generate("prompt", CONFIG)


def test_bad_configuration_rejected():
    with pytest.raises(ProviderConfigurationError):
        QwenProvider(base_url="  ")
    with pytest.raises(ProviderConfigurationError):
        QwenProvider(base_url="http://t/v1", timeout_s=0)
    with pytest.raises(ProviderConfigurationError):
        QwenProvider(base_url="http://t/v1", max_retries=-1)


def test_fake_provider_success_and_call_log():
    fake = FakeProvider(script=["SELECT a FROM t;"])
    response = fake.generate("prompt", CONFIG)
    assert response.raw_text == "SELECT a FROM t;"
    assert fake.calls[0]["prompt"] == "prompt"
    assert fake.calls[0]["config"] == CONFIG


def test_fake_provider_empty_and_malformed():
    assert FakeProvider(script=["   "]).generate("p", CONFIG).raw_text.strip() == ""
    with pytest.raises(PermanentProviderError):
        FakeProvider(script=[{"weird": 1}]).generate("p", CONFIG)
    with pytest.raises(TransientProviderError):
        FakeProvider(script=[TransientProviderError("boom")]).generate("p", CONFIG)


def test_openai_compatible_base_is_generic():
    assert OpenAICompatibleProvider.provider_name == "openai_compatible"
    assert QwenProvider.provider_name == "qwen"
