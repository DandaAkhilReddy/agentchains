"""Web Search Agent — searches the web, caches results, and sells them on the marketplace."""
import json

try:
    from google.adk.agents import Agent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

from agents.common.marketplace_tools import (
    register_with_marketplace,
    list_data_on_marketplace,
    search_marketplace,
    get_my_reputation,
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
    # In production, this would use SerpAPI, Brave Search API, or ADK's google_search
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


if ADK_AVAILABLE:
    root_agent = Agent(
        name="web_search_seller",
        model="gemini-2.0-flash",
        description="I search the web, cache results, and sell them on the data marketplace.",
        instruction="""You are a web search data seller agent. Your workflow:
1. When asked to search, use the web_search tool to get results
2. Then use search_and_list to cache results and list them on the marketplace
3. Set fair prices based on query complexity ($0.001-$0.01)
4. When asked about your data, use search_marketplace to check what you've listed
5. Report your reputation when asked using get_my_reputation

Always be helpful and transparent about the quality and freshness of your data.""",
        tools=[
            web_search,
            search_and_list,
            register_with_marketplace,
            list_data_on_marketplace,
            search_marketplace,
            get_my_reputation,
        ],
    )
