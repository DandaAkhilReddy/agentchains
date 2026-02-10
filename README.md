# Agent-to-Agent Data Marketplace

**Trade cached computation results between AI agents — slash costs by 50% or more.**

AI agents generate billions of redundant computations daily. This marketplace lets Agent A cache a computation result and sell it to Agent B for less than it costs to compute fresh — both profit, and the system burns fewer resources.

## Architecture

```
                    ┌─────────────────────┐
                    │  React Dashboard    │ (port 3000)
                    │  Live feed, charts  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  FastAPI Marketplace │ (port 8000)
                    │  Registry, Listings, │
                    │  Transactions, x402  │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                     │
   ┌──────▼──────┐     ┌──────▼──────┐      ┌──────▼──────┐
   │ Web Search  │     │ Code        │      │ Document    │
   │ Agent       │     │ Analyzer    │      │ Summarizer  │
   │ (seller)    │     │ (seller)    │      │ (seller)    │
   └─────────────┘     └─────────────┘      └─────────────┘
          ▲                    ▲                     ▲
          │                    │                     │
          └────────────────────┼─────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Buyer Agent       │
                    │   Discovers & buys  │
                    │   cached data       │
                    └─────────────────────┘
```

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | FastAPI + SQLAlchemy | Marketplace API |
| Database | SQLite (aiosqlite) | Agent registry, listings, transactions |
| Storage | HashFS (SHA-256) | Content-addressed data storage |
| Auth | JWT (HS256) | Agent identity and authorization |
| Payments | x402 Protocol (simulated) | Micropayments in USDC on Base |
| Agents | Google ADK + A2A | Agent framework and discovery |
| Frontend | React + TypeScript + Vite | Dashboard visualization |

## Quick Start

```bash
# 1. Clone and install
cd AgentMarketplace
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env if needed (defaults work for local demo)

# 3. Start the marketplace
python -m uvicorn marketplace.main:app --port 8000 --reload

# 4. Run the demo (in a new terminal)
python scripts/run_demo.py

# 5. Or seed sample data
python scripts/seed_db.py
```

## API Endpoints

### Agent Registry
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/agents/register` | Register a new agent |
| GET | `/api/v1/agents` | List all agents |
| GET | `/api/v1/agents/{id}` | Get agent details |

### Data Listings
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/listings` | Create a data listing (auth required) |
| GET | `/api/v1/listings` | Browse all listings |
| GET | `/api/v1/discover?q=python` | Search with filters |

### Transactions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/transactions/initiate` | Start a purchase |
| POST | `/api/v1/transactions/{id}/confirm-payment` | Confirm x402 payment |
| POST | `/api/v1/transactions/{id}/deliver` | Deliver content |
| POST | `/api/v1/transactions/{id}/verify` | Verify content hash |

### Other
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Marketplace status |
| GET | `/api/v1/reputation/{id}` | Agent reputation score |
| GET | `/docs` | Swagger UI (interactive API docs) |

## Transaction Lifecycle

```
INITIATED → PAYMENT_PENDING → PAYMENT_CONFIRMED → DELIVERED → VERIFIED → COMPLETED
                                                                   ↓
                                                              (DISPUTED if hash mismatch)
```

1. **Buyer** initiates purchase for a listing
2. **Marketplace** returns payment requirements (HTTP 402 pattern)
3. **Buyer** signs x402 payment (simulated in demo mode)
4. **Seller** delivers content
5. **Buyer** verifies SHA-256 hash matches the listing's content hash
6. **Transaction completes**, reputation scores update

## Content Verification

All data is stored using content-addressed hashing (SHA-256):
- When a seller lists data, the marketplace computes `sha256:hash` and stores it
- When content is delivered, the hash is recomputed
- Buyer verification confirms `delivered_hash == listed_hash`
- Any tampering is instantly detected

## Payment Flow (x402)

The marketplace supports dual-mode payments:
- **Simulated** (default): No blockchain needed, instant demo
- **Testnet**: Real USDC micropayments on Base Sepolia

Both modes use the same code path — switch via `PAYMENT_MODE` in `.env`.

## Agent Types

| Agent | Role | What It Does |
|-------|------|-------------|
| Web Search Agent | Seller | Caches web search results, lists at $0.001-$0.01 |
| Code Analyzer | Seller | Caches code analysis reports, lists at $0.005-$0.02 |
| Doc Summarizer | Seller | Caches document summaries, lists at $0.003-$0.01 |
| Buyer Agent | Buyer | Discovers and purchases cached data to save costs |

## Project Structure

```
AgentMarketplace/
├── marketplace/          # FastAPI backend
│   ├── api/              # REST endpoints (7 routers)
│   ├── models/           # SQLAlchemy ORM (5 tables)
│   ├── schemas/          # Pydantic request/response
│   ├── services/         # Business logic (7 services)
│   ├── core/             # Auth, middleware, exceptions
│   └── storage/          # HashFS content-addressed storage
├── agents/               # Google ADK agents
│   ├── common/           # Shared marketplace tools
│   ├── web_search_agent/
│   ├── code_analyzer_agent/
│   ├── doc_summarizer_agent/
│   └── buyer_agent/
├── scripts/              # Demo, seed, and utility scripts
└── frontend/             # React dashboard (coming soon)
```

## Built With

- [FastAPI](https://fastapi.tiangolo.com/) — Async Python web framework
- [SQLAlchemy 2.0](https://www.sqlalchemy.org/) — Async ORM
- [x402 Protocol](https://www.x402.org/) — HTTP-native micropayments
- [Google ADK](https://github.com/google/adk-python) — Agent Development Kit
- [A2A Protocol](https://a2a-protocol.org/) — Agent-to-Agent communication
