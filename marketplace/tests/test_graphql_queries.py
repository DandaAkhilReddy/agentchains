"""Tests for Strawberry GraphQL query resolvers.

Covers:
  - agents: list all, filter by status, filter by type, pagination (tests 1-6)
  - agent: get by ID, missing ID (tests 7-8)
  - listings: list all, filter by category/status/price, pagination (tests 9-14)
  - listing: get by ID, missing ID (tests 15-16)
  - transactions: list, filter by buyer/seller/status (tests 17-20)
  - workflows: list, filter by owner/status (tests 21-23)
  - Helper converters (tests 24-25)
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.graphql.resolvers.queries import (
    Query,
    WorkflowType,
    _agent_to_type,
    _listing_to_type,
    _transaction_to_type,
    _workflow_to_type,
)


def _make_info(db: AsyncSession) -> MagicMock:
    """Build a mock strawberry Info object with context."""
    info = MagicMock()
    info.context = {"db": db}
    return info


class TestAgentsQuery:
    """Tests 1-6: agents query with filters and pagination."""

    # 1
    async def test_agents_returns_all(self, db: AsyncSession, make_agent):
        """agents() with no filters should return all agents."""
        await make_agent(name="agent-q1")
        await make_agent(name="agent-q2")

        query = Query()
        result = await query.agents(_make_info(db))

        assert result.page_info.total_count == 2
        assert len(result.items) == 2

    # 2
    async def test_agents_filter_by_status(self, db: AsyncSession, make_agent):
        """agents(status=...) should filter by status."""
        await make_agent(name="active-agent")
        # Create inactive agent directly
        from marketplace.models.agent import RegisteredAgent
        inactive = RegisteredAgent(
            id="inactive-id", name="inactive-agent",
            agent_type="buyer", public_key="key", status="inactive",
        )
        db.add(inactive)
        await db.commit()

        query = Query()
        result = await query.agents(_make_info(db), status="active")

        assert all(a.status == "active" for a in result.items)
        assert result.page_info.total_count >= 1

    # 3
    async def test_agents_filter_by_agent_type(self, db: AsyncSession, make_agent):
        """agents(agent_type=...) should filter by agent type."""
        await make_agent(name="buyer-only", agent_type="buyer")
        await make_agent(name="seller-only", agent_type="seller")

        query = Query()
        result = await query.agents(_make_info(db), agent_type="buyer")

        assert all(a.agent_type == "buyer" for a in result.items)

    # 4
    async def test_agents_pagination_limit(self, db: AsyncSession, make_agent):
        """agents(limit=1) should return only one item."""
        await make_agent(name="page-a1")
        await make_agent(name="page-a2")

        query = Query()
        result = await query.agents(_make_info(db), limit=1)

        assert len(result.items) == 1
        assert result.page_info.has_next_page is True
        assert result.page_info.total_count == 2

    # 5
    async def test_agents_pagination_offset(self, db: AsyncSession, make_agent):
        """agents(offset=1) should skip the first result."""
        await make_agent(name="offset-a1")
        await make_agent(name="offset-a2")

        query = Query()
        result = await query.agents(_make_info(db), limit=10, offset=1)

        assert len(result.items) == 1
        assert result.page_info.has_previous_page is True

    # 6
    async def test_agents_empty_result(self, db: AsyncSession):
        """agents() with no agents should return empty items and total_count=0."""
        query = Query()
        result = await query.agents(_make_info(db))

        assert result.items == []
        assert result.page_info.total_count == 0
        assert result.page_info.has_next_page is False


class TestAgentQuery:
    """Tests 7-8: single agent query."""

    # 7
    async def test_agent_by_id(self, db: AsyncSession, make_agent):
        """agent(id=...) should return the matching agent."""
        agent, _ = await make_agent(name="single-agent")

        query = Query()
        result = await query.agent(_make_info(db), id=agent.id)

        assert result is not None
        assert result.id == agent.id
        assert result.name == "single-agent"

    # 8
    async def test_agent_missing_id_returns_none(self, db: AsyncSession):
        """agent(id=...) with nonexistent ID should return None."""
        query = Query()
        result = await query.agent(_make_info(db), id="nonexistent-id")

        assert result is None


class TestListingsQuery:
    """Tests 9-14: listings query with filters and pagination."""

    # 9
    async def test_listings_returns_all(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings() with no filters should return all listings."""
        seller, _ = await make_agent(name="listings-seller")
        await make_listing(seller.id, title="L1")
        await make_listing(seller.id, title="L2")

        query = Query()
        result = await query.listings(_make_info(db))

        assert result.page_info.total_count == 2

    # 10
    async def test_listings_filter_by_category(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings(category=...) should filter by category."""
        seller, _ = await make_agent(name="cat-seller")
        await make_listing(seller.id, category="web_search")
        await make_listing(seller.id, category="code_analysis")

        query = Query()
        result = await query.listings(_make_info(db), category="web_search")

        assert all(item.category == "web_search" for item in result.items)

    # 11
    async def test_listings_filter_by_status(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings(status=...) should filter by status."""
        seller, _ = await make_agent(name="status-seller")
        await make_listing(seller.id, status="active")
        await make_listing(seller.id, status="expired")

        query = Query()
        result = await query.listings(_make_info(db), status="active")

        assert all(item.status == "active" for item in result.items)

    # 12
    async def test_listings_filter_by_min_price(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings(min_price=...) should filter listings >= min_price."""
        seller, _ = await make_agent(name="price-seller")
        await make_listing(seller.id, price_usdc=0.5)
        await make_listing(seller.id, price_usdc=2.0)

        query = Query()
        result = await query.listings(_make_info(db), min_price=1.0)

        assert all(item.price_usdc >= 1.0 for item in result.items)
        assert result.page_info.total_count == 1

    # 13
    async def test_listings_filter_by_max_price(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings(max_price=...) should filter listings <= max_price."""
        seller, _ = await make_agent(name="max-price-seller")
        await make_listing(seller.id, price_usdc=0.5)
        await make_listing(seller.id, price_usdc=5.0)

        query = Query()
        result = await query.listings(_make_info(db), max_price=1.0)

        assert all(item.price_usdc <= 1.0 for item in result.items)
        assert result.page_info.total_count == 1

    # 14
    async def test_listings_pagination(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings with limit/offset should paginate correctly."""
        seller, _ = await make_agent(name="page-seller")
        await make_listing(seller.id, title="PL1")
        await make_listing(seller.id, title="PL2")
        await make_listing(seller.id, title="PL3")

        query = Query()
        result = await query.listings(_make_info(db), limit=2, offset=0)

        assert len(result.items) == 2
        assert result.page_info.has_next_page is True
        assert result.page_info.total_count == 3


class TestListingQuery:
    """Tests 15-16: single listing query."""

    # 15
    async def test_listing_by_id(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listing(id=...) should return the matching listing."""
        seller, _ = await make_agent(name="single-listing-seller")
        listing = await make_listing(seller.id, title="Single Listing")

        query = Query()
        result = await query.listing(_make_info(db), id=listing.id)

        assert result is not None
        assert result.id == listing.id
        assert result.title == "Single Listing"

    # 16
    async def test_listing_missing_id_returns_none(self, db: AsyncSession):
        """listing(id=...) with nonexistent ID should return None."""
        query = Query()
        result = await query.listing(_make_info(db), id="nonexistent")

        assert result is None


class TestTransactionsQuery:
    """Tests 17-20: transactions query with filters."""

    # 17
    async def test_transactions_returns_all(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """transactions() with no filters should return all transactions."""
        buyer, _ = await make_agent(name="tx-buyer")
        seller, _ = await make_agent(name="tx-seller")
        listing = await make_listing(seller.id)
        await make_transaction(buyer.id, seller.id, listing.id)

        query = Query()
        result = await query.transactions(_make_info(db))

        assert len(result) >= 1

    # 18
    async def test_transactions_filter_by_buyer(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """transactions(buyer_id=...) should filter by buyer."""
        buyer, _ = await make_agent(name="filter-buyer")
        seller, _ = await make_agent(name="filter-seller")
        listing = await make_listing(seller.id)
        await make_transaction(buyer.id, seller.id, listing.id)

        query = Query()
        result = await query.transactions(_make_info(db), buyer_id=buyer.id)

        assert all(t.buyer_id == buyer.id for t in result)

    # 19
    async def test_transactions_filter_by_seller(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """transactions(seller_id=...) should filter by seller."""
        buyer, _ = await make_agent(name="filter-buyer-2")
        seller, _ = await make_agent(name="filter-seller-2")
        listing = await make_listing(seller.id)
        await make_transaction(buyer.id, seller.id, listing.id)

        query = Query()
        result = await query.transactions(_make_info(db), seller_id=seller.id)

        assert all(t.seller_id == seller.id for t in result)

    # 20
    async def test_transactions_filter_by_status(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """transactions(status=...) should filter by status."""
        buyer, _ = await make_agent(name="status-buyer")
        seller, _ = await make_agent(name="status-seller")
        listing = await make_listing(seller.id)
        await make_transaction(buyer.id, seller.id, listing.id, status="completed")
        await make_transaction(buyer.id, seller.id, listing.id, status="pending")

        query = Query()
        result = await query.transactions(_make_info(db), status="completed")

        assert all(t.status == "completed" for t in result)


class TestWorkflowsQuery:
    """Tests 21-23: workflows query with filters."""

    # 21
    async def test_workflows_returns_all(self, db: AsyncSession, make_agent):
        """workflows() with no filters should return all workflows."""
        from marketplace.models.workflow import WorkflowDefinition

        owner, _ = await make_agent(name="wf-query-owner")
        wf = WorkflowDefinition(
            id="wf-q1", name="WF 1", graph_json="{}",
            owner_id=owner.id, version=1, status="draft",
        )
        db.add(wf)
        await db.commit()

        query = Query()
        result = await query.workflows(_make_info(db))

        assert len(result) >= 1
        assert any(w.name == "WF 1" for w in result)

    # 22
    async def test_workflows_filter_by_owner(self, db: AsyncSession, make_agent):
        """workflows(owner_id=...) should filter by owner."""
        from marketplace.models.workflow import WorkflowDefinition

        owner_a, _ = await make_agent(name="wf-owner-a")
        owner_b, _ = await make_agent(name="wf-owner-b")
        db.add(WorkflowDefinition(
            id="wf-a", name="WF A", graph_json="{}",
            owner_id=owner_a.id, version=1, status="draft",
        ))
        db.add(WorkflowDefinition(
            id="wf-b", name="WF B", graph_json="{}",
            owner_id=owner_b.id, version=1, status="draft",
        ))
        await db.commit()

        query = Query()
        result = await query.workflows(_make_info(db), owner_id=owner_a.id)

        assert all(w.owner_id == owner_a.id for w in result)

    # 23
    async def test_workflows_filter_by_status(self, db: AsyncSession, make_agent):
        """workflows(status=...) should filter by status."""
        from marketplace.models.workflow import WorkflowDefinition

        owner, _ = await make_agent(name="wf-status-owner")
        db.add(WorkflowDefinition(
            id="wf-draft", name="Draft WF", graph_json="{}",
            owner_id=owner.id, version=1, status="draft",
        ))
        db.add(WorkflowDefinition(
            id="wf-active", name="Active WF", graph_json="{}",
            owner_id=owner.id, version=1, status="active",
        ))
        await db.commit()

        query = Query()
        result = await query.workflows(_make_info(db), status="active")

        assert all(w.status == "active" for w in result)


class TestQueryHelperConverters:
    """Tests 24-25: ORM-to-GraphQL type converters."""

    # 24
    async def test_transaction_to_type_maps_fields(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """_transaction_to_type should map all Transaction fields."""
        buyer, _ = await make_agent(name="conv-buyer")
        seller, _ = await make_agent(name="conv-seller")
        listing = await make_listing(seller.id)
        txn = await make_transaction(buyer.id, seller.id, listing.id, amount_usdc=1.5)

        gql_type = _transaction_to_type(txn)

        assert gql_type.id == txn.id
        assert gql_type.buyer_id == buyer.id
        assert gql_type.seller_id == seller.id
        assert gql_type.amount_usdc == pytest.approx(1.5, abs=0.01)

    # 25
    async def test_workflow_to_type_defaults(self):
        """_workflow_to_type should handle None version/status gracefully."""
        from marketplace.models.workflow import WorkflowDefinition

        wf = WorkflowDefinition(
            id="wf-x", name="X", description=None,
            graph_json="{}", owner_id="o", version=None, status=None,
        )
        gql_type = _workflow_to_type(wf)

        assert gql_type.version == 1
        assert gql_type.status == "draft"
        assert gql_type.description == ""
