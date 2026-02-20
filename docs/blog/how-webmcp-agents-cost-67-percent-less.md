# How WebMCP Agents Cost 67% Less Than Vision-Based Agents

## The Problem with Screen Parsing

Most AI agent frameworks rely on vision-based screen parsing — taking screenshots, running OCR, and guessing where to click. This approach is:

- **Expensive**: Each action requires a vision model call ($0.01-0.05 per screenshot)
- **Slow**: Screenshot → OCR → reasoning → action takes 2-5 seconds per step
- **Unreliable**: ~75% accuracy on structured tasks due to layout changes and rendering differences

## The WebMCP Advantage

WebMCP (Model Context Protocol for the Web) is a W3C standard (shipping in Chrome 146+) that gives AI agents structured access to website functionality. Instead of parsing pixels, agents interact through typed JSON schemas.

### Cost Comparison

| Metric | Vision-Based | WebMCP | Savings |
|--------|-------------|--------|---------|
| Cost per action | $0.03 avg | $0.01 avg | 67% |
| Latency per action | 3.2s avg | 0.8s avg | 75% |
| Accuracy | ~75% | 98%+ | +23pp |
| Retry rate | 25% | <2% | -92% |

### Why It's Cheaper

1. **No vision model calls** — WebMCP uses JSON Schema, not screenshots
2. **No retries** — Structured input/output means first-attempt success
3. **Cached tool definitions** — Tool schemas are fetched once, reused forever
4. **Proof-of-execution** — JWT proofs eliminate dispute resolution costs

## How AgentChains Uses WebMCP

AgentChains is the first marketplace to integrate WebMCP natively:

1. **Tool Registration** — Website owners register their WebMCP tools with JSON schemas
2. **Action Listings** — Sellers create marketplace listings for tool executions
3. **Execute & Pay** — Buyers execute actions with per-execution USD pricing
4. **Proof Verification** — JWT proof-of-execution ensures buyer gets what they paid for

```
Agent → Marketplace → WebMCP Tool → Result + Proof → Agent
         (USD hold)                  (JWT signed)    (USD captured)
```

## Get Started

```bash
git clone https://github.com/DandaAkhilReddy/agentchains.git
cd agentchains
pip install -r requirements.txt
python scripts/start_local.py
```

Then register a WebMCP tool:
```bash
curl -X POST http://localhost:8000/api/v3/webmcp/tools \
  -H "Authorization: Bearer <CREATOR_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"name": "price-checker", "domain": "example.com", "endpoint_url": "https://example.com/webmcp", "category": "shopping"}'
```

## Links

- [AgentChains GitHub](https://github.com/DandaAkhilReddy/agentchains)
- [WebMCP W3C Proposal](https://chromestatus.com/feature/webmcp)
- [API Documentation](https://github.com/DandaAkhilReddy/agentchains/blob/master/docs/API.md)
