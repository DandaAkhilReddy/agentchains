"""Integration tests for dual-layer developer and buyer APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from marketplace.core.auth import decode_stream_token
from marketplace.models.dual_layer import ConsumerOrder, EndUser, PlatformFee
from marketplace.models.token_account import TokenAccount


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register_user(client, email: str = "buyer@test.com", password: str = "testpass123"):
    return await client.post(
        "/api/v2/users/register",
        json={"email": email, "password": password},
    )


async def test_v2_users_register_login_me_and_stream_token(client, db):
    register = await _register_user(client, email="buyer-one@test.com")
    assert register.status_code == 201
    body = register.json()
    assert body["user"]["email"] == "buyer-one@test.com"
    assert body["user"]["managed_agent_id"]
    token = body["token"]

    me = await client.get("/api/v2/users/me", headers=_auth(token))
    assert me.status_code == 200
    me_body = me.json()
    assert me_body["id"] == body["user"]["id"]

    login = await client.post(
        "/api/v2/users/login",
        json={"email": "buyer-one@test.com", "password": "testpass123"},
    )
    assert login.status_code == 200
    login_token = login.json()["token"]

    stream = await client.get("/api/v2/users/events/stream-token", headers=_auth(login_token))
    assert stream.status_code == 200
    stream_body = stream.json()
    payload = decode_stream_token(stream_body["stream_token"])
    assert payload["type"] == "stream_user"
    assert payload["sub_type"] == "user"
    assert "private.user" in stream_body["allowed_topics"]

    user_row = await db.execute(select(EndUser).where(EndUser.id == body["user"]["id"]))
    user = user_row.scalar_one()
    account_row = await db.execute(
        select(TokenAccount).where(TokenAccount.agent_id == user.managed_agent_id)
    )
    assert account_row.scalar_one_or_none() is not None


async def test_v2_builder_and_developer_profile_publish_flow(
    client,
    make_creator,
):
    creator, creator_token = await make_creator(email="builder@test.com")

    update_profile = await client.put(
        "/api/v2/creators/me/developer-profile",
        headers=_auth(creator_token),
        json={
            "bio": "I build reusable agent products.",
            "links": ["https://example.com"],
            "specialties": ["web_search", "analytics"],
            "featured_flag": True,
        },
    )
    assert update_profile.status_code == 200
    profile = update_profile.json()
    assert profile["creator_id"] == creator.id
    assert profile["featured_flag"] is True

    templates = await client.get("/api/v2/builder/templates")
    assert templates.status_code == 200
    template_key = templates.json()[0]["key"]

    create_project = await client.post(
        "/api/v2/builder/projects",
        headers=_auth(creator_token),
        json={
            "template_key": template_key,
            "title": "Reusable Web Intelligence Pack",
            "config": {
                "summary": "Precomputed research for recurring prompts",
                "price_usd": 0.33,
                "category": "web_search",
            },
        },
    )
    assert create_project.status_code == 201
    project_id = create_project.json()["id"]

    list_projects = await client.get(
        "/api/v2/builder/projects",
        headers=_auth(creator_token),
    )
    assert list_projects.status_code == 200
    assert list_projects.json()["total"] == 1

    publish = await client.post(
        f"/api/v2/builder/projects/{project_id}/publish",
        headers=_auth(creator_token),
    )
    assert publish.status_code == 200
    publish_body = publish.json()
    assert publish_body["listing_id"]
    assert publish_body["project"]["status"] == "published"

    public_listings = await client.get("/api/v2/market/listings")
    assert public_listings.status_code == 200
    listed_ids = {item["id"] for item in public_listings.json()["results"]}
    assert publish_body["listing_id"] in listed_ids


async def test_v2_builder_publish_rejects_placeholder_only_content(client, make_creator):
    _, creator_token = await make_creator(email="builder-nodata@test.com")

    templates = await client.get("/api/v2/builder/templates")
    assert templates.status_code == 200
    template_key = templates.json()[0]["key"]

    create_project = await client.post(
        "/api/v2/builder/projects",
        headers=_auth(creator_token),
        json={
            "template_key": template_key,
            "title": "No Content Project",
            "config": {
                "price_usd": 0.25,
                "category": "web_search",
            },
        },
    )
    assert create_project.status_code == 201
    project_id = create_project.json()["id"]

    publish = await client.post(
        f"/api/v2/builder/projects/{project_id}/publish",
        headers=_auth(creator_token),
    )
    assert publish.status_code == 400
    assert "placeholder data is not allowed" in publish.json()["detail"]


async def test_v2_market_listing_verified_first_order_and_fee_records(
    client,
    db,
    make_agent,
    make_listing,
):
    seller, _ = await make_agent(name="seller-dual-layer", agent_type="seller")
    verified_listing = await make_listing(seller.id, price_usdc=1.5, title="Verified Listing")
    pending_listing = await make_listing(seller.id, price_usdc=1.2, title="Pending Listing")

    # Make pending listing newer to ensure trust ranking is applied before freshness.
    verified_listing.trust_status = "verified_secure_data"
    pending_listing.trust_status = "pending_verification"
    verified_listing.freshness_at = datetime.now(timezone.utc) - timedelta(hours=2)
    pending_listing.freshness_at = datetime.now(timezone.utc)
    await db.commit()

    listings = await client.get("/api/v2/market/listings")
    assert listings.status_code == 200
    rows = listings.json()["results"]
    assert rows[0]["id"] == verified_listing.id
    assert rows[0]["trust_status"] == "verified_secure_data"
    assert rows[1]["id"] == pending_listing.id

    register = await _register_user(client, email="buyer-two@test.com")
    user_token = register.json()["token"]

    blocked = await client.post(
        "/api/v2/market/orders",
        headers=_auth(user_token),
        json={
            "listing_id": pending_listing.id,
            "payment_method": "simulated",
            "allow_unverified": False,
        },
    )
    assert blocked.status_code == 409

    allowed = await client.post(
        "/api/v2/market/orders",
        headers=_auth(user_token),
        json={
            "listing_id": pending_listing.id,
            "payment_method": "simulated",
            "allow_unverified": True,
        },
    )
    assert allowed.status_code == 201
    order = allowed.json()
    assert order["warning_acknowledged"] is True
    assert abs(order["fee_usd"] - (order["amount_usd"] * 0.10)) < 1e-6

    me_orders = await client.get("/api/v2/market/orders/me", headers=_auth(user_token))
    assert me_orders.status_code == 200
    assert me_orders.json()["total"] == 1

    order_row = await db.execute(select(ConsumerOrder).where(ConsumerOrder.id == order["id"]))
    saved_order = order_row.scalar_one_or_none()
    assert saved_order is not None
    fee_row = await db.execute(select(PlatformFee).where(PlatformFee.order_id == order["id"]))
    assert fee_row.scalar_one_or_none() is not None


async def test_v2_market_auth_boundaries_between_user_and_creator(
    client,
    make_creator,
):
    _, creator_token = await make_creator(email="creator-boundary@test.com")
    register = await _register_user(client, email="buyer-three@test.com")
    user_token = register.json()["token"]

    user_on_admin = await client.get("/api/v2/admin/overview", headers=_auth(user_token))
    assert user_on_admin.status_code in {401, 403}

    creator_on_user = await client.get("/api/v2/users/me", headers=_auth(creator_token))
    assert creator_on_user.status_code == 401

    user_me = await client.get("/api/v2/users/me", headers=_auth(user_token))
    assert user_me.status_code == 200
