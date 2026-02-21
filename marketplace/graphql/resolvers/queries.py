"""Strawberry GraphQL query resolvers for the AgentChains marketplace."""

import strawberry
from typing import Optional, List

from sqlalchemy import select, func

from marketplace.graphql.schema import (
    AgentType,
    AgentConnection,
    ListingType,
    ListingConnection,
    TransactionType,
    PageInfo,
)
from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.transaction import Transaction
from marketplace.models.workflow import WorkflowDefinition


# WorkflowType is defined locally since the linted schema doesn't export it.
@strawberry.type
class WorkflowType:
    """GraphQL type representing a workflow definition."""

    id: str
    name: str
    description: str
    owner_id: str
    version: int
    status: str


def _agent_to_type(agent: RegisteredAgent) -> AgentType:
    """Convert a RegisteredAgent ORM model to a GraphQL AgentType."""
    return AgentType(
        id=agent.id,
        name=agent.name,
        description=agent.description or "",
        agent_type=agent.agent_type,
        status=agent.status,
        created_at=agent.created_at.isoformat() if agent.created_at else "",
    )


def _listing_to_type(listing: DataListing) -> ListingType:
    """Convert a DataListing ORM model to a GraphQL ListingType."""
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
    """Convert a Transaction ORM model to a GraphQL TransactionType."""
    return TransactionType(
        id=txn.id,
        listing_id=txn.listing_id,
        buyer_id=txn.buyer_id,
        seller_id=txn.seller_id,
        amount_usdc=float(txn.amount_usdc),
        status=txn.status,
        created_at=txn.initiated_at.isoformat() if txn.initiated_at else "",
    )


def _workflow_to_type(wf: WorkflowDefinition) -> WorkflowType:
    """Convert a WorkflowDefinition ORM model to a GraphQL WorkflowType."""
    return WorkflowType(
        id=wf.id,
        name=wf.name,
        description=wf.description or "",
        owner_id=wf.owner_id,
        version=wf.version or 1,
        status=wf.status or "draft",
    )


@strawberry.type
class Query:
    """Root GraphQL query type for the marketplace."""

    @strawberry.field
    async def agents(
        self,
        info: strawberry.types.Info,
        status: Optional[str] = None,
        agent_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> AgentConnection:
        """Query registered agents with optional filters and pagination."""
        db = info.context["db"]

        query = select(RegisteredAgent)
        count_query = select(func.count(RegisteredAgent.id))

        if status:
            query = query.where(RegisteredAgent.status == status)
            count_query = count_query.where(RegisteredAgent.status == status)
        if agent_type:
            query = query.where(RegisteredAgent.agent_type == agent_type)
            count_query = count_query.where(RegisteredAgent.agent_type == agent_type)

        # Get total count
        total_result = await db.execute(count_query)
        total_count = total_result.scalar() or 0

        # Apply pagination
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        agents = result.scalars().all()

        items = [_agent_to_type(a) for a in agents]
        page_info = PageInfo(
            has_next_page=(offset + limit) < total_count,
            has_previous_page=offset > 0,
            total_count=total_count,
        )

        return AgentConnection(items=items, page_info=page_info)

    @strawberry.field
    async def agent(
        self,
        info: strawberry.types.Info,
        id: str,
    ) -> Optional[AgentType]:
        """Get a single agent by ID."""
        db = info.context["db"]
        result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            return None
        return _agent_to_type(agent)

    @strawberry.field
    async def listings(
        self,
        info: strawberry.types.Info,
        category: Optional[str] = None,
        status: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ListingConnection:
        """Query data listings with optional filters and pagination."""
        db = info.context["db"]

        query = select(DataListing)
        count_query = select(func.count(DataListing.id))

        if category:
            query = query.where(DataListing.category == category)
            count_query = count_query.where(DataListing.category == category)
        if status:
            query = query.where(DataListing.status == status)
            count_query = count_query.where(DataListing.status == status)
        if min_price is not None:
            query = query.where(DataListing.price_usdc >= min_price)
            count_query = count_query.where(DataListing.price_usdc >= min_price)
        if max_price is not None:
            query = query.where(DataListing.price_usdc <= max_price)
            count_query = count_query.where(DataListing.price_usdc <= max_price)

        # Get total count
        total_result = await db.execute(count_query)
        total_count = total_result.scalar() or 0

        # Apply pagination
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        listings = result.scalars().all()

        items = [_listing_to_type(lst) for lst in listings]
        page_info = PageInfo(
            has_next_page=(offset + limit) < total_count,
            has_previous_page=offset > 0,
            total_count=total_count,
        )

        return ListingConnection(items=items, page_info=page_info)

    @strawberry.field
    async def listing(
        self,
        info: strawberry.types.Info,
        id: str,
    ) -> Optional[ListingType]:
        """Get a single listing by ID."""
        db = info.context["db"]
        result = await db.execute(
            select(DataListing).where(DataListing.id == id)
        )
        listing = result.scalar_one_or_none()
        if listing is None:
            return None
        return _listing_to_type(listing)

    @strawberry.field
    async def transactions(
        self,
        info: strawberry.types.Info,
        buyer_id: Optional[str] = None,
        seller_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[TransactionType]:
        """Query transactions with optional filters."""
        db = info.context["db"]

        query = select(Transaction)

        if buyer_id:
            query = query.where(Transaction.buyer_id == buyer_id)
        if seller_id:
            query = query.where(Transaction.seller_id == seller_id)
        if status:
            query = query.where(Transaction.status == status)

        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        txns = result.scalars().all()

        return [_transaction_to_type(t) for t in txns]

    @strawberry.field
    async def workflows(
        self,
        info: strawberry.types.Info,
        owner_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[WorkflowType]:
        """Query workflow definitions with optional filters."""
        db = info.context["db"]

        query = select(WorkflowDefinition)

        if owner_id:
            query = query.where(WorkflowDefinition.owner_id == owner_id)
        if status:
            query = query.where(WorkflowDefinition.status == status)

        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        wfs = result.scalars().all()

        return [_workflow_to_type(w) for w in wfs]
