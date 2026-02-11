"""MCP tool definitions: 8 tools agents can call via MCP protocol.

Each tool maps to existing service functions — no business logic duplication.
"""

TOOL_DEFINITIONS = [
    {
        "name": "marketplace_discover",
        "description": "Search and discover data listings in the marketplace. Returns listings matching filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Search query"},
                "category": {"type": "string", "description": "Filter by category"},
                "min_quality": {"type": "number", "description": "Minimum quality score (0-1)"},
                "max_price": {"type": "number", "description": "Maximum price in USDC"},
                "page": {"type": "integer", "default": 1},
                "page_size": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "marketplace_express_buy",
        "description": "Purchase a listing instantly. Returns content + transaction details.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "listing_id": {"type": "string", "description": "ID of the listing to buy"},
            },
            "required": ["listing_id"],
        },
    },
    {
        "name": "marketplace_sell",
        "description": "Create a new data listing in the marketplace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "category": {"type": "string"},
                "content": {"type": "string", "description": "The data content to sell"},
                "price_usdc": {"type": "number"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "quality_score": {"type": "number", "default": 0.5},
            },
            "required": ["title", "category", "content", "price_usdc"],
        },
    },
    {
        "name": "marketplace_auto_match",
        "description": "Describe what data you need and find the best match across all sellers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Describe what data you need"},
                "category": {"type": "string"},
                "max_price": {"type": "number"},
                "auto_buy": {"type": "boolean", "default": False},
                "routing_strategy": {"type": "string", "enum": ["cheapest", "fastest", "highest_quality", "best_value", "round_robin", "weighted_random", "locality"]},
            },
            "required": ["description"],
        },
    },
    {
        "name": "marketplace_register_catalog",
        "description": "Register a capability in the data catalog. Declare what type of data you can produce.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Capability namespace, e.g. 'web_search.python'"},
                "topic": {"type": "string"},
                "description": {"type": "string"},
                "price_range_min": {"type": "number", "default": 0.001},
                "price_range_max": {"type": "number", "default": 0.01},
            },
            "required": ["namespace", "topic"],
        },
    },
    {
        "name": "marketplace_trending",
        "description": "Get trending demand signals and market opportunities.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "marketplace_reputation",
        "description": "Check an agent's reputation and helpfulness scores.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent ID to check"},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "marketplace_verify_zkp",
        "description": "Verify listing claims before purchasing using zero-knowledge proofs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "listing_id": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}, "description": "Check if these keywords are in the content"},
                "schema_has_fields": {"type": "array", "items": {"type": "string"}, "description": "Check if content has these JSON fields"},
                "min_size": {"type": "integer", "description": "Minimum content size in bytes"},
                "min_quality": {"type": "number", "description": "Minimum quality score"},
            },
            "required": ["listing_id"],
        },
    },
]


async def execute_tool(tool_name: str, arguments: dict, agent_id: str) -> dict:
    """Execute an MCP tool by calling the corresponding service function."""
    from marketplace.database import async_session

    async with async_session() as db:
        if tool_name == "marketplace_discover":
            from marketplace.services.listing_service import discover
            listings, total = await discover(
                db, q=arguments.get("q"), category=arguments.get("category"),
                min_quality=arguments.get("min_quality"), max_price=arguments.get("max_price"),
                page=arguments.get("page", 1), page_size=arguments.get("page_size", 20),
            )
            return {
                "listings": [
                    {"id": l.id, "title": l.title, "category": l.category,
                     "price_usdc": float(l.price_usdc), "quality_score": float(l.quality_score) if l.quality_score else 0.5}
                    for l in listings
                ],
                "total": total,
            }

        elif tool_name == "marketplace_express_buy":
            from marketplace.services.express_service import express_buy
            response = await express_buy(db, arguments["listing_id"], agent_id)
            import json
            return json.loads(response.body.decode("utf-8"))

        elif tool_name == "marketplace_sell":
            from marketplace.services.listing_service import create_listing
            from marketplace.schemas.listing import ListingCreateRequest
            req = ListingCreateRequest(
                title=arguments["title"],
                description=arguments.get("description", ""),
                category=arguments["category"],
                content=arguments["content"],
                price_usdc=arguments["price_usdc"],
                tags=arguments.get("tags", []),
                quality_score=arguments.get("quality_score", 0.5),
            )
            listing = await create_listing(db, agent_id, req)
            return {"listing_id": listing.id, "title": listing.title, "content_hash": listing.content_hash}

        elif tool_name == "marketplace_auto_match":
            from marketplace.services.match_service import auto_match
            return await auto_match(
                db, arguments["description"],
                category=arguments.get("category"),
                max_price=arguments.get("max_price"),
                buyer_id=agent_id,
                routing_strategy=arguments.get("routing_strategy"),
            )

        elif tool_name == "marketplace_register_catalog":
            from marketplace.services.catalog_service import register_catalog_entry
            entry = await register_catalog_entry(
                db, agent_id, arguments["namespace"], arguments["topic"],
                arguments.get("description", ""),
                price_range_min=arguments.get("price_range_min", 0.001),
                price_range_max=arguments.get("price_range_max", 0.01),
            )
            return {"entry_id": entry.id, "namespace": entry.namespace, "topic": entry.topic}

        elif tool_name == "marketplace_trending":
            from marketplace.services.demand_service import get_trending
            signals = await get_trending(db, category=arguments.get("category"), limit=arguments.get("limit", 10))
            return {"signals": signals}

        elif tool_name == "marketplace_reputation":
            from sqlalchemy import select
            from marketplace.models.agent_stats import AgentStats
            result = await db.execute(
                select(AgentStats).where(AgentStats.agent_id == arguments["agent_id"])
            )
            stats = result.scalar_one_or_none()
            if not stats:
                return {"error": "Agent not found", "agent_id": arguments["agent_id"]}
            return {
                "agent_id": arguments["agent_id"],
                "helpfulness_score": float(stats.helpfulness_score),
                "total_earned_usdc": float(stats.total_earned_usdc),
                "unique_buyers_served": stats.unique_buyers_served,
                "primary_specialization": stats.primary_specialization,
            }

        elif tool_name == "marketplace_verify_zkp":
            from marketplace.services.zkp_service import verify_listing
            return await verify_listing(
                db, arguments["listing_id"],
                keywords=arguments.get("keywords"),
                schema_has_fields=arguments.get("schema_has_fields"),
                min_size=arguments.get("min_size"),
                min_quality=arguments.get("min_quality"),
            )

        return {"error": f"Unknown tool: {tool_name}"}
