"""Marketplace database seeder for all 100 registered agents.

Seeds the ``registered_agents`` table from AGENT_DEFINITIONS.  Agents that
already exist (matched by name) are skipped; existing records are not mutated.

Usage::

    python -m agents.registry.seed_marketplace
    python -m agents.registry.seed_marketplace --upsert  # update existing rows
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.registry.agent_definitions import AGENT_DEFINITIONS, AgentDefinition
from marketplace.database import async_session, init_db
from marketplace.models.agent import RegisteredAgent


# ---------------------------------------------------------------------------
# Core seeding logic
# ---------------------------------------------------------------------------


def _agent_to_record(agent: AgentDefinition) -> dict:
    """Convert an AgentDefinition to the column dict for RegisteredAgent.

    Args:
        agent: Source agent definition.

    Returns:
        Dict of column values ready for ``RegisteredAgent(**values)``.
    """
    capabilities_json = json.dumps([s["id"] for s in agent.skills])
    a2a_endpoint = f"http://localhost:{agent.port}"
    # Minimal public key placeholder — real agents supply their own on registration
    stub_public_key = f"stub-{agent.slug}-public-key"
    agent_card = json.dumps({
        "name": agent.name,
        "description": agent.description,
        "url": a2a_endpoint,
        "skills": list(agent.skills),
        "is_stub": agent.is_stub,
        "category": agent.category,
    })

    return {
        "id": str(uuid.uuid4()),
        "name": agent.name,
        "description": agent.description,
        "agent_type": "seller",
        "public_key": stub_public_key,
        "wallet_address": "",
        "capabilities": capabilities_json,
        "a2a_endpoint": a2a_endpoint,
        "agent_card_json": agent_card,
        "creator_id": None,
        "status": "active",
    }


async def seed_all_agents(db: AsyncSession, *, upsert: bool = False) -> dict[str, int]:
    """Seed all agents from AGENT_DEFINITIONS into the registered_agents table.

    Args:
        db: Active async database session.
        upsert: If True, update existing records. If False, skip them.

    Returns:
        Dict with counts: ``{"inserted": N, "skipped": N, "updated": N}``.
    """
    inserted = 0
    skipped = 0
    updated = 0

    for agent_def in AGENT_DEFINITIONS:
        result = await db.execute(
            select(RegisteredAgent).where(RegisteredAgent.name == agent_def.name)
        )
        existing: RegisteredAgent | None = result.scalar_one_or_none()

        if existing is None:
            record_data = _agent_to_record(agent_def)
            db.add(RegisteredAgent(**record_data))
            inserted += 1
        elif upsert:
            # Update mutable fields only — preserve id and creator_id
            existing.description = agent_def.description
            existing.capabilities = json.dumps([s["id"] for s in agent_def.skills])
            existing.a2a_endpoint = f"http://localhost:{agent_def.port}"
            existing.agent_card_json = json.dumps({
                "name": agent_def.name,
                "description": agent_def.description,
                "url": existing.a2a_endpoint,
                "skills": list(agent_def.skills),
                "is_stub": agent_def.is_stub,
                "category": agent_def.category,
            })
            updated += 1
        else:
            skipped += 1

    await db.commit()
    return {"inserted": inserted, "skipped": skipped, "updated": updated}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


async def _run(upsert: bool) -> None:
    """Initialise the database and run the seeder.

    Args:
        upsert: Passed through to ``seed_all_agents``.
    """
    await init_db()

    async with async_session() as db:
        stats = await seed_all_agents(db, upsert=upsert)

    print(
        f"Seed complete — "
        f"inserted: {stats['inserted']}, "
        f"updated: {stats['updated']}, "
        f"skipped: {stats['skipped']}"
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the marketplace seeder.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code (0 for success).
    """
    parser = argparse.ArgumentParser(description="Seed all 100 agents into the marketplace DB.")
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="Update existing agent records instead of skipping them.",
    )
    args = parser.parse_args(argv)

    asyncio.run(_run(upsert=args.upsert))
    return 0


if __name__ == "__main__":
    sys.exit(main())
