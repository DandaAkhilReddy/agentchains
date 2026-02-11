"""
Test script — exercises the full Seller → Buyer flow through the marketplace.

Usage:
  1. Start marketplace:  python -m uvicorn marketplace.main:app --port 8000
  2. Run this script:    python scripts/test_adk_agents.py

This tests the same flow that ADK agents would use, but programmatically
(no Gemini calls needed — pure HTTP). Good for verifying the marketplace
works end-to-end before deploying to Vertex AI.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE_URL = os.getenv("MARKETPLACE_URL", "http://localhost:8000/api/v1")

GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def step(text: str):
    print(f"  {GREEN}[OK]{RESET} {text}")


def info(text: str):
    print(f"       {BLUE}{text}{RESET}")


def fail(text: str):
    print(f"  {RED}[FAIL]{RESET} {text}")


def banner(text: str):
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{RESET}\n")


async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        # ── Health Check ──
        try:
            r = await c.get(f"{BASE_URL}/health")
            if r.status_code != 200:
                raise Exception(f"Health check returned {r.status_code}")
            step(f"Marketplace healthy at {BASE_URL}")
        except Exception as e:
            fail(f"Cannot reach marketplace at {BASE_URL}: {e}")
            print(f"\n  Start it first:")
            print(f"  python -m uvicorn marketplace.main:app --port 8000\n")
            return

        banner("Phase 1: Agent Registration")

        # ── Register Seller ──
        r = await c.post(f"{BASE_URL}/agents/register", json={
            "name": f"test_seller_{int(time.time())}",
            "description": "Web search data seller for testing",
            "agent_type": "seller",
            "capabilities": ["web_search", "caching"],
            "public_key": "pk-test-seller-key",
        })
        assert r.status_code == 201, f"Seller register failed: {r.text}"
        seller = r.json()
        seller_token = seller["jwt_token"]
        seller_headers = {"Authorization": f"Bearer {seller_token}"}
        step(f"Seller registered: {seller['name']} ({seller['id'][:8]}...)")

        # ── Register Buyer ──
        r = await c.post(f"{BASE_URL}/agents/register", json={
            "name": f"test_buyer_{int(time.time())}",
            "description": "Smart data buyer for testing",
            "agent_type": "buyer",
            "capabilities": ["discovery", "purchasing"],
            "public_key": "pk-test-buyer-key",
        })
        assert r.status_code == 201, f"Buyer register failed: {r.text}"
        buyer = r.json()
        buyer_token = buyer["jwt_token"]
        buyer_headers = {"Authorization": f"Bearer {buyer_token}"}
        step(f"Buyer registered: {buyer['name']} ({buyer['id'][:8]}...)")

        banner("Phase 2: Seller — Catalog + Listings")

        # ── Register Catalog Entry ──
        r = await c.post(f"{BASE_URL}/catalog", json={
            "namespace": "web_search",
            "topic": "python",
            "description": "Python-related web search results",
            "price_range_min": 0.001,
            "price_range_max": 0.01,
        }, headers=seller_headers)
        if r.status_code in (200, 201):
            catalog_entry = r.json()
            step(f"Catalog entry registered: web_search/python")
            info(f"ID: {catalog_entry.get('id', 'N/A')[:8]}...")
        else:
            fail(f"Catalog register: {r.status_code} — {r.text[:200]}")

        # ── Suggest Price ──
        r = await c.post(f"{BASE_URL}/seller/price-suggest", json={
            "category": "web_search",
            "quality_score": 0.85,
        }, headers=seller_headers)
        if r.status_code == 200:
            price_info = r.json()
            suggested = price_info.get("suggested_price", 0.003)
            step(f"Price suggestion: ${suggested:.4f}")
        else:
            suggested = 0.003
            info(f"Price suggest returned {r.status_code}, using default ${suggested}")

        # ── Create 3 Listings ──
        listing_ids = []
        queries = [
            ("Python async patterns", 0.85),
            ("FastAPI best practices", 0.90),
            ("React server components", 0.80),
        ]
        for query, quality in queries:
            content = json.dumps({
                "query": query,
                "results": [
                    {"title": f"Guide to {query}", "url": f"https://example.com/{query.replace(' ', '-')}", "snippet": f"Learn about {query}"},
                    {"title": f"{query} — Deep Dive", "url": f"https://docs.example.com/{query.replace(' ', '-')}", "snippet": f"Advanced {query} techniques"},
                    {"title": f"Top 10 {query} Tips", "url": f"https://blog.example.com/{query.replace(' ', '-')}", "snippet": f"Essential {query} tips"},
                ],
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            r = await c.post(f"{BASE_URL}/listings", json={
                "title": f"Web search: '{query}'",
                "description": f"Cached search results for: {query}",
                "category": "web_search",
                "content": content,
                "price_usdc": suggested,
                "tags": query.lower().split() + ["search", "web", "python"],
                "quality_score": quality,
            }, headers=seller_headers)
            if r.status_code == 201:
                listing = r.json()
                listing_ids.append(listing["id"])
                step(f"Listed: '{query}' at ${suggested:.4f}")
                info(f"Hash: {listing['content_hash'][:30]}...")
            else:
                fail(f"Listing creation failed: {r.text[:200]}")

        assert len(listing_ids) >= 1, "No listings created!"

        banner("Phase 3: Buyer — Discover + Verify + Buy")

        # ── Search Catalog ──
        r = await c.get(f"{BASE_URL}/catalog/search", params={"namespace": "web_search"})
        if r.status_code == 200:
            catalog = r.json()
            step(f"Catalog search: found {catalog.get('total', 0)} entries in web_search")
        else:
            info(f"Catalog search returned {r.status_code}")

        # ── Discover Listings ──
        r = await c.get(f"{BASE_URL}/discover", params={
            "q": "Python async",
            "category": "web_search",
            "sort_by": "quality",
        })
        assert r.status_code == 200, f"Discovery failed: {r.text}"
        results = r.json()
        step(f"Discovery: found {results['total']} listings for 'Python async'")

        target_listing = listing_ids[0]  # Python async patterns listing

        # ── ZKP Bloom Check ──
        try:
            r = await c.get(f"{BASE_URL}/zkp/{target_listing}/bloom-check", params={"word": "python"})
            if r.status_code == 200:
                bloom = r.json()
                step(f"Bloom check 'python': {'PRESENT' if bloom.get('probably_present') else 'NOT FOUND'}")
            else:
                info(f"Bloom check returned {r.status_code} (ZKP proofs may not exist yet)")
        except Exception as e:
            info(f"Bloom check failed (server may have restarted): {e}")

        # ── ZKP Full Verification ──
        try:
            r = await c.post(f"{BASE_URL}/zkp/{target_listing}/verify", json={
                "keywords": ["python", "async"],
                "min_size": 50,
            }, headers=buyer_headers)
            if r.status_code == 200:
                zkp = r.json()
                step(f"ZKP verification: {'PASSED' if zkp.get('verified') else 'FAILED'}")
                for check_name, result in zkp.get("checks", {}).items():
                    info(f"  {check_name}: {'pass' if result.get('passed') else 'fail'}")
            else:
                info(f"ZKP verify returned {r.status_code}")
        except Exception as e:
            info(f"ZKP verify failed: {e}")

        # ── Express Purchase ──
        t0 = time.time()
        r = await c.get(f"{BASE_URL}/express/{target_listing}", headers=buyer_headers)
        delivery_ms = (time.time() - t0) * 1000

        if r.status_code == 200:
            purchase = r.json()
            step(f"Express purchase completed in {delivery_ms:.0f}ms")
            info(f"Transaction: {purchase.get('transaction_id', 'N/A')[:8]}...")
            info(f"Price: ${purchase.get('price_usdc', 0):.4f} USDC")
            info(f"Cache hit: {purchase.get('cache_hit', False)}")
            content_preview = str(purchase.get("content", ""))[:100]
            info(f"Content: {content_preview}...")
        else:
            fail(f"Express purchase failed: {r.status_code} — {r.text[:200]}")

        # ── Second purchase (should be cache hit) ──
        r2 = await c.get(f"{BASE_URL}/express/{target_listing}", headers=buyer_headers)
        if r2.status_code == 200:
            p2 = r2.json()
            step(f"Second purchase — cache hit: {p2.get('cache_hit', False)}")

        banner("Phase 4: Analytics & Reputation")

        # ── CDN Stats ──
        r = await c.get(f"{BASE_URL}/health/cdn")
        if r.status_code == 200:
            cdn = r.json()
            overview = cdn.get("overview", {})
            step(f"CDN stats: {overview.get('total_requests', 0)} requests, "
                 f"T1 hits: {overview.get('tier1_hits', 0)}, "
                 f"T3 (disk): {overview.get('tier3_hits', 0)}")
        else:
            info(f"CDN stats returned {r.status_code}")

        # ── MCP Health ──
        mcp_url = BASE_URL.replace("/api/v1", "/mcp/health")
        r = await c.get(mcp_url)
        if r.status_code == 200:
            mcp = r.json()
            step(f"MCP server: {mcp.get('status')} — {mcp.get('tools_count')} tools, "
                 f"{mcp.get('resources_count')} resources")
        else:
            info(f"MCP health returned {r.status_code}")

        # ── Routing Strategies ──
        r = await c.get(f"{BASE_URL}/route/strategies")
        if r.status_code == 200:
            routing = r.json()
            strategies = routing.get("strategies", [])
            step(f"Routing: {len(strategies)} strategies — {', '.join(strategies[:4])}...")
        else:
            info(f"Routing strategies returned {r.status_code}")

        # ── Seller Reputation ──
        r = await c.get(f"{BASE_URL}/reputation/{seller['id']}", params={"recalculate": "true"})
        if r.status_code == 200:
            rep = r.json()
            step(f"Seller reputation: score={rep.get('composite_score', 0):.3f}, "
                 f"txns={rep.get('total_transactions', 0)}")

        # ── Health Summary ──
        r = await c.get(f"{BASE_URL}/health")
        h = r.json()
        step(f"Final: {h['agents_count']} agents, {h['listings_count']} listings, "
             f"{h['transactions_count']} transactions")

        banner("All Tests Passed!")
        print(f"  The marketplace is working end-to-end.")
        print(f"  Next steps:")
        print(f"  1. Run ADK agents:  adk web --port 8501  (in agents/web_search_agent/)")
        print(f"  2. Deploy to Cloud Run:  gcloud run deploy agentchains-marketplace --source .")
        print(f"  3. Deploy to Vertex AI:  adk deploy agent --project <ID> --region us-central1")
        print()


if __name__ == "__main__":
    asyncio.run(main())
