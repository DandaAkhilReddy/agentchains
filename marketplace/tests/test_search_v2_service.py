"""Unit tests for the SearchV2Service (Azure AI Search integration).

25 tests across 5 describe blocks:
  - Stub mode behavior (1-5)
  - Index name and client caching (6-10)
  - Document indexing (11-15)
  - Search operations (16-20)
  - Database-backed sync functions (21-25)

All Azure SDK calls are mocked. The service falls back to stub mode when
no credentials are configured, which is the default in test environments.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services.search_v2_service import (
    SearchV2Service,
    _agents_fields,
    _listings_fields,
    _tools_fields,
    get_search_service,
    sync_agents_index,
    sync_listings_index,
    sync_tools_index,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


def _make_service_with_mock_client(entity: str = "listings") -> tuple[SearchV2Service, MagicMock]:
    """Create a SearchV2Service whose _get_search_client returns a mock for `entity`.

    We patch the method directly because the guard clause in _get_search_client
    checks module-level _HAS_AZURE_SEARCH (False in tests) and self._credential
    (None when no endpoint/key). Injecting into _search_clients alone is not
    enough; we must bypass those checks.
    """
    svc = SearchV2Service(endpoint="", key="", index_prefix="test")
    mock_client = MagicMock()

    original_get = svc._get_search_client

    def _patched_get(e: str):
        if e == entity:
            return mock_client
        return original_get(e)

    svc._get_search_client = _patched_get  # type: ignore[method-assign]
    return svc, mock_client


# ===========================================================================
# 1. STUB MODE BEHAVIOR (tests 1-5)
# ===========================================================================


class TestStubModeBehavior:
    """Verify that the service operates in stub mode when no Azure credentials."""

    async def test_no_credentials_returns_stub_service(self):
        """1. Service with empty endpoint/key should have no index client."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="test")
        assert svc._index_client is None
        assert svc._credential is None

    async def test_ensure_indexes_returns_empty_in_stub_mode(self):
        """2. ensure_indexes returns empty dict when no index client."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="test")
        result = svc.ensure_indexes()
        assert result == {}

    async def test_search_listings_returns_empty_in_stub_mode(self):
        """3. search_listings returns empty results in stub mode."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="test")
        result = svc.search_listings("test query")
        assert result == {"results": [], "count": 0, "facets": {}}

    async def test_search_agents_returns_empty_in_stub_mode(self):
        """4. search_agents returns empty results in stub mode."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="test")
        result = svc.search_agents("test query")
        assert result == {"results": [], "count": 0, "facets": {}}

    async def test_search_tools_returns_empty_in_stub_mode(self):
        """5. search_tools returns empty results in stub mode."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="test")
        result = svc.search_tools("test query")
        assert result == {"results": [], "count": 0, "facets": {}}


# ===========================================================================
# 2. INDEX NAME AND CLIENT CACHING (tests 6-10)
# ===========================================================================


class TestIndexNaming:
    """Verify index name generation and client caching."""

    async def test_index_name_format(self):
        """6. Index name should follow prefix-entity format."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="agentchains")
        assert svc._index_name("listings") == "agentchains-listings"
        assert svc._index_name("agents") == "agentchains-agents"
        assert svc._index_name("tools") == "agentchains-tools"

    async def test_custom_prefix(self):
        """7. Custom prefix should be used in index name."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="prod")
        assert svc._index_name("listings") == "prod-listings"

    async def test_get_search_client_returns_none_without_credentials(self):
        """8. _get_search_client returns None when no credential."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="test")
        assert svc._get_search_client("listings") is None

    async def test_field_definitions_listings(self):
        """9. Listings field schema contains expected fields."""
        fields = _listings_fields()
        field_names = {f["name"] for f in fields}
        assert "id" in field_names
        assert "title" in field_names
        assert "category" in field_names
        assert "price_usd" in field_names
        assert "tags" in field_names

    async def test_field_definitions_agents(self):
        """10. Agents field schema contains expected fields."""
        fields = _agents_fields()
        field_names = {f["name"] for f in fields}
        assert "id" in field_names
        assert "name" in field_names
        assert "reputation_score" in field_names
        assert "status" in field_names

    async def test_field_definitions_tools(self):
        """10b. Tools field schema contains expected fields."""
        fields = _tools_fields()
        field_names = {f["name"] for f in fields}
        assert "id" in field_names
        assert "name" in field_names
        assert "domain" in field_names
        assert "success_rate" in field_names

    async def test_build_search_fields_returns_empty_without_sdk(self):
        """10c. _build_search_fields returns empty list when Azure SDK not installed."""
        result = SearchV2Service._build_search_fields(_listings_fields())
        # Without Azure SDK installed, this returns an empty list
        assert isinstance(result, list)


# ===========================================================================
# 3. DOCUMENT INDEXING (tests 11-15)
# ===========================================================================


class TestDocumentIndexing:
    """Verify document upsert methods."""

    async def test_index_listing_no_client_returns_false(self):
        """11. index_listing returns False when no search client."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="test")
        result = svc.index_listing({"id": "test-1", "title": "Test"})
        assert result is False

    async def test_index_listing_with_mock_client(self):
        """12. index_listing calls merge_or_upload on the search client."""
        svc, mock_client = _make_service_with_mock_client("listings")
        doc = {"id": "test-1", "title": "Test Listing"}
        result = svc.index_listing(doc)
        assert result is True
        mock_client.merge_or_upload_documents.assert_called_once_with(documents=[doc])

    async def test_index_listing_exception_returns_false(self):
        """13. index_listing returns False on Azure SDK exception."""
        svc, mock_client = _make_service_with_mock_client("listings")
        mock_client.merge_or_upload_documents.side_effect = RuntimeError("Azure error")
        result = svc.index_listing({"id": "test-1"})
        assert result is False

    async def test_index_agent_with_mock_client(self):
        """14. index_agent calls merge_or_upload on the agents search client."""
        svc, mock_client = _make_service_with_mock_client("agents")
        doc = {"id": "agent-1", "name": "TestAgent"}
        result = svc.index_agent(doc)
        assert result is True
        mock_client.merge_or_upload_documents.assert_called_once_with(documents=[doc])

    async def test_index_tool_with_mock_client(self):
        """15. index_tool calls merge_or_upload on the tools search client."""
        svc, mock_client = _make_service_with_mock_client("tools")
        doc = {"id": "tool-1", "name": "TestTool"}
        result = svc.index_tool(doc)
        assert result is True
        mock_client.merge_or_upload_documents.assert_called_once_with(documents=[doc])

    async def test_index_agent_no_client_returns_false(self):
        """15b. index_agent returns False when no search client."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="test")
        assert svc.index_agent({"id": "a1"}) is False

    async def test_index_tool_no_client_returns_false(self):
        """15c. index_tool returns False when no search client."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="test")
        assert svc.index_tool({"id": "t1"}) is False

    async def test_index_agent_exception_returns_false(self):
        """15d. index_agent handles SDK exceptions gracefully."""
        svc, mock_client = _make_service_with_mock_client("agents")
        mock_client.merge_or_upload_documents.side_effect = RuntimeError("fail")
        assert svc.index_agent({"id": "a1"}) is False

    async def test_index_tool_exception_returns_false(self):
        """15e. index_tool handles SDK exceptions gracefully."""
        svc, mock_client = _make_service_with_mock_client("tools")
        mock_client.merge_or_upload_documents.side_effect = RuntimeError("fail")
        assert svc.index_tool({"id": "t1"}) is False


# ===========================================================================
# 4. SEARCH OPERATIONS (tests 16-20)
# ===========================================================================


class TestSearchOperations:
    """Verify search dispatching and response formatting."""

    async def test_search_with_mock_response(self):
        """16. _search returns formatted results from mock client."""
        svc, mock_client = _make_service_with_mock_client("listings")

        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(return_value=iter([
            {"id": "1", "title": "Result 1"},
            {"id": "2", "title": "Result 2"},
        ]))
        mock_response.get_count.return_value = 2
        mock_response.get_facets.return_value = {
            "category": [{"value": "web_search", "count": 2}],
        }
        mock_client.search.return_value = mock_response

        result = svc.search_listings("test")
        assert result["count"] == 2
        assert len(result["results"]) == 2
        assert result["facets"]["category"][0]["value"] == "web_search"

    async def test_search_with_filter(self):
        """17. search passes OData filter to Azure client."""
        svc, mock_client = _make_service_with_mock_client("listings")

        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(return_value=iter([]))
        mock_response.get_count.return_value = 0
        mock_response.get_facets.return_value = None
        mock_client.search.return_value = mock_response

        svc.search_listings("test", filters="status eq 'active'")
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["filter"] == "status eq 'active'"

    async def test_search_with_pagination(self):
        """18. search passes top and skip parameters."""
        svc, mock_client = _make_service_with_mock_client("listings")

        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(return_value=iter([]))
        mock_response.get_count.return_value = 0
        mock_response.get_facets.return_value = None
        mock_client.search.return_value = mock_response

        svc.search_listings("test", top=10, skip=5)
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["top"] == 10
        assert call_kwargs["skip"] == 5

    async def test_search_exception_returns_empty(self):
        """19. _search returns empty results on exception."""
        svc, mock_client = _make_service_with_mock_client("listings")
        mock_client.search.side_effect = RuntimeError("Search failed")

        result = svc.search_listings("test")
        assert result == {"results": [], "count": 0, "facets": {}}

    async def test_delete_document_no_client_returns_false(self):
        """20. delete_document returns False when no credential."""
        svc = SearchV2Service(endpoint="", key="", index_prefix="test")
        assert svc.delete_document("test-listings", "doc-1") is False

    async def test_search_agents_passes_correct_facets(self):
        """20b. search_agents uses category and status facets."""
        svc, mock_client = _make_service_with_mock_client("agents")
        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(return_value=iter([]))
        mock_response.get_count.return_value = 0
        mock_response.get_facets.return_value = None
        mock_client.search.return_value = mock_response

        svc.search_agents("bot")
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["facets"] == ["category", "status"]

    async def test_search_tools_passes_correct_facets(self):
        """20c. search_tools uses domain, category, and status facets."""
        svc, mock_client = _make_service_with_mock_client("tools")
        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(return_value=iter([]))
        mock_response.get_count.return_value = 0
        mock_response.get_facets.return_value = None
        mock_client.search.return_value = mock_response

        svc.search_tools("scraper")
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["facets"] == ["domain", "category", "status"]

    async def test_search_no_facets_from_response(self):
        """20d. _search handles None from get_facets gracefully."""
        svc, mock_client = _make_service_with_mock_client("listings")
        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(return_value=iter([{"id": "x"}]))
        mock_response.get_count.return_value = 1
        mock_response.get_facets.return_value = None
        mock_client.search.return_value = mock_response

        result = svc.search_listings("test")
        assert result["count"] == 1
        assert result["facets"] == {}


# ===========================================================================
# 5. DATABASE-BACKED SYNC FUNCTIONS (tests 21-25)
# ===========================================================================


class TestSyncFunctions:
    """Verify async sync_*_index functions that read from DB."""

    async def test_sync_listings_skipped_no_client(self, db: AsyncSession, make_agent):
        """21. sync_listings_index skips when no search client configured."""
        result = await sync_listings_index(db)
        assert result["status"] == "skipped"
        assert result["synced"] == 0

    async def test_sync_agents_skipped_no_client(self, db: AsyncSession):
        """22. sync_agents_index skips when no search client configured."""
        result = await sync_agents_index(db)
        assert result["status"] == "skipped"
        assert result["synced"] == 0

    async def test_sync_tools_skipped_no_client(self, db: AsyncSession):
        """23. sync_tools_index skips when no search client configured."""
        result = await sync_tools_index(db)
        assert result["status"] == "skipped"
        assert result["synced"] == 0

    async def test_sync_listings_with_mock_client(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """24. sync_listings_index uploads active listings to the search index."""
        agent, _ = await make_agent()
        await make_listing(agent.id, price_usdc=1.0, title="Listing A")
        await make_listing(agent.id, price_usdc=2.0, title="Listing B")

        mock_client = MagicMock()
        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_listings_index(db)

        assert result["status"] == "ok"
        assert result["synced"] == 2
        mock_client.merge_or_upload_documents.assert_called_once()
        docs = mock_client.merge_or_upload_documents.call_args[1]["documents"]
        assert len(docs) == 2
        titles = {d["title"] for d in docs}
        assert "Listing A" in titles
        assert "Listing B" in titles

    async def test_sync_listings_no_active_listings(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """25. sync_listings_index returns synced=0 when no active listings."""
        agent, _ = await make_agent()
        await make_listing(agent.id, status="suspended", title="Suspended")

        mock_client = MagicMock()
        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_listings_index(db)

        assert result["status"] == "ok"
        assert result["synced"] == 0
        mock_client.merge_or_upload_documents.assert_not_called()

    async def test_sync_agents_with_mock_client(
        self, db: AsyncSession, make_agent
    ):
        """25b. sync_agents_index uploads active agents to the search index."""
        await make_agent(name="Agent-A")
        await make_agent(name="Agent-B")

        mock_client = MagicMock()
        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_agents_index(db)

        assert result["status"] == "ok"
        assert result["synced"] == 2
        docs = mock_client.merge_or_upload_documents.call_args[1]["documents"]
        names = {d["name"] for d in docs}
        assert "Agent-A" in names
        assert "Agent-B" in names

    async def test_sync_listings_with_tags(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """24b. sync_listings_index handles listings with valid JSON tags."""
        agent, _ = await make_agent()
        listing = await make_listing(agent.id, title="Tagged Listing")
        listing.tags = '["python", "tutorial"]'
        await db.commit()

        mock_client = MagicMock()
        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_listings_index(db)

        assert result["synced"] == 1
        docs = mock_client.merge_or_upload_documents.call_args[1]["documents"]
        assert docs[0]["tags"] == ["python", "tutorial"]

    async def test_sync_listings_with_invalid_tags(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """24c. sync_listings_index handles listings with invalid JSON tags gracefully."""
        agent, _ = await make_agent()
        listing = await make_listing(agent.id, title="Bad Tags Listing")
        listing.tags = "not valid json{{"
        await db.commit()

        mock_client = MagicMock()
        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_listings_index(db)

        assert result["synced"] == 1
        docs = mock_client.merge_or_upload_documents.call_args[1]["documents"]
        # Invalid JSON tags should fall back to empty list
        assert docs[0]["tags"] == []

    async def test_sync_listings_handles_upload_failure(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """25c. sync_listings_index returns error status on upload failure."""
        agent, _ = await make_agent()
        await make_listing(agent.id, title="Listing X")

        mock_client = MagicMock()
        mock_client.merge_or_upload_documents.side_effect = RuntimeError("upload failed")

        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_listings_index(db)

        assert result["status"] == "error"
        assert "upload failed" in result["error"]

    async def test_sync_tools_with_mock_client(
        self, db: AsyncSession, make_creator
    ):
        """25d. sync_tools_index uploads approved tools to the search index."""
        from marketplace.models.webmcp_tool import WebMCPTool

        creator, _ = await make_creator()
        tool = WebMCPTool(
            id=_uid(),
            name="Test Tool",
            description="A test tool",
            domain="example.com",
            endpoint_url="https://example.com/mcp",
            creator_id=creator.id,
            category="research",
            version="1.0.0",
            status="approved",
            execution_count=5,
            success_rate=Decimal("0.95"),
        )
        db.add(tool)
        await db.commit()

        mock_client = MagicMock()
        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_tools_index(db)

        assert result["status"] == "ok"
        assert result["synced"] == 1
        docs = mock_client.merge_or_upload_documents.call_args[1]["documents"]
        assert docs[0]["name"] == "Test Tool"
        assert docs[0]["domain"] == "example.com"
        assert docs[0]["success_rate"] == 0.95


# ===========================================================================
# 6. SINGLETON FACTORY (bonus)
# ===========================================================================


class TestSyncAgentsWithUploadFailure:
    """Verify sync functions handle upload failures for agents and tools."""

    async def test_sync_agents_handles_upload_failure(
        self, db: AsyncSession, make_agent
    ):
        """25e. sync_agents_index returns error status on upload failure."""
        await make_agent(name="Agent-Fail")

        mock_client = MagicMock()
        mock_client.merge_or_upload_documents.side_effect = RuntimeError("agent upload failed")

        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_agents_index(db)

        assert result["status"] == "error"
        assert "agent upload failed" in result["error"]

    async def test_sync_tools_handles_upload_failure(
        self, db: AsyncSession, make_creator
    ):
        """25f. sync_tools_index returns error status on upload failure."""
        from marketplace.models.webmcp_tool import WebMCPTool

        creator, _ = await make_creator()
        tool = WebMCPTool(
            id=_uid(),
            name="Fail Tool",
            description="A tool that fails to sync",
            domain="fail.com",
            endpoint_url="https://fail.com/mcp",
            creator_id=creator.id,
            category="research",
            version="1.0.0",
            status="approved",
        )
        db.add(tool)
        await db.commit()

        mock_client = MagicMock()
        mock_client.merge_or_upload_documents.side_effect = RuntimeError("tools upload failed")

        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_tools_index(db)

        assert result["status"] == "error"
        assert "tools upload failed" in result["error"]

    async def test_sync_agents_no_active_agents_returns_zero(
        self, db: AsyncSession
    ):
        """25g. sync_agents_index returns synced=0 when no active agents."""
        mock_client = MagicMock()
        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_agents_index(db)

        assert result["status"] == "ok"
        assert result["synced"] == 0
        mock_client.merge_or_upload_documents.assert_not_called()

    async def test_sync_tools_no_approved_tools_returns_zero(
        self, db: AsyncSession
    ):
        """25h. sync_tools_index returns synced=0 when no approved/active tools."""
        mock_client = MagicMock()
        with patch(
            "marketplace.services.search_v2_service.get_search_service"
        ) as mock_get_svc:
            mock_svc = MagicMock(spec=SearchV2Service)
            mock_svc._get_search_client.return_value = mock_client
            mock_get_svc.return_value = mock_svc

            result = await sync_tools_index(db)

        assert result["status"] == "ok"
        assert result["synced"] == 0


class TestSingletonFactory:
    """Verify the get_search_service singleton."""

    async def test_get_search_service_returns_instance(self):
        """get_search_service returns a SearchV2Service instance."""
        with patch(
            "marketplace.services.search_v2_service._search_service", None
        ):
            svc = get_search_service()
            assert isinstance(svc, SearchV2Service)
