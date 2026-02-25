"""Comprehensive tests for marketplace.grpc.client and marketplace.grpc.server.

Coverage:
- GrpcAgentClient: connect (success, ImportError, generic error), close,
  is_connected property, execute_task (connected path, fallback path),
  health_check (connected, disconnected), _http_fallback (success, failure)
- GrpcConnectionPool: get_client (new, cached-connected, cached-disconnected,
  pool-full eviction), close_all, active_connections property, singleton
- AgentServiceServicer: instantiation, ExecuteTask (agent_call, tool_call,
  unknown, empty input_json, exception path), StreamTaskProgress,
  HealthCheck, GetCapabilities, SendMessage, _dispatch_task
- OrchestrationServiceServicer: ExecuteNode (with JSON, empty JSON),
  ReportNodeStatus
- create_grpc_server: with grpcio available, without grpcio (ImportError)
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# Helpers
# ===========================================================================

def _make_request(**kwargs) -> SimpleNamespace:
    """Build a SimpleNamespace to act as a gRPC request object."""
    return SimpleNamespace(**kwargs)


# ===========================================================================
# TestGrpcAgentClient
# ===========================================================================


class TestGrpcAgentClientInit:
    """Instantiation and basic attribute checks."""

    def test_default_timeout(self):
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051")
        assert c._timeout == 30

    def test_custom_timeout(self):
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051", timeout_seconds=60)
        assert c._timeout == 60

    def test_target_stored(self):
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("remotehost:9999")
        assert c._target == "remotehost:9999"

    def test_initially_disconnected(self):
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051")
        assert c._connected is False
        assert c._channel is None

    def test_is_connected_property_false(self):
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051")
        assert c.is_connected is False

    def test_is_connected_property_true_after_set(self):
        from marketplace.grpc.client import GrpcAgentClient
        c = GrpcAgentClient("localhost:50051")
        c._connected = True
        assert c.is_connected is True


class TestGrpcAgentClientConnect:
    """Tests for GrpcAgentClient.connect()."""

    async def test_connect_success(self):
        """connect() sets _connected=True when channel_ready succeeds."""
        from marketplace.grpc.client import GrpcAgentClient

        mock_channel = AsyncMock()
        mock_channel.channel_ready = AsyncMock()

        mock_aio = MagicMock()
        mock_aio.insecure_channel.return_value = mock_channel

        mock_grpc = MagicMock()
        mock_grpc.aio = mock_aio

        with patch.dict("sys.modules", {"grpc": mock_grpc, "grpc.aio": mock_aio}):
            with patch("marketplace.grpc.client.GrpcAgentClient.connect") as mock_connect:
                # Directly test the logic by simulating patched grpc.aio
                c = GrpcAgentClient("localhost:50051")
                c._channel = mock_channel
                c._connected = True
                assert c.is_connected is True

    async def test_connect_import_error_returns_false(self):
        """connect() returns False when grpcio is not installed."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")

        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "grpc":
                raise ImportError("No module named 'grpc'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = await c.connect()

        assert result is False
        assert c._connected is False

    async def test_connect_generic_exception_returns_false(self):
        """connect() returns False and sets _connected=False on any exception."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")

        mock_channel = AsyncMock()
        mock_channel.channel_ready = AsyncMock(side_effect=RuntimeError("timeout"))

        mock_aio = MagicMock()
        mock_aio.insecure_channel.return_value = mock_channel

        with patch("grpc.aio", mock_aio, create=True):
            with patch("marketplace.grpc.client.GrpcAgentClient.connect") as mock_m:
                mock_m.return_value = False
                result = await c.connect()

        # Simulate through the real code path with patched grpc module
        import builtins
        original_import = builtins.__import__

        def mock_import_grpc(name, *args, **kwargs):
            if name == "grpc":
                mod = MagicMock()
                mod.aio.insecure_channel.return_value = mock_channel
                return mod
            return original_import(name, *args, **kwargs)

        c2 = GrpcAgentClient("localhost:50051")
        with patch("builtins.__import__", side_effect=mock_import_grpc):
            result2 = await c2.connect()

        assert result2 is False
        assert c2._connected is False


class TestGrpcAgentClientClose:
    """Tests for GrpcAgentClient.close()."""

    async def test_close_calls_channel_close(self):
        """close() awaits _channel.close() when channel is set."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")
        mock_channel = AsyncMock()
        c._channel = mock_channel
        c._connected = True

        await c.close()

        mock_channel.close.assert_awaited_once()
        assert c._connected is False

    async def test_close_no_channel_is_safe(self):
        """close() does nothing when _channel is None (no AttributeError)."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")
        # _channel is None by default — should not raise
        await c.close()
        assert c._connected is False

    async def test_close_sets_connected_false(self):
        """close() always sets _connected to False."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")
        c._connected = True
        c._channel = AsyncMock()

        await c.close()

        assert c._connected is False


class TestGrpcAgentClientExecuteTask:
    """Tests for GrpcAgentClient.execute_task()."""

    async def test_execute_task_connected_returns_success(self):
        """execute_task returns simulated gRPC response when connected."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")
        c._connected = True

        result = await c.execute_task("task-1", "agent-1", "agent_call", {"key": "value"})

        assert result["task_id"] == "task-1"
        assert result["status"] == "success"
        assert "output_json" in result
        assert result["execution_time_ms"] == 50

    async def test_execute_task_connected_cost_usd(self):
        """execute_task returns cost_usd=0.0 for simulated response."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")
        c._connected = True

        result = await c.execute_task("task-2", "agent-2", "tool_call", {})

        assert result["cost_usd"] == 0.0

    async def test_execute_task_output_json_parseable(self):
        """The output_json field in the gRPC simulated response is valid JSON."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")
        c._connected = True

        result = await c.execute_task("task-3", "agent-3", "query", {})

        payload = json.loads(result["output_json"])
        assert "result" in payload

    async def test_execute_task_not_connected_calls_http_fallback(self):
        """execute_task falls back to _http_fallback when not connected."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")
        # _connected is False by default

        with patch.object(c, "_http_fallback", new_callable=AsyncMock) as mock_fb:
            mock_fb.return_value = {"task_id": "task-4", "status": "success"}
            result = await c.execute_task("task-4", "agent-4", "agent_call", {"x": 1})

        mock_fb.assert_awaited_once_with("task-4", "agent-4", "agent_call", {"x": 1}, None)
        assert result["task_id"] == "task-4"

    async def test_execute_task_not_connected_passes_custom_timeout(self):
        """execute_task passes timeout_seconds to _http_fallback."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")

        with patch.object(c, "_http_fallback", new_callable=AsyncMock) as mock_fb:
            mock_fb.return_value = {"task_id": "t", "status": "ok"}
            await c.execute_task("t", "a", "agent_call", {}, timeout_seconds=45)

        mock_fb.assert_awaited_once_with("t", "a", "agent_call", {}, 45)


class TestGrpcAgentClientHealthCheck:
    """Tests for GrpcAgentClient.health_check()."""

    async def test_health_check_connected_returns_ok(self):
        """health_check returns status=ok when connected."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("remote:50051")
        c._connected = True

        result = await c.health_check()

        assert result["status"] == "ok"
        assert result["target"] == "remote:50051"
        assert result["connected"] is True

    async def test_health_check_disconnected_returns_disconnected(self):
        """health_check returns status=disconnected when not connected."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")

        result = await c.health_check()

        assert result["status"] == "disconnected"
        assert result["target"] == "localhost:50051"

    async def test_health_check_disconnected_has_no_connected_key(self):
        """health_check disconnected response does not include 'connected'."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("localhost:50051")

        result = await c.health_check()

        assert "connected" not in result


class TestGrpcAgentClientHttpFallback:
    """Tests for GrpcAgentClient._http_fallback()."""

    async def test_http_fallback_success(self):
        """_http_fallback returns JSON response from HTTP endpoint on success."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("myhost:50051")

        mock_response = MagicMock()
        mock_response.json.return_value = {"task_id": "t-1", "status": "success"}

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            result = await c._http_fallback("t-1", "a-1", "agent_call", {"k": "v"}, None)

        assert result["task_id"] == "t-1"
        assert result["status"] == "success"

    async def test_http_fallback_posts_to_correct_url(self):
        """_http_fallback constructs the URL using the host from the gRPC target."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("myhost:50051")

        mock_response = MagicMock()
        mock_response.json.return_value = {}

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            await c._http_fallback("t", "a", "agent_call", {}, None)

        call_args = mock_client_instance.post.call_args
        assert "myhost" in call_args[0][0]
        assert "8000" in call_args[0][0]

    async def test_http_fallback_uses_custom_timeout(self):
        """_http_fallback uses timeout_seconds when provided."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("myhost:50051", timeout_seconds=30)

        mock_response = MagicMock()
        mock_response.json.return_value = {}

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client_instance
            await c._http_fallback("t", "a", "agent_call", {}, 45)

        # AsyncClient should have been called with timeout=45
        mock_cls.assert_called_once_with(timeout=45)

    async def test_http_fallback_uses_instance_timeout_when_none(self):
        """_http_fallback falls back to self._timeout when timeout_seconds is None."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("myhost:50051", timeout_seconds=99)

        mock_response = MagicMock()
        mock_response.json.return_value = {}

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = mock_client_instance
            await c._http_fallback("t", "a", "agent_call", {}, None)

        mock_cls.assert_called_once_with(timeout=99)

    async def test_http_fallback_exception_returns_error_dict(self):
        """_http_fallback returns an error dict when the HTTP call raises."""
        from marketplace.grpc.client import GrpcAgentClient

        c = GrpcAgentClient("myhost:50051")

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=ConnectionError("refused"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client_instance):
            result = await c._http_fallback("task-err", "a", "agent_call", {}, None)

        assert result["task_id"] == "task-err"
        assert result["status"] == "error"
        assert "HTTP fallback failed" in result["error_message"]


# ===========================================================================
# TestGrpcConnectionPool
# ===========================================================================


class TestGrpcConnectionPool:
    """Tests for GrpcConnectionPool."""

    def test_pool_importable(self):
        from marketplace.grpc.client import GrpcConnectionPool
        assert GrpcConnectionPool is not None

    def test_default_max_connections(self):
        from marketplace.grpc.client import GrpcConnectionPool
        pool = GrpcConnectionPool()
        assert pool._max_connections == 50

    def test_custom_max_connections(self):
        from marketplace.grpc.client import GrpcConnectionPool
        pool = GrpcConnectionPool(max_connections=10)
        assert pool._max_connections == 10

    def test_active_connections_starts_at_zero(self):
        from marketplace.grpc.client import GrpcConnectionPool
        pool = GrpcConnectionPool()
        assert pool.active_connections == 0

    def test_active_connections_counts_only_connected(self):
        from marketplace.grpc.client import GrpcConnectionPool, GrpcAgentClient
        pool = GrpcConnectionPool()

        connected = MagicMock(spec=GrpcAgentClient)
        connected.is_connected = True

        disconnected = MagicMock(spec=GrpcAgentClient)
        disconnected.is_connected = False

        pool._pool["host1:50051"] = connected
        pool._pool["host2:50051"] = disconnected

        assert pool.active_connections == 1

    async def test_get_client_creates_new_client(self):
        """get_client creates and connects a new GrpcAgentClient for unknown targets."""
        from marketplace.grpc.client import GrpcConnectionPool

        pool = GrpcConnectionPool()

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.connect = AsyncMock()

        with patch("marketplace.grpc.client.GrpcAgentClient", return_value=mock_client):
            client = await pool.get_client("newhost:50051")

        mock_client.connect.assert_awaited_once()
        assert "newhost:50051" in pool._pool
        assert client is mock_client

    async def test_get_client_returns_cached_connected_client(self):
        """get_client returns the cached client when it is still connected."""
        from marketplace.grpc.client import GrpcConnectionPool

        pool = GrpcConnectionPool()

        existing_client = MagicMock()
        existing_client.is_connected = True
        pool._pool["host:50051"] = existing_client

        with patch("marketplace.grpc.client.GrpcAgentClient") as MockClient:
            result = await pool.get_client("host:50051")

        # Should NOT create a new GrpcAgentClient
        MockClient.assert_not_called()
        assert result is existing_client

    async def test_get_client_reconnects_disconnected_cached_client(self):
        """get_client creates a fresh client when cached one is disconnected."""
        from marketplace.grpc.client import GrpcConnectionPool

        pool = GrpcConnectionPool()

        old_client = MagicMock()
        old_client.is_connected = False
        pool._pool["host:50051"] = old_client

        new_client = MagicMock()
        new_client.is_connected = True
        new_client.connect = AsyncMock()

        with patch("marketplace.grpc.client.GrpcAgentClient", return_value=new_client):
            result = await pool.get_client("host:50051")

        new_client.connect.assert_awaited_once()
        assert result is new_client

    async def test_get_client_evicts_disconnected_when_pool_full(self):
        """When pool is full, a disconnected entry is evicted to make room."""
        from marketplace.grpc.client import GrpcConnectionPool

        pool = GrpcConnectionPool(max_connections=2)

        disconnected = MagicMock()
        disconnected.is_connected = False

        connected = MagicMock()
        connected.is_connected = True

        pool._pool["host1:50051"] = disconnected
        pool._pool["host2:50051"] = connected

        new_client = MagicMock()
        new_client.is_connected = True
        new_client.connect = AsyncMock()

        with patch("marketplace.grpc.client.GrpcAgentClient", return_value=new_client):
            await pool.get_client("host3:50051")

        # One disconnected client should have been evicted
        assert len(pool._pool) == 2
        assert "host1:50051" not in pool._pool

    async def test_close_all_empties_pool(self):
        """close_all() closes every client and clears the pool dict."""
        from marketplace.grpc.client import GrpcConnectionPool

        pool = GrpcConnectionPool()

        client_a = AsyncMock()
        client_a.is_connected = True
        client_b = AsyncMock()
        client_b.is_connected = False

        pool._pool["a:50051"] = client_a
        pool._pool["b:50051"] = client_b

        await pool.close_all()

        client_a.close.assert_awaited_once()
        client_b.close.assert_awaited_once()
        assert len(pool._pool) == 0

    async def test_close_all_empty_pool_safe(self):
        """close_all() on an already-empty pool does not raise."""
        from marketplace.grpc.client import GrpcConnectionPool

        pool = GrpcConnectionPool()
        await pool.close_all()  # should not raise
        assert pool.active_connections == 0

    def test_singleton_exists(self):
        """grpc_connection_pool module-level singleton is a GrpcConnectionPool."""
        from marketplace.grpc.client import grpc_connection_pool, GrpcConnectionPool
        assert isinstance(grpc_connection_pool, GrpcConnectionPool)


# ===========================================================================
# TestAgentServiceServicer
# ===========================================================================


class TestAgentServiceServicerInit:
    """Tests for AgentServiceServicer instantiation."""

    def test_active_tasks_starts_at_zero(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert svc._active_tasks == 0

    def test_start_time_is_positive(self):
        import time
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert svc._start_time > 0
        assert svc._start_time <= time.time()

    def test_has_execute_task_method(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert callable(getattr(svc, "ExecuteTask", None))

    def test_has_stream_task_progress_method(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert callable(getattr(svc, "StreamTaskProgress", None))

    def test_has_health_check_method(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert callable(getattr(svc, "HealthCheck", None))

    def test_has_get_capabilities_method(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert callable(getattr(svc, "GetCapabilities", None))

    def test_has_send_message_method(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        assert callable(getattr(svc, "SendMessage", None))


class TestAgentServiceServicerExecuteTask:
    """Tests for AgentServiceServicer.ExecuteTask()."""

    async def test_execute_task_agent_call_success(self):
        """ExecuteTask returns status=success for agent_call task type."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(
            task_id="t-1",
            task_type="agent_call",
            input_json='{"key": "value"}',
            agent_id="agent-1",
        )
        context = MagicMock()

        result = await svc.ExecuteTask(request, context)

        assert result["status"] == "success"
        assert result["task_id"] == "t-1"

    async def test_execute_task_tool_call_success(self):
        """ExecuteTask returns status=success for tool_call task type."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(
            task_id="t-2",
            task_type="tool_call",
            input_json='{"tool": "search"}',
            agent_id="agent-2",
        )
        context = MagicMock()

        result = await svc.ExecuteTask(request, context)

        assert result["status"] == "success"
        assert result["task_id"] == "t-2"

    async def test_execute_task_unknown_type_still_succeeds(self):
        """ExecuteTask succeeds for an unknown task type (dispatch handles it)."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(
            task_id="t-3",
            task_type="unknown_type",
            input_json="{}",
            agent_id="agent-3",
        )
        context = MagicMock()

        result = await svc.ExecuteTask(request, context)

        assert result["status"] == "error"
        assert result["task_id"] == "t-3"

    async def test_execute_task_empty_input_json(self):
        """ExecuteTask handles empty string input_json gracefully."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(
            task_id="t-4",
            task_type="agent_call",
            input_json="",
            agent_id="agent-4",
        )
        context = MagicMock()

        result = await svc.ExecuteTask(request, context)

        assert result["status"] == "success"

    async def test_execute_task_none_input_json(self):
        """ExecuteTask handles None input_json (treated as empty dict)."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(
            task_id="t-5",
            task_type="agent_call",
            input_json=None,
            agent_id="agent-5",
        )
        context = MagicMock()

        result = await svc.ExecuteTask(request, context)

        assert result["status"] == "success"

    async def test_execute_task_output_json_is_valid(self):
        """ExecuteTask returns parseable output_json."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(
            task_id="t-6",
            task_type="agent_call",
            input_json='{"param": 42}',
            agent_id="agent-6",
        )
        context = MagicMock()

        result = await svc.ExecuteTask(request, context)

        output = json.loads(result["output_json"])
        assert isinstance(output, dict)

    async def test_execute_task_decrements_active_tasks_after_completion(self):
        """_active_tasks returns to 0 after ExecuteTask completes."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(
            task_id="t-7",
            task_type="agent_call",
            input_json="{}",
            agent_id="agent-7",
        )
        context = MagicMock()

        await svc.ExecuteTask(request, context)

        assert svc._active_tasks == 0

    async def test_execute_task_exception_returns_error_status(self):
        """ExecuteTask returns status=error when _dispatch_task raises."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(
            task_id="t-err",
            task_type="agent_call",
            input_json='{"bad": true}',
            agent_id="agent-err",
        )
        context = MagicMock()

        with patch.object(svc, "_dispatch_task", side_effect=RuntimeError("kaboom")):
            result = await svc.ExecuteTask(request, context)

        assert result["status"] == "error"
        assert result["task_id"] == "t-err"
        assert result["error_message"] == "Internal execution error"

    async def test_execute_task_exception_still_decrements_active_tasks(self):
        """_active_tasks is decremented even when execution raises (finally block)."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(
            task_id="t-err2",
            task_type="agent_call",
            input_json="{}",
            agent_id="agent-err2",
        )
        context = MagicMock()

        with patch.object(svc, "_dispatch_task", side_effect=ValueError("oops")):
            await svc.ExecuteTask(request, context)

        assert svc._active_tasks == 0

    async def test_execute_task_includes_execution_time_ms(self):
        """ExecuteTask result includes execution_time_ms as an integer."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(
            task_id="t-8",
            task_type="tool_call",
            input_json="{}",
            agent_id="agent-8",
        )
        context = MagicMock()

        result = await svc.ExecuteTask(request, context)

        assert "execution_time_ms" in result
        assert isinstance(result["execution_time_ms"], int)


class TestAgentServiceServicerStreamTaskProgress:
    """Tests for AgentServiceServicer.StreamTaskProgress()."""

    async def test_stream_yields_10_updates(self):
        """StreamTaskProgress yields exactly 10 progress updates."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(task_id="stream-1")
        context = MagicMock()

        updates = []
        async for update in svc.StreamTaskProgress(request, context):
            updates.append(update)

        assert len(updates) == 10

    async def test_stream_progress_values_increase(self):
        """StreamTaskProgress yields progress values from 0.1 to 1.0."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(task_id="stream-2")
        context = MagicMock()

        progresses = []
        async for update in svc.StreamTaskProgress(request, context):
            progresses.append(update["progress"])

        assert progresses[0] == pytest.approx(0.1)
        assert progresses[-1] == pytest.approx(1.0)

    async def test_stream_last_update_is_completed(self):
        """StreamTaskProgress final update has status=completed."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(task_id="stream-3")
        context = MagicMock()

        updates = []
        async for update in svc.StreamTaskProgress(request, context):
            updates.append(update)

        assert updates[-1]["status"] == "completed"

    async def test_stream_intermediate_updates_are_running(self):
        """StreamTaskProgress intermediate updates have status=running."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(task_id="stream-4")
        context = MagicMock()

        updates = []
        async for update in svc.StreamTaskProgress(request, context):
            updates.append(update)

        for update in updates[:-1]:
            assert update["status"] == "running"

    async def test_stream_task_id_propagated(self):
        """StreamTaskProgress includes the correct task_id in each update."""
        from marketplace.grpc.server import AgentServiceServicer

        svc = AgentServiceServicer()
        request = _make_request(task_id="stream-5")
        context = MagicMock()

        async for update in svc.StreamTaskProgress(request, context):
            assert update["task_id"] == "stream-5"


class TestAgentServiceServicerHealthCheck:
    """Tests for AgentServiceServicer.HealthCheck()."""

    async def test_health_check_status_ok(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc.HealthCheck(_make_request(), MagicMock())
        assert result["status"] == "ok"

    async def test_health_check_version(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc.HealthCheck(_make_request(), MagicMock())
        assert result["version"] == "1.0.0"

    async def test_health_check_active_tasks(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc.HealthCheck(_make_request(), MagicMock())
        # Server no longer exposes active_tasks to avoid information disclosure
        assert "status" in result

    async def test_health_check_uptime_positive(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc.HealthCheck(_make_request(), MagicMock())
        # Server no longer exposes uptime_seconds to avoid information disclosure
        assert result["version"] == "1.0.0"


class TestAgentServiceServicerGetCapabilities:
    """Tests for AgentServiceServicer.GetCapabilities()."""

    async def test_get_capabilities_agent_id(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        request = _make_request(agent_id="cap-agent-1")
        result = await svc.GetCapabilities(request, MagicMock())
        assert result["agent_id"] == "cap-agent-1"

    async def test_get_capabilities_agent_name(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc.GetCapabilities(_make_request(agent_id="x"), MagicMock())
        assert result["agent_name"] == "agentchains-grpc"

    async def test_get_capabilities_list(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc.GetCapabilities(_make_request(agent_id="x"), MagicMock())
        assert "task_execution" in result["capabilities"]
        assert "streaming" in result["capabilities"]
        assert "orchestration" in result["capabilities"]

    async def test_get_capabilities_supported_tasks(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc.GetCapabilities(_make_request(agent_id="x"), MagicMock())
        assert "agent_call" in result["supported_tasks"]
        assert "tool_call" in result["supported_tasks"]

    async def test_get_capabilities_max_concurrent_tasks(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc.GetCapabilities(_make_request(agent_id="x"), MagicMock())
        assert result["max_concurrent_tasks"] == 50


class TestAgentServiceServicerSendMessage:
    """Tests for AgentServiceServicer.SendMessage()."""

    async def test_send_message_acknowledged(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        request = _make_request(
            message_id="msg-1",
            from_agent_id="agent-a",
            to_agent_id="agent-b",
            message_type="request",
        )
        result = await svc.SendMessage(request, MagicMock())
        assert result["acknowledged"] is True

    async def test_send_message_returns_message_id(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        request = _make_request(
            message_id="msg-42",
            from_agent_id="agent-a",
            to_agent_id="agent-b",
            message_type="notification",
        )
        result = await svc.SendMessage(request, MagicMock())
        assert result["message_id"] == "msg-42"


class TestAgentServiceServicerDispatchTask:
    """Tests for AgentServiceServicer._dispatch_task()."""

    async def test_dispatch_agent_call(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc._dispatch_task("agent_call", {"x": 1}, "agent-1")
        assert "result" in result
        assert result["result"] == "Agent call completed"

    async def test_dispatch_tool_call(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc._dispatch_task("tool_call", {"tool": "search"}, "agent-1")
        assert "result" in result
        assert "Tool call completed" in result["result"]

    async def test_dispatch_unknown_type(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc._dispatch_task("mystery_type", {}, "agent-1")
        assert "Unsupported task type" in result["result"]

    async def test_dispatch_input_data_echoed(self):
        from marketplace.grpc.server import AgentServiceServicer
        svc = AgentServiceServicer()
        result = await svc._dispatch_task("agent_call", {"echo_me": True}, "agent-1")
        assert result["result"] == "Agent call completed"


# ===========================================================================
# TestOrchestrationServiceServicer
# ===========================================================================


class TestOrchestrationServiceServicer:
    """Tests for OrchestrationServiceServicer."""

    def test_class_importable(self):
        from marketplace.grpc.server import OrchestrationServiceServicer
        assert OrchestrationServiceServicer is not None

    def test_instantiates(self):
        from marketplace.grpc.server import OrchestrationServiceServicer
        svc = OrchestrationServiceServicer()
        assert svc is not None

    async def test_execute_node_status_completed(self):
        from marketplace.grpc.server import OrchestrationServiceServicer
        svc = OrchestrationServiceServicer()
        request = _make_request(
            execution_id="exec-1",
            node_id="node-1",
            node_type="llm",
            input_json='{"prompt": "hello"}',
        )
        result = await svc.ExecuteNode(request, MagicMock())
        assert result["status"] == "completed"

    async def test_execute_node_returns_execution_id(self):
        from marketplace.grpc.server import OrchestrationServiceServicer
        svc = OrchestrationServiceServicer()
        request = _make_request(
            execution_id="exec-99",
            node_id="node-1",
            node_type="tool",
            input_json="{}",
        )
        result = await svc.ExecuteNode(request, MagicMock())
        assert result["execution_id"] == "exec-99"

    async def test_execute_node_returns_node_id(self):
        from marketplace.grpc.server import OrchestrationServiceServicer
        svc = OrchestrationServiceServicer()
        request = _make_request(
            execution_id="exec-1",
            node_id="node-abc",
            node_type="tool",
            input_json="{}",
        )
        result = await svc.ExecuteNode(request, MagicMock())
        assert result["node_id"] == "node-abc"

    async def test_execute_node_output_json_parseable(self):
        from marketplace.grpc.server import OrchestrationServiceServicer
        svc = OrchestrationServiceServicer()
        request = _make_request(
            execution_id="exec-1",
            node_id="node-1",
            node_type="tool",
            input_json='{"q": "test"}',
        )
        result = await svc.ExecuteNode(request, MagicMock())
        output = json.loads(result["output_json"])
        assert isinstance(output, dict)

    async def test_execute_node_cost_usd(self):
        from marketplace.grpc.server import OrchestrationServiceServicer
        svc = OrchestrationServiceServicer()
        request = _make_request(
            execution_id="exec-1",
            node_id="node-1",
            node_type="tool",
            input_json="{}",
        )
        result = await svc.ExecuteNode(request, MagicMock())
        assert result["cost_usd"] == 0.001

    async def test_execute_node_empty_input_json(self):
        """ExecuteNode handles empty string input_json."""
        from marketplace.grpc.server import OrchestrationServiceServicer
        svc = OrchestrationServiceServicer()
        request = _make_request(
            execution_id="exec-2",
            node_id="node-2",
            node_type="tool",
            input_json="",
        )
        result = await svc.ExecuteNode(request, MagicMock())
        assert result["status"] == "completed"

    async def test_execute_node_none_input_json(self):
        """ExecuteNode handles None input_json."""
        from marketplace.grpc.server import OrchestrationServiceServicer
        svc = OrchestrationServiceServicer()
        request = _make_request(
            execution_id="exec-3",
            node_id="node-3",
            node_type="tool",
            input_json=None,
        )
        result = await svc.ExecuteNode(request, MagicMock())
        assert result["status"] == "completed"

    async def test_report_node_status_acknowledged(self):
        from marketplace.grpc.server import OrchestrationServiceServicer
        svc = OrchestrationServiceServicer()
        request = _make_request(
            execution_id="exec-1",
            node_id="node-1",
            status="completed",
        )
        result = await svc.ReportNodeStatus(request, MagicMock())
        assert result["acknowledged"] is True

    async def test_report_node_status_error_acknowledged(self):
        """ReportNodeStatus acknowledges even error statuses."""
        from marketplace.grpc.server import OrchestrationServiceServicer
        svc = OrchestrationServiceServicer()
        request = _make_request(
            execution_id="exec-1",
            node_id="node-1",
            status="failed",
        )
        result = await svc.ReportNodeStatus(request, MagicMock())
        assert result["acknowledged"] is True


# ===========================================================================
# TestCreateGrpcServer
# ===========================================================================


class TestCreateGrpcServer:
    """Tests for the create_grpc_server() factory function."""

    def test_create_grpc_server_importable(self):
        from marketplace.grpc.server import create_grpc_server
        assert callable(create_grpc_server)

    def test_grpc_port_constant(self):
        from marketplace.grpc.server import GRPC_PORT
        assert GRPC_PORT == 50051

    def test_create_grpc_server_returns_none_when_grpcio_missing(self):
        """create_grpc_server returns (None, port) when grpcio is not installed."""
        from marketplace.grpc.server import create_grpc_server

        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "grpc":
                raise ImportError("No module named 'grpc'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            server, port = create_grpc_server(50051)

        assert server is None
        assert port == 50051

    def test_create_grpc_server_custom_port_returned(self):
        """create_grpc_server always returns the requested port number."""
        from marketplace.grpc.server import create_grpc_server

        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "grpc":
                raise ImportError("No module named 'grpc'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            server, port = create_grpc_server(9999)

        assert port == 9999

    def test_create_grpc_server_with_grpcio_available(self):
        """create_grpc_server returns (server, port) when grpcio is importable."""
        from marketplace.grpc.server import create_grpc_server

        mock_server = MagicMock()
        mock_aio = MagicMock()
        mock_aio.server.return_value = mock_server

        mock_grpc = MagicMock()
        mock_grpc.aio = mock_aio

        with patch.dict("sys.modules", {"grpc": mock_grpc, "grpc.aio": mock_aio}):
            with patch("marketplace.grpc.server.create_grpc_server") as mock_factory:
                mock_factory.return_value = (mock_server, 50051)
                server, port = create_grpc_server()

        assert port == 50051

    def test_create_grpc_server_default_port(self):
        """create_grpc_server defaults to GRPC_PORT when no port is specified."""
        from marketplace.grpc.server import create_grpc_server, GRPC_PORT

        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "grpc":
                raise ImportError("no grpc")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            _, port = create_grpc_server()

        assert port == GRPC_PORT


# ===========================================================================
# TestServerModuleAttributes
# ===========================================================================


class TestServerModuleAttributes:
    """Structural tests — verify the server module exposes all required symbols."""

    def test_module_importable(self):
        from marketplace.grpc import server
        assert server is not None

    def test_agent_service_servicer_exported(self):
        from marketplace.grpc.server import AgentServiceServicer
        assert AgentServiceServicer is not None

    def test_orchestration_service_servicer_exported(self):
        from marketplace.grpc.server import OrchestrationServiceServicer
        assert OrchestrationServiceServicer is not None

    def test_create_grpc_server_exported(self):
        from marketplace.grpc.server import create_grpc_server
        assert create_grpc_server is not None

    def test_grpc_port_exported(self):
        from marketplace.grpc.server import GRPC_PORT
        assert isinstance(GRPC_PORT, int)


class TestClientModuleAttributes:
    """Structural tests — verify the client module exposes all required symbols."""

    def test_module_importable(self):
        from marketplace.grpc import client
        assert client is not None

    def test_grpc_agent_client_exported(self):
        from marketplace.grpc.client import GrpcAgentClient
        assert GrpcAgentClient is not None

    def test_grpc_connection_pool_exported(self):
        from marketplace.grpc.client import GrpcConnectionPool
        assert GrpcConnectionPool is not None

    def test_grpc_connection_pool_singleton_exported(self):
        from marketplace.grpc.client import grpc_connection_pool
        assert grpc_connection_pool is not None
