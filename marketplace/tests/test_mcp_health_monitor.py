"""Tests for MCP Federation Health Monitor — background health checks.

Covers:
- _check_server: healthy response, unhealthy response, timeout, connection error
- _run_health_checks: score updates for healthy/unhealthy/exception servers
- health_check_loop: initial delay and looping behavior
- MCPHealthMonitor class wrapper
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from marketplace.services.mcp_health_monitor import (
    MCPHealthMonitor,
    _check_server,
    _run_health_checks,
    health_check_loop,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server_stub(
    name: str = "test-srv",
    base_url: str = "https://mcp.example.com",
    status: str = "active",
    health_score: int = 100,
    server_id: str = "srv-001",
):
    """Create a mock server object matching MCPServerEntry attributes."""
    server = MagicMock()
    server.id = server_id
    server.name = name
    server.base_url = base_url
    server.status = status
    server.health_score = health_score
    server.last_health_check = None
    return server


# ---------------------------------------------------------------------------
# _check_server
# ---------------------------------------------------------------------------

class TestCheckServer:
    async def test_healthy_server_returns_ok(self):
        server = _make_server_stub(base_url="https://healthy.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        latency_ms, is_healthy = await _check_server(mock_client, server)

        assert is_healthy is True
        assert latency_ms >= 0
        mock_client.get.assert_called_once_with("https://healthy.example.com/mcp/health")

    async def test_unhealthy_status_in_response(self):
        server = _make_server_stub()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "degraded"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        latency_ms, is_healthy = await _check_server(mock_client, server)

        assert is_healthy is False

    async def test_non_200_status_code(self):
        server = _make_server_stub()

        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        latency_ms, is_healthy = await _check_server(mock_client, server)

        assert is_healthy is False
        assert latency_ms >= 0

    async def test_timeout_raises_exception(self):
        server = _make_server_stub()

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(Exception, match="Timeout"):
            await _check_server(mock_client, server)

    async def test_connect_error_raises_exception(self):
        server = _make_server_stub()

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(Exception, match="Connection failed"):
            await _check_server(mock_client, server)

    async def test_strips_trailing_slash_from_base_url(self):
        server = _make_server_stub(base_url="https://trailing.example.com/")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        await _check_server(mock_client, server)
        mock_client.get.assert_called_once_with("https://trailing.example.com/mcp/health")


# ---------------------------------------------------------------------------
# _run_health_checks
# ---------------------------------------------------------------------------

class TestRunHealthChecks:
    async def test_updates_healthy_server_score_up(self):
        server = _make_server_stub(health_score=70, status="active")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [server]
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            return_value=mock_session_ctx,
        ), patch(
            "marketplace.services.mcp_health_monitor.httpx.AsyncClient"
        ) as MockClient:
            mock_http = AsyncMock()

            # Return healthy response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_http.get.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            await _run_health_checks()

        # Score should increase by 10 (70 -> 80), status active
        assert server.health_score == 80
        assert server.status == "active"

    async def test_updates_unhealthy_server_score_down(self):
        server = _make_server_stub(health_score=60, status="active")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [server]
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            return_value=mock_session_ctx,
        ), patch(
            "marketplace.services.mcp_health_monitor.httpx.AsyncClient"
        ) as MockClient:
            mock_http = AsyncMock()

            # Return unhealthy response (status != "ok")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "error"}
            mock_http.get.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            await _run_health_checks()

        # Score should decrease by 15 (60 -> 45), status degraded
        assert server.health_score == 45
        assert server.status == "degraded"

    async def test_exception_result_decreases_score(self):
        server = _make_server_stub(health_score=50, status="active")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [server]
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            return_value=mock_session_ctx,
        ), patch(
            "marketplace.services.mcp_health_monitor.httpx.AsyncClient"
        ) as MockClient:
            mock_http = AsyncMock()

            # Simulate connection error
            mock_http.get.side_effect = httpx.ConnectError("Connection refused")
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            await _run_health_checks()

        # Score should decrease by 20 (50 -> 30), status degraded
        assert server.health_score == 30
        assert server.status == "degraded"

    async def test_score_zero_sets_inactive(self):
        server = _make_server_stub(health_score=10, status="degraded")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [server]
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            return_value=mock_session_ctx,
        ), patch(
            "marketplace.services.mcp_health_monitor.httpx.AsyncClient"
        ) as MockClient:
            mock_http = AsyncMock()
            mock_http.get.side_effect = httpx.ConnectError("dead")
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            await _run_health_checks()

        # Score would be max(0, 10 - 20) = 0, status inactive
        assert server.health_score == 0
        assert server.status == "inactive"

    async def test_no_servers_returns_early(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            return_value=mock_session_ctx,
        ), patch(
            "marketplace.services.mcp_health_monitor.httpx.AsyncClient"
        ) as MockClient:
            await _run_health_checks()
            # httpx.AsyncClient should not be instantiated when no servers
            MockClient.assert_not_called()

    async def test_healthy_server_score_caps_at_100(self):
        server = _make_server_stub(health_score=95, status="active")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [server]
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            return_value=mock_session_ctx,
        ), patch(
            "marketplace.services.mcp_health_monitor.httpx.AsyncClient"
        ) as MockClient:
            mock_http = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_http.get.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            await _run_health_checks()

        # min(100, 95+10) = 100
        assert server.health_score == 100

    async def test_unhealthy_low_score_sets_inactive(self):
        """Server with score=15 and unhealthy response goes to 0 -> inactive."""
        server = _make_server_stub(health_score=15, status="degraded")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [server]
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            return_value=mock_session_ctx,
        ), patch(
            "marketplace.services.mcp_health_monitor.httpx.AsyncClient"
        ) as MockClient:
            mock_http = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "error"}
            mock_http.get.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            await _run_health_checks()

        # max(0, 15-15) = 0, score <= 20 -> inactive
        assert server.health_score == 0
        assert server.status == "inactive"

    async def test_none_health_score_uses_default(self):
        """When health_score is None, uses fallback defaults."""
        server = _make_server_stub(health_score=None, status="active")

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [server]
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            return_value=mock_session_ctx,
        ), patch(
            "marketplace.services.mcp_health_monitor.httpx.AsyncClient"
        ) as MockClient:
            mock_http = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_http.get.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            await _run_health_checks()

        # For healthy with None score: min(100, (None or 50) + 10) = 60
        assert server.health_score == 60
        assert server.status == "active"


# ---------------------------------------------------------------------------
# health_check_loop
# ---------------------------------------------------------------------------

class TestHealthCheckLoop:
    async def test_loop_calls_run_health_checks(self):
        """Verify the loop starts, waits, and calls _run_health_checks."""
        call_count = 0

        async def mock_run():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()

        with patch(
            "marketplace.services.mcp_health_monitor._run_health_checks",
            side_effect=mock_run,
        ), patch(
            "marketplace.services.mcp_health_monitor.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            with pytest.raises(asyncio.CancelledError):
                await health_check_loop(interval=1)

        assert call_count >= 1
        # Initial delay of 15s + at least one interval sleep
        assert mock_sleep.call_count >= 2

    async def test_loop_continues_on_exception(self):
        """The loop should catch exceptions and continue."""
        call_count = 0

        async def mock_run():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient error")
            if call_count >= 3:
                raise asyncio.CancelledError()

        with patch(
            "marketplace.services.mcp_health_monitor._run_health_checks",
            side_effect=mock_run,
        ), patch(
            "marketplace.services.mcp_health_monitor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            with pytest.raises(asyncio.CancelledError):
                await health_check_loop(interval=1)

        # Should have been called at least 3 times (error + success + cancel)
        assert call_count >= 3
