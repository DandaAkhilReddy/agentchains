"""Buyer Agent — discovers and purchases data from the marketplace on behalf of users."""
import json

try:
    from google.adk.agents import Agent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

from agents.common.marketplace_tools import (
    auto_match_need,
    express_purchase,
    register_with_marketplace,
    search_marketplace,
    purchase_data,
    verify_delivered_content,
    get_my_reputation,
    get_trending_queries,
)


def find_and_buy(
    query: str,
    category: str | None = None,
    max_price: float = 0.05,
) -> str:
    """Search the marketplace for data matching a query and purchase the best match.

    This is the primary buyer workflow: search -> evaluate -> purchase -> verify.

    Args:
        query: What data you're looking for
        category: Optional filter: web_search, code_analysis, document_summary, etc.
        max_price: Maximum price willing to pay in USDC (default $0.05)

    Returns:
        JSON string with search results and purchase outcome
    """
    # Step 1: Search
    results = search_marketplace(query, category=category, max_price=max_price)

    if not results.get("results"):
        return json.dumps({
            "status": "no_results",
            "query": query,
            "message": f"No listings found matching '{query}' under ${max_price}",
        }, indent=2)

    # Step 2: Pick the best listing (highest quality, freshest, cheapest)
    listings = results["results"]
    best = listings[0]  # Already sorted by the marketplace

    # Step 3: Purchase
    purchase_result = purchase_data(best["id"])

    return json.dumps({
        "status": "purchased" if "transaction_id" in purchase_result else "failed",
        "query": query,
        "listing": {
            "id": best["id"],
            "title": best["title"],
            "price_usdc": best["price_usdc"],
            "quality_score": best.get("quality_score"),
            "seller": best.get("seller", {}).get("name", "unknown"),
        },
        "transaction": purchase_result,
        "savings_estimate": f"Saved ~${max(0, 0.01 - best['price_usdc']):.4f} vs fresh computation",
    }, indent=2, default=str)


def browse_marketplace(category: str | None = None, sort_by: str = "freshness") -> str:
    """Browse available listings on the marketplace.

    Args:
        category: Optional filter by category
        sort_by: How to sort: freshness, price_asc, price_desc, quality

    Returns:
        JSON with available listings
    """
    results = search_marketplace("", category=category, sort_by=sort_by)
    return json.dumps(results, indent=2, default=str)


if ADK_AVAILABLE:
    root_agent = Agent(
        name="data_buyer",
        model="gemini-2.0-flash",
        description="I discover and purchase cached data from the marketplace, saving computation costs.",
        instruction="""You are a data buyer agent. Your primary goal is to save money by
buying cached computation results instead of computing from scratch.

PREFERRED workflow (fastest, use auto_match_need):
1. When a user asks for information, use auto_match_need with auto_buy=True
2. The marketplace automatically finds the best match and purchases it in <100ms
3. Report the savings and delivery time to the user

Alternative workflow (manual):
1. Search the marketplace using search_marketplace
2. Compare listings by price, freshness, quality score, and seller reputation
3. Use express_purchase for instant content delivery (single request)
4. Or use find_and_buy for the traditional multi-step flow
5. Always report the cost savings compared to fresh computation

Smart purchasing with trending data:
- Use get_trending_queries() to see what other buyers are searching for right now
- If trending queries align with your needs, act quickly — popular data may be
  available at lower prices from multiple sellers competing for those queries
- Trending data also helps you anticipate upcoming needs and pre-purchase data
  before demand drives prices up

Remember:
- Fresh web search costs ~$0.01
- Fresh code analysis costs ~$0.02
- Fresh document summary costs ~$0.01
- Cached results are typically 30-60% cheaper
- express_purchase delivers content in <100ms (vs ~500ms for traditional flow)
- auto_match_need with auto_buy=True is the fastest end-to-end path""",
        tools=[
            auto_match_need,
            express_purchase,
            find_and_buy,
            browse_marketplace,
            register_with_marketplace,
            search_marketplace,
            purchase_data,
            verify_delivered_content,
            get_my_reputation,
            get_trending_queries,
        ],
    )
