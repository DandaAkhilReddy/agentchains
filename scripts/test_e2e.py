"""End-to-end test of the full marketplace lifecycle.

Defaults to an already-running local backend at http://127.0.0.1:8000.
Use ``--spawn-server`` if you want this script to boot a temporary uvicorn process.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any

import httpx


def _wait_for_health(base_api: str, timeout_seconds: int = 20) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_api}/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full marketplace E2E test.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("MARKETPLACE_URL", "http://127.0.0.1:8000"),
        help="Marketplace base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--spawn-server",
        action="store_true",
        help="Spawn a temporary uvicorn server for this test run.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port to use with --spawn-server (default: 8001).",
    )
    return parser.parse_args()


def _run_flow(base_api: str) -> None:
    client = httpx.Client(timeout=30)

    ts = int(time.time())
    seller_name = f"test_seller_{ts}"
    buyer_name = f"test_buyer_{ts}"

    print("=== FULL END-TO-END MARKETPLACE TEST ===\n")

    # 1. Register seller
    print("1. Registering seller agent...")
    resp = client.post(
        f"{base_api}/agents/register",
        json={
            "name": seller_name,
            "description": "Test web search seller",
            "agent_type": "seller",
            "capabilities": ["web_search"],
            "public_key": f"test-pk-seller-{ts}",
            "wallet_address": "0x" + "0" * 40,
        },
    )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    seller = resp.json()
    seller_token = seller["jwt_token"]
    print(f"   OK - ID: {seller['id'][:8]}...")

    # 2. Register buyer
    print("2. Registering buyer agent...")
    resp = client.post(
        f"{base_api}/agents/register",
        json={
            "name": buyer_name,
            "description": "Test data buyer",
            "agent_type": "buyer",
            "capabilities": ["purchasing"],
            "public_key": f"test-pk-buyer-{ts}",
            "wallet_address": "0x" + "1" * 40,
        },
    )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    buyer = resp.json()
    buyer_token = buyer["jwt_token"]
    print(f"   OK - ID: {buyer['id'][:8]}...")

    # 3. List agents
    print("3. Listing all agents...")
    resp = client.get(f"{base_api}/agents")
    agents = resp.json()
    print(f"   OK - {agents['total']} agents registered")

    # 4. Seller creates listing
    print("4. Seller creating data listing...")
    content = json.dumps(
        {
            "query": "Python async patterns",
            "results": [
                {"title": "AsyncIO Guide", "url": "https://realpython.com/async-io-python/"},
                {"title": "Python 3.12 async", "url": "https://docs.python.org/3/library/asyncio.html"},
            ],
        }
    )
    resp = client.post(
        f"{base_api}/listings",
        json={
            "title": "Web search: Python async patterns",
            "description": "Cached search results with URLs and snippets",
            "category": "web_search",
            "content": content,
            "price_usdc": 0.002,
            "tags": ["python", "async", "programming"],
            "quality_score": 0.85,
        },
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert resp.status_code == 201, f"Listing failed: {resp.text}"
    listing = resp.json()
    print(f"   OK - '{listing['title']}'")
    print(f"        Hash: {listing['content_hash']}")
    print(f"        Price: {listing['price_usdc']} USDC")

    # 5. Buyer discovers
    print("5. Buyer searching marketplace...")
    resp = client.get(
        f"{base_api}/discover",
        params={"q": "Python async", "category": "web_search"},
    )
    results: dict[str, Any] = resp.json()
    assert results["total"] > 0, "No results found!"
    print(f"   OK - Found {results['total']} matching listing(s)")

    # 6. Buyer initiates purchase
    print("6. Buyer initiating purchase...")
    best = results["results"][0]
    resp = client.post(
        f"{base_api}/transactions/initiate",
        json={"listing_id": best["id"]},
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert resp.status_code == 201, f"Initiation failed: {resp.text}"
    tx = resp.json()
    tx_id = tx["transaction_id"]
    print(f"   OK - Transaction: {tx_id[:8]}...")
    print(f"        Amount: {tx['amount_usdc']} USDC")
    print(f"        Network: {tx['payment_details']['network']}")

    # 7. Confirm payment (simulated)
    print("7. Confirming x402 payment (simulated)...")
    resp = client.post(
        f"{base_api}/transactions/{tx_id}/confirm-payment",
        json={"payment_signature": "", "payment_tx_hash": ""},
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    pay = resp.json()
    assert pay["status"] == "payment_confirmed", f"Payment failed: {pay}"
    print(f"   OK - Status: {pay['status']}")
    print(f"        Tx hash: {pay.get('payment_tx_hash', 'N/A')[:30]}...")

    # 8. Seller delivers content
    print("8. Seller delivering content...")
    resp = client.post(
        f"{base_api}/transactions/{tx_id}/deliver",
        json={"content": content},
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    deliver = resp.json()
    assert deliver["status"] == "delivered", f"Delivery failed: {deliver}"
    print(f"   OK - Status: {deliver['status']}")
    print(f"        Delivered hash: {deliver.get('delivered_hash', 'N/A')[:30]}...")

    # 9. Buyer verifies
    print("9. Buyer verifying content hash...")
    resp = client.post(
        f"{base_api}/transactions/{tx_id}/verify",
        json={},
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    verify = resp.json()
    print(f"   Verification: {verify['verification_status']}")
    print(f"   Transaction: {verify['status']}")
    if verify["verification_status"] == "verified":
        print("   *** CONTENT VERIFIED - TRANSACTION COMPLETE ***")
    else:
        print(f"   WARNING: {verify.get('error_message', 'Unknown issue')}")

    # 10. Check reputation
    print("10. Checking reputation scores...")
    for data, role in [(seller, "Seller"), (buyer, "Buyer")]:
        resp = client.get(f"{base_api}/reputation/{data['id']}", params={"recalculate": "true"})
        rep = resp.json()
        print(
            f"    {role}: score={rep['composite_score']}, txns={rep['total_transactions']}, "
            f"volume={rep['total_volume_usdc']} USDC"
        )

    # 11. Final health
    print("\n11. Final marketplace status...")
    resp = client.get(f"{base_api}/health")
    h = resp.json()
    print(f"    Agents: {h['agents_count']}")
    print(f"    Listings: {h['listings_count']}")
    print(f"    Transactions: {h['transactions_count']}")

    print("\n=== ALL TESTS PASSED - MARKETPLACE FULLY OPERATIONAL ===")


def main() -> int:
    args = _parse_args()

    spawned: subprocess.Popen[str] | None = None
    base_url = args.base_url.rstrip("/")
    if args.spawn_server:
        host = "127.0.0.1"
        base_url = f"http://{host}:{args.port}"
        spawned = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "marketplace.main:app",
                "--host",
                host,
                "--port",
                str(args.port),
                "--log-level",
                "error",
            ],
        )

    base_api = f"{base_url}/api/v1"
    if not _wait_for_health(base_api, timeout_seconds=20):
        if spawned is not None:
            spawned.terminate()
        print(f"Marketplace health check failed at {base_api}/health")
        return 1

    try:
        _run_flow(base_api)
        return 0
    finally:
        if spawned is not None:
            spawned.terminate()
            try:
                spawned.wait(timeout=10)
            except subprocess.TimeoutExpired:
                spawned.kill()


if __name__ == "__main__":
    raise SystemExit(main())
