"""Unit tests for action_executor — execute, get, list, cancel executions.

Covers the full execution lifecycle (pending -> executing -> completed),
consent check failure, domain lock violation, get/list with filters,
and cancel with authorization checks.
"""

import json
import uuid
from decimal import Decimal

import pytest

from marketplace.models.agent import RegisteredAgent
from marketplace.models.creator import Creator
from marketplace.services import webmcp_service
from marketplace.services.action_executor import (
    cancel_execution,
    execute_action,
    get_execution,
    list_executions,
)
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_creator(db) -> Creator:
    creator = Creator(
        id=_new_id(),
        email=f"creator-{uuid.uuid4().hex[:8]}@test.com",
        password_hash="hashed_password",
        display_name="Test Creator",
    )
    db.add(creator)
    await db.commit()
    await db.refresh(creator)
    return creator


async def _create_agent(db, name=None) -> RegisteredAgent:
    agent = RegisteredAgent(
        id=_new_id(),
        name=name or f"test-agent-{uuid.uuid4().hex[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test_key",
        status="active",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def _setup_tool_and_listing(db, creator, seller, **listing_overrides):
    """Register a tool, approve it, and create a listing. Returns (tool_dict, listing_dict)."""
    tool = await webmcp_service.register_tool(
        db,
        creator_id=creator.id,
        name=f"tool-{uuid.uuid4().hex[:8]}",
        domain="example.com",
        endpoint_url="https://example.com/.well-known/mcp",
        category="shopping",
        description="Test tool",
        input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
    )
    await webmcp_service.approve_tool(db, tool["id"], creator.id)

    listing_defaults = {
        "tool_id": tool["id"],
        "seller_id": seller.id,
        "title": f"listing-{uuid.uuid4().hex[:8]}",
        "price_per_execution": 0.05,
        "requires_consent": True,
        "domain_lock": [],
    }
    listing_defaults.update(listing_overrides)
    listing = await webmcp_service.create_action_listing(db, **listing_defaults)

    return tool, listing


# ---------------------------------------------------------------------------
# execute_action — full lifecycle
# ---------------------------------------------------------------------------

class TestExecuteAction:
    """Test action_executor.execute_action."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_pending_to_completed(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            result = await execute_action(
                db,
                listing_id=listing["id"],
                buyer_id=buyer.id,
                parameters={"q": "laptop"},
                consent=True,
            )

            assert result["status"] == "completed"
            assert result["buyer_id"] == buyer.id
            assert result["tool_id"] == tool["id"]
            assert result["action_listing_id"] == listing["id"]
            assert result["amount_usdc"] == 0.05
            assert result["proof_of_execution"] is not None
            assert result["proof_verified"] is True
            assert result["payment_status"] == "captured"
            assert result["execution_time_ms"] is not None
            assert result["started_at"] is not None
            assert result["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_result_contains_tool_output(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            result = await execute_action(
                db,
                listing_id=listing["id"],
                buyer_id=buyer.id,
                parameters={"q": "test"},
                consent=True,
            )

            # Simulated execution returns structured data
            assert result["result"]["status"] == "success"
            assert result["result"]["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_execution_updates_tool_stats(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            await execute_action(
                db,
                listing_id=listing["id"],
                buyer_id=buyer.id,
                parameters={"q": "test"},
                consent=True,
            )

            # Re-fetch the tool to check updated stats
            updated_tool = await webmcp_service.get_tool(db, tool["id"])
            assert updated_tool["execution_count"] == 1
            assert updated_tool["avg_execution_time_ms"] >= 0


# ---------------------------------------------------------------------------
# execute_action — consent check
# ---------------------------------------------------------------------------

class TestExecuteActionConsent:
    """Test consent requirement enforcement."""

    @pytest.mark.asyncio
    async def test_consent_required_but_not_given(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(
                db, creator, seller, requires_consent=True,
            )

            with pytest.raises(ValueError, match="consent required"):
                await execute_action(
                    db,
                    listing_id=listing["id"],
                    buyer_id=buyer.id,
                    parameters={"q": "test"},
                    consent=False,
                )

    @pytest.mark.asyncio
    async def test_no_consent_required_succeeds_without_consent(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(
                db, creator, seller, requires_consent=False,
            )

            result = await execute_action(
                db,
                listing_id=listing["id"],
                buyer_id=buyer.id,
                parameters={"q": "test"},
                consent=False,
            )

            assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# execute_action — domain lock
# ---------------------------------------------------------------------------

class TestExecuteActionDomainLock:
    """Test domain lock validation."""

    @pytest.mark.asyncio
    async def test_domain_lock_violation_raises(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)

            # Tool domain is example.com, but listing locks to only amazon.com
            tool, listing = await _setup_tool_and_listing(
                db, creator, seller, domain_lock=["amazon.com"],
            )

            with pytest.raises(ValueError, match="not in allowed domains"):
                await execute_action(
                    db,
                    listing_id=listing["id"],
                    buyer_id=buyer.id,
                    parameters={"q": "test"},
                    consent=True,
                )

    @pytest.mark.asyncio
    async def test_domain_lock_allows_matching_domain(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)

            # Tool domain is example.com, listing locks to example.com
            tool, listing = await _setup_tool_and_listing(
                db, creator, seller, domain_lock=["example.com"],
            )

            result = await execute_action(
                db,
                listing_id=listing["id"],
                buyer_id=buyer.id,
                parameters={"q": "test"},
                consent=True,
            )

            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_empty_domain_lock_allows_any(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)

            tool, listing = await _setup_tool_and_listing(
                db, creator, seller, domain_lock=[],
            )

            result = await execute_action(
                db,
                listing_id=listing["id"],
                buyer_id=buyer.id,
                parameters={"q": "test"},
                consent=True,
            )

            assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# execute_action — error cases
# ---------------------------------------------------------------------------

class TestExecuteActionErrors:
    """Test error handling in execute_action."""

    @pytest.mark.asyncio
    async def test_nonexistent_listing_raises(self):
        async with TestSession() as db:
            buyer = await _create_agent(db)

            with pytest.raises(ValueError, match="not found"):
                await execute_action(
                    db,
                    listing_id="nonexistent-id",
                    buyer_id=buyer.id,
                    parameters={},
                    consent=True,
                )


# ---------------------------------------------------------------------------
# get_execution
# ---------------------------------------------------------------------------

class TestGetExecution:
    """Test action_executor.get_execution."""

    @pytest.mark.asyncio
    async def test_get_existing_execution_returns_dict(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            executed = await execute_action(
                db,
                listing_id=listing["id"],
                buyer_id=buyer.id,
                parameters={"q": "test"},
                consent=True,
            )

            result = await get_execution(db, executed["id"])

            assert result is not None
            assert result["id"] == executed["id"]
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_missing_execution_returns_none(self):
        async with TestSession() as db:
            result = await get_execution(db, "nonexistent-id")

            assert result is None


# ---------------------------------------------------------------------------
# list_executions
# ---------------------------------------------------------------------------

class TestListExecutions:
    """Test action_executor.list_executions with filters."""

    @pytest.mark.asyncio
    async def test_list_all_executions(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            await execute_action(
                db, listing_id=listing["id"], buyer_id=buyer.id,
                parameters={"q": "a"}, consent=True,
            )
            await execute_action(
                db, listing_id=listing["id"], buyer_id=buyer.id,
                parameters={"q": "b"}, consent=True,
            )

            executions, total = await list_executions(db)

            assert total == 2
            assert len(executions) == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_buyer_id(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer1 = await _create_agent(db)
            buyer2 = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            await execute_action(
                db, listing_id=listing["id"], buyer_id=buyer1.id,
                parameters={"q": "a"}, consent=True,
            )
            await execute_action(
                db, listing_id=listing["id"], buyer_id=buyer2.id,
                parameters={"q": "b"}, consent=True,
            )

            executions, total = await list_executions(db, buyer_id=buyer1.id)

            assert total == 1
            assert executions[0]["buyer_id"] == buyer1.id

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            await execute_action(
                db, listing_id=listing["id"], buyer_id=buyer.id,
                parameters={"q": "test"}, consent=True,
            )

            # All executions from the simulated executor end as "completed"
            completed, total_completed = await list_executions(db, status="completed")
            pending, total_pending = await list_executions(db, status="pending")

            assert total_completed == 1
            assert total_pending == 0

    @pytest.mark.asyncio
    async def test_list_pagination(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            for i in range(5):
                await execute_action(
                    db, listing_id=listing["id"], buyer_id=buyer.id,
                    parameters={"q": f"query-{i}"}, consent=True,
                )

            page1, total = await list_executions(db, page=1, page_size=2)
            page2, _ = await list_executions(db, page=2, page_size=2)

            assert total == 5
            assert len(page1) == 2
            assert len(page2) == 2


# ---------------------------------------------------------------------------
# cancel_execution
# ---------------------------------------------------------------------------

class TestCancelExecution:
    """Test action_executor.cancel_execution."""

    @pytest.mark.asyncio
    async def test_cancel_pending_releases_funds(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            # Create a pending execution manually via the model
            # (execute_action runs the full lifecycle so we can't test cancel on it)
            from marketplace.models.action_execution import ActionExecution

            execution = ActionExecution(
                action_listing_id=listing["id"],
                buyer_id=buyer.id,
                tool_id=tool["id"],
                parameters=json.dumps({"q": "test"}),
                status="pending",
                amount_usdc=Decimal("0.05"),
                payment_status="held",
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            result = await cancel_execution(db, execution.id, buyer.id)

            assert result is not None
            assert result["status"] == "failed"
            assert result["error_message"] == "Cancelled by buyer"
            assert result["payment_status"] == "released"
            assert result["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_cancel_wrong_buyer_raises_value_error(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            other_buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            from marketplace.models.action_execution import ActionExecution

            execution = ActionExecution(
                action_listing_id=listing["id"],
                buyer_id=buyer.id,
                tool_id=tool["id"],
                parameters=json.dumps({}),
                status="pending",
                amount_usdc=Decimal("0.01"),
                payment_status="held",
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            with pytest.raises(ValueError, match="Not authorized"):
                await cancel_execution(db, execution.id, other_buyer.id)

    @pytest.mark.asyncio
    async def test_cancel_completed_execution_raises(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool, listing = await _setup_tool_and_listing(db, creator, seller)

            # Execute to completion first
            executed = await execute_action(
                db, listing_id=listing["id"], buyer_id=buyer.id,
                parameters={"q": "test"}, consent=True,
            )

            with pytest.raises(ValueError, match="Cannot cancel"):
                await cancel_execution(db, executed["id"], buyer.id)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_returns_none(self):
        async with TestSession() as db:
            buyer = await _create_agent(db)

            result = await cancel_execution(db, "nonexistent-id", buyer.id)

            assert result is None
