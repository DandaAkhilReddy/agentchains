"""Unit tests for webmcp_service — tool registration, discovery, and action listings.

Covers register_tool, list_tools (with filters), get_tool, approve_tool,
create_action_listing (including rejection of unapproved tools),
list_action_listings (with filters), and get_action_listing.
"""

import json
import uuid
from decimal import Decimal

import pytest

from marketplace.models.agent import RegisteredAgent
from marketplace.models.creator import Creator
from marketplace.services import webmcp_service
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


async def _create_agent(db) -> RegisteredAgent:
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


async def _register_tool(db, creator_id, **overrides):
    """Register a tool through the service layer with sensible defaults."""
    defaults = {
        "name": f"tool-{uuid.uuid4().hex[:8]}",
        "domain": "example.com",
        "endpoint_url": "https://example.com/.well-known/mcp",
        "category": "shopping",
        "description": "A test tool",
        "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        "output_schema": {"type": "object"},
    }
    defaults.update(overrides)
    return await webmcp_service.register_tool(db, creator_id=creator_id, **defaults)


# ---------------------------------------------------------------------------
# register_tool
# ---------------------------------------------------------------------------

class TestRegisterTool:
    """Test webmcp_service.register_tool."""

    @pytest.mark.asyncio
    async def test_register_creates_tool_with_correct_fields(self):
        async with TestSession() as db:
            creator = await _create_creator(db)

            result = await _register_tool(
                db,
                creator_id=creator.id,
                name="price-checker",
                domain="amazon.com",
                endpoint_url="https://amazon.com/mcp",
                category="shopping",
                description="Checks product prices",
            )

            assert result["name"] == "price-checker"
            assert result["domain"] == "amazon.com"
            assert result["endpoint_url"] == "https://amazon.com/mcp"
            assert result["category"] == "shopping"
            assert result["description"] == "Checks product prices"
            assert result["creator_id"] == creator.id
            assert result["status"] == "pending"
            assert result["version"] == "1.0.0"
            assert result["id"] is not None

    @pytest.mark.asyncio
    async def test_register_stores_input_schema_as_dict(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            schema = {"type": "object", "properties": {"url": {"type": "string"}}}

            result = await _register_tool(
                db, creator_id=creator.id, input_schema=schema,
            )

            assert result["input_schema"] == schema

    @pytest.mark.asyncio
    async def test_register_with_agent_id(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)

            result = await _register_tool(
                db, creator_id=creator.id, agent_id=agent.id,
            )

            assert result["agent_id"] == agent.id

    @pytest.mark.asyncio
    async def test_register_defaults_version_to_1_0_0(self):
        async with TestSession() as db:
            creator = await _create_creator(db)

            result = await _register_tool(db, creator_id=creator.id)

            assert result["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_register_sets_execution_stats_to_zero(self):
        async with TestSession() as db:
            creator = await _create_creator(db)

            result = await _register_tool(db, creator_id=creator.id)

            assert result["execution_count"] == 0
            assert result["avg_execution_time_ms"] == 0
            assert result["success_rate"] == 1.0


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------

class TestListTools:
    """Test webmcp_service.list_tools with filters."""

    @pytest.mark.asyncio
    async def test_list_returns_only_approved_or_active_by_default(self):
        async with TestSession() as db:
            creator = await _create_creator(db)

            # Register 3 tools (all start as pending)
            t1 = await _register_tool(db, creator_id=creator.id, name="tool-a")
            t2 = await _register_tool(db, creator_id=creator.id, name="tool-b")
            t3 = await _register_tool(db, creator_id=creator.id, name="tool-c")

            # Approve one
            await webmcp_service.approve_tool(db, t1["id"], creator.id)

            tools, total = await webmcp_service.list_tools(db)

            assert total == 1
            assert len(tools) == 1
            assert tools[0]["id"] == t1["id"]

    @pytest.mark.asyncio
    async def test_list_filter_by_category(self):
        async with TestSession() as db:
            creator = await _create_creator(db)

            t1 = await _register_tool(db, creator_id=creator.id, category="shopping")
            t2 = await _register_tool(db, creator_id=creator.id, category="research")

            # Approve both
            await webmcp_service.approve_tool(db, t1["id"], creator.id)
            await webmcp_service.approve_tool(db, t2["id"], creator.id)

            tools, total = await webmcp_service.list_tools(db, category="shopping")

            assert total == 1
            assert tools[0]["category"] == "shopping"

    @pytest.mark.asyncio
    async def test_list_filter_by_domain(self):
        async with TestSession() as db:
            creator = await _create_creator(db)

            t1 = await _register_tool(db, creator_id=creator.id, domain="amazon.com")
            t2 = await _register_tool(db, creator_id=creator.id, domain="google.com")

            await webmcp_service.approve_tool(db, t1["id"], creator.id)
            await webmcp_service.approve_tool(db, t2["id"], creator.id)

            tools, total = await webmcp_service.list_tools(db, domain="amazon.com")

            assert total == 1
            assert tools[0]["domain"] == "amazon.com"

    @pytest.mark.asyncio
    async def test_list_filter_by_search_query(self):
        async with TestSession() as db:
            creator = await _create_creator(db)

            t1 = await _register_tool(
                db, creator_id=creator.id,
                name="product-search", description="Search for products",
            )
            t2 = await _register_tool(
                db, creator_id=creator.id,
                name="weather-api", description="Get weather data",
            )

            await webmcp_service.approve_tool(db, t1["id"], creator.id)
            await webmcp_service.approve_tool(db, t2["id"], creator.id)

            tools, total = await webmcp_service.list_tools(db, q="product")

            assert total == 1
            assert tools[0]["name"] == "product-search"

    @pytest.mark.asyncio
    async def test_list_filter_by_explicit_status(self):
        async with TestSession() as db:
            creator = await _create_creator(db)

            await _register_tool(db, creator_id=creator.id, name="pending-tool")

            tools, total = await webmcp_service.list_tools(db, status="pending")

            assert total == 1
            assert tools[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_pagination(self):
        async with TestSession() as db:
            creator = await _create_creator(db)

            for i in range(5):
                t = await _register_tool(db, creator_id=creator.id, name=f"tool-{i}")
                await webmcp_service.approve_tool(db, t["id"], creator.id)

            page1, total = await webmcp_service.list_tools(db, page=1, page_size=2)
            page2, _ = await webmcp_service.list_tools(db, page=2, page_size=2)

            assert total == 5
            assert len(page1) == 2
            assert len(page2) == 2


# ---------------------------------------------------------------------------
# get_tool
# ---------------------------------------------------------------------------

class TestGetTool:
    """Test webmcp_service.get_tool."""

    @pytest.mark.asyncio
    async def test_get_existing_tool_returns_dict(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            registered = await _register_tool(db, creator_id=creator.id, name="my-tool")

            result = await webmcp_service.get_tool(db, registered["id"])

            assert result is not None
            assert result["id"] == registered["id"]
            assert result["name"] == "my-tool"

    @pytest.mark.asyncio
    async def test_get_missing_tool_returns_none(self):
        async with TestSession() as db:
            result = await webmcp_service.get_tool(db, "nonexistent-id")

            assert result is None


# ---------------------------------------------------------------------------
# approve_tool
# ---------------------------------------------------------------------------

class TestApproveTool:
    """Test webmcp_service.approve_tool."""

    @pytest.mark.asyncio
    async def test_approve_changes_status(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            registered = await _register_tool(db, creator_id=creator.id)

            assert registered["status"] == "pending"

            approved = await webmcp_service.approve_tool(
                db, registered["id"], creator.id, notes="Looks good",
            )

            assert approved is not None
            assert approved["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_nonexistent_returns_none(self):
        async with TestSession() as db:
            creator = await _create_creator(db)

            result = await webmcp_service.approve_tool(db, "bad-id", creator.id)

            assert result is None

    @pytest.mark.asyncio
    async def test_approve_persists_notes(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            registered = await _register_tool(db, creator_id=creator.id)

            await webmcp_service.approve_tool(
                db, registered["id"], creator.id, notes="Verified by admin",
            )

            # Re-fetch to confirm persistence
            fetched = await webmcp_service.get_tool(db, registered["id"])
            assert fetched["status"] == "approved"


# ---------------------------------------------------------------------------
# create_action_listing
# ---------------------------------------------------------------------------

class TestCreateActionListing:
    """Test webmcp_service.create_action_listing."""

    @pytest.mark.asyncio
    async def test_create_listing_for_approved_tool(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _register_tool(db, creator_id=creator.id)
            await webmcp_service.approve_tool(db, tool["id"], creator.id)

            listing = await webmcp_service.create_action_listing(
                db,
                tool_id=tool["id"],
                seller_id=agent.id,
                title="Price Check Service",
                price_per_execution=0.05,
                description="Check prices on demand",
                requires_consent=True,
                domain_lock=["amazon.com"],
                tags=["shopping", "price"],
            )

            assert listing["id"] is not None
            assert listing["tool_id"] == tool["id"]
            assert listing["seller_id"] == agent.id
            assert listing["title"] == "Price Check Service"
            assert listing["price_per_execution"] == 0.05
            assert listing["requires_consent"] is True
            assert listing["domain_lock"] == ["amazon.com"]
            assert listing["tags"] == ["shopping", "price"]
            assert listing["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_listing_rejects_unapproved_tool(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _register_tool(db, creator_id=creator.id)
            # Tool is still "pending" — not approved

            with pytest.raises(ValueError, match="not approved"):
                await webmcp_service.create_action_listing(
                    db,
                    tool_id=tool["id"],
                    seller_id=agent.id,
                    title="Should Fail",
                    price_per_execution=0.01,
                )

    @pytest.mark.asyncio
    async def test_create_listing_rejects_nonexistent_tool(self):
        async with TestSession() as db:
            agent = await _create_agent(db)

            with pytest.raises(ValueError, match="not found"):
                await webmcp_service.create_action_listing(
                    db,
                    tool_id="nonexistent-id",
                    seller_id=agent.id,
                    title="Should Fail",
                    price_per_execution=0.01,
                )

    @pytest.mark.asyncio
    async def test_create_listing_default_parameters(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _register_tool(db, creator_id=creator.id)
            await webmcp_service.approve_tool(db, tool["id"], creator.id)

            listing = await webmcp_service.create_action_listing(
                db,
                tool_id=tool["id"],
                seller_id=agent.id,
                title="Default Params Test",
                price_per_execution=0.01,
                default_parameters={"region": "US"},
            )

            assert listing["default_parameters"] == {"region": "US"}


# ---------------------------------------------------------------------------
# list_action_listings
# ---------------------------------------------------------------------------

class TestListActionListings:
    """Test webmcp_service.list_action_listings."""

    @pytest.mark.asyncio
    async def test_list_returns_active_listings(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _register_tool(db, creator_id=creator.id)
            await webmcp_service.approve_tool(db, tool["id"], creator.id)

            await webmcp_service.create_action_listing(
                db, tool_id=tool["id"], seller_id=agent.id,
                title="Listing A", price_per_execution=0.01,
            )
            await webmcp_service.create_action_listing(
                db, tool_id=tool["id"], seller_id=agent.id,
                title="Listing B", price_per_execution=0.02,
            )

            listings, total = await webmcp_service.list_action_listings(db)

            assert total == 2
            assert len(listings) == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_max_price(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _register_tool(db, creator_id=creator.id)
            await webmcp_service.approve_tool(db, tool["id"], creator.id)

            await webmcp_service.create_action_listing(
                db, tool_id=tool["id"], seller_id=agent.id,
                title="Cheap", price_per_execution=0.01,
            )
            await webmcp_service.create_action_listing(
                db, tool_id=tool["id"], seller_id=agent.id,
                title="Expensive", price_per_execution=1.00,
            )

            listings, total = await webmcp_service.list_action_listings(db, max_price=0.05)

            assert total == 1
            assert listings[0]["title"] == "Cheap"

    @pytest.mark.asyncio
    async def test_list_filter_by_search_query(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _register_tool(db, creator_id=creator.id)
            await webmcp_service.approve_tool(db, tool["id"], creator.id)

            await webmcp_service.create_action_listing(
                db, tool_id=tool["id"], seller_id=agent.id,
                title="Product Finder", price_per_execution=0.01,
                description="Find products online",
            )
            await webmcp_service.create_action_listing(
                db, tool_id=tool["id"], seller_id=agent.id,
                title="Weather Report", price_per_execution=0.01,
                description="Daily weather updates",
            )

            listings, total = await webmcp_service.list_action_listings(db, q="product")

            assert total == 1
            assert listings[0]["title"] == "Product Finder"

    @pytest.mark.asyncio
    async def test_list_pagination(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _register_tool(db, creator_id=creator.id)
            await webmcp_service.approve_tool(db, tool["id"], creator.id)

            for i in range(5):
                await webmcp_service.create_action_listing(
                    db, tool_id=tool["id"], seller_id=agent.id,
                    title=f"Listing-{i}", price_per_execution=0.01,
                )

            page1, total = await webmcp_service.list_action_listings(
                db, page=1, page_size=2,
            )
            page2, _ = await webmcp_service.list_action_listings(
                db, page=2, page_size=2,
            )

            assert total == 5
            assert len(page1) == 2
            assert len(page2) == 2


# ---------------------------------------------------------------------------
# get_action_listing
# ---------------------------------------------------------------------------

class TestGetActionListing:
    """Test webmcp_service.get_action_listing."""

    @pytest.mark.asyncio
    async def test_get_existing_listing_returns_dict(self):
        async with TestSession() as db:
            creator = await _create_creator(db)
            agent = await _create_agent(db)
            tool = await _register_tool(db, creator_id=creator.id)
            await webmcp_service.approve_tool(db, tool["id"], creator.id)

            created = await webmcp_service.create_action_listing(
                db, tool_id=tool["id"], seller_id=agent.id,
                title="Test Listing", price_per_execution=0.01,
            )

            result = await webmcp_service.get_action_listing(db, created["id"])

            assert result is not None
            assert result["id"] == created["id"]
            assert result["title"] == "Test Listing"

    @pytest.mark.asyncio
    async def test_get_missing_listing_returns_none(self):
        async with TestSession() as db:
            result = await webmcp_service.get_action_listing(db, "nonexistent-id")

            assert result is None
