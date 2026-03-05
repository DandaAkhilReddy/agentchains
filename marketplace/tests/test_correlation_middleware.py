"""Tests for marketplace.core.correlation_middleware.CorrelationMiddleware.

Tests cover header generation, header preservation, JWT agent_id extraction,
and context var lifecycle.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.core.correlation_middleware import CorrelationMiddleware
from marketplace.core.structured_logging import (
    agent_id_var,
    correlation_id_var,
    request_id_var,
)


# ---------------------------------------------------------------------------
# Helpers — build a minimal fake Request / call_next
# ---------------------------------------------------------------------------


def _make_request(
    headers: dict[str, str] | None = None,
    method: str = "GET",
    path: str = "/health",
) -> MagicMock:
    req = MagicMock()
    req.method = method
    req.url.path = path
    req.headers = headers or {}
    return req


def _make_call_next(status_code: int = 200, body: bytes = b"ok") -> AsyncMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = {}
    response.body = body

    async def _call_next(request):
        return response

    return _call_next, response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_response_has_x_correlation_id_header():
    """Middleware always sets X-Correlation-ID on the response."""
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next()
    await middleware.dispatch(_make_request(), call_next)
    assert "X-Correlation-ID" in response.headers


async def test_response_has_x_request_id_header():
    """Middleware always sets X-Request-ID on the response."""
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next()
    await middleware.dispatch(_make_request(), call_next)
    assert "X-Request-ID" in response.headers


async def test_client_correlation_id_is_preserved():
    """Incoming X-Correlation-ID is echoed back unchanged."""
    incoming = "my-fixed-correlation-id"
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next()
    req = _make_request(headers={"X-Correlation-ID": incoming})
    await middleware.dispatch(req, call_next)
    assert response.headers["X-Correlation-ID"] == incoming


async def test_new_uuid_generated_when_no_incoming_header():
    """A fresh UUID is generated when the client sends no X-Correlation-ID."""
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next()
    await middleware.dispatch(_make_request(), call_next)
    cid = response.headers["X-Correlation-ID"]
    # Must be a parseable UUID
    uuid.UUID(cid)  # raises ValueError if not valid


async def test_request_id_is_new_uuid_each_time():
    """X-Request-ID is always a fresh UUID, even when correlation ID is provided."""
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next()
    req = _make_request(headers={"X-Correlation-ID": "fixed"})
    await middleware.dispatch(req, call_next)
    rid = response.headers["X-Request-ID"]
    uuid.UUID(rid)  # must be a valid UUID


async def test_context_vars_are_set_during_handler():
    """correlation_id_var and request_id_var are set inside call_next."""
    captured: dict[str, str] = {}

    async def _recording_call_next(request):
        captured["correlation_id"] = correlation_id_var.get("")
        captured["request_id"] = request_id_var.get("")
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {}
        return resp

    middleware = CorrelationMiddleware(app=MagicMock())
    req = _make_request(headers={"X-Correlation-ID": "ctx-test-corr"})
    await middleware.dispatch(req, _recording_call_next)
    assert captured["correlation_id"] == "ctx-test-corr"
    assert captured["request_id"] != ""


async def test_bearer_jwt_extracts_agent_id():
    """A valid Bearer JWT causes agent_id_var to be set during handler."""
    from marketplace.core.auth import create_access_token

    agent_id = str(uuid.uuid4())
    token = create_access_token(agent_id, "test-agent")

    captured: dict[str, str] = {}

    # Reset agent_id_var to empty before the test to avoid cross-test leakage
    reset_token = agent_id_var.set("")
    try:
        async def _recording_call_next(request):
            captured["agent_id"] = agent_id_var.get("")
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = {}
            return resp

        middleware = CorrelationMiddleware(app=MagicMock())
        req = _make_request(headers={"Authorization": f"Bearer {token}"})
        await middleware.dispatch(req, _recording_call_next)
        assert captured["agent_id"] == agent_id
    finally:
        agent_id_var.reset(reset_token)


async def test_no_authorization_header_no_agent_id():
    """Without an Authorization header, agent_id_var is not set by middleware."""
    # Ensure agent_id_var starts empty in this test
    reset_token = agent_id_var.set("")
    captured: dict[str, str] = {}

    try:
        async def _recording_call_next(request):
            # agent_id_var should remain "" since no JWT was provided
            captured["agent_id"] = agent_id_var.get("")
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = {}
            return resp

        middleware = CorrelationMiddleware(app=MagicMock())
        await middleware.dispatch(_make_request(), _recording_call_next)
        assert captured["agent_id"] == ""
    finally:
        agent_id_var.reset(reset_token)


async def test_malformed_jwt_no_crash():
    """A malformed JWT in the Authorization header does not crash the middleware."""
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next()
    req = _make_request(headers={"Authorization": "Bearer not.a.real.jwt"})
    # Must not raise
    await middleware.dispatch(req, call_next)
    assert response.headers["X-Correlation-ID"]


async def test_non_bearer_auth_ignored():
    """Basic auth or other schemes don't trigger JWT parsing."""
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next()
    req = _make_request(headers={"Authorization": "Basic dXNlcjpwYXNz"})
    await middleware.dispatch(req, call_next)
    # No crash, response headers still set
    assert "X-Correlation-ID" in response.headers


async def test_empty_bearer_token_no_crash():
    """Bearer with an empty token string does not raise."""
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next()
    req = _make_request(headers={"Authorization": "Bearer "})
    await middleware.dispatch(req, call_next)
    assert "X-Correlation-ID" in response.headers


async def test_context_vars_reset_after_request():
    """After dispatch completes, correlation_id_var is reset to its prior state."""
    prior_token = correlation_id_var.set("prior-value")
    try:
        middleware = CorrelationMiddleware(app=MagicMock())
        call_next, _ = _make_call_next()
        req = _make_request(headers={"X-Correlation-ID": "during-request"})
        await middleware.dispatch(req, call_next)
        # After dispatch, the token reset restores the prior value
        assert correlation_id_var.get("") == "prior-value"
    finally:
        correlation_id_var.reset(prior_token)


async def test_response_body_passes_through():
    """Middleware does not alter the response body."""
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next(body=b"hello world")
    await middleware.dispatch(_make_request(), call_next)
    assert response.body == b"hello world"


async def test_response_status_code_passes_through():
    """Middleware preserves the status code from the inner handler."""
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next(status_code=404)
    await middleware.dispatch(_make_request(), call_next)
    assert response.status_code == 404


async def test_request_id_header_preserved_if_provided():
    """Incoming X-Request-ID is echoed back if provided."""
    incoming_rid = "my-request-id-xyz"
    middleware = CorrelationMiddleware(app=MagicMock())
    call_next, response = _make_call_next()
    req = _make_request(headers={"X-Request-ID": incoming_rid})
    await middleware.dispatch(req, call_next)
    assert response.headers["X-Request-ID"] == incoming_rid


async def test_operation_context_var_set_to_method_and_path():
    """operation_var is set to '{METHOD} {path}' during dispatch."""
    from marketplace.core.structured_logging import operation_var

    captured: dict[str, str] = {}

    async def _recording_call_next(request):
        captured["operation"] = operation_var.get("")
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {}
        return resp

    middleware = CorrelationMiddleware(app=MagicMock())
    req = _make_request(method="POST", path="/api/v1/agents")
    await middleware.dispatch(req, _recording_call_next)
    assert captured["operation"] == "POST /api/v1/agents"


async def test_context_vars_reset_between_two_sequential_requests():
    """Each request gets independent context vars — no bleed between requests."""
    middleware = CorrelationMiddleware(app=MagicMock())

    ids_seen: list[str] = []

    async def _capture(request):
        ids_seen.append(correlation_id_var.get(""))
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {}
        return resp

    req1 = _make_request(headers={"X-Correlation-ID": "first"})
    req2 = _make_request(headers={"X-Correlation-ID": "second"})

    await middleware.dispatch(req1, _capture)
    await middleware.dispatch(req2, _capture)

    assert ids_seen[0] == "first"
    assert ids_seen[1] == "second"
