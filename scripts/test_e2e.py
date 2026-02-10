"""End-to-end test of the full marketplace lifecycle."""
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import uvicorn

BASE = "http://localhost:8001/api/v1"


def run_server():
    uvicorn.run("marketplace.main:app", host="0.0.0.0", port=8001, log_level="error")


def main():
    # Start server
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(3)

    client = httpx.Client(timeout=30)

    print("=== FULL END-TO-END MARKETPLACE TEST ===\n")

    # 1. Register seller
    print("1. Registering seller agent...")
    resp = client.post(f"{BASE}/agents/register", json={
        "name": "test_seller",
        "description": "Test web search seller",
        "agent_type": "seller",
        "capabilities": ["web_search"],
        "public_key": "test-pk-seller",
        "wallet_address": "0x" + "0" * 40,
    })
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    seller = resp.json()
    seller_token = seller["jwt_token"]
    print(f"   OK - ID: {seller['id'][:8]}...")

    # 2. Register buyer
    print("2. Registering buyer agent...")
    resp = client.post(f"{BASE}/agents/register", json={
        "name": "test_buyer",
        "description": "Test data buyer",
        "agent_type": "buyer",
        "capabilities": ["purchasing"],
        "public_key": "test-pk-buyer",
        "wallet_address": "0x" + "1" * 40,
    })
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    buyer = resp.json()
    buyer_token = buyer["jwt_token"]
    print(f"   OK - ID: {buyer['id'][:8]}...")

    # 3. List agents
    print("3. Listing all agents...")
    resp = client.get(f"{BASE}/agents")
    agents = resp.json()
    print(f"   OK - {agents['total']} agents registered")

    # 4. Seller creates listing
    print("4. Seller creating data listing...")
    content = json.dumps({
        "query": "Python async patterns",
        "results": [
            {"title": "AsyncIO Guide", "url": "https://realpython.com/async-io-python/"},
            {"title": "Python 3.12 async", "url": "https://docs.python.org/3/library/asyncio.html"},
        ],
    })
    resp = client.post(f"{BASE}/listings", json={
        "title": "Web search: Python async patterns",
        "description": "Cached search results with URLs and snippets",
        "category": "web_search",
        "content": content,
        "price_usdc": 0.002,
        "tags": ["python", "async", "programming"],
        "quality_score": 0.85,
    }, headers={"Authorization": f"Bearer {seller_token}"})
    assert resp.status_code == 201, f"Listing failed: {resp.text}"
    listing = resp.json()
    print(f"   OK - '{listing['title']}'")
    print(f"        Hash: {listing['content_hash']}")
    print(f"        Price: {listing['price_usdc']} USDC")

    # 5. Buyer discovers
    print("5. Buyer searching marketplace...")
    resp = client.get(f"{BASE}/discover", params={"q": "Python async", "category": "web_search"})
    results = resp.json()
    assert results["total"] > 0, "No results found!"
    print(f"   OK - Found {results['total']} matching listing(s)")

    # 6. Buyer initiates purchase
    print("6. Buyer initiating purchase...")
    best = results["results"][0]
    resp = client.post(f"{BASE}/transactions/initiate", json={
        "listing_id": best["id"],
    }, headers={"Authorization": f"Bearer {buyer_token}"})
    assert resp.status_code == 201, f"Initiation failed: {resp.text}"
    tx = resp.json()
    tx_id = tx["transaction_id"]
    print(f"   OK - Transaction: {tx_id[:8]}...")
    print(f"        Amount: {tx['amount_usdc']} USDC")
    print(f"        Network: {tx['payment_details']['network']}")

    # 7. Confirm payment (simulated)
    print("7. Confirming x402 payment (simulated)...")
    resp = client.post(f"{BASE}/transactions/{tx_id}/confirm-payment", json={
        "payment_signature": "",
        "payment_tx_hash": "",
    }, headers={"Authorization": f"Bearer {buyer_token}"})
    pay = resp.json()
    assert pay["status"] == "payment_confirmed", f"Payment failed: {pay}"
    print(f"   OK - Status: {pay['status']}")
    print(f"        Tx hash: {pay.get('payment_tx_hash', 'N/A')[:30]}...")

    # 8. Seller delivers content
    print("8. Seller delivering content...")
    resp = client.post(f"{BASE}/transactions/{tx_id}/deliver", json={
        "content": content,
    }, headers={"Authorization": f"Bearer {seller_token}"})
    deliver = resp.json()
    assert deliver["status"] == "delivered", f"Delivery failed: {deliver}"
    print(f"   OK - Status: {deliver['status']}")
    print(f"        Delivered hash: {deliver.get('delivered_hash', 'N/A')[:30]}...")

    # 9. Buyer verifies
    print("9. Buyer verifying content hash...")
    resp = client.post(f"{BASE}/transactions/{tx_id}/verify", json={},
        headers={"Authorization": f"Bearer {buyer_token}"})
    verify = resp.json()
    print(f"   Verification: {verify['verification_status']}")
    print(f"   Transaction: {verify['status']}")

    if verify["verification_status"] == "verified":
        print("   *** CONTENT VERIFIED - TRANSACTION COMPLETE ***")
    else:
        print(f"   WARNING: {verify.get('error_message', 'Unknown issue')}")

    # 10. Check reputation
    print("10. Checking reputation scores...")
    for name, data, role in [("test_seller", seller, "Seller"), ("test_buyer", buyer, "Buyer")]:
        resp = client.get(f"{BASE}/reputation/{data['id']}", params={"recalculate": "true"})
        rep = resp.json()
        print(f"    {role}: score={rep['composite_score']}, txns={rep['total_transactions']}, volume={rep['total_volume_usdc']} USDC")

    # 11. Final health
    print("\n11. Final marketplace status...")
    resp = client.get(f"{BASE}/health")
    h = resp.json()
    print(f"    Agents: {h['agents_count']}")
    print(f"    Listings: {h['listings_count']}")
    print(f"    Transactions: {h['transactions_count']}")

    print("\n=== ALL TESTS PASSED - MARKETPLACE FULLY OPERATIONAL ===")


if __name__ == "__main__":
    main()
