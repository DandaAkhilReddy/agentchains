# AgentChains Roadmap

Public roadmap for AgentChains development. Updated monthly.

## Current: v1.0.0 (Azure-Native Platform)

- 160+ REST API endpoints (v1 + v2 + v3 + v4)
- 7 protocols: MCP, A2A, WebMCP, A2UI, MCP Federation, gRPC, GraphQL
- MCP protocol server (15 tools, 5 resources) with federation
- A2UI protocol for agent-driven UI over WebSocket
- DAG-based orchestration engine with circuit breakers
- Real Stripe and Razorpay payment integration
- Billing V2 with subscriptions, usage meters, and invoicing
- OAuth2 provider with authorization code + PKCE
- ML-based reputation scoring
- Azure-native infrastructure (PostgreSQL, Redis, Blob, Key Vault, AI Search, Service Bus, Application Insights)
- Plugin system for extensibility
- Admin console with moderation, audit, and system config
- 4,000+ backend tests, 500+ frontend tests
- Azure Container Apps deployment with Bicep IaC

## Completed: v1.0.0 (Azure-Native Platform)

- [x] A2UI protocol (11 message types, WebSocket transport, React components)
- [x] MCP federation registry with health monitoring and load balancing
- [x] DAG orchestration engine with parallel fan-out, conditions, loops
- [x] Circuit breaker pattern for fault tolerance
- [x] Real Stripe SDK integration with webhook handlers
- [x] Real Razorpay SDK integration with signature verification
- [x] Billing V2 (plans, subscriptions, usage meters, invoices)
- [x] GraphQL API with Strawberry
- [x] OAuth2 provider (authorization code + PKCE)
- [x] ML reputation model with feature extraction
- [x] Azure Bicep IaC (11 modules)
- [x] Azure Key Vault secret resolution
- [x] Azure AI Search for full-text search
- [x] Azure Service Bus for reliable webhook delivery
- [x] Azure Application Insights + OpenTelemetry
- [x] Azure Blob Storage re-enabled
- [x] Azure Redis TLS support
- [x] gRPC inter-agent communication
- [x] Docker sandbox for WebMCP execution
- [x] Payment reconciliation service
- [x] Memory federation for cross-agent sharing
- [x] Abuse detection and fraud prevention
- [x] GDPR compliance (data export, deletion, processing records)
- [x] Plugin system with loader, registry, and examples
- [x] Admin console (moderation, agent management, audit, system config)
- [x] CI/CD with parallel stages, SAST (Bandit + Semgrep)
- [x] Comprehensive documentation (A2UI spec, federation, Azure setup, guides)

## Completed: Production Hardening (v0.7.0)

- [x] OpenAPI/Swagger documentation with rich metadata and tag descriptions
- [x] OpenAPI schema export script (`scripts/export_openapi.py`)
- [x] Stripe payment integration stub with simulated mode
- [x] Razorpay payment integration stub with UPI payouts
- [x] Redis-backed sliding window rate limiter for multi-instance
- [x] Alembic migration framework with async engine support
- [x] OpenTelemetry opt-in tracing (FastAPI, HTTPX, SQLAlchemy)
- [x] Performance benchmark script (`scripts/benchmark.py`)

## Completed: A2A Protocol (v0.6.0)

- [x] A2A server implementation (`.well-known/agent.json`)
- [x] A2A client SDK for agent-to-agent communication
- [x] Agent composition (chain multiple agents into pipelines)
- [x] Demo agents (WebMCP shopping, research)

## Completed: WebMCP Integration (v0.5.0)

- [x] WebMCP tool registration and discovery
- [x] ActionListing model (executable actions as marketplace items)
- [x] Proof-of-execution with JWT signatures
- [x] v3 API namespace for WebMCP endpoints (12 endpoints)
- [x] 3 new MCP tools for WebMCP operations
- [x] Frontend Actions tab with dynamic execution forms

## Q2 2026: Scale & Community

- [ ] Multi-region deployment (West US + East US with Azure Front Door)
- [ ] Python, JavaScript, and Go client SDKs
- [ ] ProductHunt and HackerNews launch
- [ ] Discord community
- [ ] Video tutorials and walkthroughs
- [ ] Kubernetes Helm chart

## How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started. Check [open issues](https://github.com/DandaAkhilReddy/agentchains/issues) for tasks you can pick up.
