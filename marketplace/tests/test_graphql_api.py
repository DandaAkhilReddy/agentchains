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


class TestGraphQLDataLoaders:
    """Tests for DataLoader classes preventing N+1 queries."""

    @pytest.mark.asyncio
    async def test_agent_loader_init(self):
        from marketplace.graphql.dataloaders import AgentLoader
        db = AsyncMock()
        loader = AgentLoader(db)
        assert loader.db is db

    @pytest.mark.asyncio
    async def test_listing_loader_init(self):
        from marketplace.graphql.dataloaders import ListingLoader
        db = AsyncMock()
        loader = ListingLoader(db)
        assert loader.db is db

    @pytest.mark.asyncio
    async def test_agent_loader_missing_keys(self):
        from marketplace.graphql.dataloaders import AgentLoader
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        loader = AgentLoader(db)
        results = await loader.load(["id1", "id2"])
        assert results == [None, None]

    @pytest.mark.asyncio
    async def test_listing_loader_missing_keys(self):
        from marketplace.graphql.dataloaders import ListingLoader
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        loader = ListingLoader(db)
        results = await loader.load(["l1", "l2"])
        assert results == [None, None]

    @pytest.mark.asyncio
    async def test_agent_loader_preserves_order(self):
        from marketplace.graphql.dataloaders import AgentLoader
        agent1 = MagicMock(); agent1.id = "a1"
        agent2 = MagicMock(); agent2.id = "a2"
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [agent2, agent1]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        loader = AgentLoader(db)
        results = await loader.load(["a1", "a2"])
        assert results[0].id == "a1"
        assert results[1].id == "a2"


class TestGraphQLQueryResolvers:
    """Tests for query resolver module."""

    def test_query_class_exists(self):
        from marketplace.graphql.resolvers.queries import Query
        assert Query is not None

    def test_query_has_agents_field(self):
        from marketplace.graphql.resolvers.queries import Query
        assert hasattr(Query, "agents")

    def test_query_has_listings_field(self):
        from marketplace.graphql.resolvers.queries import Query
        assert hasattr(Query, "listings")

    def test_query_has_transactions_field(self):
        from marketplace.graphql.resolvers.queries import Query
        assert hasattr(Query, "transactions")

    def test_query_has_agent_field(self):
        from marketplace.graphql.resolvers.queries import Query
        assert hasattr(Query, "agent")

    def test_query_has_listing_field(self):
        from marketplace.graphql.resolvers.queries import Query
        assert hasattr(Query, "listing")

    def test_query_has_workflows_field(self):
        from marketplace.graphql.resolvers.queries import Query
        assert hasattr(Query, "workflows")


class TestGraphQLMutationResolvers:
    """Tests for mutation resolver module."""

    def test_mutation_class_exists(self):
        from marketplace.graphql.resolvers.mutations import Mutation
        assert Mutation is not None

    def test_mutation_has_create_agent(self):
        from marketplace.graphql.resolvers.mutations import Mutation
        assert hasattr(Mutation, "create_agent")

    def test_mutation_has_create_listing(self):
        from marketplace.graphql.resolvers.mutations import Mutation
        assert hasattr(Mutation, "create_listing")

    def test_mutation_has_create_workflow(self):
        from marketplace.graphql.resolvers.mutations import Mutation
        assert hasattr(Mutation, "create_workflow")


class TestGraphQLPagination:
    """Tests for pagination types."""

    def test_page_info_fields(self):
        from marketplace.graphql.schema import PageInfo
        pi = PageInfo(has_next_page=True, has_previous_page=False, total_count=100)
        assert pi.has_next_page is True
        assert pi.has_previous_page is False
        assert pi.total_count == 100

    def test_agent_connection_fields(self):
        from marketplace.graphql.schema import AgentConnection, AgentType, PageInfo
        agent = AgentType(id="1", name="A", description="", agent_type="buyer", status="active", created_at="")
        pi = PageInfo(has_next_page=False, has_previous_page=False, total_count=1)
        conn = AgentConnection(items=[agent], page_info=pi)
        assert len(conn.items) == 1
        assert conn.page_info.total_count == 1

    def test_listing_connection_fields(self):
        from marketplace.graphql.schema import ListingConnection, ListingType, PageInfo
        listing = ListingType(id="1", title="T", category="C", price_usdc=1.0, quality_score=0.5, status="active", seller_id="s1")
        pi = PageInfo(has_next_page=True, has_previous_page=True, total_count=50)
        conn = ListingConnection(items=[listing], page_info=pi)
        assert conn.page_info.has_next_page is True
        assert conn.page_info.has_previous_page is True

    def test_empty_connection(self):
        from marketplace.graphql.schema import AgentConnection, PageInfo
        pi = PageInfo(has_next_page=False, has_previous_page=False, total_count=0)
        conn = AgentConnection(items=[], page_info=pi)
        assert len(conn.items) == 0
        assert conn.page_info.total_count == 0


class TestGraphQLRouter:
    """Tests for the GraphQL router setup."""

    def test_graphql_router_exists(self):
        from marketplace.graphql.schema import graphql_router
        assert graphql_router is not None

    def test_schema_str_not_empty(self):
        from marketplace.graphql.schema import schema
        schema_str = schema.as_str()
        assert len(schema_str) > 100

    def test_schema_has_create_listing_mutation(self):
        from marketplace.graphql.schema import schema
        schema_str = schema.as_str()
        assert "createListing" in schema_str


class TestGraphQLHelperConversions:
    """Tests for ORM-to-GraphQL type conversion helpers."""

    def test_agent_to_type_conversion(self):
        from marketplace.graphql.schema import _agent_to_type
        agent = MagicMock()
        agent.id = "a1"; agent.name = "Test"; agent.description = "desc"
        agent.agent_type = "buyer"; agent.status = "active"; agent.created_at = None
        result = _agent_to_type(agent)
        assert result.id == "a1" and result.name == "Test"

    def test_listing_to_type_conversion(self):
        from marketplace.graphql.schema import _listing_to_type
        listing = MagicMock()
        listing.id = "l1"; listing.title = "Data"; listing.category = "NLP"
        listing.seller_id = "s1"; listing.price_usdc = 9.99
        listing.quality_score = 0.95; listing.status = "active"
        result = _listing_to_type(listing)
        assert result.title == "Data" and result.price_usdc == 9.99

    def test_transaction_to_type_conversion(self):
        from marketplace.graphql.schema import _transaction_to_type
        tx = MagicMock()
        tx.id = "t1"; tx.listing_id = "l1"; tx.buyer_id = "b1"; tx.seller_id = "s1"
        tx.amount_usdc = 25.0; tx.status = "completed"; tx.initiated_at = None
        result = _transaction_to_type(tx)
        assert result.amount_usdc == 25.0 and result.status == "completed"

    def test_agent_to_type_none_description(self):
        from marketplace.graphql.schema import _agent_to_type
        agent = MagicMock()
        agent.id = "a2"; agent.name = "X"; agent.description = None
        agent.agent_type = "seller"; agent.status = "active"; agent.created_at = None
        result = _agent_to_type(agent)
        assert result.description == ""

    def test_listing_to_type_none_quality(self):
        from marketplace.graphql.schema import _listing_to_type
        listing = MagicMock()
        listing.id = "l2"; listing.title = "T"; listing.category = "C"
        listing.seller_id = "s2"; listing.price_usdc = 1.0
        listing.quality_score = None; listing.status = "active"
        result = _listing_to_type(listing)
        assert result.quality_score == 0.0
