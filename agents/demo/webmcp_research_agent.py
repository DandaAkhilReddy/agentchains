"""WebMCP Research Agent — demo agent for structured research across academic sites.

This demonstrates how an A2A agent can use WebMCP actions from the marketplace
to extract structured data from research websites without screen parsing.

Usage:
    python -m agents.demo.webmcp_research_agent
"""

import asyncio
import json
import logging
import os

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MARKETPLACE_URL = os.getenv("MARKETPLACE_URL", "http://localhost:8000")


async def register_agent() -> dict:
    """Register this demo agent with the marketplace."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MARKETPLACE_URL}/api/v1/agents/register",
            json={
                "name": "webmcp-research-demo",
                "description": "Demo agent that extracts structured research data using WebMCP actions",
                "agent_type": "buyer",
                "capabilities": ["research", "webmcp", "data_extraction", "academic"],
                "public_key": "demo-public-key",
            },
        )
        data = response.json()
        logger.info("Registered agent: %s", data.get("name", data.get("id")))
        return data


async def discover_research_tools(token: str) -> list[dict]:
    """Discover WebMCP tools in the research category."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{MARKETPLACE_URL}/api/v3/webmcp/tools",
            params={"category": "research"},
            headers={"Authorization": f"Bearer {token}"},
        )
        data = response.json()
        tools = data.get("tools", [])
        logger.info("Found %d research tools", len(tools))
        return tools


async def find_research_actions(token: str) -> list[dict]:
    """Find available research action listings."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{MARKETPLACE_URL}/api/v3/webmcp/actions",
            params={"category": "research"},
            headers={"Authorization": f"Bearer {token}"},
        )
        data = response.json()
        actions = data.get("actions", [])
        logger.info("Found %d research actions", len(actions))
        return actions


async def execute_research_query(token: str, action_id: str, query: str, max_papers: int = 10) -> dict:
    """Execute a research extraction action."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MARKETPLACE_URL}/api/v3/webmcp/execute/{action_id}",
            json={
                "parameters": {
                    "query": query,
                    "max_papers": max_papers,
                    "include_abstracts": True,
                },
                "consent": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        result = response.json()
        logger.info(
            "Execution %s: status=%s, time=%sms",
            result.get("id", "?"),
            result.get("status"),
            result.get("execution_time_ms"),
        )
        return result


async def main():
    """Demo: register → discover tools → find actions → execute research query."""
    logger.info("=== WebMCP Research Agent Demo ===")

    # Step 1: Register
    agent = await register_agent()
    token = agent.get("jwt_token", "")
    if not token:
        logger.error("Failed to get JWT token")
        return

    # Step 2: Discover tools
    tools = await discover_research_tools(token)
    for tool in tools:
        logger.info("  Tool: %s (%s) — %s", tool["name"], tool["domain"], tool["category"])

    # Step 3: Find action listings
    actions = await find_research_actions(token)
    if not actions:
        logger.info("No research actions available yet. Create one in the marketplace.")
        logger.info("Demo complete (marketplace is empty for research actions).")
        return

    # Step 4: Execute research query
    action = actions[0]
    logger.info("Executing action: %s ($%s per execution)", action["title"], action["price_per_execution"])
    result = await execute_research_query(
        token, action["id"], "transformer attention mechanisms 2024"
    )

    logger.info("Result: %s", json.dumps(result, indent=2))
    logger.info("=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
