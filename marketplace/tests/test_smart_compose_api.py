"""Tests for POST /api/v5/chains/smart-compose endpoint.

Covers:
- Endpoint exists and returns 200 (not 404/405)
- Valid request body returns orchestrator result dict
- Missing task_description returns 422
- task_description below min_length (< 5 chars) returns 422
- task_description above max_length (> 2000 chars) returns 422
- auto_approve defaults to True when omitted
- auto_approve=False is forwarded to SmartOrchestrator
- Unauthenticated request returns 401
- Orchestrator exception is wrapped as 500
- SmartOrchestrator is constructed with the correct arguments
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from marketplace.database import get_db
from marketplace.main import app


# ---------------------------------------------------------------------------
# In-memory DB + httpx client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def _db_engine():
    """Create and tear down an in-memory SQLite engine for one test."""
    from marketplace.database import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(_db_engine) -> httpx.AsyncClient:
    """httpx AsyncClient wired to the FastAPI app with an in-memory DB override."""
    factory = async_sessionmaker(
        _db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    # Create a real agent and JWT so auth passes cleanly
    from marketplace.core.auth import create_access_token
    from marketplace.models.agent import RegisteredAgent

    async with factory() as session:
        agent = RegisteredAgent(
            id="smart-compose-test-agent",
            name="SmartComposeTestAgent",
            agent_type="both",
            public_key="ssh-rsa AAAA_test_key_placeholder",
            status="active",
        )
        session.add(agent)
        await session.commit()

    token = create_access_token("smart-compose-test-agent", "SmartComposeTestAgent")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Canned orchestrator result
# ---------------------------------------------------------------------------

_CANNED_RESULT: dict[str, Any] = {
    "task_description": "fetch and analyse market data",
    "capabilities": ["data", "analysis"],
    "assignments": [{"capability": "data", "agent": {"agent_id": "ag-1", "name": "DataAgent"}}],
    "error": "",
    "method": "fallback",
}


# ---------------------------------------------------------------------------
# Helper: mock SmartOrchestrator at the API layer
# ---------------------------------------------------------------------------

def _mock_orchestrator(result: dict = _CANNED_RESULT, *, raises: Exception | None = None):
    """Return a context manager that patches SmartOrchestrator in the API module."""
    mock_orch_instance = MagicMock()
    if raises is not None:
        mock_orch_instance.compose_and_execute = AsyncMock(side_effect=raises)
    else:
        mock_orch_instance.compose_and_execute = AsyncMock(return_value=result)

    mock_orch_cls = MagicMock(return_value=mock_orch_instance)
    return patch("marketplace.api.v5_chains.SmartOrchestrator", mock_orch_cls)


# ---------------------------------------------------------------------------
# Endpoint existence / method
# ---------------------------------------------------------------------------


class TestSmartComposeEndpointExists:
    """Basic reachability and method checks."""

    async def test_post_returns_200_not_404_or_405(self, client: httpx.AsyncClient) -> None:
        """POST /chains/smart-compose returns 200, not a routing error."""
        with _mock_orchestrator():
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={"task_description": "fetch and analyse market data"},
            )
        assert resp.status_code not in {404, 405}, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        assert resp.status_code == 200

    async def test_get_method_not_allowed(self, client: httpx.AsyncClient) -> None:
        """GET /chains/smart-compose should return 405."""
        resp = await client.get("/api/v5/chains/smart-compose")
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSmartComposeHappyPath:
    """Valid request → structured orchestrator result."""

    async def test_returns_orchestrator_result(self, client: httpx.AsyncClient) -> None:
        with _mock_orchestrator():
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={"task_description": "fetch and analyse market data"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["method"] == "fallback"
        assert "assignments" in data
        assert data["task_description"] == "fetch and analyse market data"

    async def test_auto_approve_defaults_to_true(self, client: httpx.AsyncClient) -> None:
        """When auto_approve is omitted, SmartOrchestrator receives auto_approve=True."""
        with _mock_orchestrator() as mock_cls:
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={"task_description": "fetch market data please"},
            )
        assert resp.status_code == 200
        # Verify constructor was called with auto_approve=True
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("auto_approve") is True

    async def test_auto_approve_false_forwarded(self, client: httpx.AsyncClient) -> None:
        """When auto_approve=False is sent, SmartOrchestrator receives it as False."""
        with _mock_orchestrator() as mock_cls:
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={
                    "task_description": "fetch market data please",
                    "auto_approve": False,
                },
            )
        assert resp.status_code == 200
        call_kwargs = mock_cls.call_args
        assert call_kwargs.kwargs.get("auto_approve") is False

    async def test_compose_and_execute_called_with_task_description(
        self, client: httpx.AsyncClient
    ) -> None:
        """compose_and_execute receives the exact task_description from the request."""
        with _mock_orchestrator() as mock_cls:
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={"task_description": "unique task description here"},
            )
        assert resp.status_code == 200
        mock_instance = mock_cls.return_value
        mock_instance.compose_and_execute.assert_awaited_once()
        call_args = mock_instance.compose_and_execute.call_args
        assert call_args.kwargs["task_description"] == "unique task description here"

    async def test_compose_and_execute_receives_agent_id_as_initiated_by(
        self, client: httpx.AsyncClient
    ) -> None:
        """The authenticated agent_id is forwarded as initiated_by."""
        with _mock_orchestrator() as mock_cls:
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={"task_description": "fetch and analyse data here"},
            )
        assert resp.status_code == 200
        mock_instance = mock_cls.return_value
        call_args = mock_instance.compose_and_execute.call_args
        assert call_args.kwargs["initiated_by"] == "smart-compose-test-agent"


# ---------------------------------------------------------------------------
# Validation errors (422)
# ---------------------------------------------------------------------------


class TestSmartComposeValidation:
    """Request schema validation edge cases."""

    async def test_missing_task_description_returns_422(
        self, client: httpx.AsyncClient
    ) -> None:
        resp = await client.post("/api/v5/chains/smart-compose", json={})
        assert resp.status_code == 422
        body = resp.json()
        # Pydantic v2 error detail locates the missing field
        fields = [e["loc"] for e in body["detail"]]
        assert any("task_description" in loc for loc in fields)

    async def test_task_description_below_min_length_returns_422(
        self, client: httpx.AsyncClient
    ) -> None:
        """task_description must be at least 5 characters."""
        resp = await client.post(
            "/api/v5/chains/smart-compose",
            json={"task_description": "hi"},  # 2 chars < 5
        )
        assert resp.status_code == 422

    async def test_task_description_at_min_length_passes(
        self, client: httpx.AsyncClient
    ) -> None:
        """Exactly 5 characters is the minimum — should pass validation."""
        with _mock_orchestrator():
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={"task_description": "hello"},  # exactly 5 chars
            )
        assert resp.status_code == 200

    async def test_task_description_above_max_length_returns_422(
        self, client: httpx.AsyncClient
    ) -> None:
        """task_description above 2000 chars must be rejected."""
        long_desc = "x" * 2001
        resp = await client.post(
            "/api/v5/chains/smart-compose",
            json={"task_description": long_desc},
        )
        assert resp.status_code == 422

    async def test_task_description_at_max_length_passes(
        self, client: httpx.AsyncClient
    ) -> None:
        """Exactly 2000 characters is the maximum — should pass validation."""
        with _mock_orchestrator():
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={"task_description": "a" * 2000},
            )
        assert resp.status_code == 200

    async def test_auto_approve_must_be_boolean(self, client: httpx.AsyncClient) -> None:
        """auto_approve is a boolean field — non-boolean value coerces or rejects."""
        with _mock_orchestrator():
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={"task_description": "valid task here", "auto_approve": "yes"},
            )
        # Pydantic v2 coerces "yes" → True or returns 422. Either is acceptable.
        assert resp.status_code in {200, 422}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestSmartComposeAuth:
    """Endpoint requires a valid JWT."""

    async def test_unauthenticated_request_returns_401(self, _db_engine) -> None:
        """Without an Authorization header the endpoint rejects the request."""
        factory = async_sessionmaker(
            _db_engine, class_=AsyncSession, expire_on_commit=False
        )

        async def _override_db():
            async with factory() as session:
                yield session

        app.dependency_overrides[get_db] = _override_db

        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as unauthenticated_client:
                resp = await unauthenticated_client.post(
                    "/api/v5/chains/smart-compose",
                    json={"task_description": "fetch some data here"},
                )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.clear()

    async def test_invalid_token_returns_401(self, _db_engine) -> None:
        """A malformed JWT is rejected."""
        factory = async_sessionmaker(
            _db_engine, class_=AsyncSession, expire_on_commit=False
        )

        async def _override_db():
            async with factory() as session:
                yield session

        app.dependency_overrides[get_db] = _override_db

        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
            ) as bad_client:
                resp = await bad_client.post(
                    "/api/v5/chains/smart-compose",
                    json={"task_description": "fetch some data here"},
                )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


class TestSmartComposeErrorPropagation:
    """Orchestrator failures are surfaced correctly."""

    async def test_orchestrator_exception_returns_500(
        self, client: httpx.AsyncClient
    ) -> None:
        """If compose_and_execute raises, the endpoint returns 500."""
        with _mock_orchestrator(raises=RuntimeError("unexpected orchestration failure")):
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={"task_description": "fetch and analyse data"},
            )
        assert resp.status_code == 500
        body = resp.json()
        assert "unexpected orchestration failure" in body.get("detail", "")

    async def test_orchestrator_result_with_error_field_still_returns_200(
        self, client: httpx.AsyncClient
    ) -> None:
        """A result dict with a non-empty error field is still a 200 response.

        The orchestrator communicates partial failures via the error field,
        not by raising exceptions.
        """
        partial_result = {
            "task_description": "fetch data",
            "method": "fallback",
            "assignments": [],
            "capabilities": [],
            "error": "No agents found for any capability",
        }
        with _mock_orchestrator(result=partial_result):
            resp = await client.post(
                "/api/v5/chains/smart-compose",
                json={"task_description": "fetch some data"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] == "No agents found for any capability"
        assert data["method"] == "fallback"
