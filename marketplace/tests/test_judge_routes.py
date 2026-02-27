"""HTTP endpoint tests for the judge pipeline API (v5_judge.py).

Tests cover:
- POST /api/v5/judge/evaluate — 401 without auth, 201 with valid request
- GET /api/v5/judge/evaluations/{run_id} — 404 for missing, 200 for existing
- GET /api/v5/judge/evaluations — pagination and filtering
- POST /api/v5/judge/evaluations/{run_id}/human-override — 401, 404, 409, 200
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from marketplace.tests.conftest import _new_id

# ---------------------------------------------------------------------------
# Valid evaluate payload
# ---------------------------------------------------------------------------

_VALID_EVALUATE_PAYLOAD: dict[str, Any] = {
    "target_type": "agent_output",
    "target_id": "test-target-001",
    "input_data": {"query": "What is 2+2?"},
    "output_data": {"result": "4", "status": "ok"},
    "metadata": {},
    "skip_levels": [],
}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# POST /api/v5/judge/evaluate
# ===========================================================================

class TestJudgeEvaluateEndpoint:
    """Tests for POST /api/v5/judge/evaluate."""

    @pytest.mark.asyncio
    async def test_401_without_auth_header(self, client) -> None:
        """No Authorization header → 401."""
        resp = await client.post("/api/v5/judge/evaluate", json=_VALID_EVALUATE_PAYLOAD)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_401_with_invalid_token(self, client) -> None:
        """Malformed Bearer token → 401."""
        resp = await client.post(
            "/api/v5/judge/evaluate",
            headers={"Authorization": "Bearer not.a.real.token"},
            json=_VALID_EVALUATE_PAYLOAD,
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_201_with_valid_auth_and_data(self, client, make_agent) -> None:
        """Authenticated request with valid payload → 201 and full pipeline response."""
        agent, token = await make_agent()

        resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "run_id" in body
        assert "final_verdict" in body
        assert "final_score" in body
        assert "final_confidence" in body
        assert "levels_completed" in body
        assert "verdicts" in body
        assert isinstance(body["verdicts"], list)

    @pytest.mark.asyncio
    async def test_response_schema_fields_correct_types(self, client, make_agent) -> None:
        """Response fields have the expected Python types."""
        _, token = await make_agent()

        resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )
        assert resp.status_code == 201
        body = resp.json()

        assert isinstance(body["run_id"], str)
        assert isinstance(body["final_verdict"], str)
        assert isinstance(body["final_score"], (int, float))
        assert isinstance(body["final_confidence"], (int, float))
        assert isinstance(body["levels_completed"], int)
        assert isinstance(body["verdicts"], list)

    @pytest.mark.asyncio
    async def test_verdict_items_contain_required_fields(self, client, make_agent) -> None:
        """Each item in 'verdicts' has level, name, verdict, score, confidence, duration_ms."""
        _, token = await make_agent()

        resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )
        body = resp.json()
        assert len(body["verdicts"]) > 0

        first = body["verdicts"][0]
        assert "level" in first
        assert "name" in first
        assert "verdict" in first
        assert "score" in first
        assert "confidence" in first
        assert "duration_ms" in first

    @pytest.mark.asyncio
    async def test_422_for_missing_target_type(self, client, make_agent) -> None:
        """Payload without 'target_type' → 422 validation error."""
        _, token = await make_agent()
        payload = dict(_VALID_EVALUATE_PAYLOAD)
        del payload["target_type"]

        resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=payload,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_422_for_missing_target_id(self, client, make_agent) -> None:
        """Payload without 'target_id' → 422."""
        _, token = await make_agent()
        payload = dict(_VALID_EVALUATE_PAYLOAD)
        del payload["target_id"]

        resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=payload,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_422_for_empty_target_type(self, client, make_agent) -> None:
        """Empty string 'target_type' → 422 (min_length=1)."""
        _, token = await make_agent()
        payload = {**_VALID_EVALUATE_PAYLOAD, "target_type": ""}

        resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=payload,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_run_id_is_unique_per_call(self, client, make_agent) -> None:
        """Two evaluate calls produce two different run_ids."""
        _, token = await make_agent()

        resp1 = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )
        resp2 = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json={**_VALID_EVALUATE_PAYLOAD, "target_id": "target-002"},
        )

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["run_id"] != resp2.json()["run_id"]

    @pytest.mark.asyncio
    async def test_skip_levels_in_payload_applied(self, client, make_agent) -> None:
        """skip_levels=[1,2] → first two verdict entries in response are 'skip'."""
        _, token = await make_agent()
        payload = {**_VALID_EVALUATE_PAYLOAD, "skip_levels": [1, 2]}

        resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=payload,
        )
        assert resp.status_code == 201
        body = resp.json()

        l1 = next(v for v in body["verdicts"] if v["level"] == 1)
        l2 = next(v for v in body["verdicts"] if v["level"] == 2)
        assert l1["verdict"] == "skip"
        assert l2["verdict"] == "skip"

    @pytest.mark.asyncio
    async def test_final_score_in_zero_one_range(self, client, make_agent) -> None:
        """Response final_score is always between 0.0 and 1.0."""
        _, token = await make_agent()

        resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )
        body = resp.json()
        assert 0.0 <= body["final_score"] <= 1.0


# ===========================================================================
# GET /api/v5/judge/evaluations/{run_id}
# ===========================================================================

class TestGetEvaluationEndpoint:
    """Tests for GET /api/v5/judge/evaluations/{run_id}."""

    @pytest.mark.asyncio
    async def test_404_for_nonexistent_run_id(self, client) -> None:
        """Unknown run_id → 404 with 'not found' message."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v5/judge/evaluations/{fake_id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_200_for_existing_run(self, client, make_agent) -> None:
        """A run created by POST /evaluate is retrievable by GET."""
        _, token = await make_agent()

        create_resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )
        assert create_resp.status_code == 201
        run_id = create_resp.json()["run_id"]

        get_resp = await client.get(f"/api/v5/judge/evaluations/{run_id}")
        assert get_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_response_matches_create_response(self, client, make_agent) -> None:
        """GET response has same run_id, final_verdict, and levels_completed as the POST."""
        _, token = await make_agent()

        create_resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )
        create_body = create_resp.json()
        run_id = create_body["run_id"]

        get_resp = await client.get(f"/api/v5/judge/evaluations/{run_id}")
        get_body = get_resp.json()

        assert get_body["run_id"] == run_id
        assert get_body["final_verdict"] == create_body["final_verdict"]
        assert get_body["levels_completed"] == create_body["levels_completed"]

    @pytest.mark.asyncio
    async def test_get_response_verdicts_list_populated(self, client, make_agent) -> None:
        """GET response contains a non-empty 'verdicts' list."""
        _, token = await make_agent()

        create_resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )
        run_id = create_resp.json()["run_id"]

        get_resp = await client.get(f"/api/v5/judge/evaluations/{run_id}")
        body = get_resp.json()

        assert isinstance(body["verdicts"], list)
        assert len(body["verdicts"]) > 0

    @pytest.mark.asyncio
    async def test_get_does_not_require_auth(self, client, make_agent) -> None:
        """GET /evaluations/{run_id} is publicly accessible (no auth required)."""
        _, token = await make_agent()

        create_resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )
        run_id = create_resp.json()["run_id"]

        # No auth header on the GET
        get_resp = await client.get(f"/api/v5/judge/evaluations/{run_id}")
        assert get_resp.status_code == 200


# ===========================================================================
# GET /api/v5/judge/evaluations (list)
# ===========================================================================

class TestListEvaluationsEndpoint:
    """Tests for GET /api/v5/judge/evaluations with pagination and filters."""

    @pytest.mark.asyncio
    async def test_empty_list_when_no_runs(self, client) -> None:
        """With no pipeline runs in DB → items=[], total=0."""
        resp = await client.get("/api/v5/judge/evaluations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1

    @pytest.mark.asyncio
    async def test_list_returns_created_runs(self, client, make_agent) -> None:
        """Runs created via POST appear in the list response."""
        _, token = await make_agent()

        await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json={**_VALID_EVALUATE_PAYLOAD, "target_id": "list-target-1"},
        )
        await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json={**_VALID_EVALUATE_PAYLOAD, "target_id": "list-target-2"},
        )

        resp = await client.get("/api/v5/judge/evaluations")
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    @pytest.mark.asyncio
    async def test_pagination_page_size_respected(self, client, make_agent) -> None:
        """page_size=1 returns one item even when multiple runs exist."""
        _, token = await make_agent()

        for i in range(3):
            await client.post(
                "/api/v5/judge/evaluate",
                headers=_auth(token),
                json={**_VALID_EVALUATE_PAYLOAD, "target_id": f"page-target-{i}"},
            )

        resp = await client.get("/api/v5/judge/evaluations", params={"page_size": 1})
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 1
        assert body["page"] == 1
        assert body["page_size"] == 1

    @pytest.mark.asyncio
    async def test_pagination_page_two(self, client, make_agent) -> None:
        """page=2 with page_size=1 returns the second item."""
        _, token = await make_agent()

        for i in range(3):
            await client.post(
                "/api/v5/judge/evaluate",
                headers=_auth(token),
                json={**_VALID_EVALUATE_PAYLOAD, "target_id": f"pg2-target-{i}"},
            )

        resp = await client.get("/api/v5/judge/evaluations", params={"page": 2, "page_size": 1})
        body = resp.json()
        assert body["page"] == 2
        assert len(body["items"]) == 1

    @pytest.mark.asyncio
    async def test_pagination_beyond_total_returns_empty(self, client, make_agent) -> None:
        """Requesting a page beyond available runs returns empty items list."""
        _, token = await make_agent()

        await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )

        resp = await client.get("/api/v5/judge/evaluations", params={"page": 100, "page_size": 10})
        body = resp.json()
        assert body["total"] >= 1
        assert body["items"] == []

    @pytest.mark.asyncio
    async def test_filter_by_target_type(self, client, make_agent) -> None:
        """target_type filter returns only matching runs."""
        _, token = await make_agent()

        await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json={**_VALID_EVALUATE_PAYLOAD, "target_type": "agent_output"},
        )
        await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json={**_VALID_EVALUATE_PAYLOAD, "target_type": "listing"},
        )

        resp = await client.get(
            "/api/v5/judge/evaluations", params={"target_type": "agent_output"}
        )
        body = resp.json()
        assert all(item["target_type"] == "agent_output" for item in body["items"])
        assert body["total"] == 1

    @pytest.mark.asyncio
    async def test_filter_by_target_type_no_match_returns_empty(self, client, make_agent) -> None:
        """Filter with a type that has no runs → total=0, items=[]."""
        _, token = await make_agent()

        await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json={**_VALID_EVALUATE_PAYLOAD, "target_type": "agent_output"},
        )

        resp = await client.get(
            "/api/v5/judge/evaluations", params={"target_type": "nonexistent_type"}
        )
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    @pytest.mark.asyncio
    async def test_filter_by_verdict(self, client, make_agent) -> None:
        """verdict filter returns only runs with matching final_verdict."""
        _, token = await make_agent()

        # Create a run that we know should complete with a specific verdict
        await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )

        resp = await client.get("/api/v5/judge/evaluations")
        body = resp.json()
        actual_verdict = body["items"][0]["final_verdict"]

        # Filter by the actual verdict we got
        filtered_resp = await client.get(
            "/api/v5/judge/evaluations", params={"verdict": actual_verdict}
        )
        filtered_body = filtered_resp.json()
        assert filtered_body["total"] >= 1
        assert all(item["final_verdict"] == actual_verdict for item in filtered_body["items"])

    @pytest.mark.asyncio
    async def test_list_item_schema_fields(self, client, make_agent) -> None:
        """Each item in list response has required JudgeRunSummary fields."""
        _, token = await make_agent()

        await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )

        resp = await client.get("/api/v5/judge/evaluations")
        body = resp.json()
        item = body["items"][0]

        assert "run_id" in item
        assert "target_type" in item
        assert "target_id" in item
        assert "final_verdict" in item
        assert "final_score" in item
        assert "final_confidence" in item
        assert "levels_completed" in item
        assert "created_at" in item

    @pytest.mark.asyncio
    async def test_422_for_page_zero(self, client) -> None:
        """page=0 → 422 (ge=1 constraint)."""
        resp = await client.get("/api/v5/judge/evaluations", params={"page": 0})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_422_for_page_size_over_100(self, client) -> None:
        """page_size=101 → 422 (le=100 constraint)."""
        resp = await client.get("/api/v5/judge/evaluations", params={"page_size": 101})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_does_not_require_auth(self, client) -> None:
        """Listing evaluations is publicly accessible (no auth required)."""
        resp = await client.get("/api/v5/judge/evaluations")
        assert resp.status_code == 200


# ===========================================================================
# POST /api/v5/judge/evaluations/{run_id}/human-override
# ===========================================================================

class TestHumanOverrideEndpoint:
    """Tests for POST /api/v5/judge/evaluations/{run_id}/human-override."""

    _APPROVE_PAYLOAD = {"decision": "approved", "reason": "Reviewed and approved by senior engineer"}
    _REJECT_PAYLOAD = {"decision": "rejected", "reason": "Output contains inaccurate information"}

    async def _create_run(self, client, token: str) -> str:
        """Create a pipeline run and return its run_id."""
        resp = await client.post(
            "/api/v5/judge/evaluate",
            headers=_auth(token),
            json=_VALID_EVALUATE_PAYLOAD,
        )
        assert resp.status_code == 201
        return resp.json()["run_id"]

    @pytest.mark.asyncio
    async def test_401_without_auth(self, client, make_agent) -> None:
        """No Authorization header → 401."""
        _, token = await make_agent()
        run_id = await self._create_run(client, token)

        resp = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            json=self._APPROVE_PAYLOAD,
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_401_with_invalid_token(self, client, make_agent) -> None:
        """Malformed token → 401."""
        _, token = await make_agent()
        run_id = await self._create_run(client, token)

        resp = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            headers={"Authorization": "Bearer invalid.token.here"},
            json=self._APPROVE_PAYLOAD,
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_404_for_nonexistent_run(self, client, make_agent) -> None:
        """Non-existent run_id → 404."""
        _, token = await make_agent()
        fake_id = str(uuid.uuid4())

        resp = await client.post(
            f"/api/v5/judge/evaluations/{fake_id}/human-override",
            headers=_auth(token),
            json=self._APPROVE_PAYLOAD,
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_200_with_valid_approve_override(self, client, make_agent) -> None:
        """Valid 'approved' override → 200 with updated run summary."""
        _, token = await make_agent()
        run_id = await self._create_run(client, token)

        resp = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            headers=_auth(token),
            json=self._APPROVE_PAYLOAD,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["human_override"] == "approved"
        assert body["run_id"] == run_id

    @pytest.mark.asyncio
    async def test_200_with_valid_reject_override(self, client, make_agent) -> None:
        """Valid 'rejected' override → 200 with human_override='rejected'."""
        _, token = await make_agent()
        run_id = await self._create_run(client, token)

        resp = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            headers=_auth(token),
            json=self._REJECT_PAYLOAD,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["human_override"] == "rejected"

    @pytest.mark.asyncio
    async def test_409_when_override_already_applied(self, client, make_agent) -> None:
        """Applying a second override to the same run → 409 Conflict."""
        _, token = await make_agent()
        run_id = await self._create_run(client, token)

        # First override
        resp1 = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            headers=_auth(token),
            json=self._APPROVE_PAYLOAD,
        )
        assert resp1.status_code == 200

        # Second override → conflict
        resp2 = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            headers=_auth(token),
            json=self._REJECT_PAYLOAD,
        )
        assert resp2.status_code == 409

    @pytest.mark.asyncio
    async def test_422_for_invalid_decision_value(self, client, make_agent) -> None:
        """Decision value not in {approved, rejected} → 422."""
        _, token = await make_agent()
        run_id = await self._create_run(client, token)

        resp = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            headers=_auth(token),
            json={"decision": "maybe", "reason": "Not sure"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_422_for_missing_reason(self, client, make_agent) -> None:
        """Override request without 'reason' field → 422."""
        _, token = await make_agent()
        run_id = await self._create_run(client, token)

        resp = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            headers=_auth(token),
            json={"decision": "approved"},  # missing reason
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_422_for_empty_reason(self, client, make_agent) -> None:
        """Empty reason string → 422 (min_length=1)."""
        _, token = await make_agent()
        run_id = await self._create_run(client, token)

        resp = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            headers=_auth(token),
            json={"decision": "approved", "reason": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_override_response_includes_summary_fields(self, client, make_agent) -> None:
        """Override response is a JudgeRunSummary with expected fields."""
        _, token = await make_agent()
        run_id = await self._create_run(client, token)

        resp = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            headers=_auth(token),
            json=self._APPROVE_PAYLOAD,
        )
        body = resp.json()

        assert "run_id" in body
        assert "target_type" in body
        assert "target_id" in body
        assert "final_verdict" in body
        assert "human_override" in body
        assert "created_at" in body

    @pytest.mark.asyncio
    async def test_different_agents_can_override(self, client, make_agent) -> None:
        """A different authenticated agent can apply the human override."""
        creator_agent, creator_token = await make_agent(name="creator-agent")
        reviewer_agent, reviewer_token = await make_agent(name="reviewer-agent")

        run_id = await self._create_run(client, creator_token)

        # Reviewer applies the override
        resp = await client.post(
            f"/api/v5/judge/evaluations/{run_id}/human-override",
            headers=_auth(reviewer_token),
            json=self._APPROVE_PAYLOAD,
        )
        assert resp.status_code == 200
        assert resp.json()["human_override"] == "approved"
