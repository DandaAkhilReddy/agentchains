"""MCP resource definitions: 5 read-only data resources agents can access."""

RESOURCE_DEFINITIONS = [
    {
        "uri": "marketplace://catalog",
        "name": "Data Catalog",
        "description": "Browse all registered agent capabilities and data offerings.",
        "mimeType": "application/json",
    },
    {
        "uri": "marketplace://listings/active",
        "name": "Active Listings",
        "description": "All currently active data listings in the marketplace.",
        "mimeType": "application/json",
    },
    {
        "uri": "marketplace://trending",
        "name": "Trending Demand",
        "description": "Current trending demand signals and market opportunities.",
        "mimeType": "application/json",
    },
    {
        "uri": "marketplace://opportunities",
        "name": "Opportunities",
        "description": "High-urgency supply gaps and revenue opportunities.",
        "mimeType": "application/json",
    },
    {
        "uri": "marketplace://agent/{agent_id}",
        "name": "Agent Profile",
        "description": "Detailed profile, stats, and reputation for a specific agent.",
        "mimeType": "application/json",
    },
]


async def read_resource(uri: str, agent_id: str) -> dict:
    """Read an MCP resource by URI."""
    import json
    from marketplace.database import async_session

    async with async_session() as db:
        if uri == "marketplace://catalog":
            from marketplace.services.catalog_service import search_catalog
            entries, total = await search_catalog(db, page_size=100)
            return {
                "entries": [
                    {"id": e.id, "namespace": e.namespace, "topic": e.topic,
                     "agent_id": e.agent_id, "quality_avg": float(e.quality_avg) if e.quality_avg else 0.5,
                     "active_listings": e.active_listings_count}
                    for e in entries
                ],
                "total": total,
            }

        elif uri == "marketplace://listings/active":
            from marketplace.services.listing_service import list_listings
            listings, total = await list_listings(db, page_size=50)
            return {
                "listings": [
                    {"id": l.id, "title": l.title, "category": l.category,
                     "price_usdc": float(l.price_usdc), "quality_score": float(l.quality_score) if l.quality_score else 0.5,
                     "seller_id": l.seller_id}
                    for l in listings
                ],
                "total": total,
            }

        elif uri == "marketplace://trending":
            from marketplace.services.demand_service import get_trending
            signals = await get_trending(db, limit=20)
            return {"signals": signals}

        elif uri == "marketplace://opportunities":
            from sqlalchemy import select
            from marketplace.models.opportunity import OpportunitySignal
            result = await db.execute(
                select(OpportunitySignal)
                .where(OpportunitySignal.status == "active")
                .order_by(OpportunitySignal.urgency_score.desc())
                .limit(20)
            )
            opps = list(result.scalars().all())
            return {
                "opportunities": [
                    {"id": o.id, "query_pattern": o.query_pattern,
                     "estimated_revenue_usdc": float(o.estimated_revenue_usdc),
                     "urgency_score": float(o.urgency_score)}
                    for o in opps
                ],
            }

        elif uri.startswith("marketplace://agent/"):
            target_id = uri.split("/")[-1]
            from sqlalchemy import select
            from marketplace.models.agent_stats import AgentStats
            from marketplace.models.agent import RegisteredAgent
            result = await db.execute(
                select(RegisteredAgent).where(RegisteredAgent.id == target_id)
            )
            agent = result.scalar_one_or_none()
            if not agent:
                return {"error": "Agent not found"}

            stats_result = await db.execute(
                select(AgentStats).where(AgentStats.agent_id == target_id)
            )
            stats = stats_result.scalar_one_or_none()
            return {
                "id": agent.id,
                "name": agent.name,
                "agent_type": agent.agent_type,
                "status": agent.status,
                "stats": {
                    "helpfulness_score": float(stats.helpfulness_score) if stats else 0,
                    "total_earned_usdc": float(stats.total_earned_usdc) if stats else 0,
                    "unique_buyers_served": stats.unique_buyers_served if stats else 0,
                    "primary_specialization": stats.primary_specialization if stats else None,
                } if stats else None,
            }

    return {"error": f"Unknown resource: {uri}"}
