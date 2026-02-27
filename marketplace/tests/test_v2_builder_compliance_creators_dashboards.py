"""Integration tests for v2 builder, compliance, creators-profile, dashboards, and events APIs."""

from __future__ import annotations

import uuid

from marketplace.core.auth import decode_stream_token


# ===========================================================================
# Builder API tests (/api/v2/builder/...)
# ===========================================================================


async def test_builder_list_templates_returns_all_templates(client):
    response = await client.get("/api/v2/builder/templates")
    assert response.status_code == 200
    templates = response.json()
    assert isinstance(templates, list)
    assert len(templates) >= 5
    keys = {t["key"] for t in templates}
    assert "firecrawl-web-research" in keys
    assert "api-monitoring-report" in keys
    assert "code-quality-audit" in keys
    assert "doc-brief-pack" in keys
    assert "computation-snapshot" in keys
    for template in templates:
        assert "key" in template
        assert "name" in template
        assert "description" in template
        assert "default_category" in template
        assert "suggested_price_usd" in template


async def test_builder_list_templates_no_auth_required(client):
    """Templates endpoint is public — no Authorization header needed."""
    response = await client.get("/api/v2/builder/templates")
    assert response.status_code == 200


async def test_builder_create_project_happy_path(client, make_creator):
    _, creator_token = await make_creator()
    payload = {
        "template_key": "firecrawl-web-research",
        "title": "My Research Project",
        "config": {"summary": "Weekly web research summary"},
    }
    response = await client.post(
        "/api/v2/builder/projects",
        json=payload,
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["template_key"] == "firecrawl-web-research"
    assert body["title"] == "My Research Project"
    assert body["status"] == "draft"
    assert "id" in body
    assert "creator_id" in body
    assert "created_at" in body
    assert "updated_at" in body


async def test_builder_create_project_invalid_template_key_returns_400(client, make_creator):
    _, creator_token = await make_creator()
    payload = {
        "template_key": "nonexistent-template",
        "title": "Bad Project",
        "config": {},
    }
    response = await client.post(
        "/api/v2/builder/projects",
        json=payload,
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert response.status_code == 400
    assert "nonexistent-template" in response.json()["detail"]


async def test_builder_create_project_no_auth_returns_401(client):
    payload = {
        "template_key": "firecrawl-web-research",
        "title": "Unauthorized Project",
        "config": {},
    }
    response = await client.post("/api/v2/builder/projects", json=payload)
    assert response.status_code == 401


async def test_builder_list_projects_empty_on_new_creator(client, make_creator):
    _, creator_token = await make_creator()
    response = await client.get(
        "/api/v2/builder/projects",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["projects"] == []


async def test_builder_list_projects_returns_created_projects(client, make_creator):
    _, creator_token = await make_creator()
    headers = {"Authorization": f"Bearer {creator_token}"}

    for title in ("Project Alpha", "Project Beta"):
        await client.post(
            "/api/v2/builder/projects",
            json={
                "template_key": "api-monitoring-report",
                "title": title,
                "config": {"summary": f"Summary for {title}"},
            },
            headers=headers,
        )

    response = await client.get("/api/v2/builder/projects", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    titles = {p["title"] for p in body["projects"]}
    assert "Project Alpha" in titles
    assert "Project Beta" in titles


async def test_builder_list_projects_no_auth_returns_401(client):
    response = await client.get("/api/v2/builder/projects")
    assert response.status_code == 401


async def test_builder_publish_project_happy_path(client, make_creator):
    _, creator_token = await make_creator()
    headers = {"Authorization": f"Bearer {creator_token}"}

    create_resp = await client.post(
        "/api/v2/builder/projects",
        json={
            "template_key": "code-quality-audit",
            "title": "Quality Audit Project",
            "config": {
                "summary": "Full lint and test audit",
                "sample_output": "100% pass rate",
            },
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    publish_resp = await client.post(
        f"/api/v2/builder/projects/{project_id}/publish",
        headers=headers,
    )
    assert publish_resp.status_code == 200
    body = publish_resp.json()
    assert "listing_id" in body
    assert body["listing_id"]
    assert body["project"]["status"] == "published"
    assert body["project"]["published_listing_id"] == body["listing_id"]


async def test_builder_publish_project_not_found_returns_404(client, make_creator):
    _, creator_token = await make_creator()
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v2/builder/projects/{fake_id}/publish",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert response.status_code == 404


async def test_builder_publish_project_no_auth_returns_401(client):
    fake_id = str(uuid.uuid4())
    response = await client.post(f"/api/v2/builder/projects/{fake_id}/publish")
    assert response.status_code == 401


async def test_builder_publish_idempotent_already_published(client, make_creator):
    """Publishing the same project twice returns the same listing_id."""
    _, creator_token = await make_creator()
    headers = {"Authorization": f"Bearer {creator_token}"}

    create_resp = await client.post(
        "/api/v2/builder/projects",
        json={
            "template_key": "doc-brief-pack",
            "title": "Doc Brief Project",
            "config": {
                "summary": "Executive document summaries",
                "sample_output": "1-page brief",
            },
        },
        headers=headers,
    )
    project_id = create_resp.json()["id"]

    first = await client.post(
        f"/api/v2/builder/projects/{project_id}/publish",
        headers=headers,
    )
    second = await client.post(
        f"/api/v2/builder/projects/{project_id}/publish",
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["listing_id"] == second.json()["listing_id"]


async def test_builder_publish_without_summary_returns_400(client, make_creator):
    """Publishing a project with no summary or sample_output is rejected."""
    _, creator_token = await make_creator()
    headers = {"Authorization": f"Bearer {creator_token}"}

    create_resp = await client.post(
        "/api/v2/builder/projects",
        json={
            "template_key": "computation-snapshot",
            "title": "Empty Config Project",
            "config": {},
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    publish_resp = await client.post(
        f"/api/v2/builder/projects/{project_id}/publish",
        headers=headers,
    )
    assert publish_resp.status_code == 400


# ===========================================================================
# Compliance API tests (/api/v2/compliance/...)
# ===========================================================================


async def test_compliance_data_export_happy_path(client, make_agent):
    agent, token = await make_agent()
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v2/compliance/data-export",
        json={
            "format": "json",
            "include_transactions": True,
            "include_listings": True,
            "include_reputation": True,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "completed"
    assert body["agent_id"] == agent.id
    assert body["format"] == "json"
    assert body["download_url"] is not None
    assert "created_at" in body


async def test_compliance_data_export_no_auth_returns_401(client):
    response = await client.post(
        "/api/v2/compliance/data-export",
        json={"format": "json"},
    )
    assert response.status_code == 401


async def test_compliance_data_export_cross_agent_forbidden(client, make_agent):
    agent_a, token_a = await make_agent()
    agent_b, _ = await make_agent()
    headers = {"Authorization": f"Bearer {token_a}"}

    response = await client.post(
        "/api/v2/compliance/data-export",
        json={"agent_id": agent_b.id, "format": "json"},
        headers=headers,
    )
    assert response.status_code == 403
    assert "own account" in response.json()["detail"]


async def test_compliance_get_export_status_happy_path(client, make_agent):
    agent, token = await make_agent()
    headers = {"Authorization": f"Bearer {token}"}

    post_resp = await client.post(
        "/api/v2/compliance/data-export",
        json={"format": "csv"},
        headers=headers,
    )
    assert post_resp.status_code == 200
    job_id = post_resp.json()["job_id"]

    get_resp = await client.get(
        f"/api/v2/compliance/data-export/{job_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["job_id"] == job_id
    assert body["format"] == "csv"
    assert body["agent_id"] == agent.id


async def test_compliance_get_export_status_not_found(client, make_agent):
    _, token = await make_agent()
    fake_job_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/v2/compliance/data-export/{fake_job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_compliance_get_export_status_other_agent_forbidden(client, make_agent):
    agent_a, token_a = await make_agent()
    agent_b, token_b = await make_agent()

    post_resp = await client.post(
        "/api/v2/compliance/data-export",
        json={"format": "json"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    job_id = post_resp.json()["job_id"]

    response = await client.get(
        f"/api/v2/compliance/data-export/{job_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


async def test_compliance_data_deletion_happy_path(client, make_agent):
    agent, token = await make_agent()
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v2/compliance/data-deletion",
        json={"reason": "user_request", "soft_delete": True},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "request_id" in body
    assert body["status"] == "pending"
    assert body["agent_id"] == agent.id
    assert body["reason"] == "user_request"
    assert body["soft_delete"] is True
    assert "created_at" in body


async def test_compliance_data_deletion_no_auth_returns_401(client):
    response = await client.post(
        "/api/v2/compliance/data-deletion",
        json={"reason": "user_request"},
    )
    assert response.status_code == 401


async def test_compliance_data_deletion_cross_agent_forbidden(client, make_agent):
    agent_a, token_a = await make_agent()
    agent_b, _ = await make_agent()
    headers = {"Authorization": f"Bearer {token_a}"}

    response = await client.post(
        "/api/v2/compliance/data-deletion",
        json={"agent_id": agent_b.id, "reason": "test"},
        headers=headers,
    )
    assert response.status_code == 403


async def test_compliance_get_deletion_status_happy_path(client, make_agent):
    agent, token = await make_agent()
    headers = {"Authorization": f"Bearer {token}"}

    post_resp = await client.post(
        "/api/v2/compliance/data-deletion",
        json={"reason": "privacy", "soft_delete": False},
        headers=headers,
    )
    assert post_resp.status_code == 200
    request_id = post_resp.json()["request_id"]

    get_resp = await client.get(
        f"/api/v2/compliance/data-deletion/{request_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["request_id"] == request_id
    assert body["reason"] == "privacy"
    assert body["soft_delete"] is False


async def test_compliance_get_deletion_status_not_found(client, make_agent):
    _, token = await make_agent()
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/v2/compliance/data-deletion/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_compliance_get_deletion_status_other_agent_forbidden(client, make_agent):
    agent_a, token_a = await make_agent()
    agent_b, token_b = await make_agent()

    post_resp = await client.post(
        "/api/v2/compliance/data-deletion",
        json={"reason": "user_request"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    request_id = post_resp.json()["request_id"]

    response = await client.get(
        f"/api/v2/compliance/data-deletion/{request_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


async def test_compliance_get_consent_empty_initially(client, make_agent):
    _, token = await make_agent()
    response = await client.get(
        "/api/v2/compliance/consent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_compliance_record_consent_happy_path(client, make_agent):
    agent, token = await make_agent()
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v2/compliance/consent",
        json={
            "consent_type": "data_processing",
            "granted": True,
            "purpose": "Personalized recommendations",
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert body["agent_id"] == agent.id
    assert body["consent_type"] == "data_processing"
    assert body["granted"] is True
    assert body["purpose"] == "Personalized recommendations"
    assert "recorded_at" in body


async def test_compliance_record_consent_no_auth_returns_401(client):
    response = await client.post(
        "/api/v2/compliance/consent",
        json={"consent_type": "marketing", "granted": True},
    )
    assert response.status_code == 401


async def test_compliance_consent_upsert_updates_existing(client, make_agent):
    agent, token = await make_agent()
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v2/compliance/consent",
        json={"consent_type": "analytics", "granted": True, "purpose": "Initial"},
        headers=headers,
    )
    await client.post(
        "/api/v2/compliance/consent",
        json={"consent_type": "analytics", "granted": False, "purpose": "Revoked"},
        headers=headers,
    )

    list_resp = await client.get("/api/v2/compliance/consent", headers=headers)
    assert list_resp.status_code == 200
    records = list_resp.json()
    analytics_records = [r for r in records if r["consent_type"] == "analytics"]
    assert len(analytics_records) == 1
    assert analytics_records[0]["granted"] is False
    assert analytics_records[0]["purpose"] == "Revoked"


async def test_compliance_consent_multiple_types(client, make_agent):
    _, token = await make_agent()
    headers = {"Authorization": f"Bearer {token}"}

    for consent_type in ("data_processing", "marketing", "analytics"):
        await client.post(
            "/api/v2/compliance/consent",
            json={"consent_type": consent_type, "granted": True},
            headers=headers,
        )

    list_resp = await client.get("/api/v2/compliance/consent", headers=headers)
    assert list_resp.status_code == 200
    records = list_resp.json()
    assert len(records) == 3
    types = {r["consent_type"] for r in records}
    assert types == {"data_processing", "marketing", "analytics"}


async def test_compliance_consent_isolated_between_agents(client, make_agent):
    agent_a, token_a = await make_agent()
    agent_b, token_b = await make_agent()

    await client.post(
        "/api/v2/compliance/consent",
        json={"consent_type": "marketing", "granted": True},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    list_resp = await client.get(
        "/api/v2/compliance/consent",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json() == []


# ===========================================================================
# Creators profile API tests (/api/v2/creators/me/developer-profile)
# ===========================================================================


async def test_creator_get_developer_profile_creates_default(client, make_creator):
    creator, creator_token = await make_creator()
    response = await client.get(
        "/api/v2/creators/me/developer-profile",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["creator_id"] == creator.id
    assert body["bio"] == ""
    assert body["links"] == []
    assert body["specialties"] == []
    assert body["featured_flag"] is False
    assert "created_at" in body
    assert "updated_at" in body


async def test_creator_get_developer_profile_no_auth_returns_401(client):
    response = await client.get("/api/v2/creators/me/developer-profile")
    assert response.status_code == 401


async def test_creator_update_developer_profile_happy_path(client, make_creator):
    creator, creator_token = await make_creator()
    headers = {"Authorization": f"Bearer {creator_token}"}

    update_payload = {
        "bio": "I build AI-powered data products.",
        "links": ["https://github.com/testdev", "https://testdev.io"],
        "specialties": ["web_search", "code_analysis"],
        "featured_flag": True,
    }
    response = await client.put(
        "/api/v2/creators/me/developer-profile",
        json=update_payload,
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["creator_id"] == creator.id
    assert body["bio"] == "I build AI-powered data products."
    assert "https://github.com/testdev" in body["links"]
    assert "web_search" in body["specialties"]
    assert body["featured_flag"] is True


async def test_creator_update_developer_profile_no_auth_returns_401(client):
    response = await client.put(
        "/api/v2/creators/me/developer-profile",
        json={"bio": "test"},
    )
    assert response.status_code == 401


async def test_creator_update_developer_profile_persists_on_get(client, make_creator):
    _, creator_token = await make_creator()
    headers = {"Authorization": f"Bearer {creator_token}"}

    await client.put(
        "/api/v2/creators/me/developer-profile",
        json={
            "bio": "Persistent bio",
            "links": ["https://example.com"],
            "specialties": ["computation"],
            "featured_flag": False,
        },
        headers=headers,
    )

    get_resp = await client.get(
        "/api/v2/creators/me/developer-profile",
        headers=headers,
    )
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["bio"] == "Persistent bio"
    assert body["links"] == ["https://example.com"]
    assert body["specialties"] == ["computation"]


async def test_creator_profiles_isolated_between_creators(client, make_creator):
    creator_a, token_a = await make_creator()
    creator_b, token_b = await make_creator()

    await client.put(
        "/api/v2/creators/me/developer-profile",
        json={"bio": "Creator A bio", "links": [], "specialties": [], "featured_flag": False},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    resp_b = await client.get(
        "/api/v2/creators/me/developer-profile",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 200
    assert resp_b.json()["bio"] == ""


async def test_creator_update_profile_overrides_previous(client, make_creator):
    _, creator_token = await make_creator()
    headers = {"Authorization": f"Bearer {creator_token}"}

    await client.put(
        "/api/v2/creators/me/developer-profile",
        json={"bio": "Old bio", "links": ["https://old.com"], "specialties": ["old"], "featured_flag": True},
        headers=headers,
    )
    await client.put(
        "/api/v2/creators/me/developer-profile",
        json={"bio": "New bio", "links": ["https://new.com"], "specialties": ["new"], "featured_flag": False},
        headers=headers,
    )

    resp = await client.get("/api/v2/creators/me/developer-profile", headers=headers)
    body = resp.json()
    assert body["bio"] == "New bio"
    assert body["links"] == ["https://new.com"]
    assert body["specialties"] == ["new"]
    assert body["featured_flag"] is False


# ===========================================================================
# Dashboards API tests (/api/v2/dashboards/...)
# ===========================================================================


async def test_dashboard_agent_me_accepts_agent_token(client, make_agent):
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


async def test_dashboard_agent_me_rejects_no_auth(client):
    response = await client.get("/api/v2/dashboards/agent/me")
    assert response.status_code == 401


async def test_dashboard_agent_me_rejects_creator_token(client, make_creator):
    _, creator_token = await make_creator()
    response = await client.get(
        "/api/v2/dashboards/agent/me",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert response.status_code == 401


async def test_dashboard_creator_me_happy_path(client, make_creator):
    creator, creator_token = await make_creator()
    response = await client.get(
        "/api/v2/dashboards/creator/me",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "creator_id" in body
    assert body["creator_id"] == creator.id


async def test_dashboard_creator_me_no_auth_returns_401(client):
    response = await client.get("/api/v2/dashboards/creator/me")
    assert response.status_code == 401


async def test_dashboard_agent_public_returns_public_data(client, make_agent):
    agent, _ = await make_agent(name="public-agent")
    response = await client.get(f"/api/v2/dashboards/agent/{agent.id}/public")
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == agent.id
    assert "listings_count" in body or "agent_id" in body


async def test_dashboard_agent_public_not_found_returns_404(client):
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v2/dashboards/agent/{fake_id}/public")
    assert response.status_code == 404


async def test_dashboard_agent_private_owner_access_allowed(client, db, make_agent, make_creator):
    owner_creator, owner_token = await make_creator()
    agent, _ = await make_agent()
    agent.creator_id = owner_creator.id
    await db.commit()

    response = await client.get(
        f"/api/v2/dashboards/agent/{agent.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == agent.id


async def test_dashboard_agent_private_non_owner_forbidden(client, db, make_agent, make_creator):
    owner_creator, _ = await make_creator()
    other_creator, other_token = await make_creator()
    agent, _ = await make_agent()
    agent.creator_id = owner_creator.id
    await db.commit()

    response = await client.get(
        f"/api/v2/dashboards/agent/{agent.id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 403


async def test_dashboard_agent_private_admin_can_access(client, db, make_agent, make_creator):
    from marketplace.services.role_service import assign_role, seed_system_roles

    owner_creator, _ = await make_creator()
    admin_creator, admin_token = await make_creator()
    agent, _ = await make_agent()
    agent.creator_id = owner_creator.id
    await db.commit()

    await seed_system_roles(db)
    await assign_role(db, admin_creator.id, "creator", "admin", "system")

    response = await client.get(
        f"/api/v2/dashboards/agent/{agent.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200


async def test_dashboard_agent_private_not_found_returns_404(client, make_creator):
    _, creator_token = await make_creator()
    fake_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/v2/dashboards/agent/{fake_id}",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert response.status_code == 404


async def test_dashboard_agent_private_no_auth_returns_401(client, make_agent):
    agent, _ = await make_agent()
    response = await client.get(f"/api/v2/dashboards/agent/{agent.id}")
    assert response.status_code == 401


async def test_dashboard_agent_private_agent_can_access_own(client, make_agent):
    """An agent token grants access to the same agent's private dashboard."""
    agent, agent_token = await make_agent()
    response = await client.get(
        f"/api/v2/dashboards/agent/{agent.id}",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == agent.id


# ===========================================================================
# Events API tests (/api/v2/events/stream-token)
# ===========================================================================


async def test_events_stream_token_happy_path(client, make_agent):
    agent, agent_token = await make_agent()
    response = await client.get(
        "/api/v2/events/stream-token",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == agent.id
    assert "stream_token" in body
    assert body["stream_token"]
    assert "expires_in_seconds" in body
    assert isinstance(body["expires_in_seconds"], int)
    assert body["expires_in_seconds"] > 0
    assert "expires_at" in body
    assert body["ws_url"] == "/ws/v2/events"
    assert "allowed_topics" in body
    assert set(body["allowed_topics"]) == {"public.market", "private.agent"}


async def test_events_stream_token_is_valid_stream_token(client, make_agent):
    agent, agent_token = await make_agent()
    response = await client.get(
        "/api/v2/events/stream-token",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert response.status_code == 200
    stream_token = response.json()["stream_token"]

    payload = decode_stream_token(stream_token)
    assert payload["sub"] == agent.id
    assert payload["type"] == "stream_agent"
    assert set(payload["allowed_topics"]) == {"public.market", "private.agent"}


async def test_events_stream_token_no_auth_returns_401(client):
    response = await client.get("/api/v2/events/stream-token")
    assert response.status_code == 401


async def test_events_stream_token_creator_token_rejected(client, make_creator):
    """Creator tokens must not be accepted for agent-scoped endpoints."""
    _, creator_token = await make_creator()
    response = await client.get(
        "/api/v2/events/stream-token",
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert response.status_code == 401


async def test_events_stream_token_different_agents_get_different_tokens(client, make_agent):
    agent_a, token_a = await make_agent()
    agent_b, token_b = await make_agent()

    resp_a = await client.get(
        "/api/v2/events/stream-token",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    resp_b = await client.get(
        "/api/v2/events/stream-token",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json()["agent_id"] == agent_a.id
    assert resp_b.json()["agent_id"] == agent_b.id
    assert resp_a.json()["stream_token"] != resp_b.json()["stream_token"]
