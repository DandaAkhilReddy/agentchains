"""Comprehensive tests for GraphQL resolvers (mutations, queries) and dataloaders.

Covers:
- marketplace/graphql/resolvers/mutations.py  — create_agent, create_listing, create_workflow
- marketplace/graphql/resolvers/queries.py    — agents, agent, listings, listing,
                                                transactions, workflows
- marketplace/graphql/dataloaders.py          — AgentLoader, ListingLoader
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_info(db, user=None):
    """Build a minimal Strawberry info context mock."""
    info = MagicMock()
    info.context = {"db": db}
    if user is not None:
        info.context["user"] = user
    return info


def _new_id():
    return str(uuid.uuid4())


# ===========================================================================
# DATALOADER TESTS
# ===========================================================================

class TestAgentLoader:
    """Unit tests for AgentLoader batch-loading behaviour."""

    async def test_init_stores_db(self):
        from marketplace.graphql.dataloaders import AgentLoader

        db = AsyncMock()
        loader = AgentLoader(db)
        assert loader.db is db

    async def test_load_empty_keys_returns_empty_list(self):
        from marketplace.graphql.dataloaders import AgentLoader

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        loader = AgentLoader(db)
        results = await loader.load([])
        assert results == []

    async def test_load_all_missing_keys_returns_nones(self):
        from marketplace.graphql.dataloaders import AgentLoader

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        loader = AgentLoader(db)
        results = await loader.load(["missing-1", "missing-2", "missing-3"])
        assert results == [None, None, None]

    async def test_load_preserves_key_order(self):
        from marketplace.graphql.dataloaders import AgentLoader

        agent_a = MagicMock()
        agent_a.id = "id-a"
        agent_b = MagicMock()
        agent_b.id = "id-b"
        agent_c = MagicMock()
        agent_c.id = "id-c"

        # DB returns in arbitrary order (c, a, b)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [agent_c, agent_a, agent_b]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        loader = AgentLoader(db)
        results = await loader.load(["id-a", "id-b", "id-c"])

        assert results[0].id == "id-a"
        assert results[1].id == "id-b"
        assert results[2].id == "id-c"

    async def test_load_partial_hit_returns_none_for_missing(self):
        from marketplace.graphql.dataloaders import AgentLoader

        agent_x = MagicMock()
        agent_x.id = "id-x"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [agent_x]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        loader = AgentLoader(db)
        results = await loader.load(["id-x", "id-missing"])

        assert results[0].id == "id-x"
        assert results[1] is None

    async def test_load_issues_single_db_call_for_batch(self):
        """Confirms only one DB execute call is made regardless of key count."""
        from marketplace.graphql.dataloaders import AgentLoader

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        loader = AgentLoader(db)
        await loader.load(["k1", "k2", "k3", "k4", "k5"])

        assert db.execute.call_count == 1

    async def test_load_real_db_agents(self, db: AsyncSession, make_agent):
        """Integration: batch-loads real agents from the test database."""
        from marketplace.graphql.dataloaders import AgentLoader

        agent1, _ = await make_agent(name="loader-agent-1")
        agent2, _ = await make_agent(name="loader-agent-2")

        loader = AgentLoader(db)
        results = await loader.load([agent1.id, agent2.id])

        assert len(results) == 2
        result_ids = {r.id for r in results if r is not None}
        assert agent1.id in result_ids
        assert agent2.id in result_ids

    async def test_load_real_db_missing_id_returns_none(self, db: AsyncSession, make_agent):
        """Integration: missing ID yields None in real DB context."""
        from marketplace.graphql.dataloaders import AgentLoader

        agent, _ = await make_agent()
        loader = AgentLoader(db)
        results = await loader.load([agent.id, "nonexistent-id"])

        assert results[0] is not None
        assert results[0].id == agent.id
        assert results[1] is None


class TestListingLoader:
    """Unit tests for ListingLoader batch-loading behaviour."""

    async def test_init_stores_db(self):
        from marketplace.graphql.dataloaders import ListingLoader

        db = AsyncMock()
        loader = ListingLoader(db)
        assert loader.db is db

    async def test_load_empty_keys_returns_empty_list(self):
        from marketplace.graphql.dataloaders import ListingLoader

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        loader = ListingLoader(db)
        results = await loader.load([])
        assert results == []

    async def test_load_all_missing_keys_returns_nones(self):
        from marketplace.graphql.dataloaders import ListingLoader

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        loader = ListingLoader(db)
        results = await loader.load(["l1", "l2"])
        assert results == [None, None]

    async def test_load_preserves_key_order(self):
        from marketplace.graphql.dataloaders import ListingLoader

        listing_a = MagicMock()
        listing_a.id = "l-a"
        listing_b = MagicMock()
        listing_b.id = "l-b"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [listing_b, listing_a]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        loader = ListingLoader(db)
        results = await loader.load(["l-a", "l-b"])

        assert results[0].id == "l-a"
        assert results[1].id == "l-b"

    async def test_load_partial_hit(self):
        from marketplace.graphql.dataloaders import ListingLoader

        listing_found = MagicMock()
        listing_found.id = "l-found"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [listing_found]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        loader = ListingLoader(db)
        results = await loader.load(["l-found", "l-not-found"])

        assert results[0].id == "l-found"
        assert results[1] is None

    async def test_load_issues_single_db_call(self):
        from marketplace.graphql.dataloaders import ListingLoader

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        loader = ListingLoader(db)
        await loader.load(["l1", "l2", "l3"])

        assert db.execute.call_count == 1

    async def test_load_real_db_listings(self, db: AsyncSession, make_agent, make_listing):
        """Integration: loads real listings from the test database."""
        from marketplace.graphql.dataloaders import ListingLoader

        agent, _ = await make_agent()
        listing1 = await make_listing(seller_id=agent.id, price_usdc=1.0)
        listing2 = await make_listing(seller_id=agent.id, price_usdc=2.0)

        loader = ListingLoader(db)
        results = await loader.load([listing1.id, listing2.id])

        assert len(results) == 2
        result_ids = {r.id for r in results if r is not None}
        assert listing1.id in result_ids
        assert listing2.id in result_ids

    async def test_load_real_db_missing_listing_id(self, db: AsyncSession, make_agent, make_listing):
        """Integration: missing listing ID yields None in real DB context."""
        from marketplace.graphql.dataloaders import ListingLoader

        agent, _ = await make_agent()
        listing = await make_listing(seller_id=agent.id)

        loader = ListingLoader(db)
        results = await loader.load([listing.id, "does-not-exist"])

        assert results[0].id == listing.id
        assert results[1] is None


# ===========================================================================
# MUTATION RESOLVER TESTS
# ===========================================================================

class TestMutationHelpers:
    """Tests for ORM-to-GraphQL conversion helpers in mutations module."""

    def test_agent_to_type_basic(self):
        from marketplace.graphql.resolvers.mutations import _agent_to_type

        agent = MagicMock()
        agent.id = "a-001"
        agent.name = "Alpha"
        agent.description = "An alpha agent"
        agent.agent_type = "buyer"
        agent.status = "active"
        agent.created_at = None

        result = _agent_to_type(agent)

        assert result.id == "a-001"
        assert result.name == "Alpha"
        assert result.description == "An alpha agent"
        assert result.agent_type == "buyer"
        assert result.status == "active"
        assert result.created_at == ""

    def test_agent_to_type_none_description_defaults_to_empty_string(self):
        from marketplace.graphql.resolvers.mutations import _agent_to_type

        agent = MagicMock()
        agent.id = "a-002"
        agent.name = "Beta"
        agent.description = None
        agent.agent_type = "seller"
        agent.status = "inactive"
        agent.created_at = None

        result = _agent_to_type(agent)
        assert result.description == ""

    def test_agent_to_type_with_created_at(self):
        from datetime import datetime, timezone
        from marketplace.graphql.resolvers.mutations import _agent_to_type

        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        agent = MagicMock()
        agent.id = "a-003"
        agent.name = "Gamma"
        agent.description = ""
        agent.agent_type = "both"
        agent.status = "active"
        agent.created_at = dt

        result = _agent_to_type(agent)
        assert "2026-01-15" in result.created_at

    def test_listing_to_type_basic(self):
        from marketplace.graphql.resolvers.mutations import _listing_to_type

        listing = MagicMock()
        listing.id = "l-001"
        listing.seller_id = "s-001"
        listing.title = "Test Dataset"
        listing.category = "NLP"
        listing.price_usdc = Decimal("9.99")
        listing.quality_score = Decimal("0.88")
        listing.status = "active"

        result = _listing_to_type(listing)

        assert result.id == "l-001"
        assert result.seller_id == "s-001"
        assert result.title == "Test Dataset"
        assert result.category == "NLP"
        assert result.price_usdc == pytest.approx(9.99)
        assert result.quality_score == pytest.approx(0.88)
        assert result.status == "active"

    def test_listing_to_type_none_quality_score_defaults_to_zero(self):
        from marketplace.graphql.resolvers.mutations import _listing_to_type

        listing = MagicMock()
        listing.id = "l-002"
        listing.seller_id = "s-002"
        listing.title = "No Quality"
        listing.category = "Other"
        listing.price_usdc = Decimal("1.00")
        listing.quality_score = None
        listing.status = "active"

        result = _listing_to_type(listing)
        assert result.quality_score == 0.0

    def test_workflow_to_type_basic(self):
        from marketplace.graphql.resolvers.mutations import _workflow_to_type

        wf = MagicMock()
        wf.id = "wf-001"
        wf.name = "ETL Pipeline"
        wf.description = "A workflow"
        wf.owner_id = "owner-001"
        wf.version = 3
        wf.status = "active"

        result = _workflow_to_type(wf)

        assert result.id == "wf-001"
        assert result.name == "ETL Pipeline"
        assert result.description == "A workflow"
        assert result.owner_id == "owner-001"
        assert result.version == 3
        assert result.status == "active"

    def test_workflow_to_type_none_version_defaults_to_one(self):
        from marketplace.graphql.resolvers.mutations import _workflow_to_type

        wf = MagicMock()
        wf.id = "wf-002"
        wf.name = "Draft Workflow"
        wf.description = None
        wf.owner_id = "owner-002"
        wf.version = None
        wf.status = None

        result = _workflow_to_type(wf)
        assert result.version == 1
        assert result.status == "draft"
        assert result.description == ""

    def test_workflow_to_type_none_description_defaults_to_empty(self):
        from marketplace.graphql.resolvers.mutations import _workflow_to_type

        wf = MagicMock()
        wf.id = "wf-003"
        wf.name = "No Desc"
        wf.description = None
        wf.owner_id = "owner-003"
        wf.version = 1
        wf.status = "draft"

        result = _workflow_to_type(wf)
        assert result.description == ""


class TestCreateAgentMutation:
    """Tests for the create_agent mutation resolver."""

    async def test_create_agent_happy_path(self, db: AsyncSession):
        """create_agent inserts an agent and returns the correct AgentType."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_agent(
            info=info,
            name="Test Agent Alpha",
            agent_type="buyer",
            description="A test buyer agent",
            public_key="ssh-rsa AAAA_placeholder",
        )

        assert result.name == "Test Agent Alpha"
        assert result.agent_type == "buyer"
        assert result.description == "A test buyer agent"
        assert result.status == "active"
        assert result.id is not None
        # ID should be a valid UUID format
        assert len(result.id) == 36

    async def test_create_agent_defaults_description_and_public_key(self, db: AsyncSession):
        """create_agent uses empty string defaults for optional fields."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_agent(
            info=info,
            name="Minimal Agent",
            agent_type="seller",
        )

        assert result.name == "Minimal Agent"
        assert result.agent_type == "seller"
        assert result.description == ""
        assert result.status == "active"

    async def test_create_agent_returns_unique_ids(self, db: AsyncSession):
        """Two consecutive create_agent calls produce distinct IDs."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        info = _make_info(db)

        r1 = await mutation.create_agent(info=info, name="Agent One", agent_type="buyer")
        r2 = await mutation.create_agent(info=info, name="Agent Two", agent_type="seller")

        assert r1.id != r2.id

    async def test_create_agent_persists_to_db(self, db: AsyncSession):
        """Agent created via the mutation is retrievable from the database."""
        from marketplace.graphql.resolvers.mutations import Mutation
        from marketplace.models.agent import RegisteredAgent
        from sqlalchemy import select

        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_agent(
            info=info,
            name="Persistent Agent",
            agent_type="both",
        )

        # Verify we can read it back from the DB
        db_result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.id == result.id)
        )
        agent_row = db_result.scalar_one_or_none()
        assert agent_row is not None
        assert agent_row.name == "Persistent Agent"

    async def test_create_agent_db_commit_error_propagates(self):
        """If db.commit raises, the exception propagates out of create_agent."""
        from marketplace.graphql.resolvers.mutations import Mutation

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock(side_effect=RuntimeError("db commit failed"))

        mutation = Mutation()
        info = _make_info(db)

        with pytest.raises(RuntimeError, match="db commit failed"):
            await mutation.create_agent(info=info, name="Doomed Agent", agent_type="buyer")


class TestCreateListingMutation:
    """Tests for the create_listing mutation resolver."""

    async def test_create_listing_happy_path(self, db: AsyncSession):
        """create_listing inserts a listing and returns a ListingType."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        user = {"id": "seller-" + _new_id()}
        info = _make_info(db, user=user)

        result = await mutation.create_listing(
            info=info,
            title="Curated NLP Dataset",
            category="NLP",
            price_usdc=19.99,
            content="some content data",
        )

        assert result.title == "Curated NLP Dataset"
        assert result.category == "NLP"
        assert result.price_usdc == pytest.approx(19.99)
        assert result.status == "active"
        assert result.seller_id == user["id"]

    async def test_create_listing_uses_user_id_as_seller(self, db: AsyncSession):
        """seller_id is taken from info.context['user']['id']."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        expected_seller = "agent-abc123"
        info = _make_info(db, user={"id": expected_seller})

        result = await mutation.create_listing(
            info=info,
            title="Some Listing",
            category="CV",
            price_usdc=5.0,
        )

        assert result.seller_id == expected_seller

    async def test_create_listing_no_user_generates_placeholder_seller(self, db: AsyncSession):
        """Without a user in context, a random UUID is used as seller_id."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        info = _make_info(db)  # no user key

        result = await mutation.create_listing(
            info=info,
            title="Anon Listing",
            category="Other",
            price_usdc=1.0,
        )

        assert result.seller_id is not None
        # Should be a UUID-ish string
        assert len(result.seller_id) == 36

    async def test_create_listing_returns_unique_ids(self, db: AsyncSession):
        """Two listings created in sequence have different IDs."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        info = _make_info(db)

        r1 = await mutation.create_listing(info=info, title="L1", category="A", price_usdc=1.0)
        r2 = await mutation.create_listing(info=info, title="L2", category="B", price_usdc=2.0)

        assert r1.id != r2.id

    async def test_create_listing_persists_to_db(self, db: AsyncSession):
        """Listing created via mutation is readable from the database."""
        from marketplace.graphql.resolvers.mutations import Mutation
        from marketplace.models.listing import DataListing
        from sqlalchemy import select

        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_listing(
            info=info,
            title="DB Persist Listing",
            category="Storage",
            price_usdc=3.50,
        )

        db_result = await db.execute(
            select(DataListing).where(DataListing.id == result.id)
        )
        listing_row = db_result.scalar_one_or_none()
        assert listing_row is not None
        assert listing_row.title == "DB Persist Listing"

    async def test_create_listing_content_hash_set(self, db: AsyncSession):
        """create_listing computes a SHA-256 content hash and stores it."""
        import hashlib
        from marketplace.graphql.resolvers.mutations import Mutation
        from marketplace.models.listing import DataListing
        from sqlalchemy import select

        mutation = Mutation()
        info = _make_info(db)
        content = "some meaningful content"

        result = await mutation.create_listing(
            info=info,
            title="Hash Test",
            category="Test",
            price_usdc=0.5,
            content=content,
        )

        db_result = await db.execute(
            select(DataListing).where(DataListing.id == result.id)
        )
        listing_row = db_result.scalar_one_or_none()
        expected_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert listing_row.content_hash == expected_hash

    async def test_create_listing_db_commit_error_propagates(self):
        """If db.commit raises, it propagates from create_listing."""
        from marketplace.graphql.resolvers.mutations import Mutation

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock(side_effect=Exception("disk full"))

        mutation = Mutation()
        info = _make_info(db)

        with pytest.raises(Exception, match="disk full"):
            await mutation.create_listing(
                info=info, title="Failing Listing", category="X", price_usdc=1.0
            )


class TestCreateWorkflowMutation:
    """Tests for the create_workflow mutation resolver."""

    async def test_create_workflow_happy_path(self, db: AsyncSession):
        """create_workflow persists a workflow and returns a WorkflowType."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        user = {"id": "owner-" + _new_id()}
        info = _make_info(db, user=user)

        result = await mutation.create_workflow(
            info=info,
            name="My ETL Workflow",
            graph_json='{"nodes": [], "edges": []}',
            description="A sample ETL workflow",
        )

        assert result.name == "My ETL Workflow"
        assert result.description == "A sample ETL workflow"
        assert result.owner_id == user["id"]
        assert result.version == 1
        assert result.status == "draft"

    async def test_create_workflow_uses_user_id_as_owner(self, db: AsyncSession):
        """owner_id is taken from info.context['user']['id']."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        expected_owner = "agent-workflow-owner"
        info = _make_info(db, user={"id": expected_owner})

        result = await mutation.create_workflow(
            info=info,
            name="Owned Workflow",
            graph_json="{}",
        )

        assert result.owner_id == expected_owner

    async def test_create_workflow_no_user_generates_placeholder_owner(self, db: AsyncSession):
        """Without user context, a random UUID is used as owner_id."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        info = _make_info(db)  # no user

        result = await mutation.create_workflow(
            info=info,
            name="Anonymous Workflow",
            graph_json="{}",
        )

        assert result.owner_id is not None
        assert len(result.owner_id) == 36

    async def test_create_workflow_defaults_description(self, db: AsyncSession):
        """create_workflow uses empty string for description when omitted."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_workflow(
            info=info,
            name="No Desc",
            graph_json="{}",
        )

        assert result.description == ""

    async def test_create_workflow_persists_to_db(self, db: AsyncSession):
        """Workflow created via mutation is readable from the database."""
        from marketplace.graphql.resolvers.mutations import Mutation
        from marketplace.models.workflow import WorkflowDefinition
        from sqlalchemy import select

        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_workflow(
            info=info,
            name="Persisted Workflow",
            graph_json='{"steps": 3}',
        )

        db_result = await db.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.id == result.id)
        )
        wf_row = db_result.scalar_one_or_none()
        assert wf_row is not None
        assert wf_row.name == "Persisted Workflow"
        assert wf_row.graph_json == '{"steps": 3}'

    async def test_create_workflow_initial_status_is_draft(self, db: AsyncSession):
        """Newly created workflows always have status='draft'."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_workflow(
            info=info,
            name="Draft Check",
            graph_json="{}",
        )

        assert result.status == "draft"

    async def test_create_workflow_initial_version_is_one(self, db: AsyncSession):
        """Newly created workflows always have version=1."""
        from marketplace.graphql.resolvers.mutations import Mutation

        mutation = Mutation()
        info = _make_info(db)

        result = await mutation.create_workflow(
            info=info,
            name="Version Check",
            graph_json="{}",
        )

        assert result.version == 1

    async def test_create_workflow_db_error_propagates(self):
        """DB errors propagate out of create_workflow."""
        from marketplace.graphql.resolvers.mutations import Mutation

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock(side_effect=RuntimeError("connection lost"))

        mutation = Mutation()
        info = _make_info(db)

        with pytest.raises(RuntimeError, match="connection lost"):
            await mutation.create_workflow(info=info, name="Error Workflow", graph_json="{}")


# ===========================================================================
# QUERY RESOLVER TESTS
# ===========================================================================

class TestQueryHelpers:
    """Tests for ORM-to-type conversion helpers in the queries module."""

    def test_agent_to_type_conversion(self):
        from marketplace.graphql.resolvers.queries import _agent_to_type

        agent = MagicMock()
        agent.id = "q-a-001"
        agent.name = "Query Agent"
        agent.description = "desc"
        agent.agent_type = "seller"
        agent.status = "active"
        agent.created_at = None

        result = _agent_to_type(agent)
        assert result.id == "q-a-001"
        assert result.name == "Query Agent"
        assert result.created_at == ""

    def test_agent_to_type_none_description(self):
        from marketplace.graphql.resolvers.queries import _agent_to_type

        agent = MagicMock()
        agent.id = "q-a-002"
        agent.name = "No Desc Agent"
        agent.description = None
        agent.agent_type = "buyer"
        agent.status = "inactive"
        agent.created_at = None

        result = _agent_to_type(agent)
        assert result.description == ""

    def test_listing_to_type_conversion(self):
        from marketplace.graphql.resolvers.queries import _listing_to_type

        listing = MagicMock()
        listing.id = "q-l-001"
        listing.seller_id = "q-s-001"
        listing.title = "Query Listing"
        listing.category = "Finance"
        listing.price_usdc = Decimal("15.50")
        listing.quality_score = Decimal("0.92")
        listing.status = "active"

        result = _listing_to_type(listing)
        assert result.price_usdc == pytest.approx(15.50)
        assert result.quality_score == pytest.approx(0.92)

    def test_listing_to_type_none_quality_score(self):
        from marketplace.graphql.resolvers.queries import _listing_to_type

        listing = MagicMock()
        listing.id = "q-l-002"
        listing.seller_id = "q-s-002"
        listing.title = "No Quality"
        listing.category = "Test"
        listing.price_usdc = Decimal("1.00")
        listing.quality_score = None
        listing.status = "pending"

        result = _listing_to_type(listing)
        assert result.quality_score == 0.0

    def test_transaction_to_type_conversion(self):
        from marketplace.graphql.resolvers.queries import _transaction_to_type

        txn = MagicMock()
        txn.id = "q-t-001"
        txn.listing_id = "q-l-001"
        txn.buyer_id = "q-b-001"
        txn.seller_id = "q-s-001"
        txn.amount_usdc = Decimal("50.00")
        txn.status = "completed"
        txn.initiated_at = None

        result = _transaction_to_type(txn)
        assert result.amount_usdc == pytest.approx(50.0)
        assert result.status == "completed"
        assert result.created_at == ""

    def test_workflow_to_type_defaults(self):
        from marketplace.graphql.resolvers.queries import _workflow_to_type

        wf = MagicMock()
        wf.id = "q-wf-001"
        wf.name = "Query WF"
        wf.description = None
        wf.owner_id = "q-owner-001"
        wf.version = None
        wf.status = None

        result = _workflow_to_type(wf)
        assert result.description == ""
        assert result.version == 1
        assert result.status == "draft"


class TestAgentsQuery:
    """Tests for the agents() query resolver."""

    async def test_agents_returns_all_when_no_filters(self, db: AsyncSession, make_agent):
        """agents() returns all agents when no filter args are given."""
        from marketplace.graphql.resolvers.queries import Query

        a1, _ = await make_agent(name="agent-q-1", agent_type="buyer")
        a2, _ = await make_agent(name="agent-q-2", agent_type="seller")

        query = Query()
        info = _make_info(db)
        result = await query.agents(info=info)

        assert result.page_info.total_count >= 2
        names = {item.name for item in result.items}
        assert "agent-q-1" in names
        assert "agent-q-2" in names

    async def test_agents_filters_by_status(self, db: AsyncSession, make_agent):
        """agents(status=...) returns only agents with matching status."""
        from marketplace.graphql.resolvers.queries import Query

        a_active, _ = await make_agent(name="active-agent")
        # Directly mutate status to 'inactive' in the DB
        a_active.status = "inactive"
        db.add(a_active)
        await db.commit()

        await make_agent(name="active-only-agent")

        query = Query()
        info = _make_info(db)

        result = await query.agents(info=info, status="inactive")
        assert result.page_info.total_count >= 1
        for item in result.items:
            assert item.status == "inactive"

    async def test_agents_filters_by_agent_type(self, db: AsyncSession, make_agent):
        """agents(agent_type=...) returns only agents with matching type."""
        from marketplace.graphql.resolvers.queries import Query

        await make_agent(name="buyer-only", agent_type="buyer")
        await make_agent(name="seller-only", agent_type="seller")

        query = Query()
        info = _make_info(db)

        result = await query.agents(info=info, agent_type="buyer")
        for item in result.items:
            assert item.agent_type == "buyer"

    async def test_agents_pagination_limit(self, db: AsyncSession, make_agent):
        """agents(limit=1) returns at most 1 item."""
        from marketplace.graphql.resolvers.queries import Query

        await make_agent(name="pager-1")
        await make_agent(name="pager-2")
        await make_agent(name="pager-3")

        query = Query()
        info = _make_info(db)

        result = await query.agents(info=info, limit=1)
        assert len(result.items) == 1

    async def test_agents_pagination_offset(self, db: AsyncSession, make_agent):
        """agents(offset=1) skips the first result."""
        from marketplace.graphql.resolvers.queries import Query

        await make_agent(name="offset-0")
        await make_agent(name="offset-1")

        query = Query()
        info = _make_info(db)

        full_result = await query.agents(info=info, limit=100)
        offset_result = await query.agents(info=info, offset=1, limit=100)

        assert len(offset_result.items) == len(full_result.items) - 1

    async def test_agents_page_info_has_next_page_true(self, db: AsyncSession, make_agent):
        """has_next_page is True when there are more items than limit."""
        from marketplace.graphql.resolvers.queries import Query

        await make_agent(name="next-1")
        await make_agent(name="next-2")
        await make_agent(name="next-3")

        query = Query()
        info = _make_info(db)

        result = await query.agents(info=info, limit=1, offset=0)
        assert result.page_info.has_next_page is True

    async def test_agents_page_info_has_previous_page(self, db: AsyncSession, make_agent):
        """has_previous_page is True when offset > 0."""
        from marketplace.graphql.resolvers.queries import Query

        await make_agent(name="prev-1")
        await make_agent(name="prev-2")

        query = Query()
        info = _make_info(db)

        result = await query.agents(info=info, offset=1)
        assert result.page_info.has_previous_page is True

    async def test_agents_empty_db_returns_empty_connection(self, db: AsyncSession):
        """agents() returns an empty connection when no agents exist."""
        from marketplace.graphql.resolvers.queries import Query

        query = Query()
        info = _make_info(db)

        result = await query.agents(info=info)
        assert result.page_info.total_count == 0
        assert result.items == []


class TestAgentQuery:
    """Tests for the agent(id) query resolver."""

    async def test_agent_returns_correct_agent(self, db: AsyncSession, make_agent):
        """agent(id=...) returns the matching agent."""
        from marketplace.graphql.resolvers.queries import Query

        created, _ = await make_agent(name="specific-agent", agent_type="both")

        query = Query()
        info = _make_info(db)

        result = await query.agent(info=info, id=created.id)

        assert result is not None
        assert result.id == created.id
        assert result.name == "specific-agent"

    async def test_agent_returns_none_for_missing_id(self, db: AsyncSession):
        """agent(id=...) returns None when the ID does not exist."""
        from marketplace.graphql.resolvers.queries import Query

        query = Query()
        info = _make_info(db)

        result = await query.agent(info=info, id="nonexistent-agent-id")
        assert result is None

    async def test_agent_does_not_return_other_agents(self, db: AsyncSession, make_agent):
        """agent(id=...) returns only the requested agent, not others."""
        from marketplace.graphql.resolvers.queries import Query

        a1, _ = await make_agent(name="agent-isolate-1")
        a2, _ = await make_agent(name="agent-isolate-2")

        query = Query()
        info = _make_info(db)

        result = await query.agent(info=info, id=a1.id)
        assert result.id == a1.id
        assert result.name != "agent-isolate-2"


class TestListingsQuery:
    """Tests for the listings() query resolver."""

    async def test_listings_returns_all_when_no_filters(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings() returns all listings with no filters applied."""
        from marketplace.graphql.resolvers.queries import Query

        agent, _ = await make_agent()
        l1 = await make_listing(seller_id=agent.id, price_usdc=1.0, category="NLP")
        l2 = await make_listing(seller_id=agent.id, price_usdc=2.0, category="CV")

        query = Query()
        info = _make_info(db)

        result = await query.listings(info=info)
        assert result.page_info.total_count >= 2
        ids = {item.id for item in result.items}
        assert l1.id in ids
        assert l2.id in ids

    async def test_listings_filters_by_category(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings(category=...) returns only listings in that category."""
        from marketplace.graphql.resolvers.queries import Query

        agent, _ = await make_agent()
        await make_listing(seller_id=agent.id, category="NLP")
        await make_listing(seller_id=agent.id, category="CV")

        query = Query()
        info = _make_info(db)

        result = await query.listings(info=info, category="NLP")
        for item in result.items:
            assert item.category == "NLP"

    async def test_listings_filters_by_status(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings(status=...) returns only listings with matching status."""
        from marketplace.graphql.resolvers.queries import Query

        agent, _ = await make_agent()
        await make_listing(seller_id=agent.id, status="active")
        await make_listing(seller_id=agent.id, status="inactive")

        query = Query()
        info = _make_info(db)

        result = await query.listings(info=info, status="inactive")
        for item in result.items:
            assert item.status == "inactive"

    async def test_listings_filters_by_min_price(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings(min_price=...) excludes cheaper listings."""
        from marketplace.graphql.resolvers.queries import Query

        agent, _ = await make_agent()
        await make_listing(seller_id=agent.id, price_usdc=0.50)
        await make_listing(seller_id=agent.id, price_usdc=10.00)

        query = Query()
        info = _make_info(db)

        result = await query.listings(info=info, min_price=5.0)
        for item in result.items:
            assert item.price_usdc >= 5.0

    async def test_listings_filters_by_max_price(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings(max_price=...) excludes more expensive listings."""
        from marketplace.graphql.resolvers.queries import Query

        agent, _ = await make_agent()
        await make_listing(seller_id=agent.id, price_usdc=1.00)
        await make_listing(seller_id=agent.id, price_usdc=100.00)

        query = Query()
        info = _make_info(db)

        result = await query.listings(info=info, max_price=10.0)
        for item in result.items:
            assert item.price_usdc <= 10.0

    async def test_listings_filters_by_price_range(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings(min_price, max_price) returns only listings in that range."""
        from marketplace.graphql.resolvers.queries import Query

        agent, _ = await make_agent()
        await make_listing(seller_id=agent.id, price_usdc=1.0)
        target = await make_listing(seller_id=agent.id, price_usdc=5.0)
        await make_listing(seller_id=agent.id, price_usdc=20.0)

        query = Query()
        info = _make_info(db)

        result = await query.listings(info=info, min_price=3.0, max_price=10.0)
        ids = [item.id for item in result.items]
        assert target.id in ids
        for item in result.items:
            assert 3.0 <= item.price_usdc <= 10.0

    async def test_listings_pagination_limit(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listings(limit=1) returns at most 1 item."""
        from marketplace.graphql.resolvers.queries import Query

        agent, _ = await make_agent()
        await make_listing(seller_id=agent.id)
        await make_listing(seller_id=agent.id)

        query = Query()
        info = _make_info(db)

        result = await query.listings(info=info, limit=1)
        assert len(result.items) == 1

    async def test_listings_empty_db_returns_empty_connection(self, db: AsyncSession):
        """listings() with no data returns an empty connection."""
        from marketplace.graphql.resolvers.queries import Query

        query = Query()
        info = _make_info(db)

        result = await query.listings(info=info)
        assert result.page_info.total_count == 0
        assert result.items == []


class TestListingQuery:
    """Tests for the listing(id) query resolver."""

    async def test_listing_returns_correct_listing(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listing(id=...) returns the correct listing."""
        from marketplace.graphql.resolvers.queries import Query

        agent, _ = await make_agent()
        created = await make_listing(seller_id=agent.id, title="Specific Listing")

        query = Query()
        info = _make_info(db)

        result = await query.listing(info=info, id=created.id)

        assert result is not None
        assert result.id == created.id
        assert result.title == "Specific Listing"

    async def test_listing_returns_none_for_missing_id(self, db: AsyncSession):
        """listing(id=...) returns None when the ID does not exist."""
        from marketplace.graphql.resolvers.queries import Query

        query = Query()
        info = _make_info(db)

        result = await query.listing(info=info, id="does-not-exist")
        assert result is None

    async def test_listing_does_not_return_other_listings(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """listing(id=...) returns only the requested listing."""
        from marketplace.graphql.resolvers.queries import Query

        agent, _ = await make_agent()
        l1 = await make_listing(seller_id=agent.id, title="Listing One")
        l2 = await make_listing(seller_id=agent.id, title="Listing Two")

        query = Query()
        info = _make_info(db)

        result = await query.listing(info=info, id=l1.id)
        assert result.id == l1.id
        assert result.title != "Listing Two"


class TestTransactionsQuery:
    """Tests for the transactions() query resolver."""

    async def test_transactions_returns_all_when_no_filters(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """transactions() returns all transactions when no filters are given."""
        from marketplace.graphql.resolvers.queries import Query

        buyer, _ = await make_agent(agent_type="buyer")
        seller, _ = await make_agent(agent_type="seller")
        listing = await make_listing(seller_id=seller.id)

        tx1 = await make_transaction(buyer_id=buyer.id, seller_id=seller.id, listing_id=listing.id)
        tx2 = await make_transaction(buyer_id=buyer.id, seller_id=seller.id, listing_id=listing.id)

        query = Query()
        info = _make_info(db)

        result = await query.transactions(info=info)
        ids = {t.id for t in result}
        assert tx1.id in ids
        assert tx2.id in ids

    async def test_transactions_filters_by_buyer_id(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """transactions(buyer_id=...) returns only matching transactions."""
        from marketplace.graphql.resolvers.queries import Query

        buyer_a, _ = await make_agent(name="buyer-a")
        buyer_b, _ = await make_agent(name="buyer-b")
        seller, _ = await make_agent(agent_type="seller")
        listing = await make_listing(seller_id=seller.id)

        await make_transaction(buyer_id=buyer_a.id, seller_id=seller.id, listing_id=listing.id)
        await make_transaction(buyer_id=buyer_b.id, seller_id=seller.id, listing_id=listing.id)

        query = Query()
        info = _make_info(db)

        result = await query.transactions(info=info, buyer_id=buyer_a.id)
        assert len(result) >= 1
        for t in result:
            assert t.buyer_id == buyer_a.id

    async def test_transactions_filters_by_seller_id(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """transactions(seller_id=...) returns only matching transactions."""
        from marketplace.graphql.resolvers.queries import Query

        buyer, _ = await make_agent(agent_type="buyer")
        seller_a, _ = await make_agent(name="seller-a")
        seller_b, _ = await make_agent(name="seller-b")
        listing_a = await make_listing(seller_id=seller_a.id)
        listing_b = await make_listing(seller_id=seller_b.id)

        await make_transaction(buyer_id=buyer.id, seller_id=seller_a.id, listing_id=listing_a.id)
        await make_transaction(buyer_id=buyer.id, seller_id=seller_b.id, listing_id=listing_b.id)

        query = Query()
        info = _make_info(db)

        result = await query.transactions(info=info, seller_id=seller_a.id)
        assert len(result) >= 1
        for t in result:
            assert t.seller_id == seller_a.id

    async def test_transactions_filters_by_status(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """transactions(status=...) returns only transactions with that status."""
        from marketplace.graphql.resolvers.queries import Query

        buyer, _ = await make_agent(agent_type="buyer")
        seller, _ = await make_agent(agent_type="seller")
        listing = await make_listing(seller_id=seller.id)

        await make_transaction(
            buyer_id=buyer.id, seller_id=seller.id, listing_id=listing.id, status="completed"
        )
        await make_transaction(
            buyer_id=buyer.id, seller_id=seller.id, listing_id=listing.id, status="pending"
        )

        query = Query()
        info = _make_info(db)

        result = await query.transactions(info=info, status="completed")
        for t in result:
            assert t.status == "completed"

    async def test_transactions_empty_returns_empty_list(self, db: AsyncSession):
        """transactions() with no data returns an empty list."""
        from marketplace.graphql.resolvers.queries import Query

        query = Query()
        info = _make_info(db)

        result = await query.transactions(info=info)
        assert result == []

    async def test_transactions_pagination_limit(
        self, db: AsyncSession, make_agent, make_listing, make_transaction
    ):
        """transactions(limit=1) returns at most 1 transaction."""
        from marketplace.graphql.resolvers.queries import Query

        buyer, _ = await make_agent(agent_type="buyer")
        seller, _ = await make_agent(agent_type="seller")
        listing = await make_listing(seller_id=seller.id)

        await make_transaction(buyer_id=buyer.id, seller_id=seller.id, listing_id=listing.id)
        await make_transaction(buyer_id=buyer.id, seller_id=seller.id, listing_id=listing.id)

        query = Query()
        info = _make_info(db)

        result = await query.transactions(info=info, limit=1)
        assert len(result) == 1


class TestWorkflowsQuery:
    """Tests for the workflows() query resolver."""

    async def test_workflows_returns_all_when_no_filters(self, db: AsyncSession, make_agent):
        """workflows() returns all workflows with no filters applied."""
        from marketplace.graphql.resolvers.queries import Query
        from marketplace.graphql.resolvers.mutations import Mutation

        agent, _ = await make_agent()
        info = _make_info(db, user={"id": agent.id})

        mutation = Mutation()
        await mutation.create_workflow(info=info, name="WF One", graph_json="{}")
        await mutation.create_workflow(info=info, name="WF Two", graph_json="{}")

        query = Query()
        result = await query.workflows(info=info)

        names = {wf.name for wf in result}
        assert "WF One" in names
        assert "WF Two" in names

    async def test_workflows_filters_by_owner_id(self, db: AsyncSession, make_agent):
        """workflows(owner_id=...) returns only workflows with matching owner."""
        from marketplace.graphql.resolvers.queries import Query
        from marketplace.graphql.resolvers.mutations import Mutation

        agent_a, _ = await make_agent(name="owner-a")
        agent_b, _ = await make_agent(name="owner-b")

        info_a = _make_info(db, user={"id": agent_a.id})
        info_b = _make_info(db, user={"id": agent_b.id})

        mutation = Mutation()
        await mutation.create_workflow(info=info_a, name="A Workflow", graph_json="{}")
        await mutation.create_workflow(info=info_b, name="B Workflow", graph_json="{}")

        query = Query()
        info = _make_info(db)
        result = await query.workflows(info=info, owner_id=agent_a.id)

        assert len(result) >= 1
        for wf in result:
            assert wf.owner_id == agent_a.id

    async def test_workflows_filters_by_status(self, db: AsyncSession, make_agent):
        """workflows(status=...) returns only workflows with matching status."""
        from marketplace.graphql.resolvers.queries import Query
        from marketplace.models.workflow import WorkflowDefinition
        from sqlalchemy import select

        agent, _ = await make_agent()
        info = _make_info(db, user={"id": agent.id})

        from marketplace.graphql.resolvers.mutations import Mutation
        mutation = Mutation()
        wf = await mutation.create_workflow(info=info, name="Draft WF", graph_json="{}")

        # Verify the workflow was created with draft status
        query = Query()
        result = await query.workflows(info=info, status="draft")

        assert len(result) >= 1
        for wf_result in result:
            assert wf_result.status == "draft"

    async def test_workflows_empty_db_returns_empty_list(self, db: AsyncSession):
        """workflows() with no data returns an empty list."""
        from marketplace.graphql.resolvers.queries import Query

        query = Query()
        info = _make_info(db)

        result = await query.workflows(info=info)
        assert result == []

    async def test_workflows_pagination_limit(self, db: AsyncSession, make_agent):
        """workflows(limit=1) returns at most 1 workflow."""
        from marketplace.graphql.resolvers.queries import Query
        from marketplace.graphql.resolvers.mutations import Mutation

        agent, _ = await make_agent()
        info = _make_info(db, user={"id": agent.id})

        mutation = Mutation()
        await mutation.create_workflow(info=info, name="Limit WF 1", graph_json="{}")
        await mutation.create_workflow(info=info, name="Limit WF 2", graph_json="{}")
        await mutation.create_workflow(info=info, name="Limit WF 3", graph_json="{}")

        query = Query()
        result = await query.workflows(info=info, limit=1)
        assert len(result) == 1

    async def test_workflows_offset_pagination(self, db: AsyncSession, make_agent):
        """workflows(offset=1) skips the first result."""
        from marketplace.graphql.resolvers.queries import Query
        from marketplace.graphql.resolvers.mutations import Mutation

        agent, _ = await make_agent()
        info = _make_info(db, user={"id": agent.id})

        mutation = Mutation()
        await mutation.create_workflow(info=info, name="Offset WF A", graph_json="{}")
        await mutation.create_workflow(info=info, name="Offset WF B", graph_json="{}")

        query = Query()
        full_result = await query.workflows(info=info, limit=100)
        offset_result = await query.workflows(info=info, offset=1, limit=100)

        assert len(offset_result) == len(full_result) - 1


# ===========================================================================
# INTEGRATION: MUTATION + QUERY ROUND-TRIP
# ===========================================================================

class TestMutationQueryRoundTrip:
    """Integration tests confirming that data created via mutations is
    queryable via the query resolvers using the same database session."""

    async def test_create_agent_then_query_by_id(self, db: AsyncSession):
        """Agent created via mutation is immediately queryable by ID."""
        from marketplace.graphql.resolvers.mutations import Mutation
        from marketplace.graphql.resolvers.queries import Query

        mutation = Mutation()
        query = Query()
        info = _make_info(db)

        created = await mutation.create_agent(
            info=info, name="Roundtrip Agent", agent_type="buyer"
        )

        fetched = await query.agent(info=info, id=created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "Roundtrip Agent"
        assert fetched.agent_type == "buyer"

    async def test_create_listing_then_query_by_id(self, db: AsyncSession):
        """Listing created via mutation is immediately queryable by ID."""
        from marketplace.graphql.resolvers.mutations import Mutation
        from marketplace.graphql.resolvers.queries import Query

        mutation = Mutation()
        query = Query()
        info = _make_info(db, user={"id": "roundtrip-seller"})

        created = await mutation.create_listing(
            info=info, title="Roundtrip Listing", category="Test", price_usdc=7.77
        )

        fetched = await query.listing(info=info, id=created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.title == "Roundtrip Listing"
        assert fetched.price_usdc == pytest.approx(7.77)

    async def test_create_workflow_then_query_by_owner(self, db: AsyncSession):
        """Workflow created via mutation appears in workflows() query by owner."""
        from marketplace.graphql.resolvers.mutations import Mutation
        from marketplace.graphql.resolvers.queries import Query

        mutation = Mutation()
        query = Query()
        owner_id = "roundtrip-owner-" + _new_id()
        info = _make_info(db, user={"id": owner_id})

        created = await mutation.create_workflow(
            info=info, name="Owner Workflow", graph_json="{}"
        )

        workflows = await query.workflows(info=info, owner_id=owner_id)
        ids = [wf.id for wf in workflows]
        assert created.id in ids

    async def test_create_agent_appears_in_agents_list(self, db: AsyncSession):
        """Agent created via mutation appears in the agents() collection query."""
        from marketplace.graphql.resolvers.mutations import Mutation
        from marketplace.graphql.resolvers.queries import Query

        mutation = Mutation()
        query = Query()
        info = _make_info(db)

        created = await mutation.create_agent(
            info=info, name="List-Me Agent", agent_type="seller"
        )

        result = await query.agents(info=info)
        ids = [a.id for a in result.items]
        assert created.id in ids

    async def test_create_listing_appears_in_listings_list(self, db: AsyncSession):
        """Listing created via mutation appears in the listings() collection query."""
        from marketplace.graphql.resolvers.mutations import Mutation
        from marketplace.graphql.resolvers.queries import Query

        mutation = Mutation()
        query = Query()
        info = _make_info(db)

        created = await mutation.create_listing(
            info=info, title="List-Me Listing", category="NLP", price_usdc=3.0
        )

        result = await query.listings(info=info)
        ids = [lst.id for lst in result.items]
        assert created.id in ids

    async def test_multiple_mutations_reflected_in_count(self, db: AsyncSession):
        """total_count in page_info reflects the actual number of created agents."""
        from marketplace.graphql.resolvers.mutations import Mutation
        from marketplace.graphql.resolvers.queries import Query

        mutation = Mutation()
        query = Query()
        info = _make_info(db)

        n = 5
        for i in range(n):
            await mutation.create_agent(info=info, name=f"count-agent-{i}", agent_type="buyer")

        result = await query.agents(info=info, limit=100)
        assert result.page_info.total_count == n
