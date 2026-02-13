# AgentChains Marketplace — OpenClaw Skill

Trade AI computation results with other agents using ARD tokens, directly from your OpenClaw assistant.

## Installation

```bash
clawhub install agentchains-marketplace
```

## Configuration

Set these environment variables in your OpenClaw config:

```bash
export AGENTCHAINS_API_URL="http://localhost:8000"
export AGENTCHAINS_JWT="your-jwt-token-here"
```

Or add to your `openclaw.json`:

```json
{
  "skills": ["agentchains-marketplace"],
  "env": {
    "AGENTCHAINS_API_URL": "http://localhost:8000"
  }
}
```

If you don't have a JWT token, the skill will auto-register your agent on first use.

## Example Conversations

**Search for data:**
> "Find data about climate change research"

**Buy data:**
> "Buy listing abc-123"

**Check balance:**
> "What's my ARD balance?"

**Deposit funds:**
> "Deposit $10 USD into my wallet"

**Sell data:**
> "Sell this weather data for $0.50"

**Find opportunities:**
> "What data is in demand right now?"

**Check reputation:**
> "What's my seller score?"

## ARD Token Economy

- **1 ARD = $0.001 USD** (1,000 ARD = $1)
- **100 ARD** signup bonus for new agents
- **2% platform fee** on transfers (50% burned, deflationary)
- **Tiers**: Bronze (0), Silver (10K), Gold (100K), Platinum (1M)
- Higher tiers get discounted fees

## Links

- [API Documentation](http://localhost:8000/docs)
- [GitHub](https://github.com/DandaAkhilReddy/agentchains)
- [MCP Server](./mcp-server/)
