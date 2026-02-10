"""Knowledge Broker Agent — a market-maker that coordinates supply and demand.

This agent produces no data itself. Instead it monitors demand signals,
identifies gaps, and orchestrates other agents to fill them.  It demonstrates
*emergent specialization*: an intermediary role arising from simple marketplace
rules rather than being hard-coded.
"""
import json

try:
    from google.adk.agents import Agent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

from agents.common.marketplace_tools import (
    register_with_marketplace,
    search_marketplace,
    get_my_reputation,
    get_trending_queries,
    get_demand_gaps,
    get_opportunities,
    get_my_earnings,
    get_my_stats,
)


def analyze_market(category: str | None = None) -> str:
    """Provide a full market analysis combining trending, gaps, and opportunities.

    Args:
        category: Optional category filter (web_search, code_analysis, document_summary)

    Returns:
        JSON market report with trends, gaps, and recommendations
    """
    trending_raw = get_trending_queries(limit=10, hours=6)
    gaps_raw = get_demand_gaps(limit=10, category=category)
    opps_raw = get_opportunities(limit=10, category=category)

    try:
        trending = json.loads(trending_raw) if isinstance(trending_raw, str) else trending_raw
        gaps = json.loads(gaps_raw) if isinstance(gaps_raw, str) else gaps_raw
        opps = json.loads(opps_raw) if isinstance(opps_raw, str) else opps_raw
    except (json.JSONDecodeError, TypeError):
        trending, gaps, opps = {}, {}, {}

    report = {
        "market_report": {
            "trending_count": len(trending.get("queries", [])),
            "gap_count": len(gaps.get("gaps", [])),
            "opportunity_count": len(opps.get("opportunities", [])),
            "trending_queries": trending.get("queries", [])[:5],
            "top_gaps": gaps.get("gaps", [])[:5],
            "top_opportunities": opps.get("opportunities", [])[:5],
        },
        "recommendations": [],
    }

    # Generate recommendations from gaps
    for gap in gaps.get("gaps", [])[:5]:
        report["recommendations"].append({
            "action": "fill_gap",
            "query": gap.get("query_pattern", ""),
            "category": gap.get("category", ""),
            "search_count": gap.get("search_count", 0),
            "avg_budget": gap.get("avg_max_price", 0),
            "rationale": f"'{gap.get('query_pattern', '')}' has {gap.get('search_count', 0)} searches with 0% fulfillment",
        })

    return json.dumps(report, indent=2, default=str)


def match_supply_to_demand(query: str, max_price: float = 0.01) -> str:
    """Check if existing marketplace supply can fill a demand query.

    Args:
        query: The demand query to check
        max_price: Maximum price to consider

    Returns:
        JSON with matching listings or a gap advisory
    """
    results_raw = search_marketplace(query=query, category=None, max_price=max_price)
    try:
        results = json.loads(results_raw) if isinstance(results_raw, str) else results_raw
    except (json.JSONDecodeError, TypeError):
        results = {"listings": []}

    listings = results.get("listings", [])
    if listings:
        return json.dumps({
            "status": "supply_available",
            "query": query,
            "matching_listings": len(listings),
            "best_match": listings[0] if listings else None,
            "recommendation": "Direct buyers to existing supply",
        }, indent=2, default=str)
    else:
        return json.dumps({
            "status": "gap_detected",
            "query": query,
            "matching_listings": 0,
            "recommendation": "Signal seller agents to produce data for this query",
        }, indent=2, default=str)


if ADK_AVAILABLE:
    root_agent = Agent(
        name="knowledge_broker",
        model="gemini-2.0-flash",
        description="I am a market-maker agent that coordinates supply and demand without producing data myself.",
        instruction="""You are the Knowledge Broker — a market-making agent for the data marketplace.
You do NOT produce data yourself. Your role is to:

1. MONITOR: Continuously check trending queries and demand gaps
   - Call analyze_market() for a full market overview
   - Call get_trending_queries() for real-time hot topics
   - Call get_demand_gaps() to find unmet needs

2. COORDINATE: Match existing supply to demand
   - Call match_supply_to_demand(query) to check if a gap can be filled
   - Call search_marketplace(query) to find relevant existing listings

3. ADVISE: Provide market intelligence to other agents
   - When asked, report which queries have the highest demand
   - Recommend categories where new agents would be most valuable
   - Identify arbitrage opportunities (low price vs high demand)

4. TRACK: Monitor your own impact on the ecosystem
   - Call get_my_earnings() and get_my_stats() to track your contribution
   - Call get_my_reputation() to check standing

Your value comes from INFORMATION, not production. You are the transparent
order book of the knowledge economy.  You succeed when the marketplace
has fewer gaps and buyers find what they need faster.""",
        tools=[
            analyze_market,
            match_supply_to_demand,
            register_with_marketplace,
            search_marketplace,
            get_my_reputation,
            get_trending_queries,
            get_demand_gaps,
            get_opportunities,
            get_my_earnings,
            get_my_stats,
        ],
    )
