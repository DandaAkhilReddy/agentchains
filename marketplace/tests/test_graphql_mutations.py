"""Tests for Strawberry GraphQL mutation resolvers.

Covers:
  - create_agent: success, field mapping (tests 1-3)
  - create_listing: success, content hash, authenticated user (tests 4-7)
  - create_workflow: success, defaults (tests 8-10)
  - Helper converters: _agent_to_type, _listing_to_type, _workflow_to_type (tests 11-13)
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.graphql.resolvers.mutations import (
    Mutation,
    WorkflowType,
    _agent_to_type,
    _listing_to_type,
    _workflow_to_type,
)


def _make_info(db: AsyncSession, user: dict | None = None) -> MagicMock:
    """Build a mock strawberry Info object with context."""
    info = MagicMock()
    info.context = {"db": db}
    if user is not None:
        info.context["user"] = user
    return info


class TestCreateAgentMutation:
    """Tests 1-3: create_agent mutation."""

    # 1
    async def test_create_agent_returns_agent_type(self, db: AsyncSession):
        """create_agent should return an AgentType with correct fields."""
        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_agent(
            info, name="test-gql-agent", agent_type="buyer", description="A buyer"
        )

        assert result.name == "test-gql-agent"
        assert result.agent_type == "buyer"
        assert result.description == "A buyer"
        assert result.status == "active"
        assert len(result.id) == 36  # UUID

    # 2
    async def test_create_agent_default_description(self, db: AsyncSession):
        """create_agent with no description should default to empty string."""
        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_agent(
            info, name="no-desc-agent", agent_type="seller"
        )

        assert result.description == ""

    # 3
    async def test_create_agent_persists_to_db(self, db: AsyncSession):
        """Created agent should be queryable from the database."""
        from sqlalchemy import select
        from marketplace.models.agent import RegisteredAgent

        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_agent(
            info, name="persistent-agent", agent_type="both"
        )

        row = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == result.id)
        )
        agent = row.scalar_one()
        assert agent.name == "persistent-agent"


class TestCreateListingMutation:
    """Tests 4-7: create_listing mutation."""

    # 4
    async def test_create_listing_returns_listing_type(self, db: AsyncSession, make_agent):
        """create_listing should return a ListingType with correct fields."""
        seller, _ = await make_agent(name="gql-seller")
        mutation = Mutation()
        info = _make_info(db, user={"id": seller.id})

        result = await mutation.create_listing(
            info, title="GQL Listing", category="web_search", price_usdc=2.5
        )

        assert result.title == "GQL Listing"
        assert result.category == "web_search"
        assert result.price_usdc == 2.5
        assert result.status == "active"

    # 5
    async def test_create_listing_computes_content_hash(self, db: AsyncSession, make_agent):
        """create_listing should compute sha256 hash of content."""
        seller, _ = await make_agent(name="hash-seller")
        mutation = Mutation()
        info = _make_info(db, user={"id": seller.id})

        result = await mutation.create_listing(
            info, title="Hash Test", category="code_analysis",
            price_usdc=1.0, content="hello world"
        )

        # Verify hash was computed — listing should be persisted
        from sqlalchemy import select
        from marketplace.models.listing import DataListing

        row = await db.execute(
            select(DataListing).where(DataListing.id == result.id)
        )
        listing = row.scalar_one()
        assert listing.content_hash.startswith("sha256:")
        assert len(listing.content_hash) == 71  # "sha256:" + 64 hex chars

    # 6
    async def test_create_listing_uses_authenticated_user_as_seller(
        self, db: AsyncSession, make_agent
    ):
        """seller_id should come from info.context user when present."""
        seller, _ = await make_agent(name="auth-seller")
        mutation = Mutation()
        info = _make_info(db, user={"id": seller.id})

        result = await mutation.create_listing(
            info, title="Auth Listing", category="web_search", price_usdc=1.0
        )

        assert result.seller_id == seller.id

    # 7
    async def test_create_listing_empty_content(self, db: AsyncSession, make_agent):
        """create_listing with empty content should still produce a valid hash."""
        seller, _ = await make_agent(name="empty-content-seller")
        mutation = Mutation()
        info = _make_info(db, user={"id": seller.id})

        result = await mutation.create_listing(
            info, title="Empty", category="web_search", price_usdc=0.5
        )

        assert result.id is not None
        assert result.status == "active"


class TestCreateWorkflowMutation:
    """Tests 8-10: create_workflow mutation."""

    # 8
    async def test_create_workflow_returns_workflow_type(self, db: AsyncSession, make_agent):
        """create_workflow should return a WorkflowType."""
        owner, _ = await make_agent(name="wf-owner")
        mutation = Mutation()
        info = _make_info(db, user={"id": owner.id})

        result = await mutation.create_workflow(
            info, name="Test Workflow", graph_json='{"nodes": []}',
            description="A test workflow"
        )

        assert isinstance(result, WorkflowType)
        assert result.name == "Test Workflow"
        assert result.description == "A test workflow"
        assert result.version == 1
        assert result.status == "draft"

    # 9
    async def test_create_workflow_default_description(self, db: AsyncSession, make_agent):
        """create_workflow with no description should default to empty."""
        owner, _ = await make_agent(name="wf-owner-2")
        mutation = Mutation()
        info = _make_info(db, user={"id": owner.id})

        result = await mutation.create_workflow(
            info, name="No Desc WF", graph_json='{}'
        )

        assert result.description == ""

    # 10
    async def test_create_workflow_persists_to_db(self, db: AsyncSession, make_agent):
        """Created workflow should be queryable from the database."""
        from sqlalchemy import select
        from marketplace.models.workflow import WorkflowDefinition

        owner, _ = await make_agent(name="wf-owner-3")
        mutation = Mutation()
        info = _make_info(db, user={"id": owner.id})

        result = await mutation.create_workflow(
            info, name="Persisted WF", graph_json='{"edges": []}'
        )

        row = await db.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.id == result.id)
        )
        wf = row.scalar_one()
        assert wf.name == "Persisted WF"
        assert wf.graph_json == '{"edges": []}'


class TestHelperConverters:
    """Tests 11-13: ORM-to-GraphQL type converters."""

    # 11
    async def test_agent_to_type_maps_fields(self, db: AsyncSession, make_agent):
        """_agent_to_type should map all RegisteredAgent fields."""
        agent, _ = await make_agent(name="converter-agent")

        gql_type = _agent_to_type(agent)

        assert gql_type.id == agent.id
        assert gql_type.name == "converter-agent"
        assert gql_type.agent_type == agent.agent_type
        assert gql_type.status == "active"

    # 12
    async def test_listing_to_type_maps_fields(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """_listing_to_type should map all DataListing fields."""
        seller, _ = await make_agent(name="converter-seller")
        listing = await make_listing(seller.id, price_usdc=3.14, title="Converter Listing")

        gql_type = _listing_to_type(listing)

        assert gql_type.id == listing.id
        assert gql_type.title == "Converter Listing"
        assert gql_type.price_usdc == pytest.approx(3.14, abs=0.01)
        assert gql_type.seller_id == seller.id

    # 13
    async def test_workflow_to_type_handles_none_fields(self, db: AsyncSession):
        """_workflow_to_type should handle None description/version/status."""
        from marketplace.models.workflow import WorkflowDefinition

        wf = WorkflowDefinition(
            id="wf-test",
            name="Raw WF",
            description=None,
            graph_json="{}",
            owner_id="owner-1",
            version=None,
            status=None,
        )

        gql_type = _workflow_to_type(wf)

        assert gql_type.description == ""
        assert gql_type.version == 1
        assert gql_type.status == "draft"
