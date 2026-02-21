"""Strawberry GraphQL mutation resolvers for the AgentChains marketplace."""

import uuid
import hashlib
from datetime import datetime, timezone

import strawberry
from typing import Optional

from sqlalchemy import select

from marketplace.graphql.schema import AgentType, ListingType
from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
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
class Mutation:
    """Root GraphQL mutation type for the marketplace."""

    @strawberry.mutation
    async def create_agent(
        self,
        info: strawberry.types.Info,
        name: str,
        agent_type: str,
        description: str = "",
        public_key: str = "",
    ) -> AgentType:
        """Register a new agent in the marketplace."""
        db = info.context["db"]

        agent = RegisteredAgent(
            id=str(uuid.uuid4()),
            name=name,
            agent_type=agent_type,
            description=description,
            public_key=public_key,
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)

        return _agent_to_type(agent)

    @strawberry.mutation
    async def create_listing(
        self,
        info: strawberry.types.Info,
        title: str,
        category: str,
        price_usdc: float,
        content: str = "",
    ) -> ListingType:
        """Create a new data listing in the marketplace."""
        db = info.context["db"]

        # Compute content hash
        content_bytes = content.encode("utf-8") if content else b""
        content_hash = "sha256:" + hashlib.sha256(content_bytes).hexdigest()

        # Use the authenticated user as seller, or a placeholder
        user = info.context.get("user", {})
        seller_id = user.get("id", str(uuid.uuid4()))

        listing = DataListing(
            id=str(uuid.uuid4()),
            seller_id=seller_id,
            title=title,
            category=category,
            price_usdc=price_usdc,
            content_hash=content_hash,
            content_size=len(content_bytes),
            content_type="application/json",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(listing)
        await db.commit()
        await db.refresh(listing)

        return _listing_to_type(listing)

    @strawberry.mutation
    async def create_workflow(
        self,
        info: strawberry.types.Info,
        name: str,
        graph_json: str,
        description: str = "",
    ) -> WorkflowType:
        """Create a new workflow definition."""
        db = info.context["db"]

        # Use the authenticated user as owner, or a placeholder
        user = info.context.get("user", {})
        owner_id = user.get("id", str(uuid.uuid4()))

        workflow = WorkflowDefinition(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            graph_json=graph_json,
            owner_id=owner_id,
            version=1,
            status="draft",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)

        return _workflow_to_type(workflow)
