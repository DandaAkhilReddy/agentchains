"""Register the AgentChains Test Fleet — 20 test writers + 3 judges + 1 final arbiter.

Calls the real API to create a creator account and onboard 24 agents.
Agent JWT tokens are saved to `data/fleet_tokens.json` for later use.

Usage:
    python scripts/register_agent_fleet.py --base-url http://localhost:8000
    python scripts/register_agent_fleet.py --base-url https://agentchains-marketplace.orangemeadow-3bb536df.eastus.azurecontainerapps.io
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

TEST_WRITERS: list[dict[str, str | list[str]]] = [
    {"name": "pytest-unit-writer", "description": "Python unit test specialist using pytest", "capabilities": ["test", "python", "pytest", "unit"]},
    {"name": "pytest-edge-case-writer", "description": "Python edge case and boundary test specialist", "capabilities": ["test", "python", "edge-case", "boundary"]},
    {"name": "pytest-integration-writer", "description": "Python integration and API test specialist", "capabilities": ["test", "python", "integration", "api"]},
    {"name": "pytest-async-writer", "description": "Python async/asyncio test specialist", "capabilities": ["test", "python", "async", "asyncio"]},
    {"name": "jest-unit-writer", "description": "TypeScript/Jest unit test specialist", "capabilities": ["test", "typescript", "jest", "unit"]},
    {"name": "vitest-react-writer", "description": "React component test specialist using Vitest", "capabilities": ["test", "react", "vitest", "component"]},
    {"name": "vitest-hook-writer", "description": "React hook test specialist using Vitest", "capabilities": ["test", "react", "hooks", "vitest"]},
    {"name": "api-contract-tester", "description": "API contract and schema validation test specialist", "capabilities": ["test", "api", "contract", "schema"]},
    {"name": "security-scanner-agent", "description": "Security test writer covering OWASP vulnerabilities", "capabilities": ["test", "security", "owasp", "vulnerability"]},
    {"name": "performance-test-writer", "description": "Load testing and performance benchmark specialist", "capabilities": ["test", "performance", "load", "benchmark"]},
    {"name": "mutation-test-writer", "description": "Mutation testing and coverage quality specialist", "capabilities": ["test", "mutation", "coverage", "quality"]},
    {"name": "database-test-writer", "description": "Database, SQL, and migration test specialist", "capabilities": ["test", "database", "sql", "migration"]},
    {"name": "e2e-playwright-writer", "description": "End-to-end browser test specialist using Playwright", "capabilities": ["test", "e2e", "playwright", "browser"]},
    {"name": "snapshot-test-writer", "description": "Snapshot and golden file regression test specialist", "capabilities": ["test", "snapshot", "regression", "golden"]},
    {"name": "error-path-tester", "description": "Error handling and exception path test specialist", "capabilities": ["test", "error", "exception", "failure"]},
    {"name": "concurrency-test-writer", "description": "Race condition and thread safety test specialist", "capabilities": ["test", "concurrency", "race-condition", "thread"]},
    {"name": "mock-factory-agent", "description": "Mock, fixture, and factory generation specialist", "capabilities": ["test", "mock", "fixture", "factory"]},
    {"name": "property-test-writer", "description": "Property-based testing specialist using Hypothesis", "capabilities": ["test", "property", "hypothesis", "fuzzing"]},
    {"name": "accessibility-test-writer", "description": "Accessibility and WCAG compliance test specialist", "capabilities": ["test", "accessibility", "a11y", "wcag"]},
    {"name": "go-test-writer", "description": "Go table-driven test specialist", "capabilities": ["test", "go", "golang", "table-driven"]},
]

JUDGES: list[dict[str, str | list[str]]] = [
    {"name": "judge-correctness", "description": "Reviews test correctness, assertions, and coverage completeness", "capabilities": ["judge", "review", "correctness", "coverage"]},
    {"name": "judge-security", "description": "Reviews tests for security gaps and OWASP compliance", "capabilities": ["judge", "review", "security", "compliance"]},
    {"name": "judge-quality", "description": "Reviews test code quality, patterns, and maintainability", "capabilities": ["judge", "review", "quality", "patterns"]},
    {"name": "final-arbiter", "description": "Final verdict agent — approves or requests changes to test suites", "capabilities": ["judge", "arbiter", "final-review", "decision"]},
]

ALL_AGENTS = TEST_WRITERS + JUDGES

FLEET_CREATOR_EMAIL = "fleet@agentchains.io"
FLEET_CREATOR_PASSWORD = "FleetAdmin2024!"
FLEET_CREATOR_NAME = "AgentChains Test Fleet"


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def register_creator(client: httpx.Client, base_url: str) -> tuple[str, str]:
    """Register or login as the fleet creator. Returns (creator_id, token)."""
    # Try login first (idempotent)
    resp = client.post(
        f"{base_url}/api/v1/creators/login",
        json={"email": FLEET_CREATOR_EMAIL, "password": FLEET_CREATOR_PASSWORD},
    )
    if resp.status_code == 200:
        data = resp.json()
        logger.info("Logged in as existing fleet creator: %s", data["creator"]["id"])
        return data["creator"]["id"], data["token"]

    # Register
    resp = client.post(
        f"{base_url}/api/v1/creators/register",
        json={
            "email": FLEET_CREATOR_EMAIL,
            "password": FLEET_CREATOR_PASSWORD,
            "display_name": FLEET_CREATOR_NAME,
            "country": "US",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    logger.info("Registered fleet creator: %s", data["creator"]["id"])
    return data["creator"]["id"], data["token"]


def onboard_agent(
    client: httpx.Client,
    base_url: str,
    creator_token: str,
    agent_def: dict[str, str | list[str]],
) -> dict[str, str]:
    """Onboard a single agent. Returns {agent_id, agent_jwt_token, name}."""
    public_key = str(uuid.uuid4())  # Placeholder key for fleet agents
    resp = client.post(
        f"{base_url}/api/v2/agents/onboard",
        headers={"Authorization": f"Bearer {creator_token}"},
        json={
            "name": agent_def["name"],
            "description": agent_def["description"],
            "agent_type": "both",
            "public_key": public_key,
            "capabilities": agent_def["capabilities"],
        },
    )
    if resp.status_code == 409:
        logger.warning("Agent '%s' already exists, skipping", agent_def["name"])
        return {"agent_id": "", "agent_jwt_token": "", "name": str(agent_def["name"]), "skipped": "true"}

    resp.raise_for_status()
    data = resp.json()
    return {
        "agent_id": data["agent_id"],
        "agent_jwt_token": data["agent_jwt_token"],
        "name": str(agent_def["name"]),
    }


def register_catalog_entry(
    client: httpx.Client,
    base_url: str,
    agent_token: str,
    agent_def: dict[str, str | list[str]],
) -> None:
    """Register a catalog entry for the agent's primary capability."""
    caps = agent_def.get("capabilities", [])
    if not caps or not isinstance(caps, list):
        return

    primary = str(caps[0])
    topic = str(caps[1]) if len(caps) > 1 else primary

    resp = client.post(
        f"{base_url}/api/v1/catalog",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={
            "namespace": primary,
            "topic": topic,
            "description": str(agent_def.get("description", "")),
            "price_range_min": 0.0,
            "price_range_max": 0.0,
        },
    )
    if resp.status_code in (200, 201):
        logger.info("  Catalog entry registered for %s/%s", primary, topic)
    else:
        logger.warning("  Catalog registration failed (%d): %s", resp.status_code, resp.text[:200])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Register the AgentChains Test Fleet")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the marketplace API",
    )
    parser.add_argument(
        "--output",
        default="data/fleet_tokens.json",
        help="Output file for agent tokens",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = httpx.Client(timeout=30.0)

    # 1. Register / login creator
    logger.info("Registering fleet creator at %s", base_url)
    creator_id, creator_token = register_creator(client, base_url)

    # 2. Onboard all agents
    results: list[dict[str, str]] = []
    for agent_def in ALL_AGENTS:
        logger.info("Onboarding agent: %s", agent_def["name"])
        result = onboard_agent(client, base_url, creator_token, agent_def)
        results.append(result)

        # 3. Register catalog entry (skip if agent was already registered)
        if result.get("agent_jwt_token"):
            register_catalog_entry(client, base_url, result["agent_jwt_token"], agent_def)

    # 4. Save tokens
    fleet_data = {
        "creator_id": creator_id,
        "creator_token": creator_token,
        "agents": results,
    }
    output_path.write_text(json.dumps(fleet_data, indent=2))
    logger.info("Fleet tokens saved to %s", output_path)

    # Summary
    registered = [r for r in results if r.get("agent_jwt_token")]
    skipped = [r for r in results if r.get("skipped")]
    logger.info("Done: %d registered, %d skipped", len(registered), len(skipped))

    if not registered and not skipped:
        logger.error("No agents were registered")
        sys.exit(1)


if __name__ == "__main__":
    main()
