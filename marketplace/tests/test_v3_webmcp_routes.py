"""Integration tests for the v3 WebMCP API routes.

39 async tests exercising all 11 endpoints through the FastAPI ASGI transport
(httpx AsyncClient). Covers tool registration, discovery, approval, action
listing creation/browsing, and the full execution lifecycle including consent
enforcement and cancellation.

Route prefix: /api/v3/webmcp

Auth notes:
  - Creator endpoints (POST /tools, PUT /tools/{id}/approve) use
    ``Depends(get_current_creator_id)`` which reads ``authorization``
    as a *query parameter* (no ``Header()`` annotation), so creator tokens
    are passed as ``params={"authorization": f"Bearer {token}"}``.
  - Agent endpoints (POST /actions, POST /execute, GET /executions, …) use
    ``Depends(get_current_agent_id)`` which reads ``Authorization`` as a
    proper ``Header``, so agent tokens are passed as
    ``headers={"Authorization": f"Bearer {token}"}``.
"""

import pytest

V3 = "/api/v3/webmcp"


# ---------------------------------------------------------------------------
# Shared payload factories
# ---------------------------------------------------------------------------


def _tool_payload(**overrides) -> dict:
    """Build a minimal valid ToolRegisterRequest payload."""
    base = {
        "name": "price-checker",
        "description": "Check product prices on demand",
        "domain": "amazon.com",
        "endpoint_url": "https://amazon.com/.well-known/mcp",
        "category": "shopping",
        "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        "output_schema": {"type": "object"},
        "version": "1.0.0",
    }
    base.update(overrides)
    return base


def _action_payload(tool_id: str, **overrides) -> dict:
    """Build a minimal valid ActionCreateRequest payload."""
    base = {
        "tool_id": tool_id,
        "title": "Price Check Service",
        "description": "On-demand price lookup",
        "price_per_execution": 0.05,
        "max_executions_per_hour": 60,
        "requires_consent": True,
    }
    base.update(overrides)
    return base


def _creator_params(token: str) -> dict:
    """Return query-param dict for creator-auth endpoints."""
    return {"authorization": f"Bearer {token}"}


def _agent_headers(token: str) -> dict:
    """Return header dict for agent-auth endpoints."""
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# TestToolEndpoints — POST /tools, GET /tools, GET /tools/{id},
#                    PUT /tools/{id}/approve
# ---------------------------------------------------------------------------


class TestToolEndpoints:
    """Tests for the /api/v3/webmcp/tools family of endpoints."""

    @pytest.mark.asyncio
    async def test_register_tool_requires_creator_auth(self, client):
        """POST /tools without any authorization returns 401."""
        resp = await client.post(f"{V3}/tools", json=_tool_payload())
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_register_tool_rejects_agent_token(self, client, make_agent):
        """POST /tools with an agent JWT passed as creator query-param returns 401.

        An agent token lacks ``type: creator`` so get_current_creator_id raises.
        """
        agent, token = await make_agent()
        resp = await client.post(
            f"{V3}/tools",
            json=_tool_payload(),
            params=_creator_params(token),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_register_tool_creates_pending_tool(self, client, make_creator):
        """POST /tools with valid creator auth returns a new tool in pending status."""
        creator, token = await make_creator()
        resp = await client.post(
            f"{V3}/tools",
            json=_tool_payload(name="my-test-tool", domain="shop.test"),
            params=_creator_params(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "my-test-tool"
        assert body["domain"] == "shop.test"
        assert body["status"] == "pending"
        assert body["creator_id"] == creator.id
        assert body["id"] is not None

    @pytest.mark.asyncio
    async def test_register_tool_stores_schemas(self, client, make_creator):
        """POST /tools stores input_schema and output_schema as dicts."""
        creator, token = await make_creator()
        schema = {"type": "object", "properties": {"url": {"type": "string"}}}
        resp = await client.post(
            f"{V3}/tools",
            json=_tool_payload(input_schema=schema, output_schema={"type": "object"}),
            params=_creator_params(token),
        )
        assert resp.status_code == 200
        assert resp.json()["input_schema"] == schema

    @pytest.mark.asyncio
    async def test_list_tools_returns_empty_before_approval(self, client, make_creator):
        """GET /tools returns empty list when no tools are approved yet."""
        creator, token = await make_creator()
        # Register a tool (it will be pending)
        await client.post(
            f"{V3}/tools",
            json=_tool_payload(),
            params=_creator_params(token),
        )
        resp = await client.get(f"{V3}/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["tools"] == []

    @pytest.mark.asyncio
    async def test_list_tools_returns_tools_after_approval(self, client, make_creator):
        """GET /tools returns tools after they have been approved."""
        creator, token = await make_creator()

        reg = await client.post(
            f"{V3}/tools",
            json=_tool_payload(name="approved-tool"),
            params=_creator_params(token),
        )
        tool_id = reg.json()["id"]

        await client.put(
            f"{V3}/tools/{tool_id}/approve",
            json={"notes": "Looks good"},
            params=_creator_params(token),
        )

        resp = await client.get(f"{V3}/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["tools"][0]["id"] == tool_id

    @pytest.mark.asyncio
    async def test_list_tools_with_category_filter(self, client, make_creator):
        """GET /tools?category=research returns only tools matching that category."""
        creator, token = await make_creator()

        r1 = await client.post(
            f"{V3}/tools",
            json=_tool_payload(name="shop-tool", category="shopping"),
            params=_creator_params(token),
        )
        r2 = await client.post(
            f"{V3}/tools",
            json=_tool_payload(name="research-tool", category="research"),
            params=_creator_params(token),
        )

        for tool_id in [r1.json()["id"], r2.json()["id"]]:
            await client.put(
                f"{V3}/tools/{tool_id}/approve",
                json={"notes": "ok"},
                params=_creator_params(token),
            )

        resp = await client.get(f"{V3}/tools", params={"category": "research"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["tools"][0]["category"] == "research"

    @pytest.mark.asyncio
    async def test_list_tools_with_query_filter(self, client, make_creator):
        """GET /tools?q=<term> filters by name/description substring."""
        creator, token = await make_creator()

        r1 = await client.post(
            f"{V3}/tools",
            json=_tool_payload(name="product-search", description="Find products online"),
            params=_creator_params(token),
        )
        r2 = await client.post(
            f"{V3}/tools",
            json=_tool_payload(name="weather-api", description="Get weather data"),
            params=_creator_params(token),
        )
        for tid in [r1.json()["id"], r2.json()["id"]]:
            await client.put(
                f"{V3}/tools/{tid}/approve",
                json={},
                params=_creator_params(token),
            )

        resp = await client.get(f"{V3}/tools", params={"q": "product"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["tools"][0]["name"] == "product-search"

    @pytest.mark.asyncio
    async def test_get_tool_by_id_returns_tool(self, client, make_creator):
        """GET /tools/{tool_id} returns tool details regardless of approval status."""
        creator, token = await make_creator()
        reg = await client.post(
            f"{V3}/tools",
            json=_tool_payload(name="findable-tool"),
            params=_creator_params(token),
        )
        tool_id = reg.json()["id"]

        resp = await client.get(f"{V3}/tools/{tool_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == tool_id
        assert body["name"] == "findable-tool"

    @pytest.mark.asyncio
    async def test_get_tool_nonexistent_returns_404(self, client):
        """GET /tools/{bad_id} returns 404 when no tool exists with that id."""
        resp = await client.get(f"{V3}/tools/does-not-exist")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_approve_tool_changes_status_to_approved(self, client, make_creator):
        """PUT /tools/{id}/approve updates status from pending to approved."""
        creator, token = await make_creator()

        reg = await client.post(
            f"{V3}/tools",
            json=_tool_payload(),
            params=_creator_params(token),
        )
        tool_id = reg.json()["id"]
        assert reg.json()["status"] == "pending"

        resp = await client.put(
            f"{V3}/tools/{tool_id}/approve",
            json={"notes": "Verified by admin"},
            params=_creator_params(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["id"] == tool_id

    @pytest.mark.asyncio
    async def test_approve_tool_requires_creator_auth(self, client, make_creator, make_agent):
        """PUT /tools/{id}/approve with an agent token as query param returns 401."""
        creator, creator_token = await make_creator()
        agent, agent_token = await make_agent()

        reg = await client.post(
            f"{V3}/tools",
            json=_tool_payload(),
            params=_creator_params(creator_token),
        )
        tool_id = reg.json()["id"]

        # Agent token passed in the creator query-param position is invalid
        resp = await client.put(
            f"{V3}/tools/{tool_id}/approve",
            json={"notes": "Should fail"},
            params=_creator_params(agent_token),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_approve_nonexistent_tool_returns_404(self, client, make_creator):
        """PUT /tools/{bad_id}/approve returns 404 for an unknown tool."""
        creator, token = await make_creator()
        resp = await client.put(
            f"{V3}/tools/no-such-tool/approve",
            json={"notes": ""},
            params=_creator_params(token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestActionEndpoints — POST /actions, GET /actions, GET /actions/{id}
# ---------------------------------------------------------------------------


class TestActionEndpoints:
    """Tests for the /api/v3/webmcp/actions family of endpoints."""

    async def _registered_approved_tool(self, client, creator_token: str) -> str:
        """Register a tool and approve it; return the tool_id."""
        reg = await client.post(
            f"{V3}/tools",
            json=_tool_payload(),
            params=_creator_params(creator_token),
        )
        tool_id = reg.json()["id"]
        await client.put(
            f"{V3}/tools/{tool_id}/approve",
            json={},
            params=_creator_params(creator_token),
        )
        return tool_id

    @pytest.mark.asyncio
    async def test_create_action_requires_agent_auth(self, client, make_creator):
        """POST /actions without Authorization header returns 401."""
        creator, creator_token = await make_creator()
        tool_id = await self._registered_approved_tool(client, creator_token)

        resp = await client.post(f"{V3}/actions", json=_action_payload(tool_id))
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_action_creator_token_rejected(self, client, make_creator):
        """POST /actions with a creator JWT in the Authorization header returns 401.

        Creator tokens have ``type: creator`` which the agent auth dependency
        explicitly rejects.
        """
        creator, creator_token = await make_creator()
        tool_id = await self._registered_approved_tool(client, creator_token)

        resp = await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id),
            headers=_agent_headers(creator_token),  # wrong token type in header
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_action_for_approved_tool(self, client, make_creator, make_agent):
        """POST /actions creates a listing for an approved tool and returns it."""
        creator, creator_token = await make_creator()
        agent, agent_token = await make_agent()
        tool_id = await self._registered_approved_tool(client, creator_token)

        resp = await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id, title="My Action Listing", price_per_execution=0.1),
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["tool_id"] == tool_id
        assert body["seller_id"] == agent.id
        assert body["title"] == "My Action Listing"
        assert body["price_per_execution"] == pytest.approx(0.1)
        assert body["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_action_with_unapproved_tool_returns_400(
        self, client, make_creator, make_agent
    ):
        """POST /actions for a pending (unapproved) tool returns 400."""
        creator, creator_token = await make_creator()
        agent, agent_token = await make_agent()

        # Register without approving
        reg = await client.post(
            f"{V3}/tools",
            json=_tool_payload(),
            params=_creator_params(creator_token),
        )
        tool_id = reg.json()["id"]

        resp = await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id),
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 400
        assert "not approved" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_action_with_nonexistent_tool_returns_400(
        self, client, make_agent
    ):
        """POST /actions referencing a non-existent tool returns 400."""
        agent, agent_token = await make_agent()
        resp = await client.post(
            f"{V3}/actions",
            json=_action_payload("no-such-tool-id"),
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_actions_returns_empty_initially(self, client):
        """GET /actions returns empty list when no action listings exist."""
        resp = await client.get(f"{V3}/actions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["actions"] == []

    @pytest.mark.asyncio
    async def test_list_actions_returns_created_listings(self, client, make_creator, make_agent):
        """GET /actions returns all active listings after creation."""
        creator, creator_token = await make_creator()
        agent, agent_token = await make_agent()
        tool_id = await self._registered_approved_tool(client, creator_token)

        await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id, title="Listing A"),
            headers=_agent_headers(agent_token),
        )
        await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id, title="Listing B"),
            headers=_agent_headers(agent_token),
        )

        resp = await client.get(f"{V3}/actions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["actions"]) == 2

    @pytest.mark.asyncio
    async def test_list_actions_max_price_filter(self, client, make_creator, make_agent):
        """GET /actions?max_price=0.05 returns only listings at or below threshold."""
        creator, creator_token = await make_creator()
        agent, agent_token = await make_agent()
        tool_id = await self._registered_approved_tool(client, creator_token)

        await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id, title="Cheap", price_per_execution=0.01),
            headers=_agent_headers(agent_token),
        )
        await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id, title="Expensive", price_per_execution=5.00),
            headers=_agent_headers(agent_token),
        )

        resp = await client.get(f"{V3}/actions", params={"max_price": 0.05})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["actions"][0]["title"] == "Cheap"

    @pytest.mark.asyncio
    async def test_get_action_by_id_returns_listing(self, client, make_creator, make_agent):
        """GET /actions/{action_id} returns details for a specific listing."""
        creator, creator_token = await make_creator()
        agent, agent_token = await make_agent()
        tool_id = await self._registered_approved_tool(client, creator_token)

        created = await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id, title="Unique Listing"),
            headers=_agent_headers(agent_token),
        )
        action_id = created.json()["id"]

        resp = await client.get(f"{V3}/actions/{action_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == action_id
        assert body["title"] == "Unique Listing"

    @pytest.mark.asyncio
    async def test_get_action_nonexistent_returns_404(self, client):
        """GET /actions/{bad_id} returns 404 for an unknown listing."""
        resp = await client.get(f"{V3}/actions/no-such-action")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TestExecutionEndpoints — POST /execute/{id}, GET /executions,
#                          GET /executions/{id}, POST /executions/{id}/cancel
# ---------------------------------------------------------------------------


class TestExecutionEndpoints:
    """Tests for the /api/v3/webmcp/execute and /executions endpoints."""

    async def _setup_approved_listing(
        self, client, make_creator, make_agent, *, requires_consent: bool = True
    ) -> tuple[str, str, str]:
        """Full setup: register + approve tool + create listing.

        Returns (action_id, creator_token, agent_token).
        """
        creator, creator_token = await make_creator()
        agent, agent_token = await make_agent()

        reg = await client.post(
            f"{V3}/tools",
            json=_tool_payload(name="exec-tool"),
            params=_creator_params(creator_token),
        )
        tool_id = reg.json()["id"]
        await client.put(
            f"{V3}/tools/{tool_id}/approve",
            json={"notes": "ready"},
            params=_creator_params(creator_token),
        )
        listing = await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id, requires_consent=requires_consent),
            headers=_agent_headers(agent_token),
        )
        action_id = listing.json()["id"]
        return action_id, creator_token, agent_token

    @pytest.mark.asyncio
    async def test_execute_action_requires_agent_auth(self, client, make_creator, make_agent):
        """POST /execute/{id} without Authorization header returns 401."""
        action_id, _, _ = await self._setup_approved_listing(client, make_creator, make_agent)
        resp = await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {}, "consent": True},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_execute_action_without_consent_returns_400(
        self, client, make_creator, make_agent
    ):
        """POST /execute/{id} without consent=True returns 400 when listing requires_consent."""
        action_id, _, agent_token = await self._setup_approved_listing(
            client, make_creator, make_agent, requires_consent=True,
        )
        resp = await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {}, "consent": False},
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 400
        assert "consent" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_execute_action_with_consent_returns_execution(
        self, client, make_creator, make_agent
    ):
        """POST /execute/{id} with consent=True returns a completed execution dict."""
        action_id, _, agent_token = await self._setup_approved_listing(
            client, make_creator, make_agent,
        )
        resp = await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {"q": "laptop"}, "consent": True},
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["action_listing_id"] == action_id
        assert body["status"] in ("completed", "failed")
        assert body["id"] is not None

    @pytest.mark.asyncio
    async def test_execute_action_result_contains_proof(
        self, client, make_creator, make_agent
    ):
        """A successful execution includes a proof_of_execution JWT and proof_verified=True."""
        action_id, _, agent_token = await self._setup_approved_listing(
            client, make_creator, make_agent,
        )
        resp = await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {}, "consent": True},
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        # Simulated execution always produces a signed proof
        assert body["status"] == "completed"
        assert body["proof_verified"] is True
        assert isinstance(body["proof_of_execution"], str)
        assert len(body["proof_of_execution"]) > 0

    @pytest.mark.asyncio
    async def test_execute_no_consent_flag_not_required_when_listing_allows(
        self, client, make_creator, make_agent
    ):
        """POST /execute/{id} with consent=False succeeds when requires_consent=False."""
        action_id, _, agent_token = await self._setup_approved_listing(
            client, make_creator, make_agent, requires_consent=False,
        )
        resp = await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {}, "consent": False},
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_action_returns_400(
        self, client, make_agent
    ):
        """POST /execute/{bad_id} returns 400 when the listing does not exist."""
        agent, agent_token = await make_agent()
        resp = await client.post(
            f"{V3}/execute/no-such-listing",
            json={"parameters": {}, "consent": True},
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_executions_requires_agent_auth(self, client):
        """GET /executions without Authorization header returns 401."""
        resp = await client.get(f"{V3}/executions")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_executions_returns_empty_initially(self, client, make_agent):
        """GET /executions returns empty list for an agent with no executions."""
        agent, agent_token = await make_agent()
        resp = await client.get(
            f"{V3}/executions",
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["executions"] == []

    @pytest.mark.asyncio
    async def test_list_executions_returns_own_executions(
        self, client, make_creator, make_agent
    ):
        """GET /executions returns executions belonging to the authenticated agent."""
        action_id, _, agent_token = await self._setup_approved_listing(
            client, make_creator, make_agent,
        )
        # Execute twice
        await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {}, "consent": True},
            headers=_agent_headers(agent_token),
        )
        await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {"extra": "val"}, "consent": True},
            headers=_agent_headers(agent_token),
        )

        resp = await client.get(f"{V3}/executions", headers=_agent_headers(agent_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["executions"]) == 2

    @pytest.mark.asyncio
    async def test_list_executions_isolation_between_agents(
        self, client, make_creator, make_agent
    ):
        """GET /executions only returns executions belonging to the requesting agent."""
        creator, creator_token = await make_creator()
        agent_a, token_a = await make_agent(name="agent-alpha")
        agent_b, token_b = await make_agent(name="agent-beta")

        reg = await client.post(
            f"{V3}/tools",
            json=_tool_payload(name="shared-tool"),
            params=_creator_params(creator_token),
        )
        tool_id = reg.json()["id"]
        await client.put(
            f"{V3}/tools/{tool_id}/approve",
            json={},
            params=_creator_params(creator_token),
        )
        listing = await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id, requires_consent=False),
            headers=_agent_headers(token_a),
        )
        action_id = listing.json()["id"]

        # agent_a executes
        await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {}, "consent": False},
            headers=_agent_headers(token_a),
        )

        # agent_b sees no executions
        resp = await client.get(f"{V3}/executions", headers=_agent_headers(token_b))
        body = resp.json()
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_get_execution_by_id_returns_details(
        self, client, make_creator, make_agent
    ):
        """GET /executions/{id} returns the matching execution record."""
        action_id, _, agent_token = await self._setup_approved_listing(
            client, make_creator, make_agent,
        )
        exec_resp = await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {}, "consent": True},
            headers=_agent_headers(agent_token),
        )
        execution_id = exec_resp.json()["id"]

        resp = await client.get(
            f"{V3}/executions/{execution_id}",
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == execution_id
        assert body["action_listing_id"] == action_id

    @pytest.mark.asyncio
    async def test_get_execution_requires_agent_auth(
        self, client, make_creator, make_agent
    ):
        """GET /executions/{id} without Authorization header returns 401."""
        action_id, _, agent_token = await self._setup_approved_listing(
            client, make_creator, make_agent,
        )
        exec_resp = await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {}, "consent": True},
            headers=_agent_headers(agent_token),
        )
        execution_id = exec_resp.json()["id"]

        resp = await client.get(f"{V3}/executions/{execution_id}")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_execution_nonexistent_returns_404(self, client, make_agent):
        """GET /executions/{bad_id} returns 404 when no such execution exists."""
        agent, agent_token = await make_agent()
        resp = await client.get(
            f"{V3}/executions/no-such-exec",
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cancel_execution_requires_agent_auth(self, client):
        """POST /executions/{id}/cancel without auth returns 401."""
        resp = await client.post(f"{V3}/executions/any-id/cancel")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_cancel_completed_execution_returns_400(
        self, client, make_creator, make_agent
    ):
        """POST /executions/{id}/cancel on an already-completed execution returns 400.

        The executor completes the execution synchronously; cancellation of a
        completed execution violates the state machine and raises ValueError.
        """
        action_id, _, agent_token = await self._setup_approved_listing(
            client, make_creator, make_agent,
        )
        exec_resp = await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {}, "consent": True},
            headers=_agent_headers(agent_token),
        )
        execution_id = exec_resp.json()["id"]
        assert exec_resp.json()["status"] == "completed"

        cancel_resp = await client.post(
            f"{V3}/executions/{execution_id}/cancel",
            headers=_agent_headers(agent_token),
        )
        assert cancel_resp.status_code == 400

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_execution_returns_404(self, client, make_agent):
        """POST /executions/{bad_id}/cancel returns 404 for an unknown execution."""
        agent, agent_token = await make_agent()
        resp = await client.post(
            f"{V3}/executions/no-such-exec/cancel",
            headers=_agent_headers(agent_token),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_executions_pagination_envelope(self, client, make_agent):
        """GET /executions response always includes the full pagination envelope."""
        agent, agent_token = await make_agent()
        resp = await client.get(
            f"{V3}/executions",
            headers=_agent_headers(agent_token),
            params={"page": 1, "page_size": 10},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "executions" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert body["page"] == 1
        assert body["page_size"] == 10

    @pytest.mark.asyncio
    async def test_execution_amount_usdc_matches_listing_price(
        self, client, make_creator, make_agent
    ):
        """The execution record's amount_usdc equals the listing's price_per_execution."""
        creator, creator_token = await make_creator()
        agent, agent_token = await make_agent()

        reg = await client.post(
            f"{V3}/tools",
            json=_tool_payload(name="priced-tool"),
            params=_creator_params(creator_token),
        )
        tool_id = reg.json()["id"]
        await client.put(
            f"{V3}/tools/{tool_id}/approve",
            json={},
            params=_creator_params(creator_token),
        )
        listing_resp = await client.post(
            f"{V3}/actions",
            json=_action_payload(tool_id, price_per_execution=0.25, requires_consent=False),
            headers=_agent_headers(agent_token),
        )
        action_id = listing_resp.json()["id"]

        exec_resp = await client.post(
            f"{V3}/execute/{action_id}",
            json={"parameters": {}, "consent": False},
            headers=_agent_headers(agent_token),
        )
        assert exec_resp.status_code == 200
        body = exec_resp.json()
        assert body["amount_usdc"] == pytest.approx(0.25)

    @pytest.mark.asyncio
    async def test_list_tools_pagination_envelope(self, client):
        """GET /tools response includes the full pagination envelope."""
        resp = await client.get(f"{V3}/tools", params={"page": 1, "page_size": 5})
        assert resp.status_code == 200
        body = resp.json()
        assert "tools" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert body["page"] == 1
        assert body["page_size"] == 5

    @pytest.mark.asyncio
    async def test_list_actions_pagination_envelope(self, client):
        """GET /actions response includes the full pagination envelope."""
        resp = await client.get(f"{V3}/actions", params={"page": 2, "page_size": 15})
        assert resp.status_code == 200
        body = resp.json()
        assert "actions" in body
        assert "total" in body
        assert body["page"] == 2
        assert body["page_size"] == 15
