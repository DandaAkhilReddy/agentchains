"""Performance benchmarks for AgentChains API.

Measures request throughput and latency for key endpoints.
Usage: python scripts/benchmark.py [--host HOST] [--requests N] [--concurrent C]
"""

import argparse
import asyncio
import json
import statistics
import time
from datetime import datetime, timezone

import httpx


async def benchmark_endpoint(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    body: dict | None = None,
    headers: dict | None = None,
    num_requests: int = 100,
    concurrency: int = 10,
) -> dict:
    """Benchmark a single endpoint."""
    latencies: list[float] = []
    errors = 0
    semaphore = asyncio.Semaphore(concurrency)

    async def _request():
        nonlocal errors
        async with semaphore:
            start = time.perf_counter()
            try:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                elif method == "POST":
                    resp = await client.post(url, json=body, headers=headers)
                else:
                    resp = await client.request(method, url, json=body, headers=headers)
                elapsed = (time.perf_counter() - start) * 1000
                if resp.status_code >= 400:
                    errors += 1
                latencies.append(elapsed)
            except Exception:
                errors += 1
                latencies.append((time.perf_counter() - start) * 1000)

    tasks = [_request() for _ in range(num_requests)]
    wall_start = time.perf_counter()
    await asyncio.gather(*tasks)
    wall_elapsed = time.perf_counter() - wall_start

    return {
        "endpoint": f"{method} {url}",
        "requests": num_requests,
        "concurrency": concurrency,
        "wall_time_s": round(wall_elapsed, 3),
        "rps": round(num_requests / wall_elapsed, 1),
        "latency_ms": {
            "min": round(min(latencies), 1) if latencies else 0,
            "max": round(max(latencies), 1) if latencies else 0,
            "mean": round(statistics.mean(latencies), 1) if latencies else 0,
            "median": round(statistics.median(latencies), 1) if latencies else 0,
            "p95": round(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 1),
            "p99": round(sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0, 1),
        },
        "errors": errors,
        "error_rate": round(errors / num_requests * 100, 1) if num_requests else 0,
    }


async def run_benchmarks(host: str, num_requests: int, concurrency: int) -> list[dict]:
    """Run benchmarks against all key endpoints."""
    results = []

    async with httpx.AsyncClient(base_url=host, timeout=30.0) as client:
        # 1. Health check
        r = await benchmark_endpoint(
            client, "GET", "/api/v1/health",
            num_requests=num_requests, concurrency=concurrency,
        )
        results.append(r)

        # 2. Register a test agent
        agent_data = {
            "name": f"bench-agent-{int(time.time())}",
            "capabilities": ["benchmark"],
        }
        resp = await client.post("/api/v1/agents", json=agent_data)
        token = None
        if resp.status_code == 200:
            token = resp.json().get("token")

        auth = {"Authorization": f"Bearer {token}"} if token else {}

        # 3. Catalog browsing
        r = await benchmark_endpoint(
            client, "GET", "/api/v1/catalog",
            num_requests=num_requests, concurrency=concurrency,
        )
        results.append(r)

        # 4. Agent search
        r = await benchmark_endpoint(
            client, "GET", "/api/v1/agents/search?q=test",
            headers=auth,
            num_requests=num_requests, concurrency=concurrency,
        )
        results.append(r)

        # 5. WebMCP tool discovery
        r = await benchmark_endpoint(
            client, "GET", "/api/v3/webmcp/tools",
            num_requests=num_requests, concurrency=concurrency,
        )
        results.append(r)

        # 6. Action listings
        r = await benchmark_endpoint(
            client, "GET", "/api/v3/webmcp/actions",
            num_requests=num_requests, concurrency=concurrency,
        )
        results.append(r)

        # 7. MCP health
        r = await benchmark_endpoint(
            client, "GET", "/mcp/health",
            num_requests=num_requests, concurrency=concurrency,
        )
        results.append(r)

    return results


def print_results(results: list[dict]) -> None:
    """Print benchmark results as a formatted table."""
    print("\n" + "=" * 90)
    print(f"AgentChains Performance Benchmark — {datetime.now(timezone.utc).isoformat()}")
    print("=" * 90)
    print(f"{'Endpoint':<35} {'RPS':>8} {'Mean':>8} {'P95':>8} {'P99':>8} {'Errors':>8}")
    print("-" * 90)
    for r in results:
        endpoint = r["endpoint"][:35]
        print(
            f"{endpoint:<35} "
            f"{r['rps']:>7.1f} "
            f"{r['latency_ms']['mean']:>7.1f} "
            f"{r['latency_ms']['p95']:>7.1f} "
            f"{r['latency_ms']['p99']:>7.1f} "
            f"{r['errors']:>7d}"
        )
    print("-" * 90)
    total_rps = sum(r["rps"] for r in results) / len(results) if results else 0
    print(f"{'Average':.<35} {total_rps:>7.1f}")
    print("=" * 90)


def main():
    parser = argparse.ArgumentParser(description="AgentChains Performance Benchmarks")
    parser.add_argument("--host", default="http://localhost:8000", help="Server URL")
    parser.add_argument("--requests", type=int, default=100, help="Requests per endpoint")
    parser.add_argument("--concurrent", type=int, default=10, help="Concurrent requests")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print(f"Benchmarking {args.host} — {args.requests} requests, {args.concurrent} concurrent")
    results = asyncio.run(run_benchmarks(args.host, args.requests, args.concurrent))

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results(results)


if __name__ == "__main__":
    main()
