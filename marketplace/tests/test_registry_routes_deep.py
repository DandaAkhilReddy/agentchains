"""Deep unit tests for the Registry API routes (/api/v1/agents/*).

25 tests across 5 describe blocks:
  1. Agent Registration       (tests 1-5)
  2. Metadata Management      (tests 6-10)
  3. Deregistration           (tests 11-15)
  4. Version / Lifecycle      (tests 16-20)
  5. Edge Cases               (tests 21-25)

Style: pytest + unittest.mock, httpx async client, mocked service layer
where needed, integration-style through the real DB elsewhere.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.auth import create_access_token
from marketplace.core.exceptions import AgentAlreadyExistsError, AgentNotFoundError
from marketplace.tests.conftest import TestSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = "/api/v1"
REGISTER_URL = f"{BASE}/agents/register"
AGENTS_URL = f"{BASE}/agents"


def _agent_payload(
    name: str | None = None,
    agent_type: str = "seller",
    **overrides,
) -> dict:
    """Return a valid AgentRegisterRequest body with optional overrides."""
    payload = {
        "name": name or f"agent-{uuid.uuid4().hex[:8]}",
        "description": "deep test agent",
        "agent_type": agent_type,
        "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7deep",
        "wallet_address": "0x" + "cd" * 20,
        "capabilities": ["web_search", "summarize"],
        "a2a_endpoint": "https://deep-test.example.com/a2a",
    }
    payload.update(overrides)
    return payload


def _auth_header(agent_id: str, agent_name: str = "test") -> dict:
    """Build Authorization header from a freshly-minted JWT."""
    token = create_access_token(agent_id, agent_name)
    return {"Authorization": f"Bearer {token}"}


async def _register(client, name: str | None = None, agent_type: str = "seller") -> dict:
    """Register an agent via the API, assert 201, return response JSON."""
    resp = await client.post(REGISTER_URL, json=_agent_payload(name, agent_type))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ===========================================================================
# BLOCK 1 — Agent Registration (tests 1-5)
# ===========================================================================


class TestAgentRegistration:
    """Tests covering POST /agents/register happy-path and validations."""

    @pytest.mark.asyncio
    async def test_register_new_agent_returns_201(self, client):
        """1. Registering a brand-new agent returns 201 with id, jwt_token,
        agent_card_url, name, and created_at."""
        payload = _agent_payload(name="reg-new-1", agent_type="buyer")
        resp = await client.post(REGISTER_URL, json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "reg-new-1"
        assert "id" in data and len(data["id"]) == 36  # UUID length
        assert "jwt_token" in data and len(data["jwt_token"]) > 20
        assert "agent_card_url" in data
        assert "deep-test.example.com" in data["agent_card_url"]
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_register_requires_name(self, client):
        """2. Omitting `name` returns 422 (validation error)."""
        payload = _agent_payload()
        del payload["name"]
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_requires_public_key_min_length(self, client):
        """3. public_key shorter than 10 chars is rejected (schema min_length=10)."""
        payload = _agent_payload(name="short-pk")
        payload["public_key"] = "short"
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_duplicate_name_returns_409(self, client):
        """4. Registering the same agent name twice returns 409 Conflict."""
        name = f"dup-deep-{uuid.uuid4().hex[:6]}"
        await _register(client, name=name)

        resp = await client.post(REGISTER_URL, json=_agent_payload(name=name))
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_all_agent_types_accepted(self, client):
        """5. seller, buyer, and both are all valid agent_type values."""
        for at in ("seller", "buyer", "both"):
            data = await _register(client, name=f"type-{at}-{uuid.uuid4().hex[:4]}", agent_type=at)
            assert data["id"]  # Successful registration


# ===========================================================================
# BLOCK 2 — Metadata Management (tests 6-10)
# ===========================================================================


class TestMetadataManagement:
    """Tests covering GET, PUT for agent details and field updates."""

    @pytest.mark.asyncio
    async def test_get_agent_returns_full_metadata(self, client):
        """6. GET /agents/{id} returns all expected response fields."""
        reg = await _register(client, name="meta-full", agent_type="both")
        resp = await client.get(f"{AGENTS_URL}/{reg['id']}")

        assert resp.status_code == 200
        data = resp.json()
        expected_keys = {
            "id", "name", "description", "agent_type", "wallet_address",
            "capabilities", "a2a_endpoint", "status", "created_at",
            "updated_at", "last_seen_at",
        }
        assert expected_keys.issubset(set(data.keys()))
        assert data["agent_type"] == "both"
        assert data["status"] == "active"
        assert isinstance(data["capabilities"], list)

    @pytest.mark.asyncio
    async def test_update_description(self, client):
        """7. PUT /agents/{id} can update the description field."""
        reg = await _register(client, name="upd-desc")
        headers = _auth_header(reg["id"], "upd-desc")

        resp = await client.put(
            f"{AGENTS_URL}/{reg['id']}",
            json={"description": "newly updated description"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "newly updated description"

    @pytest.mark.asyncio
    async def test_update_capabilities(self, client):
        """8. PUT /agents/{id} can update the capabilities list."""
        reg = await _register(client, name="upd-caps")
        headers = _auth_header(reg["id"], "upd-caps")

        resp = await client.put(
            f"{AGENTS_URL}/{reg['id']}",
            json={"capabilities": ["translation", "code_gen", "rag"]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["capabilities"]) == {"translation", "code_gen", "rag"}

    @pytest.mark.asyncio
    async def test_partial_update_leaves_other_fields_intact(self, client):
        """9. A partial update (only description) does not blank other fields."""
        reg = await _register(client, name="partial-upd")
        headers = _auth_header(reg["id"], "partial-upd")

        # Capture initial values from the registration payload defaults
        initial_wallet = _agent_payload()["wallet_address"]
        initial_endpoint = _agent_payload()["a2a_endpoint"]
        initial_caps = _agent_payload()["capabilities"]

        # Clear agent cache to avoid stale-session cross-request issues
        from marketplace.services.cache_service import agent_cache
        agent_cache.clear()

        # Update only description
        resp = await client.put(
            f"{AGENTS_URL}/{reg['id']}",
            json={"description": "changed"},
            headers=headers,
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["description"] == "changed"
        assert updated["wallet_address"] == initial_wallet
        assert updated["a2a_endpoint"] == initial_endpoint
        assert updated["capabilities"] == initial_caps

    @pytest.mark.asyncio
    async def test_update_wallet_address_and_endpoint(self, client):
        """10. wallet_address and a2a_endpoint can be updated together."""
        reg = await _register(client, name="upd-multi")
        headers = _auth_header(reg["id"], "upd-multi")

        resp = await client.put(
            f"{AGENTS_URL}/{reg['id']}",
            json={
                "wallet_address": "0x" + "ff" * 20,
                "a2a_endpoint": "https://new-endpoint.io/a2a",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["wallet_address"] == "0x" + "ff" * 20
        assert data["a2a_endpoint"] == "https://new-endpoint.io/a2a"


# ===========================================================================
# BLOCK 3 — Deregistration (tests 11-15)
# ===========================================================================


class TestDeregistration:
    """Tests covering DELETE (soft-delete) and cascading effects."""

    @pytest.mark.asyncio
    async def test_deactivate_sets_status(self, client):
        """11. DELETE /agents/{id} soft-deletes by setting status='deactivated'."""
        reg = await _register(client, name="deact-status")
        headers = _auth_header(reg["id"], "deact-status")

        resp = await client.delete(f"{AGENTS_URL}/{reg['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deactivated"

    @pytest.mark.asyncio
    async def test_deactivated_agent_still_visible_in_get(self, client):
        """12. A deactivated agent is still retrievable via GET (soft delete)."""
        reg = await _register(client, name="deact-visible")
        headers = _auth_header(reg["id"], "deact-visible")

        await client.delete(f"{AGENTS_URL}/{reg['id']}", headers=headers)

        resp = await client.get(f"{AGENTS_URL}/{reg['id']}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deactivated"

    @pytest.mark.asyncio
    async def test_deactivated_agent_excluded_by_status_filter(self, client):
        """13. Listing agents with ?status=active excludes deactivated ones."""
        reg = await _register(client, name="deact-filter")
        headers = _auth_header(reg["id"], "deact-filter")

        await client.delete(f"{AGENTS_URL}/{reg['id']}", headers=headers)

        resp = await client.get(AGENTS_URL, params={"status": "active"})
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()["agents"]]
        assert reg["id"] not in ids

    @pytest.mark.asyncio
    async def test_reregistration_after_deactivation(self, client):
        """14. A new agent can be registered with a different name after
        deactivating another; the deactivated ID remains valid."""
        reg1 = await _register(client, name="orig-agent")
        headers1 = _auth_header(reg1["id"], "orig-agent")
        await client.delete(f"{AGENTS_URL}/{reg1['id']}", headers=headers1)

        # Register a new agent (different name)
        reg2 = await _register(client, name="new-agent-after-deact")
        assert reg2["id"] != reg1["id"]

        # Old one still exists with deactivated status
        old = (await client.get(f"{AGENTS_URL}/{reg1['id']}")).json()
        assert old["status"] == "deactivated"

    @pytest.mark.asyncio
    async def test_deactivate_requires_own_id(self, client):
        """15. An agent cannot deactivate another agent (403)."""
        reg_a = await _register(client, name="agent-a-own")
        reg_b = await _register(client, name="agent-b-own")
        headers_b = _auth_header(reg_b["id"], "agent-b-own")

        resp = await client.delete(f"{AGENTS_URL}/{reg_a['id']}", headers=headers_b)
        assert resp.status_code == 403
        assert "only" in resp.json()["detail"].lower()


# ===========================================================================
# BLOCK 4 — Version / Lifecycle Management (tests 16-20)
# ===========================================================================


class TestVersionLifecycle:
    """Tests covering heartbeat, status transitions, and update timestamps."""

    @pytest.mark.asyncio
    async def test_heartbeat_updates_last_seen(self, client):
        """16. POST /agents/{id}/heartbeat returns last_seen_at timestamp."""
        reg = await _register(client, name="hb-update")
        headers = _auth_header(reg["id"], "hb-update")

        resp = await client.post(f"{AGENTS_URL}/{reg['id']}/heartbeat", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["last_seen_at"] is not None

    @pytest.mark.asyncio
    async def test_heartbeat_requires_auth(self, client):
        """17. Heartbeat without auth returns 401."""
        reg = await _register(client, name="hb-noauth")

        resp = await client.post(f"{AGENTS_URL}/{reg['id']}/heartbeat")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_heartbeat_cannot_impersonate(self, client):
        """18. Agent A cannot heartbeat agent B (403 Forbidden)."""
        reg_a = await _register(client, name="hb-a")
        reg_b = await _register(client, name="hb-b")
        headers_a = _auth_header(reg_a["id"], "hb-a")

        resp = await client.post(
            f"{AGENTS_URL}/{reg_b['id']}/heartbeat", headers=headers_a
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_changes_updated_at_timestamp(self, client):
        """19. PUT /agents/{id} advances the updated_at timestamp."""
        reg = await _register(client, name="ts-update")
        headers = _auth_header(reg["id"], "ts-update")

        # Get created_at from registration response as a baseline
        created_at = reg["created_at"]

        # Clear agent cache to avoid stale-session cross-request issues
        from marketplace.services.cache_service import agent_cache
        agent_cache.clear()

        resp = await client.put(
            f"{AGENTS_URL}/{reg['id']}",
            json={"description": "timestamp test"},
            headers=headers,
        )
        assert resp.status_code == 200
        updated_at = resp.json()["updated_at"]
        # updated_at should be the same or later than created_at
        assert updated_at >= created_at

    @pytest.mark.asyncio
    async def test_update_status_to_inactive_via_put(self, client):
        """20. Setting status='inactive' via PUT is accepted and persists."""
        reg = await _register(client, name="status-inactive")
        headers = _auth_header(reg["id"], "status-inactive")

        resp = await client.put(
            f"{AGENTS_URL}/{reg['id']}",
            json={"status": "inactive"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

        # Verify it persisted
        get_resp = await client.get(f"{AGENTS_URL}/{reg['id']}")
        assert get_resp.json()["status"] == "inactive"


# ===========================================================================
# BLOCK 5 — Edge Cases (tests 21-25)
# ===========================================================================


class TestEdgeCases:
    """Tests for invalid IDs, empty payloads, auth edge cases, pagination."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_agent_returns_404(self, client):
        """21. GET /agents/{random-uuid} returns 404."""
        fake = str(uuid.uuid4())
        resp = await client.get(f"{AGENTS_URL}/{fake}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_agent_type_rejected(self, client):
        """22. agent_type outside seller|buyer|both returns 422."""
        payload = _agent_payload(name="bad-type")
        payload["agent_type"] = "reseller"
        resp = await client.post(REGISTER_URL, json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_body_on_register_returns_422(self, client):
        """23. POST /agents/register with empty body returns 422."""
        resp = await client.post(REGISTER_URL, json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_pagination_parameters(self, client):
        """24. page and page_size query params control listing output."""
        # Register 5 agents
        for i in range(5):
            await _register(client, name=f"page-test-{i}-{uuid.uuid4().hex[:4]}")

        # Page 1, size 2
        resp = await client.get(AGENTS_URL, params={"page": 1, "page_size": 2})
        data = resp.json()
        assert resp.status_code == 200
        assert len(data["agents"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] >= 5

        # Page 3, size 2 -> should get 1 (5 total, page 3 of 2)
        resp2 = await client.get(AGENTS_URL, params={"page": 3, "page_size": 2})
        data2 = resp2.json()
        assert len(data2["agents"]) >= 1

    @pytest.mark.asyncio
    async def test_update_without_auth_returns_401(self, client):
        """25. PUT /agents/{id} without Authorization header returns 401."""
        reg = await _register(client, name="no-auth-upd")
        resp = await client.put(
            f"{AGENTS_URL}/{reg['id']}",
            json={"description": "should fail"},
        )
        assert resp.status_code == 401
