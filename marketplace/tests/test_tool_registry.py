"""Tests for marketplace.mcp.tool_registry — ToolRegistry, ToolPolicy, AgentToolAllowlist."""

from __future__ import annotations

import pytest

from marketplace.mcp.tool_registry import (
    AgentToolAllowlist,
    RiskLevel,
    ToolPolicy,
    ToolRegistry,
)


# ---------------------------------------------------------------------------
# ToolPolicy defaults and custom values
# ---------------------------------------------------------------------------


def test_tool_policy_defaults() -> None:
    policy = ToolPolicy(name="my_tool")
    assert policy.name == "my_tool"
    assert policy.timeout_seconds == 30.0
    assert policy.max_input_size_bytes == 1_048_576
    assert policy.requires_consent is False
    assert policy.risk_level == RiskLevel.MEDIUM
    assert policy.rate_limit_per_minute == 60


def test_tool_policy_custom() -> None:
    policy = ToolPolicy(
        name="dangerous_tool",
        timeout_seconds=120.0,
        max_input_size_bytes=512,
        requires_consent=True,
        risk_level=RiskLevel.CRITICAL,
        rate_limit_per_minute=5,
    )
    assert policy.timeout_seconds == 120.0
    assert policy.max_input_size_bytes == 512
    assert policy.requires_consent is True
    assert policy.risk_level == RiskLevel.CRITICAL
    assert policy.rate_limit_per_minute == 5


# ---------------------------------------------------------------------------
# RiskLevel enum
# ---------------------------------------------------------------------------


def test_risk_level_values() -> None:
    assert RiskLevel.LOW == "low"
    assert RiskLevel.MEDIUM == "medium"
    assert RiskLevel.HIGH == "high"
    assert RiskLevel.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# AgentToolAllowlist
# ---------------------------------------------------------------------------


def test_agent_allowlist_defaults() -> None:
    al = AgentToolAllowlist(agent_id="agent-1")
    assert al.agent_id == "agent-1"
    assert al.allowed_tools == set()
    assert al.denied_tools == set()
    assert al.max_concurrent_calls == 10


def test_agent_allowlist_empty_allowed() -> None:
    al = AgentToolAllowlist(agent_id="agent-1", allowed_tools=set())
    # Empty allowed_tools means all tools allowed (not filtered)
    assert al.allowed_tools == set()


def test_agent_allowlist_max_concurrent() -> None:
    al = AgentToolAllowlist(agent_id="agent-1", max_concurrent_calls=25)
    assert al.max_concurrent_calls == 25


def test_agent_allowlist_none_allowed_means_all_allowed() -> None:
    # allowed_tools is a set; an empty set (default) means all tools are allowed
    # because the registry only restricts when allowed_tools is *non-empty*
    al = AgentToolAllowlist(agent_id="agent-1")
    assert len(al.allowed_tools) == 0  # empty → all tools allowed by registry logic


# ---------------------------------------------------------------------------
# ToolRegistry — register_tool
# ---------------------------------------------------------------------------


def test_register_tool_basic() -> None:
    registry = ToolRegistry()
    defn = {"name": "search", "description": "Search something"}
    registry.register_tool(defn)
    assert registry.list_all_tools() == [defn]


def test_register_tool_with_policy() -> None:
    registry = ToolRegistry()
    defn = {"name": "buy", "description": "Buy item"}
    policy = ToolPolicy(name="buy", risk_level=RiskLevel.HIGH, requires_consent=True)
    registry.register_tool(defn, policy=policy)
    stored = registry.get_policy("buy")
    assert stored is not None
    assert stored.risk_level == RiskLevel.HIGH
    assert stored.requires_consent is True


def test_register_tool_no_policy_creates_default() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "ping"})
    policy = registry.get_policy("ping")
    assert policy is not None
    assert policy.name == "ping"
    assert policy.risk_level == RiskLevel.MEDIUM


def test_register_tool_duplicate_overwrites() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "ping", "description": "v1"})
    registry.register_tool({"name": "ping", "description": "v2"})
    tools = registry.list_all_tools()
    assert len(tools) == 1
    assert tools[0]["description"] == "v2"


# ---------------------------------------------------------------------------
# ToolRegistry — authorize_tool_call
# ---------------------------------------------------------------------------


def test_authorize_tool_not_registered_returns_false() -> None:
    registry = ToolRegistry()
    # Tool was never registered
    result = registry.authorize_tool_call("agent-1", "ghost_tool")
    assert result is False


def test_authorize_tool_no_allowlist_returns_true() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "search"})
    # No allowlist set for agent → default allow
    assert registry.authorize_tool_call("agent-99", "search") is True


def test_authorize_tool_in_allowed_returns_true() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "search"})
    al = AgentToolAllowlist(agent_id="agent-1", allowed_tools={"search"})
    registry.set_agent_allowlist(al)
    assert registry.authorize_tool_call("agent-1", "search") is True


def test_authorize_tool_not_in_allowed_returns_false() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "search"})
    registry.register_tool({"name": "buy"})
    al = AgentToolAllowlist(agent_id="agent-1", allowed_tools={"search"})
    registry.set_agent_allowlist(al)
    # 'buy' not in allowlist
    assert registry.authorize_tool_call("agent-1", "buy") is False


def test_authorize_tool_in_denied_returns_false() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "buy"})
    al = AgentToolAllowlist(agent_id="agent-1", denied_tools={"buy"})
    registry.set_agent_allowlist(al)
    assert registry.authorize_tool_call("agent-1", "buy") is False


def test_authorize_tool_denied_overrides_allowed() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "buy"})
    # Tool is in both — deny wins
    al = AgentToolAllowlist(
        agent_id="agent-1",
        allowed_tools={"buy"},
        denied_tools={"buy"},
    )
    registry.set_agent_allowlist(al)
    assert registry.authorize_tool_call("agent-1", "buy") is False


# ---------------------------------------------------------------------------
# ToolRegistry — set_agent_allowlist
# ---------------------------------------------------------------------------


def test_set_agent_allowlist_stores() -> None:
    registry = ToolRegistry()
    al = AgentToolAllowlist(agent_id="agent-1", allowed_tools={"search"})
    registry.set_agent_allowlist(al)
    assert registry._allowlists["agent-1"] is al


def test_set_agent_allowlist_overwrites() -> None:
    registry = ToolRegistry()
    al1 = AgentToolAllowlist(agent_id="agent-1", allowed_tools={"search"})
    al2 = AgentToolAllowlist(agent_id="agent-1", allowed_tools={"buy"})
    registry.set_agent_allowlist(al1)
    registry.set_agent_allowlist(al2)
    assert registry._allowlists["agent-1"] is al2


# ---------------------------------------------------------------------------
# ToolRegistry — get_tools_for_agent
# ---------------------------------------------------------------------------


def test_get_tools_for_agent_no_allowlist_returns_all() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "search"})
    registry.register_tool({"name": "buy"})
    tools = registry.get_tools_for_agent("agent-any")
    assert len(tools) == 2


def test_get_tools_for_agent_with_allowlist_filters() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "search"})
    registry.register_tool({"name": "buy"})
    al = AgentToolAllowlist(agent_id="agent-1", allowed_tools={"search"})
    registry.set_agent_allowlist(al)
    tools = registry.get_tools_for_agent("agent-1")
    assert len(tools) == 1
    assert tools[0]["name"] == "search"


def test_get_tools_for_agent_with_denied_excluded() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "search"})
    registry.register_tool({"name": "buy"})
    al = AgentToolAllowlist(agent_id="agent-1", denied_tools={"buy"})
    registry.set_agent_allowlist(al)
    tools = registry.get_tools_for_agent("agent-1")
    names = {t["name"] for t in tools}
    assert "buy" not in names
    assert "search" in names


# ---------------------------------------------------------------------------
# ToolRegistry — list_all_tools
# ---------------------------------------------------------------------------


def test_list_all_tools_empty() -> None:
    registry = ToolRegistry()
    assert registry.list_all_tools() == []


def test_list_all_tools_multiple() -> None:
    registry = ToolRegistry()
    registry.register_tool({"name": "a"})
    registry.register_tool({"name": "b"})
    registry.register_tool({"name": "c"})
    tools = registry.list_all_tools()
    assert len(tools) == 3
    names = {t["name"] for t in tools}
    assert names == {"a", "b", "c"}
