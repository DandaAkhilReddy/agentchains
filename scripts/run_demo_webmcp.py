"""One-command WebMCP demo launcher.

Starts the marketplace server (if not running), then runs both
demo agents sequentially to showcase the WebMCP integration.

Usage:
    python scripts/run_demo_webmcp.py
"""

import asyncio
import logging
import subprocess
import sys
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HEALTH_URL = "http://localhost:8000/api/v1/health"


async def check_server() -> bool:
    """Check if the marketplace server is running."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(HEALTH_URL)
            return resp.status_code == 200
    except Exception:
        return False


async def main():
    logger.info("=== AgentChains WebMCP Demo Launcher ===")

    # Check if server is running
    if not await check_server():
        logger.info("Marketplace server not running. Start it with:")
        logger.info("  python scripts/start_local.py")
        logger.info("Then re-run this demo.")
        sys.exit(1)

    logger.info("Marketplace server is healthy.")

    # Run shopping agent demo
    logger.info("\n--- Shopping Agent Demo ---")
    try:
        from agents.demo.webmcp_shopping_agent import main as shopping_main
        await shopping_main()
    except Exception as e:
        logger.error("Shopping agent demo failed: %s", e)

    # Run research agent demo
    logger.info("\n--- Research Agent Demo ---")
    try:
        from agents.demo.webmcp_research_agent import main as research_main
        await research_main()
    except Exception as e:
        logger.error("Research agent demo failed: %s", e)

    logger.info("\n=== All demos complete ===")


if __name__ == "__main__":
    asyncio.run(main())
