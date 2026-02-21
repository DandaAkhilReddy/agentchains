"""Unit tests for the 3 WebMCP MCP tool handlers in marketplace/mcp/tools.py.

Covers:
  - TOOL_DEFINITIONS static validation for webmcp_discover_tools,
    webmcp_execute_action, webmcp_verify_execution
  - execute_tool dispatch for all 3 handlers with mocked service calls
  - Edge cases: missing required args, no-proof execution, execution not found

19 tests total.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.mcp.tools import TOOL_DEFINITIONS, execute_tool
from marketplace.tests.conftest import TestSession


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())


def _get_tool_def(name: str) -> dict:
    """Fetch a single tool definition by name; raises if missing."""
    for tool in TOOL_DEFINITIONS:
        if tool["name"] == name:
            return tool
    raise KeyError(f"Tool '{name}' not found in TOOL_DEFINITIONS")


WEBMCP_TOOL_NAMES = [
    "webmcp_discover_tools",
    "webmcp_execute_action",
    "webmcp_verify_execution",
]


# ═══════════════════════════════════════════════════════════════════════════════
# TestWebMCPToolDefinitions (7 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebMCPToolDefinitions:
    """Static validation of the 3 WebMCP entries in TOOL_DEFINITIONS."""

    def test_webmcp_discover_tools_exists(self):
        """webmcp_discover_tools is registered in TOOL_DEFINITIONS."""
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "webmcp_discover_tools" in names

    def test_webmcp_execute_action_exists(self):
        """webmcp_execute_action is registered in TOOL_DEFINITIONS."""
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "webmcp_execute_action" in names

    def test_webmcp_verify_execution_exists(self):
        """webmcp_verify_execution is registered in TOOL_DEFINITIONS."""
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "webmcp_verify_execution" in names

    def test_all_webmcp_tools_have_name_description_inputschema(self):
        """Every WebMCP tool definition has name, description, and inputSchema."""
        for name in WEBMCP_TOOL_NAMES:
            tool = _get_tool_def(name)
            assert "name" in tool
            assert "description" in tool, f"{name} missing description"
            assert "inputSchema" in tool, f"{name} missing inputSchema"
            assert isinstance(tool["description"], str) and tool["description"]

    def test_all_webmcp_tools_inputschema_type_is_object(self):
        """inputSchema.type == 'object' for every WebMCP tool."""
        for name in WEBMCP_TOOL_NAMES:
            tool = _get_tool_def(name)
            assert tool["inputSchema"]["type"] == "object", (
                f"{name} inputSchema.type is not 'object'"
            )

    def test_webmcp_execute_action_requires_action_id(self):
        """webmcp_execute_action declares 'action_id' in required fields."""
        tool = _get_tool_def("webmcp_execute_action")
        required = tool["inputSchema"].get("required", [])
        assert "action_id" in required

    def test_webmcp_verify_execution_requires_execution_id(self):
        """webmcp_verify_execution declares 'execution_id' in required fields."""
        tool = _get_tool_def("webmcp_verify_execution")
        required = tool["inputSchema"].get("required", [])
        assert "execution_id" in required

    def test_webmcp_discover_tools_has_no_required_fields(self):
        """webmcp_discover_tools has no mandatory fields — all params are optional."""
        tool = _get_tool_def("webmcp_discover_tools")
        required = tool["inputSchema"].get("required", [])
        assert required == [], (
            "webmcp_discover_tools should have no required fields; got: " + str(required)
        )

    def test_webmcp_discover_tools_properties_include_category_and_domain(self):
        """webmcp_discover_tools exposes 'category' and 'domain' filter properties."""
        tool = _get_tool_def("webmcp_discover_tools")
        props = tool["inputSchema"].get("properties", {})
        assert "category" in props
        assert "domain" in props

    def test_webmcp_execute_action_properties_include_consent(self):
        """webmcp_execute_action exposes a 'consent' boolean property."""
        tool = _get_tool_def("webmcp_execute_action")
        props = tool["inputSchema"].get("properties", {})
        assert "consent" in props
        assert props["consent"]["type"] == "boolean"


# ═══════════════════════════════════════════════════════════════════════════════
# TestWebMCPDiscoverTools (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebMCPDiscoverTools:
    """execute_tool('webmcp_discover_tools', ...) dispatches correctly."""

    @pytest.mark.asyncio
    async def test_discover_returns_tools_list_and_total(self):
        """webmcp_discover_tools returns dict with 'tools' list and 'total' count."""
        fake_tools = [
            {"id": _new_id(), "name": "amazon-search", "category": "shopping"},
            {"id": _new_id(), "name": "google-forms", "category": "form_fill"},
        ]
        mock_list_tools = AsyncMock(return_value=(fake_tools, 2))

        async with TestSession() as db:
            with patch(
                "marketplace.services.webmcp_service.list_tools",
                mock_list_tools,
            ):
                result = await execute_tool(
                    "webmcp_discover_tools",
                    {},
                    agent_id=_new_id(),
                    db=db,
                )

        assert "tools" in result
        assert "total" in result
        assert result["total"] == 2
        assert len(result["tools"]) == 2

    @pytest.mark.asyncio
    async def test_discover_passes_category_filter_to_service(self):
        """webmcp_discover_tools forwards 'category' argument to list_tools."""
        mock_list_tools = AsyncMock(return_value=([], 0))

        async with TestSession() as db:
            with patch(
                "marketplace.services.webmcp_service.list_tools",
                mock_list_tools,
            ):
                await execute_tool(
                    "webmcp_discover_tools",
                    {"category": "shopping"},
                    agent_id=_new_id(),
                    db=db,
                )

        _call_kwargs = mock_list_tools.call_args
        assert _call_kwargs is not None
        # category is passed as keyword argument
        assert _call_kwargs.kwargs.get("category") == "shopping"

    @pytest.mark.asyncio
    async def test_discover_empty_db_returns_zero_total(self):
        """webmcp_discover_tools with no matching tools returns total=0 and empty list."""
        mock_list_tools = AsyncMock(return_value=([], 0))

        async with TestSession() as db:
            with patch(
                "marketplace.services.webmcp_service.list_tools",
                mock_list_tools,
            ):
                result = await execute_tool(
                    "webmcp_discover_tools",
                    {},
                    agent_id=_new_id(),
                    db=db,
                )

        assert result["tools"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_discover_passes_domain_filter_to_service(self):
        """webmcp_discover_tools forwards 'domain' argument to list_tools."""
        mock_list_tools = AsyncMock(return_value=([], 0))

        async with TestSession() as db:
            with patch(
                "marketplace.services.webmcp_service.list_tools",
                mock_list_tools,
            ):
                await execute_tool(
                    "webmcp_discover_tools",
                    {"domain": "amazon.com"},
                    agent_id=_new_id(),
                    db=db,
                )

        _call_kwargs = mock_list_tools.call_args
        assert _call_kwargs.kwargs.get("domain") == "amazon.com"

    @pytest.mark.asyncio
    async def test_discover_passes_page_and_page_size(self):
        """webmcp_discover_tools forwards pagination args with defaults page=1, page_size=20."""
        mock_list_tools = AsyncMock(return_value=([], 0))

        async with TestSession() as db:
            with patch(
                "marketplace.services.webmcp_service.list_tools",
                mock_list_tools,
            ):
                await execute_tool(
                    "webmcp_discover_tools",
                    {"page": 2, "page_size": 10},
                    agent_id=_new_id(),
                    db=db,
                )

        _call_kwargs = mock_list_tools.call_args
        assert _call_kwargs.kwargs.get("page") == 2
        assert _call_kwargs.kwargs.get("page_size") == 10


# ═══════════════════════════════════════════════════════════════════════════════
# TestWebMCPExecuteAction (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebMCPExecuteAction:
    """execute_tool('webmcp_execute_action', ...) dispatches correctly."""

    @pytest.mark.asyncio
    async def test_execute_with_valid_params_returns_execution_result(self):
        """webmcp_execute_action with action_id returns the service result dict."""
        action_id = _new_id()
        agent_id = _new_id()
        execution_id = _new_id()

        fake_result = {
            "id": execution_id,
            "action_listing_id": action_id,
            "buyer_id": agent_id,
            "status": "completed",
            "proof_of_execution": "eyJhbGciOiJIUzI1NiJ9.fake",
            "proof_verified": True,
        }
        mock_execute = AsyncMock(return_value=fake_result)

        async with TestSession() as db:
            with patch(
                "marketplace.services.action_executor.execute_action",
                mock_execute,
            ):
                result = await execute_tool(
                    "webmcp_execute_action",
                    {"action_id": action_id, "consent": True},
                    agent_id=agent_id,
                    db=db,
                )

        assert result["id"] == execution_id
        assert result["status"] == "completed"
        assert result["proof_verified"] is True

    @pytest.mark.asyncio
    async def test_execute_passes_consent_true_by_default(self):
        """webmcp_execute_action defaults consent=True when not supplied."""
        action_id = _new_id()
        mock_execute = AsyncMock(return_value={"status": "completed"})

        async with TestSession() as db:
            with patch(
                "marketplace.services.action_executor.execute_action",
                mock_execute,
            ):
                await execute_tool(
                    "webmcp_execute_action",
                    {"action_id": action_id},          # no consent key
                    agent_id=_new_id(),
                    db=db,
                )

        _call_kwargs = mock_execute.call_args
        assert _call_kwargs.kwargs.get("consent") is True

    @pytest.mark.asyncio
    async def test_execute_passes_parameters_dict_to_service(self):
        """webmcp_execute_action forwards 'parameters' dict to execute_action."""
        action_id = _new_id()
        params = {"url": "https://example.com", "query": "coffee"}
        mock_execute = AsyncMock(return_value={"status": "completed"})

        async with TestSession() as db:
            with patch(
                "marketplace.services.action_executor.execute_action",
                mock_execute,
            ):
                await execute_tool(
                    "webmcp_execute_action",
                    {"action_id": action_id, "parameters": params, "consent": True},
                    agent_id=_new_id(),
                    db=db,
                )

        _call_kwargs = mock_execute.call_args
        assert _call_kwargs.kwargs.get("parameters") == params

    @pytest.mark.asyncio
    async def test_execute_maps_action_id_to_listing_id_param(self):
        """webmcp_execute_action passes action_id as listing_id to execute_action."""
        action_id = _new_id()
        mock_execute = AsyncMock(return_value={"status": "completed"})

        async with TestSession() as db:
            with patch(
                "marketplace.services.action_executor.execute_action",
                mock_execute,
            ):
                await execute_tool(
                    "webmcp_execute_action",
                    {"action_id": action_id, "consent": True},
                    agent_id=_new_id(),
                    db=db,
                )

        _call_kwargs = mock_execute.call_args
        # The handler passes action_id as listing_id (not action_id) to the service
        assert _call_kwargs.kwargs.get("listing_id") == action_id


# ═══════════════════════════════════════════════════════════════════════════════
# TestWebMCPVerifyExecution (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebMCPVerifyExecution:
    """execute_tool('webmcp_verify_execution', ...) dispatches correctly."""

    @pytest.mark.asyncio
    async def test_verify_returns_verified_true_for_valid_proof(self):
        """webmcp_verify_execution returns verified=True when proof is valid."""
        execution_id = _new_id()
        tool_id = _new_id()

        fake_execution = {
            "id": execution_id,
            "tool_id": tool_id,
            "status": "completed",
            "proof_of_execution": "eyJhbGciOiJIUzI1NiJ9.valid_proof",
        }
        fake_verify_result = {
            "valid": True,
            "claims": {"execution_id": execution_id, "tool_id": tool_id},
            "error": None,
        }

        mock_get_execution = AsyncMock(return_value=fake_execution)
        mock_verify_proof = MagicMock(return_value=fake_verify_result)

        async with TestSession() as db:
            with patch(
                "marketplace.services.action_executor.get_execution",
                mock_get_execution,
            ), patch(
                "marketplace.services.proof_of_execution_service.verify_proof",
                mock_verify_proof,
            ):
                result = await execute_tool(
                    "webmcp_verify_execution",
                    {"execution_id": execution_id},
                    agent_id=_new_id(),
                    db=db,
                )

        assert result["execution_id"] == execution_id
        assert result["verified"] is True
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_verify_returns_error_when_execution_not_found(self):
        """webmcp_verify_execution returns an error dict when execution_id is unknown."""
        execution_id = _new_id()
        mock_get_execution = AsyncMock(return_value=None)

        async with TestSession() as db:
            with patch(
                "marketplace.services.action_executor.get_execution",
                mock_get_execution,
            ):
                result = await execute_tool(
                    "webmcp_verify_execution",
                    {"execution_id": execution_id},
                    agent_id=_new_id(),
                    db=db,
                )

        assert "error" in result
        assert result["error"] == "Execution not found"
        assert result["execution_id"] == execution_id

    @pytest.mark.asyncio
    async def test_verify_returns_verified_false_when_no_proof(self):
        """webmcp_verify_execution returns verified=False when proof_of_execution is None."""
        execution_id = _new_id()
        fake_execution = {
            "id": execution_id,
            "status": "completed",
            "proof_of_execution": None,  # no proof yet
        }
        mock_get_execution = AsyncMock(return_value=fake_execution)

        async with TestSession() as db:
            with patch(
                "marketplace.services.action_executor.get_execution",
                mock_get_execution,
            ):
                result = await execute_tool(
                    "webmcp_verify_execution",
                    {"execution_id": execution_id},
                    agent_id=_new_id(),
                    db=db,
                )

        assert result["verified"] is False
        assert "error" in result
        assert result["error"] == "No proof available"
        assert result["execution_id"] == execution_id

    @pytest.mark.asyncio
    async def test_verify_returns_claims_on_success(self):
        """webmcp_verify_execution includes claims dict in result when proof is valid."""
        execution_id = _new_id()
        expected_claims = {
            "execution_id": execution_id,
            "tool_id": _new_id(),
            "status": "success",
        }
        fake_execution = {
            "id": execution_id,
            "status": "completed",
            "proof_of_execution": "eyJhbGciOiJIUzI1NiJ9.some_jwt",
        }
        fake_verify_result = {
            "valid": True,
            "claims": expected_claims,
            "error": None,
        }

        async with TestSession() as db:
            with patch(
                "marketplace.services.action_executor.get_execution",
                AsyncMock(return_value=fake_execution),
            ), patch(
                "marketplace.services.proof_of_execution_service.verify_proof",
                MagicMock(return_value=fake_verify_result),
            ):
                result = await execute_tool(
                    "webmcp_verify_execution",
                    {"execution_id": execution_id},
                    agent_id=_new_id(),
                    db=db,
                )

        assert result["claims"] == expected_claims

    @pytest.mark.asyncio
    async def test_verify_returns_verified_false_for_invalid_proof(self):
        """webmcp_verify_execution returns verified=False when verify_proof says invalid."""
        execution_id = _new_id()
        fake_execution = {
            "id": execution_id,
            "status": "completed",
            "proof_of_execution": "eyJhbGciOiJIUzI1NiJ9.tampered_jwt",
        }
        fake_verify_result = {
            "valid": False,
            "claims": None,
            "error": "Signature verification failed",
        }

        async with TestSession() as db:
            with patch(
                "marketplace.services.action_executor.get_execution",
                AsyncMock(return_value=fake_execution),
            ), patch(
                "marketplace.services.proof_of_execution_service.verify_proof",
                MagicMock(return_value=fake_verify_result),
            ):
                result = await execute_tool(
                    "webmcp_verify_execution",
                    {"execution_id": execution_id},
                    agent_id=_new_id(),
                    db=db,
                )

        assert result["verified"] is False
        assert result["error"] == "Signature verification failed"


# ═══════════════════════════════════════════════════════════════════════════════
# TestUnknownToolFallthrough (1 test)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnknownToolFallthrough:
    """execute_tool returns an error dict for tool names it doesn't recognise."""

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_dict(self):
        """Calling execute_tool with an unknown name returns {'error': 'Unknown tool: ...'} ."""
        async with TestSession() as db:
            result = await execute_tool(
                "webmcp_nonexistent_tool",
                {},
                agent_id=_new_id(),
                db=db,
            )

        assert "error" in result
        assert "webmcp_nonexistent_tool" in result["error"]
