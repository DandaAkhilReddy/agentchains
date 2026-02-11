"""Web Search Agent — searches the web, caches results, and sells them on the marketplace."""
import json

from agents.common.marketplace_tools import (
    register_with_marketplace,
    list_data_on_marketplace,
    search_marketplace,
    get_my_reputation,
    get_trending_queries,
    get_demand_gaps,
    get_opportunities,
    get_my_earnings,
    get_my_stats,
    register_catalog_entry,
    suggest_price,
    get_demand_for_me,
)


def web_search(query: str, num_results: int = 10) -> str:
    """Execute a web search and return structured results.

    Args:
        query: The search query to execute
        num_results: Number of results to return (default 10)

    Returns:
        JSON string with search results including titles, URLs, and snippets
    """
    # Simulated search results for demo
    # In production, this would use SerpAPI, Brave Search API, or similar
    results = []
    for i in range(min(num_results, 5)):
        results.append({
            "position": i + 1,
            "title": f"Result {i+1} for: {query}",
            "url": f"https://example.com/result-{i+1}",
            "snippet": f"This is a comprehensive resource about {query}. "
                       f"It covers key concepts, best practices, and real-world examples.",
        })

    return json.dumps({
        "query": query,
        "total_results": len(results),
        "results": results,
        "source": "simulated_search",
    }, indent=2)


def search_and_list(query: str, price_usdc: float = 0.002) -> str:
    """Search the web for a query and list the results on the marketplace for sale.

    Args:
        query: The search query
        price_usdc: Price to list at in USDC (default $0.002)

    Returns:
        Listing confirmation with listing_id and content_hash
    """
    # Execute search
    results = web_search(query)

    # List on marketplace
    listing = list_data_on_marketplace(
        title=f"Web search: '{query}' - Top results",
        description=f"Cached web search results for query: {query}",
        category="web_search",
        content=results,
        price_usdc=price_usdc,
        metadata={"query": query, "source": "web_search", "result_count": 5},
        tags=query.lower().split() + ["search", "web"],
        quality_score=0.85,
    )
    return json.dumps(listing, indent=2, default=str)


# --- Azure OpenAI Agent ---
try:
    from agents.common.azure_agent import AzureAgent

    root_agent = AzureAgent(
        name="web_search_seller",
        description="I search the web, cache results, and sell them on the data marketplace.",
        instruction="""You are a web search data seller agent. Your workflow:

SETUP (do this first when joining the marketplace):
1. Call register_with_marketplace() to register and get your JWT token
2. Call register_catalog_entry(namespace="web_search", topic="general") to declare your capabilities
3. Call suggest_price(category="web_search") to get optimal pricing for your data

PROACTIVE workflow (maximize earnings):
1. Call get_demand_for_me() to see what buyers specifically need from you
2. Call get_trending_queries() to see what buyers want right now
3. Call get_demand_gaps() to find unmet needs in web_search category
4. Call get_opportunities() to find high-urgency revenue opportunities
5. For each opportunity, search the web, produce data, and list it

SELLING workflow:
1. Use web_search to get results for a query
2. Call suggest_price(category="web_search") to get the optimal price
3. Use search_and_list to cache results and list them on the marketplace
4. When asked about your data, use search_marketplace to check listings

MONITORING:
- Monitor earnings with get_my_earnings() and helpfulness with get_my_stats()
- Check reputation with get_my_reputation()

Always be helpful and transparent about the quality and freshness of your data.""",
        tools=[
            web_search,
            search_and_list,
            register_with_marketplace,
            list_data_on_marketplace,
            search_marketplace,
            get_my_reputation,
            get_trending_queries,
            get_demand_gaps,
            get_opportunities,
            get_my_earnings,
            get_my_stats,
            register_catalog_entry,
            suggest_price,
            get_demand_for_me,
        ],
    )
except ImportError:
    root_agent = None
