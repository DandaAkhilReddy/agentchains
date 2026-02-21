# MCP Federation Protocol

## Overview

MCP Federation extends the Model Context Protocol to aggregate tools and resources from multiple MCP servers. A central registry tracks servers, and the marketplace transparently routes tool calls to the appropriate server based on namespace prefixes.

## Architecture

```
Client -> AgentChains MCP Server -> Federation Handler
                                        |
                +-----------+-----------+-----------+
                |           |           |           |
            Server A    Server B    Server C    Local Tools
            (weather)   (code)      (search)    (marketplace)
```

## Server Registration

Register an MCP server via REST API:

```
POST /api/v3/federation/servers
{
  "name": "weather-tools",
  "base_url": "https://weather-mcp.example.com",
  "namespace": "weather",
  "auth_type": "bearer",
  "auth_credential_ref": "keyvault:weather-api-key"
}
```

## Namespaced Tools

When `tools/list` is called, the federation handler:
1. Collects tools from all active federated servers
2. Prefixes each tool name with its namespace: `weather.get_forecast`
3. Merges with local marketplace tools (no prefix)
4. Returns the unified tool list

## Tool Call Routing

When `tools/call` receives a namespaced tool:
1. Parse namespace prefix from tool name
2. Look up the server for that namespace
3. Forward the call to the server's MCP endpoint
4. Return the result to the client

## Health Monitoring

- Background task pings each server every 30 seconds
- Health score: 0-100 (increases on success, decreases on failure)
- States: `active` (score > 50), `degraded` (20-50), `inactive` (< 20)

## Load Balancing

When multiple servers share a namespace:
- `health_first` — Pick healthiest server (default)
- `round_robin` — Rotate between servers
- `least_loaded` — Pick server with fewest active requests
- `weighted` — Random selection weighted by health score
