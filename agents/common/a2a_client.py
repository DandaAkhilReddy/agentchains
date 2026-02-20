"""A2A Client SDK — discover and communicate with A2A-compliant agents."""

import json
import logging
from typing import Any, AsyncGenerator

import httpx

logger = logging.getLogger(__name__)


class A2AClient:
    """Client for discovering and calling A2A-compliant agents.

    Usage:
        client = A2AClient("http://localhost:9000")
        card = await client.discover()
        result = await client.send_task("search", "Find Python tutorials")
        task = await client.get_task(result["id"])
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        auth_token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.auth_token = auth_token
        self._agent_card: dict | None = None

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def discover(self, url: str | None = None) -> dict:
        """Fetch the agent card from /.well-known/agent.json.

        Args:
            url: Override URL (default: self.base_url)

        Returns:
            Agent card dict with name, description, skills, capabilities
        """
        target = url or self.base_url
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{target}/.well-known/agent.json",
                headers=self._headers(),
            )
            response.raise_for_status()
            self._agent_card = response.json()
            return self._agent_card

    async def send_task(
        self,
        skill_id: str,
        message: str,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """Send a task to the agent using JSON-RPC tasks/send.

        Args:
            skill_id: Which skill to invoke
            message: The input message text
            params: Additional parameters

        Returns:
            Task dict with id, state, artifacts
        """
        rpc_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "skill_id": skill_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": message}],
                },
                **(params or {}),
            },
        }

        return await self._rpc_call(rpc_body)

    async def get_task(self, task_id: str) -> dict:
        """Get task status and artifacts using JSON-RPC tasks/get.

        Args:
            task_id: The task ID to query

        Returns:
            Task dict with current state and artifacts
        """
        rpc_body = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tasks/get",
            "params": {"id": task_id},
        }
        return await self._rpc_call(rpc_body)

    async def cancel_task(self, task_id: str) -> dict:
        """Cancel a running task using JSON-RPC tasks/cancel.

        Args:
            task_id: The task ID to cancel

        Returns:
            Task dict with updated state
        """
        rpc_body = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tasks/cancel",
            "params": {"id": task_id},
        }
        return await self._rpc_call(rpc_body)

    async def send_task_streaming(
        self,
        skill_id: str,
        message: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Send a task and stream updates via SSE using tasks/sendSubscribe.

        Args:
            skill_id: Which skill to invoke
            message: The input message text
            params: Additional parameters

        Yields:
            Update dicts with type, task_id, and data
        """
        rpc_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/sendSubscribe",
            "params": {
                "skill_id": skill_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": message}],
                },
                **(params or {}),
            },
        }

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                self.base_url,
                json=rpc_body,
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue

    async def _rpc_call(self, body: dict) -> dict:
        """Make a JSON-RPC call with retry logic."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.base_url,
                        json=body,
                        headers=self._headers(),
                    )
                    response.raise_for_status()
                    result = response.json()

                    if "error" in result:
                        error = result["error"]
                        raise A2AError(
                            code=error.get("code", -1),
                            message=error.get("message", "Unknown error"),
                        )

                    return result.get("result", {})

            except httpx.HTTPStatusError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

            except A2AError:
                raise

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                    continue

        raise A2AError(code=-1, message=f"All retries failed: {last_error}")

    @property
    def agent_card(self) -> dict | None:
        """Return cached agent card (call discover() first)."""
        return self._agent_card


class A2AError(Exception):
    """Error from an A2A JSON-RPC call."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"A2A Error {code}: {message}")
