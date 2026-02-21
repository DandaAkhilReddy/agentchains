"""AgentChains API client with async support."""

from __future__ import annotations

from typing import Any

import httpx


class AgentChainsClient:
    """Async client for the AgentChains marketplace API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        token: str | None = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> AgentChainsClient:
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Use 'async with AgentChainsClient() as client:'")
        return self._client

    # --- Health ---

    async def health(self) -> dict[str, Any]:
        resp = await self.client.get("/api/v1/health")
        resp.raise_for_status()
        return resp.json()

    # --- Agents ---

    async def register_agent(self, data: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/api/v1/agents", json=data)
        resp.raise_for_status()
        return resp.json()

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        resp = await self.client.get(f"/api/v1/agents/{agent_id}")
        resp.raise_for_status()
        return resp.json()

    async def list_agents(self, skip: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        resp = await self.client.get("/api/v1/agents", params={"skip": skip, "limit": limit})
        resp.raise_for_status()
        return resp.json()

    # --- Listings ---

    async def create_listing(self, data: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/api/v1/listings", json=data)
        resp.raise_for_status()
        return resp.json()

    async def get_listing(self, listing_id: str) -> dict[str, Any]:
        resp = await self.client.get(f"/api/v1/listings/{listing_id}")
        resp.raise_for_status()
        return resp.json()

    async def search_listings(self, query: str = "", skip: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        resp = await self.client.get("/api/v1/listings", params={"q": query, "skip": skip, "limit": limit})
        resp.raise_for_status()
        return resp.json()

    # --- Transactions ---

    async def create_transaction(self, data: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/api/v1/transactions", json=data)
        resp.raise_for_status()
        return resp.json()

    async def get_transaction(self, tx_id: str) -> dict[str, Any]:
        resp = await self.client.get(f"/api/v1/transactions/{tx_id}")
        resp.raise_for_status()
        return resp.json()

    # --- WebMCP Actions ---

    async def execute_action(self, action_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = await self.client.post(
            f"/api/v3/webmcp/actions/{action_id}/execute",
            json={"parameters": params or {}},
        )
        resp.raise_for_status()
        return resp.json()

    # --- Workflows ---

    async def create_workflow(self, data: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/api/v3/orchestration/workflows", json=data)
        resp.raise_for_status()
        return resp.json()

    async def execute_workflow(self, workflow_id: str, input_data: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = await self.client.post(
            f"/api/v3/orchestration/workflows/{workflow_id}/execute",
            json={"input_data": input_data or {}},
        )
        resp.raise_for_status()
        return resp.json()
