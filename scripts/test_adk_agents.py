"""
End-to-end script that exercises the Seller -> Buyer flow through the marketplace.

Usage:
  1. Start marketplace:  python -m uvicorn marketplace.main:app --port 8000
  2. Run this script:    python scripts/test_adk_agents.py

Override target:
  MARKETPLACE_URL=http://127.0.0.1:8000/api/v1 python scripts/test_adk_agents.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any

import httpx

BASE_URL = os.getenv("MARKETPLACE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")

GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

COUNTS = {"passed": 0, "failed": 0, "skipped": 0}
FAILURES: list[str] = []


def _ok(text: str) -> None:
    COUNTS["passed"] += 1
    print(f"  {GREEN}[OK]{RESET} {text}")


def _info(text: str) -> None:
    print(f"       {BLUE}{text}{RESET}")


def _fail(text: str) -> None:
    COUNTS["failed"] += 1
    FAILURES.append(text)
    print(f"  {RED}[FAIL]{RESET} {text}")


def _skip(text: str) -> None:
    COUNTS["skipped"] += 1
    print(f"  {YELLOW}[SKIP]{RESET} {text}")


def banner(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{RESET}\n")


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    retries: int = 3,
    **kwargs: Any,
) -> httpx.Response:
    for attempt in range(retries + 1):
        response = await client.request(method, url, **kwargs)
        if response.status_code != 429 or attempt == retries:
            return response
        retry_after = int(response.json().get("retry_after", 1))
        await asyncio.sleep(max(1, retry_after))
    return response


async def main() -> int:
    async with httpx.AsyncClient(timeout=30) as c:
        # Health check
        try:
            r = await c.get(f"{BASE_URL}/health")
            if r.status_code != 200:
                _fail(f"Health check returned {r.status_code}: {r.text[:200]}")
                return 1
            _ok(f"Marketplace healthy at {BASE_URL}")
        except Exception as exc:
            _fail(f"Cannot reach marketplace at {BASE_URL}: {exc}")
            print("\n  Start it first:")
            print("  python -m uvicorn marketplace.main:app --port 8000\n")
            return 1

        banner("Phase 1: Agent Registration")

        seller_headers: dict[str, str] = {}
        buyer_headers: dict[str, str] = {}
        seller: dict[str, Any] | None = None

        seller_resp = await _request_with_retry(
            c,
            "POST",
            f"{BASE_URL}/agents/register",
            json={
                "name": f"test_seller_{int(time.time())}",
                "description": "Web search data seller for testing",
                "agent_type": "seller",
                "capabilities": ["web_search", "caching"],
                "public_key": "pk-test-seller-key",
            },
        )
        if seller_resp.status_code == 201:
            seller = seller_resp.json()
            seller_token = seller["jwt_token"]
            seller_headers = {"Authorization": f"Bearer {seller_token}"}
            _ok(f"Seller registered: {seller['name']} ({seller['id'][:8]}...)")
        else:
            _fail(f"Seller register failed: {seller_resp.status_code} - {seller_resp.text[:200]}")

        buyer_resp = await _request_with_retry(
            c,
            "POST",
            f"{BASE_URL}/agents/register",
            json={
                "name": f"test_buyer_{int(time.time())}",
                "description": "Smart data buyer for testing",
                "agent_type": "buyer",
                "capabilities": ["discovery", "purchasing"],
                "public_key": "pk-test-buyer-key",
            },
        )
        if buyer_resp.status_code == 201:
            buyer = buyer_resp.json()
            buyer_token = buyer["jwt_token"]
            buyer_headers = {"Authorization": f"Bearer {buyer_token}"}
            _ok(f"Buyer registered: {buyer['name']} ({buyer['id'][:8]}...)")
        else:
            _fail(f"Buyer register failed: {buyer_resp.status_code} - {buyer_resp.text[:200]}")

        if not seller_headers or not buyer_headers:
            _fail("Cannot continue without both seller and buyer tokens")
            return 1

        banner("Phase 2: Seller - Catalog + Listings")

        r = await c.post(
            f"{BASE_URL}/catalog",
            json={
                "namespace": "web_search",
                "topic": "python",
                "description": "Python-related web search results",
                "price_range_min": 0.001,
                "price_range_max": 0.01,
            },
            headers=seller_headers,
        )
        if r.status_code in (200, 201):
            catalog_entry = r.json()
            _ok("Catalog entry registered: web_search/python")
            _info(f"ID: {catalog_entry.get('id', 'N/A')[:8]}...")
        else:
            _fail(f"Catalog register failed: {r.status_code} - {r.text[:200]}")

        r = await c.post(
            f"{BASE_URL}/seller/price-suggest",
            json={"category": "web_search", "quality_score": 0.85},
            headers=seller_headers,
        )
        if r.status_code == 200:
            suggested = r.json().get("suggested_price", 0.003)
            _ok(f"Price suggestion: ${suggested:.4f}")
        else:
            suggested = 0.003
            _skip(f"Price suggest returned {r.status_code}, using default ${suggested}")

        listing_ids: list[str] = []
        queries = [
            ("Python async patterns", 0.85),
            ("FastAPI best practices", 0.90),
            ("React server components", 0.80),
        ]
        for query, quality in queries:
            content = json.dumps(
                {
                    "query": query,
                    "results": [
                        {
                            "title": f"Guide to {query}",
                            "url": f"https://example.com/{query.replace(' ', '-')}",
                            "snippet": f"Learn about {query}",
                        },
                        {
                            "title": f"{query} - Deep Dive",
                            "url": f"https://docs.example.com/{query.replace(' ', '-')}",
                            "snippet": f"Advanced {query} techniques",
                        },
                    ],
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
            r = await c.post(
                f"{BASE_URL}/listings",
                json={
                    "title": f"Web search: '{query}'",
                    "description": f"Cached search results for: {query}",
                    "category": "web_search",
                    "content": content,
                    "price_usdc": suggested,
                    "tags": query.lower().split() + ["search", "web", "python"],
                    "quality_score": quality,
                },
                headers=seller_headers,
            )
            if r.status_code == 201:
                listing = r.json()
                listing_ids.append(listing["id"])
                _ok(f"Listed: '{query}' at ${suggested:.4f}")
                _info(f"Hash: {listing['content_hash'][:30]}...")
            else:
                _fail(f"Listing creation failed: {r.status_code} - {r.text[:200]}")

        if not listing_ids:
            _fail("No listings were created; aborting remaining phases")
            return 1

        banner("Phase 3: Buyer - Discover + Verify + Buy")

        r = await c.get(f"{BASE_URL}/catalog/search", params={"namespace": "web_search"})
        if r.status_code == 200:
            _ok(f"Catalog search: found {r.json().get('total', 0)} entries in web_search")
        else:
            _skip(f"Catalog search returned {r.status_code}")

        r = await c.get(
            f"{BASE_URL}/discover",
            params={"q": "Python async", "category": "web_search", "sort_by": "quality"},
        )
        if r.status_code == 200:
            results = r.json()
            _ok(f"Discovery: found {results['total']} listings for 'Python async'")
        else:
            _fail(f"Discovery failed: {r.status_code} - {r.text[:200]}")
            results = {"total": 0}

        target_listing = listing_ids[0]

        r = await c.get(f"{BASE_URL}/zkp/{target_listing}/bloom-check", params={"word": "python"})
        if r.status_code == 200:
            bloom = r.json()
            present = bloom.get("probably_present") or bloom.get("probably_contains")
            _ok(f"Bloom check 'python': {'PRESENT' if present else 'NOT FOUND'}")
        else:
            _skip(f"Bloom check returned {r.status_code}")

        r = await c.post(
            f"{BASE_URL}/zkp/{target_listing}/verify",
            json={"keywords": ["python", "async"], "min_size": 50},
            headers=buyer_headers,
        )
        if r.status_code == 200:
            zkp = r.json()
            _ok(f"ZKP verification: {'PASSED' if zkp.get('verified') else 'FAILED'}")
        else:
            _skip(f"ZKP verify returned {r.status_code}")

        t0 = time.time()
        r = await c.post(
            f"{BASE_URL}/express/{target_listing}",
            headers=buyer_headers,
            json={"payment_method": "token"},
        )
        delivery_ms = (time.time() - t0) * 1000
        if r.status_code == 200:
            purchase = r.json()
            _ok(f"Express purchase completed in {delivery_ms:.0f}ms")
            _info(f"Transaction: {purchase.get('transaction_id', 'N/A')[:8]}...")
            _info(f"Cache hit: {purchase.get('cache_hit', False)}")
        else:
            _fail(f"Express purchase failed: {r.status_code} - {r.text[:200]}")

        r2 = await c.post(
            f"{BASE_URL}/express/{target_listing}",
            headers=buyer_headers,
            json={"payment_method": "token"},
        )
        if r2.status_code == 200:
            p2 = r2.json()
            _ok(f"Second purchase - cache hit: {p2.get('cache_hit', False)}")
        else:
            _fail(f"Second express purchase failed: {r2.status_code} - {r2.text[:200]}")

        banner("Phase 4: Analytics & Reputation")

        r = await c.get(f"{BASE_URL}/health/cdn")
        if r.status_code == 200:
            overview = r.json().get("overview", {})
            _ok(
                f"CDN stats: {overview.get('total_requests', 0)} requests, "
                f"T1 hits: {overview.get('tier1_hits', 0)}, "
                f"T3 (disk): {overview.get('tier3_hits', 0)}"
            )
        else:
            _skip(f"CDN stats returned {r.status_code}")

        mcp_url = BASE_URL.replace("/api/v1", "/mcp/health")
        r = await c.get(mcp_url)
        if r.status_code == 200:
            mcp = r.json()
            _ok(f"MCP server: {mcp.get('status')} - {mcp.get('tools_count')} tools")
        else:
            _skip(f"MCP health returned {r.status_code}")

        r = await c.get(f"{BASE_URL}/route/strategies")
        if r.status_code == 200:
            strategies = r.json().get("strategies", [])
            _ok(f"Routing: {len(strategies)} strategies")
        else:
            _skip(f"Routing strategies returned {r.status_code}")

        if seller is not None:
            r = await c.get(f"{BASE_URL}/reputation/{seller['id']}", params={"recalculate": "true"})
            if r.status_code == 200:
                rep = r.json()
                _ok(f"Seller reputation: score={rep.get('composite_score', 0):.3f}")
            else:
                _skip(f"Seller reputation returned {r.status_code}")

        r = await c.get(f"{BASE_URL}/health")
        if r.status_code == 200:
            h = r.json()
            _ok(
                f"Final: {h['agents_count']} agents, {h['listings_count']} listings, "
                f"{h['transactions_count']} transactions"
            )
        else:
            _fail(f"Final health check failed: {r.status_code} - {r.text[:200]}")

    banner("Run Summary")
    print(
        f"  Passed: {COUNTS['passed']} | Failed: {COUNTS['failed']} | "
        f"Skipped: {COUNTS['skipped']}"
    )
    if FAILURES:
        print("  Failures:")
        for item in FAILURES:
            print(f"    - {item}")
        return 1

    print("  All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
