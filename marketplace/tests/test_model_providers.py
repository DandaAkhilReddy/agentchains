"""Tests for marketplace.model_layer.providers — all 4 provider backends."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from marketplace.model_layer.config import ProviderConfig
from marketplace.model_layer.providers.foundry_local import FoundryLocalBackend
from marketplace.model_layer.providers.ollama import OllamaBackend
from marketplace.model_layer.types import (
    CompletionRequest,
    ModelProvider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_openai_response(
    content: str = "Hello!",
    model: str = "gpt-4o-mini",
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    tool_calls=None,
) -> MagicMock:
    """Build a mock openai ChatCompletion response object."""
    mock_resp = MagicMock()
    mock_resp.model = model

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    mock_resp.usage = usage

    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls or []

    choice = MagicMock()
    choice.message = message
    mock_resp.choices = [choice]

    return mock_resp


def _make_httpx_response(data: dict, status_code: int = 200) -> MagicMock:
    """Build a fake httpx response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# FoundryLocalBackend
# ---------------------------------------------------------------------------


@pytest.fixture
def foundry_config() -> ProviderConfig:
    return ProviderConfig(
        base_url="http://localhost:5272",
        default_model="phi-4-mini",
        timeout_seconds=30.0,
    )


async def test_foundry_complete_success(foundry_config: ProviderConfig) -> None:
    backend = FoundryLocalBackend(foundry_config)
    response_data = {
        "model": "phi-4-mini",
        "choices": [{"message": {"content": "Hello from Foundry!", "tool_calls": []}}],
        "usage": {"prompt_tokens": 15, "completion_tokens": 25},
    }
    mock_resp = _make_httpx_response(response_data)
    backend._client.post = AsyncMock(return_value=mock_resp)

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await backend.complete(req)

    assert result.content == "Hello from Foundry!"
    assert result.provider == ModelProvider.FOUNDRY_LOCAL
    assert result.model == "phi-4-mini"
    assert result.prompt_tokens == 15
    assert result.completion_tokens == 25
    assert result.tool_calls == []


async def test_foundry_complete_with_tool_calls(foundry_config: ProviderConfig) -> None:
    backend = FoundryLocalBackend(foundry_config)
    response_data = {
        "model": "phi-4-mini",
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": [{
                    "id": "call_xyz",
                    "function": {"name": "search", "arguments": '{"query": "test"}'},
                }],
            }
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    mock_resp = _make_httpx_response(response_data)
    backend._client.post = AsyncMock(return_value=mock_resp)

    req = CompletionRequest(
        messages=[{"role": "user", "content": "search something"}],
        tools=[{"type": "function", "function": {"name": "search"}}],
    )
    result = await backend.complete(req)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_xyz"
    assert result.tool_calls[0].name == "search"
    assert result.tool_calls[0].arguments == '{"query": "test"}'


async def test_foundry_complete_timeout(foundry_config: ProviderConfig) -> None:
    backend = FoundryLocalBackend(foundry_config)
    backend._client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(httpx.TimeoutException):
        await backend.complete(req)


async def test_foundry_complete_http_error_500(foundry_config: ProviderConfig) -> None:
    backend = FoundryLocalBackend(foundry_config)
    mock_resp = _make_httpx_response({}, status_code=500)
    backend._client.post = AsyncMock(return_value=mock_resp)

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(httpx.HTTPStatusError):
        await backend.complete(req)


async def test_foundry_complete_empty_choices_raises(foundry_config: ProviderConfig) -> None:
    """Foundry Local source uses [{}])[0] which raises IndexError on empty choices list."""
    backend = FoundryLocalBackend(foundry_config)
    response_data = {
        "model": "phi-4-mini",
        "choices": [],
        "usage": {},
    }
    mock_resp = _make_httpx_response(response_data)
    backend._client.post = AsyncMock(return_value=mock_resp)

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(IndexError):
        await backend.complete(req)


async def test_foundry_health_check_healthy(foundry_config: ProviderConfig) -> None:
    backend = FoundryLocalBackend(foundry_config)
    mock_resp = _make_httpx_response({"data": []})
    backend._client.get = AsyncMock(return_value=mock_resp)

    health = await backend.health_check()

    assert health.available is True
    assert health.provider == ModelProvider.FOUNDRY_LOCAL
    assert health.error == ""
    assert health.latency_ms >= 0.0


async def test_foundry_health_check_down(foundry_config: ProviderConfig) -> None:
    backend = FoundryLocalBackend(foundry_config)
    backend._client.get = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    health = await backend.health_check()

    assert health.available is False
    assert health.provider == ModelProvider.FOUNDRY_LOCAL
    assert "Connection refused" in health.error


async def test_foundry_close_idempotent(foundry_config: ProviderConfig) -> None:
    backend = FoundryLocalBackend(foundry_config)
    backend._client.aclose = AsyncMock()
    await backend.close()
    backend._client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# OllamaBackend
# ---------------------------------------------------------------------------


@pytest.fixture
def ollama_config() -> ProviderConfig:
    return ProviderConfig(
        base_url="http://localhost:11434",
        default_model="llama3.2",
        timeout_seconds=30.0,
    )


async def test_ollama_complete_success(ollama_config: ProviderConfig) -> None:
    backend = OllamaBackend(ollama_config)
    response_data = {
        "model": "llama3.2",
        "message": {"content": "Hello from Ollama!", "tool_calls": []},
        "prompt_eval_count": 12,
        "eval_count": 18,
    }
    mock_resp = _make_httpx_response(response_data)
    backend._client.post = AsyncMock(return_value=mock_resp)

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await backend.complete(req)

    assert result.content == "Hello from Ollama!"
    assert result.provider == ModelProvider.OLLAMA
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 18


async def test_ollama_complete_with_tools_dict_arguments(ollama_config: ProviderConfig) -> None:
    backend = OllamaBackend(ollama_config)
    response_data = {
        "model": "llama3.2",
        "message": {
            "content": "",
            "tool_calls": [{
                "id": "",
                "function": {"name": "calculator", "arguments": {"x": 1, "y": 2}},
            }],
        },
        "prompt_eval_count": 5,
        "eval_count": 3,
    }
    mock_resp = _make_httpx_response(response_data)
    backend._client.post = AsyncMock(return_value=mock_resp)

    req = CompletionRequest(
        messages=[{"role": "user", "content": "calc"}],
        tools=[{"type": "function", "function": {"name": "calculator"}}],
    )
    result = await backend.complete(req)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "calculator"
    # dict arguments should be JSON-dumped
    parsed = json.loads(result.tool_calls[0].arguments)
    assert parsed == {"x": 1, "y": 2}


async def test_ollama_complete_with_string_arguments(ollama_config: ProviderConfig) -> None:
    backend = OllamaBackend(ollama_config)
    response_data = {
        "model": "llama3.2",
        "message": {
            "content": "",
            "tool_calls": [{
                "id": "tc1",
                "function": {"name": "fn", "arguments": '{"key": "value"}'},
            }],
        },
        "prompt_eval_count": 5,
        "eval_count": 3,
    }
    mock_resp = _make_httpx_response(response_data)
    backend._client.post = AsyncMock(return_value=mock_resp)

    req = CompletionRequest(messages=[{"role": "user", "content": "run"}])
    result = await backend.complete(req)

    assert result.tool_calls[0].arguments == '{"key": "value"}'


async def test_ollama_health_check_healthy(ollama_config: ProviderConfig) -> None:
    backend = OllamaBackend(ollama_config)
    mock_resp = _make_httpx_response({"models": []})
    backend._client.get = AsyncMock(return_value=mock_resp)

    health = await backend.health_check()

    assert health.available is True
    assert health.provider == ModelProvider.OLLAMA
    assert health.latency_ms >= 0.0


async def test_ollama_health_check_down(ollama_config: ProviderConfig) -> None:
    backend = OllamaBackend(ollama_config)
    backend._client.get = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    health = await backend.health_check()

    assert health.available is False
    assert "Connection refused" in health.error


async def test_ollama_num_predict_mapping(ollama_config: ProviderConfig) -> None:
    """max_tokens maps to options.num_predict in the Ollama payload."""
    backend = OllamaBackend(ollama_config)
    response_data = {
        "model": "llama3.2",
        "message": {"content": "ok", "tool_calls": []},
        "prompt_eval_count": 1,
        "eval_count": 1,
    }
    mock_resp = _make_httpx_response(response_data)
    post_mock = AsyncMock(return_value=mock_resp)
    backend._client.post = post_mock

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}], max_tokens=512)
    await backend.complete(req)

    call_kwargs = post_mock.call_args
    payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
    assert payload["options"]["num_predict"] == 512


async def test_ollama_close(ollama_config: ProviderConfig) -> None:
    backend = OllamaBackend(ollama_config)
    backend._client.aclose = AsyncMock()
    await backend.close()
    backend._client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# AzureOpenAIBackend
# ---------------------------------------------------------------------------


@pytest.fixture
def azure_config() -> ProviderConfig:
    return ProviderConfig(
        base_url="https://my-instance.openai.azure.com",
        api_key="test-azure-key",
        default_model="gpt-4o-mini",
        timeout_seconds=30.0,
        max_retries=2,
    )


async def test_azure_complete_success(azure_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    backend = AzureOpenAIBackend(azure_config)
    mock_resp = _make_openai_response(
        content="Azure says hi!", model="gpt-4o-mini", prompt_tokens=20, completion_tokens=10
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    backend._client = mock_client

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await backend.complete(req)

    assert result.content == "Azure says hi!"
    assert result.provider == ModelProvider.AZURE_OPENAI
    assert result.prompt_tokens == 20
    assert result.completion_tokens == 10


async def test_azure_complete_with_tool_calls(azure_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    backend = AzureOpenAIBackend(azure_config)

    mock_tc = MagicMock()
    mock_tc.id = "call_abc"
    mock_tc.function.name = "get_info"
    mock_tc.function.arguments = '{"q": "test"}'

    mock_resp = _make_openai_response(content="", model="gpt-4o-mini")
    mock_resp.choices[0].message.tool_calls = [mock_tc]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    backend._client = mock_client

    req = CompletionRequest(
        messages=[{"role": "user", "content": "use tool"}],
        tools=[{"type": "function"}],
    )
    result = await backend.complete(req)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_abc"
    assert result.tool_calls[0].name == "get_info"


async def test_azure_complete_api_error_raises(azure_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    backend = AzureOpenAIBackend(azure_config)
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API error"))
    backend._client = mock_client

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(RuntimeError, match="API error"):
        await backend.complete(req)


async def test_azure_cost_calculation(azure_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    backend = AzureOpenAIBackend(azure_config)
    mock_resp = _make_openai_response(prompt_tokens=1000, completion_tokens=1000)
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    backend._client = mock_client

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await backend.complete(req)

    # 1000 prompt @ $0.00015/1K + 1000 completion @ $0.0006/1K = 0.00015 + 0.0006 = 0.00075
    expected = (1000 * 0.00015 + 1000 * 0.0006) / 1000
    assert result.cost_usd == pytest.approx(expected, rel=1e-6)


async def test_azure_lazy_client_init(azure_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    backend = AzureOpenAIBackend(azure_config)
    # Before first call, client should be None
    assert backend._client is None


async def test_azure_health_check(azure_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    backend = AzureOpenAIBackend(azure_config)
    mock_client = MagicMock()
    mock_client.models.list = AsyncMock(return_value=MagicMock())
    backend._client = mock_client

    health = await backend.health_check()

    assert health.available is True
    assert health.provider == ModelProvider.AZURE_OPENAI
    assert health.latency_ms >= 0.0


async def test_azure_health_check_failure(azure_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    backend = AzureOpenAIBackend(azure_config)
    mock_client = MagicMock()
    mock_client.models.list = AsyncMock(side_effect=RuntimeError("auth failed"))
    backend._client = mock_client

    health = await backend.health_check()

    assert health.available is False
    assert "auth failed" in health.error


async def test_azure_env_var_fallback() -> None:
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    config = ProviderConfig(base_url="", api_key="", default_model="gpt-4o-mini")
    backend = AzureOpenAIBackend(config)

    with patch.dict(
        "os.environ",
        {
            "AZURE_OPENAI_ENDPOINT": "https://fallback.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "fallback-key",
            "AZURE_OPENAI_API_VERSION": "2024-06-01",
        },
    ):
        with patch("openai.AsyncAzureOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = backend._get_client()
            assert client is not None
            mock_cls.assert_called_once()
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["azure_endpoint"] == "https://fallback.openai.azure.com"
            assert call_kwargs["api_key"] == "fallback-key"


async def test_azure_close_clears_client(azure_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    backend = AzureOpenAIBackend(azure_config)
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    backend._client = mock_client

    await backend.close()

    mock_client.close.assert_awaited_once()
    assert backend._client is None


async def test_azure_close_when_no_client(azure_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    backend = AzureOpenAIBackend(azure_config)
    # Should not raise even if _client is None
    await backend.close()


# ---------------------------------------------------------------------------
# OpenAIBackend
# ---------------------------------------------------------------------------


@pytest.fixture
def openai_config() -> ProviderConfig:
    return ProviderConfig(
        api_key="test-openai-key",
        default_model="gpt-4o-mini",
        timeout_seconds=30.0,
        max_retries=2,
    )


async def test_openai_complete_success(openai_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.openai_provider import OpenAIBackend

    backend = OpenAIBackend(openai_config)
    mock_resp = _make_openai_response(
        content="OpenAI says hi!", model="gpt-4o-mini", prompt_tokens=8, completion_tokens=12
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    backend._client = mock_client

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await backend.complete(req)

    assert result.content == "OpenAI says hi!"
    assert result.provider == ModelProvider.OPENAI
    assert result.prompt_tokens == 8
    assert result.completion_tokens == 12


async def test_openai_health_check_success(openai_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.openai_provider import OpenAIBackend

    backend = OpenAIBackend(openai_config)
    mock_client = MagicMock()
    mock_client.models.list = AsyncMock(return_value=MagicMock())
    backend._client = mock_client

    health = await backend.health_check()

    assert health.available is True
    assert health.provider == ModelProvider.OPENAI


async def test_openai_health_check_failure(openai_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.openai_provider import OpenAIBackend

    backend = OpenAIBackend(openai_config)
    mock_client = MagicMock()
    mock_client.models.list = AsyncMock(side_effect=RuntimeError("no key"))
    backend._client = mock_client

    health = await backend.health_check()

    assert health.available is False
    assert "no key" in health.error


async def test_openai_env_var_fallback() -> None:
    from marketplace.model_layer.providers.openai_provider import OpenAIBackend

    config = ProviderConfig(api_key="", default_model="gpt-4o-mini")
    backend = OpenAIBackend(config)

    with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
        with patch("openai.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            backend._get_client()
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["api_key"] == "env-key"


async def test_openai_cost_calculation(openai_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.openai_provider import OpenAIBackend

    backend = OpenAIBackend(openai_config)
    mock_resp = _make_openai_response(prompt_tokens=2000, completion_tokens=500)
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    backend._client = mock_client

    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    result = await backend.complete(req)

    expected = (2000 * 0.00015 + 500 * 0.0006) / 1000
    assert result.cost_usd == pytest.approx(expected, rel=1e-6)


async def test_openai_lazy_client_init(openai_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.openai_provider import OpenAIBackend

    backend = OpenAIBackend(openai_config)
    assert backend._client is None


async def test_openai_close_clears_client(openai_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.openai_provider import OpenAIBackend

    backend = OpenAIBackend(openai_config)
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    backend._client = mock_client

    await backend.close()

    mock_client.close.assert_awaited_once()
    assert backend._client is None


async def test_openai_close_when_no_client(openai_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.openai_provider import OpenAIBackend

    backend = OpenAIBackend(openai_config)
    # Should not raise
    await backend.close()


async def test_openai_complete_with_tool_calls(openai_config: ProviderConfig) -> None:
    from marketplace.model_layer.providers.openai_provider import OpenAIBackend

    backend = OpenAIBackend(openai_config)

    mock_tc = MagicMock()
    mock_tc.id = "call_openai_1"
    mock_tc.function.name = "list_items"
    mock_tc.function.arguments = '{"limit": 10}'

    mock_resp = _make_openai_response(content="", model="gpt-4o-mini")
    mock_resp.choices[0].message.tool_calls = [mock_tc]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    backend._client = mock_client

    req = CompletionRequest(
        messages=[{"role": "user", "content": "list items"}],
        tools=[{"type": "function"}],
    )
    result = await backend.complete(req)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "list_items"
    assert result.tool_calls[0].arguments == '{"limit": 10}'
