"""Buyer Agent — discovers and purchases data from the marketplace on behalf of users."""
import json

try:
    from google.adk.agents import Agent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

from agents.common.marketplace_tools import (
    register_with_marketplace,
    search_marketplace,
    purchase_data,
    verify_delivered_content,
    get_my_reputation,
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

Your workflow:
1. When a user asks for information, FIRST search the marketplace using search_marketplace
2. Compare listings by price, freshness, quality score, and seller reputation
3. If a good match exists at a lower cost than fresh computation, use find_and_buy to purchase it
4. After purchase, verify the content hash before accepting
5. Always report the cost savings compared to fresh computation
6. If no good match exists, use browse_marketplace to show what's available
7. Check your reputation periodically with get_my_reputation

Remember:
- Fresh web search costs ~$0.01
- Fresh code analysis costs ~$0.02
- Fresh document summary costs ~$0.01
- Cached results are typically 30-60% cheaper""",
        tools=[
            find_and_buy,
            browse_marketplace,
            register_with_marketplace,
            search_marketplace,
            purchase_data,
            verify_delivered_content,
            get_my_reputation,
        ],
    )
