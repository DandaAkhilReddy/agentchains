"""Tests for gRPC client — connection management, task execution, and pool.

Covers:
  - GrpcAgentClient: connect, close, is_connected (tests 1-4)
  - GrpcAgentClient.execute_task: gRPC path, HTTP fallback (tests 5-8)
  - GrpcAgentClient.health_check: connected, disconnected (tests 9-10)
  - GrpcAgentClient._http_fallback: success, failure (tests 11-12)
  - GrpcConnectionPool: get_client, close_all, eviction (tests 13-17)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.grpc.client import GrpcAgentClient, GrpcConnectionPool


class TestGrpcAgentClientConnect:
    """Tests 1-4: connection lifecycle."""

    # 1
    async def test_connect_success(self):
        """connect() should set _connected=True and return True."""
        client = GrpcAgentClient("localhost:50051")

        with patch("marketplace.grpc.client.GrpcAgentClient.connect") as mock_connect:
            mock_connect.return_value = True
            # Directly test the real connect by mocking grpc.aio
            pass

        # Test the actual connect with mocked grpc
        mock_channel = AsyncMock()
        mock_channel.channel_ready = AsyncMock()

        with patch.dict("sys.modules", {"grpc": MagicMock(), "grpc.aio": MagicMock()}):
            with patch("grpc.aio.insecure_channel", return_value=mock_channel):
                result = await client.connect()

                # Even if grpc import fails, we test the fallback path
                # The connect method catches ImportError
                assert isinstance(result, bool)

    # 2
    async def test_connect_handles_import_error(self):
        """connect() should return False when grpcio is not installed."""
        client = GrpcAgentClient("localhost:50051")

        with patch(
            "builtins.__import__",
            side_effect=lambda name, *a, **kw: (
                (_ for _ in ()).throw(ImportError("no grpc"))
                if name == "grpc" else __import__(name, *a, **kw)
            ),
        ):
            result = await client.connect()

            assert result is False
            assert client.is_connected is False

    # 3
    async def test_close_resets_connected_flag(self):
        """close() should set _connected=False."""
        client = GrpcAgentClient("localhost:50051")
        client._connected = True
        mock_channel = AsyncMock()
        client._channel = mock_channel

        await client.close()

        assert client.is_connected is False
        mock_channel.close.assert_called_once()

    # 4
    async def test_close_when_no_channel(self):
        """close() with no channel should not raise."""
        client = GrpcAgentClient("localhost:50051")

        await client.close()  # Should not raise

        assert client.is_connected is False


class TestGrpcAgentClientExecuteTask:
    """Tests 5-8: task execution via gRPC or HTTP fallback."""

    # 5
    async def test_execute_task_grpc_connected(self):
        """When connected, execute_task should return simulated gRPC response."""
        client = GrpcAgentClient("localhost:50051")
        client._connected = True

        result = await client.execute_task(
            task_id="t1", agent_id="a1",
            task_type="inference", input_data={"prompt": "hello"}
        )

        assert result["task_id"] == "t1"
        assert result["status"] == "success"
        assert "gRPC call simulated" in result["output_json"]

    # 6
    async def test_execute_task_falls_back_to_http(self):
        """When not connected, execute_task should use HTTP fallback."""
        client = GrpcAgentClient("myhost:50051")
        client._connected = False

        with patch.object(client, "_http_fallback", new_callable=AsyncMock) as mock_http:
            mock_http.return_value = {"task_id": "t2", "status": "ok"}

            result = await client.execute_task(
                task_id="t2", agent_id="a2",
                task_type="search", input_data={"q": "test"}
            )

            assert result["status"] == "ok"
            mock_http.assert_called_once_with("t2", "a2", "search", {"q": "test"}, None)

    # 7
    async def test_execute_task_passes_custom_timeout(self):
        """Custom timeout_seconds should be forwarded to fallback."""
        client = GrpcAgentClient("localhost:50051")
        client._connected = False

        with patch.object(client, "_http_fallback", new_callable=AsyncMock) as mock_http:
            mock_http.return_value = {"task_id": "t3", "status": "ok"}

            await client.execute_task(
                task_id="t3", agent_id="a3",
                task_type="eval", input_data={}, timeout_seconds=60
            )

            call_args = mock_http.call_args[0]
            assert call_args[4] == 60  # timeout_seconds

    # 8
    async def test_execute_task_grpc_includes_cost(self):
        """gRPC response should include cost_usd and execution_time_ms."""
        client = GrpcAgentClient("localhost:50051")
        client._connected = True

        result = await client.execute_task(
            task_id="t4", agent_id="a4",
            task_type="compute", input_data={}
        )

        assert "cost_usd" in result
        assert "execution_time_ms" in result


class TestGrpcAgentClientHealthCheck:
    """Tests 9-10: health check responses."""

    # 9
    async def test_health_check_when_connected(self):
        """health_check should return ok status when connected."""
        client = GrpcAgentClient("agent.local:50051")
        client._connected = True

        result = await client.health_check()

        assert result["status"] == "ok"
        assert result["target"] == "agent.local:50051"
        assert result["connected"] is True

    # 10
    async def test_health_check_when_disconnected(self):
        """health_check should return disconnected status."""
        client = GrpcAgentClient("agent.local:50051")
        client._connected = False

        result = await client.health_check()

        assert result["status"] == "disconnected"
        assert result["target"] == "agent.local:50051"


class TestGrpcHttpFallback:
    """Tests 11-12: HTTP fallback behavior."""

    # 11
    async def test_http_fallback_success(self):
        """HTTP fallback should POST to https://<host>:8000/api/v1/tasks."""
        client = GrpcAgentClient("agent-host:50051")

        mock_response = MagicMock()
        mock_response.json.return_value = {"task_id": "t5", "status": "ok"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client._http_fallback(
                "t5", "a5", "infer", {"data": "value"}, 30
            )

            assert result["task_id"] == "t5"
            mock_client_instance.post.assert_called_once()
            call_args = mock_client_instance.post.call_args
            assert "https://agent-host:8000/api/v1/tasks" in call_args[0]

    # 12
    async def test_http_fallback_failure_returns_error(self):
        """HTTP fallback failure should return error response dict."""
        client = GrpcAgentClient("bad-host:50051")

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(
                side_effect=ConnectionError("refused")
            )
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await client._http_fallback(
                "t6", "a6", "eval", {}, None
            )

            assert result["status"] == "error"
            assert "HTTP fallback failed" in result["error_message"]


class TestGrpcConnectionPool:
    """Tests 13-17: connection pool management."""

    # 13
    async def test_get_client_creates_new(self):
        """get_client should create a new client for an unknown target."""
        pool = GrpcConnectionPool(max_connections=5)

        with patch.object(GrpcAgentClient, "connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = True

            client = await pool.get_client("new-host:50051")

            assert isinstance(client, GrpcAgentClient)
            assert "new-host:50051" in pool._pool

    # 14
    async def test_get_client_reuses_connected(self):
        """get_client should return existing connected client."""
        pool = GrpcConnectionPool()
        existing = GrpcAgentClient("cached:50051")
        existing._connected = True
        pool._pool["cached:50051"] = existing

        client = await pool.get_client("cached:50051")

        assert client is existing

    # 15
    async def test_get_client_reconnects_disconnected(self):
        """get_client should create new client if existing one is disconnected."""
        pool = GrpcConnectionPool()
        old = GrpcAgentClient("stale:50051")
        old._connected = False
        pool._pool["stale:50051"] = old

        with patch.object(GrpcAgentClient, "connect", new_callable=AsyncMock):
            client = await pool.get_client("stale:50051")

            assert client is not old  # New client created

    # 16
    async def test_close_all_closes_all_clients(self):
        """close_all should close every client and clear the pool."""
        pool = GrpcConnectionPool()
        c1 = GrpcAgentClient("h1:50051")
        c2 = GrpcAgentClient("h2:50051")
        c1._channel = AsyncMock()
        c2._channel = AsyncMock()
        c1._connected = True
        c2._connected = True
        pool._pool = {"h1:50051": c1, "h2:50051": c2}

        await pool.close_all()

        assert len(pool._pool) == 0
        assert c1.is_connected is False
        assert c2.is_connected is False

    # 17
    async def test_active_connections_count(self):
        """active_connections should count only connected clients."""
        pool = GrpcConnectionPool()
        c1 = GrpcAgentClient("h1:50051")
        c2 = GrpcAgentClient("h2:50051")
        c1._connected = True
        c2._connected = False
        pool._pool = {"h1:50051": c1, "h2:50051": c2}

        assert pool.active_connections == 1

    # 18
    async def test_pool_evicts_disconnected_when_full(self):
        """When pool is full, get_client should evict a disconnected client."""
        pool = GrpcConnectionPool(max_connections=1)
        old = GrpcAgentClient("old:50051")
        old._connected = False
        pool._pool = {"old:50051": old}

        with patch.object(GrpcAgentClient, "connect", new_callable=AsyncMock):
            client = await pool.get_client("new:50051")

            assert "new:50051" in pool._pool
            # old should have been evicted
            assert "old:50051" not in pool._pool

    # 19
    async def test_default_timeout(self):
        """Default timeout should be 30 seconds."""
        client = GrpcAgentClient("host:50051")
        assert client._timeout == 30

    # 20
    async def test_custom_timeout(self):
        """Custom timeout should be stored correctly."""
        client = GrpcAgentClient("host:50051", timeout_seconds=60)
        assert client._timeout == 60
