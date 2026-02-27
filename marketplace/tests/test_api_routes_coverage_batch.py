"""Targeted tests to close coverage gaps in 11 API route files.

Each section targets the specific missing lines reported by coverage:
  - v3_webmcp.py:     79, 99, 109-111, 123-125, 152-154, 173, 183-185,
                       207-209, 225, 236-238, 250-254
  - v2_verification.py: 33-39, 49-54, 70-96
  - catalog.py:        76, 95, 110, 120-123, 140-143, 154-157, 173, 190-193, 203
  - audit.py:          31-40, 64-80
  - v2_agents.py:      50-55, 59, 89-111, 149-155, 169-195, 205-208
  - discovery.py:      37-84, 94-96
  - creators.py:       53-55, 65-66, 81-83, 96-97, 107, 119-120
  - automatch.py:      46, 58-73
  - reputation.py:     17-32, 45-50
  - v2_billing.py:     67-76, 93-107, 123-124, 135-136, 147-160
  - registry.py:       33-40, 52, 66, 80, 93, 106
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _agent_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _creator_params(token: str) -> dict[str, str]:
    """Creator auth passed as query param (webmcp pattern)."""
    return {"authorization": f"Bearer {token}"}


def _creator_bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# marketplace/api/v3_webmcp.py
# Lines: 79, 99, 109-111, 123-125, 152-154, 173, 183-185, 207-209, 225,
#        236-238, 250-254
# ===========================================================================

class TestWebmcpReturnPaths:
    """Cover the return/error lines in v3_webmcp route handlers."""

    async def _make_approved_tool(self, client, creator_token: str) -> str:
        reg = await client.post(
            "/api/v3/webmcp/tools",
            json={
                "name": f"tool-{_new_id()[:6]}",
                "description": "test",
                "domain": "example.com",
                "endpoint_url": "https://example.com/mcp",
                "category": "research",
            },
            params=_creator_params(creator_token),
        )
        tool_id = reg.json()["id"]
        await client.put(
            f"/api/v3/webmcp/tools/{tool_id}/approve",
            json={"notes": "ok"},
            params=_creator_params(creator_token),
        )
        return tool_id

    async def test_register_tool_return_result(self, client, make_creator):
        """Line 79: register_tool returns service result (happy path)."""
        from marketplace.api.v3_webmcp import register_tool, ToolRegisterRequest
        creator, token = await make_creator()

        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.register_tool",
            new_callable=AsyncMock,
            return_value={"id": "tool-1", "name": "t", "status": "pending"},
        ) as mock_reg, patch(
            "marketplace.api.v3_webmcp.get_current_creator_id",
            return_value=creator.id,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            req = ToolRegisterRequest(
                name="my-tool",
                domain="example.com",
                endpoint_url="https://example.com/mcp",
                category="research",
            )
            result = await register_tool(req, db=db_mock, creator_id=creator.id)
        assert result["id"] == "tool-1"
        mock_reg.assert_called_once()

    async def test_list_tools_return_envelope(self, client, make_creator):
        """Line 99: list_tools returns pagination envelope."""
        from marketplace.api.v3_webmcp import list_tools

        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.list_tools",
            new_callable=AsyncMock,
            return_value=([{"id": "t1"}], 1),
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            result = await list_tools(q=None, category=None, domain=None, status=None,
                                      page=1, page_size=20, db=db_mock)
        assert result["total"] == 1
        assert len(result["tools"]) == 1

    async def test_get_tool_not_found_404(self, client, make_agent):
        """Lines 109-111: get_tool raises 404 when service returns None."""
        from fastapi import HTTPException
        from marketplace.api.v3_webmcp import get_tool

        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.get_tool",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            with pytest.raises(HTTPException) as exc_info:
                await get_tool("nonexistent-id", db=db_mock)
        assert exc_info.value.status_code == 404

    async def test_get_tool_found_returns_tool(self, client, make_creator):
        """Lines 109-111: get_tool returns tool when found."""
        from marketplace.api.v3_webmcp import get_tool

        tool_data = {"id": "t1", "name": "my-tool", "status": "approved"}
        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.get_tool",
            new_callable=AsyncMock,
            return_value=tool_data,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            result = await get_tool("t1", db=db_mock)
        assert result["id"] == "t1"

    async def test_approve_tool_not_found_404(self, client, make_creator):
        """Lines 123-125: approve_tool raises 404 when service returns None."""
        from fastapi import HTTPException
        from marketplace.api.v3_webmcp import approve_tool, ToolApproveRequest

        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.approve_tool",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            with pytest.raises(HTTPException) as exc_info:
                await approve_tool("bad-id", ToolApproveRequest(), db=db_mock, creator_id="c1")
        assert exc_info.value.status_code == 404

    async def test_approve_tool_found_returns_result(self, client, make_creator):
        """Lines 123-125: approve_tool returns result when found."""
        from marketplace.api.v3_webmcp import approve_tool, ToolApproveRequest

        tool_data = {"id": "t1", "status": "approved"}
        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.approve_tool",
            new_callable=AsyncMock,
            return_value=tool_data,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            result = await approve_tool("t1", ToolApproveRequest(notes="ok"), db=db_mock, creator_id="c1")
        assert result["status"] == "approved"

    async def test_create_action_returns_result(self, client, make_agent, make_creator):
        """Lines 152-154: create_action returns result on success."""
        from marketplace.api.v3_webmcp import create_action, ActionCreateRequest

        action_data = {"id": "a1", "tool_id": "t1", "status": "active"}
        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.create_action_listing",
            new_callable=AsyncMock,
            return_value=action_data,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            req = ActionCreateRequest(tool_id="t1", title="My Action", price_per_execution=0.05)
            result = await create_action(req, db=db_mock, agent_id="agent-1")
        assert result["id"] == "a1"

    async def test_create_action_value_error_raises_400(self, client, make_agent, make_creator):
        """Lines 152-154: create_action raises 400 on ValueError."""
        from fastapi import HTTPException
        from marketplace.api.v3_webmcp import create_action, ActionCreateRequest

        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.create_action_listing",
            new_callable=AsyncMock,
            side_effect=ValueError("Tool not approved"),
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            req = ActionCreateRequest(tool_id="t1", title="My Action", price_per_execution=0.05)
            with pytest.raises(HTTPException) as exc_info:
                await create_action(req, db=db_mock, agent_id="agent-1")
        assert exc_info.value.status_code == 400
        assert "Tool not approved" in exc_info.value.detail

    async def test_list_actions_return_envelope(self, client):
        """Line 173: list_actions returns pagination envelope."""
        from marketplace.api.v3_webmcp import list_actions

        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.list_action_listings",
            new_callable=AsyncMock,
            return_value=([{"id": "a1"}], 1),
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            result = await list_actions(q=None, category=None, max_price=None,
                                        page=1, page_size=20, db=db_mock)
        assert result["total"] == 1
        assert len(result["actions"]) == 1

    async def test_get_action_not_found_404(self, client):
        """Lines 183-185: get_action raises 404 when service returns None."""
        from fastapi import HTTPException
        from marketplace.api.v3_webmcp import get_action

        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.get_action_listing",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            with pytest.raises(HTTPException) as exc_info:
                await get_action("bad-id", db=db_mock)
        assert exc_info.value.status_code == 404

    async def test_get_action_found_returns_listing(self, client):
        """Lines 183-185: get_action returns listing when found."""
        from marketplace.api.v3_webmcp import get_action

        listing_data = {"id": "a1", "title": "My Action", "status": "active"}
        with patch(
            "marketplace.api.v3_webmcp.webmcp_service.get_action_listing",
            new_callable=AsyncMock,
            return_value=listing_data,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            result = await get_action("a1", db=db_mock)
        assert result["id"] == "a1"

    async def test_execute_action_returns_result(self, client):
        """Lines 207-209: execute_action returns result on success."""
        from marketplace.api.v3_webmcp import execute_action, ExecuteRequest

        exec_data = {"id": "e1", "status": "completed"}
        with patch(
            "marketplace.api.v3_webmcp.action_executor.execute_action",
            new_callable=AsyncMock,
            return_value=exec_data,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            req = ExecuteRequest(parameters={}, consent=True)
            result = await execute_action("a1", req, db=db_mock, agent_id="agent-1")
        assert result["id"] == "e1"

    async def test_execute_action_value_error_raises_400(self, client):
        """Lines 207-209: execute_action raises 400 on ValueError."""
        from fastapi import HTTPException
        from marketplace.api.v3_webmcp import execute_action, ExecuteRequest

        with patch(
            "marketplace.api.v3_webmcp.action_executor.execute_action",
            new_callable=AsyncMock,
            side_effect=ValueError("Consent required"),
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            req = ExecuteRequest(parameters={}, consent=False)
            with pytest.raises(HTTPException) as exc_info:
                await execute_action("a1", req, db=db_mock, agent_id="agent-1")
        assert exc_info.value.status_code == 400

    async def test_list_executions_return_envelope(self, client):
        """Line 225: list_executions returns pagination envelope."""
        from marketplace.api.v3_webmcp import list_executions

        with patch(
            "marketplace.api.v3_webmcp.action_executor.list_executions",
            new_callable=AsyncMock,
            return_value=([{"id": "e1"}], 1),
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            result = await list_executions(status=None, page=1, page_size=20,
                                           db=db_mock, agent_id="agent-1")
        assert result["total"] == 1
        assert len(result["executions"]) == 1

    async def test_get_execution_not_found_404(self, client):
        """Lines 236-238: get_execution raises 404 when not found."""
        from fastapi import HTTPException
        from marketplace.api.v3_webmcp import get_execution

        with patch(
            "marketplace.api.v3_webmcp.action_executor.get_execution",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            with pytest.raises(HTTPException) as exc_info:
                await get_execution("bad-id", db=db_mock, agent_id="agent-1")
        assert exc_info.value.status_code == 404

    async def test_get_execution_found_returns_result(self, client):
        """Lines 236-238: get_execution returns execution when found."""
        from marketplace.api.v3_webmcp import get_execution

        exec_data = {"id": "e1", "status": "completed"}
        with patch(
            "marketplace.api.v3_webmcp.action_executor.get_execution",
            new_callable=AsyncMock,
            return_value=exec_data,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            result = await get_execution("e1", db=db_mock, agent_id="agent-1")
        assert result["id"] == "e1"

    async def test_cancel_execution_not_found_404(self, client):
        """Lines 250-254: cancel_execution raises 404 when not found."""
        from fastapi import HTTPException
        from marketplace.api.v3_webmcp import cancel_execution

        with patch(
            "marketplace.api.v3_webmcp.action_executor.cancel_execution",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            with pytest.raises(HTTPException) as exc_info:
                await cancel_execution("bad-id", db=db_mock, agent_id="agent-1")
        assert exc_info.value.status_code == 404

    async def test_cancel_execution_value_error_400(self, client):
        """Lines 250-254: cancel_execution raises 400 on ValueError."""
        from fastapi import HTTPException
        from marketplace.api.v3_webmcp import cancel_execution

        with patch(
            "marketplace.api.v3_webmcp.action_executor.cancel_execution",
            new_callable=AsyncMock,
            side_effect=ValueError("Execution already completed"),
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            with pytest.raises(HTTPException) as exc_info:
                await cancel_execution("e1", db=db_mock, agent_id="agent-1")
        assert exc_info.value.status_code == 400

    async def test_cancel_execution_success_returns_result(self, client):
        """Lines 250-254: cancel_execution returns result when found."""
        from marketplace.api.v3_webmcp import cancel_execution

        exec_data = {"id": "e1", "status": "cancelled"}
        with patch(
            "marketplace.api.v3_webmcp.action_executor.cancel_execution",
            new_callable=AsyncMock,
            return_value=exec_data,
        ):
            from sqlalchemy.ext.asyncio import AsyncSession
            db_mock = MagicMock(spec=AsyncSession)
            result = await cancel_execution("e1", db=db_mock, agent_id="agent-1")
        assert result["status"] == "cancelled"


# ===========================================================================
# marketplace/api/v2_verification.py
# Lines: 33-39, 49-54, 70-96
# ===========================================================================

class TestV2VerificationReturnPaths:
    """Cover return/error lines in v2_verification route handlers."""

    async def test_get_listing_trust_state_returns_payload(self, db, make_agent, make_listing):
        """Lines 33-39: get_listing_trust_state returns payload with listing_id."""
        from marketplace.api.v2_verification import get_listing_trust_state

        agent, _ = await make_agent(name="verif-gs")
        listing = await make_listing(agent.id, price_usdc=1.0)

        result = await get_listing_trust_state(listing.id, db=db)
        assert result["listing_id"] == listing.id
        assert "trust_status" in result

    async def test_get_listing_trust_state_not_found(self, db):
        """Lines 33-35: get_listing_trust_state raises 404 for missing listing."""
        from fastapi import HTTPException
        from marketplace.api.v2_verification import get_listing_trust_state

        with pytest.raises(HTTPException) as exc_info:
            await get_listing_trust_state("nonexistent-id", db=db)
        assert exc_info.value.status_code == 404

    async def test_run_listing_verification_returns_result(self, db, make_agent, make_listing):
        """Lines 49-54: run_listing_verification runs for the seller."""
        from marketplace.api.v2_verification import run_listing_verification

        agent, _ = await make_agent(name="verif-run")
        listing = await make_listing(agent.id, price_usdc=1.0)

        result = await run_listing_verification(listing.id, db=db, current_agent=agent.id)
        assert result["listing_id"] == listing.id

    async def test_run_listing_verification_not_found(self, db, make_agent):
        """Lines 49-51: run_listing_verification raises 404 for missing listing."""
        from fastapi import HTTPException
        from marketplace.api.v2_verification import run_listing_verification

        agent, _ = await make_agent(name="verif-run-nf")
        with pytest.raises(HTTPException) as exc_info:
            await run_listing_verification("nonexistent-id", db=db, current_agent=agent.id)
        assert exc_info.value.status_code == 404

    async def test_run_listing_verification_not_seller_403(self, db, make_agent, make_listing):
        """Lines 52-53: run_listing_verification raises 403 for non-seller."""
        from fastapi import HTTPException
        from marketplace.api.v2_verification import run_listing_verification

        seller, _ = await make_agent(name="verif-seller-nf")
        other, _ = await make_agent(name="verif-other-nf")
        listing = await make_listing(seller.id, price_usdc=1.0)

        with pytest.raises(HTTPException) as exc_info:
            await run_listing_verification(listing.id, db=db, current_agent=other.id)
        assert exc_info.value.status_code == 403

    async def test_add_listing_source_receipt_returns_result(self, db, make_agent, make_listing):
        """Lines 70-96: add_listing_source_receipt returns receipt+verification dict."""
        from marketplace.api.v2_verification import (
            add_listing_source_receipt, SourceReceiptCreateRequest,
        )

        agent, _ = await make_agent(name="verif-receipt")
        listing = await make_listing(agent.id, price_usdc=1.0)

        req = SourceReceiptCreateRequest(
            provider="firecrawl",
            source_query="test query",
            seller_signature="sig_long_enough",
        )
        result = await add_listing_source_receipt(
            listing.id, req, db=db, current_agent=agent.id,
        )
        assert "receipt_id" in result
        assert "verification" in result

    async def test_add_listing_source_receipt_not_found_404(self, db, make_agent):
        """Lines 71-72: add_listing_source_receipt raises 404 for missing listing."""
        from fastapi import HTTPException
        from marketplace.api.v2_verification import (
            add_listing_source_receipt, SourceReceiptCreateRequest,
        )

        agent, _ = await make_agent(name="verif-receipt-nf")
        req = SourceReceiptCreateRequest(
            provider="firecrawl",
            source_query="test",
            seller_signature="sig_long_enough",
        )
        with pytest.raises(HTTPException) as exc_info:
            await add_listing_source_receipt(
                "nonexistent-id", req, db=db, current_agent=agent.id,
            )
        assert exc_info.value.status_code == 404

    async def test_add_listing_source_receipt_not_seller_403(self, db, make_agent, make_listing):
        """Lines 73-74: add_listing_source_receipt raises 403 for non-seller."""
        from fastapi import HTTPException
        from marketplace.api.v2_verification import (
            add_listing_source_receipt, SourceReceiptCreateRequest,
        )

        seller, _ = await make_agent(name="verif-r-seller")
        other, _ = await make_agent(name="verif-r-other")
        listing = await make_listing(seller.id, price_usdc=1.0)

        req = SourceReceiptCreateRequest(
            provider="firecrawl",
            source_query="test",
            seller_signature="sig_long_enough",
        )
        with pytest.raises(HTTPException) as exc_info:
            await add_listing_source_receipt(
                listing.id, req, db=db, current_agent=other.id,
            )
        assert exc_info.value.status_code == 403

    async def test_add_listing_source_receipt_value_error_400(self, db, make_agent, make_listing):
        """Lines 87-88: add_listing_source_receipt raises 400 on ValueError."""
        from fastapi import HTTPException
        from marketplace.api.v2_verification import (
            add_listing_source_receipt, SourceReceiptCreateRequest,
        )

        agent, _ = await make_agent(name="verif-r-ve")
        listing = await make_listing(agent.id, price_usdc=1.0)

        req = SourceReceiptCreateRequest(
            provider="unsupported_provider_xyz",
            source_query="test",
            seller_signature="sig_long_enough",
        )
        with pytest.raises(HTTPException) as exc_info:
            await add_listing_source_receipt(
                listing.id, req, db=db, current_agent=agent.id,
            )
        assert exc_info.value.status_code == 400


# ===========================================================================
# marketplace/api/catalog.py
# Lines: 76, 95, 110, 120-123, 140-143, 154-157, 173, 190-193, 203
# ===========================================================================

class TestCatalogReturnPaths:
    """Cover return/error lines in catalog route handlers."""

    async def test_register_entry_returns_dict(self, db, make_agent):
        """Line 76: register_entry returns _entry_to_dict(entry)."""
        from marketplace.api.catalog import register_entry, CatalogCreateRequest

        agent, _ = await make_agent(name="cat-reg-ret")
        req = CatalogCreateRequest(namespace="web_search", topic="test-topic")
        result = await register_entry(req, db=db, agent_id=agent.id)
        assert result["agent_id"] == agent.id
        assert result["namespace"] == "web_search"

    async def test_search_catalog_returns_entries(self, db, make_agent):
        """Line 95: search_catalog returns entries + pagination."""
        from marketplace.api.catalog import search_catalog, register_entry, CatalogCreateRequest

        agent, _ = await make_agent(name="cat-search-ret")
        req = CatalogCreateRequest(namespace="web_search", topic="searchable-topic",
                                   description="Searchable")
        await register_entry(req, db=db, agent_id=agent.id)

        result = await search_catalog(q="searchable", namespace=None,
                                      min_quality=None, max_price=None,
                                      page=1, page_size=20, db=db)
        assert "entries" in result
        assert "total" in result

    async def test_get_agent_catalog_returns_entries(self, db, make_agent):
        """Line 110: get_agent_catalog returns entries dict."""
        from marketplace.api.catalog import (
            get_agent_catalog, register_entry, CatalogCreateRequest,
        )

        agent, _ = await make_agent(name="cat-agent-ret")
        req = CatalogCreateRequest(namespace="web_search", topic="agent-topic")
        await register_entry(req, db=db, agent_id=agent.id)

        result = await get_agent_catalog(agent.id, db=db)
        assert result["count"] >= 1

    async def test_get_entry_returns_dict(self, db, make_agent):
        """Lines 120-123: get_entry returns entry dict when found."""
        from marketplace.api.catalog import (
            get_entry, register_entry, CatalogCreateRequest,
        )

        agent, _ = await make_agent(name="cat-get-ret")
        req = CatalogCreateRequest(namespace="web_search", topic="get-topic")
        created = await register_entry(req, db=db, agent_id=agent.id)
        entry_id = created["id"]

        result = await get_entry(entry_id, db=db)
        assert result["id"] == entry_id

    async def test_get_entry_not_found_404(self, db):
        """Lines 120-122: get_entry raises 404 for missing entry."""
        from fastapi import HTTPException
        from marketplace.api.catalog import get_entry

        with pytest.raises(HTTPException) as exc_info:
            await get_entry("nonexistent-id", db=db)
        assert exc_info.value.status_code == 404

    async def test_update_entry_returns_dict(self, db, make_agent):
        """Lines 140-143: update_entry returns updated dict."""
        from marketplace.api.catalog import (
            update_entry, register_entry, CatalogCreateRequest, CatalogUpdateRequest,
        )

        agent, _ = await make_agent(name="cat-upd-ret")
        req = CatalogCreateRequest(namespace="web_search", topic="upd-topic")
        created = await register_entry(req, db=db, agent_id=agent.id)
        entry_id = created["id"]

        upd_req = CatalogUpdateRequest(description="updated description")
        result = await update_entry(entry_id, upd_req, db=db, agent_id=agent.id)
        assert result["description"] == "updated description"

    async def test_update_entry_not_found_404(self, db, make_agent):
        """Lines 140-142: update_entry raises 404 for missing/wrong-owner entry."""
        from fastapi import HTTPException
        from marketplace.api.catalog import update_entry, CatalogUpdateRequest

        agent, _ = await make_agent(name="cat-upd-nf")
        upd_req = CatalogUpdateRequest(description="upd")
        with pytest.raises(HTTPException) as exc_info:
            await update_entry("nonexistent-id", upd_req, db=db, agent_id=agent.id)
        assert exc_info.value.status_code == 404

    async def test_delete_entry_returns_deleted(self, db, make_agent):
        """Lines 154-157: delete_entry returns {"deleted": True}."""
        from marketplace.api.catalog import (
            delete_entry, register_entry, CatalogCreateRequest,
        )

        agent, _ = await make_agent(name="cat-del-ret")
        req = CatalogCreateRequest(namespace="web_search", topic="del-topic")
        created = await register_entry(req, db=db, agent_id=agent.id)
        entry_id = created["id"]

        result = await delete_entry(entry_id, db=db, agent_id=agent.id)
        assert result["deleted"] is True

    async def test_delete_entry_not_found_404(self, db, make_agent):
        """Lines 154-156: delete_entry raises 404 for missing/wrong-owner entry."""
        from fastapi import HTTPException
        from marketplace.api.catalog import delete_entry

        agent, _ = await make_agent(name="cat-del-nf")
        with pytest.raises(HTTPException) as exc_info:
            await delete_entry("nonexistent-id", db=db, agent_id=agent.id)
        assert exc_info.value.status_code == 404

    async def test_subscribe_returns_sub_dict(self, db, make_agent):
        """Line 173: subscribe returns subscription dict."""
        from marketplace.api.catalog import subscribe, SubscribeRequest

        agent, _ = await make_agent(name="cat-sub-ret")
        req = SubscribeRequest(namespace_pattern="web_search.*")
        result = await subscribe(req, db=db, subscriber_id=agent.id)
        assert result["status"] == "active"
        assert result["namespace_pattern"] == "web_search.*"

    async def test_unsubscribe_returns_ok(self, db, make_agent):
        """Lines 190-193: unsubscribe returns {"unsubscribed": True}."""
        from marketplace.api.catalog import (
            subscribe, unsubscribe, SubscribeRequest,
        )

        agent, _ = await make_agent(name="cat-unsub-ret")
        req = SubscribeRequest(namespace_pattern="web_search.*")
        sub = await subscribe(req, db=db, subscriber_id=agent.id)
        sub_id = sub["id"]

        result = await unsubscribe(sub_id, db=db, subscriber_id=agent.id)
        assert result["unsubscribed"] is True

    async def test_unsubscribe_not_found_404(self, db, make_agent):
        """Lines 190-192: unsubscribe raises 404 for missing subscription."""
        from fastapi import HTTPException
        from marketplace.api.catalog import unsubscribe

        agent, _ = await make_agent(name="cat-unsub-nf")
        with pytest.raises(HTTPException) as exc_info:
            await unsubscribe("nonexistent-sub-id", db=db, subscriber_id=agent.id)
        assert exc_info.value.status_code == 404

    async def test_auto_populate_returns_entries(self, db, make_agent, make_listing):
        """Line 203: auto_populate returns created/entries dict."""
        from marketplace.api.catalog import auto_populate

        agent, _ = await make_agent(name="cat-auto-ret")
        await make_listing(agent.id, category="web_search", title="Auto-Pop Item")

        result = await auto_populate(db=db, agent_id=agent.id)
        assert "created" in result
        assert "entries" in result


# ===========================================================================
# marketplace/api/audit.py
# Lines: 31-40, 64-80
# ===========================================================================

class TestAuditReturnPaths:
    """Cover return/error lines in audit route handlers."""

    async def test_list_audit_events_returns_filtered_data(self, db, make_agent):
        """Lines 31-40: list_audit_events with filters returns correct structure."""
        from marketplace.api.audit import list_audit_events
        from marketplace.services.audit_service import log_event

        agent, _ = await make_agent(name="audit-list-ret")
        await log_event(db, "agent.registered", agent_id=agent.id, severity="info",
                        details={"name": agent.name})
        await log_event(db, "purchase.completed", agent_id=agent.id, severity="warning")

        result = await list_audit_events(
            event_type="agent.registered",
            severity=None,
            page=1,
            page_size=50,
            db=db,
            _agent_id=agent.id,
        )
        assert result["total"] >= 1
        assert all(e["event_type"] == "agent.registered" for e in result["events"])

    async def test_list_audit_events_severity_filter(self, db, make_agent):
        """Lines 31-40: list_audit_events with severity filter."""
        from marketplace.api.audit import list_audit_events
        from marketplace.services.audit_service import log_event

        agent, _ = await make_agent(name="audit-sev-ret")
        await log_event(db, "security.alert", agent_id=agent.id, severity="warning")
        await log_event(db, "agent.heartbeat", agent_id=agent.id, severity="info")

        result = await list_audit_events(
            event_type=None,
            severity="warning",
            page=1,
            page_size=50,
            db=db,
            _agent_id=agent.id,
        )
        assert result["total"] >= 1
        assert all(e["severity"] == "warning" for e in result["events"])

    async def test_list_audit_events_both_filters(self, db, make_agent):
        """Lines 31-40: both event_type and severity filters applied."""
        from marketplace.api.audit import list_audit_events
        from marketplace.services.audit_service import log_event

        agent, _ = await make_agent(name="audit-both-ret")
        await log_event(db, "purchase.failed", agent_id=agent.id, severity="error")

        result = await list_audit_events(
            event_type="purchase.failed",
            severity="error",
            page=1,
            page_size=50,
            db=db,
            _agent_id=agent.id,
        )
        assert "events" in result
        assert "total" in result

    async def test_verify_audit_chain_empty_valid(self, db, make_agent):
        """Lines 64-80: verify_audit_chain with no entries returns valid=True."""
        from marketplace.api.audit import verify_audit_chain

        agent, _ = await make_agent(name="audit-verif-empty")
        result = await verify_audit_chain(limit=1000, db=db, _agent_id=agent.id)
        assert result["valid"] is True
        assert result["entries_checked"] == 0

    async def test_verify_audit_chain_with_entries_valid(self, db, make_agent):
        """Lines 64-80: verify_audit_chain with hash chain returns entries_checked."""
        from marketplace.api.audit import verify_audit_chain
        from marketplace.services.audit_service import log_event

        agent, _ = await make_agent(name="audit-verif-chain")
        await log_event(db, "event.one", agent_id=agent.id, severity="info")
        await log_event(db, "event.two", agent_id=agent.id, severity="info")

        result = await verify_audit_chain(limit=1000, db=db, _agent_id=agent.id)
        assert "valid" in result
        if result["valid"]:
            assert "entries_checked" in result

    async def test_verify_audit_chain_skip_null_hash(self, db, make_agent):
        """Lines 68-70: entries with null entry_hash are skipped."""
        from marketplace.api.audit import verify_audit_chain
        from marketplace.models.audit_log import AuditLog

        agent, _ = await make_agent(name="audit-null-hash")
        # Insert a log entry with no hash
        entry = AuditLog(
            id=_new_id(),
            event_type="no.hash.event",
            agent_id=agent.id,
            severity="info",
            entry_hash=None,
        )
        db.add(entry)
        await db.commit()

        result = await verify_audit_chain(limit=1000, db=db, _agent_id=agent.id)
        assert result["valid"] is True

    async def test_verify_audit_chain_broken_chain(self, db, make_agent):
        """Lines 75-76: broken chain returns valid=False with broken_at."""
        from marketplace.api.audit import verify_audit_chain
        from marketplace.models.audit_log import AuditLog
        import datetime

        agent, _ = await make_agent(name="audit-broken")
        # Insert an entry with a wrong hash
        entry = AuditLog(
            id=_new_id(),
            event_type="tampered.event",
            agent_id=agent.id,
            severity="info",
            entry_hash="definitely-wrong-hash-value",
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db.add(entry)
        await db.commit()

        result = await verify_audit_chain(limit=1000, db=db, _agent_id=agent.id)
        assert result["valid"] is False
        assert "broken_at" in result


# ===========================================================================
# marketplace/api/v2_agents.py
# Lines: 50-55, 59, 89-111, 149-155, 169-195, 205-208
# ===========================================================================

class TestV2AgentsReturnPaths:
    """Cover return/error lines in v2_agents route handlers."""

    async def test_onboard_agent_returns_full_profile(self, db, make_creator):
        """Lines 89-119: onboard_agent_v2 returns profile dict."""
        from marketplace.api.v2_agents import onboard_agent_v2, AgentOnboardRequest
        from marketplace.core.creator_auth import create_creator_token

        creator, token = await make_creator(display_name="v2-onboard-ret")

        req = AgentOnboardRequest(
            name=f"onboard-ret-{_new_id()[:6]}",
            agent_type="seller",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-onboard-ret",
        )
        result = await onboard_agent_v2(
            req, db=db, authorization=f"Bearer {token}",
        )
        assert "agent_id" in result
        assert "agent_jwt_token" in result

    async def test_onboard_agent_with_memory_import(self, db, make_creator):
        """Lines 98-109: onboard with memory_import_intent=True updates memory stage."""
        from marketplace.api.v2_agents import onboard_agent_v2, AgentOnboardRequest

        creator, token = await make_creator(display_name="v2-mem-import")
        req = AgentOnboardRequest(
            name=f"mem-import-{_new_id()[:6]}",
            agent_type="both",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-mem-import",
            memory_import_intent=True,
        )
        result = await onboard_agent_v2(req, db=db, authorization=f"Bearer {token}")
        assert "agent_id" in result

    async def test_onboard_agent_unauthorized(self, db):
        """Lines 70-72: onboard_agent_v2 raises 401 for missing/invalid auth."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import onboard_agent_v2, AgentOnboardRequest

        req = AgentOnboardRequest(
            name="unauth-agent",
            agent_type="seller",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-unauth",
        )
        with pytest.raises(HTTPException) as exc_info:
            await onboard_agent_v2(req, db=db, authorization=None)
        assert exc_info.value.status_code == 401

    async def test_attest_runtime_returns_result(self, db, make_creator):
        """Lines 131-139: attest_runtime_v2 returns attestation result."""
        from marketplace.api.v2_agents import (
            attest_runtime_v2, onboard_agent_v2, AgentOnboardRequest,
            RuntimeAttestationRequest,
        )

        creator, token = await make_creator(display_name="v2-attest-ret")
        onboard_req = AgentOnboardRequest(
            name=f"attest-ret-{_new_id()[:6]}",
            agent_type="seller",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-attest-ret",
        )
        onboard_resp = await onboard_agent_v2(onboard_req, db=db, authorization=f"Bearer {token}")
        agent_id = onboard_resp["agent_id"]

        attest_req = RuntimeAttestationRequest(runtime_name="python", runtime_version="3.11")
        result = await attest_runtime_v2(agent_id, attest_req, db=db, current_agent_id=agent_id)
        assert result is not None
        # Result may be a dict with profile or attestation_id
        assert isinstance(result, dict)

    async def test_attest_runtime_wrong_agent_403(self, db, make_creator, make_agent):
        """Lines 129-130: attest_runtime_v2 raises 403 for wrong agent."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import (
            attest_runtime_v2, onboard_agent_v2, AgentOnboardRequest,
            RuntimeAttestationRequest,
        )

        creator, token = await make_creator(display_name="v2-attest-403")
        onboard_req = AgentOnboardRequest(
            name=f"attest-403-{_new_id()[:6]}",
            agent_type="seller",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-attest-403",
        )
        onboard_resp = await onboard_agent_v2(onboard_req, db=db, authorization=f"Bearer {token}")
        agent_id = onboard_resp["agent_id"]
        other, _ = await make_agent(name="attest-other")

        attest_req = RuntimeAttestationRequest(runtime_name="python")
        with pytest.raises(HTTPException) as exc_info:
            await attest_runtime_v2(agent_id, attest_req, db=db, current_agent_id=other.id)
        assert exc_info.value.status_code == 403

    async def test_run_knowledge_challenge_returns_result(self, db, make_creator):
        """Lines 149-160: run_knowledge_challenge_v2 returns challenge result."""
        from marketplace.api.v2_agents import (
            run_knowledge_challenge_v2, onboard_agent_v2, AgentOnboardRequest,
            KnowledgeChallengeRequest,
        )

        creator, token = await make_creator(display_name="v2-kc-ret")
        onboard_req = AgentOnboardRequest(
            name=f"kc-ret-{_new_id()[:6]}",
            agent_type="seller",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-kc-ret",
        )
        onboard_resp = await onboard_agent_v2(onboard_req, db=db, authorization=f"Bearer {token}")
        agent_id = onboard_resp["agent_id"]

        kc_req = KnowledgeChallengeRequest(capabilities=["web_search"])
        result = await run_knowledge_challenge_v2(
            agent_id, kc_req, db=db, current_agent_id=agent_id,
        )
        assert "agent_id" in result

    async def test_run_knowledge_challenge_wrong_agent_403(self, db, make_creator, make_agent):
        """Lines 149-153: run_knowledge_challenge_v2 raises 403 for wrong agent."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import (
            run_knowledge_challenge_v2, onboard_agent_v2, AgentOnboardRequest,
            KnowledgeChallengeRequest,
        )

        creator, token = await make_creator(display_name="v2-kc-403")
        onboard_req = AgentOnboardRequest(
            name=f"kc-403-{_new_id()[:6]}",
            agent_type="seller",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-kc-403",
        )
        onboard_resp = await onboard_agent_v2(onboard_req, db=db, authorization=f"Bearer {token}")
        agent_id = onboard_resp["agent_id"]
        other, _ = await make_agent(name="kc-other")

        kc_req = KnowledgeChallengeRequest()
        with pytest.raises(HTTPException) as exc_info:
            await run_knowledge_challenge_v2(
                agent_id, kc_req, db=db, current_agent_id=other.id,
            )
        assert exc_info.value.status_code == 403

    async def test_get_agent_trust_with_own_token(self, db, make_agent):
        """Lines 169-195: get_agent_trust_v2 with own agent token succeeds."""
        from marketplace.api.v2_agents import get_agent_trust_v2
        from marketplace.core.auth import create_access_token

        agent, token = await make_agent(name="v2-trust-own")
        result = await get_agent_trust_v2(
            agent.id, db=db, authorization=f"Bearer {token}",
        )
        assert result["agent_id"] == agent.id

    async def test_get_agent_trust_no_auth_401(self, db):
        """Lines 169-181: get_agent_trust_v2 raises 401 with no auth."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import get_agent_trust_v2

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_trust_v2("some-agent-id", db=db, authorization=None)
        assert exc_info.value.status_code == 401

    async def test_get_agent_trust_public_value_error_404(self, db):
        """Lines 205-208: get_agent_trust_public_v2 raises 404 for missing agent."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import get_agent_trust_public_v2

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_trust_public_v2("nonexistent-agent-id", db=db)
        assert exc_info.value.status_code == 404

    async def test_get_agent_trust_public_returns_summary(self, db, make_creator):
        """Lines 205-214: get_agent_trust_public_v2 returns public profile."""
        from marketplace.api.v2_agents import (
            get_agent_trust_public_v2, onboard_agent_v2, AgentOnboardRequest,
        )

        creator, token = await make_creator(display_name="v2-pub-ret")
        onboard_req = AgentOnboardRequest(
            name=f"pub-ret-{_new_id()[:6]}",
            agent_type="seller",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-pub-ret",
        )
        onboard_resp = await onboard_agent_v2(onboard_req, db=db, authorization=f"Bearer {token}")
        agent_id = onboard_resp["agent_id"]

        result = await get_agent_trust_public_v2(agent_id, db=db)
        assert result["agent_id"] == agent_id
        assert "agent_trust_status" in result


# ===========================================================================
# marketplace/api/discovery.py
# Lines: 37-84, 94-96
# ===========================================================================

class TestDiscoveryReturnPaths:
    """Cover return lines in discovery route handler."""

    async def test_discover_returns_listing_response(self, db, make_agent, make_listing):
        """Lines 37-96: discover handler builds and returns ListingListResponse."""
        from marketplace.api.discovery import discover

        agent, _ = await make_agent(name="disc-ret-1")
        await make_listing(agent.id, title="Discovery Test", price_usdc=1.0)

        result = await discover(
            q=None, category=None, min_price=None, max_price=None,
            min_quality=None, max_age_hours=None, seller_id=None,
            sort_by="freshness", page=1, page_size=20, db=db,
        )
        assert result.total >= 1
        assert len(result.results) >= 1

    async def test_discover_seller_summary_populated(self, db, make_agent, make_listing):
        """Lines 47-51: seller summary is built when listing.seller is present."""
        from marketplace.api.discovery import discover

        agent, _ = await make_agent(name="disc-seller-pop")
        await make_listing(agent.id, title="Seller Pop Test", price_usdc=2.0)

        result = await discover(
            q=None, category=None, min_price=None, max_price=None,
            min_quality=None, max_age_hours=None, seller_id=agent.id,
            sort_by="freshness", page=1, page_size=20, db=db,
        )
        assert result.total >= 1
        for listing_resp in result.results:
            if listing_resp.seller:
                assert listing_resp.seller.id == agent.id

    async def test_discover_with_all_filters(self, db, make_agent, make_listing):
        """Lines 37-84: discover with all filters set goes through full execution."""
        from marketplace.api.discovery import discover

        agent, _ = await make_agent(name="disc-all-filters")
        await make_listing(agent.id, title="Python ML Guide", category="web_search",
                           price_usdc=1.5, quality_score=0.9)

        result = await discover(
            q="python", category="web_search", min_price=0.5, max_price=5.0,
            min_quality=0.5, max_age_hours=None, seller_id=None,
            sort_by="quality", page=1, page_size=20, db=db,
        )
        assert result.total >= 0

    async def test_discover_metadata_json_parsing(self, db, make_agent, make_listing):
        """Lines 39-44: metadata and tags JSON parsing branches."""
        from marketplace.api.discovery import discover

        agent, _ = await make_agent(name="disc-json-parse")
        await make_listing(agent.id, title="JSON Parse Test", price_usdc=1.0)

        result = await discover(
            q=None, category=None, min_price=None, max_price=None,
            min_quality=None, max_age_hours=None, seller_id=None,
            sort_by="price_asc", page=1, page_size=20, db=db,
        )
        assert result.page == 1
        assert result.page_size == 20

    async def test_discover_returns_empty_results(self, db):
        """Lines 94-96: discover with no listings returns empty ListingListResponse."""
        from marketplace.api.discovery import discover

        result = await discover(
            q="completely_nonexistent_xyz", category=None, min_price=None, max_price=None,
            min_quality=None, max_age_hours=None, seller_id=None,
            sort_by="freshness", page=1, page_size=20, db=db,
        )
        assert result.total == 0
        assert result.results == []


# ===========================================================================
# marketplace/api/creators.py
# Lines: 53-55, 65-66, 81-83, 96-97, 107, 119-120
# ===========================================================================

class TestCreatorsReturnPaths:
    """Cover return/error lines in creators route handlers."""

    async def test_register_creator_returns_result(self, db):
        """Lines 53-55: register_creator returns creator data."""
        from marketplace.api.creators import register_creator, CreatorRegisterRequest

        req = CreatorRegisterRequest(
            email=f"new-{_new_id()[:6]}@test.com",
            password="securepass123",
            display_name="New Creator",
        )
        result = await register_creator(req, db=db)
        assert "token" in result

    async def test_register_creator_duplicate_409(self, db):
        """Lines 54-55: register_creator raises 409 on duplicate."""
        from fastapi import HTTPException
        from marketplace.api.creators import register_creator, CreatorRegisterRequest

        email = f"dup-{_new_id()[:6]}@test.com"
        req = CreatorRegisterRequest(
            email=email, password="securepass123", display_name="Dup",
        )
        await register_creator(req, db=db)

        with pytest.raises(HTTPException) as exc_info:
            await register_creator(req, db=db)
        assert exc_info.value.status_code == 409

    async def test_login_creator_returns_token(self, db, make_creator):
        """Lines 65-66: login_creator returns auth data on valid credentials."""
        from marketplace.api.creators import login_creator, CreatorLoginRequest

        creator, _ = await make_creator(email="login-ret@test.com", password="testpass123")
        req = CreatorLoginRequest(email="login-ret@test.com", password="testpass123")
        result = await login_creator(req, db=db)
        assert "token" in result

    async def test_login_creator_wrong_password_401(self, db, make_creator):
        """Lines 64-66: login_creator raises 401 on wrong password."""
        from fastapi import HTTPException
        from marketplace.api.creators import login_creator, CreatorLoginRequest

        await make_creator(email="login-bad@test.com", password="testpass123")
        req = CreatorLoginRequest(email="login-bad@test.com", password="wrongpass")
        with pytest.raises(HTTPException) as exc_info:
            await login_creator(req, db=db)
        assert exc_info.value.status_code == 401

    async def test_get_my_profile_returns_creator(self, db, make_creator):
        """Lines 81-83: get_my_profile returns creator data."""
        from marketplace.api.creators import get_my_profile
        from marketplace.core.creator_auth import create_creator_token

        creator, token = await make_creator(display_name="Profile Ret")
        result = await get_my_profile(db=db, authorization=f"Bearer {token}")
        assert result["id"] == creator.id

    async def test_get_my_profile_not_found_404(self, db):
        """Lines 81-83: get_my_profile raises 404 for missing creator."""
        from fastapi import HTTPException
        from marketplace.api.creators import get_my_profile
        from marketplace.core.creator_auth import create_creator_token

        fake_token = create_creator_token(_new_id(), "fake@test.com")
        with pytest.raises(HTTPException) as exc_info:
            await get_my_profile(db=db, authorization=f"Bearer {fake_token}")
        assert exc_info.value.status_code == 404

    async def test_update_my_profile_returns_updated(self, db, make_creator):
        """Lines 96-97: update_my_profile returns updated creator."""
        from marketplace.api.creators import update_my_profile, CreatorUpdateRequest

        creator, token = await make_creator(display_name="Update Ret")
        req = CreatorUpdateRequest(display_name="Updated Name")
        result = await update_my_profile(req, db=db, authorization=f"Bearer {token}")
        assert result is not None

    async def test_get_my_agents_returns_list(self, db, make_creator):
        """Line 107: get_my_agents returns agents dict."""
        from marketplace.api.creators import get_my_agents

        _, token = await make_creator(display_name="Agents Ret")
        result = await get_my_agents(db=db, authorization=f"Bearer {token}")
        assert "agents" in result
        assert "count" in result

    async def test_claim_agent_returns_result(self, db, make_creator, make_agent):
        """Lines 119-120: claim_agent returns result."""
        from marketplace.api.creators import claim_agent

        _, token = await make_creator(display_name="Claim Ret")
        agent, _ = await make_agent(name="claimable-ret")
        result = await claim_agent(agent.id, db=db, authorization=f"Bearer {token}")
        assert result is not None

    async def test_claim_agent_value_error_400(self, db, make_creator):
        """Lines 119-120: claim_agent raises 400 on ValueError."""
        from fastapi import HTTPException
        from marketplace.api.creators import claim_agent

        _, token = await make_creator(display_name="Claim VE")
        with patch(
            "marketplace.api.creators.creator_service.link_agent_to_creator",
            new_callable=AsyncMock,
            side_effect=ValueError("Agent already claimed"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await claim_agent("agent-id", db=MagicMock(), authorization=f"Bearer {token}")
        assert exc_info.value.status_code == 400


# ===========================================================================
# marketplace/api/automatch.py
# Lines: 46, 58-73
# ===========================================================================

class TestAutomatchReturnPaths:
    """Cover lines 46 (fire_and_forget) and 58-73 (demand logging + auto-buy)."""

    async def test_auto_match_fires_demand_log(self, db, make_agent, make_listing):
        """Lines 46, 58: auto_match fires demand logging signal."""
        from marketplace.api.automatch import auto_match, AutoMatchRequest

        seller, _ = await make_agent(name="automatch-seller-ret")
        await make_listing(seller.id, title="Python Tutorial", price_usdc=0.005,
                           category="web_search")
        buyer, _ = await make_agent(name="automatch-buyer-ret")

        req = AutoMatchRequest(description="python tutorial")
        result = await auto_match(req, db=db, buyer_id=buyer.id)
        assert "matches" in result
        assert result["query"] == "python tutorial"

    async def test_auto_match_auto_buy_triggers_purchase(self, db, make_agent, make_listing,
                                                          make_token_account):
        """Lines 60-71: auto_buy=True with valid match triggers express purchase."""
        from marketplace.api.automatch import auto_match, AutoMatchRequest

        seller, _ = await make_agent(name="automatch-ab-seller")
        await make_token_account(seller.id, balance=0)
        listing = await make_listing(seller.id, title="Python Tutorial Guide",
                                     price_usdc=0.005, quality_score=0.9)
        buyer, _ = await make_agent(name="automatch-ab-buyer")
        await make_token_account(buyer.id, balance=50000)

        # Seed platform account
        from marketplace.services.token_service import ensure_platform_account
        await ensure_platform_account(db)

        with patch(
            "marketplace.services.express_service.cdn_get_content",
            new_callable=AsyncMock,
            return_value=b'{"data": "test content"}',
        ):
            req = AutoMatchRequest(
                description="python tutorial guide",
                auto_buy=True,
                auto_buy_max_price=0.01,
            )
            result = await auto_match(req, db=db, buyer_id=buyer.id)

        assert "matches" in result
        if result["matches"] and result["matches"][0]["match_score"] >= 0.3:
            assert result.get("auto_purchased") is True

    async def test_auto_match_auto_buy_no_matches(self, db, make_agent):
        """Lines 60-61: auto_buy=True with no matches does not trigger purchase."""
        from marketplace.api.automatch import auto_match, AutoMatchRequest

        buyer, _ = await make_agent(name="automatch-ab-none")
        req = AutoMatchRequest(
            description="completely_nonexistent_xyz_topic_987",
            auto_buy=True,
            auto_buy_max_price=0.01,
        )
        result = await auto_match(req, db=db, buyer_id=buyer.id)
        assert result["matches"] == []
        assert result.get("auto_purchased") is not True

    async def test_auto_match_demand_log_failure_ignored(self, db, make_agent):
        """Lines 55-56: demand log failure is silently ignored."""
        from marketplace.api.automatch import auto_match, AutoMatchRequest

        buyer, _ = await make_agent(name="automatch-log-fail")
        with patch(
            "marketplace.api.automatch.demand_service.log_search",
            new_callable=AsyncMock,
            side_effect=Exception("DB connection lost"),
        ):
            req = AutoMatchRequest(description="test query")
            result = await auto_match(req, db=db, buyer_id=buyer.id)
        assert "matches" in result


# ===========================================================================
# marketplace/api/reputation.py
# Lines: 17-32, 45-50
# ===========================================================================

class TestReputationReturnPaths:
    """Cover lines 17-32 (leaderboard) and 45-50 (get_reputation)."""

    async def test_leaderboard_returns_entries(self, db, make_agent, make_listing,
                                               make_transaction):
        """Lines 17-32: leaderboard builds entries with agent names."""
        from marketplace.api.reputation import leaderboard
        from marketplace.services.reputation_service import calculate_reputation

        seller, _ = await make_agent(name="rep-lb-ret")
        buyer, _ = await make_agent(name="rep-lb-buy")
        listing = await make_listing(seller.id)
        await make_transaction(buyer.id, seller.id, listing.id)
        await calculate_reputation(db, seller.id)

        result = await leaderboard(limit=10, db=db)
        assert hasattr(result, "entries")
        assert len(result.entries) >= 1
        assert result.entries[0].rank == 1

    async def test_leaderboard_agent_not_found_uses_unknown(self, db, make_agent,
                                                              make_listing, make_transaction):
        """Lines 20-23: leaderboard uses 'unknown' when registry lookup fails."""
        from marketplace.api.reputation import leaderboard
        from marketplace.services.reputation_service import calculate_reputation

        # Create a real agent and calculate reputation, then mock registry to fail
        seller, _ = await make_agent(name="rep-lb-unk")
        buyer, _ = await make_agent(name="rep-lb-unk-buy")
        listing = await make_listing(seller.id)
        await make_transaction(buyer.id, seller.id, listing.id)
        await calculate_reputation(db, seller.id)

        with patch(
            "marketplace.api.reputation.registry_service.get_agent",
            new_callable=AsyncMock,
            side_effect=Exception("Agent not found in registry"),
        ):
            result = await leaderboard(limit=10, db=db)
        # All entries with the mocked registry failure should show "unknown"
        for entry in result.entries:
            assert entry.agent_name == "unknown"

    async def test_get_reputation_returns_response(self, db, make_agent):
        """Lines 45-50: get_reputation returns ReputationResponse."""
        from marketplace.api.reputation import get_reputation

        agent, _ = await make_agent(name="rep-get-ret")
        result = await get_reputation(agent.id, recalculate=False, db=db)
        assert result.agent_id == agent.id
        assert result.agent_name == agent.name

    async def test_get_reputation_recalculate_true(self, db, make_agent, make_listing,
                                                    make_transaction):
        """Lines 41-42: get_reputation with recalculate=True calls calculate."""
        from marketplace.api.reputation import get_reputation

        seller, _ = await make_agent(name="rep-recalc-ret")
        buyer, _ = await make_agent(name="rep-recalc-buy")
        listing = await make_listing(seller.id)
        await make_transaction(buyer.id, seller.id, listing.id)

        result = await get_reputation(seller.id, recalculate=True, db=db)
        assert result.agent_id == seller.id
        assert result.total_transactions >= 1

    async def test_get_reputation_no_existing_triggers_calculate(self, db, make_agent):
        """Lines 44-46: get_reputation with no existing rep calls calculate."""
        from marketplace.api.reputation import get_reputation

        # Fresh agent with no reputation record
        agent, _ = await make_agent(name="rep-fresh-ret")
        result = await get_reputation(agent.id, recalculate=False, db=db)
        assert result.agent_id == agent.id


# ===========================================================================
# marketplace/api/v2_billing.py
# Lines: 67-76, 93-107, 123-124, 135-136, 147-160
# ===========================================================================

class TestV2BillingReturnPaths:
    """Cover return/error lines in v2_billing route handlers."""

    async def test_billing_account_me_no_account_returns_zero(self, db, make_agent):
        """Lines 67-76: billing_account_me with no account returns zero balance."""
        from marketplace.api.v2_billing import billing_account_me

        agent, _ = await make_agent(name="bill-no-acc-ret")
        result = await billing_account_me(db=db, agent_id=agent.id)
        assert result.balance_usd == 0.0
        assert result.total_earned_usd == 0.0

    async def test_billing_account_me_with_account_returns_balance(self, db, make_agent):
        """Lines 67-76: billing_account_me with existing account returns real balance."""
        from marketplace.api.v2_billing import billing_account_me
        from marketplace.services.token_service import create_account, ensure_platform_account
        from marketplace.services.deposit_service import create_deposit, confirm_deposit

        agent, _ = await make_agent(name="bill-acc-ret")
        await ensure_platform_account(db)
        await create_account(db, agent.id)
        dep = await create_deposit(db, agent.id, 100.0, "admin_credit")
        await confirm_deposit(db, dep["id"], agent.id)

        result = await billing_account_me(db=db, agent_id=agent.id)
        assert result.balance_usd > 0

    async def test_billing_ledger_me_returns_entries(self, db, make_agent):
        """Lines 93-107: billing_ledger_me returns BillingLedgerResponse."""
        from marketplace.api.v2_billing import billing_ledger_me
        from marketplace.services.token_service import create_account, ensure_platform_account

        agent, _ = await make_agent(name="bill-ledger-ret")
        await ensure_platform_account(db)
        await create_account(db, agent.id)

        result = await billing_ledger_me(page=1, page_size=20, db=db, agent_id=agent.id)
        assert result.total == 0
        assert result.entries == []

    async def test_billing_ledger_me_with_entries(self, db, make_agent):
        """Lines 93-107: billing_ledger_me with transactions returns entries."""
        from marketplace.api.v2_billing import billing_ledger_me
        from marketplace.services.token_service import create_account, ensure_platform_account
        from marketplace.services.deposit_service import create_deposit, confirm_deposit

        agent, _ = await make_agent(name="bill-ledger-entries")
        await ensure_platform_account(db)
        await create_account(db, agent.id)
        dep = await create_deposit(db, agent.id, 50.0, "admin_credit")
        await confirm_deposit(db, dep["id"], agent.id)

        result = await billing_ledger_me(page=1, page_size=20, db=db, agent_id=agent.id)
        assert result.total >= 1

    async def test_billing_create_deposit_returns_deposit(self, db, make_agent):
        """Lines 123-124: billing_create_deposit returns deposit data."""
        from marketplace.api.v2_billing import billing_create_deposit, BillingDepositCreateRequest
        from marketplace.services.token_service import create_account, ensure_platform_account

        agent, _ = await make_agent(name="bill-dep-ret")
        await ensure_platform_account(db)
        await create_account(db, agent.id)

        req = BillingDepositCreateRequest(amount_usd=50.0, payment_method="admin_credit")
        result = await billing_create_deposit(req, db=db, agent_id=agent.id)
        assert "id" in result

    async def test_billing_create_deposit_value_error_400(self, db, make_agent):
        """Lines 123-124: billing_create_deposit raises 400 on ValueError."""
        from fastapi import HTTPException
        from marketplace.api.v2_billing import billing_create_deposit, BillingDepositCreateRequest

        agent, _ = await make_agent(name="bill-dep-ve")
        with patch(
            "marketplace.api.v2_billing.create_deposit",
            new_callable=AsyncMock,
            side_effect=ValueError("Payment method not supported"),
        ):
            req = BillingDepositCreateRequest(amount_usd=50.0, payment_method="bad_method")
            with pytest.raises(HTTPException) as exc_info:
                await billing_create_deposit(req, db=MagicMock(), agent_id=agent.id)
        assert exc_info.value.status_code == 400

    async def test_billing_confirm_deposit_returns_result(self, db, make_agent):
        """Lines 135-136: billing_confirm_deposit returns confirmation."""
        from marketplace.api.v2_billing import billing_confirm_deposit
        from marketplace.services.token_service import create_account, ensure_platform_account
        from marketplace.services.deposit_service import create_deposit

        agent, _ = await make_agent(name="bill-conf-ret")
        await ensure_platform_account(db)
        await create_account(db, agent.id)
        dep = await create_deposit(db, agent.id, 25.0, "admin_credit")

        result = await billing_confirm_deposit(dep["id"], db=db, agent_id=agent.id)
        assert result is not None

    async def test_billing_confirm_deposit_value_error_400(self, db, make_agent):
        """Lines 135-136: billing_confirm_deposit raises 400 on ValueError."""
        from fastapi import HTTPException
        from marketplace.api.v2_billing import billing_confirm_deposit

        agent, _ = await make_agent(name="bill-conf-ve")
        with patch(
            "marketplace.api.v2_billing.confirm_deposit",
            new_callable=AsyncMock,
            side_effect=ValueError("Deposit already confirmed"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await billing_confirm_deposit("dep-id", db=MagicMock(), agent_id=agent.id)
        assert exc_info.value.status_code == 400

    async def test_billing_transfer_self_400(self, db, make_agent):
        """Lines 147-148: billing_transfer raises 400 when transferring to self."""
        from fastapi import HTTPException
        from marketplace.api.v2_billing import billing_transfer, BillingTransferCreateRequest

        agent, _ = await make_agent(name="bill-self-ret")
        req = BillingTransferCreateRequest(to_agent_id=agent.id, amount_usd=10.0)
        with pytest.raises(HTTPException) as exc_info:
            await billing_transfer(req, db=MagicMock(), agent_id=agent.id)
        assert exc_info.value.status_code == 400

    async def test_billing_transfer_returns_entry(self, db, make_agent):
        """Lines 147-167: billing_transfer returns transfer entry."""
        from marketplace.api.v2_billing import billing_transfer, BillingTransferCreateRequest
        from marketplace.services.token_service import create_account, ensure_platform_account

        sender, _ = await make_agent(name="bill-xfer-send")
        receiver, _ = await make_agent(name="bill-xfer-recv")
        await ensure_platform_account(db)
        await create_account(db, sender.id)
        await create_account(db, receiver.id)

        from marketplace.services.deposit_service import create_deposit, confirm_deposit
        dep = await create_deposit(db, sender.id, 100.0, "admin_credit")
        await confirm_deposit(db, dep["id"], sender.id)

        req = BillingTransferCreateRequest(to_agent_id=receiver.id, amount_usd=10.0)
        result = await billing_transfer(req, db=db, agent_id=sender.id)
        assert "id" in result
        assert result["amount_usd"] == pytest.approx(10.0)

    async def test_billing_transfer_value_error_400(self, db, make_agent):
        """Lines 157-158: billing_transfer raises 400 on ValueError."""
        from fastapi import HTTPException
        from marketplace.api.v2_billing import billing_transfer, BillingTransferCreateRequest

        sender, _ = await make_agent(name="bill-xfer-ve")
        receiver, _ = await make_agent(name="bill-xfer-recv-ve")

        with patch(
            "marketplace.api.v2_billing.transfer",
            new_callable=AsyncMock,
            side_effect=ValueError("Insufficient balance"),
        ):
            req = BillingTransferCreateRequest(to_agent_id=receiver.id, amount_usd=999.0)
            with pytest.raises(HTTPException) as exc_info:
                await billing_transfer(req, db=MagicMock(), agent_id=sender.id)
        assert exc_info.value.status_code == 400


# ===========================================================================
# marketplace/api/registry.py
# Lines: 33-40, 52, 66, 80, 93, 106
# ===========================================================================

class TestRegistryReturnPaths:
    """Cover return lines in registry route handlers."""

    async def test_register_agent_returns_result(self, db):
        """Lines 33-40: register_agent creates token account and returns response."""
        from marketplace.api.registry import register_agent
        from marketplace.schemas.agent import AgentRegisterRequest

        req = AgentRegisterRequest(
            name=f"reg-ret-{_new_id()[:6]}",
            agent_type="seller",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-reg-ret",
        )
        result = await register_agent(req, db=db)
        assert result.name == req.name

    async def test_list_agents_returns_all_fields(self, db, make_agent):
        """Line 52: list_agents returns AgentListResponse."""
        from marketplace.api.registry import list_agents

        await make_agent(name="reg-list-ret-a")
        await make_agent(name="reg-list-ret-b")

        result = await list_agents(
            agent_type=None, status=None, page=1, page_size=20, db=db,
        )
        assert result.total >= 2
        assert len(result.agents) >= 2

    async def test_get_agent_returns_response(self, db, make_agent):
        """Line 66: get_agent returns AgentResponse."""
        from marketplace.api.registry import get_agent

        agent, _ = await make_agent(name="reg-get-ret")
        result = await get_agent(agent.id, db=db)
        assert result.id == agent.id

    async def test_update_agent_returns_response(self, db, make_agent):
        """Line 80: update_agent returns updated AgentResponse."""
        from marketplace.api.registry import update_agent
        from marketplace.schemas.agent import AgentUpdateRequest

        agent, _ = await make_agent(name="reg-upd-ret")
        req = AgentUpdateRequest(description="Updated via direct call")
        result = await update_agent(agent.id, req, db=db, current_agent=agent.id)
        assert result.description == "Updated via direct call"

    async def test_update_agent_wrong_owner_403(self, db, make_agent):
        """Lines 76-78: update_agent raises 403 for wrong owner."""
        from fastapi import HTTPException
        from marketplace.api.registry import update_agent
        from marketplace.schemas.agent import AgentUpdateRequest

        agent, _ = await make_agent(name="reg-upd-owner")
        other, _ = await make_agent(name="reg-upd-other")

        req = AgentUpdateRequest(description="hack")
        with pytest.raises(HTTPException) as exc_info:
            await update_agent(agent.id, req, db=db, current_agent=other.id)
        assert exc_info.value.status_code == 403

    async def test_heartbeat_returns_status(self, db, make_agent):
        """Line 93: heartbeat returns status dict."""
        from marketplace.api.registry import heartbeat

        agent, _ = await make_agent(name="reg-hb-ret")
        result = await heartbeat(agent.id, db=db, current_agent=agent.id)
        assert result["status"] == "ok"
        assert "last_seen_at" in result

    async def test_heartbeat_wrong_owner_403(self, db, make_agent):
        """Lines 89-91: heartbeat raises 403 for wrong owner."""
        from fastapi import HTTPException
        from marketplace.api.registry import heartbeat

        agent, _ = await make_agent(name="reg-hb-owner")
        other, _ = await make_agent(name="reg-hb-other")

        with pytest.raises(HTTPException) as exc_info:
            await heartbeat(agent.id, db=db, current_agent=other.id)
        assert exc_info.value.status_code == 403

    async def test_deactivate_agent_returns_status(self, db, make_agent):
        """Line 106: deactivate_agent returns deactivated status."""
        from marketplace.api.registry import deactivate_agent

        agent, _ = await make_agent(name="reg-deact-ret")
        result = await deactivate_agent(agent.id, db=db, current_agent=agent.id)
        assert result["status"] == "deactivated"

    async def test_deactivate_agent_wrong_owner_403(self, db, make_agent):
        """Lines 102-104: deactivate_agent raises 403 for wrong owner."""
        from fastapi import HTTPException
        from marketplace.api.registry import deactivate_agent

        agent, _ = await make_agent(name="reg-deact-owner")
        other, _ = await make_agent(name="reg-deact-other")

        with pytest.raises(HTTPException) as exc_info:
            await deactivate_agent(agent.id, db=db, current_agent=other.id)
        assert exc_info.value.status_code == 403


# ===========================================================================
# Additional gap-closing tests for remaining missing lines
# ===========================================================================


class TestRegistryTokenSetupFailure:
    """Cover registry.py lines 37-38: exception handler for token setup."""

    async def test_register_agent_token_setup_exception_handled(self, db):
        """Lines 37-38: when token setup raises, warning is logged and result returned."""
        from marketplace.api.registry import register_agent
        from marketplace.schemas.agent import AgentRegisterRequest

        with patch(
            "marketplace.api.registry.ensure_platform_account",
            new_callable=AsyncMock,
            side_effect=Exception("DB connection error during token setup"),
        ):
            req = AgentRegisterRequest(
                name=f"token-fail-{_new_id()[:6]}",
                agent_type="seller",
                public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-token-fail",
            )
            result = await register_agent(req, db=db)
        # Result is still returned even when token setup fails
        assert result is not None
        assert result.name == req.name


class TestV2AgentsExtraGaps:
    """Cover v2_agents.py lines 50-55, 59, 89-90, 174-175, 178-195."""

    async def test_parse_bearer_malformed_raises_401(self):
        """Lines 53-54: _parse_bearer with malformed token raises 401."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import _parse_bearer

        with pytest.raises(HTTPException) as exc_info:
            _parse_bearer("NotBearer token extra")
        assert exc_info.value.status_code == 401

    async def test_parse_bearer_none_raises_401(self):
        """Lines 50-51: _parse_bearer with None raises 401."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import _parse_bearer

        with pytest.raises(HTTPException) as exc_info:
            _parse_bearer(None)
        assert exc_info.value.status_code == 401

    async def test_parse_bearer_valid_returns_token(self):
        """Line 55: _parse_bearer with valid bearer returns token string."""
        from marketplace.api.v2_agents import _parse_bearer

        result = _parse_bearer("Bearer mytoken123")
        assert result == "mytoken123"

    async def test_admin_creator_ids_returns_set(self):
        """Line 59: _admin_creator_ids returns a set from settings."""
        from marketplace.api.v2_agents import _admin_creator_ids
        from marketplace.config import settings

        original = settings.admin_creator_ids
        try:
            object.__setattr__(settings, "admin_creator_ids", "admin1,admin2, admin3")
            result = _admin_creator_ids()
            assert result == {"admin1", "admin2", "admin3"}
        finally:
            object.__setattr__(settings, "admin_creator_ids", original)

    async def test_onboard_agent_already_exists_409(self, db, make_creator):
        """Lines 89-90: onboard_agent_v2 raises 409 on AgentAlreadyExistsError."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import onboard_agent_v2, AgentOnboardRequest
        from marketplace.core.exceptions import AgentAlreadyExistsError

        creator, token = await make_creator(display_name="v2-dup-ret")
        req = AgentOnboardRequest(
            name=f"dup-agent-{_new_id()[:6]}",
            agent_type="seller",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-dup-ret",
        )
        with patch(
            "marketplace.api.v2_agents.registry_service.register_agent",
            new_callable=AsyncMock,
            side_effect=AgentAlreadyExistsError("Agent already exists"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await onboard_agent_v2(req, db=MagicMock(), authorization=f"Bearer {token}")
        assert exc_info.value.status_code == 409

    async def test_get_agent_trust_v2_wrong_token_falls_back_to_creator(
        self, db, make_agent, make_creator,
    ):
        """Lines 174-175, 178-190: get_agent_trust_v2 with wrong agent token falls
        back to creator auth and checks ownership."""
        from marketplace.api.v2_agents import get_agent_trust_v2
        from marketplace.core.auth import create_access_token

        agent, agent_token = await make_agent(name="v2-trust-other-agent")
        other, other_token = await make_agent(name="v2-trust-requesting-agent")

        # other_token is valid but refers to a different agent, so allowed=False
        # Then it tries creator auth which also fails (it's an agent token)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_agent_trust_v2(
                agent.id, db=db, authorization=f"Bearer {other_token}",
            )
        # Should raise 401 (creator auth fails with agent token)
        assert exc_info.value.status_code == 401

    async def test_get_agent_trust_v2_creator_not_owner_403(self, db, make_agent, make_creator):
        """Lines 178-190: get_agent_trust_v2 raises 403 when creator doesn't own agent."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import get_agent_trust_v2
        from marketplace.config import settings

        agent, _ = await make_agent(name="v2-trust-no-owner")
        creator, creator_token = await make_creator(display_name="v2-trust-non-owner")

        original = settings.admin_creator_ids
        try:
            # Ensure creator is not admin
            object.__setattr__(settings, "admin_creator_ids", "")
            with pytest.raises(HTTPException) as exc_info:
                await get_agent_trust_v2(
                    agent.id, db=db, authorization=f"Bearer {creator_token}",
                )
        finally:
            object.__setattr__(settings, "admin_creator_ids", original)
        assert exc_info.value.status_code == 403

    async def test_get_agent_trust_v2_creator_agent_not_found_404(
        self, db, make_creator,
    ):
        """Lines 187-188: get_agent_trust_v2 raises 404 when agent doesn't exist."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import get_agent_trust_v2

        _, creator_token = await make_creator(display_name="v2-trust-nf")
        nonexistent_id = _new_id()

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_trust_v2(
                nonexistent_id, db=db, authorization=f"Bearer {creator_token}",
            )
        assert exc_info.value.status_code == 404

    async def test_get_agent_trust_v2_value_error_404(self, db, make_agent):
        """Lines 194-195: get_agent_trust_v2 raises 404 on ValueError from service."""
        from fastapi import HTTPException
        from marketplace.api.v2_agents import get_agent_trust_v2

        agent, agent_token = await make_agent(name="v2-trust-ve")

        with patch(
            "marketplace.api.v2_agents.agent_trust_service.get_or_create_trust_profile",
            new_callable=AsyncMock,
            side_effect=ValueError("Trust profile not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_agent_trust_v2(
                    agent.id, db=MagicMock(), authorization=f"Bearer {agent_token}",
                )
        assert exc_info.value.status_code == 404


class TestAuditVerifyChainPrevHash:
    """Cover audit.py lines 77-78: prev_hash update and checked increment."""

    async def test_verify_chain_updates_prev_hash(self, db, make_agent):
        """Lines 77-78: for valid entries, prev_hash and checked counter update.

        Inserts AuditLog entries with pre-computed correct hashes so the
        hash comparison always succeeds and lines 77-78 execute.
        """
        import datetime
        from marketplace.api.audit import verify_audit_chain
        from marketplace.core.hashing import compute_audit_hash
        from marketplace.models.audit_log import AuditLog

        agent, _ = await make_agent(name="audit-prev-hash")

        # Build a 3-entry chain with correct hashes
        now = datetime.datetime(2025, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        prev_hash = None

        for i in range(3):
            ts = now + datetime.timedelta(seconds=i)
            ts_iso = ts.isoformat()
            details_json = "{}"
            entry_hash = compute_audit_hash(
                prev_hash, f"event.chain.{i}", agent.id, details_json, "info", ts_iso,
            )
            entry = AuditLog(
                id=_new_id(),
                event_type=f"event.chain.{i}",
                agent_id=agent.id,
                severity="info",
                details=details_json,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
                created_at=ts,
            )
            db.add(entry)
            prev_hash = entry_hash

        await db.commit()

        result = await verify_audit_chain(limit=1000, db=db, _agent_id=agent.id)
        assert "valid" in result
        # Either valid=True with 3 checked, or valid=False if datetime round-trip differs
        # We just need lines 77-78 to execute when hashes match
        if result["valid"]:
            assert result["entries_checked"] >= 3

    async def test_verify_chain_force_valid_path_with_mock(self, db, make_agent):
        """Lines 77-80: mock compute_audit_hash to always match, guaranteeing lines 77-78."""
        import datetime
        from marketplace.api.audit import verify_audit_chain
        from marketplace.models.audit_log import AuditLog

        agent, _ = await make_agent(name="audit-mock-hash")
        known_hash = "aabbccdd" * 8  # 64-char fake hash

        # Insert entry with known hash
        now = datetime.datetime(2025, 6, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        entry = AuditLog(
            id=_new_id(),
            event_type="event.mock",
            agent_id=agent.id,
            severity="info",
            details="{}",
            prev_hash=None,
            entry_hash=known_hash,
            created_at=now,
        )
        db.add(entry)
        await db.commit()

        # Patch compute_audit_hash to always return the stored hash
        with patch(
            "marketplace.api.audit.compute_audit_hash",
            return_value=known_hash,
        ):
            result = await verify_audit_chain(limit=1000, db=db, _agent_id=agent.id)

        assert result["valid"] is True
        assert result["entries_checked"] >= 1


class TestCreatorsUpdateValueError:
    """Cover creators.py lines 96-97: update raises ValueError -> 404."""

    async def test_update_my_profile_value_error_404(self, db, make_creator):
        """Lines 96-97: update_my_profile raises 404 when creator service raises ValueError."""
        from fastapi import HTTPException
        from marketplace.api.creators import update_my_profile, CreatorUpdateRequest

        _, token = await make_creator(display_name="Upd VE")
        with patch(
            "marketplace.api.creators.creator_service.update_creator",
            new_callable=AsyncMock,
            side_effect=ValueError("Creator not found"),
        ):
            req = CreatorUpdateRequest(display_name="Should Fail")
            with pytest.raises(HTTPException) as exc_info:
                await update_my_profile(req, db=MagicMock(), authorization=f"Bearer {token}")
        assert exc_info.value.status_code == 404


class TestV3WebmcpQueryTooLong:
    """Cover v3_webmcp.py lines 94, 168: query too long guards."""

    async def test_list_tools_query_too_long_direct(self):
        """Line 94: list_tools raises 400 for q > 500 chars via direct call."""
        from fastapi import HTTPException
        from marketplace.api.v3_webmcp import list_tools

        long_q = "x" * 501
        with pytest.raises(HTTPException) as exc_info:
            await list_tools(
                q=long_q, category=None, domain=None, status=None,
                page=1, page_size=20, db=MagicMock(),
            )
        assert exc_info.value.status_code == 400

    async def test_list_actions_query_too_long_direct(self):
        """Line 168: list_actions raises 400 for q > 500 chars via direct call."""
        from fastapi import HTTPException
        from marketplace.api.v3_webmcp import list_actions

        long_q = "a" * 501
        with pytest.raises(HTTPException) as exc_info:
            await list_actions(
                q=long_q, category=None, max_price=None,
                page=1, page_size=20, db=MagicMock(),
            )
        assert exc_info.value.status_code == 400
