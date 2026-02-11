"""Shared tool functions that ADK agents use to interact with the marketplace API."""
import os

import httpx

MARKETPLACE_URL = os.getenv("MARKETPLACE_URL", "http://localhost:8000/api/v1")

# Agent state (populated after registration)
_agent_state: dict = {}


def _headers() -> dict:
    token = _agent_state.get("jwt_token", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def register_with_marketplace(
    name: str,
    description: str,
    agent_type: str,
    capabilities: list[str],
    public_key: str = "placeholder-public-key",
    wallet_address: str = "",
    a2a_endpoint: str = "",
) -> dict:
    """Register this agent with the data marketplace.

    Args:
        name: Unique agent name
        description: What this agent does
        agent_type: 'seller', 'buyer', or 'both'
        capabilities: List of capability tags
        public_key: RSA public key for JWT auth
        wallet_address: Ethereum address for x402 payments
        a2a_endpoint: URL where A2A server runs

    Returns:
        Dict with id, name, jwt_token, agent_card_url, created_at
    """
    response = httpx.post(
        f"{MARKETPLACE_URL}/agents/register",
        json={
            "name": name,
            "description": description,
            "agent_type": agent_type,
            "capabilities": capabilities,
            "public_key": public_key,
            "wallet_address": wallet_address,
            "a2a_endpoint": a2a_endpoint,
        },
        timeout=30,
    )
    data = response.json()
    if response.status_code == 201:
        _agent_state["agent_id"] = data["id"]
        _agent_state["jwt_token"] = data["jwt_token"]
        _agent_state["name"] = data["name"]
    return data


def list_data_on_marketplace(
    title: str,
    description: str,
    category: str,
    content: str,
    price_usdc: float,
    metadata: dict | None = None,
    tags: list[str] | None = None,
    quality_score: float = 0.8,
) -> dict:
    """List computed data for sale on the marketplace.

    Args:
        title: Short title for the data listing
        description: Detailed description of what the data contains
        category: One of: web_search, code_analysis, document_summary, api_response, computation
        content: The actual data content as a string (JSON or text)
        price_usdc: Price in USDC (e.g., 0.001 for a tenth of a cent)
        metadata: Optional metadata dict (source, query, model used, etc.)
        tags: Optional list of searchable tags
        quality_score: Self-assessed quality from 0.0 to 1.0

    Returns:
        Dict with listing id, content_hash, and other listing details
    """
    response = httpx.post(
        f"{MARKETPLACE_URL}/listings",
        json={
            "title": title,
            "description": description,
            "category": category,
            "content": content,
            "price_usdc": price_usdc,
            "metadata": metadata or {},
            "tags": tags or [],
            "quality_score": quality_score,
        },
        headers=_headers(),
        timeout=30,
    )
    return response.json()


def search_marketplace(
    query: str,
    category: str | None = None,
    max_price: float | None = None,
    max_age_hours: int | None = None,
    sort_by: str = "freshness",
) -> dict:
    """Search the marketplace for data listings matching your query.

    Args:
        query: Search text to match against listing titles, descriptions, and tags
        category: Filter by category (web_search, code_analysis, document_summary, etc.)
        max_price: Maximum price in USDC
        max_age_hours: Maximum age of data in hours
        sort_by: Sort order: freshness, price_asc, price_desc, quality

    Returns:
        Dict with total count and list of matching listings
    """
    params: dict = {"q": query, "sort_by": sort_by}
    if category:
        params["category"] = category
    if max_price is not None:
        params["max_price"] = max_price
    if max_age_hours is not None:
        params["max_age_hours"] = max_age_hours

    response = httpx.get(
        f"{MARKETPLACE_URL}/discover",
        params=params,
        timeout=30,
    )
    return response.json()


def purchase_data(listing_id: str) -> dict:
    """Purchase a data listing from the marketplace.

    This initiates the transaction, auto-confirms payment (in simulated mode),
    and returns the transaction details.

    Args:
        listing_id: The ID of the listing to purchase

    Returns:
        Dict with transaction_id, status, amount_usdc, payment_details, content_hash
    """
    # Step 1: Initiate
    init_resp = httpx.post(
        f"{MARKETPLACE_URL}/transactions/initiate",
        json={"listing_id": listing_id},
        headers=_headers(),
        timeout=30,
    )
    init_data = init_resp.json()

    if init_resp.status_code != 201:
        return init_data

    tx_id = init_data["transaction_id"]

    # Step 2: Confirm payment (simulated mode auto-confirms)
    confirm_resp = httpx.post(
        f"{MARKETPLACE_URL}/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers=_headers(),
        timeout=30,
    )

    return {
        "initiation": init_data,
        "payment_confirmation": confirm_resp.json(),
        "transaction_id": tx_id,
    }


def deliver_data(transaction_id: str, content: str) -> dict:
    """Deliver content for a purchased transaction (seller action).

    Args:
        transaction_id: The transaction to deliver content for
        content: The actual data content

    Returns:
        Transaction status after delivery
    """
    response = httpx.post(
        f"{MARKETPLACE_URL}/transactions/{transaction_id}/deliver",
        json={"content": content},
        headers=_headers(),
        timeout=30,
    )
    return response.json()


def verify_delivered_content(transaction_id: str) -> dict:
    """Verify that delivered content matches the expected hash (buyer action).

    Args:
        transaction_id: The transaction to verify

    Returns:
        Transaction status after verification
    """
    response = httpx.post(
        f"{MARKETPLACE_URL}/transactions/{transaction_id}/verify",
        json={},
        headers=_headers(),
        timeout=30,
    )
    return response.json()


def get_my_reputation() -> dict:
    """Get this agent's reputation score from the marketplace.

    Returns:
        Dict with composite_score, total_transactions, delivery stats, etc.
    """
    agent_id = _agent_state.get("agent_id", "")
    response = httpx.get(
        f"{MARKETPLACE_URL}/reputation/{agent_id}",
        params={"recalculate": "true"},
        timeout=30,
    )
    return response.json()


def express_purchase(listing_id: str) -> dict:
    """Express-buy a listing in a single request. Returns content immediately.

    This is the fastest way to buy data — one request, content returned inline.
    Behind the scenes: auto-creates transaction, auto-confirms payment, auto-verifies.

    Args:
        listing_id: The ID of the listing to buy

    Returns:
        Dict with content, transaction_id, delivery_ms, price_usdc, cache_hit
    """
    response = httpx.get(
        f"{MARKETPLACE_URL}/express/{listing_id}",
        headers=_headers(),
        timeout=10,
    )
    return response.json()


def auto_match_need(
    description: str,
    category: str | None = None,
    max_price: float | None = None,
    auto_buy: bool = False,
    auto_buy_max_price: float | None = None,
) -> dict:
    """Ask the marketplace to automatically find the best listing for your need.

    The marketplace scores listings by keyword overlap, quality, and freshness,
    and shows estimated savings vs. fresh computation.

    Args:
        description: Natural language description of what you need
        category: Optional category filter
        max_price: Maximum price willing to pay
        auto_buy: If True, auto-purchase the top match
        auto_buy_max_price: Max price for auto-purchase

    Returns:
        Matches with savings estimates. If auto_buy=True, includes purchase result.
    """
    response = httpx.post(
        f"{MARKETPLACE_URL}/agents/auto-match",
        json={
            "description": description,
            "category": category,
            "max_price": max_price,
            "auto_buy": auto_buy,
            "auto_buy_max_price": auto_buy_max_price,
        },
        headers=_headers(),
        timeout=30,
    )
    return response.json()


def get_trending_queries(limit: int = 10, hours: int = 6) -> dict:
    """Get currently trending search queries on the marketplace.

    Reveals what buyers are searching for RIGHT NOW. Use this to
    decide what data to produce and list for sale.
    """
    response = httpx.get(
        f"{MARKETPLACE_URL}/analytics/trending",
        params={"limit": limit, "hours": hours},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_demand_gaps(limit: int = 10, category: str | None = None) -> dict:
    """Get unmet demand — queries that buyers search for but nobody sells.

    These are REVENUE OPPORTUNITIES: produce this data and buyers will pay.
    """
    params: dict = {"limit": limit}
    if category:
        params["category"] = category
    response = httpx.get(
        f"{MARKETPLACE_URL}/analytics/demand-gaps",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_opportunities(limit: int = 10, category: str | None = None) -> dict:
    """Get revenue opportunities ranked by urgency.

    Each opportunity includes estimated revenue and urgency level.
    Prioritize high-urgency opportunities for maximum earnings.
    """
    params: dict = {"limit": limit}
    if category:
        params["category"] = category
    response = httpx.get(
        f"{MARKETPLACE_URL}/analytics/opportunities",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_my_earnings() -> dict:
    """Get this agent's earnings breakdown.

    Returns total earned, total spent, net revenue, earnings by category,
    and a daily earnings timeline.
    """
    response = httpx.get(
        f"{MARKETPLACE_URL}/analytics/my-earnings",
        headers=_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_my_stats() -> dict:
    """Get this agent's performance analytics and helpfulness score.

    Returns unique buyers served, cache hits, category coverage,
    helpfulness score, and leaderboard rankings.
    """
    response = httpx.get(
        f"{MARKETPLACE_URL}/analytics/my-stats",
        headers=_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


# ── Catalog Tools ──


def register_catalog_entry(
    namespace: str,
    topic: str,
    description: str = "",
    price_range_min: float = 0.001,
    price_range_max: float = 0.01,
) -> dict:
    """Register a catalog entry declaring what data this agent can produce.

    Other agents can discover your capabilities by searching the catalog.

    Args:
        namespace: Category namespace like "web_search", "code_analysis", etc.
        topic: Specific topic within the namespace (e.g., "python", "react")
        description: What kind of data you produce
        price_range_min: Minimum price in USDC
        price_range_max: Maximum price in USDC

    Returns:
        Dict with catalog entry id, namespace, topic, status
    """
    response = httpx.post(
        f"{MARKETPLACE_URL}/catalog",
        json={
            "namespace": namespace,
            "topic": topic,
            "description": description,
            "price_range_min": price_range_min,
            "price_range_max": price_range_max,
        },
        headers=_headers(),
        timeout=30,
    )
    return response.json()


def search_catalog(
    q: str = "",
    namespace: str | None = None,
    min_quality: float | None = None,
) -> dict:
    """Search the data catalog to discover what sellers can produce.

    The catalog shows registered capabilities — what data sellers
    are willing and able to produce, along with price ranges and quality.

    Args:
        q: Search text for catalog topics and descriptions
        namespace: Filter by namespace (e.g., "web_search")
        min_quality: Minimum quality score (0.0 to 1.0)

    Returns:
        Dict with catalog entries, total count, and pagination info
    """
    params: dict = {}
    if q:
        params["q"] = q
    if namespace:
        params["namespace"] = namespace
    if min_quality is not None:
        params["min_quality"] = min_quality

    response = httpx.get(
        f"{MARKETPLACE_URL}/catalog/search",
        params=params,
        timeout=30,
    )
    return response.json()


def subscribe_catalog(
    namespace_pattern: str,
    topic_pattern: str = "*",
    max_price: float | None = None,
    min_quality: float | None = None,
) -> dict:
    """Subscribe to catalog updates matching a pattern.

    Get notified when new sellers register capabilities in your
    area of interest.

    Args:
        namespace_pattern: Glob pattern like "web_search.*" or "*"
        topic_pattern: Glob pattern for topics (default "*" = all)
        max_price: Only notify if price is below this
        min_quality: Only notify if quality is above this

    Returns:
        Dict with subscription id and status
    """
    body: dict = {
        "namespace_pattern": namespace_pattern,
        "topic_pattern": topic_pattern,
    }
    if max_price is not None:
        body["max_price"] = max_price
    if min_quality is not None:
        body["min_quality"] = min_quality

    response = httpx.post(
        f"{MARKETPLACE_URL}/catalog/subscribe",
        json=body,
        headers=_headers(),
        timeout=30,
    )
    return response.json()


# ── ZKP Tools ──


def verify_zkp(
    listing_id: str,
    keywords: list[str] | None = None,
    schema_has_fields: list[str] | None = None,
    min_size: int | None = None,
    min_quality: float | None = None,
) -> dict:
    """Verify a listing's content claims using Zero-Knowledge Proofs.

    Check content properties WITHOUT seeing the actual data. Useful
    for verifying quality before purchasing.

    Args:
        listing_id: The listing to verify
        keywords: Check if these keywords are probably in the content
        schema_has_fields: Check if JSON content has these field names
        min_size: Check if content is at least this many bytes
        min_quality: Check if quality score meets minimum

    Returns:
        Dict with verified (bool), individual check results, and proof types
    """
    body: dict = {}
    if keywords:
        body["keywords"] = keywords
    if schema_has_fields:
        body["schema_has_fields"] = schema_has_fields
    if min_size is not None:
        body["min_size"] = min_size
    if min_quality is not None:
        body["min_quality"] = min_quality

    response = httpx.post(
        f"{MARKETPLACE_URL}/zkp/{listing_id}/verify",
        json=body,
        headers=_headers(),
        timeout=30,
    )
    return response.json()


def bloom_check(listing_id: str, word: str) -> dict:
    """Quick check if a word is probably in a listing's content.

    Uses a Bloom filter — fast probabilistic check. If it says "yes",
    the word is probably there. If "no", it's definitely not there.

    Args:
        listing_id: The listing to check
        word: The keyword to look for

    Returns:
        Dict with probably_present (bool) and note
    """
    response = httpx.get(
        f"{MARKETPLACE_URL}/zkp/{listing_id}/bloom-check",
        params={"word": word},
        timeout=30,
    )
    return response.json()


# ── Seller Tools ──


def suggest_price(category: str, quality_score: float = 0.8) -> dict:
    """Get an optimal price suggestion for a listing you're about to create.

    The marketplace analyzes competing listings, demand velocity, and
    your quality score to recommend the best price.

    Args:
        category: The category (web_search, code_analysis, etc.)
        quality_score: Your self-assessed quality (0.0 to 1.0)

    Returns:
        Dict with suggested_price, median_price, competitors count, demand info
    """
    response = httpx.post(
        f"{MARKETPLACE_URL}/seller/price-suggest",
        json={"category": category, "quality_score": quality_score},
        headers=_headers(),
        timeout=30,
    )
    return response.json()


def get_demand_for_me() -> dict:
    """Get unmet demand that matches this agent's catalog capabilities.

    Cross-references what buyers are searching for with what you've
    registered in the catalog. Shows revenue opportunities specific to you.

    Returns:
        Dict with matches (demand signals you can fill) and count
    """
    response = httpx.get(
        f"{MARKETPLACE_URL}/seller/demand-for-me",
        headers=_headers(),
        timeout=30,
    )
    return response.json()


# ── Routing Tools ──


def fetch_routing_strategies() -> dict:
    """Get available routing strategies for multi-seller scenarios.

    When multiple sellers have similar data, the marketplace can route
    buyers to the best seller using different strategies.

    Returns:
        Dict with strategies list, default strategy, and descriptions
    """
    response = httpx.get(
        f"{MARKETPLACE_URL}/route/strategies",
        timeout=30,
    )
    return response.json()
