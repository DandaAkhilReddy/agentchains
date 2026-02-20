"""Unit tests for WebMCP models — WebMCPTool, ActionListing, ActionExecution.

Covers CRUD operations, default values, FK relationships, and index existence.
Uses in-memory SQLite via conftest TestSession.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select

from marketplace.models.action_execution import ActionExecution
from marketplace.models.action_listing import ActionListing
from marketplace.models.agent import RegisteredAgent
from marketplace.models.creator import Creator
from marketplace.models.webmcp_tool import WebMCPTool
from marketplace.tests.conftest import TestSession, _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_creator(db) -> Creator:
    """Insert a Creator for FK relationships."""
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


async def _create_agent(db) -> RegisteredAgent:
    """Insert a RegisteredAgent for FK relationships."""
    agent = RegisteredAgent(
        id=_new_id(),
        name=f"test-agent-{uuid.uuid4().hex[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test_key",
        status="active",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def _create_tool(db, creator_id: str, agent_id: str = None, **overrides) -> WebMCPTool:
    """Insert a WebMCPTool with sensible defaults."""
    defaults = {
        "name": f"tool-{uuid.uuid4().hex[:8]}",
        "description": "A test WebMCP tool",
        "domain": "example.com",
        "endpoint_url": "https://example.com/.well-known/mcp",
        "input_schema": json.dumps({"type": "object"}),
        "output_schema": json.dumps({"type": "object"}),
        "schema_hash": "abc123",
        "creator_id": creator_id,
        "agent_id": agent_id,
        "category": "shopping",
        "version": "1.0.0",
        "status": "pending",
    }
    defaults.update(overrides)
    tool = WebMCPTool(**defaults)
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


async def _create_listing(db, tool_id: str, seller_id: str, **overrides) -> ActionListing:
    """Insert an ActionListing with sensible defaults."""
    defaults = {
        "tool_id": tool_id,
        "seller_id": seller_id,
        "title": f"listing-{uuid.uuid4().hex[:8]}",
        "description": "A test action listing",
        "price_per_execution": Decimal("0.01"),
        "currency": "USD",
        "default_parameters": json.dumps({}),
        "max_executions_per_hour": 60,
        "requires_consent": True,
        "domain_lock": json.dumps([]),
        "status": "active",
        "tags": json.dumps(["test"]),
    }
    defaults.update(overrides)
    listing = ActionListing(**defaults)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing


# ---------------------------------------------------------------------------
# WebMCPTool CRUD
# ---------------------------------------------------------------------------

class TestWebMCPToolCRUD:
    """Test WebMCPTool model creation, reading, updating, and deletion."""

    @pytest.mark.asyncio
    async def test_create_tool_and_verify_fields(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)

            tool = await _create_tool(
                db,
                creator_id=creator.id,
                agent_id=agent.id,
                name="price-checker",
                domain="amazon.com",
                endpoint_url="https://amazon.com/.well-known/mcp",
                category="shopping",
            )

            assert tool.id is not None
            assert len(tool.id) == 36  # UUID format
            assert tool.name == "price-checker"
            assert tool.domain == "amazon.com"
            assert tool.endpoint_url == "https://amazon.com/.well-known/mcp"
            assert tool.category == "shopping"
            assert tool.creator_id == creator.id
            assert tool.agent_id == agent.id
            assert tool.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_read_tool_by_id(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            tool = await _create_tool(db, creator_id=creator.id)

            result = await db.execute(
                select(WebMCPTool).where(WebMCPTool.id == tool.id)
            )
            fetched = result.scalar_one_or_none()

            assert fetched is not None
            assert fetched.id == tool.id
            assert fetched.name == tool.name

    @pytest.mark.asyncio
    async def test_update_tool_status(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            tool = await _create_tool(db, creator_id=creator.id)

            tool.status = "approved"
            await db.commit()
            await db.refresh(tool)

            assert tool.status == "approved"

    @pytest.mark.asyncio
    async def test_delete_tool(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            tool = await _create_tool(db, creator_id=creator.id)
            tool_id = tool.id

            await db.delete(tool)
            await db.commit()

            result = await db.execute(
                select(WebMCPTool).where(WebMCPTool.id == tool_id)
            )
            assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# WebMCPTool defaults
# ---------------------------------------------------------------------------

class TestWebMCPToolDefaults:
    """Test default values assigned by the model."""

    @pytest.mark.asyncio
    async def test_default_status_is_pending(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            tool = await _create_tool(db, creator_id=creator.id)

            assert tool.status == "pending"

    @pytest.mark.asyncio
    async def test_default_version(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            # Create without explicit version
            tool = WebMCPTool(
                name="default-ver",
                domain="test.com",
                endpoint_url="https://test.com/mcp",
                category="research",
                creator_id=creator.id,
            )
            db.add(tool)
            await db.commit()
            await db.refresh(tool)

            assert tool.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_default_execution_count_is_zero(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            tool = await _create_tool(db, creator_id=creator.id)

            assert tool.execution_count == 0

    @pytest.mark.asyncio
    async def test_default_avg_execution_time_is_zero(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            tool = await _create_tool(db, creator_id=creator.id)

            assert tool.avg_execution_time_ms == 0

    @pytest.mark.asyncio
    async def test_default_success_rate_is_one(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            tool = await _create_tool(db, creator_id=creator.id)

            assert float(tool.success_rate) == 1.0

    @pytest.mark.asyncio
    async def test_created_at_is_auto_set(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            tool = await _create_tool(db, creator_id=creator.id)

            assert tool.created_at is not None
            assert isinstance(tool.created_at, datetime)

    @pytest.mark.asyncio
    async def test_updated_at_is_auto_set(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            tool = await _create_tool(db, creator_id=creator.id)

            assert tool.updated_at is not None
            assert isinstance(tool.updated_at, datetime)


# ---------------------------------------------------------------------------
# ActionListing CRUD
# ---------------------------------------------------------------------------

class TestActionListingCRUD:
    """Test ActionListing model creation, FK relationship, and fields."""

    @pytest.mark.asyncio
    async def test_create_listing_with_tool_fk(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)

            listing = await _create_listing(
                db,
                tool_id=tool.id,
                seller_id=agent.id,
                title="Buy Price Check",
                price_per_execution=Decimal("0.05"),
            )

            assert listing.id is not None
            assert listing.tool_id == tool.id
            assert listing.seller_id == agent.id
            assert listing.title == "Buy Price Check"
            assert float(listing.price_per_execution) == 0.05

    @pytest.mark.asyncio
    async def test_listing_fields_full(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)

            listing = await _create_listing(
                db,
                tool_id=tool.id,
                seller_id=agent.id,
                requires_consent=False,
                domain_lock=json.dumps(["example.com"]),
                max_executions_per_hour=100,
                tags=json.dumps(["shopping", "price"]),
            )

            assert listing.requires_consent is False
            assert json.loads(listing.domain_lock) == ["example.com"]
            assert listing.max_executions_per_hour == 100
            assert json.loads(listing.tags) == ["shopping", "price"]

    @pytest.mark.asyncio
    async def test_listing_default_status_is_active(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)

            listing = await _create_listing(db, tool_id=tool.id, seller_id=agent.id)

            assert listing.status == "active"

    @pytest.mark.asyncio
    async def test_listing_default_access_count_is_zero(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)

            listing = await _create_listing(db, tool_id=tool.id, seller_id=agent.id)

            assert listing.access_count == 0

    @pytest.mark.asyncio
    async def test_listing_timestamps_auto_set(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)

            listing = await _create_listing(db, tool_id=tool.id, seller_id=agent.id)

            assert listing.created_at is not None
            assert listing.updated_at is not None

    @pytest.mark.asyncio
    async def test_read_listing_by_id(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)
            listing = await _create_listing(db, tool_id=tool.id, seller_id=agent.id)

            result = await db.execute(
                select(ActionListing).where(ActionListing.id == listing.id)
            )
            fetched = result.scalar_one_or_none()

            assert fetched is not None
            assert fetched.id == listing.id

    @pytest.mark.asyncio
    async def test_delete_listing(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)
            listing = await _create_listing(db, tool_id=tool.id, seller_id=agent.id)
            listing_id = listing.id

            await db.delete(listing)
            await db.commit()

            result = await db.execute(
                select(ActionListing).where(ActionListing.id == listing_id)
            )
            assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# ActionExecution CRUD
# ---------------------------------------------------------------------------

class TestActionExecutionCRUD:
    """Test ActionExecution model creation, FK relationships, and fields."""

    @pytest.mark.asyncio
    async def test_create_execution_with_fks(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)
            listing = await _create_listing(db, tool_id=tool.id, seller_id=seller.id)

            execution = ActionExecution(
                action_listing_id=listing.id,
                buyer_id=buyer.id,
                tool_id=tool.id,
                parameters=json.dumps({"query": "laptop"}),
                amount_usdc=Decimal("0.05"),
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            assert execution.id is not None
            assert execution.action_listing_id == listing.id
            assert execution.buyer_id == buyer.id
            assert execution.tool_id == tool.id
            assert json.loads(execution.parameters) == {"query": "laptop"}
            assert float(execution.amount_usdc) == 0.05

    @pytest.mark.asyncio
    async def test_execution_default_status_is_pending(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)
            listing = await _create_listing(db, tool_id=tool.id, seller_id=seller.id)

            execution = ActionExecution(
                action_listing_id=listing.id,
                buyer_id=buyer.id,
                tool_id=tool.id,
                amount_usdc=Decimal("0.01"),
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            assert execution.status == "pending"

    @pytest.mark.asyncio
    async def test_execution_default_payment_status_is_held(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)
            listing = await _create_listing(db, tool_id=tool.id, seller_id=seller.id)

            execution = ActionExecution(
                action_listing_id=listing.id,
                buyer_id=buyer.id,
                tool_id=tool.id,
                amount_usdc=Decimal("0.01"),
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            assert execution.payment_status == "held"

    @pytest.mark.asyncio
    async def test_execution_default_proof_verified_is_false(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)
            listing = await _create_listing(db, tool_id=tool.id, seller_id=seller.id)

            execution = ActionExecution(
                action_listing_id=listing.id,
                buyer_id=buyer.id,
                tool_id=tool.id,
                amount_usdc=Decimal("0.01"),
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            assert execution.proof_verified is False

    @pytest.mark.asyncio
    async def test_execution_timestamps(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)
            listing = await _create_listing(db, tool_id=tool.id, seller_id=seller.id)

            execution = ActionExecution(
                action_listing_id=listing.id,
                buyer_id=buyer.id,
                tool_id=tool.id,
                amount_usdc=Decimal("0.01"),
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            assert execution.created_at is not None
            # started_at and completed_at should be None initially
            assert execution.started_at is None
            assert execution.completed_at is None

    @pytest.mark.asyncio
    async def test_read_execution_by_id(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)
            listing = await _create_listing(db, tool_id=tool.id, seller_id=seller.id)

            execution = ActionExecution(
                action_listing_id=listing.id,
                buyer_id=buyer.id,
                tool_id=tool.id,
                amount_usdc=Decimal("0.01"),
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            result = await db.execute(
                select(ActionExecution).where(ActionExecution.id == execution.id)
            )
            fetched = result.scalar_one_or_none()

            assert fetched is not None
            assert fetched.id == execution.id

    @pytest.mark.asyncio
    async def test_delete_execution(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            seller = await _create_agent(db)
            buyer = await _create_agent(db)
            tool = await _create_tool(db, creator_id=creator.id)
            listing = await _create_listing(db, tool_id=tool.id, seller_id=seller.id)

            execution = ActionExecution(
                action_listing_id=listing.id,
                buyer_id=buyer.id,
                tool_id=tool.id,
                amount_usdc=Decimal("0.01"),
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)
            exec_id = execution.id

            await db.delete(execution)
            await db.commit()

            result = await db.execute(
                select(ActionExecution).where(ActionExecution.id == exec_id)
            )
            assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# Index existence
# ---------------------------------------------------------------------------

class TestIndexExistence:
    """Verify expected indexes are created on the tables."""

    @pytest.mark.asyncio
    async def test_webmcp_tools_indexes(self):
        async with TestSession() as db:
            # Trigger a query so the connection is established
            await db.execute(select(WebMCPTool).limit(0))
            insp = inspect(db.get_bind())
            indexes = insp.get_indexes("webmcp_tools")
            index_names = {idx["name"] for idx in indexes}

            assert "idx_webmcp_tools_domain" in index_names
            assert "idx_webmcp_tools_category" in index_names
            assert "idx_webmcp_tools_status" in index_names
            assert "idx_webmcp_tools_creator" in index_names

    @pytest.mark.asyncio
    async def test_action_listings_indexes(self):
        async with TestSession() as db:
            await db.execute(select(ActionListing).limit(0))
            insp = inspect(db.get_bind())
            indexes = insp.get_indexes("action_listings")
            index_names = {idx["name"] for idx in indexes}

            assert "idx_action_listings_tool" in index_names
            assert "idx_action_listings_seller" in index_names
            assert "idx_action_listings_status" in index_names

    @pytest.mark.asyncio
    async def test_action_executions_indexes(self):
        async with TestSession() as db:
            await db.execute(select(ActionExecution).limit(0))
            insp = inspect(db.get_bind())
            indexes = insp.get_indexes("action_executions")
            index_names = {idx["name"] for idx in indexes}

            assert "idx_action_executions_listing" in index_names
            assert "idx_action_executions_buyer" in index_names
            assert "idx_action_executions_status" in index_names
            assert "idx_action_executions_tool" in index_names
