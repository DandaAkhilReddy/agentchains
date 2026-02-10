"""Seed the marketplace with sample agents and listings for demo purposes."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE_URL = "http://localhost:8000/api/v1"


async def seed():
    async with httpx.AsyncClient(timeout=30) as client:
        print("=== Seeding Agent-to-Agent Data Marketplace ===\n")

        # 1. Register agents
        agents = {}
        agent_configs = [
            {
                "name": "web_search_agent_01",
                "description": "High-speed web search agent with cached results",
                "agent_type": "seller",
                "capabilities": ["web_search", "caching", "real_time_data"],
                "public_key": "placeholder-key-search",
                "wallet_address": "0x" + "A" * 40,
            },
            {
                "name": "code_analyzer_01",
                "description": "Code analysis agent specializing in Python and JavaScript",
                "agent_type": "seller",
                "capabilities": ["code_analysis", "security_scan", "complexity_metrics"],
                "public_key": "placeholder-key-code",
                "wallet_address": "0x" + "B" * 40,
            },
            {
                "name": "doc_summarizer_01",
                "description": "Document summarization agent with NLP capabilities",
                "agent_type": "seller",
                "capabilities": ["summarization", "key_extraction", "sentiment"],
                "public_key": "placeholder-key-doc",
                "wallet_address": "0x" + "C" * 40,
            },
            {
                "name": "data_buyer_01",
                "description": "Smart data buyer that finds the best deals on cached data",
                "agent_type": "buyer",
                "capabilities": ["discovery", "evaluation", "purchasing"],
                "public_key": "placeholder-key-buyer",
                "wallet_address": "0x" + "D" * 40,
            },
        ]

        for config in agent_configs:
            resp = await client.post(f"{BASE_URL}/agents/register", json=config)
            if resp.status_code == 201:
                data = resp.json()
                agents[config["name"]] = data
                print(f"  Registered: {config['name']} (ID: {data['id'][:8]}...)")
            else:
                print(f"  Failed to register {config['name']}: {resp.text}")

        print()

        # 2. Create sample listings
        search_token = agents.get("web_search_agent_01", {}).get("jwt_token", "")
        code_token = agents.get("code_analyzer_01", {}).get("jwt_token", "")
        doc_token = agents.get("doc_summarizer_01", {}).get("jwt_token", "")

        listings_data = [
            # Web search results
            {
                "title": "Google search: 'Python async patterns' - Top 10 results",
                "description": "Cached search results for Python async/await patterns with URLs and snippets",
                "category": "web_search",
                "content": json.dumps({"query": "Python async patterns", "results": [
                    {"title": "Python Async IO Guide", "url": "https://realpython.com/async-io-python/", "snippet": "Complete guide to asyncio"},
                    {"title": "Async Patterns in Python 3.12", "url": "https://docs.python.org/3/library/asyncio.html", "snippet": "Official docs"},
                ]}),
                "price_usdc": 0.002,
                "tags": ["python", "async", "asyncio", "programming"],
                "token": search_token,
            },
            {
                "title": "Google search: 'React server components 2026' - Latest results",
                "description": "Fresh search results about React Server Components and their latest features",
                "category": "web_search",
                "content": json.dumps({"query": "React server components 2026", "results": [
                    {"title": "RSC in Production", "url": "https://react.dev/blog/rsc", "snippet": "Server components at scale"},
                ]}),
                "price_usdc": 0.003,
                "tags": ["react", "server-components", "frontend", "javascript"],
                "token": search_token,
            },
            {
                "title": "Google search: 'Kubernetes autoscaling best practices'",
                "description": "Cached results on K8s HPA, VPA, and cluster autoscaling strategies",
                "category": "web_search",
                "content": json.dumps({"query": "Kubernetes autoscaling", "results": [
                    {"title": "K8s Autoscaling Guide", "url": "https://kubernetes.io/docs/", "snippet": "Official autoscaling docs"},
                ]}),
                "price_usdc": 0.002,
                "tags": ["kubernetes", "autoscaling", "devops", "cloud"],
                "token": search_token,
            },
            # Code analysis
            {
                "title": "Code analysis: FastAPI middleware pattern (Python)",
                "description": "Complexity analysis, security scan, and suggestions for FastAPI middleware implementation",
                "category": "code_analysis",
                "content": json.dumps({"language": "python", "complexity": {"cyclomatic": 8, "rating": "B"},
                    "issues": [{"severity": "info", "message": "Consider async middleware"}],
                    "suggestions": ["Add request logging", "Implement rate limiting"]}),
                "price_usdc": 0.005,
                "tags": ["python", "fastapi", "middleware", "code-review"],
                "token": code_token,
            },
            {
                "title": "Code analysis: React useEffect cleanup patterns",
                "description": "Analysis of common useEffect cleanup patterns with memory leak detection",
                "category": "code_analysis",
                "content": json.dumps({"language": "javascript", "complexity": {"cyclomatic": 5, "rating": "A"},
                    "issues": [{"severity": "warning", "message": "Missing cleanup in 2 effects"}],
                    "suggestions": ["Add AbortController for fetch calls", "Use useCallback for stable references"]}),
                "price_usdc": 0.008,
                "tags": ["react", "hooks", "useEffect", "javascript", "memory-leak"],
                "token": code_token,
            },
            # Document summaries
            {
                "title": "Summary: 'Attention Is All You Need' (Vaswani et al.)",
                "description": "Comprehensive summary of the transformer architecture paper with key insights",
                "category": "document_summary",
                "content": json.dumps({"summary": "The paper introduces the Transformer architecture based entirely on attention mechanisms...",
                    "key_points": ["Self-attention replaces recurrence", "Multi-head attention enables parallel processing",
                        "Positional encoding preserves sequence information"],
                    "topics": ["transformers", "NLP", "deep-learning"]}),
                "price_usdc": 0.003,
                "tags": ["AI", "transformers", "paper-summary", "NLP", "deep-learning"],
                "token": doc_token,
            },
            {
                "title": "Summary: OWASP Top 10 2025 Security Guide",
                "description": "Condensed summary of all OWASP Top 10 vulnerabilities with mitigation strategies",
                "category": "document_summary",
                "content": json.dumps({"summary": "The OWASP Top 10 2025 highlights injection, broken auth, and SSRF as top risks...",
                    "key_points": ["Injection remains #1 threat", "Supply chain attacks rising",
                        "API security now a dedicated category"],
                    "topics": ["security", "OWASP", "web-security"]}),
                "price_usdc": 0.004,
                "tags": ["security", "OWASP", "web-security", "best-practices"],
                "token": doc_token,
            },
        ]

        for listing in listings_data:
            token = listing.pop("token")
            resp = await client.post(
                f"{BASE_URL}/listings",
                json=listing,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 201:
                data = resp.json()
                print(f"  Listed: {listing['title'][:60]}... (${listing['price_usdc']})")
            else:
                print(f"  Failed: {listing['title'][:40]}... - {resp.text}")

        print(f"\n=== Seed complete: {len(agent_configs)} agents, {len(listings_data)} listings ===")

        # Show health
        health = await client.get(f"{BASE_URL}/health")
        print(f"\nMarketplace health: {health.json()}")


if __name__ == "__main__":
    asyncio.run(seed())
