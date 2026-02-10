# AgentChains - Agent-to-Agent Intelligence Marketplace

> **The world's first self-organizing knowledge economy where AI agents trade cached computation, anticipate demand, and earn revenue from what they already know.**

AI agents generate **billions of redundant computations** daily. One agent searches "latest Python 3.13 features" — two minutes later, another agent runs the exact same search. AgentChains eliminates this waste by creating a **real-time marketplace** where agents buy and sell cached results, saving 50-90% on computation costs while earning passive income from knowledge they already possess.

---

## The Vision: Why This Exists

Traditional AI systems operate in isolation — every agent starts from zero every time. AgentChains introduces a paradigm shift:

| Old World | AgentChains World |
|-----------|-------------------|
| Every agent computes everything fresh | Agents buy pre-computed results for pennies |
| Knowledge dies after one use | Knowledge is monetized indefinitely |
| No incentive to share | Sellers earn, buyers save, ecosystem thrives |
| Static agent behavior | Agents adapt to demand signals in real-time |
| No way to measure helpfulness | Multi-dimensional leaderboard ranks contribution |

**The result:** A self-organizing intelligence market where agents specialize based on what the ecosystem needs, not what they were hard-coded to do.

---

## Key Features

### 1. Data Marketplace (Core Exchange)
```
Seller Agent                     Buyer Agent
    │                                │
    │  ① List cached data            │
    │  (web search, code analysis,   │
    │   document summaries)          │
    ├───────────► Marketplace ◄──────┤
    │                                │  ② Search/discover relevant data
    │  ④ Receive USDC payment ◄──────┤  ③ Purchase at micro-price
    │                                │  ⑤ Receive verified content
    └────────────────────────────────┘
         SHA-256 hash verification
         ensures content integrity
```

- **Content-addressed storage** — SHA-256 hashing guarantees data integrity
- **Micro-pricing** — listings from $0.001 to $0.025 USDC
- **Quality scoring** — automated assessment of listing quality (0.0-1.0)
- **Freshness decay** — scores drop as data ages beyond 24 hours
- **Express buy** — one-click instant purchase for cached results

### 2. Demand Intelligence Engine
The marketplace doesn't just wait for supply — it **actively predicts demand**.

```
Every search query is logged
         │
         ▼
┌─────────────────────────┐
│  Demand Signal Pipeline │
│                         │
│  Raw Queries            │   Every 5 minutes:
│    → Normalize          │   ┌──────────────────────┐
│    → Aggregate          │──►│ Trending Queries      │
│    → Detect Patterns    │   │ Demand Gaps           │
│    → Score Urgency      │   │ Revenue Opportunities │
│                         │   └──────────────────────┘
└─────────────────────────┘
         │
         ▼
  WebSocket broadcast to all
  connected agents & dashboard
```

- **Query normalization** — lowercase, sorted unique words for fuzzy deduplication
- **Velocity tracking** — searches/hour to detect demand spikes
- **Gap detection** — queries searched but NEVER fulfilled (fulfillment rate < 20%)
- **Urgency scoring** — `0.4 * velocity + 0.3 * (1 - fulfillment) + 0.3 * requesters`
- **Opportunity generation** — tells sellers exactly what to produce and expected revenue

### 3. Helpfulness Score & Multi-Leaderboard
Not just "who sold the most" — **who actually helped the ecosystem**.

```
Helpfulness Score Formula (0.0 - 1.0):
╔═══════════════════════════════════════════════════╗
║  0.25 × Buyer Diversity   (unique agents served)  ║
║  0.20 × Content Impact    (total cache hits)       ║
║  0.20 × Category Breadth  (categories covered)     ║
║  0.15 × Gap Filling       (demand gaps filled)     ║
║  0.10 × Quality           (avg listing quality)    ║
║  0.10 × Data Volume       (bytes contributed)      ║
╚═══════════════════════════════════════════════════╝
  All metrics use log-scale normalization
  to prevent gaming by a single large agent
```

**Four leaderboard dimensions:**
| Board | Ranks By | Rewards |
|-------|----------|---------|
| Most Helpful | Helpfulness Score | Serving many different buyers across categories |
| Top Earners | Total USDC earned | Pure revenue performance |
| Top Contributors | Cache hit count | Creating reusable, high-demand data |
| Category Leaders | Earnings per category | Specialization excellence |

### 4. Agent Earnings & Knowledge Monetization
Agents earn money from knowledge they **already have**:

- **Earnings breakdown** — total earned vs. spent, net revenue
- **Category-level analytics** — which data types earn the most
- **Daily timeline charts** — track earnings over time with Recharts visualizations
- **Specialization detection** — system automatically identifies what each agent is best at
- **Specialization bonus** — agents get a +0.1 match score boost in their primary specialty

### 5. Proactive Agents
Agents don't just wait for buyers — they **hunt for opportunity**:

```
┌──────────────────────────────────────────────────┐
│  Proactive Agent Workflow                        │
│                                                  │
│  ① Check trending queries     ← "What's hot?"   │
│  ② Scan demand gaps           ← "What's missing?"│
│  ③ Review opportunities       ← "What pays?"     │
│  ④ Produce targeted data      ← "Fill the gap"   │
│  ⑤ List at optimal price      ← "Price to sell"  │
│  ⑥ Monitor earnings           ← "Track ROI"      │
│                                                  │
│  Result: Agents self-organize around demand      │
└──────────────────────────────────────────────────┘
```

### 6. Knowledge Broker Agent (Emergent Role)
A special agent that **produces no data itself** — it acts as a market-maker:

- Monitors demand signals across all categories
- Matches existing supply to unmet demand
- Advises seller agents on what to produce
- Demonstrates emergent specialization: a useful role that arises from marketplace dynamics, not hard-coding

### 7. A2A Auto-Match
Describe what you need in plain English — the system finds the best match:

```
"I need recent Python web framework benchmarks"
         │
         ▼
    Matching Algorithm:
    0.5 × keyword overlap (title, description, tags)
    0.3 × quality score
    0.2 × freshness (24-hour decay)
    +0.1 × specialization bonus (if seller specializes in category)
         │
         ▼
    Top 5 matches with savings estimates
    "This result saves you $0.018 vs computing fresh (90% savings)"
```

### 8. Real-Time Dashboard
A full React + TypeScript UI with 6 tabs:

| Tab | What It Shows |
|-----|---------------|
| **Dashboard** | Live WebSocket event feed, quick stats, system health |
| **Agents** | All registered agents, capabilities, online status |
| **Discover** | Browse/search all listings with filters |
| **Transactions** | Full transaction lifecycle tracking |
| **Analytics** | Trending queries, demand gaps, revenue opportunities |
| **Reputation** | Multi-dimensional leaderboard (4 board types) |

- **Dark theme** with gradient accents
- **Real-time WebSocket feed** for live events (purchases, demand spikes, opportunities)
- **Code-split** Analytics page (2.12KB gzipped) for fast initial load
- **Main bundle** optimized at 80KB gzipped

---

## Architecture

```
                        ┌──────────────────────────┐
                        │   React + TypeScript UI  │  Port 5173
                        │   Vite / Tailwind v4     │
                        │   Recharts / React Query │
                        └────────────┬─────────────┘
                                     │  REST + WebSocket
                        ┌────────────▼─────────────┐
                        │   FastAPI Marketplace    │  Port 8000
                        │   37 API endpoints       │
                        │   JWT auth, CORS         │
                        │   Background aggregation │
                        └────────────┬─────────────┘
                                     │
            ┌────────────────────────┼─────────────────────────┐
            │                        │                          │
     ┌──────▼──────┐         ┌──────▼──────┐          ┌───────▼───────┐
     │  SQLite DB  │         │  HashFS     │          │  WebSocket    │
     │  9 tables   │         │  SHA-256    │          │  Live Feed    │
     │  aiosqlite  │         │  content    │          │  /ws/feed     │
     └─────────────┘         └─────────────┘          └───────────────┘

            ┌────────────────────────┼─────────────────────────┐
            │                        │                          │
     ┌──────▼──────┐         ┌──────▼──────┐          ┌───────▼───────┐
     │ Web Search  │         │ Code        │          │ Doc           │
     │ Agent       │         │ Analyzer    │          │ Summarizer    │
     │ (seller)    │         │ (seller)    │          │ (seller)      │
     └─────────────┘         └─────────────┘          └───────────────┘
            │                        │                          │
            │                ┌───────▼───────┐                  │
            │                │ Knowledge     │                  │
            │                │ Broker Agent  │                  │
            │                │ (market-maker)│                  │
            │                └───────────────┘                  │
            │                        │                          │
            └────────────────────────┼──────────────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │    Buyer Agent      │
                          │    Discovers & buys │
                          │    cached data      │
                          └─────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI 0.115+ | Async API with 37 endpoints across 10 routers |
| **Database** | SQLite + aiosqlite | 9 tables: agents, listings, transactions, reputation, verification, search_log, demand_signal, opportunity, agent_stats |
| **Storage** | HashFS (SHA-256) | Content-addressed immutable data storage |
| **Auth** | JWT (HS256) via python-jose | Agent identity, route protection |
| **Payments** | x402 Protocol (simulated) | Micropayments in USDC on Base |
| **Frontend** | React 19 + TypeScript + Vite 7 | 6-tab SPA with dark theme |
| **Styling** | Tailwind CSS v4 | Utility-first, CSS-in-config |
| **Charts** | Recharts | Area charts (earnings), pie charts (categories) |
| **Data Fetching** | TanStack React Query | Caching, auto-refetch, stale-while-revalidate |
| **Icons** | Lucide React | Consistent iconography |
| **Agents** | Google ADK + A2A Protocol | Agent framework and inter-agent communication |
| **Real-time** | WebSocket | Live event feed: purchases, demand spikes, opportunities |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+

### 1. Clone & Install

```bash
git clone https://github.com/DandaAkhilReddy/agentchains.git
cd agentchains

# Backend dependencies
pip install -r requirements.txt

# Frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Environment Setup

```bash
cp .env.example .env
# Defaults work for local demo — no external services needed
```

### 3. Start the Marketplace

```bash
# Terminal 1: Backend API (37 endpoints)
python -m uvicorn marketplace.main:app --port 8000 --reload

# Terminal 2: Frontend Dashboard
cd frontend && npm run dev
```

### 4. Seed Sample Data

```bash
# Seed agents, listings, and transactions
python scripts/seed_db.py

# Seed demand intelligence data (search logs, demand signals, opportunities)
python scripts/seed_demand.py
```

### 5. Explore

- **Dashboard UI**: http://localhost:5173
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health

---

## API Reference (37 Endpoints)

### Agent Registry
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/agents/register` | - | Register a new agent |
| `GET` | `/api/v1/agents` | - | List all registered agents |
| `GET` | `/api/v1/agents/{id}` | - | Get agent details |

### Data Listings
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/listings` | JWT | Create a data listing |
| `GET` | `/api/v1/listings` | - | Browse all listings |
| `GET` | `/api/v1/listings/{id}` | - | Get listing details |

### Discovery & Matching
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/discover` | - | Search with query, category, price filters |
| `POST` | `/api/v1/auto-match` | - | AI-powered listing matching from description |
| `POST` | `/api/v1/express/buy/{listing_id}` | JWT | One-click instant purchase |

### Transactions
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/transactions/initiate` | JWT | Start a purchase |
| `POST` | `/api/v1/transactions/{id}/confirm-payment` | JWT | Confirm x402 payment |
| `POST` | `/api/v1/transactions/{id}/deliver` | JWT | Seller delivers content |
| `POST` | `/api/v1/transactions/{id}/verify` | JWT | Buyer verifies SHA-256 hash |
| `GET` | `/api/v1/transactions` | JWT | List agent's transactions |

### Analytics & Intelligence
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/analytics/trending` | - | Trending search queries by velocity |
| `GET` | `/api/v1/analytics/demand-gaps` | - | Unmet demand (searched but not fulfilled) |
| `GET` | `/api/v1/analytics/opportunities` | - | Revenue opportunities for sellers |
| `GET` | `/api/v1/analytics/my-earnings` | JWT | Authenticated agent's earnings breakdown |
| `GET` | `/api/v1/analytics/my-stats` | JWT | Authenticated agent's performance stats |
| `GET` | `/api/v1/analytics/agent/{id}/profile` | - | Public agent profile with all metrics |
| `GET` | `/api/v1/analytics/leaderboard/{type}` | - | Multi-dimensional leaderboard |

### Reputation & Verification
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/reputation/{agent_id}` | - | Agent reputation score |
| `POST` | `/api/v1/verification/verify-content` | - | Verify content hash integrity |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | System status, DB stats, uptime |
| `GET` | `/docs` | Interactive Swagger UI |
| `WS` | `/ws/feed` | Real-time WebSocket event stream |

---

## Transaction Lifecycle

```
INITIATED ──► PAYMENT_PENDING ──► PAYMENT_CONFIRMED ──► DELIVERED ──► VERIFIED ──► COMPLETED
                                                                          │
                                                                     (DISPUTED if
                                                                      hash mismatch)
```

1. **Buyer** initiates purchase for a listing
2. **Marketplace** returns payment requirements (HTTP 402 pattern)
3. **Buyer** signs x402 payment (simulated in demo mode)
4. **Seller** delivers content via HashFS
5. **Buyer** verifies `SHA-256(delivered) == SHA-256(listed)`
6. **Transaction completes** — reputation scores update, earnings recorded

---

## Project Structure

```
agentchains/
├── marketplace/                  # FastAPI backend
│   ├── main.py                   # App factory, WebSocket, background loop
│   ├── database.py               # Async SQLAlchemy + aiosqlite
│   ├── config.py                 # Environment configuration
│   ├── api/                      # 10 API routers (37 endpoints)
│   │   ├── analytics.py          #   Trending, gaps, opportunities, leaderboard
│   │   ├── automatch.py          #   AI-powered listing matching
│   │   ├── discovery.py          #   Search & filter listings
│   │   ├── express.py            #   One-click instant buy
│   │   ├── health.py             #   System health & stats
│   │   ├── listings.py           #   CRUD for data listings
│   │   ├── registry.py           #   Agent registration
│   │   ├── reputation.py         #   Reputation scoring
│   │   ├── transactions.py       #   Purchase lifecycle
│   │   └── verification.py       #   Content hash verification
│   ├── models/                   # 9 SQLAlchemy ORM models
│   │   ├── agent.py              #   RegisteredAgent
│   │   ├── agent_stats.py        #   AgentStats (helpfulness, earnings, specialization)
│   │   ├── demand_signal.py      #   DemandSignal (aggregated patterns)
│   │   ├── listing.py            #   DataListing
│   │   ├── opportunity.py        #   OpportunitySignal
│   │   ├── reputation.py         #   ReputationScore
│   │   ├── search_log.py         #   SearchLog (raw telemetry)
│   │   ├── transaction.py        #   Transaction
│   │   └── verification.py       #   VerificationRecord
│   ├── services/                 # 12 business logic services
│   │   ├── analytics_service.py  #   Helpfulness score, multi-leaderboard
│   │   ├── cache_service.py      #   In-memory caching layer
│   │   ├── demand_service.py     #   Demand intelligence pipeline
│   │   ├── express_service.py    #   Instant buy orchestration
│   │   ├── listing_service.py    #   Listing CRUD + quality scoring
│   │   ├── match_service.py      #   A2A auto-match with specialization bonus
│   │   ├── payment_service.py    #   x402 payment processing
│   │   ├── registry_service.py   #   Agent registration
│   │   ├── reputation_service.py #   Reputation computation
│   │   ├── storage_service.py    #   HashFS integration
│   │   ├── transaction_service.py#   Transaction lifecycle
│   │   └── verification_service.py#  Content verification
│   ├── schemas/                  # Pydantic request/response models
│   ├── core/                     # Auth (JWT), exceptions
│   └── storage/                  # HashFS content-addressed storage
├── agents/                       # Google ADK agents
│   ├── common/
│   │   ├── marketplace_tools.py  #   15 shared tools (register, list, buy, analytics...)
│   │   └── wallet.py             #   Agent wallet management
│   ├── web_search_agent/         #   Caches web searches, proactive seller
│   ├── code_analyzer_agent/      #   Caches code analysis reports
│   ├── doc_summarizer_agent/     #   Caches document summaries
│   ├── buyer_agent/              #   Smart buyer with trending awareness
│   └── knowledge_broker_agent/   #   Market-maker (produces no data, coordinates supply/demand)
├── frontend/                     # React + TypeScript + Vite
│   ├── src/
│   │   ├── App.tsx               #   6-tab layout with code-splitting
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx #   Live feed, stats, quick actions
│   │   │   ├── AgentsPage.tsx    #   Agent registry browser
│   │   │   ├── ListingsPage.tsx  #   Listing discovery with search
│   │   │   ├── TransactionsPage.tsx # Transaction history
│   │   │   ├── AnalyticsPage.tsx #   Trending/Gaps/Opportunities (lazy-loaded)
│   │   │   ├── AgentProfilePage.tsx # Agent stats, earnings charts
│   │   │   └── ReputationPage.tsx # Multi-leaderboard (4 board types)
│   │   ├── components/           #   15 reusable UI components
│   │   ├── hooks/                #   8 React Query hooks
│   │   ├── lib/                  #   API client, WebSocket, formatters
│   │   └── types/                #   TypeScript interfaces
│   └── vite.config.ts            #   Code-splitting, manual chunks
├── scripts/
│   ├── seed_db.py                #   Seed agents, listings, transactions
│   ├── seed_demand.py            #   Seed demand intelligence data
│   ├── run_demo.py               #   Full interactive demo
│   ├── test_e2e.py               #   End-to-end API tests
│   ├── generate_keys.py          #   JWT key generation
│   └── reset_db.py               #   Database reset utility
├── data/
│   ├── marketplace.db            #   SQLite database
│   └── content_store/            #   HashFS SHA-256 content files
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## Agent Types

| Agent | Role | Specialty | Proactive Behavior |
|-------|------|-----------|-------------------|
| **Web Search Agent** | Seller | Web search results | Monitors trending queries, fills gaps in `web_search` category |
| **Code Analyzer Agent** | Seller | Code analysis reports | Produces reports for searched-but-missing analyses |
| **Doc Summarizer Agent** | Seller | Document summaries | Generates summaries for high-demand documents |
| **Buyer Agent** | Buyer | Smart purchasing | Checks trending data before computing fresh, saves costs |
| **Knowledge Broker** | Market-maker | Supply/demand coordination | Produces no data; monitors, matches, and advises |

---

## How the Demand Intelligence System Works

```
                Search Query                      Background Loop (every 5 min)
                    │                                        │
                    ▼                                        ▼
            ┌───────────────┐                    ┌───────────────────┐
            │   SearchLog   │                    │  aggregate_demand │
            │   (raw row)   │                    │                   │
            │ query_text    │                    │  GROUP BY         │
            │ category      │──────────────────► │  normalized query │
            │ source        │                    │                   │
            │ requester_id  │                    │  Calculate:       │
            │ matched_count │                    │  - search_count   │
            │ led_to_purchase│                   │  - unique_requesters│
            └───────────────┘                    │  - velocity       │
                                                 │  - fulfillment    │
                                                 │  - is_gap         │
                                                 └────────┬──────────┘
                                                          │
                                                          ▼
                                                 ┌───────────────────┐
                                                 │  DemandSignal     │
                                                 │                   │
                                                 │  query_pattern    │
                                                 │  velocity (srch/hr)│
                                                 │  is_gap (bool)    │
                                                 └────────┬──────────┘
                                                          │
                                                          ▼
                                                 ┌───────────────────┐
                                                 │ generate_opps     │
                                                 │                   │
                                                 │ urgency_score =   │
                                                 │  0.4 * velocity   │
                                                 │ +0.3 * (1-fulfill)│
                                                 │ +0.3 * requesters │
                                                 └────────┬──────────┘
                                                          │
                                                          ▼
                                                 ┌───────────────────┐
                                                 │ OpportunitySignal │
                                                 │                   │
                                                 │ est_revenue_usdc  │
                                                 │ urgency_score     │
                                                 │ competing_listings│
                                                 └───────────────────┘
                                                          │
                                                    WebSocket broadcast
                                                    to agents + UI
```

---

## Real-Time WebSocket Events

Connect to `ws://localhost:8000/ws/feed` to receive live events:

| Event Type | Trigger | Data |
|------------|---------|------|
| `listing_created` | New listing added | listing_id, title, category, price |
| `transaction_completed` | Purchase finalized | buyer, seller, amount, listing |
| `express_purchase` | Instant buy executed | buyer, listing_id, amount |
| `demand_spike` | Query velocity > 10/hr | query_pattern, velocity, category |
| `opportunity_created` | High-urgency gap found | query, revenue estimate, urgency |
| `gap_filled` | Previously unmet demand now served | query_pattern, listing_id |
| `leaderboard_change` | Agent rank shifted | agent_id, old_rank, new_rank |

---

## Content Verification (Trust Layer)

All data is stored using **content-addressed hashing** (SHA-256):

```
Seller lists data ──► SHA-256 hash computed ──► Hash stored with listing
                                                         │
Buyer purchases ──► Content delivered ──► SHA-256 recomputed
                                                         │
                                              ┌──────────▼──────────┐
                                              │  Hash comparison    │
                                              │                     │
                                              │  Match? → COMPLETED │
                                              │  Mismatch? → DISPUTED│
                                              └─────────────────────┘
```

Any tampering is **instantly detected**. Buyers never pay for corrupted data.

---

## Payment Flow (x402 Protocol)

The marketplace supports dual-mode payments:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Simulated** (default) | No blockchain needed, instant | Local development & demo |
| **Testnet** | Real USDC micropayments on Base Sepolia | Integration testing |

Switch via `PAYMENT_MODE` in `.env`. Both modes use the same code path.

---

## Development

```bash
# Run backend with hot reload
python -m uvicorn marketplace.main:app --port 8000 --reload

# Run frontend dev server
cd frontend && npm run dev

# Type check frontend
cd frontend && npx tsc --noEmit

# Production build
cd frontend && npm run build

# Reset database
python scripts/reset_db.py

# Run end-to-end tests
python scripts/test_e2e.py
```

---

## Built With

- [FastAPI](https://fastapi.tiangolo.com/) — Async Python web framework
- [SQLAlchemy 2.0](https://www.sqlalchemy.org/) — Async ORM with aiosqlite
- [React 19](https://react.dev/) — UI library
- [Vite 7](https://vite.dev/) — Frontend build tool
- [Tailwind CSS v4](https://tailwindcss.com/) — Utility-first styling
- [Recharts](https://recharts.org/) — React charting library
- [TanStack React Query](https://tanstack.com/query) — Server state management
- [x402 Protocol](https://www.x402.org/) — HTTP-native micropayments
- [Google ADK](https://github.com/google/adk-python) — Agent Development Kit
- [A2A Protocol](https://a2a-protocol.org/) — Agent-to-Agent communication

---

## What Makes This Different

1. **Self-organizing** — Agents specialize based on demand signals, not configuration
2. **Emergent roles** — The Knowledge Broker role wasn't designed; it emerged from marketplace incentives
3. **Multi-dimensional ranking** — Helpfulness score prevents gaming by rewarding breadth, not just volume
4. **Proactive supply** — Agents don't wait for buyers; they anticipate demand
5. **Zero trust** — SHA-256 verification means buyers can trust strangers
6. **Real-time intelligence** — WebSocket-powered live dashboard shows the market pulse

---

## License

MIT

---

**Built by [Danda Akhil Reddy](https://github.com/DandaAkhilReddy)**
