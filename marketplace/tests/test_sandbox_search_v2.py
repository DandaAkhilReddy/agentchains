"""Comprehensive tests for sandbox_executor and search_v2_service.

Covers:
- execute_action_in_sandbox: happy paths for each action type, error path,
  finally-block cleanup, default argument wiring.
- _build_execution_script: all four branches (web_scrape, screenshot,
  form_fill, generic fallback).
- SearchV2Service: stub mode (no Azure SDK / no credentials), index_listing /
  index_agent / index_tool success and failure paths, search_listings /
  search_agents / search_tools, ensure_indexes, delete_document.
- Module-level sync functions: sync_listings_index, sync_agents_index,
  sync_tools_index — skipped path (no client) and DB-backed happy path.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers / shared factories
# ---------------------------------------------------------------------------

def _make_sandbox_result(sandbox_id: str = "sb-test-123") -> MagicMock:
    """Return a mock object whose .sandbox_id attribute is set."""
    sb = MagicMock()
    sb.sandbox_id = sandbox_id
    return sb


# ===========================================================================
# sandbox_executor — _build_execution_script
# ===========================================================================


class TestBuildExecutionScript:
    """Unit tests for _build_execution_script — pure function, no mocks needed."""

    def test_web_scrape_uses_input_url(self):
        """web_scrape script uses url from input_data first."""
        from marketplace.services.sandbox_executor import _build_execution_script

        script = _build_execution_script(
            "web_scrape",
            {"url": "https://config.example.com", "selector": ".title"},
            {"url": "https://input.example.com"},
        )

        assert "https://input.example.com" in script
        assert "sync_playwright" in script
        assert ".title" in script

    def test_web_scrape_falls_back_to_config_url(self):
        """web_scrape script falls back to action_config url when input_data has none."""
        from marketplace.services.sandbox_executor import _build_execution_script

        script = _build_execution_script(
            "web_scrape",
            {"url": "https://config.example.com", "selector": "body"},
            {},
        )

        assert "https://config.example.com" in script
        assert "body" in script

    def test_web_scrape_default_selector_is_body(self):
        """web_scrape defaults to 'body' selector when not specified."""
        from marketplace.services.sandbox_executor import _build_execution_script

        script = _build_execution_script("web_scrape", {}, {"url": "https://x.com"})

        # 'body' should appear as the selector fallback
        assert '"body"' in script

    def test_screenshot_generates_playwright_script(self):
        """screenshot action generates a screenshot script."""
        from marketplace.services.sandbox_executor import _build_execution_script

        script = _build_execution_script(
            "screenshot",
            {},
            {"url": "https://screenshot.example.com"},
        )

        assert "screenshot_base64" in script
        assert "base64" in script
        assert "https://screenshot.example.com" in script

    def test_screenshot_uses_input_url_over_config(self):
        """screenshot prefers url from input_data."""
        from marketplace.services.sandbox_executor import _build_execution_script

        script = _build_execution_script(
            "screenshot",
            {"url": "https://config-url.com"},
            {"url": "https://input-url.com"},
        )

        assert "https://input-url.com" in script

    def test_form_fill_embeds_fields(self):
        """form_fill script embeds field selector/value mapping."""
        from marketplace.services.sandbox_executor import _build_execution_script

        fields = {"#username": "alice", "#password": "secret"}
        script = _build_execution_script(
            "form_fill",
            {},
            {"url": "https://login.example.com", "fields": fields},
        )

        assert "https://login.example.com" in script
        assert "filled_fields" in script
        assert "page.fill" in script

    def test_generic_action_returns_status_executed(self):
        """Unknown action types return a generic JSON-printing script."""
        from marketplace.services.sandbox_executor import _build_execution_script

        script = _build_execution_script(
            "custom_action_xyz",
            {},
            {},
        )

        assert "custom_action_xyz" in script
        assert "executed" in script
        assert "json.dumps" in script

    def test_generic_script_has_no_playwright(self):
        """Generic fallback script does not include playwright."""
        from marketplace.services.sandbox_executor import _build_execution_script

        script = _build_execution_script("unknown", {}, {})

        assert "playwright" not in script


# ===========================================================================
# sandbox_executor — execute_action_in_sandbox
# ===========================================================================


class TestExecuteActionInSandbox:
    """Integration-style tests that mock the sandbox_manager singleton."""

    @staticmethod
    def _patch_manager(sandbox_id: str = "sb-abc-123", exec_result: Any = None):
        """Build a context manager that patches sandbox_manager in the executor module."""
        fake_sandbox = _make_sandbox_result(sandbox_id)
        mock_mgr = MagicMock()
        mock_mgr.create_sandbox = AsyncMock(return_value=fake_sandbox)
        mock_mgr.start_sandbox = AsyncMock(return_value=None)
        mock_mgr.execute_in_sandbox = AsyncMock(return_value=exec_result or {"status": "ok"})
        mock_mgr.destroy_sandbox = AsyncMock(return_value=None)
        return patch(
            "marketplace.services.sandbox_executor.sandbox_manager",
            mock_mgr,
        ), mock_mgr

    async def test_happy_path_returns_success(self):
        """execute_action_in_sandbox returns success=True on normal execution."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        ctx, mock_mgr = self._patch_manager(exec_result={"data": "hello"})
        with ctx:
            result = await execute_action_in_sandbox(
                "web_scrape",
                {"selector": "h1"},
                {"url": "https://example.com"},
            )

        assert result["success"] is True
        assert result["sandbox_id"] == "sb-abc-123"
        assert result["output"] == {"data": "hello"}
        assert result["proof"]["execution_mode"] == "sandbox"
        assert result["proof"]["action_type"] == "web_scrape"

    async def test_happy_path_proof_contains_sandbox_id(self):
        """Proof block echoes sandbox_id and action_type."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        ctx, _ = self._patch_manager(sandbox_id="sb-xyz-999")
        with ctx:
            result = await execute_action_in_sandbox("screenshot", {}, {"url": "https://a.com"})

        assert result["proof"]["sandbox_id"] == "sb-xyz-999"
        assert result["proof"]["isolated"] is True  # default network_isolated=True

    async def test_network_isolated_false_propagates(self):
        """network_isolated=False is reflected in the proof dict."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        ctx, _ = self._patch_manager()
        with ctx:
            result = await execute_action_in_sandbox(
                "form_fill",
                {},
                {},
                network_isolated=False,
            )

        assert result["proof"]["isolated"] is False

    async def test_sandbox_config_passed_to_create(self):
        """SandboxConfig is built from the kwargs and passed to create_sandbox."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        ctx, mock_mgr = self._patch_manager()
        with ctx:
            await execute_action_in_sandbox(
                "web_scrape",
                {},
                {},
                timeout_seconds=60,
                memory_limit_mb=256,
            )

        # create_sandbox is called once with a SandboxConfig instance
        mock_mgr.create_sandbox.assert_awaited_once()
        config_arg = mock_mgr.create_sandbox.call_args[0][0]
        assert config_arg.timeout_seconds == 60
        assert config_arg.memory_limit_mb == 256

    async def test_allowed_domains_forwarded_to_config(self):
        """allowed_domains list is forwarded to SandboxConfig."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        ctx, mock_mgr = self._patch_manager()
        with ctx:
            await execute_action_in_sandbox(
                "web_scrape",
                {},
                {},
                allowed_domains=["example.com", "api.example.com"],
            )

        config_arg = mock_mgr.create_sandbox.call_args[0][0]
        assert config_arg.allowed_domains == ["example.com", "api.example.com"]

    async def test_none_allowed_domains_becomes_empty_list(self):
        """None for allowed_domains is converted to empty list in SandboxConfig."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        ctx, mock_mgr = self._patch_manager()
        with ctx:
            await execute_action_in_sandbox("web_scrape", {}, {}, allowed_domains=None)

        config_arg = mock_mgr.create_sandbox.call_args[0][0]
        assert config_arg.allowed_domains == []

    async def test_execute_in_sandbox_called_with_correct_script(self):
        """execute_in_sandbox receives the built script and input_data."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        ctx, mock_mgr = self._patch_manager()
        input_data = {"url": "https://test.com"}
        with ctx:
            await execute_action_in_sandbox("web_scrape", {}, input_data)

        call_kwargs = mock_mgr.execute_in_sandbox.call_args
        # Verify sandbox_id is passed
        assert call_kwargs[1]["input_data"] == input_data
        script = call_kwargs[1]["action_script"]
        assert "test.com" in script

    async def test_exception_during_execute_returns_error_dict(self):
        """If execute_in_sandbox raises, result has success=False and error key."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        fake_sandbox = _make_sandbox_result("sb-err-001")
        mock_mgr = MagicMock()
        mock_mgr.create_sandbox = AsyncMock(return_value=fake_sandbox)
        mock_mgr.start_sandbox = AsyncMock(return_value=None)
        mock_mgr.execute_in_sandbox = AsyncMock(side_effect=RuntimeError("timeout"))
        mock_mgr.destroy_sandbox = AsyncMock(return_value=None)

        with patch("marketplace.services.sandbox_executor.sandbox_manager", mock_mgr):
            result = await execute_action_in_sandbox("web_scrape", {}, {})

        assert result["success"] is False
        assert result["sandbox_id"] == "sb-err-001"
        assert "timeout" in result["error"]
        assert result["proof"]["failed"] is True

    async def test_destroy_sandbox_always_called(self):
        """destroy_sandbox is called in the finally block even when execution fails."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        fake_sandbox = _make_sandbox_result("sb-cleanup-007")
        mock_mgr = MagicMock()
        mock_mgr.create_sandbox = AsyncMock(return_value=fake_sandbox)
        mock_mgr.start_sandbox = AsyncMock(return_value=None)
        mock_mgr.execute_in_sandbox = AsyncMock(side_effect=ValueError("bad input"))
        mock_mgr.destroy_sandbox = AsyncMock(return_value=None)

        with patch("marketplace.services.sandbox_executor.sandbox_manager", mock_mgr):
            await execute_action_in_sandbox("screenshot", {}, {})

        mock_mgr.destroy_sandbox.assert_awaited_once_with("sb-cleanup-007")

    async def test_destroy_sandbox_called_on_success_too(self):
        """destroy_sandbox is called in the finally block on success as well."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        ctx, mock_mgr = self._patch_manager(sandbox_id="sb-done-555")
        with ctx:
            await execute_action_in_sandbox("form_fill", {}, {})

        mock_mgr.destroy_sandbox.assert_awaited_once_with("sb-done-555")

    async def test_start_sandbox_is_called_with_sandbox_id(self):
        """start_sandbox is called with the sandbox's ID after creation."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        ctx, mock_mgr = self._patch_manager(sandbox_id="sb-start-222")
        with ctx:
            await execute_action_in_sandbox("screenshot", {}, {})

        mock_mgr.start_sandbox.assert_awaited_once_with("sb-start-222")

    async def test_error_proof_contains_action_type(self):
        """Error result proof still contains the correct action_type."""
        from marketplace.services.sandbox_executor import execute_action_in_sandbox

        fake_sandbox = _make_sandbox_result("sb-proof-000")
        mock_mgr = MagicMock()
        mock_mgr.create_sandbox = AsyncMock(return_value=fake_sandbox)
        mock_mgr.start_sandbox = AsyncMock(return_value=None)
        mock_mgr.execute_in_sandbox = AsyncMock(side_effect=Exception("crash"))
        mock_mgr.destroy_sandbox = AsyncMock(return_value=None)

        with patch("marketplace.services.sandbox_executor.sandbox_manager", mock_mgr):
            result = await execute_action_in_sandbox("form_fill", {}, {})

        assert result["proof"]["action_type"] == "form_fill"
        assert result["proof"]["execution_mode"] == "sandbox"


# ===========================================================================
# SearchV2Service — stub mode (no endpoint / no SDK)
# ===========================================================================


class TestSearchV2ServiceStubMode:
    """Tests for SearchV2Service operating without Azure credentials."""

    def _make_stub_service(self):
        """Return a SearchV2Service with no endpoint (stub mode)."""
        from marketplace.services.search_v2_service import SearchV2Service
        return SearchV2Service(endpoint="", key="", index_prefix="test")

    def test_index_listing_returns_false_when_no_client(self):
        """index_listing returns False when there is no Azure client."""
        svc = self._make_stub_service()
        result = svc.index_listing({"id": "L-1", "title": "Test"})
        assert result is False

    def test_index_agent_returns_false_when_no_client(self):
        """index_agent returns False when there is no Azure client."""
        svc = self._make_stub_service()
        result = svc.index_agent({"id": "A-1", "name": "TestAgent"})
        assert result is False

    def test_index_tool_returns_false_when_no_client(self):
        """index_tool returns False when there is no Azure client."""
        svc = self._make_stub_service()
        result = svc.index_tool({"id": "T-1", "name": "TestTool"})
        assert result is False

    def test_search_listings_stub_returns_empty(self):
        """search_listings returns empty result set in stub mode."""
        svc = self._make_stub_service()
        result = svc.search_listings("machine learning")
        assert result == {"results": [], "count": 0, "facets": {}}

    def test_search_agents_stub_returns_empty(self):
        """search_agents returns empty result set in stub mode."""
        svc = self._make_stub_service()
        result = svc.search_agents("data analyst")
        assert result == {"results": [], "count": 0, "facets": {}}

    def test_search_tools_stub_returns_empty(self):
        """search_tools returns empty result set in stub mode."""
        svc = self._make_stub_service()
        result = svc.search_tools("web scraper")
        assert result == {"results": [], "count": 0, "facets": {}}

    def test_ensure_indexes_stub_returns_empty_dict(self):
        """ensure_indexes returns an empty dict when no index client is available."""
        svc = self._make_stub_service()
        result = svc.ensure_indexes()
        assert result == {}

    def test_delete_document_stub_returns_false(self):
        """delete_document returns False when there is no Azure client."""
        svc = self._make_stub_service()
        result = svc.delete_document("agentchains-listings", "some-doc-id")
        assert result is False

    def test_index_name_helper(self):
        """_index_name builds '<prefix>-<entity>' strings."""
        svc = self._make_stub_service()
        assert svc._index_name("listings") == "test-listings"
        assert svc._index_name("agents") == "test-agents"
        assert svc._index_name("tools") == "test-tools"

    def test_get_search_client_stub_returns_none(self):
        """_get_search_client returns None in stub mode."""
        svc = self._make_stub_service()
        assert svc._get_search_client("listings") is None


# ===========================================================================
# SearchV2Service — with a mocked Azure client
# ===========================================================================


class TestSearchV2ServiceWithMockedClient:
    """Tests that inject a fake Azure search client to verify indexing logic."""

    def _make_service_with_mock_clients(self):
        """Build a SearchV2Service and manually inject a fake _credential and clients."""
        from marketplace.services.search_v2_service import SearchV2Service

        svc = SearchV2Service(endpoint="https://fake.search.windows.net", key="fakekey")
        # Override the credential so the client-existence checks pass
        svc._credential = MagicMock()

        # Build a generic fake search client
        fake_client = MagicMock()
        fake_client.merge_or_upload_documents = MagicMock(return_value=None)
        fake_client.search = MagicMock()
        fake_client.delete_documents = MagicMock(return_value=None)

        # Pre-populate _search_clients so _get_search_client returns our fake
        for entity in ("listings", "agents", "tools"):
            idx_name = svc._index_name(entity)
            svc._search_clients[idx_name] = fake_client

        return svc, fake_client

    # --- index_listing ---

    def test_index_listing_calls_merge_or_upload(self):
        """index_listing calls merge_or_upload_documents with the document."""
        svc, fake_client = self._make_service_with_mock_clients()
        doc = {"id": "L-100", "title": "Great Listing"}
        result = svc.index_listing(doc)
        fake_client.merge_or_upload_documents.assert_called_once_with(documents=[doc])
        assert result is True

    def test_index_listing_returns_false_on_exception(self):
        """index_listing returns False when merge_or_upload_documents raises."""
        svc, fake_client = self._make_service_with_mock_clients()
        fake_client.merge_or_upload_documents.side_effect = Exception("Azure error")
        result = svc.index_listing({"id": "L-bad"})
        assert result is False

    # --- index_agent ---

    def test_index_agent_calls_merge_or_upload(self):
        """index_agent calls merge_or_upload_documents on the agents index."""
        svc, fake_client = self._make_service_with_mock_clients()
        doc = {"id": "A-200", "name": "Smart Agent"}
        result = svc.index_agent(doc)
        fake_client.merge_or_upload_documents.assert_called_with(documents=[doc])
        assert result is True

    def test_index_agent_returns_false_on_exception(self):
        """index_agent returns False when the underlying SDK call raises."""
        svc, fake_client = self._make_service_with_mock_clients()
        fake_client.merge_or_upload_documents.side_effect = ConnectionError("network fail")
        result = svc.index_agent({"id": "A-bad"})
        assert result is False

    # --- index_tool ---

    def test_index_tool_calls_merge_or_upload(self):
        """index_tool calls merge_or_upload_documents on the tools index."""
        svc, fake_client = self._make_service_with_mock_clients()
        doc = {"id": "T-300", "name": "Web Scraper"}
        result = svc.index_tool(doc)
        fake_client.merge_or_upload_documents.assert_called_with(documents=[doc])
        assert result is True

    def test_index_tool_returns_false_on_exception(self):
        """index_tool returns False on SDK exception."""
        svc, fake_client = self._make_service_with_mock_clients()
        fake_client.merge_or_upload_documents.side_effect = TimeoutError("timeout")
        result = svc.index_tool({"id": "T-bad"})
        assert result is False

    # --- search helpers ---

    def _build_fake_search_response(self, docs: list[dict], count: int = None, facets=None):
        """Build a MagicMock that looks like an Azure SearchItemPaged."""
        response = MagicMock()
        response.__iter__ = MagicMock(return_value=iter(docs))
        response.get_count = MagicMock(return_value=count if count is not None else len(docs))
        if facets is not None:
            response.get_facets = MagicMock(return_value=facets)
        else:
            response.get_facets = MagicMock(return_value=None)
        return response

    def test_search_listings_returns_results(self):
        """search_listings parses Azure response into results/count/facets."""
        svc, fake_client = self._make_service_with_mock_clients()
        docs = [{"id": "L-1", "title": "Data Set"}, {"id": "L-2", "title": "ML Model"}]
        fake_client.search = MagicMock(return_value=self._build_fake_search_response(docs, count=2))

        result = svc.search_listings("data")

        assert len(result["results"]) == 2
        assert result["count"] == 2
        assert result["facets"] == {}

    def test_search_listings_with_filter_and_facets(self):
        """search_listings passes filter and facet parameters to the client."""
        svc, fake_client = self._make_service_with_mock_clients()
        fake_client.search = MagicMock(
            return_value=self._build_fake_search_response([], count=0)
        )

        svc.search_listings(
            "python",
            filters="status eq 'active'",
            facets=["category"],
            top=5,
            skip=10,
        )

        call_kwargs = fake_client.search.call_args[1]
        assert call_kwargs["filter"] == "status eq 'active'"
        assert "category" in call_kwargs["facets"]
        assert call_kwargs["top"] == 5
        assert call_kwargs["skip"] == 10

    def test_search_listings_returns_empty_on_exception(self):
        """search_listings returns empty dict when SDK raises."""
        svc, fake_client = self._make_service_with_mock_clients()
        fake_client.search.side_effect = Exception("search crashed")

        result = svc.search_listings("query")
        assert result == {"results": [], "count": 0, "facets": {}}

    def test_search_agents_returns_results(self):
        """search_agents parses response correctly."""
        svc, fake_client = self._make_service_with_mock_clients()
        docs = [{"id": "A-1", "name": "Analyst Agent"}]
        fake_client.search = MagicMock(return_value=self._build_fake_search_response(docs, count=1))

        result = svc.search_agents("analyst")

        assert len(result["results"]) == 1
        assert result["count"] == 1

    def test_search_tools_returns_results(self):
        """search_tools parses response correctly."""
        svc, fake_client = self._make_service_with_mock_clients()
        docs = [{"id": "T-1", "name": "Scraper"}]
        fake_client.search = MagicMock(return_value=self._build_fake_search_response(docs, count=1))

        result = svc.search_tools("scraper")

        assert len(result["results"]) == 1
        assert result["count"] == 1

    def test_search_with_facet_data_is_parsed(self):
        """Facet data from get_facets is correctly parsed into the result."""
        svc, fake_client = self._make_service_with_mock_clients()
        raw_facets = {
            "category": [{"value": "web_search", "count": 5}, {"value": "ml_models", "count": 3}],
        }
        fake_client.search = MagicMock(
            return_value=self._build_fake_search_response([], facets=raw_facets)
        )

        result = svc.search_listings("test")

        assert "category" in result["facets"]
        assert result["facets"]["category"][0]["value"] == "web_search"
        assert result["facets"]["category"][0]["count"] == 5

    # --- ensure_indexes ---

    def test_ensure_indexes_creates_new_index(self):
        """ensure_indexes creates an index when it does not yet exist."""
        from marketplace.services.search_v2_service import SearchV2Service

        svc = SearchV2Service(endpoint="https://fake.search.windows.net", key="fakekey")
        svc._credential = MagicMock()

        fake_index_client = MagicMock()
        # Simulate no existing indexes
        fake_index_client.list_indexes = MagicMock(return_value=[])
        fake_index_client.create_index = MagicMock(return_value=None)
        svc._index_client = fake_index_client

        with patch(
            "marketplace.services.search_v2_service._HAS_AZURE_SEARCH", True
        ), patch(
            "marketplace.services.search_v2_service.SearchIndex"
        ) as mock_si:
            results = svc.ensure_indexes()

        # Should have tried to create all three indexes
        assert fake_index_client.create_index.call_count == 3
        assert all(created for created in results.values())

    def test_ensure_indexes_skips_existing(self):
        """ensure_indexes skips creation when the index already exists."""
        from marketplace.services.search_v2_service import SearchV2Service

        svc = SearchV2Service(endpoint="https://fake.search.windows.net", key="fakekey")
        svc._credential = MagicMock()

        # Simulate one existing index
        existing_idx = MagicMock()
        existing_idx.name = "agentchains-listings"
        fake_index_client = MagicMock()
        fake_index_client.list_indexes = MagicMock(return_value=[existing_idx])
        fake_index_client.create_index = MagicMock(return_value=None)
        svc._index_client = fake_index_client

        with patch(
            "marketplace.services.search_v2_service._HAS_AZURE_SEARCH", True
        ), patch("marketplace.services.search_v2_service.SearchIndex"):
            results = svc.ensure_indexes()

        # listings already existed, agents and tools should be created
        assert results.get("agentchains-listings") is False
        assert results.get("agentchains-agents") is True
        assert results.get("agentchains-tools") is True
        assert fake_index_client.create_index.call_count == 2

    # --- delete_document ---

    def test_delete_document_calls_sdk(self):
        """delete_document calls delete_documents on a freshly built SearchClient."""
        from marketplace.services.search_v2_service import SearchV2Service

        svc = SearchV2Service(endpoint="https://fake.search.windows.net", key="fakekey")
        svc._credential = MagicMock()

        fake_client = MagicMock()
        fake_client.delete_documents = MagicMock(return_value=None)

        with patch(
            "marketplace.services.search_v2_service._HAS_AZURE_SEARCH", True
        ), patch(
            "marketplace.services.search_v2_service.SearchClient",
            return_value=fake_client,
        ):
            result = svc.delete_document("agentchains-listings", "doc-abc")

        fake_client.delete_documents.assert_called_once_with(documents=[{"id": "doc-abc"}])
        assert result is True

    def test_delete_document_returns_false_on_exception(self):
        """delete_document returns False when the SDK raises."""
        from marketplace.services.search_v2_service import SearchV2Service

        svc = SearchV2Service(endpoint="https://fake.search.windows.net", key="fakekey")
        svc._credential = MagicMock()

        fake_client = MagicMock()
        fake_client.delete_documents.side_effect = Exception("delete failed")

        with patch(
            "marketplace.services.search_v2_service._HAS_AZURE_SEARCH", True
        ), patch(
            "marketplace.services.search_v2_service.SearchClient",
            return_value=fake_client,
        ):
            result = svc.delete_document("agentchains-listings", "doc-abc")

        assert result is False


# ===========================================================================
# SearchV2Service — field schema helpers
# ===========================================================================


class TestFieldSchemas:
    """Test the internal field-definition helpers."""

    def test_listings_fields_has_required_keys(self):
        """_listings_fields returns all expected field names."""
        from marketplace.services.search_v2_service import _listings_fields

        fields = _listings_fields()
        names = {f["name"] for f in fields}
        assert "id" in names
        assert "title" in names
        assert "description" in names
        assert "category" in names
        assert "price_usd" in names
        assert "seller_id" in names
        assert "status" in names
        assert "trust_score" in names
        assert "tags" in names

    def test_agents_fields_has_required_keys(self):
        """_agents_fields returns all expected field names."""
        from marketplace.services.search_v2_service import _agents_fields

        fields = _agents_fields()
        names = {f["name"] for f in fields}
        assert "id" in names
        assert "name" in names
        assert "description" in names
        assert "category" in names
        assert "status" in names
        assert "creator_id" in names

    def test_tools_fields_has_required_keys(self):
        """_tools_fields returns all expected field names."""
        from marketplace.services.search_v2_service import _tools_fields

        fields = _tools_fields()
        names = {f["name"] for f in fields}
        assert "id" in names
        assert "name" in names
        assert "domain" in names
        assert "category" in names
        assert "version" in names
        assert "status" in names
        assert "execution_count" in names
        assert "success_rate" in names

    def test_listings_id_field_is_key(self):
        """The id field in listings schema is marked as the key."""
        from marketplace.services.search_v2_service import _listings_fields

        id_field = next(f for f in _listings_fields() if f["name"] == "id")
        assert id_field.get("key") is True

    def test_build_search_fields_returns_empty_without_azure(self):
        """_build_search_fields returns [] when Azure SDK is not installed."""
        from marketplace.services.search_v2_service import SearchV2Service

        with patch("marketplace.services.search_v2_service._HAS_AZURE_SEARCH", False):
            result = SearchV2Service._build_search_fields([{"name": "id", "type": "Edm.String"}])

        assert result == []


# ===========================================================================
# get_search_service singleton
# ===========================================================================


class TestGetSearchService:
    """Test the module-level singleton factory."""

    def test_get_search_service_returns_instance(self):
        """get_search_service returns a SearchV2Service instance."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import SearchV2Service, get_search_service

        # Reset the module-level singleton so we get a fresh one
        original = svc_module._search_service
        svc_module._search_service = None
        try:
            service = get_search_service()
            assert isinstance(service, SearchV2Service)
        finally:
            svc_module._search_service = original

    def test_get_search_service_is_cached(self):
        """Calling get_search_service twice returns the same object."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import get_search_service

        original = svc_module._search_service
        svc_module._search_service = None
        try:
            s1 = get_search_service()
            s2 = get_search_service()
            assert s1 is s2
        finally:
            svc_module._search_service = original


# ===========================================================================
# Async DB-backed sync functions — skipped path (no client)
# ===========================================================================


class TestSyncFunctionsSkippedPath:
    """Tests for sync_* functions when there is no Azure search client."""

    async def test_sync_listings_index_skipped_returns_skipped(self, db: AsyncSession):
        """sync_listings_index returns status=skipped when no client."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_listings_index

        # Inject a stub service with no client
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=None)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_listings_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "skipped"
        assert result["synced"] == 0

    async def test_sync_agents_index_skipped_returns_skipped(self, db: AsyncSession):
        """sync_agents_index returns status=skipped when no client."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_agents_index

        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=None)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_agents_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "skipped"
        assert result["synced"] == 0

    async def test_sync_tools_index_skipped_returns_skipped(self, db: AsyncSession):
        """sync_tools_index returns status=skipped when no client."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_tools_index

        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=None)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_tools_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "skipped"
        assert result["synced"] == 0


# ===========================================================================
# Async DB-backed sync functions — happy path with real DB records
# ===========================================================================


class TestSyncFunctionsHappyPath:
    """Tests for sync_* functions that actually read from the in-memory DB."""

    def _make_fake_client(self) -> MagicMock:
        fake = MagicMock()
        fake.merge_or_upload_documents = MagicMock(return_value=None)
        return fake

    async def test_sync_listings_index_syncs_active_listings(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """sync_listings_index uploads active listings to the search client."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_listings_index

        seller, _ = await make_agent("sync-seller-1")
        await make_listing(seller.id, price_usdc=5.0, status="active")
        await make_listing(seller.id, price_usdc=3.0, status="active")

        fake_client = self._make_fake_client()
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=fake_client)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_listings_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "ok"
        assert result["synced"] == 2
        fake_client.merge_or_upload_documents.assert_called_once()
        docs = fake_client.merge_or_upload_documents.call_args[1]["documents"]
        assert len(docs) == 2

    async def test_sync_listings_index_skips_inactive(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """sync_listings_index only uploads active listings, not inactive ones."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_listings_index

        seller, _ = await make_agent("sync-seller-2")
        await make_listing(seller.id, status="active")
        await make_listing(seller.id, status="inactive")
        await make_listing(seller.id, status="pending")

        fake_client = self._make_fake_client()
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=fake_client)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_listings_index(db)
        finally:
            svc_module._search_service = original

        assert result["synced"] == 1

    async def test_sync_listings_index_no_listings_returns_ok(
        self, db: AsyncSession
    ):
        """sync_listings_index returns ok with synced=0 when DB is empty."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_listings_index

        fake_client = self._make_fake_client()
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=fake_client)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_listings_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "ok"
        assert result["synced"] == 0
        fake_client.merge_or_upload_documents.assert_not_called()

    async def test_sync_listings_index_error_path(
        self, db: AsyncSession, make_agent, make_listing
    ):
        """sync_listings_index returns status=error when SDK upload raises."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_listings_index

        seller, _ = await make_agent("sync-seller-err")
        await make_listing(seller.id, status="active")

        fake_client = self._make_fake_client()
        fake_client.merge_or_upload_documents.side_effect = Exception("upload error")
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=fake_client)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_listings_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "error"
        assert result["synced"] == 0
        assert "upload error" in result["error"]

    async def test_sync_agents_index_syncs_active_agents(
        self, db: AsyncSession, make_agent
    ):
        """sync_agents_index uploads active agents to the search client."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_agents_index

        await make_agent("active-agent-a")
        await make_agent("active-agent-b")

        fake_client = self._make_fake_client()
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=fake_client)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_agents_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "ok"
        assert result["synced"] == 2

    async def test_sync_agents_index_no_agents_returns_ok(self, db: AsyncSession):
        """sync_agents_index returns ok with synced=0 when no agents in DB."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_agents_index

        fake_client = self._make_fake_client()
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=fake_client)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_agents_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "ok"
        assert result["synced"] == 0

    async def test_sync_agents_index_error_path(
        self, db: AsyncSession, make_agent
    ):
        """sync_agents_index returns status=error when SDK upload raises."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_agents_index

        await make_agent("err-agent")

        fake_client = self._make_fake_client()
        fake_client.merge_or_upload_documents.side_effect = Exception("agent upload failed")
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=fake_client)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_agents_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "error"
        assert "agent upload failed" in result["error"]

    async def test_sync_tools_index_syncs_approved_and_active(
        self, db: AsyncSession, make_agent, make_creator
    ):
        """sync_tools_index uploads tools with status=approved or status=active."""
        import uuid
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_tools_index
        from marketplace.models.webmcp_tool import WebMCPTool

        creator, _ = await make_creator()

        for status in ("approved", "active", "pending", "suspended"):
            tool = WebMCPTool(
                id=str(uuid.uuid4()),
                name=f"Tool-{status}",
                domain="example.com",
                endpoint_url="https://example.com/mcp",
                creator_id=creator.id,
                category="research",
                version="1.0.0",
                status=status,
            )
            db.add(tool)
        await db.commit()

        fake_client = self._make_fake_client()
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=fake_client)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_tools_index(db)
        finally:
            svc_module._search_service = original

        # Only approved + active (2 tools)
        assert result["status"] == "ok"
        assert result["synced"] == 2

    async def test_sync_tools_index_no_tools_returns_ok(self, db: AsyncSession):
        """sync_tools_index returns ok/0 when no tools match the filter."""
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_tools_index

        fake_client = self._make_fake_client()
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=fake_client)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_tools_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "ok"
        assert result["synced"] == 0

    async def test_sync_tools_index_error_path(
        self, db: AsyncSession, make_agent, make_creator
    ):
        """sync_tools_index returns status=error when SDK upload raises."""
        import uuid
        import marketplace.services.search_v2_service as svc_module
        from marketplace.services.search_v2_service import sync_tools_index
        from marketplace.models.webmcp_tool import WebMCPTool

        creator, _ = await make_creator()
        tool = WebMCPTool(
            id=str(uuid.uuid4()),
            name="SomeTool",
            domain="example.com",
            endpoint_url="https://example.com/mcp",
            creator_id=creator.id,
            category="research",
            version="1.0.0",
            status="active",
        )
        db.add(tool)
        await db.commit()

        fake_client = self._make_fake_client()
        fake_client.merge_or_upload_documents.side_effect = Exception("tool upload failed")
        stub_svc = MagicMock()
        stub_svc._get_search_client = MagicMock(return_value=fake_client)
        original = svc_module._search_service
        svc_module._search_service = stub_svc
        try:
            result = await sync_tools_index(db)
        finally:
            svc_module._search_service = original

        assert result["status"] == "error"
        assert "tool upload failed" in result["error"]
