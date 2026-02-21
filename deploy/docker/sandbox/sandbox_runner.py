"""Playwright sandbox runner — HTTP server that executes browser tasks.

Receives task JSON via POST /task, runs Playwright actions inside a
sandboxed container, and returns structured results.  Exposes a
/health endpoint for readiness probes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def execute_task(task: dict[str, Any]) -> dict[str, Any]:
    """Execute a Playwright task described by *task* JSON.

    Supported actions:
    - ``navigate``: Go to a URL and return the page title.
    - ``screenshot``: Navigate and capture a base64-encoded screenshot.
    - ``evaluate``: Navigate and run a JavaScript expression.

    Returns a dict with ``status``, ``action``, and action-specific
    result fields.
    """
    from playwright.async_api import async_playwright

    action = task.get("action", "navigate")
    url = task.get("url", "about:blank")
    timeout = task.get("timeout", 30_000)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(timeout)

        try:
            await page.goto(url, wait_until="domcontentloaded")

            if action == "navigate":
                title = await page.title()
                return {"status": "ok", "action": action, "url": url, "title": title}

            elif action == "screenshot":
                screenshot_bytes = await page.screenshot(type="png")
                import base64

                encoded = base64.b64encode(screenshot_bytes).decode()
                return {
                    "status": "ok",
                    "action": action,
                    "url": url,
                    "screenshot_base64": encoded,
                }

            elif action == "evaluate":
                expression = task.get("expression", "document.title")
                result = await page.evaluate(expression)
                return {
                    "status": "ok",
                    "action": action,
                    "url": url,
                    "result": result,
                }

            else:
                return {"status": "error", "message": f"Unknown action: {action}"}

        finally:
            await browser.close()


class SandboxHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the sandbox runner."""

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests — only /health is supported."""
        if self.path == "/health":
            self._json_response(200, {"status": "healthy"})
        else:
            self._json_response(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        """Handle POST /task — execute a Playwright task."""
        if self.path != "/task":
            self._json_response(404, {"error": "Not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            task = json.loads(body)
        except json.JSONDecodeError:
            self._json_response(400, {"error": "Invalid JSON"})
            return

        try:
            result = asyncio.run(execute_task(task))
            self._json_response(200, result)
        except Exception:
            logger.exception("Task execution failed")
            self._json_response(
                500,
                {"status": "error", "message": traceback.format_exc()},
            )

    def _json_response(self, status: int, data: dict[str, Any]) -> None:
        """Write a JSON HTTP response."""
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Route HTTP log messages through the stdlib logger."""
        logger.info(format, *args)


def main() -> None:
    """Start the sandbox HTTP server on port 8080."""
    host, port = "0.0.0.0", 8080
    server = HTTPServer((host, port), SandboxHandler)
    logger.info("Sandbox runner listening on %s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down sandbox runner")
        server.server_close()


if __name__ == "__main__":
    main()
