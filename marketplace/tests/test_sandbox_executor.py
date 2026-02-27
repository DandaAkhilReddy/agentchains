"""Tests for sandbox_executor — script building and sandboxed execution.

The sandbox_manager singleton is mocked because it requires container
infrastructure (Docker/Azure). This is a genuine external dependency.
The _build_execution_script function is tested directly (pure function).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from marketplace.services.sandbox_executor import (
    _build_execution_script,
    execute_action_in_sandbox,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_sandbox(sandbox_id: str = "sb-123"):
    """Return a mock object mimicking a sandbox with a sandbox_id attribute."""
    return SimpleNamespace(sandbox_id=sandbox_id)


# ---------------------------------------------------------------------------
# _build_execution_script — pure unit tests
# ---------------------------------------------------------------------------


class TestBuildExecutionScript:

    def test_web_scrape_generates_playwright_script(self):
        script = _build_execution_script(
            "web_scrape",
            {"url": "https://example.com", "selector": "div.content"},
            {"url": "https://override.com"},
        )
        assert "sync_playwright" in script
        assert '"https://override.com"' in script
        assert '"div.content"' in script

    def test_web_scrape_uses_config_url_when_input_missing(self):
        script = _build_execution_script(
            "web_scrape",
            {"url": "https://config-url.com", "selector": "body"},
            {},
        )
        assert "config-url.com" in script

    def test_web_scrape_defaults_selector_to_body(self):
        script = _build_execution_script(
            "web_scrape",
            {"url": "https://example.com"},
            {},
        )
        assert '"body"' in script

    def test_screenshot_generates_screenshot_script(self):
        script = _build_execution_script(
            "screenshot",
            {"url": "https://example.com"},
            {"url": "https://shot.com"},
        )
        assert "screenshot" in script.lower()
        assert "base64" in script
        assert '"https://shot.com"' in script

    def test_screenshot_uses_config_url_fallback(self):
        script = _build_execution_script(
            "screenshot",
            {"url": "https://fallback.com"},
            {},
        )
        assert "fallback.com" in script

    def test_form_fill_generates_fill_script(self):
        script = _build_execution_script(
            "form_fill",
            {"url": "https://form.com"},
            {"url": "https://form.com", "fields": {"#name": "John"}},
        )
        assert "fill" in script.lower()
        assert "form.com" in script

    def test_form_fill_empty_fields(self):
        script = _build_execution_script(
            "form_fill",
            {"url": "https://form.com"},
            {"url": "https://form.com", "fields": {}},
        )
        assert "fill" in script.lower()

    def test_unknown_action_generates_generic_script(self):
        script = _build_execution_script(
            "custom_action",
            {"some": "config"},
            {"some": "input"},
        )
        assert '"custom_action"' in script
        assert '"executed"' in script

    def test_web_scrape_escapes_url_with_quotes(self):
        """URLs with special characters are safely serialized via json.dumps."""
        script = _build_execution_script(
            "web_scrape",
            {"selector": "body"},
            {"url": 'https://example.com/path?q="test"&a=b'},
        )
        assert "example.com" in script
        assert "json" in script

    def test_form_fill_fields_are_json_serialized(self):
        fields = {"#email": "user@test.com", "#pass": "se<cret>"}
        script = _build_execution_script(
            "form_fill",
            {"url": "https://form.com"},
            {"url": "https://form.com", "fields": fields},
        )
        assert "json.loads" in script

    def test_form_fill_uses_config_url_fallback(self):
        script = _build_execution_script(
            "form_fill",
            {"url": "https://config-form.com"},
            {"fields": {"#name": "John"}},
        )
        assert "config-form.com" in script


# ---------------------------------------------------------------------------
# execute_action_in_sandbox — success path
# ---------------------------------------------------------------------------


class TestExecuteActionSuccess:

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_returns_success_on_normal_execution(self, mock_mgr):
        sandbox = _mock_sandbox("sb-ok")
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={"result": "data"})
        mock_mgr.destroy_sandbox = AsyncMock()

        result = await execute_action_in_sandbox(
            "web_scrape",
            {"url": "https://example.com", "selector": "body"},
            {"url": "https://example.com"},
        )
        assert result["success"] is True
        assert result["sandbox_id"] == "sb-ok"
        assert result["output"] == {"result": "data"}
        assert result["proof"]["action_type"] == "web_scrape"
        assert result["proof"]["execution_mode"] == "sandbox"

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_sandbox_created_with_custom_config(self, mock_mgr):
        sandbox = _mock_sandbox()
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={})
        mock_mgr.destroy_sandbox = AsyncMock()

        await execute_action_in_sandbox(
            "screenshot",
            {"url": "https://example.com"},
            {},
            timeout_seconds=60,
            memory_limit_mb=256,
            network_isolated=False,
            allowed_domains=["example.com"],
        )

        config = mock_mgr.create_sandbox.call_args[0][0]
        assert config.timeout_seconds == 60
        assert config.memory_limit_mb == 256
        assert config.network_enabled is True
        assert config.allowed_domains == ["example.com"]

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_proof_contains_isolated_flag(self, mock_mgr):
        sandbox = _mock_sandbox()
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={})
        mock_mgr.destroy_sandbox = AsyncMock()

        result = await execute_action_in_sandbox(
            "web_scrape", {}, {}, network_isolated=True
        )
        assert result["proof"]["isolated"] is True

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_proof_contains_not_isolated_flag(self, mock_mgr):
        sandbox = _mock_sandbox()
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={})
        mock_mgr.destroy_sandbox = AsyncMock()

        result = await execute_action_in_sandbox(
            "web_scrape", {}, {}, network_isolated=False
        )
        assert result["proof"]["isolated"] is False


# ---------------------------------------------------------------------------
# execute_action_in_sandbox — failure path
# ---------------------------------------------------------------------------


class TestExecuteActionFailure:

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_returns_failure_on_execution_error(self, mock_mgr):
        sandbox = _mock_sandbox("sb-fail")
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(side_effect=RuntimeError("timeout"))
        mock_mgr.destroy_sandbox = AsyncMock()

        result = await execute_action_in_sandbox(
            "web_scrape", {"url": "https://example.com"}, {}
        )
        assert result["success"] is False
        assert result["sandbox_id"] == "sb-fail"
        assert "timeout" in result["error"]
        assert result["proof"]["failed"] is True

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_sandbox_destroyed_on_failure(self, mock_mgr):
        sandbox = _mock_sandbox("sb-cleanup")
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(side_effect=Exception("boom"))
        mock_mgr.destroy_sandbox = AsyncMock()

        await execute_action_in_sandbox("web_scrape", {}, {})
        mock_mgr.destroy_sandbox.assert_awaited_once_with("sb-cleanup")

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_sandbox_destroyed_on_success(self, mock_mgr):
        sandbox = _mock_sandbox("sb-ok")
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={"ok": True})
        mock_mgr.destroy_sandbox = AsyncMock()

        await execute_action_in_sandbox("web_scrape", {}, {})
        mock_mgr.destroy_sandbox.assert_awaited_once_with("sb-ok")

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_start_sandbox_failure_still_destroys(self, mock_mgr):
        sandbox = _mock_sandbox("sb-start-fail")
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock(side_effect=RuntimeError("start failed"))
        mock_mgr.destroy_sandbox = AsyncMock()

        result = await execute_action_in_sandbox("web_scrape", {}, {})
        assert result["success"] is False
        assert "start failed" in result["error"]
        mock_mgr.destroy_sandbox.assert_awaited_once_with("sb-start-fail")


# ---------------------------------------------------------------------------
# execute_action_in_sandbox — default parameters
# ---------------------------------------------------------------------------


class TestExecuteActionDefaults:

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_default_timeout_is_120(self, mock_mgr):
        sandbox = _mock_sandbox()
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={})
        mock_mgr.destroy_sandbox = AsyncMock()

        await execute_action_in_sandbox("web_scrape", {}, {})
        config = mock_mgr.create_sandbox.call_args[0][0]
        assert config.timeout_seconds == 120

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_default_memory_limit_is_512(self, mock_mgr):
        sandbox = _mock_sandbox()
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={})
        mock_mgr.destroy_sandbox = AsyncMock()

        await execute_action_in_sandbox("web_scrape", {}, {})
        config = mock_mgr.create_sandbox.call_args[0][0]
        assert config.memory_limit_mb == 512

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_default_network_isolated_true(self, mock_mgr):
        sandbox = _mock_sandbox()
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={})
        mock_mgr.destroy_sandbox = AsyncMock()

        await execute_action_in_sandbox("web_scrape", {}, {})
        config = mock_mgr.create_sandbox.call_args[0][0]
        assert config.network_enabled is False

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_default_allowed_domains_empty(self, mock_mgr):
        sandbox = _mock_sandbox()
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={})
        mock_mgr.destroy_sandbox = AsyncMock()

        await execute_action_in_sandbox("web_scrape", {}, {})
        config = mock_mgr.create_sandbox.call_args[0][0]
        assert config.allowed_domains == []

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_execute_passes_script_and_input(self, mock_mgr):
        sandbox = _mock_sandbox("sb-check")
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={})
        mock_mgr.destroy_sandbox = AsyncMock()

        input_data = {"url": "https://test.com"}
        await execute_action_in_sandbox(
            "web_scrape", {"selector": "h1"}, input_data
        )
        call_args = mock_mgr.execute_in_sandbox.call_args
        assert call_args[0][0] == "sb-check"
        assert "action_script" in call_args[1] or len(call_args[0]) > 1

    @patch("marketplace.services.sandbox_executor.sandbox_manager")
    async def test_generic_action_returns_success(self, mock_mgr):
        sandbox = _mock_sandbox("sb-generic")
        mock_mgr.create_sandbox = AsyncMock(return_value=sandbox)
        mock_mgr.start_sandbox = AsyncMock()
        mock_mgr.execute_in_sandbox = AsyncMock(return_value={"status": "executed"})
        mock_mgr.destroy_sandbox = AsyncMock()

        result = await execute_action_in_sandbox(
            "custom_action", {"key": "val"}, {"input": "data"}
        )
        assert result["success"] is True
        assert result["proof"]["action_type"] == "custom_action"
