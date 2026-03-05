"""Tests for marketplace.model_layer.router — ModelRouter and FallbackChain."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.model_layer.config import ModelLayerConfig, ProviderConfig
from marketplace.model_layer.router import FallbackChain, ModelRouter
from marketplace.model_layer.types import (
    CompletionRequest,
    CompletionResponse,
    ModelHealth,
    ModelProvider,
    ToolCall,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_backend(
    content: str = "ok",
    provider: ModelProvider = ModelProvider.OPENAI,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    fail: bool = False,
    error: Exception | None = None,
) -> MagicMock:
    backend = MagicMock()
    if fail or error is not None:
        backend.complete = AsyncMock(side_effect=error or RuntimeError("backend failure"))
    else:
        backend.complete = AsyncMock(return_value=CompletionResponse(
            content=content,
            model="test-model",
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=50.0,
        ))
    backend.health_check = AsyncMock(return_value=ModelHealth(
        provider=provider, available=True, latency_ms=10.0
    ))
    backend.close = AsyncMock()
    return backend


def _make_config(
    default_provider: ModelProvider = ModelProvider.OPENAI,
    fallback_order: list[ModelProvider] | None = None,
) -> ModelLayerConfig:
    return ModelLayerConfig(
        default_provider=default_provider,
        fallback_order=fallback_order or [ModelProvider.OPENAI],
        foundry_local=ProviderConfig(default_model="phi-4-mini", enabled=True),
        ollama=ProviderConfig(default_model="llama3.2", enabled=True),
        azure_openai=ProviderConfig(default_model="gpt-4o-mini", enabled=True),
        openai=ProviderConfig(default_model="gpt-4o-mini", enabled=True),
    )


# ---------------------------------------------------------------------------
# FallbackChain
# ---------------------------------------------------------------------------


def test_fallback_chain_stores_providers() -> None:
    providers = [ModelProvider.FOUNDRY_LOCAL, ModelProvider.OLLAMA]
    chain = FallbackChain(providers)
    assert chain.providers == providers


def test_fallback_chain_ordering() -> None:
    chain = FallbackChain([
        ModelProvider.FOUNDRY_LOCAL,
        ModelProvider.OLLAMA,
        ModelProvider.AZURE_OPENAI,
        ModelProvider.OPENAI,
    ])
    assert chain.providers[0] == ModelProvider.FOUNDRY_LOCAL
    assert chain.providers[-1] == ModelProvider.OPENAI


def test_fallback_chain_single_provider() -> None:
    chain = FallbackChain([ModelProvider.OPENAI])
    assert len(chain.providers) == 1


def test_fallback_chain_empty_providers() -> None:
    chain = FallbackChain([])
    assert chain.providers == []


# ---------------------------------------------------------------------------
# ModelRouter — register_provider
# ---------------------------------------------------------------------------


def test_register_provider_adds_to_registry() -> None:
    config = _make_config()
    router = ModelRouter(config)
    backend = _make_backend()

    router.register_provider(ModelProvider.OPENAI, backend)

    assert ModelProvider.OPENAI in router._backends
    assert router._backends[ModelProvider.OPENAI] is backend


def test_register_multiple_providers() -> None:
    config = _make_config()
    router = ModelRouter(config)

    openai_backend = _make_backend(provider=ModelProvider.OPENAI)
    ollama_backend = _make_backend(provider=ModelProvider.OLLAMA)

    router.register_provider(ModelProvider.OPENAI, openai_backend)
    router.register_provider(ModelProvider.OLLAMA, ollama_backend)

    assert len(router._backends) == 2


# ---------------------------------------------------------------------------
# ModelRouter — complete
# ---------------------------------------------------------------------------


async def test_complete_routes_to_registered_provider() -> None:
    config = _make_config(fallback_order=[ModelProvider.OPENAI])
    router = ModelRouter(config)
    backend = _make_backend(content="success", provider=ModelProvider.OPENAI)
    router.register_provider(ModelProvider.OPENAI, backend)

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await router.complete(req)

    assert result.content == "success"
    assert result.provider == ModelProvider.OPENAI
    backend.complete.assert_awaited_once()


async def test_complete_fallback_on_first_provider_failure() -> None:
    config = _make_config(
        fallback_order=[ModelProvider.FOUNDRY_LOCAL, ModelProvider.OPENAI]
    )
    router = ModelRouter(config)

    failing_backend = _make_backend(fail=True)
    success_backend = _make_backend(content="fallback response", provider=ModelProvider.OPENAI)

    router.register_provider(ModelProvider.FOUNDRY_LOCAL, failing_backend)
    router.register_provider(ModelProvider.OPENAI, success_backend)

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await router.complete(req)

    assert result.content == "fallback response"
    failing_backend.complete.assert_awaited_once()
    success_backend.complete.assert_awaited_once()


async def test_complete_all_providers_fail_raises_runtime_error() -> None:
    config = _make_config(
        fallback_order=[ModelProvider.FOUNDRY_LOCAL, ModelProvider.OPENAI]
    )
    router = ModelRouter(config)

    router.register_provider(ModelProvider.FOUNDRY_LOCAL, _make_backend(fail=True))
    router.register_provider(ModelProvider.OPENAI, _make_backend(fail=True))

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(RuntimeError, match="All model providers failed"):
        await router.complete(req)


async def test_complete_emits_token_metrics() -> None:
    config = _make_config(fallback_order=[ModelProvider.OPENAI])
    router = ModelRouter(config)
    backend = _make_backend(
        provider=ModelProvider.OPENAI, prompt_tokens=100, completion_tokens=50
    )
    router.register_provider(ModelProvider.OPENAI, backend)

    with patch("marketplace.model_layer.router.MODEL_TOKENS_TOTAL") as mock_metric:
        mock_labels = MagicMock()
        mock_metric.labels.return_value = mock_labels

        req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
        await router.complete(req)

        assert mock_metric.labels.call_count == 2
        # prompt direction
        prompt_call = mock_metric.labels.call_args_list[0]
        assert prompt_call[1]["direction"] == "prompt"
        mock_labels.inc.assert_called()


async def test_complete_skips_unregistered_provider() -> None:
    """Provider in fallback chain but not registered should be skipped silently."""
    config = _make_config(
        fallback_order=[ModelProvider.FOUNDRY_LOCAL, ModelProvider.OPENAI]
    )
    router = ModelRouter(config)
    # Only register OPENAI, not FOUNDRY_LOCAL
    backend = _make_backend(content="only openai", provider=ModelProvider.OPENAI)
    router.register_provider(ModelProvider.OPENAI, backend)

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await router.complete(req)

    assert result.content == "only openai"


async def test_complete_skips_disabled_provider() -> None:
    """Provider registered but disabled in config should be skipped."""
    config = ModelLayerConfig(
        default_provider=ModelProvider.OPENAI,
        fallback_order=[ModelProvider.FOUNDRY_LOCAL, ModelProvider.OPENAI],
        foundry_local=ProviderConfig(default_model="phi-4-mini", enabled=False),
        ollama=ProviderConfig(default_model="llama3.2", enabled=True),
        azure_openai=ProviderConfig(default_model="gpt-4o-mini", enabled=True),
        openai=ProviderConfig(default_model="gpt-4o-mini", enabled=True),
    )
    router = ModelRouter(config)

    disabled_backend = _make_backend(provider=ModelProvider.FOUNDRY_LOCAL)
    active_backend = _make_backend(content="active", provider=ModelProvider.OPENAI)

    router.register_provider(ModelProvider.FOUNDRY_LOCAL, disabled_backend)
    router.register_provider(ModelProvider.OPENAI, active_backend)

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await router.complete(req)

    assert result.content == "active"
    disabled_backend.complete.assert_not_awaited()


async def test_complete_uses_default_model_when_request_model_empty() -> None:
    config = _make_config(fallback_order=[ModelProvider.OPENAI])
    router = ModelRouter(config)
    backend = _make_backend(provider=ModelProvider.OPENAI)
    router.register_provider(ModelProvider.OPENAI, backend)

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}], model="")
    await router.complete(req)

    # The request model should be set to the default_model from config
    call_args = backend.complete.call_args[0][0]
    assert call_args.model == "gpt-4o-mini"


async def test_complete_request_with_tools_passed_through() -> None:
    config = _make_config(fallback_order=[ModelProvider.OPENAI])
    router = ModelRouter(config)
    backend = _make_backend(provider=ModelProvider.OPENAI)
    router.register_provider(ModelProvider.OPENAI, backend)

    tools = [{"type": "function", "function": {"name": "search"}}]
    req = CompletionRequest(
        messages=[{"role": "user", "content": "search for X"}],
        tools=tools,
    )
    await router.complete(req)

    call_args = backend.complete.call_args[0][0]
    assert call_args.tools is tools


async def test_complete_response_has_provider_field() -> None:
    config = _make_config(fallback_order=[ModelProvider.AZURE_OPENAI])
    router = ModelRouter(config)
    backend = _make_backend(provider=ModelProvider.AZURE_OPENAI)
    router.register_provider(ModelProvider.AZURE_OPENAI, backend)

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await router.complete(req)

    assert result.provider == ModelProvider.AZURE_OPENAI


async def test_complete_fallback_logs_failure_warning() -> None:
    config = _make_config(
        fallback_order=[ModelProvider.FOUNDRY_LOCAL, ModelProvider.OPENAI]
    )
    router = ModelRouter(config)
    router.register_provider(ModelProvider.FOUNDRY_LOCAL, _make_backend(fail=True))
    router.register_provider(ModelProvider.OPENAI, _make_backend(provider=ModelProvider.OPENAI))

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    with patch("marketplace.model_layer.router.logger") as mock_logger:
        await router.complete(req)
        # warning should be called for the failed foundry provider
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args[0][0]
        assert "model_provider_failed" in call_kwargs


# ---------------------------------------------------------------------------
# ModelRouter — health_check_all
# ---------------------------------------------------------------------------


async def test_health_check_all_returns_dict() -> None:
    config = _make_config()
    router = ModelRouter(config)
    backend = _make_backend(provider=ModelProvider.OPENAI)
    router.register_provider(ModelProvider.OPENAI, backend)

    results = await router.health_check_all()

    assert isinstance(results, dict)
    assert ModelProvider.OPENAI in results
    assert results[ModelProvider.OPENAI].available is True


async def test_health_check_all_mixed_results() -> None:
    config = _make_config()
    router = ModelRouter(config)

    healthy_backend = _make_backend(provider=ModelProvider.OPENAI)
    down_backend = MagicMock()
    down_backend.health_check = AsyncMock(
        return_value=ModelHealth(provider=ModelProvider.FOUNDRY_LOCAL, available=False, error="down")
    )

    router.register_provider(ModelProvider.OPENAI, healthy_backend)
    router.register_provider(ModelProvider.FOUNDRY_LOCAL, down_backend)

    results = await router.health_check_all()

    assert results[ModelProvider.OPENAI].available is True
    assert results[ModelProvider.FOUNDRY_LOCAL].available is False


# ---------------------------------------------------------------------------
# ModelRouter — close
# ---------------------------------------------------------------------------


async def test_close_closes_all_registered_providers() -> None:
    config = _make_config()
    router = ModelRouter(config)

    backend_a = _make_backend(provider=ModelProvider.OPENAI)
    backend_b = _make_backend(provider=ModelProvider.OLLAMA)

    router.register_provider(ModelProvider.OPENAI, backend_a)
    router.register_provider(ModelProvider.OLLAMA, backend_b)

    await router.close()

    backend_a.close.assert_awaited_once()
    backend_b.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# build_model_router_from_settings
# ---------------------------------------------------------------------------


async def test_build_model_router_from_settings_returns_router() -> None:
    from marketplace.model_layer.router import build_model_router_from_settings

    mock_settings = MagicMock()
    mock_settings.model_default_provider = "openai"
    mock_settings.model_fallback_order = "foundry_local,ollama,azure_openai,openai"
    mock_settings.foundry_local_base_url = "http://localhost:5272"
    mock_settings.foundry_local_default_model = "phi-4-mini"
    mock_settings.ollama_base_url = "http://localhost:11434"
    mock_settings.ollama_default_model = "llama3.2"
    mock_settings.openai_model = "gpt-4o-mini"
    mock_settings.openai_api_key = "test-key"

    with patch("marketplace.config.settings", mock_settings):
        router = build_model_router_from_settings()

    assert isinstance(router, ModelRouter)
    assert len(router._backends) == 4


async def test_build_model_router_default_fallback_order() -> None:
    from marketplace.model_layer.router import build_model_router_from_settings

    mock_settings = MagicMock()
    mock_settings.model_default_provider = "azure_openai"
    mock_settings.model_fallback_order = "foundry_local,ollama,azure_openai,openai"
    mock_settings.foundry_local_base_url = "http://localhost:5272"
    mock_settings.foundry_local_default_model = "phi-4-mini"
    mock_settings.ollama_base_url = "http://localhost:11434"
    mock_settings.ollama_default_model = "llama3.2"
    mock_settings.openai_model = "gpt-4o-mini"
    mock_settings.openai_api_key = ""

    with patch("marketplace.config.settings", mock_settings):
        router = build_model_router_from_settings()

    chain = router._fallback_chain
    assert chain.providers[0] == ModelProvider.FOUNDRY_LOCAL
    assert chain.providers[-1] == ModelProvider.OPENAI


async def test_complete_all_fail_error_includes_provider_names() -> None:
    config = _make_config(
        fallback_order=[ModelProvider.FOUNDRY_LOCAL, ModelProvider.OPENAI]
    )
    router = ModelRouter(config)

    router.register_provider(
        ModelProvider.FOUNDRY_LOCAL,
        _make_backend(fail=True, error=RuntimeError("connection timeout")),
    )
    router.register_provider(
        ModelProvider.OPENAI,
        _make_backend(fail=True, error=RuntimeError("auth denied")),
    )

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(RuntimeError) as exc_info:
        await router.complete(req)

    error_text = str(exc_info.value)
    assert "foundry_local" in error_text
    assert "openai" in error_text
