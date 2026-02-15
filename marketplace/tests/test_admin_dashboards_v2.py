"""Integration tests for v2 admin and role dashboard APIs."""

from __future__ import annotations

from marketplace.config import settings
from marketplace.core.auth import decode_stream_token
from marketplace.services import dashboard_service


async def test_v2_admin_overview_requires_allowlisted_creator(
    client,
    make_creator,
    monkeypatch,
):
    admin_creator, admin_token = await make_creator()
    _, non_admin_token = await make_creator()
    monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

    forbidden = await client.get(
        "/api/v2/admin/overview",
        headers={"Authorization": f"Bearer {non_admin_token}"},
    )
    assert forbidden.status_code == 403

    allowed = await client.get(
        "/api/v2/admin/overview",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["environment"]
    assert "platform_volume_usd" in body
    assert "trust_weighted_revenue_usd" in body


async def test_v2_admin_stream_token_is_scoped_to_admin_topics(
    client,
    make_creator,
    monkeypatch,
):
    admin_creator, admin_token = await make_creator()
    monkeypatch.setattr(settings, "admin_creator_ids", admin_creator.id)

    response = await client.get(
        "/api/v2/admin/events/stream-token",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    payload = decode_stream_token(body["stream_token"])
    assert payload["sub"] == admin_creator.id
    assert payload["type"] == "stream_admin"
    assert payload["sub_type"] == "admin"
    assert set(body["allowed_topics"]) == {"public.market", "private.admin"}


async def test_v2_agent_dashboard_me_rejects_creator_token(client, make_creator):
    _, creator_token = await make_creator()
    response = await client.get(
        "/api/v2/dashboards/agent/me",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert response.status_code == 401


async def test_v2_agent_dashboard_me_accepts_agent_token(client, make_agent):
    agent, agent_token = await make_agent()

    response = await client.get(
        "/api/v2/dashboards/agent/me",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == agent.id
    assert "money_received_usd" in body
    assert "savings" in body


async def test_v2_agent_private_dashboard_enforces_owner_or_admin(
    client,
    db,
    make_agent,
    make_creator,
    monkeypatch,
):
    owner_creator, owner_token = await make_creator()
    other_creator, other_token = await make_creator()
    agent, _ = await make_agent()
    agent.creator_id = owner_creator.id
    await db.commit()

    forbidden = await client.get(
        f"/api/v2/dashboards/agent/{agent.id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 403

    owner_allowed = await client.get(
        f"/api/v2/dashboards/agent/{agent.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_allowed.status_code == 200

    monkeypatch.setattr(settings, "admin_creator_ids", other_creator.id)
    admin_allowed = await client.get(
        f"/api/v2/dashboards/agent/{agent.id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert admin_allowed.status_code == 200


async def test_v2_open_market_analytics_is_public_and_redacted(
    client,
    make_agent,
    make_listing,
    make_transaction,
):
    seller, _ = await make_agent(name="seller-agent")
    buyer, _ = await make_agent(name="buyer-agent")
    listing = await make_listing(
        seller.id,
        price_usdc=1.2,
        category="web_search",
        content_size=512,
    )
    await make_transaction(
        buyer_id=buyer.id,
        seller_id=seller.id,
        listing_id=listing.id,
        amount_usdc=1.0,
        status="completed",
    )

    response = await client.get("/api/v2/analytics/market/open")
    assert response.status_code == 200
    body = response.json()
    assert body["total_completed_transactions"] == 1
    assert body["platform_volume_usd"] >= 1.0

    revenue_row = body["top_agents_by_revenue"][0]
    assert set(revenue_row) == {"agent_id", "agent_name", "money_received_usd"}
    assert "buyer_id" not in revenue_row
    assert "transaction_id" not in revenue_row


async def test_v2_open_market_analytics_falls_back_on_internal_error(
    client,
    monkeypatch,
):
    async def _raise(*args, **kwargs):
        raise RuntimeError("forced_failure")

    monkeypatch.setattr(dashboard_service, "get_open_market_analytics", _raise)
    response = await client.get("/api/v2/analytics/market/open")
    assert response.status_code == 200
    body = response.json()
    assert body["total_completed_transactions"] == 0
    assert body["platform_volume_usd"] == 0.0
    assert body["top_agents_by_revenue"] == []

