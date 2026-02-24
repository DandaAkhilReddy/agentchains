"""Sandbox-based WebMCP action executor.

Replaces the simulated _simulate_tool_execution in action_executor.py
with real sandboxed execution using the sandbox manager.
"""

from __future__ import annotations

import logging
from typing import Any

from marketplace.core.sandbox import SandboxConfig, SandboxManager, sandbox_manager

logger = logging.getLogger(__name__)


async def execute_action_in_sandbox(
    action_type: str,
    action_config: dict[str, Any],
    input_data: dict[str, Any],
    *,
    timeout_seconds: int = 120,
    memory_limit_mb: int = 512,
    network_isolated: bool = True,
    allowed_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Execute a WebMCP action inside an isolated sandbox.

    Returns the execution result including proof-of-execution data.
    """
    config = SandboxConfig(
        timeout_seconds=timeout_seconds,
        memory_limit_mb=memory_limit_mb,
        network_enabled=not network_isolated,
        allowed_domains=allowed_domains or [],
    )

    sandbox = await sandbox_manager.create_sandbox(config)
    try:
        await sandbox_manager.start_sandbox(sandbox.sandbox_id)

        # Build the execution script from the action config
        script = _build_execution_script(action_type, action_config, input_data)

        result = await sandbox_manager.execute_in_sandbox(
            sandbox.sandbox_id,
            action_script=script,
            input_data=input_data,
        )

        return {
            "success": True,
            "sandbox_id": sandbox.sandbox_id,
            "output": result,
            "proof": {
                "sandbox_id": sandbox.sandbox_id,
                "action_type": action_type,
                "execution_mode": "sandbox",
                "isolated": network_isolated,
            },
        }

    except Exception as e:
        logger.error("Sandbox execution failed: %s", e)
        return {
            "success": False,
            "sandbox_id": sandbox.sandbox_id,
            "error": str(e),
            "proof": {
                "sandbox_id": sandbox.sandbox_id,
                "action_type": action_type,
                "execution_mode": "sandbox",
                "failed": True,
            },
        }

    finally:
        await sandbox_manager.destroy_sandbox(sandbox.sandbox_id)


def _build_execution_script(
    action_type: str,
    action_config: dict[str, Any],
    input_data: dict[str, Any],
) -> str:
    """Build an execution script from the action configuration.

    Maps action types to their corresponding execution scripts.
    All user-supplied values are serialised via json.dumps() to prevent
    code injection through crafted URLs, selectors, or field values.
    """
    import json as _json

    if action_type == "web_scrape":
        url = input_data.get("url", action_config.get("url", ""))
        selector = action_config.get("selector", "body")
        url_literal = _json.dumps(url)
        selector_literal = _json.dumps(selector)
        return f"""
import json, sys
from playwright.sync_api import sync_playwright

_url = {url_literal}
_selector = {selector_literal}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(_url, timeout=30000)
    content = page.query_selector(_selector)
    result = content.inner_text() if content else ""
    browser.close()
    print(json.dumps({{"result": result}}))
"""

    elif action_type == "screenshot":
        url = input_data.get("url", action_config.get("url", ""))
        url_literal = _json.dumps(url)
        return f"""
import json, base64
from playwright.sync_api import sync_playwright

_url = {url_literal}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(_url, timeout=30000)
    screenshot = page.screenshot()
    browser.close()
    print(json.dumps({{"screenshot_base64": base64.b64encode(screenshot).decode()}}))
"""

    elif action_type == "form_fill":
        url = input_data.get("url", action_config.get("url", ""))
        fields = input_data.get("fields", {})
        url_literal = _json.dumps(url)
        fields_literal = _json.dumps(fields)
        return f"""
import json
from playwright.sync_api import sync_playwright

_url = {url_literal}
_fields = json.loads({_json.dumps(fields_literal)})
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(_url, timeout=30000)
    for selector, value in _fields.items():
        page.fill(selector, str(value))
    browser.close()
    print(json.dumps({{"filled_fields": len(_fields)}}))
"""

    else:
        # Generic action — no user input interpolated
        action_literal = _json.dumps(action_type)
        return f"""
import json
print(json.dumps({{"action_type": {action_literal}, "status": "executed"}}))
"""
