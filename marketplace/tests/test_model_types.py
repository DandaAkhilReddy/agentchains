"""Tests for marketplace.model_layer.types — enums and dataclasses."""

from __future__ import annotations

import dataclasses

import pytest

from marketplace.model_layer.types import (
    CompletionRequest,
    CompletionResponse,
    ModelHealth,
    ModelProvider,
    ModelSpec,
    ToolCall,
)


# ---------------------------------------------------------------------------
# ModelProvider
# ---------------------------------------------------------------------------


def test_model_provider_has_all_four_values() -> None:
    values = {p.value for p in ModelProvider}
    assert values == {"foundry_local", "ollama", "azure_openai", "openai"}


def test_model_provider_is_string_enum() -> None:
    assert isinstance(ModelProvider.OPENAI, str)
    assert str(ModelProvider.OPENAI) == "ModelProvider.OPENAI"
    # The value itself is a str
    assert ModelProvider.OPENAI.value == "openai"


def test_model_provider_string_comparison() -> None:
    # str Enum allows direct value comparison
    assert ModelProvider.FOUNDRY_LOCAL == "foundry_local"
    assert ModelProvider.OLLAMA == "ollama"
    assert ModelProvider.AZURE_OPENAI == "azure_openai"


def test_model_provider_construction_from_string() -> None:
    assert ModelProvider("openai") is ModelProvider.OPENAI
    assert ModelProvider("foundry_local") is ModelProvider.FOUNDRY_LOCAL


# ---------------------------------------------------------------------------
# ModelSpec
# ---------------------------------------------------------------------------


def test_model_spec_defaults() -> None:
    spec = ModelSpec(provider=ModelProvider.OPENAI, model_id="gpt-4o")
    assert spec.max_tokens == 4096
    assert spec.temperature == 0.7
    assert spec.timeout_seconds == 30.0


def test_model_spec_is_frozen_cannot_mutate() -> None:
    spec = ModelSpec(provider=ModelProvider.OPENAI, model_id="gpt-4o")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        spec.max_tokens = 8192  # type: ignore[misc]


def test_model_spec_equality() -> None:
    spec_a = ModelSpec(provider=ModelProvider.OLLAMA, model_id="llama3.2")
    spec_b = ModelSpec(provider=ModelProvider.OLLAMA, model_id="llama3.2")
    assert spec_a == spec_b


def test_model_spec_inequality_different_model_id() -> None:
    spec_a = ModelSpec(provider=ModelProvider.OLLAMA, model_id="llama3.2")
    spec_b = ModelSpec(provider=ModelProvider.OLLAMA, model_id="mistral")
    assert spec_a != spec_b


def test_model_spec_custom_values() -> None:
    spec = ModelSpec(
        provider=ModelProvider.AZURE_OPENAI,
        model_id="gpt-4o-mini",
        max_tokens=2048,
        temperature=0.0,
        timeout_seconds=60.0,
    )
    assert spec.max_tokens == 2048
    assert spec.temperature == 0.0
    assert spec.timeout_seconds == 60.0


# ---------------------------------------------------------------------------
# CompletionRequest
# ---------------------------------------------------------------------------


def test_completion_request_defaults() -> None:
    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    assert req.model == ""
    assert req.tools is None
    assert req.max_tokens == 4096
    assert req.temperature == 0.7


def test_completion_request_with_tools() -> None:
    tools = [{"type": "function", "function": {"name": "get_weather"}}]
    req = CompletionRequest(
        messages=[{"role": "user", "content": "What is the weather?"}],
        tools=tools,
    )
    assert req.tools is tools
    assert len(req.tools) == 1


def test_completion_request_is_mutable() -> None:
    req = CompletionRequest(messages=[])
    req.model = "gpt-4o"
    assert req.model == "gpt-4o"


# ---------------------------------------------------------------------------
# ToolCall
# ---------------------------------------------------------------------------


def test_tool_call_fields() -> None:
    tc = ToolCall(id="call_abc123", name="get_weather", arguments='{"city": "London"}')
    assert tc.id == "call_abc123"
    assert tc.name == "get_weather"
    assert tc.arguments == '{"city": "London"}'


def test_tool_call_is_dataclass() -> None:
    assert dataclasses.is_dataclass(ToolCall)


# ---------------------------------------------------------------------------
# CompletionResponse
# ---------------------------------------------------------------------------


def test_completion_response_defaults_all_numeric_zero() -> None:
    resp = CompletionResponse(content="Hello!")
    assert resp.prompt_tokens == 0
    assert resp.completion_tokens == 0
    assert resp.latency_ms == 0.0
    assert resp.cost_usd == 0.0


def test_completion_response_tool_calls_defaults_to_empty_list() -> None:
    resp = CompletionResponse(content="")
    assert resp.tool_calls == []
    assert isinstance(resp.tool_calls, list)


def test_completion_response_tool_calls_are_independent_instances() -> None:
    """Each CompletionResponse must get its own tool_calls list (no shared mutable default)."""
    resp_a = CompletionResponse(content="a")
    resp_b = CompletionResponse(content="b")
    resp_a.tool_calls.append(ToolCall(id="1", name="fn", arguments="{}"))
    assert len(resp_b.tool_calls) == 0


def test_completion_response_default_model_and_provider() -> None:
    resp = CompletionResponse(content="test")
    assert resp.model == ""
    assert resp.provider == ModelProvider.AZURE_OPENAI


def test_completion_response_with_all_fields() -> None:
    tc = ToolCall(id="id1", name="search", arguments="{}")
    resp = CompletionResponse(
        content="result",
        tool_calls=[tc],
        model="gpt-4o-mini",
        provider=ModelProvider.OPENAI,
        prompt_tokens=100,
        completion_tokens=50,
        latency_ms=123.4,
        cost_usd=0.0002,
    )
    assert resp.content == "result"
    assert len(resp.tool_calls) == 1
    assert resp.prompt_tokens == 100
    assert resp.completion_tokens == 50
    assert resp.latency_ms == pytest.approx(123.4)
    assert resp.cost_usd == pytest.approx(0.0002)


# ---------------------------------------------------------------------------
# ModelHealth
# ---------------------------------------------------------------------------


def test_model_health_defaults() -> None:
    health = ModelHealth(provider=ModelProvider.FOUNDRY_LOCAL, available=True)
    assert health.latency_ms == 0.0
    assert health.error == ""


def test_model_health_unavailable_with_error() -> None:
    health = ModelHealth(
        provider=ModelProvider.OLLAMA,
        available=False,
        error="Connection refused",
    )
    assert health.available is False
    assert health.error == "Connection refused"


def test_model_health_is_dataclass() -> None:
    assert dataclasses.is_dataclass(ModelHealth)
