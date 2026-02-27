"""Tests for Strawberry DataLoader classes — N+1 query prevention.

Covers:
  - AgentLoader.load: batch load, ordering, missing keys (tests 1-4)
  - ListingLoader.load: batch load, ordering, missing keys (tests 5-8)
  - Empty key lists (tests 9-10)
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.graphql.dataloaders import AgentLoader, ListingLoader


class TestAgentLoader:
    """Tests 1-4: AgentLoader batch loading."""

    # 1
    async def test_load_returns_agents_in_key_order(self, db: AsyncSession, make_agent):
        """Loaded agents should be in the same order as the input keys."""
        agent_a, _ = await make_agent(name="agent-a-loader")
        agent_b, _ = await make_agent(name="agent-b-loader")

        loader = AgentLoader(db)
        results = await loader.load([agent_b.id, agent_a.id])

        assert results[0].id == agent_b.id
        assert results[1].id == agent_a.id

    # 2
    async def test_load_returns_none_for_missing_keys(self, db: AsyncSession, make_agent):
        """Missing IDs should return None in the corresponding position."""
        agent, _ = await make_agent(name="agent-exists")

        loader = AgentLoader(db)
        results = await loader.load(["nonexistent-id", agent.id])

        assert results[0] is None
        assert results[1] is not None
        assert results[1].id == agent.id

    # 3
    async def test_load_single_agent(self, db: AsyncSession, make_agent):
        """Should work correctly with a single key."""
        agent, _ = await make_agent(name="solo-agent")

        loader = AgentLoader(db)
        results = await loader.load([agent.id])

        assert len(results) == 1
        assert results[0].name == "solo-agent"

    # 4
    async def test_load_all_missing(self, db: AsyncSession):
        """When all keys are missing, should return list of None."""
        loader = AgentLoader(db)
        results = await loader.load(["ghost-1", "ghost-2"])

        assert results == [None, None]


class TestListingLoader:
    """Tests 5-8: ListingLoader batch loading."""

    # 5
    async def test_load_returns_listings_in_key_order(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """Loaded listings should be in the same order as input keys."""
        seller, _ = await make_agent(name="seller-loader")
        listing_a = await make_listing(seller.id, price_usdc=1.0, title="Listing A")
        listing_b = await make_listing(seller.id, price_usdc=2.0, title="Listing B")

        loader = ListingLoader(db)
        results = await loader.load([listing_b.id, listing_a.id])

        assert results[0].id == listing_b.id
        assert results[1].id == listing_a.id

    # 6
    async def test_load_returns_none_for_missing_listings(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """Missing listing IDs should return None in the corresponding position."""
        seller, _ = await make_agent(name="seller-missing")
        listing = await make_listing(seller.id)

        loader = ListingLoader(db)
        results = await loader.load(["nonexistent", listing.id])

        assert results[0] is None
        assert results[1].id == listing.id

    # 7
    async def test_load_single_listing(self, db: AsyncSession, make_agent, make_listing):
        """Should work correctly with a single key."""
        seller, _ = await make_agent(name="seller-single")
        listing = await make_listing(seller.id, title="Solo Listing")

        loader = ListingLoader(db)
        results = await loader.load([listing.id])

        assert len(results) == 1
        assert results[0].title == "Solo Listing"

    # 8
    async def test_load_all_missing_listings(self, db: AsyncSession):
        """When all keys are missing, should return list of None."""
        loader = ListingLoader(db)
        results = await loader.load(["no-1", "no-2", "no-3"])

        assert results == [None, None, None]


class TestLoaderEmptyKeys:
    """Tests 9-10: edge case with empty key lists."""

    # 9
    async def test_agent_loader_empty_keys(self, db: AsyncSession):
        """AgentLoader with empty keys should return empty list."""
        loader = AgentLoader(db)
        results = await loader.load([])
        assert results == []

    # 10
    async def test_listing_loader_empty_keys(self, db: AsyncSession):
        """ListingLoader with empty keys should return empty list."""
        loader = ListingLoader(db)
        results = await loader.load([])
        assert results == []
