"""Strawberry GraphQL schema with types, queries, mutations, and the router."""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import strawberry
from strawberry.fastapi import GraphQLRouter

from sqlalchemy import select

from marketplace.database import async_session
from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction


# ---------------------------------------------------------------------------
# GraphQL Types
# ---------------------------------------------------------------------------

@strawberry.type
class AgentType:
    """GraphQL type representing a registered agent."""

    id: str
    name: str
    description: str
    agent_type: str
    status: str
    created_at: str


@strawberry.type
class ListingType:
    """GraphQL type representing a data listing."""

    id: str
    title: str
    category: str
    price_usdc: float
    quality_score: float
    status: str
    seller_id: str


@strawberry.type
class TransactionType:
    """GraphQL type representing a transaction."""

    id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    amount_usdc: float
    status: str
    created_at: str


@strawberry.type
class PageInfo:
    """Pagination metadata for connection types."""

    has_next_page: bool
    has_previous_page: bool
    total_count: int


@strawberry.type
class AgentConnection:
    """Paginated list of agents."""

    items: List[AgentType]
    page_info: PageInfo


@strawberry.type
class ListingConnection:
    """Paginated list of listings."""

    items: List[ListingType]
    page_info: PageInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_to_type(agent: RegisteredAgent) -> AgentType:
    return AgentType(
        id=agent.id,
        name=agent.name,
        description=agent.description or "",
        agent_type=agent.agent_type,
        status=agent.status,
        created_at=agent.created_at.isoformat() if agent.created_at else "",
    )


def _listing_to_type(listing: DataListing) -> ListingType:
    return ListingType(
        id=listing.id,
        seller_id=listing.seller_id,
        title=listing.title,
        category=listing.category,
        price_usdc=float(listing.price_usdc),
        quality_score=float(listing.quality_score) if listing.quality_score else 0.0,
        status=listing.status,
    )


def _transaction_to_type(txn: Transaction) -> TransactionType:
    return TransactionType(
        id=txn.id,
        listing_id=txn.listing_id,
        buyer_id=txn.buyer_id,
        seller_id=txn.seller_id,
        amount_usdc=float(txn.amount_usdc),
        status=txn.status,
        created_at=txn.initiated_at.isoformat() if txn.initiated_at else "",
    )


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

@strawberry.type
class Query:
    """Root GraphQL query type."""

    @strawberry.field
    async def agents(
        self,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> List[AgentType]:
        """List agents with optional status filter."""
        async with async_session() as db:
            stmt = select(RegisteredAgent).limit(limit)
            if status:
                stmt = stmt.where(RegisteredAgent.status == status)
            result = await db.execute(stmt)
            return [_agent_to_type(a) for a in result.scalars().all()]

    @strawberry.field
    async def agent(self, id: str) -> Optional[AgentType]:
        """Get a single agent by ID."""
        async with async_session() as db:
            result = await db.execute(
                select(RegisteredAgent).where(RegisteredAgent.id == id)
            )
            agent = result.scalar_one_or_none()
            return _agent_to_type(agent) if agent else None

    @strawberry.field
    async def listings(
        self,
        limit: int = 20,
        category: Optional[str] = None,
    ) -> List[ListingType]:
        """List data listings with optional category filter."""
        async with async_session() as db:
            stmt = select(DataListing).limit(limit)
            if category:
                stmt = stmt.where(DataListing.category == category)
            result = await db.execute(stmt)
            return [_listing_to_type(lst) for lst in result.scalars().all()]

    @strawberry.field
    async def listing(self, id: str) -> Optional[ListingType]:
        """Get a single listing by ID."""
        async with async_session() as db:
            result = await db.execute(
                select(DataListing).where(DataListing.id == id)
            )
            listing = result.scalar_one_or_none()
            return _listing_to_type(listing) if listing else None

    @strawberry.field
    async def transactions(
        self,
        agent_id: str,
        limit: int = 20,
    ) -> List[TransactionType]:
        """List transactions where agent_id is either buyer or seller."""
        async with async_session() as db:
            stmt = (
                select(Transaction)
                .where(
                    (Transaction.buyer_id == agent_id)
                    | (Transaction.seller_id == agent_id)
                )
                .limit(limit)
            )
            result = await db.execute(stmt)
            return [_transaction_to_type(t) for t in result.scalars().all()]


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

@strawberry.type
class Mutation:
    """Root GraphQL mutation type."""

    @strawberry.mutation
    async def create_listing(
        self,
        title: str,
        category: str,
        price_usdc: float,
        seller_id: str,
    ) -> ListingType:
        """Create a new data listing in the marketplace."""
        async with async_session() as db:
            content_hash = "sha256:" + hashlib.sha256(b"").hexdigest()
            listing = DataListing(
                id=str(uuid.uuid4()),
                seller_id=seller_id,
                title=title,
                category=category,
                price_usdc=price_usdc,
                content_hash=content_hash,
                content_size=0,
                content_type="application/json",
                status="active",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(listing)
            await db.commit()
            await db.refresh(listing)
            return _listing_to_type(listing)


# ---------------------------------------------------------------------------
# Schema & Router
# ---------------------------------------------------------------------------

schema = strawberry.Schema(query=Query, mutation=Mutation)

graphql_router = GraphQLRouter(schema, path="/graphql")
