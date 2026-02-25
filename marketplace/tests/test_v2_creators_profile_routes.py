"""Tests for v2 creator developer-profile endpoints.

Covers: marketplace/api/v2_creators_profile.py
  - GET  /api/v2/creators/me/developer-profile
  - PUT  /api/v2/creators/me/developer-profile
"""

from __future__ import annotations

import pytest


# ===========================================================================
# GET /api/v2/creators/me/developer-profile
# ===========================================================================

class TestGetDeveloperProfile:
    """Tests for retrieving the developer profile."""

    async def test_get_profile_creates_default_on_first_access(self, client, make_creator):
        _, token = await make_creator()

        resp = await client.get(
            "/api/v2/creators/me/developer-profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "creator_id" in body
        assert body["bio"] == ""
        assert body["links"] == []
        assert body["specialties"] == []
        assert body["featured_flag"] is False
        assert "created_at" in body
        assert "updated_at" in body

    async def test_get_profile_returns_same_data_on_repeat_call(self, client, make_creator):
        _, token = await make_creator()
        headers = {"Authorization": f"Bearer {token}"}

        resp1 = await client.get("/api/v2/creators/me/developer-profile", headers=headers)
        resp2 = await client.get("/api/v2/creators/me/developer-profile", headers=headers)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["creator_id"] == resp2.json()["creator_id"]

    async def test_get_profile_rejects_missing_auth(self, client):
        resp = await client.get("/api/v2/creators/me/developer-profile")
        assert resp.status_code == 401

    async def test_get_profile_rejects_invalid_token(self, client):
        resp = await client.get(
            "/api/v2/creators/me/developer-profile",
            headers={"Authorization": "Bearer invalid-jwt-token"},
        )
        assert resp.status_code == 401

    async def test_get_profile_rejects_agent_token(self, client, make_agent):
        _, agent_token = await make_agent()
        resp = await client.get(
            "/api/v2/creators/me/developer-profile",
            headers={"Authorization": f"Bearer {agent_token}"},
        )
        assert resp.status_code == 401


# ===========================================================================
# PUT /api/v2/creators/me/developer-profile
# ===========================================================================

class TestUpdateDeveloperProfile:
    """Tests for updating the developer profile."""

    async def test_update_profile_happy_path(self, client, make_creator):
        _, token = await make_creator()
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "bio": "Expert in AI agent development",
            "links": ["https://github.com/testdev", "https://linkedin.com/in/testdev"],
            "specialties": ["python", "langchain", "fastapi"],
            "featured_flag": True,
        }
        resp = await client.put(
            "/api/v2/creators/me/developer-profile",
            headers=headers,
            json=payload,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["bio"] == "Expert in AI agent development"
        assert body["links"] == ["https://github.com/testdev", "https://linkedin.com/in/testdev"]
        assert body["specialties"] == ["python", "langchain", "fastapi"]
        assert body["featured_flag"] is True

    async def test_update_profile_persists_across_reads(self, client, make_creator):
        _, token = await make_creator()
        headers = {"Authorization": f"Bearer {token}"}

        update_payload = {
            "bio": "Updated bio",
            "links": ["https://example.com"],
            "specialties": ["rust"],
            "featured_flag": False,
        }
        await client.put(
            "/api/v2/creators/me/developer-profile",
            headers=headers,
            json=update_payload,
        )

        resp = await client.get(
            "/api/v2/creators/me/developer-profile",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["bio"] == "Updated bio"
        assert body["links"] == ["https://example.com"]
        assert body["specialties"] == ["rust"]

    async def test_update_profile_with_empty_fields(self, client, make_creator):
        _, token = await make_creator()
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "bio": "",
            "links": [],
            "specialties": [],
            "featured_flag": False,
        }
        resp = await client.put(
            "/api/v2/creators/me/developer-profile",
            headers=headers,
            json=payload,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["bio"] == ""
        assert body["links"] == []
        assert body["specialties"] == []

    async def test_update_profile_overwrite_previous(self, client, make_creator):
        """Second PUT fully replaces the first."""
        _, token = await make_creator()
        headers = {"Authorization": f"Bearer {token}"}

        first_payload = {
            "bio": "First bio",
            "links": ["https://first.com"],
            "specialties": ["alpha"],
            "featured_flag": True,
        }
        await client.put(
            "/api/v2/creators/me/developer-profile",
            headers=headers,
            json=first_payload,
        )

        second_payload = {
            "bio": "Second bio",
            "links": [],
            "specialties": ["beta", "gamma"],
            "featured_flag": False,
        }
        resp = await client.put(
            "/api/v2/creators/me/developer-profile",
            headers=headers,
            json=second_payload,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["bio"] == "Second bio"
        assert body["links"] == []
        assert body["specialties"] == ["beta", "gamma"]
        assert body["featured_flag"] is False

    async def test_update_profile_rejects_missing_auth(self, client):
        resp = await client.put(
            "/api/v2/creators/me/developer-profile",
            json={"bio": "test", "links": [], "specialties": [], "featured_flag": False},
        )
        assert resp.status_code == 401

    async def test_update_profile_rejects_agent_token(self, client, make_agent):
        _, agent_token = await make_agent()
        resp = await client.put(
            "/api/v2/creators/me/developer-profile",
            headers={"Authorization": f"Bearer {agent_token}"},
            json={"bio": "test", "links": [], "specialties": [], "featured_flag": False},
        )
        assert resp.status_code == 401

    async def test_update_profile_validates_bio_max_length(self, client, make_creator):
        _, token = await make_creator()
        headers = {"Authorization": f"Bearer {token}"}

        # 5001 chars should exceed the max_length=5000 on the schema
        payload = {
            "bio": "x" * 5001,
            "links": [],
            "specialties": [],
            "featured_flag": False,
        }
        resp = await client.put(
            "/api/v2/creators/me/developer-profile",
            headers=headers,
            json=payload,
        )
        assert resp.status_code == 422

    async def test_update_profile_isolation_between_creators(self, client, make_creator):
        """Two creators should have independent profiles."""
        _, token_a = await make_creator()
        _, token_b = await make_creator()

        await client.put(
            "/api/v2/creators/me/developer-profile",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"bio": "Creator A", "links": [], "specialties": [], "featured_flag": True},
        )
        await client.put(
            "/api/v2/creators/me/developer-profile",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"bio": "Creator B", "links": [], "specialties": [], "featured_flag": False},
        )

        resp_a = await client.get(
            "/api/v2/creators/me/developer-profile",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        resp_b = await client.get(
            "/api/v2/creators/me/developer-profile",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp_a.json()["bio"] == "Creator A"
        assert resp_a.json()["featured_flag"] is True
        assert resp_b.json()["bio"] == "Creator B"
        assert resp_b.json()["featured_flag"] is False
