"""Shared tool functions that ADK agents use to interact with the marketplace API."""
import httpx

MARKETPLACE_URL = "http://localhost:8000/api/v1"

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
