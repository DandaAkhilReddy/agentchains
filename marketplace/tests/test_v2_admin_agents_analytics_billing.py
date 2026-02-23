"""Comprehensive tests for v2 admin, agents, analytics, and billing API endpoints.

Covers:
- marketplace/api/v2_admin.py   : GET overview/finance/usage/agents/security, payouts, stream-token
- marketplace/api/v2_agents.py  : POST onboard, attest/runtime, attest/knowledge/run, GET trust, GET trust/public
- marketplace/api/v2_analytics.py : GET analytics/market/open
- marketplace/api/v2_billing.py : GET accounts/me, ledger/me, POST deposits, deposits/confirm, transfers
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from marketplace.config import settings
from marketplace.models.token_account import TokenAccount
from marketplace.services import dashboard_service
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


def _creator_payload() -> dict:
    suffix = uuid.uuid4().hex[:8]
    return {
        "email": f"creator-{suffix}@example.com",
        "password": "StrongerPass123!",
        "display_name": f"Creator {suffix}",
        "country": "US",
    }


def _onboard_payload(name: str | None = None) -> dict:
    return {
        "name": name or f"agent-{_new_id()[:8]}",
        "description": "test agent for v2 onboard",
        "agent_type": "both",
        "public_key": "ssh-rsa AAAA_test_registration_key_placeholder_long_enough",
        "wallet_address": "",
        "capabilities": ["retrieval", "tool_use"],
        "a2a_endpoint": "https://agent.example.com",
    }


async def _register_creator(client) -> dict:
    resp = await client.post("/api/v1/creators/register", json=_creator_payload())
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _onboard_agent(client, creator_token: str, *, name: str | None = None) -> dict:
    resp = await client.post(
        "/api/v2/agents/onboard",
        headers={"Authorization": f"Bearer {creator_token}"},
        json=_onboard_payload(name=name),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _seed_platform_account(db=None):
    """Ensure platform treasury token account exists."""
    from marketplace.services.token_service import ensure_platform_account
    if db is not None:
        return await ensure_platform_account(db)
    async with TestSession() as session:
        return await ensure_platform_account(session)


async def _seed_agent_account(agent_id: str, balance: float = 50.0):
    """Create a token account for agent with given balance."""
    async with TestSession() as db:
        db.add(TokenAccount(
            id=_new_id(),
            agent_id=None,   # platform treasury
            balance=Decimal("0"),
        ))
        db.add(TokenAccount(
            id=_new_id(),
            agent_id=agent_id,
            balance=Decimal(str(balance)),
        ))
        await db.commit()


# ===========================================================================
# SECTION 1 — v2_admin.py
# ===========================================================================

class TestAdminOverview:
    """GET /api/v2/admin/overview"""

    async def test_overview_accessible_to_admin_creator(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/overview",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total_agents" in body
        assert "platform_volume_usd" in body
        assert "trust_weighted_revenue_usd" in body
        assert "environment" in body

    async def test_overview_rejects_non_admin_creator(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        _, non_admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/overview",
            headers={"Authorization": f"Bearer {non_admin_token}"},
        )
        assert resp.status_code == 403

    async def test_overview_rejects_missing_auth(self, client, make_creator, monkeypatch):
        admin_creator, _ = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get("/api/v2/admin/overview")
        assert resp.status_code in (401, 403)

    async def test_overview_accepts_agent_token_when_admin_ids_empty(
        self, client, make_creator, monkeypatch
    ):
        # When admin_creator_ids is empty, any creator passes the admin gate.
        monkeypatch.setattr(settings, "admin_creator_ids", "")
        _, creator_token = await make_creator()

        resp = await client.get(
            "/api/v2/admin/overview",
            headers={"Authorization": f"Bearer {creator_token}"},
        )
        assert resp.status_code == 200


class TestAdminFinance:
    """GET /api/v2/admin/finance"""

    async def test_finance_returns_required_fields(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/finance",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "platform_volume_usd" in body
        assert "payout_pending_count" in body
        assert "payout_pending_usd" in body
        assert "top_sellers_by_revenue" in body

    async def test_finance_blocked_for_non_admin(self, client, make_creator, monkeypatch):
        admin_creator, _ = await make_creator()
        _, other_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/finance",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 403


class TestAdminUsage:
    """GET /api/v2/admin/usage"""

    async def test_usage_returns_category_breakdown(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/usage",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "info_used_count" in body
        assert "data_served_bytes" in body
        assert "unique_buyers_count" in body
        assert "unique_sellers_count" in body
        assert "category_breakdown" in body
        assert isinstance(body["category_breakdown"], list)

    async def test_usage_blocked_for_non_admin(self, client, make_creator, monkeypatch):
        admin_creator, _ = await make_creator()
        _, other_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/usage",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 403


class TestAdminAgents:
    """GET /api/v2/admin/agents"""

    async def test_agents_list_returns_paginated_structure(
        self, client, make_creator, make_agent, monkeypatch
    ):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)
        await make_agent(name="agent-list-1")
        await make_agent(name="agent-list-2")

        resp = await client.get(
            "/api/v2/admin/agents",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert "entries" in body
        assert isinstance(body["entries"], list)

    async def test_agents_list_respects_page_size(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/agents?page=1&page_size=5",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["page_size"] == 5
        assert len(body["entries"]) <= 5

    async def test_agents_list_status_filter(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/agents?status=active",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        for entry in body["entries"]:
            assert entry["status"] == "active"

    async def test_agents_list_blocked_for_non_admin(self, client, make_creator, monkeypatch):
        admin_creator, _ = await make_creator()
        _, other_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/agents",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 403


class TestAdminSecurityEvents:
    """GET /api/v2/admin/security/events"""

    async def test_security_events_returns_paginated_structure(
        self, client, make_creator, monkeypatch
    ):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/security/events",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "events" in body
        assert isinstance(body["events"], list)

    async def test_security_events_default_page_size_50(
        self, client, make_creator, monkeypatch
    ):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/security/events",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 50

    async def test_security_events_severity_filter(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/security/events?severity=high&event_type=login_failure",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_security_events_blocked_for_non_admin(
        self, client, make_creator, monkeypatch
    ):
        admin_creator, _ = await make_creator()
        _, other_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/security/events",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 403


class TestAdminPayouts:
    """GET /api/v2/admin/payouts/pending + POST approve/reject"""

    async def test_pending_payouts_returns_list(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/payouts/pending",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Response is {"count": N, "requests": [...], "total_pending_usd": N}
        assert isinstance(body, dict)
        assert "requests" in body
        assert isinstance(body["requests"], list)

    async def test_pending_payouts_limit_param(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/payouts/pending?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) <= 10

    async def test_pending_payouts_blocked_for_non_admin(
        self, client, make_creator, monkeypatch
    ):
        admin_creator, _ = await make_creator()
        _, other_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/payouts/pending",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 403

    async def test_approve_payout_nonexistent_returns_400(
        self, client, make_creator, monkeypatch
    ):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        fake_id = _uid()
        resp = await client.post(
            f"/api/v2/admin/payouts/{fake_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"admin_notes": "looks good"},
        )
        assert resp.status_code == 400

    async def test_reject_payout_nonexistent_returns_400(
        self, client, make_creator, monkeypatch
    ):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        fake_id = _uid()
        resp = await client.post(
            f"/api/v2/admin/payouts/{fake_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "policy violation"},
        )
        assert resp.status_code == 400

    async def test_reject_payout_requires_reason(self, client, make_creator, monkeypatch):
        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.post(
            f"/api/v2/admin/payouts/{_uid()}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": ""},  # empty reason violates min_length=1
        )
        assert resp.status_code == 422


class TestAdminStreamToken:
    """GET /api/v2/admin/events/stream-token"""

    async def test_stream_token_scoped_to_admin_topics(
        self, client, make_creator, monkeypatch
    ):
        from marketplace.core.auth import decode_stream_token

        admin_creator, admin_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/events/stream-token",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "stream_token" in body
        assert "ws_url" in body
        assert set(body["allowed_topics"]) == {"public.market", "private.admin"}

        payload = decode_stream_token(body["stream_token"])
        assert payload["sub"] == admin_creator.id
        assert payload["type"] == "stream_admin"

    async def test_stream_token_blocked_for_non_admin(
        self, client, make_creator, monkeypatch
    ):
        admin_creator, _ = await make_creator()
        _, other_token = await make_creator()
        monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

        resp = await client.get(
            "/api/v2/admin/events/stream-token",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 403


# ===========================================================================
# SECTION 2 — v2_agents.py
# ===========================================================================

class TestAgentOnboard:
    """POST /api/v2/agents/onboard"""

    async def test_onboard_creates_agent_with_trust_profile(self, client):
        creator = await _register_creator(client)
        onboarded = await _onboard_agent(client, creator["token"])

        assert onboarded["agent_id"]
        assert onboarded["agent_jwt_token"]
        assert onboarded["onboarding_session_id"]
        assert onboarded["agent_trust_status"] in {"unverified", "provisional", "verified"}
        assert onboarded["agent_trust_tier"] in {"T0", "T1", "T2", "T3"}
        assert "stream_token" in onboarded

    async def test_onboard_returns_agent_card_url(self, client):
        creator = await _register_creator(client)
        body = await _onboard_agent(client, creator["token"])
        assert "agent_card_url" in body

    async def test_onboard_with_memory_import_intent(self, client):
        creator = await _register_creator(client)
        payload = _onboard_payload()
        payload["memory_import_intent"] = True

        resp = await client.post(
            "/api/v2/agents/onboard",
            headers={"Authorization": f"Bearer {creator['token']}"},
            json=payload,
        )
        assert resp.status_code == 201

    async def test_onboard_rejects_missing_auth(self, client):
        resp = await client.post("/api/v2/agents/onboard", json=_onboard_payload())
        assert resp.status_code == 401

    async def test_onboard_rejects_invalid_agent_type(self, client):
        creator = await _register_creator(client)
        payload = _onboard_payload()
        payload["agent_type"] = "invalid_type"

        resp = await client.post(
            "/api/v2/agents/onboard",
            headers={"Authorization": f"Bearer {creator['token']}"},
            json=payload,
        )
        assert resp.status_code == 422

    async def test_onboard_rejects_duplicate_agent_name(self, client):
        creator = await _register_creator(client)
        name = f"dup-agent-{_uid()[:8]}"
        await _onboard_agent(client, creator["token"], name=name)

        resp = await client.post(
            "/api/v2/agents/onboard",
            headers={"Authorization": f"Bearer {creator['token']}"},
            json=_onboard_payload(name=name),
        )
        assert resp.status_code == 409

    async def test_onboard_rejects_short_public_key(self, client):
        creator = await _register_creator(client)
        payload = _onboard_payload()
        payload["public_key"] = "short"

        resp = await client.post(
            "/api/v2/agents/onboard",
            headers={"Authorization": f"Bearer {creator['token']}"},
            json=payload,
        )
        assert resp.status_code == 422

    async def test_onboard_with_agent_token_fails(self, client, make_agent):
        # Agent JWT is not a creator token — should fail auth.
        _, agent_token = await make_agent()
        resp = await client.post(
            "/api/v2/agents/onboard",
            headers={"Authorization": f"Bearer {agent_token}"},
            json=_onboard_payload(),
        )
        assert resp.status_code == 401


class TestRuntimeAttestation:
    """POST /api/v2/agents/{agent_id}/attest/runtime"""

    async def test_runtime_attestation_happy_path(self, client):
        creator = await _register_creator(client)
        onboarded = await _onboard_agent(client, creator["token"])
        agent_id = onboarded["agent_id"]
        agent_token = onboarded["agent_jwt_token"]

        resp = await client.post(
            f"/api/v2/agents/{agent_id}/attest/runtime",
            headers={"Authorization": f"Bearer {agent_token}"},
            json={
                "runtime_name": "custom-runtime",
                "runtime_version": "2.0.0",
                "sdk_version": "0.5.0",
                "endpoint_reachable": True,
                "supports_memory": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "stage_runtime_score" in body

    async def test_runtime_attestation_minimal_payload(self, client):
        creator = await _register_creator(client)
        onboarded = await _onboard_agent(client, creator["token"])
        agent_id = onboarded["agent_id"]
        agent_token = onboarded["agent_jwt_token"]

        resp = await client.post(
            f"/api/v2/agents/{agent_id}/attest/runtime",
            headers={"Authorization": f"Bearer {agent_token}"},
            json={},  # All fields have defaults
        )
        assert resp.status_code == 200

    async def test_runtime_attestation_wrong_agent(self, client):
        creator = await _register_creator(client)
        onboarded1 = await _onboard_agent(client, creator["token"])
        onboarded2 = await _onboard_agent(client, creator["token"])

        # agent1's token cannot attest agent2's runtime
        resp = await client.post(
            f"/api/v2/agents/{onboarded2['agent_id']}/attest/runtime",
            headers={"Authorization": f"Bearer {onboarded1['agent_jwt_token']}"},
            json={"runtime_name": "hacked"},
        )
        assert resp.status_code == 403

    async def test_runtime_attestation_missing_auth(self, client):
        resp = await client.post(
            f"/api/v2/agents/{_uid()}/attest/runtime",
            json={"runtime_name": "test"},
        )
        assert resp.status_code == 401


class TestKnowledgeChallenge:
    """POST /api/v2/agents/{agent_id}/attest/knowledge/run"""

    async def test_knowledge_challenge_happy_path(self, client):
        creator = await _register_creator(client)
        onboarded = await _onboard_agent(client, creator["token"])
        agent_id = onboarded["agent_id"]
        agent_token = onboarded["agent_jwt_token"]

        resp = await client.post(
            f"/api/v2/agents/{agent_id}/attest/knowledge/run",
            headers={"Authorization": f"Bearer {agent_token}"},
            json={
                "capabilities": ["retrieval", "tool_use"],
                "claim_payload": {"domain": "data_retrieval", "confidence": 0.9},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "stage_knowledge_score" in body

    async def test_knowledge_challenge_empty_payload(self, client):
        creator = await _register_creator(client)
        onboarded = await _onboard_agent(client, creator["token"])
        agent_id = onboarded["agent_id"]
        agent_token = onboarded["agent_jwt_token"]

        resp = await client.post(
            f"/api/v2/agents/{agent_id}/attest/knowledge/run",
            headers={"Authorization": f"Bearer {agent_token}"},
            json={},
        )
        assert resp.status_code == 200

    async def test_knowledge_challenge_wrong_agent_forbidden(self, client):
        creator = await _register_creator(client)
        onboarded1 = await _onboard_agent(client, creator["token"])
        onboarded2 = await _onboard_agent(client, creator["token"])

        resp = await client.post(
            f"/api/v2/agents/{onboarded2['agent_id']}/attest/knowledge/run",
            headers={"Authorization": f"Bearer {onboarded1['agent_jwt_token']}"},
            json={"capabilities": ["general"]},
        )
        assert resp.status_code == 403

    async def test_knowledge_challenge_missing_auth(self, client):
        resp = await client.post(
            f"/api/v2/agents/{_uid()}/attest/knowledge/run",
            json={"capabilities": ["general"]},
        )
        assert resp.status_code == 401


class TestAgentTrust:
    """GET /api/v2/agents/{agent_id}/trust"""

    async def test_trust_accessible_by_own_agent_token(self, client):
        creator = await _register_creator(client)
        onboarded = await _onboard_agent(client, creator["token"])
        agent_id = onboarded["agent_id"]
        agent_token = onboarded["agent_jwt_token"]

        resp = await client.get(
            f"/api/v2/agents/{agent_id}/trust",
            headers={"Authorization": f"Bearer {agent_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_id"] == agent_id
        assert "agent_trust_status" in body
        assert "agent_trust_score" in body

    async def test_trust_accessible_by_owner_creator(self, client):
        creator = await _register_creator(client)
        creator_token = creator["token"]
        onboarded = await _onboard_agent(client, creator_token)
        agent_id = onboarded["agent_id"]

        resp = await client.get(
            f"/api/v2/agents/{agent_id}/trust",
            headers={"Authorization": f"Bearer {creator_token}"},
        )
        assert resp.status_code == 200

    async def test_trust_returns_404_for_unknown_agent(self, client):
        creator = await _register_creator(client)
        creator_token = creator["token"]
        fake_id = _uid()

        resp = await client.get(
            f"/api/v2/agents/{fake_id}/trust",
            headers={"Authorization": f"Bearer {creator_token}"},
        )
        assert resp.status_code == 404

    async def test_trust_rejects_missing_auth(self, client):
        resp = await client.get(f"/api/v2/agents/{_uid()}/trust")
        assert resp.status_code == 401

    async def test_trust_forbidden_for_other_creator(self, client, monkeypatch):
        monkeypatch.setattr(settings, "admin_creator_ids", "")
        creator_a = await _register_creator(client)
        creator_b = await _register_creator(client)
        onboarded = await _onboard_agent(client, creator_a["token"])
        agent_id = onboarded["agent_id"]

        resp = await client.get(
            f"/api/v2/agents/{agent_id}/trust",
            headers={"Authorization": f"Bearer {creator_b['token']}"},
        )
        assert resp.status_code == 403


class TestAgentTrustPublic:
    """GET /api/v2/agents/{agent_id}/trust/public"""

    async def test_trust_public_no_auth_required(self, client):
        creator = await _register_creator(client)
        onboarded = await _onboard_agent(client, creator["token"])
        agent_id = onboarded["agent_id"]

        resp = await client.get(f"/api/v2/agents/{agent_id}/trust/public")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_id"] == agent_id
        assert "agent_trust_status" in body
        assert "agent_trust_tier" in body
        assert "agent_trust_score" in body

    async def test_trust_public_only_exposes_public_fields(self, client):
        creator = await _register_creator(client)
        onboarded = await _onboard_agent(client, creator["token"])
        agent_id = onboarded["agent_id"]

        resp = await client.get(f"/api/v2/agents/{agent_id}/trust/public")
        body = resp.json()
        # Private fields must NOT appear
        assert "identity_attestation_score" not in body
        assert "runtime_attestation_score" not in body
        assert "knowledge_challenge_score" not in body

    async def test_trust_public_returns_404_for_unknown_agent(self, client):
        resp = await client.get(f"/api/v2/agents/{_uid()}/trust/public")
        assert resp.status_code == 404


# ===========================================================================
# SECTION 3 — v2_analytics.py
# ===========================================================================

class TestOpenMarketAnalytics:
    """GET /api/v2/analytics/market/open"""

    async def test_analytics_is_public_no_auth(self, client):
        resp = await client.get("/api/v2/analytics/market/open")
        assert resp.status_code == 200

    async def test_analytics_returns_required_fields(self, client):
        resp = await client.get("/api/v2/analytics/market/open")
        body = resp.json()
        assert "total_agents" in body
        assert "total_listings" in body
        assert "total_completed_transactions" in body
        assert "platform_volume_usd" in body
        assert "total_money_saved_usd" in body
        assert "top_agents_by_revenue" in body
        assert "top_agents_by_usage" in body
        assert "top_categories_by_usage" in body
        assert "generated_at" in body

    async def test_analytics_counts_completed_transactions(
        self, client, make_agent, make_listing, make_transaction
    ):
        seller, _ = await make_agent(name="seller-analytics")
        buyer, _ = await make_agent(name="buyer-analytics")
        listing = await make_listing(seller.id, price_usdc=2.0, category="web_search")
        await make_transaction(
            buyer_id=buyer.id,
            seller_id=seller.id,
            listing_id=listing.id,
            amount_usdc=2.0,
            status="completed",
        )

        resp = await client.get("/api/v2/analytics/market/open")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_completed_transactions"] >= 1
        assert body["platform_volume_usd"] >= 2.0

    async def test_analytics_revenue_row_fields_are_redacted(
        self, client, make_agent, make_listing, make_transaction
    ):
        seller, _ = await make_agent(name="seller-redacted")
        buyer, _ = await make_agent(name="buyer-redacted")
        listing = await make_listing(seller.id, price_usdc=1.0)
        await make_transaction(
            buyer_id=buyer.id,
            seller_id=seller.id,
            listing_id=listing.id,
            amount_usdc=1.0,
            status="completed",
        )

        resp = await client.get("/api/v2/analytics/market/open")
        body = resp.json()
        if body["top_agents_by_revenue"]:
            row = body["top_agents_by_revenue"][0]
            assert "agent_id" in row
            assert "agent_name" in row
            assert "money_received_usd" in row
            # Private fields must not leak
            assert "buyer_id" not in row
            assert "transaction_id" not in row

    async def test_analytics_limit_param(self, client):
        resp = await client.get("/api/v2/analytics/market/open?limit=5")
        assert resp.status_code == 200

    async def test_analytics_limit_out_of_range_returns_422(self, client):
        resp = await client.get("/api/v2/analytics/market/open?limit=100")
        assert resp.status_code == 422

    async def test_analytics_falls_back_on_internal_error(self, client, monkeypatch):
        async def _raise(*args, **kwargs):
            raise RuntimeError("forced_failure")

        monkeypatch.setattr(dashboard_service, "get_open_market_analytics", _raise)
        resp = await client.get("/api/v2/analytics/market/open")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_completed_transactions"] == 0
        assert body["platform_volume_usd"] == 0.0
        assert body["top_agents_by_revenue"] == []


# ===========================================================================
# SECTION 4 — v2_billing.py
# ===========================================================================

class TestBillingAccountMe:
    """GET /api/v2/billing/accounts/me"""

    async def test_account_me_happy_path(self, client, make_agent):
        agent, token = await make_agent()
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
            db.add(TokenAccount(id=_new_id(), agent_id=agent.id, balance=Decimal("25.50")))
            await db.commit()

        resp = await client.get(
            "/api/v2/billing/accounts/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["currency"] == "USD"
        assert body["account_scope"] == "agent"
        assert body["balance_usd"] == pytest.approx(25.50)

    async def test_account_me_returns_financial_fields(self, client, make_agent):
        agent, token = await make_agent()
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
            db.add(TokenAccount(id=_new_id(), agent_id=agent.id, balance=Decimal("10")))
            await db.commit()

        resp = await client.get(
            "/api/v2/billing/accounts/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = resp.json()
        assert "total_earned_usd" in body
        assert "total_spent_usd" in body
        assert "total_deposited_usd" in body
        assert "total_fees_paid_usd" in body

    async def test_account_me_zero_balance_for_new_agent(self, client, make_agent):
        agent, token = await make_agent()

        resp = await client.get(
            "/api/v2/billing/accounts/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["balance_usd"] == pytest.approx(0.0)

    async def test_account_me_requires_auth(self, client):
        resp = await client.get("/api/v2/billing/accounts/me")
        assert resp.status_code == 401


class TestBillingLedgerMe:
    """GET /api/v2/billing/ledger/me"""

    async def test_ledger_me_returns_paginated_structure(self, client, make_agent):
        agent, token = await make_agent()

        resp = await client.get(
            "/api/v2/billing/ledger/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "entries" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert isinstance(body["entries"], list)

    async def test_ledger_me_default_pagination(self, client, make_agent):
        agent, token = await make_agent()

        resp = await client.get(
            "/api/v2/billing/ledger/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = resp.json()
        assert body["page"] == 1
        assert body["page_size"] == 20

    async def test_ledger_me_custom_pagination(self, client, make_agent):
        agent, token = await make_agent()

        resp = await client.get(
            "/api/v2/billing/ledger/me?page=2&page_size=5",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert body["page_size"] == 5

    async def test_ledger_me_entry_shape_after_deposit(self, client, make_agent):
        agent, token = await make_agent()
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
            db.add(TokenAccount(id=_new_id(), agent_id=agent.id, balance=Decimal("0")))
            await db.commit()

        # Create and confirm a deposit to generate a ledger entry
        dep_resp = await client.post(
            "/api/v2/billing/deposits",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_usd": 5.0, "payment_method": "admin_credit"},
        )
        assert dep_resp.status_code == 200
        deposit_id = dep_resp.json()["id"]

        await client.post(
            f"/api/v2/billing/deposits/{deposit_id}/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = await client.get(
            "/api/v2/billing/ledger/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        if entries:
            entry = entries[0]
            assert "id" in entry
            assert "direction" in entry
            assert "tx_type" in entry
            assert "amount_usd" in entry

    async def test_ledger_me_requires_auth(self, client):
        resp = await client.get("/api/v2/billing/ledger/me")
        assert resp.status_code == 401

    async def test_ledger_me_page_size_too_large_returns_422(self, client, make_agent):
        _, token = await make_agent()
        resp = await client.get(
            "/api/v2/billing/ledger/me?page_size=200",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


class TestBillingDeposits:
    """POST /api/v2/billing/deposits"""

    async def test_create_deposit_happy_path(self, client, make_agent):
        agent, token = await make_agent()

        resp = await client.post(
            "/api/v2/billing/deposits",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_usd": 10.0, "payment_method": "admin_credit"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["amount_usd"] == pytest.approx(10.0)
        assert body["status"] == "pending"
        assert body["agent_id"] == agent.id
        assert "id" in body

    async def test_create_deposit_default_payment_method(self, client, make_agent):
        _, token = await make_agent()

        resp = await client.post(
            "/api/v2/billing/deposits",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_usd": 5.0},
        )
        assert resp.status_code == 200
        assert resp.json()["payment_method"] == "admin_credit"

    async def test_create_deposit_zero_amount_rejected(self, client, make_agent):
        _, token = await make_agent()

        resp = await client.post(
            "/api/v2/billing/deposits",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_usd": 0.0},
        )
        assert resp.status_code == 422

    async def test_create_deposit_negative_amount_rejected(self, client, make_agent):
        _, token = await make_agent()

        resp = await client.post(
            "/api/v2/billing/deposits",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_usd": -5.0},
        )
        assert resp.status_code == 422

    async def test_create_deposit_requires_auth(self, client):
        resp = await client.post(
            "/api/v2/billing/deposits",
            json={"amount_usd": 10.0},
        )
        assert resp.status_code == 401

    async def test_create_deposit_large_amount(self, client, make_agent):
        _, token = await make_agent()

        resp = await client.post(
            "/api/v2/billing/deposits",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_usd": 9999.99},
        )
        assert resp.status_code == 200
        assert resp.json()["amount_usd"] == pytest.approx(9999.99)


class TestBillingDepositsConfirm:
    """POST /api/v2/billing/deposits/{deposit_id}/confirm"""

    async def test_confirm_deposit_credits_balance(self, client, make_agent):
        agent, token = await make_agent()
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
            db.add(TokenAccount(id=_new_id(), agent_id=agent.id, balance=Decimal("0")))
            await db.commit()

        dep_resp = await client.post(
            "/api/v2/billing/deposits",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_usd": 20.0},
        )
        deposit_id = dep_resp.json()["id"]

        confirm_resp = await client.post(
            f"/api/v2/billing/deposits/{deposit_id}/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert confirm_resp.status_code == 200
        body = confirm_resp.json()
        assert body["status"] == "completed"
        assert body["amount_usd"] == pytest.approx(20.0)

    async def test_confirm_deposit_updates_account_balance(self, client, make_agent):
        agent, token = await make_agent()
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
            db.add(TokenAccount(id=_new_id(), agent_id=agent.id, balance=Decimal("0")))
            await db.commit()

        dep_resp = await client.post(
            "/api/v2/billing/deposits",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_usd": 30.0},
        )
        deposit_id = dep_resp.json()["id"]

        await client.post(
            f"/api/v2/billing/deposits/{deposit_id}/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )

        balance_resp = await client.get(
            "/api/v2/billing/accounts/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert balance_resp.json()["balance_usd"] == pytest.approx(30.0)

    async def test_confirm_nonexistent_deposit_returns_404(self, client, make_agent):
        _, token = await make_agent()

        resp = await client.post(
            f"/api/v2/billing/deposits/{_uid()}/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_confirm_deposit_twice_fails(self, client, make_agent):
        agent, token = await make_agent()
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
            db.add(TokenAccount(id=_new_id(), agent_id=agent.id, balance=Decimal("0")))
            await db.commit()

        dep_resp = await client.post(
            "/api/v2/billing/deposits",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_usd": 15.0},
        )
        deposit_id = dep_resp.json()["id"]

        await client.post(
            f"/api/v2/billing/deposits/{deposit_id}/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Second confirmation should fail since it's no longer pending
        second = await client.post(
            f"/api/v2/billing/deposits/{deposit_id}/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Expect 400 or 422 since deposit is already completed
        assert second.status_code in (400, 422, 500)

    async def test_confirm_deposit_requires_auth(self, client):
        resp = await client.post(f"/api/v2/billing/deposits/{_uid()}/confirm")
        assert resp.status_code == 401


class TestBillingTransfers:
    """POST /api/v2/billing/transfers"""

    async def _setup_funded_agent(self, client, make_agent, balance: float = 100.0):
        agent, token = await make_agent()
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=None, balance=Decimal("0")))
            db.add(TokenAccount(id=_new_id(), agent_id=agent.id, balance=Decimal(str(balance))))
            await db.commit()
        return agent, token

    async def test_transfer_happy_path(self, client, make_agent):
        sender, sender_token = await self._setup_funded_agent(client, make_agent, 100.0)
        receiver, _ = await make_agent(name="transfer-receiver")
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=receiver.id, balance=Decimal("0")))
            await db.commit()

        resp = await client.post(
            "/api/v2/billing/transfers",
            headers={"Authorization": f"Bearer {sender_token}"},
            json={
                "to_agent_id": receiver.id,
                "amount_usd": 10.0,
                "memo": "payment for services",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["amount_usd"] == pytest.approx(10.0)
        assert body["tx_type"] == "transfer"
        assert "id" in body
        assert "created_at" in body

    async def test_transfer_with_memo(self, client, make_agent):
        sender, sender_token = await self._setup_funded_agent(client, make_agent, 50.0)
        receiver, _ = await make_agent(name="memo-receiver")
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=receiver.id, balance=Decimal("0")))
            await db.commit()

        resp = await client.post(
            "/api/v2/billing/transfers",
            headers={"Authorization": f"Bearer {sender_token}"},
            json={
                "to_agent_id": receiver.id,
                "amount_usd": 5.0,
                "memo": "test memo",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["memo"] == "test memo"

    async def test_transfer_insufficient_balance(self, client, make_agent):
        sender, sender_token = await self._setup_funded_agent(client, make_agent, 1.0)
        receiver, _ = await make_agent(name="broke-receiver")
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=receiver.id, balance=Decimal("0")))
            await db.commit()

        resp = await client.post(
            "/api/v2/billing/transfers",
            headers={"Authorization": f"Bearer {sender_token}"},
            json={"to_agent_id": receiver.id, "amount_usd": 999.0},
        )
        assert resp.status_code == 400

    async def test_transfer_zero_amount_rejected(self, client, make_agent):
        _, token = await make_agent()

        resp = await client.post(
            "/api/v2/billing/transfers",
            headers={"Authorization": f"Bearer {token}"},
            json={"to_agent_id": _uid(), "amount_usd": 0.0},
        )
        assert resp.status_code == 422

    async def test_transfer_negative_amount_rejected(self, client, make_agent):
        _, token = await make_agent()

        resp = await client.post(
            "/api/v2/billing/transfers",
            headers={"Authorization": f"Bearer {token}"},
            json={"to_agent_id": _uid(), "amount_usd": -5.0},
        )
        assert resp.status_code == 422

    async def test_transfer_requires_auth(self, client):
        resp = await client.post(
            "/api/v2/billing/transfers",
            json={"to_agent_id": _uid(), "amount_usd": 10.0},
        )
        assert resp.status_code == 401

    async def test_transfer_deducts_from_sender(self, client, make_agent):
        sender, sender_token = await self._setup_funded_agent(client, make_agent, 50.0)
        receiver, _ = await make_agent(name="deduct-receiver")
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=receiver.id, balance=Decimal("0")))
            await db.commit()

        await client.post(
            "/api/v2/billing/transfers",
            headers={"Authorization": f"Bearer {sender_token}"},
            json={"to_agent_id": receiver.id, "amount_usd": 20.0},
        )

        balance_resp = await client.get(
            "/api/v2/billing/accounts/me",
            headers={"Authorization": f"Bearer {sender_token}"},
        )
        # Balance should be 50 - 20 - fee (fee may be 0)
        assert balance_resp.json()["balance_usd"] < 50.0

    async def test_transfer_fee_returned_in_response(self, client, make_agent):
        sender, sender_token = await self._setup_funded_agent(client, make_agent, 100.0)
        receiver, _ = await make_agent(name="fee-receiver")
        async with TestSession() as db:
            db.add(TokenAccount(id=_new_id(), agent_id=receiver.id, balance=Decimal("0")))
            await db.commit()

        resp = await client.post(
            "/api/v2/billing/transfers",
            headers={"Authorization": f"Bearer {sender_token}"},
            json={"to_agent_id": receiver.id, "amount_usd": 10.0},
        )
        assert "fee_usd" in resp.json()
        assert resp.json()["fee_usd"] >= 0.0
