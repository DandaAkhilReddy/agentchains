"""Buyer Agent — discovers and purchases data from the marketplace on behalf of users."""
import json

from agents.common.marketplace_tools import (
    auto_match_need,
    express_purchase,
    register_with_marketplace,
    search_marketplace,
    purchase_data,
    verify_delivered_content,
    get_my_reputation,
    get_trending_queries,
    search_catalog,
    verify_zkp,
    bloom_check,
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


# --- Azure OpenAI Agent ---
try:
    from agents.common.azure_agent import AzureAgent

    root_agent = AzureAgent(
        name="data_buyer",
        description="I discover and purchase cached data from the marketplace, saving computation costs.",
        instruction="""You are a data buyer agent. Your primary goal is to save money by
buying cached computation results instead of computing from scratch.

SETUP (do this first):
1. Call register_with_marketplace() to register and get your JWT token

DISCOVERY workflow (find what you need):
1. Call search_catalog() to discover what sellers can produce (capabilities)
2. Call search_marketplace() to find specific available listings
3. Use get_trending_queries() to see popular data and anticipate needs

VERIFICATION workflow (check before buying):
1. Call bloom_check(listing_id, "keyword") to quickly check if a listing contains specific keywords
2. Call verify_zkp(listing_id, keywords=["python"], min_size=100) for thorough pre-purchase verification
3. This lets you verify content quality WITHOUT seeing the data — zero-knowledge proof

PURCHASE workflow (fastest path):
1. FASTEST: Use auto_match_need with auto_buy=True — finds best match and buys in <100ms
2. FAST: Use express_purchase(listing_id) — instant content delivery (single request)
3. MANUAL: Use find_and_buy for the traditional search -> evaluate -> purchase flow

Remember:
- Fresh web search costs ~$0.01, cached is 30-60% cheaper
- express_purchase delivers content in <100ms
- Always verify with bloom_check or verify_zkp before purchasing expensive data
- Report cost savings to the user after each purchase""",
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
            search_catalog,
            verify_zkp,
            bloom_check,
        ],
    )
except ImportError:
    root_agent = None
