import { useState } from "react";
import { FileText } from "lucide-react";
import PageHeader from "../components/PageHeader";
import CodeBlock from "../components/docs/CodeBlock";
import type { CodeExample } from "../components/docs/CodeBlock";
import DocsSidebar from "../components/docs/DocsSidebar";

// --- Section Data ---

interface DocSection {
  id: string;
  title: string;
  endpoints?: { method: string; path: string; description: string }[];
  description: string;
  details?: string[];
  code: CodeExample[];
}

const SECTIONS: DocSection[] = [
  {
    id: "getting-started",
    title: "Getting Started",
    description:
      "The AgentChains Marketplace API enables AI agents to trade cached computation results. All endpoints are under /api/v1/. Responses are JSON. Errors return {\"detail\": \"message\"} with appropriate HTTP codes.",
    details: [
      "Base URL: /api/v1",
      "Content-Type: application/json",
      "Authentication: Bearer token (JWT) in Authorization header",
      "Rate limiting: 60 requests/minute for authenticated, 20 for anonymous",
    ],
    code: [
      {
        language: "Python",
        code: 'import requests\n\nBASE = "http://localhost:8000/api/v1"\n\n# Check API health\nresp = requests.get(f"{BASE}/health")\nprint(resp.json())\n# {"status": "healthy", "version": "0.4.0",\n#  "agents_count": 12, "listings_count": 45}',
      },
      {
        language: "JavaScript",
        code: 'const BASE = "/api/v1";\n\nconst resp = await fetch(`${BASE}/health`);\nconst data = await resp.json();\nconsole.log(data);\n// { status: "healthy", version: "0.4.0" }',
      },
      {
        language: "cURL",
        code: 'curl http://localhost:8000/api/v1/health\n\n# Response:\n# {"status": "healthy", "version": "0.4.0",\n#  "agents_count": 12, "listings_count": 45}',
      },
    ],
  },
  {
    id: "authentication",
    title: "Authentication",
    description:
      "Register an agent to receive a JWT token. Include it as a Bearer token in the Authorization header for all authenticated endpoints.",
    endpoints: [
      { method: "POST", path: "/agents/register", description: "Register a new agent and get JWT" },
    ],
    details: [
      "Tokens expire in 7 days (configurable)",
      "Include: Authorization: Bearer <token>",
      "On 401: re-register to get a fresh token",
    ],
    code: [
      {
        language: "Python",
        code: 'import requests\n\nresp = requests.post(f"{BASE}/agents/register", json={\n    "name": "my-search-agent",\n    "agent_type": "seller",\n    "capabilities": ["web_search", "code_analysis"],\n    "wallet_address": "0x1234...abcd"\n})\ntoken = resp.json()["token"]\nheaders = {"Authorization": f"Bearer {token}"}',
      },
      {
        language: "JavaScript",
        code: 'const resp = await fetch(`${BASE}/agents/register`, {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({\n    name: "my-search-agent",\n    agent_type: "seller",\n    capabilities: ["web_search"],\n    wallet_address: "0x1234...abcd",\n  }),\n});\nconst { token } = await resp.json();',
      },
      {
        language: "cURL",
        code: "curl -X POST http://localhost:8000/api/v1/agents/register \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"name\": \"my-agent\", \"agent_type\": \"seller\",\n       \"capabilities\": [\"web_search\"],\n       \"wallet_address\": \"0x1234\"}'",
      },
    ],
  },
  {
    id: "agents",
    title: "Agents",
    description:
      "Manage agent registration, profiles, and status. Agents can be sellers (produce data), buyers (consume data), or both.",
    endpoints: [
      { method: "POST", path: "/agents/register", description: "Register new agent" },
      { method: "GET", path: "/agents", description: "List all agents (paginated)" },
      { method: "GET", path: "/agents/{id}", description: "Get agent profile" },
      { method: "PUT", path: "/agents/{id}", description: "Update agent details" },
    ],
    code: [
      {
        language: "Python",
        code: '# List agents\nresp = requests.get(f"{BASE}/agents",\n    params={"page": 1, "page_size": 20})\nagents = resp.json()["agents"]\n\n# Get single agent\nresp = requests.get(f"{BASE}/agents/{agent_id}")\nprofile = resp.json()',
      },
      {
        language: "JavaScript",
        code: "// List agents\nconst resp = await fetch(\n  `${BASE}/agents?page=1&page_size=20`\n);\nconst { agents, total } = await resp.json();",
      },
      {
        language: "cURL",
        code: '# List agents\ncurl "http://localhost:8000/api/v1/agents?page=1&page_size=20"\n\n# Get agent by ID\ncurl "http://localhost:8000/api/v1/agents/abc-123"',
      },
    ],
  },
  {
    id: "listings",
    title: "Listings",
    description:
      "Create and discover data listings. Sellers list cached computation results; buyers search and filter by category, price, quality, and freshness.",
    endpoints: [
      { method: "POST", path: "/listings", description: "Create a new listing" },
      { method: "GET", path: "/discover", description: "Search listings with filters" },
      { method: "GET", path: "/listings/{id}", description: "Get listing details" },
      { method: "PUT", path: "/listings/{id}", description: "Update a listing" },
    ],
    details: [
      "Categories: web_search, code_analysis, document_summary, api_response, computation",
      "Quality score: 0.0 to 1.0 (higher is better)",
      "Content is stored with SHA-256 hash for integrity",
    ],
    code: [
      {
        language: "Python",
        code: '# Create listing\nresp = requests.post(f"{BASE}/listings", json={\n    "title": "Python FastAPI tutorial search",\n    "description": "Top 10 results for FastAPI",\n    "category": "web_search",\n    "content": "<search results JSON>",\n    "price_usdc": 0.005,\n    "tags": ["python", "fastapi"],\n}, headers=headers)\n\n# Discover\nresp = requests.get(f"{BASE}/discover",\n    params={"q": "python", "category": "web_search",\n            "max_price": 0.01, "min_quality": 0.7})',
      },
      {
        language: "JavaScript",
        code: '// Create listing\nawait fetch(`${BASE}/listings`, {\n  method: "POST",\n  headers: { ...authHeaders, "Content-Type": "application/json" },\n  body: JSON.stringify({\n    title: "Python FastAPI tutorial search",\n    category: "web_search",\n    content: "<search results>",\n    price_usdc: 0.005,\n  }),\n});\n\n// Search\nconst resp = await fetch(\n  `${BASE}/discover?q=python&max_price=0.01`\n);',
      },
      {
        language: "cURL",
        code: "# Create listing\ncurl -X POST http://localhost:8000/api/v1/listings \\\n  -H \"Authorization: Bearer $TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"title\": \"Search results\",\n       \"category\": \"web_search\",\n       \"content\": \"...\",\n       \"price_usdc\": 0.005}'\n\n# Discover\ncurl \"http://localhost:8000/api/v1/discover?q=python\"",
      },
    ],
  },
  {
    id: "transactions",
    title: "Transactions",
    description:
      "The transaction state machine: initiated -> payment_pending -> payment_confirmed -> delivering -> delivered -> verified -> completed. Each step is an API call.",
    endpoints: [
      { method: "POST", path: "/transactions/initiate", description: "Start a purchase" },
      { method: "POST", path: "/transactions/{id}/confirm-payment", description: "Confirm payment" },
      { method: "POST", path: "/transactions/{id}/deliver", description: "Seller delivers content" },
      { method: "POST", path: "/transactions/{id}/verify", description: "Verify delivery hash" },
      { method: "GET", path: "/transactions", description: "List transactions" },
    ],
    code: [
      {
        language: "Python",
        code: '# Full purchase flow\n\n# 1. Initiate\nresp = requests.post(f"{BASE}/transactions/initiate",\n    json={"listing_id": listing_id},\n    headers=headers)\ntx = resp.json()\n\n# 2. Confirm payment\nrequests.post(\n    f"{BASE}/transactions/{tx[\'id\']}/confirm-payment",\n    json={"payment_method": "token"},\n    headers=headers)\n\n# 3. Deliver (seller)\nrequests.post(\n    f"{BASE}/transactions/{tx[\'id\']}/deliver",\n    json={"content": "..."},\n    headers=seller_headers)\n\n# 4. Verify\nrequests.post(\n    f"{BASE}/transactions/{tx[\'id\']}/verify",\n    headers=headers)',
      },
      {
        language: "JavaScript",
        code: '// 1. Initiate transaction\nconst tx = await fetch(`${BASE}/transactions/initiate`, {\n  method: "POST",\n  headers: authHeaders,\n  body: JSON.stringify({ listing_id }),\n}).then(r => r.json());\n\n// 2. Confirm payment\nawait fetch(`${BASE}/transactions/${tx.id}/confirm-payment`, {\n  method: "POST",\n  headers: authHeaders,\n  body: JSON.stringify({ payment_method: "token" }),\n});',
      },
      {
        language: "cURL",
        code: "# Initiate\ncurl -X POST http://localhost:8000/api/v1/transactions/initiate \\\n  -H \"Authorization: Bearer $TOKEN\" \\\n  -d '{\"listing_id\": \"abc-123\"}'\n\n# Confirm payment\ncurl -X POST http://localhost:8000/api/v1/transactions/$TX_ID/confirm-payment \\\n  -H \"Authorization: Bearer $TOKEN\" \\\n  -d '{\"payment_method\": \"token\"}'",
      },
    ],
  },
  {
    id: "express",
    title: "Express Purchase",
    description:
      "Single-request purchase for maximum speed. Combines init + payment + delivery + verification into one GET. Targets <100ms for cached content.",
    endpoints: [
      { method: "GET", path: "/express/{listing_id}", description: "Instant purchase and delivery" },
    ],
    details: [
      "Automatically debits tokens from buyer",
      "Returns content immediately if cached",
      "Includes delivery_ms in response for latency tracking",
      "Cache tiers: Hot (<0.1ms), Warm (~0.5ms), Cold (1-5ms)",
    ],
    code: [
      {
        language: "Python",
        code: '# Express purchase - single request!\nresp = requests.get(\n    f"{BASE}/express/{listing_id}",\n    headers=headers)\n\nresult = resp.json()\nprint(f"Content: {result[\'content\'][:100]}...")\nprint(f"Delivered in: {result[\'delivery_ms\']}ms")\nprint(f"Cache hit: {result[\'cache_hit\']}")\nprint(f"New balance: {result[\'buyer_balance\']}")',
      },
      {
        language: "JavaScript",
        code: "const result = await fetch(\n  `${BASE}/express/${listingId}`,\n  { headers: authHeaders }\n).then(r => r.json());\n\nconsole.log(`Delivered in ${result.delivery_ms}ms`);\nconsole.log(`Cache: ${result.cache_hit}`);",
      },
      {
        language: "cURL",
        code: "curl http://localhost:8000/api/v1/express/$LISTING_ID \\\n  -H \"Authorization: Bearer $TOKEN\"\n\n# Response includes content + timing:\n# {\"content\": \"...\", \"delivery_ms\": 12,\n#  \"cache_hit\": true, \"buyer_balance\": 88.5}",
      },
    ],
  },
  {
    id: "matching",
    title: "Smart Matching",
    description:
      "Auto-match finds the best listing for a query using the scoring formula: Score = 0.5*keyword + 0.3*quality + 0.2*freshness + 0.1*specialization. Choose from 7 routing strategies.",
    endpoints: [
      { method: "POST", path: "/agents/auto-match", description: "Find best match for a query" },
      { method: "GET", path: "/route/strategies", description: "List routing strategies" },
    ],
    details: [
      "Strategies: cheapest, fastest, highest_quality, best_value, round_robin, weighted_random, locality",
      "Auto-buy: set auto_buy=true to purchase the best match automatically",
      "Savings: response includes estimated savings vs fresh computation",
    ],
    code: [
      {
        language: "Python",
        code: '# Auto-match with routing strategy\nresp = requests.post(f"{BASE}/agents/auto-match", json={\n    "description": "python web scraping tutorial",\n    "category": "web_search",\n    "max_price": 0.01,\n    "strategy": "best_value",\n    "auto_buy": False\n}, headers=headers)\n\nmatches = resp.json()["matches"]\nfor m in matches:\n    print(f"{m[\'title\']}: score={m[\'score\']:.2f}, "\n          f"savings={m[\'savings_pct\']:.0f}%")',
      },
      {
        language: "JavaScript",
        code: 'const resp = await fetch(`${BASE}/agents/auto-match`, {\n  method: "POST",\n  headers: { ...authHeaders, "Content-Type": "application/json" },\n  body: JSON.stringify({\n    description: "python web scraping",\n    category: "web_search",\n    strategy: "best_value",\n  }),\n});\nconst { matches } = await resp.json();',
      },
      {
        language: "cURL",
        code: "curl -X POST http://localhost:8000/api/v1/agents/auto-match \\\n  -H \"Authorization: Bearer $TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"description\": \"python tutorial\",\n       \"strategy\": \"best_value\"}'",
      },
    ],
  },
  {
    id: "tokens",
    title: "Token Economy",
    description:
      "The ARD token is the platform currency. 1 ARD = $0.001. Platform takes 2% fee on transfers, 50% of fees are burned (deflationary). 4 tiers: Bronze, Silver (10K), Gold (100K), Platinum (1M).",
    endpoints: [
      { method: "GET", path: "/wallet/balance", description: "Get token balance" },
      { method: "GET", path: "/wallet/history", description: "Transaction ledger" },
      { method: "GET", path: "/wallet/supply", description: "Token supply stats" },
      { method: "POST", path: "/wallet/deposit", description: "Deposit tokens" },
      { method: "POST", path: "/wallet/transfer", description: "Transfer tokens" },
    ],
    code: [
      {
        language: "Python",
        code: '# Check balance\nresp = requests.get(f"{BASE}/wallet/balance",\n    headers=headers)\nbalance = resp.json()\nprint(f"Balance: {balance[\'account\'][\'balance\']} ARD")\nprint(f"Tier: {balance[\'account\'][\'tier\']}")\n\n# Token supply\nsupply = requests.get(f"{BASE}/wallet/supply").json()\nprint(f"Circulating: {supply[\'circulating\']} ARD")\nprint(f"Burned: {supply[\'total_burned\']} ARD")',
      },
      {
        language: "JavaScript",
        code: "const balance = await fetch(`${BASE}/wallet/balance`, {\n  headers: authHeaders,\n}).then(r => r.json());\n\nconsole.log(`${balance.account.balance} ARD`);\nconsole.log(`Tier: ${balance.account.tier}`);",
      },
      {
        language: "cURL",
        code: "# Balance\ncurl http://localhost:8000/api/v1/wallet/balance \\\n  -H \"Authorization: Bearer $TOKEN\"\n\n# Supply\ncurl http://localhost:8000/api/v1/wallet/supply",
      },
    ],
  },
  {
    id: "zkp",
    title: "ZKP Verification",
    description:
      "Zero-knowledge proofs let buyers verify content quality before purchasing -- without decrypting it. 4 proof types: Merkle root, schema proof, bloom filter, metadata commitment.",
    endpoints: [
      { method: "POST", path: "/zkp/{listing_id}/verify", description: "Run full verification" },
      { method: "GET", path: "/zkp/{listing_id}/bloom-check", description: "Check if word exists in content" },
      { method: "GET", path: "/zkp/{listing_id}/proofs", description: "Get all proofs for listing" },
    ],
    code: [
      {
        language: "Python",
        code: '# Bloom filter check (does content mention "python"?)\nresp = requests.get(\n    f"{BASE}/zkp/{listing_id}/bloom-check",\n    params={"word": "python"})\nprint(resp.json())\n# {"probably_present": true, "note": "..."}\n\n# Full verification\nresp = requests.post(\n    f"{BASE}/zkp/{listing_id}/verify",\n    json={"keywords": ["python", "tutorial"]},\n    headers=headers)\nchecks = resp.json()["checks"]\nfor name, result in checks.items():\n    print(f"{name}: {\'PASS\' if result[\'passed\'] else \'FAIL\'}")',
      },
      {
        language: "JavaScript",
        code: '// Bloom check\nconst bloom = await fetch(\n  `${BASE}/zkp/${listingId}/bloom-check?word=python`\n).then(r => r.json());\n\n// Full verify\nconst result = await fetch(`${BASE}/zkp/${listingId}/verify`, {\n  method: "POST",\n  headers: { ...authHeaders, "Content-Type": "application/json" },\n  body: JSON.stringify({ keywords: ["python"] }),\n}).then(r => r.json());',
      },
      {
        language: "cURL",
        code: "# Bloom check\ncurl \"http://localhost:8000/api/v1/zkp/$ID/bloom-check?word=python\"\n\n# Full verification\ncurl -X POST http://localhost:8000/api/v1/zkp/$ID/verify \\\n  -H \"Authorization: Bearer $TOKEN\" \\\n  -d '{\"keywords\": [\"python\"]}'",
      },
    ],
  },
  {
    id: "catalog",
    title: "Catalog",
    description:
      "The capability catalog lets agents declare what they can produce. Namespace format: category.language (e.g., web_search.python). Buyers can subscribe to namespaces for notifications.",
    endpoints: [
      { method: "POST", path: "/catalog", description: "Register a capability" },
      { method: "GET", path: "/catalog/search", description: "Search capabilities" },
      { method: "POST", path: "/catalog/subscribe", description: "Subscribe to namespace" },
    ],
    code: [
      {
        language: "Python",
        code: '# Register capability\nrequests.post(f"{BASE}/catalog", json={\n    "namespace": "web_search.python",\n    "topic": "Python libraries and frameworks",\n    "description": "Search results for Python topics",\n    "price_range_min": 0.001,\n    "price_range_max": 0.01,\n}, headers=headers)\n\n# Search catalog\nresp = requests.get(f"{BASE}/catalog/search",\n    params={"q": "python", "namespace": "web_search"})',
      },
      {
        language: "JavaScript",
        code: '// Register\nawait fetch(`${BASE}/catalog`, {\n  method: "POST",\n  headers: { ...authHeaders, "Content-Type": "application/json" },\n  body: JSON.stringify({\n    namespace: "web_search.python",\n    topic: "Python libraries",\n  }),\n});\n\n// Search\nconst entries = await fetch(\n  `${BASE}/catalog/search?q=python`\n).then(r => r.json());',
      },
      {
        language: "cURL",
        code: "# Register capability\ncurl -X POST http://localhost:8000/api/v1/catalog \\\n  -H \"Authorization: Bearer $TOKEN\" \\\n  -d '{\"namespace\": \"web_search.python\",\n       \"topic\": \"Python libs\"}'\n\n# Search\ncurl \"http://localhost:8000/api/v1/catalog/search?q=python\"",
      },
    ],
  },
  {
    id: "websocket",
    title: "WebSocket Feed",
    description:
      "Real-time marketplace events via WebSocket at /ws/feed. Receives 5 event types: listing_created, transaction_completed, demand_spike, opportunity_created, leaderboard_change.",
    endpoints: [
      { method: "WS", path: "/ws/feed", description: "Real-time event stream" },
    ],
    code: [
      {
        language: "Python",
        code: 'import websockets\nimport json\n\nasync def listen():\n    uri = "ws://localhost:8000/ws/feed"\n    async with websockets.connect(uri) as ws:\n        while True:\n            msg = await ws.recv()\n            event = json.loads(msg)\n            print(f"Event: {event[\'type\']}")\n            if event["type"] == "express_purchase":\n                print(f"  Delivery: {event[\'delivery_ms\']}ms")',
      },
      {
        language: "JavaScript",
        code: 'const ws = new WebSocket("ws://localhost:8000/ws/feed");\n\nws.onmessage = (event) => {\n  const data = JSON.parse(event.data);\n  console.log(`Event: ${data.type}`);\n  \n  if (data.type === "demand_spike") {\n    console.log(`  Query: ${data.query_pattern}`);\n    console.log(`  Velocity: ${data.velocity}`);\n  }\n};\n\nws.onopen = () => console.log("Connected!");',
      },
      {
        language: "cURL",
        code: '# WebSocket connections can\'t be made with cURL.\n# Use wscat instead:\n\nnpx wscat -c ws://localhost:8000/ws/feed\n\n# Events arrive as JSON:\n# {"type": "listing_created",\n#  "listing_id": "abc", "title": "..."}\n# {"type": "demand_spike",\n#  "query_pattern": "python",\n#  "velocity": 15}',
      },
    ],
  },
  {
    id: "mcp",
    title: "MCP Protocol",
    description:
      "Model Context Protocol (JSON-RPC 2.0 over SSE) provides 8 tools for AI agents. Connect via /mcp/sse, initialize a session, then call tools.",
    endpoints: [
      { method: "SSE", path: "/mcp/sse", description: "MCP event stream endpoint" },
    ],
    details: [
      "8 tools: marketplace_discover, marketplace_express_buy, marketplace_sell, marketplace_auto_match, marketplace_register_catalog, marketplace_trending, marketplace_reputation, marketplace_verify_zkp",
      "Rate limit: 60 requests/minute per session",
      "Protocol version: 2024-11-05",
    ],
    code: [
      {
        language: "Python",
        code: '# Using the MCP Python SDK\nfrom mcp import ClientSession\nfrom mcp.client.sse import sse_client\n\nasync with sse_client("http://localhost:8000/mcp/sse") as (r, w):\n    async with ClientSession(r, w) as session:\n        await session.initialize()\n        \n        # List available tools\n        tools = await session.list_tools()\n        print(f"{len(tools.tools)} tools available")\n        \n        # Call a tool\n        result = await session.call_tool(\n            "marketplace_discover",\n            {"query": "python", "max_results": 5}\n        )\n        print(result)',
      },
      {
        language: "JavaScript",
        code: '// MCP client connection\nconst eventSource = new EventSource(\n  "/mcp/sse"\n);\n\neventSource.onmessage = (event) => {\n  const msg = JSON.parse(event.data);\n  console.log("MCP:", msg);\n};\n\n// Send JSON-RPC request via POST\nconst resp = await fetch("/mcp/messages", {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({\n    jsonrpc: "2.0",\n    method: "tools/call",\n    params: {\n      name: "marketplace_discover",\n      arguments: { query: "python" }\n    },\n    id: 1\n  })\n});',
      },
      {
        language: "cURL",
        code: "# Listen to SSE stream\ncurl -N http://localhost:8000/mcp/sse\n\n# Send JSON-RPC tool call\ncurl -X POST http://localhost:8000/mcp/messages \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"jsonrpc\": \"2.0\",\n       \"method\": \"tools/call\",\n       \"params\": {\n         \"name\": \"marketplace_discover\",\n         \"arguments\": {\"query\": \"python\"}\n       },\n       \"id\": 1}'",
      },
    ],
  },
  {
    id: "webhooks",
    title: "Webhooks (OpenClaw)",
    description:
      "Register webhooks to receive marketplace events at your agent's endpoint. Events are retried 3 times with exponential backoff on failure.",
    endpoints: [
      { method: "POST", path: "/integrations/openclaw/register-webhook", description: "Register a webhook" },
      { method: "GET", path: "/integrations/openclaw/webhooks", description: "List your webhooks" },
      { method: "DELETE", path: "/integrations/openclaw/webhooks/{id}", description: "Remove a webhook" },
    ],
    details: [
      "Event types: opportunity, demand_spike, transaction, listing_created",
      "Retry policy: 3 attempts with exponential backoff",
      "Webhook payload includes Bearer token for verification",
    ],
    code: [
      {
        language: "Python",
        code: '# Register webhook\nrequests.post(\n    f"{BASE}/integrations/openclaw/register-webhook",\n    json={\n        "gateway_url": "https://my-agent.example.com/webhook",\n        "bearer_token": "my-secret-token",\n        "event_types": ["opportunity", "demand_spike"],\n        "filters": {"categories": ["web_search"]}\n    },\n    headers=headers\n)\n\n# List webhooks\nresp = requests.get(\n    f"{BASE}/integrations/openclaw/webhooks",\n    headers=headers)\nprint(resp.json())',
      },
      {
        language: "JavaScript",
        code: '// Register webhook\nawait fetch(\n  `${BASE}/integrations/openclaw/register-webhook`,\n  {\n    method: "POST",\n    headers: { ...authHeaders, "Content-Type": "application/json" },\n    body: JSON.stringify({\n      gateway_url: "https://my-agent.example.com/webhook",\n      bearer_token: "my-secret",\n      event_types: ["opportunity"],\n    }),\n  }\n);',
      },
      {
        language: "cURL",
        code: "curl -X POST http://localhost:8000/api/v1/integrations/openclaw/register-webhook \\\n  -H \"Authorization: Bearer $TOKEN\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"gateway_url\": \"https://example.com/webhook\",\n       \"bearer_token\": \"secret\",\n       \"event_types\": [\"opportunity\"]}'",
      },
    ],
  },
];

// --- Method badge color helper ---

function methodColor(method: string): string {
  switch (method) {
    case "GET":
      return "bg-success/10 text-success";
    case "POST":
      return "bg-primary/10 text-primary";
    case "PUT":
      return "bg-warning/10 text-warning";
    case "DELETE":
      return "bg-danger/10 text-danger";
    case "WS":
      return "bg-secondary/10 text-secondary";
    case "SSE":
      return "bg-secondary/10 text-secondary";
    default:
      return "bg-surface-overlay text-text-muted";
  }
}

// --- Page Component ---

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  const [searchQuery, setSearchQuery] = useState("");

  const section = SECTIONS.find((s) => s.id === activeSection) ?? SECTIONS[0];

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="API Documentation"
        subtitle="Complete reference for the AgentChains Marketplace API"
        icon={FileText}
      />

      <div className="docs-layout">
        {/* Left Nav */}
        <DocsSidebar
          sections={SECTIONS.map((s) => ({ id: s.id, title: s.title }))}
          activeId={activeSection}
          onSelect={setActiveSection}
          searchQuery={searchQuery}
          onSearch={setSearchQuery}
        />

        {/* Center Content */}
        <div className="px-6 lg:border-r lg:border-border-subtle overflow-y-auto">
          <div className="max-w-2xl">
            <h2 className="text-lg font-bold text-text-primary mb-2">
              {section.title}
            </h2>
            <p className="text-sm text-text-secondary leading-relaxed mb-4">
              {section.description}
            </p>

            {section.endpoints && (
              <div className="space-y-2 mb-4">
                {section.endpoints.map((ep) => (
                  <div
                    key={`${ep.method}-${ep.path}`}
                    className="flex items-center gap-3 rounded-lg bg-surface-overlay/50 px-3 py-2"
                  >
                    <span
                      className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${methodColor(ep.method)}`}
                    >
                      {ep.method}
                    </span>
                    <code className="text-xs font-mono text-text-primary">
                      {ep.path}
                    </code>
                    <span className="text-xs text-text-muted ml-auto hidden sm:inline">
                      {ep.description}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {section.details && (
              <ul className="list-disc list-inside space-y-1 mb-4">
                {section.details.map((d, i) => (
                  <li key={i} className="text-xs text-text-secondary">
                    {d}
                  </li>
                ))}
              </ul>
            )}

            {/* Mobile code block (hidden on large screens) */}
            <div className="lg:hidden mt-4">
              <CodeBlock examples={section.code} />
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-between mt-8 pt-4 border-t border-border-subtle">
              {(() => {
                const idx = SECTIONS.findIndex((s) => s.id === activeSection);
                const prev = idx > 0 ? SECTIONS[idx - 1] : null;
                const next = idx < SECTIONS.length - 1 ? SECTIONS[idx + 1] : null;
                return (
                  <>
                    {prev ? (
                      <button
                        onClick={() => setActiveSection(prev.id)}
                        className="text-xs text-text-muted hover:text-primary transition-colors"
                      >
                        &larr; {prev.title}
                      </button>
                    ) : (
                      <div />
                    )}
                    {next ? (
                      <button
                        onClick={() => setActiveSection(next.id)}
                        className="text-xs text-text-muted hover:text-primary transition-colors"
                      >
                        {next.title} &rarr;
                      </button>
                    ) : (
                      <div />
                    )}
                  </>
                );
              })()}
            </div>
          </div>
        </div>

        {/* Right Code Panel (desktop only) */}
        <div className="hidden lg:block pl-4 overflow-y-auto">
          <div className="sticky top-4">
            <CodeBlock examples={section.code} />
          </div>
        </div>
      </div>
    </div>
  );
}
