"""Full E2E test against a configurable AgentChains deployment.

Defaults to local deployment:
  MARKETPLACE_URL=http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Callable

import httpx

BASE = os.getenv("MARKETPLACE_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE}/api/v1"

passed = 0
failed = 0
errors: list[tuple[str, str]] = []


def test(name: str, fn: Callable[[], None]):
    global passed, failed
    try:
        result = fn()
        passed += 1
        print(f"  PASS  {name}")
        return result
    except Exception as exc:
        failed += 1
        errors.append((name, str(exc)))
        print(f"  FAIL  {name}: {exc}")
        return None


def post_with_retry(client: httpx.Client, path: str, *, json_body: dict, headers: dict | None = None) -> httpx.Response:
    retries = 3
    for attempt in range(retries + 1):
        response = client.post(path, json=json_body, headers=headers)
        if response.status_code != 429 or attempt == retries:
            return response
        retry_after = int(response.json().get("retry_after", 1))
        time.sleep(max(1, retry_after))
    return response


def main():
    global passed, failed
    client = httpx.Client(base_url=API, verify=False, timeout=30)
    mcp_client = httpx.Client(base_url=BASE, verify=False, timeout=30)

    print("=" * 60)
    print("  AgentChains Deployment E2E Test")
    print("=" * 60)
    print(f"         Target: {BASE}")

    # 1. Health
    def t1():
        r = client.get("/health")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "healthy"
        print(
            f"         Version: {d['version']}, Agents: {d['agents_count']}, "
            f"Listings: {d['listings_count']}"
        )

    test("1. Health Check", t1)

    # 2. MCP Health
    def t2():
        r = mcp_client.get("/mcp/health")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ok"
        print(f"         Tools: {d['tools_count']}, Resources: {d['resources_count']}")

    test("2. MCP Health", t2)

    seller_token = None
    seller_id = None

    # 3. Register Seller
    def t3():
        nonlocal seller_token, seller_id
        ts = int(time.time())
        r = post_with_retry(
            client,
            "/agents/register",
            json_body={
                "name": f"e2e_seller_{ts}",
                "agent_type": "seller",
                "capabilities": ["web_search", "code_analysis"],
                "public_key": f"e2e-seller-{ts}-key",
            },
        )
        assert r.status_code in (200, 201), f"Status {r.status_code}: {r.text}"
        d = r.json()
        assert "jwt_token" in d, f"No token in response: {d}"
        seller_token = d["jwt_token"]
        seller_id = d["id"]
        print(f"         ID: {seller_id[:20]}...")

    test("3. Register Seller Agent", t3)

    buyer_token = None
    buyer_id = None

    # 4. Register Buyer
    def t4():
        nonlocal buyer_token, buyer_id
        ts = int(time.time())
        r = post_with_retry(
            client,
            "/agents/register",
            json_body={
                "name": f"e2e_buyer_{ts}",
                "agent_type": "buyer",
                "capabilities": ["data_consumer"],
                "public_key": f"e2e-buyer-{ts}-key",
            },
        )
        assert r.status_code in (200, 201), f"Status {r.status_code}: {r.text}"
        d = r.json()
        buyer_token = d["jwt_token"]
        buyer_id = d["id"]
        print(f"         ID: {buyer_id[:20]}...")

    test("4. Register Buyer Agent", t4)

    if not seller_token or not buyer_token:
        print("\nCRITICAL: Agent registration failed. Cannot continue.")
        sys.exit(1)

    seller_headers = {"Authorization": f"Bearer {seller_token}"}
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

    # 5. Register Catalog Entry
    def t5():
        r = client.post(
            "/catalog",
            json={
                "namespace": "web_search",
                "topic": "python",
                "description": "Python web search results",
                "price_range_min": 0.002,
                "price_range_max": 0.010,
            },
            headers=seller_headers,
        )
        assert r.status_code in (200, 201), f"Status {r.status_code}: {r.text}"
        d = r.json()
        print(f"         Catalog ID: {d.get('id', 'N/A')}")

    test("5. Register Catalog Entry", t5)

    listing1_id = None

    # 6. Create Listing 1
    def t6():
        nonlocal listing1_id
        r = client.post(
            "/listings",
            json={
                "title": "E2E: Python web search results",
                "description": "Comprehensive Python tutorial search",
                "category": "web_search",
                "content": json.dumps(
                    [
                        {"position": 1, "title": "Python.org", "url": "https://python.org"},
                        {"position": 2, "title": "Real Python", "url": "https://realpython.com"},
                    ]
                ),
                "price_usdc": 0.003,
                "tags": ["python", "tutorial", "web_search"],
                "quality_score": 0.92,
            },
            headers=seller_headers,
        )
        assert r.status_code in (200, 201), f"Status {r.status_code}: {r.text}"
        d = r.json()
        listing1_id = d["id"]
        print(f"         ID: {listing1_id}, Hash: {d['content_hash'][:30]}...")

    test("6. Create Listing (Python search)", t6)

    listing2_id = None

    # 7. Create Listing 2
    def t7():
        nonlocal listing2_id
        r = client.post(
            "/listings",
            json={
                "title": "E2E: React vs Vue comparison",
                "description": "JavaScript framework benchmarks 2026",
                "category": "code_analysis",
                "content": json.dumps(
                    [
                        {"framework": "React", "stars": 230000, "bundle_kb": 42},
                        {"framework": "Vue", "stars": 210000, "bundle_kb": 33},
                    ]
                ),
                "price_usdc": 0.005,
                "tags": ["javascript", "react", "vue"],
                "quality_score": 0.88,
            },
            headers=seller_headers,
        )
        assert r.status_code in (200, 201), f"Status {r.status_code}: {r.text}"
        d = r.json()
        listing2_id = d["id"]
        print(f"         ID: {listing2_id}")

    test("7. Create Listing (JS frameworks)", t7)

    # 8. List All Listings
    def t8():
        r = client.get("/listings", headers=buyer_headers)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        d = r.json()
        count = len(d) if isinstance(d, list) else d.get("total", len(d.get("results", [])))
        print(f"         Total listings: {count}")

    test("8. List All Listings", t8)

    # 9. Discover/Search
    def t9():
        r = client.get("/discover", params={"q": "python"}, headers=buyer_headers)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        d = r.json()
        print(f"         Found: {d.get('total', len(d.get('results', [])))} results")

    test("9. Discover (search 'python')", t9)

    # 10. Search Catalog
    def t10():
        r = client.get("/catalog/search", params={"q": "python"}, headers=buyer_headers)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        d = r.json()
        print(f"         Catalog entries: {d.get('total', 0)}")

    test("10. Search Catalog", t10)

    # 11. Bloom Check (ZKP)
    if listing1_id:
        def t11():
            r = client.get(
                f"/zkp/{listing1_id}/bloom-check",
                params={"word": "python"},
                headers=buyer_headers,
            )
            assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
            d = r.json()
            print(f"         Contains 'python': {d.get('probably_contains', d)}")

        test("11. Bloom Check (ZKP)", t11)

    # 12. ZKP Full Verify
    if listing1_id:
        def t12():
            r = client.post(
                f"/zkp/{listing1_id}/verify",
                json={"claims": {"keywords": ["python", "tutorial"], "min_size": 10}},
                headers=buyer_headers,
            )
            assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
            d = r.json()
            print(f"         Verified: {d.get('verified', d.get('all_passed', d))}")

        test("12. ZKP Full Verify", t12)

    # 13. Express Purchase
    if listing1_id:
        def t13():
            r = client.post(
                f"/express/{listing1_id}",
                headers=buyer_headers,
                json={"payment_method": "token"},
            )
            assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
            d = r.json()
            print(f"         TX: {d.get('transaction_id', 'N/A')}, Content delivered: {'content' in d}")

        test("13. Express Purchase", t13)

    # 14. Initiate Transaction (manual flow)
    tx_id = None
    if listing2_id:
        def t14():
            nonlocal tx_id
            r = client.post("/transactions/initiate", json={"listing_id": listing2_id}, headers=buyer_headers)
            assert r.status_code in (200, 201), f"Status {r.status_code}: {r.text}"
            d = r.json()
            tx_id = d.get("id", d.get("transaction_id"))
            print(f"         TX ID: {tx_id}, Status: {d.get('status', 'N/A')}")

        test("14. Initiate Transaction", t14)

    # 15. Auto-Match
    def t15():
        r = client.post(
            "/agents/auto-match",
            json={"description": "python tutorial search", "category": "web_search", "max_price": 0.01},
            headers=buyer_headers,
        )
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        d = r.json()
        print(f"         Match: {d.get('match', d.get('best_match', 'N/A'))}")

    test("15. Auto-Match", t15)

    # 16. Routing
    if listing1_id and listing2_id:
        def t16():
            r = client.post(
                "/route/select",
                json={
                    "candidates": [
                        {
                            "listing_id": listing1_id,
                            "price_usdc": 0.003,
                            "quality_score": 0.92,
                            "seller_id": seller_id,
                            "match_score": 0.9,
                        },
                        {
                            "listing_id": listing2_id,
                            "price_usdc": 0.005,
                            "quality_score": 0.88,
                            "seller_id": seller_id,
                            "match_score": 0.85,
                        },
                    ],
                    "strategy": "best_value",
                },
                headers=buyer_headers,
            )
            assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
            d = r.json()
            print(f"         Strategy: {d.get('strategy', 'N/A')}, Winner: {d.get('selected', 'N/A')}")

        test("16. Routing (best_value)", t16)

    # 17. Analytics - Trending
    def t17():
        r = client.get("/analytics/trending", headers=buyer_headers)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        d = r.json()
        print(f"         Trends: {len(d.get('trends', []))} queries")

    test("17. Analytics - Trending", t17)

    # 18. Analytics - My Earnings
    def t18():
        r = client.get("/analytics/my-earnings", headers=seller_headers)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        d = r.json()
        print(f"         Earnings: ${d.get('total_earned_usdc', 0)}")

    test("18. Seller Earnings", t18)

    # 19. Analytics - My Stats
    def t19():
        r = client.get("/analytics/my-stats", headers=seller_headers)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        d = r.json()
        print(f"         Stats: {json.dumps(d)[:100]}...")

    test("19. Seller Stats", t19)

    # 20. Reputation
    if seller_id:
        def t20():
            r = client.get(f"/reputation/{seller_id}", headers=seller_headers)
            assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
            d = r.json()
            print(f"         Score: {d.get('composite_score', d.get('score', d))}")

        test("20. Seller Reputation", t20)

    # 21. Agent Profile
    if seller_id:
        def t21():
            r = client.get(f"/analytics/agent/{seller_id}/profile", headers=seller_headers)
            assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
            d = r.json()
            print(f"         Name: {d.get('agent_name', d.get('name', 'N/A'))}")

        test("21. Agent Profile", t21)

    # 22. CDN Stats
    def t22():
        r = client.get("/health/cdn")
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        d = r.json()
        print(f"         Requests: {d.get('overview', {}).get('total_requests', 0)}")

    test("22. CDN Stats", t22)

    # 23. Leaderboard
    def t23():
        r = client.get("/analytics/leaderboard/helpfulness", headers=buyer_headers)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        d = r.json()
        print(f"         Leaderboard entries: {len(d.get('entries', []))}")

    test("23. Reputation Leaderboard", t23)

    # 24. Demand Gaps
    def t24():
        r = client.get("/analytics/demand-gaps", params={"category": "web_search"}, headers=seller_headers)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        d = r.json()
        print(f"         Gaps: {len(d.get('gaps', []))}")

    test("24. Demand Gaps", t24)

    # 25. Final Health
    def t25():
        r = client.get("/health")
        assert r.status_code == 200
        d = r.json()
        print(f"         Agents: {d['agents_count']} | Listings: {d['listings_count']} | TX: {d['transactions_count']}")
        assert d["agents_count"] >= 2
        assert d["listings_count"] >= 2

    test("25. Final Health Verify", t25)

    print()
    print("=" * 60)
    total = passed + failed
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    if errors:
        print("\n  Failed tests:")
        for name, err in errors:
            print(f"    {name}: {err[:160]}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
