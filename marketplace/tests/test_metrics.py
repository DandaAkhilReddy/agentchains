"""Tests for Prometheus metrics, MetricsMiddleware, and /metrics endpoint.

Prometheus uses a global registry, so tests that inspect raw metric values
must be handled carefully. We test:
  - Metric objects exist with correct configuration
  - _normalize_path logic
  - MetricsMiddleware skips /metrics and records method/status
  - GET /metrics returns Prometheus text format
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.core.metrics import (
    ACTIVE_WORKFLOWS,
    AGENT_CALL_COST,
    AGENT_CALL_LATENCY,
    CIRCUIT_BREAKER_STATE,
    MODEL_TOKENS_TOTAL,
    REQUEST_COUNT,
    REQUEST_LATENCY,
)
from marketplace.core.metrics_middleware import MetricsMiddleware, _normalize_path


# ---------------------------------------------------------------------------
# Metric object existence and configuration
# ---------------------------------------------------------------------------


def test_request_count_is_counter():
    """REQUEST_COUNT is a Prometheus Counter."""
    from prometheus_client import Counter
    assert isinstance(REQUEST_COUNT, Counter)


def test_request_latency_is_histogram():
    """REQUEST_LATENCY is a Prometheus Histogram."""
    from prometheus_client import Histogram
    assert isinstance(REQUEST_LATENCY, Histogram)


def test_agent_call_latency_exists():
    """AGENT_CALL_LATENCY is a Prometheus Histogram."""
    from prometheus_client import Histogram
    assert isinstance(AGENT_CALL_LATENCY, Histogram)


def test_agent_call_cost_exists():
    """AGENT_CALL_COST is a Prometheus Counter."""
    from prometheus_client import Counter
    assert isinstance(AGENT_CALL_COST, Counter)


def test_model_tokens_total_exists():
    """MODEL_TOKENS_TOTAL is a Prometheus Counter."""
    from prometheus_client import Counter
    assert isinstance(MODEL_TOKENS_TOTAL, Counter)


def test_active_workflows_is_gauge():
    """ACTIVE_WORKFLOWS is a Prometheus Gauge."""
    from prometheus_client import Gauge
    assert isinstance(ACTIVE_WORKFLOWS, Gauge)


def test_circuit_breaker_state_is_gauge():
    """CIRCUIT_BREAKER_STATE is a Prometheus Gauge."""
    from prometheus_client import Gauge
    assert isinstance(CIRCUIT_BREAKER_STATE, Gauge)


# ---------------------------------------------------------------------------
# _normalize_path tests
# ---------------------------------------------------------------------------


def test_normalize_path_preserves_plain_segments():
    """Named segments are kept as-is."""
    assert _normalize_path("/api/v1/agents") == "/api/v1/agents"


def test_normalize_path_collapses_uuid():
    """UUID path segments are replaced with {id}."""
    uuid_str = "550e8400-e29b-41d4-a716-446655440000"
    result = _normalize_path(f"/api/v1/agents/{uuid_str}")
    assert result == "/api/v1/agents/{id}"


def test_normalize_path_collapses_integer():
    """Pure numeric segments are replaced with {id}."""
    assert _normalize_path("/api/v1/listings/42") == "/api/v1/listings/{id}"


def test_normalize_path_collapses_uuid_mid_path():
    """UUID in the middle of a longer path is collapsed."""
    uuid_str = "123e4567-e89b-12d3-a456-426614174000"
    result = _normalize_path(f"/api/v1/agents/{uuid_str}/skills")
    assert result == "/api/v1/agents/{id}/skills"


def test_normalize_path_multiple_ids():
    """Multiple UUID/int segments each get collapsed."""
    uuid_str = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
    result = _normalize_path(f"/api/v1/agents/{uuid_str}/items/99")
    assert result == "/api/v1/agents/{id}/items/{id}"


def test_normalize_path_root():
    """Root path is returned unchanged."""
    assert _normalize_path("/") == "/"


def test_normalize_path_empty_string():
    """Empty string returns root slash."""
    result = _normalize_path("")
    assert result == "/"


def test_normalize_path_non_uuid_hex_not_collapsed():
    """A hex string that is NOT UUID format is NOT collapsed."""
    result = _normalize_path("/api/v1/hash/abc123def456")
    assert result == "/api/v1/hash/abc123def456"


# ---------------------------------------------------------------------------
# MetricsMiddleware behaviour
# ---------------------------------------------------------------------------


def _make_request_mock(path: str, method: str = "GET") -> MagicMock:
    req = MagicMock()
    req.url.path = path
    req.method = method
    return req


def _make_call_next_mock(status_code: int = 200) -> tuple[AsyncMock, MagicMock]:
    response = MagicMock()
    response.status_code = status_code
    response.headers = {}

    async def _call_next(request):
        return response

    return _call_next, response


async def test_metrics_middleware_skips_metrics_endpoint():
    """/metrics path is not instrumented (avoid recursive counting)."""
    middleware = MetricsMiddleware(app=MagicMock())
    call_next, _ = _make_call_next_mock()

    with patch.object(REQUEST_COUNT, "labels") as mock_labels:
        req = _make_request_mock("/metrics")
        await middleware.dispatch(req, call_next)
        mock_labels.assert_not_called()


async def test_metrics_middleware_records_request_count():
    """Non-/metrics requests increment REQUEST_COUNT."""
    middleware = MetricsMiddleware(app=MagicMock())
    call_next, _ = _make_call_next_mock(status_code=200)

    incremented = {}

    original_labels = REQUEST_COUNT.labels

    def _capturing_labels(**kwargs):
        incremented.update(kwargs)
        return original_labels(**kwargs)

    with patch.object(REQUEST_COUNT, "labels", side_effect=_capturing_labels):
        req = _make_request_mock("/api/v1/health", method="GET")
        await middleware.dispatch(req, call_next)

    assert incremented.get("method") == "GET"
    assert incremented.get("status_code") == "200"


async def test_metrics_middleware_records_latency():
    """Non-/metrics requests call REQUEST_LATENCY.observe."""
    middleware = MetricsMiddleware(app=MagicMock())
    call_next, _ = _make_call_next_mock()

    observed: list[float] = []

    original_labels = REQUEST_LATENCY.labels

    def _capturing_labels(**kwargs):
        obj = original_labels(**kwargs)
        original_observe = obj.observe

        def _capturing_observe(duration):
            observed.append(duration)
            original_observe(duration)

        obj.observe = _capturing_observe
        return obj

    with patch.object(REQUEST_LATENCY, "labels", side_effect=_capturing_labels):
        req = _make_request_mock("/api/v1/listings", method="GET")
        await middleware.dispatch(req, call_next)

    assert len(observed) == 1
    assert observed[0] >= 0.0


async def test_metrics_middleware_records_error_status():
    """500 status is recorded in REQUEST_COUNT labels."""
    middleware = MetricsMiddleware(app=MagicMock())
    call_next, _ = _make_call_next_mock(status_code=500)

    recorded_status: list[str] = []
    original_labels = REQUEST_COUNT.labels

    def _capturing_labels(**kwargs):
        recorded_status.append(kwargs.get("status_code", ""))
        return original_labels(**kwargs)

    with patch.object(REQUEST_COUNT, "labels", side_effect=_capturing_labels):
        req = _make_request_mock("/api/v1/agents", method="POST")
        await middleware.dispatch(req, call_next)

    assert "500" in recorded_status


async def test_metrics_middleware_records_http_method():
    """HTTP method is captured in REQUEST_COUNT labels."""
    middleware = MetricsMiddleware(app=MagicMock())
    call_next, _ = _make_call_next_mock()

    recorded_method: list[str] = []
    original_labels = REQUEST_COUNT.labels

    def _capturing_labels(**kwargs):
        recorded_method.append(kwargs.get("method", ""))
        return original_labels(**kwargs)

    with patch.object(REQUEST_COUNT, "labels", side_effect=_capturing_labels):
        req = _make_request_mock("/api/v1/listings", method="DELETE")
        await middleware.dispatch(req, call_next)

    assert "DELETE" in recorded_method


async def test_metrics_middleware_normalizes_path_in_labels():
    """UUID in path is collapsed to {id} in recorded endpoint label."""
    middleware = MetricsMiddleware(app=MagicMock())
    call_next, _ = _make_call_next_mock()

    recorded_endpoint: list[str] = []
    original_labels = REQUEST_COUNT.labels

    def _capturing_labels(**kwargs):
        recorded_endpoint.append(kwargs.get("endpoint", ""))
        return original_labels(**kwargs)

    uuid_str = "550e8400-e29b-41d4-a716-446655440000"
    with patch.object(REQUEST_COUNT, "labels", side_effect=_capturing_labels):
        req = _make_request_mock(f"/api/v1/agents/{uuid_str}", method="GET")
        await middleware.dispatch(req, call_next)

    assert "/api/v1/agents/{id}" in recorded_endpoint


# ---------------------------------------------------------------------------
# /metrics endpoint via client fixture
# ---------------------------------------------------------------------------


async def test_get_metrics_endpoint_returns_200(client):
    """GET /metrics returns 200 OK."""
    resp = await client.get("/metrics")
    assert resp.status_code == 200


async def test_get_metrics_endpoint_returns_prometheus_format(client):
    """GET /metrics body contains Prometheus HELP comment."""
    resp = await client.get("/metrics")
    assert b"# HELP" in resp.content


async def test_get_metrics_endpoint_content_type(client):
    """GET /metrics has the Prometheus content-type header."""
    resp = await client.get("/metrics")
    assert "text/plain" in resp.headers.get("content-type", "")
