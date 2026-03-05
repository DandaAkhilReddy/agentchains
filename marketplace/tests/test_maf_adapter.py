"""Tests for marketplace.model_layer.maf_adapter — MAFAdapter and MAFAgentManifest."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from marketplace.model_layer.maf_adapter import MAFAdapter, MAFAgentManifest
from marketplace.model_layer.types import (
    CompletionRequest,
    CompletionResponse,
    ModelProvider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_router(response: CompletionResponse | None = None) -> MagicMock:
    router = MagicMock()
    router.complete = AsyncMock(
        return_value=response or CompletionResponse(
            content="Router says hi",
            model="gpt-4o-mini",
            provider=ModelProvider.OPENAI,
            prompt_tokens=10,
            completion_tokens=5,
        )
    )
    return router


def _basic_manifest(name: str = "TestAgent") -> dict:
    return {
        "name": name,
        "description": "A test agent",
        "version": "1.2.3",
        "skills": [{"id": "skill_a"}, {"id": "skill_b"}],
        "model_preferences": {"model": "gpt-4o-mini"},
        "tools": [],
    }


# ---------------------------------------------------------------------------
# MAFAgentManifest — parsing
# ---------------------------------------------------------------------------


def test_parse_maf_manifest_valid_dict() -> None:
    raw = {
        "name": "MyAgent",
        "description": "Does things",
        "version": "2.0.0",
        "skills": [{"id": "skill1"}],
        "model_preferences": {"model": "phi-4-mini"},
        "tools": [{"type": "function"}],
    }
    manifest = MAFAgentManifest(raw)

    assert manifest.name == "MyAgent"
    assert manifest.description == "Does things"
    assert manifest.version == "2.0.0"
    assert len(manifest.skills) == 1
    assert manifest.model_preferences == {"model": "phi-4-mini"}
    assert len(manifest.tools) == 1


def test_parse_manifest_missing_optional_fields_uses_defaults() -> None:
    """Manifest with only required/missing fields should still parse without error."""
    manifest = MAFAgentManifest({})

    assert manifest.name == ""
    assert manifest.description == ""
    assert manifest.version == "1.0.0"
    assert manifest.skills == []
    assert manifest.model_preferences == {}
    assert manifest.tools == []


def test_parse_manifest_preserves_raw() -> None:
    raw = {"name": "Raw", "custom_field": "value"}
    manifest = MAFAgentManifest(raw)
    assert manifest._raw is raw


def test_manifest_with_system_prompt_in_model_preferences() -> None:
    raw = {
        "name": "PromptAgent",
        "model_preferences": {"model": "gpt-4o", "system_prompt": "You are helpful."},
    }
    manifest = MAFAgentManifest(raw)
    assert manifest.model_preferences["system_prompt"] == "You are helpful."


# ---------------------------------------------------------------------------
# MAFAdapter — register and get manifest
# ---------------------------------------------------------------------------


def test_register_manifest_stores_it() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)

    raw = _basic_manifest("SearchAgent")
    result = adapter.register_manifest("agent-001", raw)

    assert isinstance(result, MAFAgentManifest)
    assert result.name == "SearchAgent"
    assert "agent-001" in adapter._agents


def test_register_manifest_returns_parsed_manifest() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)

    raw = _basic_manifest()
    returned = adapter.register_manifest("id-1", raw)

    assert returned is adapter._agents["id-1"]


def test_get_manifest_returns_existing() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)

    adapter.register_manifest("agent-x", _basic_manifest("X"))
    manifest = adapter.get_manifest("agent-x")

    assert manifest is not None
    assert manifest.name == "X"


def test_get_manifest_not_found_returns_none() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)

    result = adapter.get_manifest("nonexistent")

    assert result is None


# ---------------------------------------------------------------------------
# MAFAdapter — invoke
# ---------------------------------------------------------------------------


async def test_invoke_agent_calls_router_complete() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)
    adapter.register_manifest("agent-1", _basic_manifest("Agent1"))

    messages = [{"role": "user", "content": "hello"}]
    result = await adapter.invoke("agent-1", messages)

    assert result.content == "Router says hi"
    router.complete.assert_awaited_once()


async def test_invoke_unregistered_agent_still_works_with_empty_model() -> None:
    """Unregistered agent: model defaults to empty string, tools stay as passed."""
    router = _make_router()
    adapter = MAFAdapter(router)

    messages = [{"role": "user", "content": "hi"}]
    result = await adapter.invoke("unknown-agent", messages)

    assert isinstance(result, CompletionResponse)
    call_args: CompletionRequest = router.complete.call_args[0][0]
    assert call_args.model == ""


async def test_invoke_uses_model_preference_from_manifest() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)

    raw = {
        "name": "PrefAgent",
        "model_preferences": {"model": "phi-4-mini"},
        "tools": [],
    }
    adapter.register_manifest("pref-agent", raw)
    messages = [{"role": "user", "content": "go"}]
    await adapter.invoke("pref-agent", messages)

    call_req: CompletionRequest = router.complete.call_args[0][0]
    assert call_req.model == "phi-4-mini"


async def test_invoke_with_tools_merges_manifest_tools() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)

    manifest_tools = [{"type": "function", "function": {"name": "manifest_tool"}}]
    caller_tools = [{"type": "function", "function": {"name": "caller_tool"}}]

    raw = {"name": "ToolAgent", "tools": manifest_tools, "model_preferences": {}}
    adapter.register_manifest("tool-agent", raw)

    messages = [{"role": "user", "content": "use tools"}]
    await adapter.invoke("tool-agent", messages, tools=caller_tools)

    call_req: CompletionRequest = router.complete.call_args[0][0]
    assert call_req.tools is not None
    tool_names = [t["function"]["name"] for t in call_req.tools]
    assert "manifest_tool" in tool_names
    assert "caller_tool" in tool_names


async def test_invoke_no_tools_passes_none() -> None:
    """When manifest has no tools and caller passes none, tools should be None."""
    router = _make_router()
    adapter = MAFAdapter(router)

    raw = {"name": "NoTools", "tools": [], "model_preferences": {}}
    adapter.register_manifest("no-tools", raw)

    messages = [{"role": "user", "content": "hi"}]
    await adapter.invoke("no-tools", messages)

    call_req: CompletionRequest = router.complete.call_args[0][0]
    assert call_req.tools is None


async def test_invoke_returns_completion_response() -> None:
    expected = CompletionResponse(
        content="structured reply",
        model="phi-4-mini",
        provider=ModelProvider.FOUNDRY_LOCAL,
        prompt_tokens=20,
        completion_tokens=10,
    )
    router = _make_router(response=expected)
    adapter = MAFAdapter(router)
    adapter.register_manifest("agent-2", _basic_manifest())

    result = await adapter.invoke("agent-2", [{"role": "user", "content": "hi"}])

    assert result is expected
    assert result.content == "structured reply"
    assert result.provider == ModelProvider.FOUNDRY_LOCAL


# ---------------------------------------------------------------------------
# MAFAdapter — list_agents
# ---------------------------------------------------------------------------


def test_list_agents_empty() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)

    agents = adapter.list_agents()

    assert agents == []


def test_list_agents_multiple() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)

    adapter.register_manifest("agent-a", _basic_manifest("AgentA"))
    adapter.register_manifest("agent-b", {"name": "AgentB", "description": "B", "version": "0.1.0", "skills": [], "tools": []})

    agents = adapter.list_agents()

    assert len(agents) == 2
    ids = {a["agent_id"] for a in agents}
    assert "agent-a" in ids
    assert "agent-b" in ids


def test_list_agents_has_required_fields() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)

    raw = _basic_manifest("MyAgent")
    adapter.register_manifest("my-agent", raw)

    agents = adapter.list_agents()
    agent = agents[0]

    assert "agent_id" in agent
    assert "name" in agent
    assert "description" in agent
    assert "version" in agent
    assert "skills" in agent


def test_list_agents_skills_count() -> None:
    router = _make_router()
    adapter = MAFAdapter(router)

    raw = _basic_manifest("Agent")  # has 2 skills
    adapter.register_manifest("agent-cnt", raw)

    agents = adapter.list_agents()
    assert agents[0]["skills"] == 2
