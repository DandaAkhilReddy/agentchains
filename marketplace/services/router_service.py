"""Smart Routing: 7 strategies for choosing among competing sellers.

When multiple sellers have similar data, the router picks the best one
based on the buyer's preference (price, speed, quality, fairness, etc.).
"""

import math
import random
import time
from collections import defaultdict

from marketplace.services.cache_service import TTLCache

# Round-robin state: tracks per content_hash:seller_id access counts
_round_robin_state = TTLCache(maxsize=4096, default_ttl=3600.0)  # 1-hour TTL

STRATEGIES = [
    "cheapest",
    "fastest",
    "highest_quality",
    "best_value",
    "round_robin",
    "weighted_random",
    "locality",
]


def smart_route(
    candidates: list[dict],
    strategy: str = "best_value",
    buyer_region: str | None = None,
) -> list[dict]:
    """Apply a routing strategy to re-rank candidates.

    Each candidate dict must have: listing_id, price_usdc, quality_score,
    match_score, seller_id. Optional: avg_response_ms, region.

    Returns candidates re-ranked by the chosen strategy.
    """
    if not candidates:
        return candidates

    if strategy not in STRATEGIES:
        strategy = "best_value"

    router_fn = {
        "cheapest": _route_cheapest,
        "fastest": _route_fastest,
        "highest_quality": _route_highest_quality,
        "best_value": _route_best_value,
        "round_robin": _route_round_robin,
        "weighted_random": _route_weighted_random,
        "locality": _route_locality,
    }[strategy]

    scored = router_fn(candidates, buyer_region)

    # Add routing metadata
    for item in scored:
        item["routing_strategy"] = strategy

    return scored


def _normalize(values: list[float]) -> list[float]:
    """Min-max normalize to [0, 1]."""
    if not values:
        return values
    mn, mx = min(values), max(values)
    rng = mx - mn
    if rng == 0:
        return [0.5] * len(values)
    return [(v - mn) / rng for v in values]


def _route_cheapest(candidates: list[dict], _region: str | None) -> list[dict]:
    """Score = 1 - normalize(price). Cheapest wins."""
    prices = [c["price_usdc"] for c in candidates]
    normed = _normalize(prices)
    for c, n in zip(candidates, normed):
        c["routing_score"] = round(1 - n, 4)
    return sorted(candidates, key=lambda x: x["routing_score"], reverse=True)


def _route_fastest(candidates: list[dict], _region: str | None) -> list[dict]:
    """Score = 1 - normalize(avg_response_ms). Fastest wins."""
    times = [c.get("avg_response_ms", 100) for c in candidates]
    normed = _normalize(times)
    for c, n in zip(candidates, normed):
        c["routing_score"] = round(1 - n, 4)
    return sorted(candidates, key=lambda x: x["routing_score"], reverse=True)


def _route_highest_quality(candidates: list[dict], _region: str | None) -> list[dict]:
    """0.5*quality + 0.3*reputation + 0.2*freshness."""
    for c in candidates:
        quality = c.get("quality_score", 0.5)
        reputation = c.get("reputation", 0.5)
        freshness = c.get("freshness_score", 0.5)
        c["routing_score"] = round(0.5 * quality + 0.3 * reputation + 0.2 * freshness, 4)
    return sorted(candidates, key=lambda x: x["routing_score"], reverse=True)


def _route_best_value(candidates: list[dict], _region: str | None) -> list[dict]:
    """0.4*(quality/price) + 0.25*reputation + 0.2*freshness + 0.15*(1-price_norm)."""
    prices = [c["price_usdc"] for c in candidates]
    price_normed = _normalize(prices)
    for c, pn in zip(candidates, price_normed):
        quality = c.get("quality_score", 0.5)
        price = max(c["price_usdc"], 0.0001)
        reputation = c.get("reputation", 0.5)
        freshness = c.get("freshness_score", 0.5)
        value_ratio = min(quality / price, 100)  # cap at 100
        value_norm = value_ratio / 100
        c["routing_score"] = round(
            0.4 * value_norm + 0.25 * reputation + 0.2 * freshness + 0.15 * (1 - pn), 4
        )
    return sorted(candidates, key=lambda x: x["routing_score"], reverse=True)


def _route_round_robin(candidates: list[dict], _region: str | None) -> list[dict]:
    """Fair rotation among sellers: score = 1/(1+access_count)."""
    for c in candidates:
        key = f"rr:{c.get('content_hash', '')}:{c['seller_id']}"
        count = _round_robin_state.get(key) or 0
        c["routing_score"] = round(1 / (1 + count), 4)
        c["_rr_key"] = key
        c["_rr_count"] = count

    result = sorted(candidates, key=lambda x: x["routing_score"], reverse=True)

    # Increment winner's count
    if result:
        winner = result[0]
        key = winner.pop("_rr_key", "")
        count = winner.pop("_rr_count", 0)
        if key:
            _round_robin_state.put(key, count + 1)
    for c in result[1:]:
        c.pop("_rr_key", None)
        c.pop("_rr_count", None)

    return result


def _route_weighted_random(candidates: list[dict], _region: str | None) -> list[dict]:
    """Probabilistic selection proportional to quality*reputation/price."""
    weights = []
    for c in candidates:
        quality = c.get("quality_score", 0.5)
        reputation = c.get("reputation", 0.5)
        price = max(c["price_usdc"], 0.0001)
        w = quality * reputation / price
        weights.append(max(w, 0.001))

    total_weight = sum(weights)
    probabilities = [w / total_weight for w in weights]

    # Assign routing score = probability
    for c, p in zip(candidates, probabilities):
        c["routing_score"] = round(p, 4)

    # Shuffle by weighted random selection
    result = []
    remaining = list(zip(candidates, weights))
    while remaining:
        total = sum(w for _, w in remaining)
        r = random.random() * total
        cumulative = 0.0
        for i, (c, w) in enumerate(remaining):
            cumulative += w
            if cumulative >= r:
                result.append(c)
                remaining.pop(i)
                break

    return result


# Region adjacency map (simplified)
REGION_ADJACENCY = {
    "us-east": {"us-west", "us-central", "eu-west"},
    "us-west": {"us-east", "us-central", "asia-east"},
    "us-central": {"us-east", "us-west"},
    "eu-west": {"us-east", "eu-central"},
    "eu-central": {"eu-west", "asia-west"},
    "asia-east": {"us-west", "asia-south"},
    "asia-south": {"asia-east", "asia-west"},
    "asia-west": {"eu-central", "asia-south"},
}


def _route_locality(candidates: list[dict], buyer_region: str | None) -> list[dict]:
    """1.0 same_region, 0.5 adjacent, 0.2 other. Falls back to best_value."""
    if not buyer_region:
        return _route_best_value(candidates, None)

    adjacent = REGION_ADJACENCY.get(buyer_region, set())

    for c in candidates:
        seller_region = c.get("region", "")
        if seller_region == buyer_region:
            locality = 1.0
        elif seller_region in adjacent:
            locality = 0.5
        else:
            locality = 0.2

        quality = c.get("quality_score", 0.5)
        price_inv = 1 - min(c["price_usdc"] / 0.1, 1.0)
        c["routing_score"] = round(0.5 * locality + 0.3 * quality + 0.2 * price_inv, 4)

    return sorted(candidates, key=lambda x: x["routing_score"], reverse=True)
