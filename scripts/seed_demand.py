"""Seed the demand intelligence system with simulated search activity."""
import asyncio
import os
import sys
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from marketplace.database import async_session, init_db
from marketplace.models.search_log import SearchLog
from marketplace.services import demand_service

# Simulated search queries that agents might make
SEARCH_PATTERNS = [
    # High-frequency web search queries (trending)
    ("python async patterns", "web_search", 35),
    ("react server components 2026", "web_search", 28),
    ("kubernetes autoscaling", "web_search", 22),
    ("LLM fine-tuning techniques", "web_search", 40),
    ("rust vs go performance 2026", "web_search", 18),
    ("docker compose best practices", "web_search", 15),

    # Code analysis queries (medium frequency)
    ("fastapi middleware security", "code_analysis", 12),
    ("react useEffect memory leaks", "code_analysis", 20),
    ("python type hints advanced", "code_analysis", 8),
    ("typescript generics patterns", "code_analysis", 10),

    # Document summaries (lower frequency)
    ("attention is all you need summary", "document_summary", 6),
    ("OWASP top 10 2025", "document_summary", 14),
    ("scaling distributed systems paper", "document_summary", 5),

    # Demand gaps (searched but no listings exist)
    ("GraphQL subscriptions real-time", "web_search", 25),
    ("WebAssembly performance benchmarks", "web_search", 19),
    ("AI agent orchestration patterns", "code_analysis", 30),
    ("zero knowledge proofs explained", "document_summary", 16),
    ("rust async runtime comparison", "code_analysis", 11),
    ("vector database benchmarks 2026", "web_search", 22),
    ("microservices observability stack", "web_search", 13),
]


async def seed_demand():
    """Create simulated SearchLog entries spanning the last 24 hours."""
    await init_db()

    async with async_session() as db:
        print("=== Seeding Demand Intelligence ===\n")

        # Get agent IDs for realistic requester_ids
        from sqlalchemy import select
        from marketplace.models.agent import RegisteredAgent
        result = await db.execute(select(RegisteredAgent.id))
        agent_ids = [row[0] for row in result.all()]

        if not agent_ids:
            agent_ids = [None]
            print("  (No agents found, using anonymous searches)\n")

        total_logs = 0
        now = datetime.now(timezone.utc)

        for query, category, count in SEARCH_PATTERNS:
            # Determine if this is a gap (no matching listings)
            is_gap = query in {
                "GraphQL subscriptions real-time",
                "WebAssembly performance benchmarks",
                "AI agent orchestration patterns",
                "zero knowledge proofs explained",
                "rust async runtime comparison",
                "vector database benchmarks 2026",
                "microservices observability stack",
            }

            for i in range(count):
                # Spread searches over the last 24 hours
                hours_ago = random.uniform(0, 24)
                created_at = now - timedelta(hours=hours_ago)

                requester_id = random.choice(agent_ids) if agent_ids[0] else None
                matched_count = 0 if is_gap else random.randint(1, 5)
                led_to_purchase = 0 if is_gap else (1 if random.random() < 0.3 else 0)
                max_price = round(random.uniform(0.001, 0.02), 6)

                log = SearchLog(
                    query_text=query,
                    category=category,
                    source=random.choice(["discover", "auto_match", "discover"]),
                    requester_id=requester_id,
                    matched_count=matched_count,
                    led_to_purchase=led_to_purchase,
                    max_price=max_price,
                    created_at=created_at,
                )
                db.add(log)
                total_logs += 1

            status = "GAP" if is_gap else "OK"
            print(f"  [{status}] {query}: {count} searches")

        await db.commit()
        print(f"\n  Total search logs created: {total_logs}")

        # Run aggregation
        print("\n  Running demand aggregation...")
        signals = await demand_service.aggregate_demand(db)
        print(f"  Demand signals created: {len(signals)}")

        gaps = [s for s in signals if s.is_gap]
        print(f"  Demand gaps detected: {len(gaps)}")

        # Generate opportunities
        print("  Generating opportunities...")
        opps = await demand_service.generate_opportunities(db)
        print(f"  Opportunities created: {len(opps)}")

        # Show top trending
        print("\n  Top trending queries:")
        trending = await demand_service.get_trending(db, limit=5, hours=24)
        for t in trending:
            print(f"    {t.query_pattern} — {float(t.velocity):.1f}/hr (fulfillment: {float(t.fulfillment_rate)*100:.0f}%)")

        # Show top gaps
        print("\n  Top demand gaps:")
        gap_list = await demand_service.get_demand_gaps(db, limit=5)
        for g in gap_list:
            print(f"    {g.query_pattern} — {g.search_count} searches, {g.unique_requesters} requesters")

        # Calculate agent stats
        print("\n  Calculating agent stats...")
        from marketplace.services import analytics_service
        for aid in agent_ids:
            if aid:
                stats = await analytics_service.calculate_agent_stats(db, aid)
                print(f"    Agent {aid[:8]}... — helpfulness: {float(stats.helpfulness_score)*100:.1f}%, earned: ${float(stats.total_earned_usdc):.4f}")

        print("\n=== Demand seed complete ===")


if __name__ == "__main__":
    asyncio.run(seed_demand())
