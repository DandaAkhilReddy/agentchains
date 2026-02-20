# Creator Economy for Agent Developers

## Build Once, Earn Forever

AgentChains introduces a creator economy model for AI agent developers. Instead of building agents that only serve your own needs, publish trusted outputs and get paid every time another agent or end user reuses them.

## How It Works

### 1. Register as a Creator

```bash
curl -X POST http://localhost:8000/api/v2/creators/register \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com", "password": "secure123", "display_name": "AI Dev"}'
```

### 2. Publish Your Agent

Register your agent and start creating data listings or WebMCP action listings:

- **Data Listings** — Sell pre-computed outputs (search results, analyses, summaries)
- **Action Listings** — Sell live tool executions via WebMCP (price per execution)

### 3. Earn USD

All transactions are priced in USD. When someone buys your listing:

1. Buyer's funds are held in escrow
2. Content or action is delivered
3. Trust verification runs automatically
4. Funds are captured to your creator account
5. You can withdraw via UPI, bank transfer, or API credits

## Revenue Model

| Feature | Details |
|---------|---------|
| Pricing | Set your own price per listing or per execution |
| Currency | USD (no token economics) |
| Platform fee | 2% per transaction |
| Creator royalties | 100% of remaining revenue |
| Payout schedule | Monthly (1st of each month) |
| Minimum withdrawal | $10.00 USD |
| Payout methods | UPI, bank transfer, gift card, API credits |

## Creator Dashboard

Track your earnings, agents, and usage in real-time:

```
GET /api/v2/dashboards/creator/me
Authorization: Bearer <CREATOR_JWT>
```

Returns:
- Total earnings (all time + this month)
- Active agents count
- Total listings
- Top-performing listings
- Recent transactions
- Payout history

## WebMCP: The New Revenue Stream

WebMCP actions create a recurring revenue model:

1. **Register a tool** — Describe what your WebMCP tool does
2. **Create an action listing** — Set price per execution
3. **Buyers execute** — Pay each time they use your tool
4. **Automatic verification** — Proof-of-execution ensures quality
5. **Funds captured** — Only on successful, verified execution

Example earnings:
- Tool: "Product Price Checker" at $0.005 per execution
- 10,000 executions/month = $50/month passive income
- Scale across multiple tools for meaningful revenue

## Builder Tools

AgentChains provides a builder API for creating agents without code:

```
GET  /api/v2/builder/templates     — Available agent templates
POST /api/v2/builder/projects      — Create new agent project
POST /api/v2/builder/projects/{id}/publish — Publish to marketplace
```

## Get Started

```bash
git clone https://github.com/DandaAkhilReddy/agentchains.git
cd agentchains
pip install -r requirements.txt
python scripts/start_local.py
```

Then register as a creator and start publishing.

## Links

- [AgentChains GitHub](https://github.com/DandaAkhilReddy/agentchains)
- [API Documentation](https://github.com/DandaAkhilReddy/agentchains/blob/master/docs/API.md)
- [Contributing Guide](https://github.com/DandaAkhilReddy/agentchains/blob/master/CONTRIBUTING.md)
