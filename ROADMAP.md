# AgentChains Roadmap

Public roadmap for AgentChains development. Updated monthly.

## Current: v0.5.0 (WebMCP Integration)

- 94+ REST API endpoints (v1 + v2 + v3)
- MCP protocol server (11 tools, 5 resources)
- 4-stage trust verification pipeline
- Creator economy with USD-first billing
- Dual-layer marketplace (builders + buyers)
- Real-time WebSocket event streaming
- WebMCP tool registration, discovery, and execution
- Proof-of-execution with JWT signatures
- A2A protocol server + client SDK + pipeline composition
- 2,454+ backend tests, 376+ frontend tests
- Azure Container Apps deployment

## Completed: WebMCP Integration (v0.5.0)

- [x] WebMCP tool registration and discovery
- [x] ActionListing model (executable actions as marketplace items)
- [x] Proof-of-execution with JWT signatures
- [x] v3 API namespace for WebMCP endpoints (12 endpoints)
- [x] 3 new MCP tools for WebMCP operations
- [x] Frontend Actions tab with dynamic execution forms
- [x] Domain Lock and Tool Lock security
- [x] 85 new WebMCP tests

## Completed: A2A Protocol (v0.6.0)

- [x] A2A server implementation (`.well-known/agent.json`)
- [x] A2A client SDK for agent-to-agent communication
- [x] Agent composition (chain multiple agents into pipelines)
- [x] Demo agents (WebMCP shopping, research)
- [x] 4 blog posts (WebMCP costs, A2A marketplace, trust verification, creator economy)

## Completed: Production Hardening (v0.7.0)

- [x] OpenAPI/Swagger documentation with rich metadata and tag descriptions
- [x] OpenAPI schema export script (`scripts/export_openapi.py`)
- [x] Stripe payment integration stub with simulated mode
- [x] Razorpay payment integration stub with UPI payouts
- [x] Redis-backed sliding window rate limiter for multi-instance
- [x] Alembic migration framework with async engine support
- [x] OpenTelemetry opt-in tracing (FastAPI, HTTPX, SQLAlchemy)
- [x] Performance benchmark script (`scripts/benchmark.py`)

## Q2 2026: Community & Launch (v1.0.0)

- [ ] ProductHunt and HackerNews launch
- [ ] Discord community
- [ ] Video tutorials and walkthroughs
- [ ] Docker sandbox isolation for action execution

## Q3 2026: Scale

- [ ] Real Stripe/Razorpay payment activation (remove stubs)
- [ ] Multi-region deployment support
- [ ] Kubernetes Helm chart

## How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started. Check [open issues](https://github.com/DandaAkhilReddy/agentchains/issues) for tasks you can pick up.
