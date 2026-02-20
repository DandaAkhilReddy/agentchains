"""WebMCP Shopping Agent — demo agent for price comparison across e-commerce sites.

This demonstrates how an A2A agent can use WebMCP actions from the marketplace
to perform structured price comparisons without screen scraping.

Usage:
    python -m agents.demo.webmcp_shopping_agent
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
                "name": "webmcp-shopping-demo",
                "description": "Demo agent that compares prices across e-commerce sites using WebMCP actions",
                "agent_type": "buyer",
                "capabilities": ["price_comparison", "webmcp", "shopping"],
                "public_key": "demo-public-key",
            },
        )
        data = response.json()
        logger.info("Registered agent: %s", data.get("name", data.get("id")))
        return data


async def discover_shopping_tools(token: str) -> list[dict]:
    """Discover WebMCP tools in the shopping category."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{MARKETPLACE_URL}/api/v3/webmcp/tools",
            params={"category": "shopping"},
            headers={"Authorization": f"Bearer {token}"},
        )
        data = response.json()
        tools = data.get("tools", [])
        logger.info("Found %d shopping tools", len(tools))
        return tools


async def find_action_listings(token: str) -> list[dict]:
    """Find available action listings for shopping."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{MARKETPLACE_URL}/api/v3/webmcp/actions",
            params={"category": "shopping"},
            headers={"Authorization": f"Bearer {token}"},
        )
        data = response.json()
        actions = data.get("actions", [])
        logger.info("Found %d shopping actions", len(actions))
        return actions


async def execute_price_comparison(token: str, action_id: str, product: str) -> dict:
    """Execute a price comparison action."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MARKETPLACE_URL}/api/v3/webmcp/execute/{action_id}",
            json={
                "parameters": {"product": product, "max_results": 5},
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
    """Demo: register → discover tools → find actions → execute comparison."""
    logger.info("=== WebMCP Shopping Agent Demo ===")

    # Step 1: Register
    agent = await register_agent()
    token = agent.get("jwt_token", "")
    if not token:
        logger.error("Failed to get JWT token")
        return

    # Step 2: Discover tools
    tools = await discover_shopping_tools(token)
    for tool in tools:
        logger.info("  Tool: %s (%s) — %s", tool["name"], tool["domain"], tool["category"])

    # Step 3: Find action listings
    actions = await find_action_listings(token)
    if not actions:
        logger.info("No shopping actions available yet. Create one in the marketplace.")
        logger.info("Demo complete (marketplace is empty for shopping actions).")
        return

    # Step 4: Execute price comparison
    action = actions[0]
    logger.info("Executing action: %s ($%s per execution)", action["title"], action["price_per_execution"])
    result = await execute_price_comparison(token, action["id"], "wireless headphones")

    logger.info("Result: %s", json.dumps(result, indent=2))
    logger.info("=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
