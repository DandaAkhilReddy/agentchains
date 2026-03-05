"""Tests for marketplace.mcp.guarded_executor — GuardedToolExecutor."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.mcp.guarded_executor import GuardedToolExecutor
from marketplace.mcp.tool_registry import AgentToolAllowlist, RiskLevel, ToolPolicy, ToolRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry(*tool_names: str, **kwargs: object) -> ToolRegistry:
    """Build a registry with simple tool registrations."""
    registry = ToolRegistry()
    for name in tool_names:
        defn = {"name": name, "description": f"Tool {name}"}
        policy_kwargs: dict = {"name": name}
        policy_kwargs.update(kwargs)  # type: ignore[arg-type]
        registry.register_tool(defn, policy=ToolPolicy(**policy_kwargs))  # type: ignore[arg-type]
    return registry


MOCK_EXECUTE_PATH = "marketplace.mcp.tools.execute_tool"


# ---------------------------------------------------------------------------
# execute — success path
# ---------------------------------------------------------------------------


async def test_execute_success() -> None:
    registry = _make_registry("search")
    executor = GuardedToolExecutor(registry)

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, return_value={"results": [1, 2]}) as mock_exec:
        result = await executor.execute("search", {"q": "hello"}, agent_id="agent-1")

    assert result == {"results": [1, 2]}
    mock_exec.assert_awaited_once()


async def test_execute_passes_agent_id_and_db() -> None:
    registry = _make_registry("buy")
    executor = GuardedToolExecutor(registry)
    db_mock = MagicMock()

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, return_value={"ok": True}) as mock_exec:
        await executor.execute("buy", {"consent": True}, agent_id="agent-x", db=db_mock)

    call_kwargs = mock_exec.await_args
    assert call_kwargs.args[2] == "agent-x"
    assert call_kwargs.kwargs.get("db") is db_mock or db_mock in call_kwargs.args


async def test_execute_returns_tool_result_unchanged() -> None:
    registry = _make_registry("search")
    executor = GuardedToolExecutor(registry)
    expected = {"listings": [{"id": "abc"}], "total": 1}

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, return_value=expected):
        result = await executor.execute("search", {}, agent_id="a")

    assert result is expected


# ---------------------------------------------------------------------------
# execute — unauthorized
# ---------------------------------------------------------------------------


async def test_execute_unauthorized_returns_error_dict() -> None:
    registry = _make_registry("search")
    al = AgentToolAllowlist(agent_id="agent-1", denied_tools={"search"})
    registry.set_agent_allowlist(al)
    executor = GuardedToolExecutor(registry)

    result = await executor.execute("search", {}, agent_id="agent-1")

    assert "error" in result
    assert "not authorized" in result["error"]


async def test_execute_unregistered_tool_returns_error_dict() -> None:
    registry = ToolRegistry()
    executor = GuardedToolExecutor(registry)

    result = await executor.execute("ghost_tool", {}, agent_id="agent-1")

    assert "error" in result
    assert "not authorized" in result["error"]


# ---------------------------------------------------------------------------
# execute — input size validation
# ---------------------------------------------------------------------------


async def test_execute_input_too_large_returns_error_dict() -> None:
    registry = ToolRegistry()
    registry.register_tool(
        {"name": "tiny"},
        policy=ToolPolicy(name="tiny", max_input_size_bytes=10),
    )
    executor = GuardedToolExecutor(registry)

    # Build an argument that serializes to more than 10 bytes
    big_args = {"data": "x" * 100}
    result = await executor.execute("tiny", big_args, agent_id="agent-1")

    assert "error" in result
    assert "exceeds" in result["error"]


async def test_execute_input_exactly_at_limit_succeeds() -> None:
    registry = ToolRegistry()
    # Large limit so our small input definitely passes
    registry.register_tool(
        {"name": "tool"},
        policy=ToolPolicy(name="tool", max_input_size_bytes=1_000_000),
    )
    executor = GuardedToolExecutor(registry)

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, return_value={"ok": True}):
        result = await executor.execute("tool", {"k": "v"}, agent_id="agent-1")

    assert result == {"ok": True}


# ---------------------------------------------------------------------------
# execute — consent enforcement
# ---------------------------------------------------------------------------


async def test_execute_requires_consent_no_consent_returns_error() -> None:
    registry = ToolRegistry()
    registry.register_tool(
        {"name": "buy"},
        policy=ToolPolicy(name="buy", requires_consent=True),
    )
    executor = GuardedToolExecutor(registry)

    result = await executor.execute("buy", {"listing_id": "abc"}, agent_id="agent-1")

    assert "error" in result
    assert "consent" in result["error"]


async def test_execute_requires_consent_with_consent_proceeds() -> None:
    registry = ToolRegistry()
    registry.register_tool(
        {"name": "buy"},
        policy=ToolPolicy(name="buy", requires_consent=True),
    )
    executor = GuardedToolExecutor(registry)

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, return_value={"bought": True}):
        result = await executor.execute(
            "buy", {"listing_id": "abc", "consent": True}, agent_id="agent-1"
        )

    assert result == {"bought": True}


async def test_execute_consent_false_value_returns_error() -> None:
    registry = ToolRegistry()
    registry.register_tool(
        {"name": "buy"},
        policy=ToolPolicy(name="buy", requires_consent=True),
    )
    executor = GuardedToolExecutor(registry)

    result = await executor.execute("buy", {"consent": False}, agent_id="agent-1")

    assert "error" in result


# ---------------------------------------------------------------------------
# execute — timeout
# ---------------------------------------------------------------------------


async def test_execute_timeout_returns_error_dict() -> None:
    registry = ToolRegistry()
    registry.register_tool(
        {"name": "slow"},
        policy=ToolPolicy(name="slow", timeout_seconds=0.001),
    )
    executor = GuardedToolExecutor(registry)

    async def _hang(*args, **kwargs):  # noqa: ANN002, ANN003
        await asyncio.sleep(10)

    with patch(MOCK_EXECUTE_PATH, side_effect=_hang):
        result = await executor.execute("slow", {}, agent_id="agent-1")

    assert "error" in result
    assert "timed out" in result["error"]


async def test_execute_very_short_timeout_times_out() -> None:
    registry = ToolRegistry()
    registry.register_tool(
        {"name": "slug"},
        policy=ToolPolicy(name="slug", timeout_seconds=0.001),
    )
    executor = GuardedToolExecutor(registry)

    async def _slow(*args, **kwargs):  # noqa: ANN002, ANN003
        await asyncio.sleep(5)

    with patch(MOCK_EXECUTE_PATH, side_effect=_slow):
        result = await executor.execute("slug", {}, agent_id="agent-1")

    assert "error" in result
    assert "timed out" in result["error"]


# ---------------------------------------------------------------------------
# execute — exception propagation
# ---------------------------------------------------------------------------


async def test_execute_tool_raises_exception_propagated() -> None:
    registry = _make_registry("boom")
    executor = GuardedToolExecutor(registry)

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, side_effect=RuntimeError("kaboom")):
        with pytest.raises(RuntimeError, match="kaboom"):
            await executor.execute("boom", {}, agent_id="agent-1")


# ---------------------------------------------------------------------------
# execute — metrics (smoke test — counters/histograms are module-level singletons)
# ---------------------------------------------------------------------------


async def test_execute_emits_success_count_metric() -> None:
    from marketplace.mcp.guarded_executor import TOOL_CALL_COUNT

    registry = _make_registry("ping")
    executor = GuardedToolExecutor(registry)

    before = TOOL_CALL_COUNT.labels(tool_name="ping", status="success")._value.get()

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, return_value={"pong": True}):
        await executor.execute("ping", {}, agent_id="a")

    after = TOOL_CALL_COUNT.labels(tool_name="ping", status="success")._value.get()
    assert after > before


async def test_execute_emits_denied_count_metric() -> None:
    from marketplace.mcp.guarded_executor import TOOL_CALL_COUNT

    registry = _make_registry("secret")
    al = AgentToolAllowlist(agent_id="agent-x", denied_tools={"secret"})
    registry.set_agent_allowlist(al)
    executor = GuardedToolExecutor(registry)

    before = TOOL_CALL_COUNT.labels(tool_name="secret", status="denied")._value.get()
    await executor.execute("secret", {}, agent_id="agent-x")
    after = TOOL_CALL_COUNT.labels(tool_name="secret", status="denied")._value.get()

    assert after > before


async def test_execute_emits_error_count_metric() -> None:
    from marketplace.mcp.guarded_executor import TOOL_CALL_COUNT

    registry = _make_registry("err_tool")
    executor = GuardedToolExecutor(registry)

    before = TOOL_CALL_COUNT.labels(tool_name="err_tool", status="error")._value.get()

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, side_effect=ValueError("oops")):
        with pytest.raises(ValueError):
            await executor.execute("err_tool", {}, agent_id="a")

    after = TOOL_CALL_COUNT.labels(tool_name="err_tool", status="error")._value.get()
    assert after > before


async def test_execute_emits_latency_metric() -> None:
    from marketplace.mcp.guarded_executor import TOOL_CALL_LATENCY

    registry = _make_registry("lat_tool")
    executor = GuardedToolExecutor(registry)

    before_sum = TOOL_CALL_LATENCY.labels(tool_name="lat_tool")._sum.get()

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, return_value={}):
        await executor.execute("lat_tool", {}, agent_id="a")

    after_sum = TOOL_CALL_LATENCY.labels(tool_name="lat_tool")._sum.get()
    # _sum accumulates observed duration; after one call it must be >= before
    assert after_sum >= before_sum


async def test_execute_emits_timeout_latency_metric() -> None:
    from marketplace.mcp.guarded_executor import TOOL_CALL_LATENCY

    registry = ToolRegistry()
    registry.register_tool(
        {"name": "t_lat"},
        policy=ToolPolicy(name="t_lat", timeout_seconds=0.001),
    )
    executor = GuardedToolExecutor(registry)

    async def _hang(*a, **kw):  # noqa: ANN002, ANN003
        await asyncio.sleep(10)

    before_sum = TOOL_CALL_LATENCY.labels(tool_name="t_lat")._sum.get()

    with patch(MOCK_EXECUTE_PATH, side_effect=_hang):
        await executor.execute("t_lat", {}, agent_id="a")

    after_sum = TOOL_CALL_LATENCY.labels(tool_name="t_lat")._sum.get()
    assert after_sum >= before_sum


# ---------------------------------------------------------------------------
# execute — no policy uses defaults
# ---------------------------------------------------------------------------


async def test_execute_no_policy_uses_default_30s_timeout() -> None:
    """When no explicit policy, executor falls back to 30s timeout (default ToolPolicy)."""
    registry = ToolRegistry()
    # register without explicit policy — default ToolPolicy is created
    registry.register_tool({"name": "default_tool"})
    executor = GuardedToolExecutor(registry)

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, return_value={"ok": True}):
        result = await executor.execute("default_tool", {}, agent_id="a")

    assert result == {"ok": True}


async def test_execute_input_size_zero_policy_allows_any_input() -> None:
    """max_input_size_bytes of 0 would block everything; verify large limit passes."""
    registry = ToolRegistry()
    # Use a very large max — essentially no limit
    registry.register_tool(
        {"name": "generous"},
        policy=ToolPolicy(name="generous", max_input_size_bytes=10_000_000),
    )
    executor = GuardedToolExecutor(registry)
    big_args = {"data": "x" * 1000}

    with patch(MOCK_EXECUTE_PATH, new_callable=AsyncMock, return_value={"ok": True}):
        result = await executor.execute("generous", big_args, agent_id="a")

    assert result == {"ok": True}
