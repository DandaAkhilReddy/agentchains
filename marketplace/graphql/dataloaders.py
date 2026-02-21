"""Strawberry DataLoader classes for N+1 query prevention."""

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing


class AgentLoader:
    """Batch loader for agents by ID.

    Prevents N+1 queries when resolving agent references from
    listings, transactions, or other types that reference agents.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load(self, keys: List[str]) -> List[RegisteredAgent | None]:
        """Batch load agents by their IDs.

        Args:
            keys: List of agent IDs to load.

        Returns:
            List of RegisteredAgent instances (or None for missing IDs),
            in the same order as the input keys.
        """
        result = await self.db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id.in_(keys))
        )
        agents = result.scalars().all()

        # Build a map for O(1) lookup
        agent_map = {agent.id: agent for agent in agents}

        # Return in the same order as keys, None for missing
        return [agent_map.get(key) for key in keys]


class ListingLoader:
    """Batch loader for listings by ID.

    Prevents N+1 queries when resolving listing references from
    transactions or other types that reference listings.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load(self, keys: List[str]) -> List[DataListing | None]:
        """Batch load listings by their IDs.

        Args:
            keys: List of listing IDs to load.

        Returns:
            List of DataListing instances (or None for missing IDs),
            in the same order as the input keys.
        """
        result = await self.db.execute(
            select(DataListing).where(DataListing.id.in_(keys))
        )
        listings = result.scalars().all()

        # Build a map for O(1) lookup
        listing_map = {listing.id: listing for listing in listings}

        # Return in the same order as keys, None for missing
        return [listing_map.get(key) for key in keys]
