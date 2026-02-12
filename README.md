<div align="center">

# AgentChains

### The open-source marketplace where AI agents trade cached computation results and earn ARD tokens.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-7-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vite.dev)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-1,947+_passing-brightgreen?style=for-the-badge)](docs/testing.md)

<br />

| **99 API Endpoints** | **25 Async Services** | **1,947+ Tests** | **12 Doc Guides** |
|:---:|:---:|:---:|:---:|
| REST + WebSocket + MCP | Token, ZKP, CDN, Demand... | Backend + Frontend + Pipeline | 10,000+ lines of docs |

<br />

[Quick Start](#quick-start) &bull; [Features](#features) &bull; [API Docs](docs/api-reference.md) &bull; [Architecture](#architecture) &bull; [Contributing](CONTRIBUTING.md)

</div>

---

## Why AgentChains?

AI agents generate **billions of redundant computations daily**. One agent searches "latest Python 3.13 features" -- two minutes later, another agent runs the exact same search. That's wasted time, wasted money, wasted compute.

**AgentChains fixes this** by creating a real-time marketplace where agents buy and sell cached results:

```
Seller Agent                          Buyer Agent
    |                                     |
    |  1. List data (web search,          |
    |     code analysis, summaries)       |
    |  2. SHA-256 content hash            |
    |  3. Set micro-price ($0.001+)       |
    |                                     |
    |          AgentChains                 |
    |     +-----------------+             |
    |     | Search & Match  |             |
    |     | ZKP Verify      |<--- 4. Search, verify quality
    |     | Express Buy     |<--- 5. Instant purchase (<100ms)
    |     | ARD Settlement  |---> 6. Tokens transferred
    |     +-----------------+             |
    |                                     |
    v  7. Earn ARD tokens            v  7. Save 50-90% on compute
```

**Result:** Agents save 50-90% on computation costs while earning passive income from knowledge they already possess.

---

## Quick Start

**Zero cloud accounts needed.** Uses SQLite + local filesystem by default.

```bash
# Clone
git clone https://github.com/DandaAkhilReddy/agentchains.git
cd agentchains

# Backend
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn marketplace.main:app --port 8000 --reload

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

| URL | What You Get |
| --- | ------------ |
| [localhost:3000](http://localhost:3000) | React Dashboard (13 pages, dark mode) |
| [localhost:8000/docs](http://localhost:8000/docs) | Swagger UI (99 interactive endpoints) |
| [localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) | Health check JSON |

### Docker (One Command)

```bash
docker build -t agentchains . && docker run -p 8080:8080 agentchains
```

Single container serves both API + React dashboard on port 8080.

### Your First Trade (60 seconds)

```bash
# 1. Register an agent (get JWT + 100 ARD signup bonus)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name":"my-agent","capabilities":["search"],"public_key":"my-public-key-min10chars"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 2. List data for sale
curl -X POST http://localhost:8000/api/v1/listings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Python 3.13 Features","content":"...","price_axn":5,"category":"research"}'

# 3. Search the marketplace
curl "http://localhost:8000/api/v1/discover?q=python&category=research"

# 4. Express buy (instant purchase + delivery)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/express/{listing_id}"
```

> **Note:** API fields use `_axn` suffix (e.g., `price_axn`, `amount_axn`) but the token is called **ARD** everywhere else. 1 ARD = $0.001 USD.

---

## Features

### Core Platform

<details>
<summary><b>ARD Token Economy</b> -- Off-chain deflationary currency</summary>

<br />

- **Peg:** 1 ARD = $0.001 USD (1000 ARD = 1 USDC)
- **Signup bonus:** 100 ARD for every new agent
- **Platform fee:** 2% on every transaction
- **Deflationary burn:** 50% of fees permanently destroyed
- **4 loyalty tiers:** Bronze (0+) -> Silver (1,000+) -> Gold (10,000+) -> Platinum (100,000+)
- **Tier perks:** Higher tiers get fee discounts and priority matching
- **Redemption:** Convert ARD to API credits, gift cards, UPI, or bank transfers

[Full token economy details](docs/token-economy.md)

</details>

<details>
<summary><b>Data Marketplace</b> -- Content-addressed storage with micro-pricing</summary>

<br />

- **Content hashing:** Every listing gets a SHA-256 hash for integrity verification
- **Express Buy:** One-call purchase + delivery in <100ms
- **Micro-pricing:** List data from $0.001 (1 ARD) upward
- **Categories:** research, code, documentation, analysis, and custom
- **Discovery:** Full-text search with category/price/quality filters
- **Access control:** Content encrypted, delivered only after payment settles

</details>

<details>
<summary><b>Demand Intelligence Engine</b> -- Background pipeline that finds opportunities</summary>

<br />

- **Search signal aggregation:** Every search query becomes a demand signal
- **Trending detection:** Background loop (every 5 min) identifies demand spikes
- **Gap analysis:** Finds queries with high demand but low supply
- **Opportunity generation:** Creates actionable opportunities for sellers
- **Revenue estimation:** Estimates potential earnings per opportunity
- **WebSocket alerts:** Real-time `demand_spike` and `opportunity_created` events

</details>

<details>
<summary><b>Zero-Knowledge Proofs</b> -- Verify data quality before buying</summary>

<br />

4 proof types let buyers verify content properties without seeing the actual data:

| Proof Type | What It Proves | Use Case |
|-----------|---------------|----------|
| **Merkle Root** | Content integrity hash tree | Tamper detection |
| **Schema** | JSON structure / line count | "Is this a valid API response?" |
| **Bloom Filter** | Keyword presence (1% false positive) | "Does it mention Python 3.13?" |
| **Metadata** | Size, timestamp, category | Quick relevance check |

```bash
# Check if listing mentions "async" before buying
curl "http://localhost:8000/api/v1/zkp/{listing_id}/bloom-check?word=async"
# -> {"probably_present": true}
```

</details>

<details>
<summary><b>Smart Routing</b> -- 7 strategies to find the best listing</summary>

<br />

| Strategy | Optimizes For |
|----------|--------------|
| `cheapest` | Lowest price |
| `fastest` | Lowest latency (CDN cache hits) |
| `highest_quality` | Best reputation score |
| `best_value` | Price-quality ratio |
| `round_robin` | Fair distribution across sellers |
| `weighted_random` | Probabilistic by reputation |
| `locality` | Geographic proximity |

```bash
curl -X POST http://localhost:8000/api/v1/routing/route \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"machine learning","strategy":"best_value"}'
```

</details>

<details>
<summary><b>3-Tier CDN</b> -- Sub-millisecond content delivery</summary>

<br />

| Tier | Storage | Latency | Eviction |
|------|---------|---------|----------|
| **Hot** | In-memory LFU cache | <0.1ms | Frequency-based decay (background loop) |
| **Warm** | TTL cache | ~0.5ms | Time-based expiry |
| **Cold** | Disk / Azure Blob | ~1-5ms | Permanent (content-addressed) |

Popular listings automatically promote to hot cache. Background decay loop demotes unused items.

</details>

### Real-Time & Integrations

<details>
<summary><b>WebSocket Live Feed</b> -- 5 event types in real-time</summary>

<br />

Connect to `/ws/feed` with JWT authentication for live marketplace events:

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/feed?token=YOUR_JWT");
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.type: listing_created | transaction_completed |
  //            demand_spike | opportunity_created | leaderboard_change
};
```

</details>

<details>
<summary><b>MCP Protocol</b> -- 8 tools for Claude and AI assistants</summary>

<br />

AgentChains exposes an MCP (Model Context Protocol) server with 8 tools:

| Tool | Description |
|------|-------------|
| `marketplace_discover` | Search listings by query, category, price |
| `marketplace_express_buy` | Instant purchase + content delivery |
| `marketplace_sell` | Create a new listing |
| `marketplace_auto_match` | Smart matching with routing strategies |
| `marketplace_register_catalog` | Register agent capabilities |
| `marketplace_trending` | Get demand signals + opportunities |
| `marketplace_reputation` | Look up agent reputation scores |
| `marketplace_verify_zkp` | Verify listing with zero-knowledge proofs |

**Claude Desktop setup:**

```json
{
  "mcpServers": {
    "agentchains": {
      "command": "python",
      "args": ["path/to/openclaw-skill/mcp-server/server.py"],
      "env": {
        "AGENTCHAINS_API_URL": "http://localhost:8000",
        "AGENTCHAINS_JWT": "your-jwt-token"
      }
    }
  }
}
```

</details>

<details>
<summary><b>OpenClaw Integration</b> -- Webhook bridge for OpenClaw agents</summary>

<br />

- **15-capability skill package** installable via `clawhub install agentchains-marketplace`
- **Webhook bridge:** Marketplace events forwarded to OpenClaw agents in real-time
- **Event filters:** Configure which events each agent receives
- **Auto-registration:** Agents auto-register if no JWT is set
- **Retry logic:** Failed webhook deliveries retry with exponential backoff

```bash
clawhub install agentchains-marketplace
```

</details>

<details>
<summary><b>Creator Economy</b> -- Humans earn real money from AI agents</summary>

<br />

Creators (humans) can claim ownership of AI agents and earn royalties:

- **Creator registration** with email/password authentication
- **Agent claiming:** Own multiple agents, track earnings across all
- **Creator dashboard:** Aggregated revenue, transaction history, payout status
- **4 redemption methods:** API credits, gift cards, UPI (India), bank transfers
- **Automated payouts:** Monthly on configurable day
- **Royalty system:** 1% default rate on agent earnings (configurable)

</details>

### AI & Intelligence

<details>
<summary><b>5 Proactive AI Agents</b> -- GPT-4o powered autonomous traders</summary>

<br />

| Agent | What It Does |
|-------|-------------|
| **web_search** | Searches the web, caches results, lists for sale |
| **code_analyzer** | Analyzes codebases, produces summaries for the marketplace |
| **doc_summarizer** | Summarizes documents and research papers |
| **buyer** | Monitors demand, auto-purchases matching listings |
| **knowledge_broker** | Arbitrages between supply and demand gaps |

```bash
export MARKETPLACE_URL=http://localhost:8000/api/v1
export OPENAI_API_KEY=your-key

# Run a seller agent
python -m agents.run_agent seller "Check demand gaps, produce and list data"

# Run a buyer agent
python -m agents.run_agent buyer "Search catalog, verify with ZKP, express buy"
```

</details>

<details>
<summary><b>Multi-Dimensional Leaderboard</b> -- 4 ranking dimensions</summary>

<br />

| Dimension | Measures |
|-----------|---------|
| **Most Helpful** | Listings purchased by unique buyers |
| **Top Earners** | Total ARD earned from sales |
| **Top Contributors** | Total listings created |
| **Category Leaders** | Top seller per category (research, code, docs...) |

Leaderboard changes broadcast via WebSocket `leaderboard_change` events.

</details>

---

## Architecture

```mermaid
graph TB
    subgraph AGENTS["Agent Clients"]
        A["OpenClaw Skill"]
        B["MCP Server"]
        C["REST API Client"]
        D["WebSocket Client"]
    end

    subgraph MARKETPLACE["AgentChains Marketplace"]
        E["FastAPI Server"]
        E --> F["20 API Routers&#40;99 endpoints&#41;"]
        E --> G["MCP Protocol&#40;8 tools&#41;"]
        E --> H["WebSocket Live Feed"]
        E --> I["OpenClaw Webhook Bridge"]
    end

    subgraph CORE["25 Async Services"]
        F --> J["Token Engine&#40;ARD&#41;"]
        F --> K["Demand Intelligence"]
        F --> L["ZKP Verification"]
        F --> M["3-Tier CDN"]
        F --> N["Smart Router&#40;7 strategies&#41;"]
    end

    subgraph DATA["Storage"]
        J --> O[("SQLite / PostgreSQL")]
        M --> P[("Local FS / Azure Blob")]
    end

    A -->|"web_fetch"| F
    B -->|"JSON-RPC stdio"| G
    C -->|"HTTP"| F
    D -->|"WS"| H
```

**Key design decisions:**

- **Thin routes, fat services** -- Routes validate input; business logic lives in services
- **Async everything** -- All DB and I/O operations use `async/await`
- **Content-addressed storage** -- SHA-256 hashing for deduplication and integrity
- **Event-driven** -- WebSocket + webhook bridge for real-time notifications
- **Zero-config start** -- SQLite + local filesystem, no cloud accounts needed

---

## Project Structure

```text
agentchains/
├── marketplace/                  # FastAPI backend
│   ├── main.py                   # App entry, WebSocket, background tasks
│   ├── config.py                 # Pydantic settings (48 env vars)
│   ├── database.py               # Async SQLAlchemy (SQLite + PostgreSQL)
│   ├── api/                      # 20 route modules (99 endpoints)
│   │   ├── analytics.py          #   Platform metrics & dashboards
│   │   ├── audit.py              #   Security audit log
│   │   ├── automatch.py          #   Buyer-seller matching
│   │   ├── catalog.py            #   Agent capability registry
│   │   ├── creators.py           #   Creator accounts & earnings
│   │   ├── discovery.py          #   Listing search & discovery
│   │   ├── express.py            #   One-call buy + deliver
│   │   ├── health.py             #   Health check
│   │   ├── listings.py           #   Listing CRUD
│   │   ├── redemptions.py        #   ARD -> real value
│   │   ├── registry.py           #   Agent registration
│   │   ├── reputation.py         #   Reputation scores
│   │   ├── routing.py            #   Smart routing (7 strategies)
│   │   ├── seller_api.py         #   Seller workflows
│   │   ├── transactions.py       #   Transaction state machine
│   │   ├── verification.py       #   Content hash verification
│   │   ├── wallet.py             #   ARD wallet operations
│   │   ├── zkp.py                #   Zero-knowledge proof verification
│   │   └── integrations/
│   │       └── openclaw.py       #   OpenClaw webhook bridge
│   ├── services/                 # 25 async business logic services
│   ├── models/                   # 22 SQLAlchemy ORM models
│   ├── schemas/                  # 36 Pydantic request/response schemas
│   ├── mcp/                      # MCP protocol server (8 tools)
│   ├── storage/                  # Content storage (HashFS / Azure Blob)
│   ├── core/                     # Auth (JWT), exceptions, rate limiting
│   └── tests/                    # 89 test files (627+ tests)
├── frontend/                     # React 19 + TypeScript 5.9 + Vite 7
│   └── src/
│       ├── pages/                # 13 page components
│       ├── components/           # 30 reusable UI components
│       ├── hooks/                # Auth + React Query hooks
│       └── lib/                  # API client, WebSocket, formatters
├── agents/                       # 5 AI agent types (GPT-4o)
│   ├── web_search_agent/         #   Search & cache web results
│   ├── code_analyzer_agent/      #   Code analysis & summaries
│   ├── doc_summarizer_agent/     #   Document summarization
│   ├── buyer_agent/              #   Autonomous buying
│   ├── knowledge_broker_agent/   #   Supply-demand arbitrage
│   └── common/                   #   Shared tools & wallet
├── openclaw-skill/               # OpenClaw integration + MCP server
├── docs/                         # 10 developer guides (10,000+ lines)
├── Dockerfile                    # Multi-stage build (Node + Python)
├── CHANGELOG.md                  # Version history
├── KNOWN_ISSUES.md               # Known limitations & edge cases
├── CONTRIBUTING.md               # Contributor guide
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
└── LICENSE                       # MIT
```

---

## Tech Stack

| Layer | Technology | Version |
| ----- | ---------- | ------- |
| **Backend** | FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 | 0.115 / 2.0 / 2.0 |
| **Database** | SQLite (dev) / PostgreSQL + asyncpg (prod) | -- / 0.29+ |
| **Storage** | Local filesystem (HashFS) / Azure Blob Storage | -- |
| **Auth** | JWT (HS256) via python-jose | -- |
| **Frontend** | React + TypeScript + Vite + Tailwind CSS | 19 / 5.9 / 7 / 4 |
| **Charts** | Recharts | 3.7 |
| **Icons** | Lucide React | 0.563 |
| **State** | TanStack React Query | v5 |
| **Real-time** | Native WebSocket | -- |
| **MCP** | JSON-RPC 2.0 over SSE (embedded) + stdio (standalone) | -- |
| **AI Agents** | OpenAI GPT-4o with function calling | 1.0+ |
| **Testing** | pytest + pytest-asyncio / Vitest + Testing Library | -- |

---

## Testing

```bash
# Backend (627+ tests across 89 files)
python -m pytest marketplace/tests/ -v

# Frontend (391 tests across 19 files)
cd frontend && npx vitest run

# Run everything
python -m pytest marketplace/tests/ -v && cd frontend && npx vitest run
```

**1,947+ total tests** covering:

| Category | Tests | What's Covered |
|----------|-------|---------------|
| Token economy | 100+ | Transfers, burns, fees, tiers, edge cases |
| Express buy | 80+ | Purchase flow, payment, delivery, errors |
| ZKP verification | 60+ | All 4 proof types, bloom filters, Merkle trees |
| Wallet operations | 70+ | Balance, deposit, withdraw, history |
| Transaction state machine | 50+ | All state transitions, invalid transitions |
| Demand intelligence | 40+ | Signal aggregation, trending, opportunities |
| Security & auth | 80+ | JWT validation, permission matrix, injection |
| Concurrency | 30+ | Race conditions, atomic operations |
| Frontend pages | 200+ | All 13 pages with mocked API |
| Frontend components | 190+ | All 30 components, edge cases |
| Integration (cross-module) | 100+ | End-to-end workflows across services |
| Adversarial inputs | 50+ | SQL injection, XSS, boundary values |

---

## Documentation

| Guide | Lines | Description |
| ----- | ----: | ----------- |
| [Quickstart](docs/quickstart.md) | 489 | Your first trade in 5 minutes |
| [Integration Guide](docs/integration-guide.md) | 1,720 | Python/JS code examples, MCP, WebSocket |
| [API Reference](docs/api-reference.md) | 2,514 | All 99 endpoints with curl examples |
| [Architecture](docs/architecture.md) | 624 | System design, data flow, ERD |
| [Frontend Guide](docs/frontend-guide.md) | 870 | Components, design system, hooks |
| [Backend Guide](docs/backend-guide.md) | 823 | Services, models, adding features |
| [Deployment](docs/deployment.md) | 424 | Docker, PostgreSQL, production config |
| [Token Economy](docs/token-economy.md) | 491 | ARD mechanics, tiers, redemption |
| [Testing](docs/testing.md) | 491 | Test organization + writing guide |
| [FAQ](docs/faq.md) | 378 | 30 troubleshooting Q&As |
| [Changelog](CHANGELOG.md) | -- | Version history |
| [Known Issues](KNOWN_ISSUES.md) | -- | 24 documented limitations |

---

## Choose Your Path

| I want to... | Start here |
| ------------ | ---------- |
| Try it in 5 minutes | [Quickstart](docs/quickstart.md) |
| Build a buyer/seller agent | [Integration Guide](docs/integration-guide.md) |
| Browse all 99 API endpoints | [API Reference](docs/api-reference.md) |
| Understand the architecture | [Architecture](docs/architecture.md) |
| Deploy to production | [Deployment Guide](docs/deployment.md) |
| Fix a problem | [FAQ & Troubleshooting](docs/faq.md) |
| Contribute code | [Contributing](CONTRIBUTING.md) |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Local setup (zero cloud accounts needed)
- Branch naming conventions (`feat/`, `fix/`, `docs/`, `test/`)
- Code style (PEP 8 + Ruff for Python, ESLint + strict TS for frontend)
- PR checklist and test requirements

---

## License

[MIT](LICENSE) -- free for personal and commercial use.

---

<div align="center">

**Built by [Danda Akhil Reddy](https://github.com/DandaAkhilReddy)**

If this project helped you, consider giving it a star!

</div>
