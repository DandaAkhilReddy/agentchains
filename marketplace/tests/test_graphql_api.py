"""GraphQL API tests — types, queries, mutations, and dataloader resolution."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest


class TestGraphQLTypes:
    """Tests for GraphQL Strawberry type definitions."""

    def test_agent_type_fields(self):
        from marketplace.graphql.schema import AgentType

        agent = AgentType(
            id="a1", name="Test Agent", description="desc",
            agent_type="buyer", status="active", created_at="2026-01-01",
        )
        assert agent.id == "a1"
        assert agent.name == "Test Agent"
        assert agent.agent_type == "buyer"
        assert agent.status == "active"

    def test_listing_type_fields(self):
        from marketplace.graphql.schema import ListingType

        listing = ListingType(
            id="l1", title="Dataset", category="NLP",
            price_usdc=9.99, quality_score=0.95,
            status="active", seller_id="s1",
        )
        assert listing.title == "Dataset"
        assert listing.price_usdc == 9.99
        assert listing.quality_score == 0.95

    def test_transaction_type_fields(self):
        from marketplace.graphql.schema import TransactionType

        tx = TransactionType(
            id="t1", listing_id="l1", buyer_id="b1", seller_id="s1",
            amount_usdc=25.0, status="completed", created_at="2026-01-01",
        )
        assert tx.amount_usdc == 25.0
        assert tx.status == "completed"
        assert tx.buyer_id == "b1"

    def test_agent_type_description(self):
        from marketplace.graphql.schema import AgentType

        agent = AgentType(
            id="a2", name="Agent", description="A helpful agent",
            agent_type="seller", status="active", created_at="2026-02-01",
        )
        assert agent.description == "A helpful agent"

    def test_listing_type_seller_id(self):
        from marketplace.graphql.schema import ListingType

        listing = ListingType(
            id="l2", title="Images", category="CV",
            price_usdc=5.0, quality_score=0.88,
            status="pending", seller_id="seller-42",
        )
        assert listing.seller_id == "seller-42"
        assert listing.status == "pending"


class TestGraphQLSchema:
    """Tests for the Strawberry schema object."""

    def test_schema_exists(self):
        from marketplace.graphql.schema import schema
        assert schema is not None

    def test_schema_has_query_type(self):
        from marketplace.graphql.schema import schema
        introspection = schema.as_str()
        assert "Query" in introspection

    def test_schema_has_mutation_type(self):
        from marketplace.graphql.schema import schema
        introspection = schema.as_str()
        assert "Mutation" in introspection

    def test_schema_has_agent_type(self):
        from marketplace.graphql.schema import schema
        introspection = schema.as_str()
        assert "AgentType" in introspection

    def test_schema_has_listing_type(self):
        from marketplace.graphql.schema import schema
        introspection = schema.as_str()
        assert "ListingType" in introspection

    def test_schema_has_transaction_type(self):
        from marketplace.graphql.schema import schema
        introspection = schema.as_str()
        assert "TransactionType" in introspection


class TestGraphQLResolvers:
    """Tests for query and mutation resolver imports."""

    def test_queries_module_imports(self):
        from marketplace.graphql.resolvers import queries
        assert queries is not None

    def test_mutations_module_imports(self):
        from marketplace.graphql.resolvers import mutations
        assert mutations is not None

    def test_dataloaders_module_imports(self):
        from marketplace.graphql import dataloaders
        assert dataloaders is not None


class TestGraphQLTypeConstructors:
    """Tests for constructing various type combinations."""

    def test_agent_type_with_empty_description(self):
        from marketplace.graphql.schema import AgentType

        agent = AgentType(
            id="a3", name="Agent", description="",
            agent_type="buyer", status="active", created_at="2026-01-01",
        )
        assert agent.description == ""

    def test_listing_with_zero_price(self):
        from marketplace.graphql.schema import ListingType

        listing = ListingType(
            id="l3", title="Free Dataset", category="Other",
            price_usdc=0.0, quality_score=0.5,
            status="active", seller_id="s1",
        )
        assert listing.price_usdc == 0.0

    def test_transaction_with_all_same_ids(self):
        from marketplace.graphql.schema import TransactionType

        tx = TransactionType(
            id="t2", listing_id="x", buyer_id="x", seller_id="x",
            amount_usdc=1.0, status="pending", created_at="2026-02-20",
        )
        assert tx.listing_id == tx.buyer_id == tx.seller_id

    def test_listing_high_quality_score(self):
        from marketplace.graphql.schema import ListingType

        listing = ListingType(
            id="l4", title="Premium", category="AI",
            price_usdc=999.99, quality_score=1.0,
            status="active", seller_id="s2",
        )
        assert listing.quality_score == 1.0

    def test_multiple_agents_are_independent(self):
        from marketplace.graphql.schema import AgentType

        a1 = AgentType(id="1", name="A", description="", agent_type="buyer", status="active", created_at="")
        a2 = AgentType(id="2", name="B", description="", agent_type="seller", status="inactive", created_at="")
        assert a1.id != a2.id
        assert a1.name != a2.name
        assert a1.agent_type != a2.agent_type
