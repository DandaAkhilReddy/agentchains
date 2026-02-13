"""Standalone MCP server for AgentChains Marketplace.

Proxies 8 marketplace tools to the REST API via httpx.
Reads AGENTCHAINS_API_URL and AGENTCHAINS_JWT from environment.

Usage:
    python server.py              # stdio transport (default)
    mcporter install agentchains-mcp  # via OpenClaw's mcporter
"""

import asyncio
import json
import os
import sys
from typing import Any

import httpx

JSONRPC_VERSION = "2.0"

API_URL = os.environ.get(
    "AGENTCHAINS_API_URL",
    "http://localhost:8000",
)
JWT = os.environ.get("AGENTCHAINS_JWT", "")


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if JWT:
        h["Authorization"] = f"Bearer {JWT}"
    return h


TOOLS = [
    {
        "name": "marketplace_discover",
        "description": "Search for data listings on the AgentChains Marketplace",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "category": {"type": "string", "description": "Filter by category"},
                "page": {"type": "integer", "default": 1},
                "page_size": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "marketplace_express_buy",
        "description": "Buy a data listing instantly with ARD tokens",
        "inputSchema": {
            "type": "object",
            "properties": {
                "listing_id": {"type": "string", "description": "ID of the listing to buy"},
                "payment_method": {"type": "string", "enum": ["token", "fiat"], "default": "token"},
            },
            "required": ["listing_id"],
        },
    },
    {
        "name": "marketplace_sell",
        "description": "Create a new data listing for sale",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "category": {"type": "string"},
                "content_hash": {"type": "string"},
                "content_size": {"type": "integer"},
                "price_usdc": {"type": "number"},
                "description": {"type": "string"},
            },
            "required": ["title", "category", "content_hash", "content_size", "price_usdc"],
        },
    },
    {
        "name": "marketplace_auto_match",
        "description": "Find best matching listings for a data need",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "marketplace_register_catalog",
        "description": "Register your data production capabilities",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "category": {"type": "string"},
                "description": {"type": "string"},
                "capabilities": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "category"],
        },
    },
    {
        "name": "marketplace_trending",
        "description": "Get trending data categories and listings",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "marketplace_reputation",
        "description": "Get your agent reputation and statistics",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "marketplace_wallet_balance",
        "description": "Check your ARD token balance and tier",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


async def execute_tool(name: str, args: dict) -> Any:
    async with httpx.AsyncClient(base_url=API_URL, headers=_headers(), timeout=30) as client:
        if name == "marketplace_discover":
            params = {"q": args["query"], "page": args.get("page", 1), "page_size": args.get("page_size", 10)}
            if args.get("category"):
                params["category"] = args["category"]
            resp = await client.get("/api/v1/discover", params=params)
        elif name == "marketplace_express_buy":
            method = args.get("payment_method", "token")
            resp = await client.get(f"/api/v1/express/{args['listing_id']}", params={"payment_method": method})
        elif name == "marketplace_sell":
            resp = await client.post("/api/v1/listings", json=args)
        elif name == "marketplace_auto_match":
            resp = await client.post("/api/v1/agents/auto-match", json=args)
        elif name == "marketplace_register_catalog":
            resp = await client.post("/api/v1/catalog", json=args)
        elif name == "marketplace_trending":
            resp = await client.get("/api/v1/analytics/trending")
        elif name == "marketplace_reputation":
            resp = await client.get("/api/v1/analytics/my-stats")
        elif name == "marketplace_wallet_balance":
            resp = await client.get("/api/v1/wallet/balance")
        else:
            return {"error": f"Unknown tool: {name}"}

        if resp.status_code >= 400:
            return {"error": resp.text, "status_code": resp.status_code}
        return resp.json()


def send_response(id, result):
    msg = json.dumps({"jsonrpc": JSONRPC_VERSION, "id": id, "result": result})
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def send_error(id, code, message):
    msg = json.dumps({"jsonrpc": JSONRPC_VERSION, "id": id, "error": {"code": code, "message": message}})
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


async def handle_request(request: dict):
    method = request.get("method", "")
    id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        send_response(id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "agentchains-marketplace", "version": "1.0.0"},
        })
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        send_response(id, {"tools": TOOLS})
    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            result = await execute_tool(tool_name, tool_args)
            send_response(id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}],
            })
        except Exception as exc:
            send_response(id, {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "isError": True,
            })
    elif method == "ping":
        send_response(id, {})
    else:
        if id is not None:
            send_error(id, -32601, f"Method not found: {method}")


async def main():
    loop = asyncio.get_event_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            await handle_request(request)
        except json.JSONDecodeError:
            send_error(None, -32700, "Parse error")


if __name__ == "__main__":
    asyncio.run(main())
