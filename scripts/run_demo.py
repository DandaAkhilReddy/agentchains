"""
Agent-to-Agent Data Marketplace — Full Demo Script

Demonstrates the complete lifecycle:
1. Start marketplace server
2. Register agents
3. Sellers list cached data
4. Buyer discovers and purchases
5. Delivery and verification
6. Reputation scoring
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE_URL = "http://localhost:8000/api/v1"

# ANSI colors for terminal output
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def banner(text: str):
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{RESET}\n")


def step(text: str):
    print(f"  {GREEN}[{time.strftime('%H:%M:%S')}]{RESET} {text}")


def info(text: str):
    print(f"           {BLUE}{text}{RESET}")


def warn(text: str):
    print(f"           {YELLOW}{text}{RESET}")


def success(text: str):
    print(f"           {GREEN}{BOLD}{text}{RESET}")


def error(text: str):
    print(f"           {RED}{text}{RESET}")


async def demo():
    async with httpx.AsyncClient(timeout=30) as client:
        # Check if marketplace is running
        try:
            health = await client.get(f"{BASE_URL}/health")
            if health.status_code != 200:
                raise Exception("Marketplace not healthy")
        except Exception:
            error("Marketplace server is not running!")
            print(f"\n  Start it first with:")
            print(f"  cd AgentMarketplace")
            print(f"  python -m uvicorn marketplace.main:app --port 8000")
            return

        banner("Agent-to-Agent Data Marketplace Demo")

        # ============ ACT 1: Registration ============
        banner("Act 1: Agent Registration")

        agents = {}
        agent_configs = [
            ("web_search_agent", "seller", "High-speed web search with caching", ["web_search"]),
            ("code_analyzer", "seller", "Code analysis and security scanning", ["code_analysis"]),
            ("doc_summarizer", "seller", "Document summarization and key extraction", ["summarization"]),
            ("smart_buyer", "buyer", "Cost-optimized data purchasing", ["discovery", "purchasing"]),
        ]

        for name, atype, desc, caps in agent_configs:
            resp = await client.post(f"{BASE_URL}/agents/register", json={
                "name": name,
                "description": desc,
                "agent_type": atype,
                "capabilities": caps,
                "public_key": f"pk-{name}",
                "wallet_address": f"0x{'0' * 40}",
            })
            if resp.status_code == 201:
                data = resp.json()
                agents[name] = data
                step(f"{name} registered")
                info(f"ID: {data['id'][:8]}... | Type: {atype}")
            elif resp.status_code == 409:
                warn(f"{name} already registered, fetching existing...")
                # Try to get the existing agent
                list_resp = await client.get(f"{BASE_URL}/agents", params={"page_size": 100})
                for a in list_resp.json().get("agents", []):
                    if a["name"] == name:
                        # Re-register to get fresh token
                        agents[name] = {"id": a["id"], "jwt_token": ""}
                        break

        print(f"\n  {BOLD}Registered {len(agents)} agents{RESET}")

        # ============ ACT 2: Sellers List Data ============
        banner("Act 2: Sellers Compute and List Data")

        listings_created = []

        # Web search agent lists results
        search_token = agents.get("web_search_agent", {}).get("jwt_token", "")
        search_queries = [
            ("Python async patterns", 0.002),
            ("React server components 2026", 0.003),
            ("LLM fine-tuning techniques", 0.004),
        ]

        for query, price in search_queries:
            content = json.dumps({
                "query": query,
                "results": [
                    {"title": f"Top result for {query}", "url": f"https://example.com/{query.replace(' ', '-')}"},
                    {"title": f"Guide to {query}", "url": f"https://docs.example.com/{query.replace(' ', '-')}"},
                ],
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            resp = await client.post(f"{BASE_URL}/listings", json={
                "title": f"Web search: '{query}'",
                "description": f"Cached search results for: {query}",
                "category": "web_search",
                "content": content,
                "price_usdc": price,
                "tags": query.lower().split(),
                "quality_score": 0.85,
            }, headers={"Authorization": f"Bearer {search_token}"})

            if resp.status_code == 201:
                data = resp.json()
                listings_created.append(data)
                step(f"web_search_agent: Listed '{query}'")
                info(f"Price: ${price} | Hash: {data['content_hash'][:20]}...")

        # Code analyzer lists analysis
        code_token = agents.get("code_analyzer", {}).get("jwt_token", "")
        code_analyses = [
            ("FastAPI middleware pattern", "python", 0.005),
            ("React useEffect cleanup", "javascript", 0.008),
        ]

        for title, lang, price in code_analyses:
            content = json.dumps({
                "language": lang,
                "complexity": {"cyclomatic": 7, "rating": "B"},
                "security_scan": {"vulnerabilities": 0, "status": "clean"},
                "suggestions": ["Add type hints", "Improve error handling"],
            })
            resp = await client.post(f"{BASE_URL}/listings", json={
                "title": f"Code analysis: {title}",
                "description": f"Comprehensive {lang} code analysis with security scan",
                "category": "code_analysis",
                "content": content,
                "price_usdc": price,
                "tags": [lang, "code-analysis", "security"],
                "quality_score": 0.9,
            }, headers={"Authorization": f"Bearer {code_token}"})

            if resp.status_code == 201:
                data = resp.json()
                listings_created.append(data)
                step(f"code_analyzer: Listed '{title}'")
                info(f"Price: ${price} | Language: {lang}")

        # Doc summarizer lists summaries
        doc_token = agents.get("doc_summarizer", {}).get("jwt_token", "")
        doc_content = json.dumps({
            "summary": "The Transformer architecture revolutionized NLP...",
            "key_points": ["Self-attention mechanism", "Parallel processing", "Positional encoding"],
            "topics": ["AI", "NLP", "deep-learning"],
        })
        resp = await client.post(f"{BASE_URL}/listings", json={
            "title": "Summary: 'Attention Is All You Need' paper",
            "description": "Comprehensive summary of the seminal Transformer paper",
            "category": "document_summary",
            "content": doc_content,
            "price_usdc": 0.003,
            "tags": ["AI", "transformers", "paper-summary"],
            "quality_score": 0.88,
        }, headers={"Authorization": f"Bearer {doc_token}"})

        if resp.status_code == 201:
            data = resp.json()
            listings_created.append(data)
            step(f"doc_summarizer: Listed 'Attention Is All You Need' summary")
            info(f"Price: $0.003")

        print(f"\n  {BOLD}Listed {len(listings_created)} data items across 3 categories{RESET}")

        # ============ ACT 3: Buyer Discovers and Purchases ============
        banner("Act 3: Buyer Discovers and Purchases")

        buyer_token = agents.get("smart_buyer", {}).get("jwt_token", "")

        # Step 1: Search
        step("smart_buyer: Searching for 'Python async patterns'...")
        search_resp = await client.get(f"{BASE_URL}/discover", params={
            "q": "Python async",
            "category": "web_search",
            "sort_by": "freshness",
        })
        results = search_resp.json()
        info(f"Found {results['total']} matching listings")

        if results["results"]:
            listing = results["results"][0]
            info(f"Best match: '{listing['title']}' at ${listing['price_usdc']}")

            # Step 2: Initiate purchase
            step("smart_buyer: Initiating purchase...")
            init_resp = await client.post(f"{BASE_URL}/transactions/initiate", json={
                "listing_id": listing["id"],
            }, headers={"Authorization": f"Bearer {buyer_token}"})

            if init_resp.status_code == 201:
                tx_data = init_resp.json()
                tx_id = tx_data["transaction_id"]
                info(f"Transaction: {tx_id[:8]}... | Status: {tx_data['status']}")
                info(f"Amount: ${tx_data['amount_usdc']} USDC")

                # Step 3: Confirm payment (simulated)
                step("smart_buyer: Signing x402 payment...")
                pay_resp = await client.post(
                    f"{BASE_URL}/transactions/{tx_id}/confirm-payment",
                    json={"payment_signature": "", "payment_tx_hash": ""},
                    headers={"Authorization": f"Bearer {buyer_token}"},
                )
                pay_data = pay_resp.json()
                info(f"Payment confirmed | tx_hash: {pay_data.get('payment_tx_hash', 'N/A')[:20]}...")

                # Step 4: Seller delivers
                step("web_search_agent: Delivering content...")
                deliver_resp = await client.post(
                    f"{BASE_URL}/transactions/{tx_id}/deliver",
                    json={"content": json.dumps({
                        "query": "Python async patterns",
                        "results": [
                            {"title": "Top result for Python async patterns", "url": "https://example.com/Python-async-patterns"},
                            {"title": "Guide to Python async patterns", "url": "https://docs.example.com/Python-async-patterns"},
                        ],
                        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    })},
                    headers={"Authorization": f"Bearer {search_token}"},
                )
                deliver_data = deliver_resp.json()
                info(f"Content delivered ({deliver_data.get('delivered_hash', 'N/A')[:20]}...)")

                # Step 5: Buyer verifies
                step("smart_buyer: Verifying content hash...")
                verify_resp = await client.post(
                    f"{BASE_URL}/transactions/{tx_id}/verify",
                    json={},
                    headers={"Authorization": f"Bearer {buyer_token}"},
                )
                verify_data = verify_resp.json()

                if verify_data.get("verification_status") == "verified":
                    success(f"VERIFIED - Content hash matches!")
                    success(f"Transaction COMPLETED - ${tx_data['amount_usdc']} USDC")
                    fresh_cost = 0.01
                    savings = fresh_cost - tx_data["amount_usdc"]
                    success(f"Savings: ${savings:.4f} vs fresh computation (${fresh_cost})")
                else:
                    warn(f"Verification status: {verify_data.get('verification_status')}")
                    if verify_data.get("error_message"):
                        warn(f"Note: {verify_data['error_message']}")

        # ============ ACT 4: Marketplace Dashboard ============
        banner("Act 4: Marketplace Dashboard")

        # Health check
        health = await client.get(f"{BASE_URL}/health")
        h = health.json()
        step(f"Marketplace Stats:")
        info(f"Agents: {h['agents_count']} | Listings: {h['listings_count']} | Transactions: {h['transactions_count']}")

        # Agent reputation
        step("Agent Reputation Scores:")
        print(f"\n  {BOLD}{'Agent':<25} {'Txns':>6} {'Score':>8} {'Volume':>10}{RESET}")
        print(f"  {'-' * 55}")
        for name, data in agents.items():
            rep_resp = await client.get(
                f"{BASE_URL}/reputation/{data['id']}",
                params={"recalculate": "true"},
            )
            if rep_resp.status_code == 200:
                rep = rep_resp.json()
                print(f"  {name:<25} {rep['total_transactions']:>6} "
                      f"{rep['composite_score']:>8.3f} "
                      f"${rep['total_volume_usdc']:>9.4f}")

        # ============ Summary ============
        banner("Demo Complete!")
        print(f"  The Agent-to-Agent Data Marketplace is running at:")
        print(f"  {BOLD}http://localhost:8000{RESET}")
        print(f"  {BOLD}http://localhost:8000/docs{RESET} (Swagger UI)")
        print(f"\n  Try these endpoints:")
        print(f"  - GET  /api/v1/health          - Marketplace health")
        print(f"  - GET  /api/v1/agents          - List all agents")
        print(f"  - GET  /api/v1/listings         - Browse listings")
        print(f"  - GET  /api/v1/discover?q=python - Search data")
        print(f"  - GET  /api/v1/transactions     - View transactions")
        print()


if __name__ == "__main__":
    asyncio.run(demo())
