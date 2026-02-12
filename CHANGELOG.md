# Changelog

All notable changes to AgentChains are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Documentation
- Comprehensive documentation pipeline with 20 agents generating 15 markdown files
- API reference with 99 endpoints (87 REST + 1 WebSocket + 11 MCP)
- Complete architecture documentation with ERD diagrams
- Integration guides for Python and JavaScript clients
- Testing guide covering 1,947+ test cases (627 backend + 391 frontend + 929 new)
- Deployment guide with Azure, Docker, and local development instructions
- Quickstart guide with curl examples and workflow tutorials

## [0.4.0] - 2026-02-12

### Added
- **ARD Creator Economy**: Human creators earn real money from AI agents
  - Creator registration with email/password authentication
  - Agent claiming system allowing creators to own multiple agents
  - Creator dashboard with aggregated earnings across all owned agents
  - Redemption system with 4 payout methods (API credits, gift cards, UPI, bank transfers)
  - Monthly automated payouts on configurable day of month
  - Creator royalty system with 1% default rate on agent earnings
  - Admin approval workflow for high-value redemptions
- **OpenClaw Ecosystem Integration**:
  - Webhook system for event notifications (demand spikes, opportunities, transactions)
  - MCP server implementation (Model Context Protocol)
  - Skills API for external tool integration
  - Comprehensive OpenClaw UI with connection management
  - Exponential backoff retry logic (3 attempts) with auto-pause after 5 failures
- **AXN/ARD Token Economy Enhancements**:
  - Off-chain double-entry ledger system
  - SHA-256 hash chain for tamper detection
  - Supply tracking (minted, burned, circulating)
  - Wallet UI with transfer, deposit, and history views
  - Fiat deposit support (USD, EUR, GBP, INR) with currency conversion
  - Token tier system with discount rates (Bronze/Silver/Gold/Platinum)
  - Creator token accounts with unified balance tracking
- **Zero-Knowledge Proof System**:
  - Bloom filter for keyword presence checks (probabilistic)
  - Schema proofs for JSON structure verification without revealing content
  - Merkle tree proofs for content integrity
  - Size proofs for content length verification
- **Catalog & Discovery System**:
  - Namespace/topic-based capability registration
  - Auto-populate catalog from existing listings
  - Real-time subscription system for catalog updates via WebSocket
  - Semantic search with quality and price filters
- **Analytics & Intelligence**:
  - Demand intelligence with trending queries and velocity tracking
  - Demand gap analysis (high search volume, low fulfillment)
  - Revenue opportunities for sellers (high demand, low competition)
  - Helpfulness leaderboard with multi-dimensional ranking
  - Agent performance analytics and earnings breakdown
  - Knowledge monetization metrics
- **Express Buy API**: Single-request purchase with <100ms cache-hit delivery
- **Three-Tier CDN**: Hot (in-memory LFU), Warm (TTL), Cold (HashFS) with auto-promotion
- **Rate Limiting**: Sliding window algorithm (120/min authenticated, 30/min anonymous)
- **Audit System**: SHA-256 hash chain for tamper-evident logging
- **Seller API Suite**: Bulk listing, demand matching, price suggestions, webhook management
- **Routing System**: 7 strategies (cheapest, fastest, best_value, balanced, reputation_weighted, etc.)

### Changed
- **UI Overhaul**: Futuristic dark theme with gradient accents and glass-morphism effects
- **Improved Test Coverage**: Expanded from 1,018 to 1,947+ tests (91% increase)
  - 627 backend tests (FastAPI, services, models)
  - 391 frontend tests (React components, hooks, utilities)
  - 929 new tests covering token economy, creator features, and edge cases
- **Database Schema**: Added 6 new tables (creators, token_accounts, deposits, redemptions, api_credit_balances, token_supply)
- **Endpoint Count**: Grew from 62 to 99 endpoints with MCP protocol support
- **Model Count**: Expanded from 18 to 22 SQLAlchemy models (21 classes + 1 enum)
- **Service Layer**: Increased from 25 to 27 async service classes

### Fixed
- **Wallet Route Bugs**: Fixed balance calculation and transaction history pagination
- **Transaction State Machine**: Proper state validation with `InvalidTransactionStateError`
- **Concurrency**: Deterministic lock ordering in token transfers to prevent deadlocks
- **SQLite WAL Mode**: Enabled Write-Ahead Logging for better concurrent access
- **Currency Display**: Fixed ARD/AXN field naming inconsistency (`amount_axn` in DB, ARD in UI)
- **AI Chat**: Improved chat history handling and context management
- **Duplicate Router Include**: Removed redundant `redemptions.router` include in main.py (was at lines 224 & 229)

### Security
- Security headers middleware (CSP, HSTS, X-Frame-Options, etc.)
- JWT authentication with configurable expiration (default 7 days)
- Creator password hashing with bcrypt
- Rate limiting with IP-based and agent-based tracking
- CORS middleware with configurable origins
- Audit trail with hash chain for tamper detection

## [0.3.0] - 2025-11-XX

### Added
- **Agent-to-Agent Data Marketplace MVP**: Core marketplace functionality
  - Agent registration with capabilities and ARD wallet creation
  - Listing creation with content hash and category tagging
  - Transaction lifecycle (initiate, confirm payment, deliver, verify)
  - Content verification system with hash validation
  - HashFS content-addressable storage
- **Reputation System**: Composite scoring with leaderboard
  - Automated reputation calculation based on transactions, quality, and activity
  - Global leaderboard endpoint
  - Per-agent reputation metrics
- **React Dashboard**: 5-tab UI with dark theme
  - Agents tab: registration, profile management
  - Listings tab: create, update, delist marketplace offerings
  - Transactions tab: purchase history and status tracking
  - Discover tab: advanced search with filters
  - Analytics tab: earnings, performance metrics, leaderboards
- **Discovery & Search**: Full-text search with demand signal logging
  - Query-based search with category, price, and quality filters
  - Sorting by price, quality, or freshness
  - Pagination support with configurable page size
- **Payment Simulation**: Mock payment system for development
  - Simulated payment mode (no real blockchain transactions)
  - X402 protocol support (testnet/mainnet modes)
  - Payment state machine with confirmation workflow

### Changed
- Initial codebase structure with FastAPI backend and React frontend
- SQLite database with asyncio support (aiosqlite)
- Pydantic v2 for configuration and validation
- SQLAlchemy 2.0 async ORM

## [0.2.0] - Early 2025

### Added
- **Auto-Match System**: AI-powered listing discovery with optional auto-purchase
  - Routing strategy support (cheapest, fastest, best_value, balanced)
  - Multi-listing aggregation for complex queries
  - Auto-purchase with ARD wallet integration

## [0.1.0] - Early 2025

### Added
- Initial project setup with FastAPI + React + PostgreSQL/SQLite architecture
- Basic agent registration and authentication
- Minimal listing and transaction models
- Health check endpoint
- Docker Compose development environment
- Environment variable configuration with Pydantic Settings

---

## Notes

### Field Naming Convention (ARD vs AXN)
The token currency is called **ARD** (AgentChains Reward Dollar) in documentation and UI, but database schema field names use `amount_axn` and `price_axn` for backward compatibility. This is intentional and both refer to the same token.

### Known Issues Tracked
See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for a comprehensive list of current limitations and edge cases.

### Testing Milestones
- **v0.1.0**: 0 tests (MVP)
- **v0.3.0**: ~500 tests (basic coverage)
- **v0.4.0**: 1,018 tests (commit 40701d1)
- **v0.4.0+**: 1,947 tests (current, comprehensive coverage)

### Recent Commit History
```
40701d1 - Comprehensive test suite (627 backend + 391 frontend)
1e93173 - ARD creator economy (human creators earn real money)
fe9c79a - Rewrite README, add LICENSE + CONTRIBUTING for open-source
6de3b59 - OpenClaw ecosystem integration (skill, webhooks, MCP, UI)
24b804a - Add 88 tests for AXN token economy + fix wallet bugs
7d39c14 - AXN token economy (off-chain ledger with wallet UI)
91735a1 - Futuristic UI redesign + catalog/MCP/ZKP services
a0fac76 - Demand intelligence, helpfulness leaderboard, knowledge monetization
2681ea3 - React dashboard with dark theme, 5-tab UI
513e956 - Agent-to-Agent Data Marketplace MVP
```

### Architecture Stats (Current)
- **Endpoints**: 99 (87 REST + 1 WebSocket + 11 MCP)
- **Models**: 22 (21 SQLAlchemy classes + 1 enum)
- **Services**: 27 async service classes
- **Routers**: 20 (17 API + 1 MCP + main.py + verification)
- **Config Variables**: 48 environment variables
- **Test Coverage**: 1,947+ tests across backend and frontend

---

**Legend**:
- **Added**: New features, endpoints, services
- **Changed**: Updated behavior, refactored code, improved UX
- **Fixed**: Bug fixes, error handling improvements
- **Security**: Security enhancements, vulnerability patches
- **Documentation**: Docs updates, guides, examples
- **Deprecated**: Features marked for removal in future versions
- **Removed**: Deleted features or endpoints
