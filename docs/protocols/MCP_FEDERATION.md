# MCP Federation Protocol

Aggregate tools from multiple MCP servers into a unified namespace with health-aware routing and automatic discovery.

---

## 1. Overview

MCP Federation extends the AgentChains MCP server to transparently route tool calls across multiple federated MCP servers. Agents interact with a single MCP endpoint while the federation layer handles server registration, tool discovery, namespace routing, health monitoring, and load balancing.

```
Agent
  |
  v
AgentChains MCP Gateway
  |
  +---> Local Tools (11 built-in)
  |
  +---> Federated Server A (namespace: "weather")
  |       - weather.get_forecast
  |       - weather.get_alerts
  |
  +---> Federated Server B (namespace: "finance")
  |       - finance.get_quote
  |       - finance.analyze_trend
  |
  +---> Federated Server C (namespace: "search")
          - search.web
          - search.academic
```

---

## 2. Architecture

### 2.1 Components

| Component | Location | Responsibility |
|-----------|----------|---------------|
| Federation Handler | `marketplace/mcp/federation_handler.py` | Merges local and federated tools; routes tool calls |
| Federation Service | `marketplace/services/mcp_federation_service.py` | Server CRUD, tool discovery, health management |
| MCPServerEntry Model | `marketplace/models/mcp_server.py` | Database model for registered servers |
| MCP Gateway | `marketplace/mcp/server.py` | JSON-RPC router that delegates to federation handler |

### 2.2 Data Model

The `MCPServerEntry` table (`mcp_servers`) stores registered federated servers:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (string 36) | Primary key |
| `name` | string(100) | Unique human-readable name |
| `base_url` | string(500) | Server's base URL (e.g., `https://weather-mcp.example.com`) |
| `namespace` | string(100) | Tool namespace prefix (e.g., `weather`) |
| `description` | text | Server description |
| `tools_json` | text | Cached JSON array of tool definitions |
| `resources_json` | text | Cached JSON array of resource definitions |
| `health_score` | integer | 0-100 health score (default: 100) |
| `last_health_check` | datetime | Timestamp of last health check |
| `status` | string(20) | `active`, `degraded`, or `inactive` |
| `auth_type` | string(20) | `none`, `bearer`, or `api_key` |
| `auth_credential_ref` | string(200) | Credential value or Key Vault reference |
| `registered_by` | string(36) | Agent ID that registered the server |
| `created_at` | datetime | Registration timestamp |
| `updated_at` | datetime | Last update timestamp |

Database indexes: `idx_mcp_servers_namespace`, `idx_mcp_servers_status`.

---

## 3. Server Registration and Discovery

### 3.1 Register a Server

```python
from marketplace.services.mcp_federation_service import register_server

server = await register_server(
    db=db,
    name="Weather MCP Server",
    base_url="https://weather-mcp.example.com",
    namespace="weather",
    description="Provides weather forecasts and alerts",
    auth_type="bearer",
    auth_credential_ref="sk-weather-abc123",
    registered_by=agent_id,
)
```

### 3.2 REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v4/federation/servers` | Register a new server |
| GET | `/api/v4/federation/servers` | List all registered servers (filterable by namespace, status) |
| GET | `/api/v4/federation/servers/{id}` | Get server details |
| DELETE | `/api/v4/federation/servers/{id}` | Unregister a server |
| POST | `/api/v4/federation/servers/{id}/refresh` | Refresh server's tool cache |
| GET | `/api/v4/federation/tools` | List all federated tools (merged with local) |

**Register a server (REST):**

```http
POST /api/v4/federation/servers
Authorization: Bearer <agent_token>
Content-Type: application/json

{
  "name": "weather-tools",
  "base_url": "https://weather-mcp.example.com",
  "namespace": "weather",
  "description": "Weather data tools",
  "auth_type": "bearer",
  "auth_credential_ref": "keyvault:weather-api-key"
}
```

### 3.3 List Servers

```python
from marketplace.services.mcp_federation_service import list_servers

# All servers
servers = await list_servers(db)

# Filter by namespace
weather_servers = await list_servers(db, namespace="weather")

# Filter by status
active_servers = await list_servers(db, status="active")
```

### 3.4 Unregister a Server

```python
from marketplace.services.mcp_federation_service import unregister_server

deleted = await unregister_server(db, server_id="550e8400-...")
# Returns True if found and deleted, False otherwise
```

### 3.5 Discover Tools

The `discover_tools()` function aggregates tools from all active servers:

1. Query all `MCPServerEntry` records with `status = "active"`.
2. Parse `tools_json` from each server (cached from last refresh).
3. Prefix each tool name with the server's namespace (e.g., `weather.get_forecast`).
4. Attach `_server_id` and `_namespace` metadata to each federated tool.
5. Return the combined list.

```python
from marketplace.services.mcp_federation_service import discover_tools

# All federated tools
tools = await discover_tools(db)

# Tools from a specific namespace only
weather_tools = await discover_tools(db, namespace="weather")
```

### 3.6 Refresh Server Tools

To update the cached tool list from a remote server:

```python
from marketplace.services.mcp_federation_service import refresh_server_tools

result = await refresh_server_tools(db, server_id="...")
# Success: {"tools": [...], "count": 5}
# Error:   {"error": "HTTP 503", "server_id": "..."}
```

The refresh operation:
1. Sends a POST request to `{base_url}/tools/list` with auth headers.
2. Parses the response and updates `tools_json` in the database.
3. Updates `health_score` to 100 and `status` to `active` on success.
4. Degrades `health_score` by 20 (HTTP error) or 30 (connection error) on failure.

---

## 4. Namespaced Tool Routing

### 4.1 Routing Logic

When an agent calls a tool, the federation handler inspects the tool name:

- **Contains a dot** (e.g., `weather.get_forecast`): Treated as a federated tool. The namespace prefix is extracted, the target server is located, and the call is forwarded.
- **No dot** (e.g., `search_listings`): Treated as a local tool and executed directly by `execute_tool()`.

```python
from marketplace.mcp.federation_handler import handle_federated_tool_call

result = await handle_federated_tool_call(
    db=db,
    tool_name="weather.get_forecast",
    arguments={"city": "Seattle", "days": 5},
    agent_id="agent-123",
)
```

### 4.2 Tool Call Flow

```
Agent calls "weather.get_forecast"
  |
  v
Federation Handler (handle_federated_tool_call)
  |-- Detects "." in tool name
  |-- Split: namespace="weather", tool="get_forecast"
  |
  v
Query MCPServerEntry WHERE namespace="weather" AND status="active"
  |
  v
Select server with highest health_score
  |
  v
Build auth headers (bearer / api_key / none)
  |
  v
POST {base_url}/tools/call
  {
    "name": "get_forecast",
    "arguments": {"city": "Seattle", "days": 5},
    "meta": {"agent_id": "agent-123"}
  }
  |
  v
Return response to agent
  (on error: degrade health score, return error dict)
```

### 4.3 Authentication

The federation service builds auth headers based on the server's `auth_type`:

| Auth Type | Header Generated |
|-----------|-----------------|
| `none` | No additional headers |
| `bearer` | `Authorization: Bearer {auth_credential_ref}` |
| `api_key` | `X-API-Key: {auth_credential_ref}` |

---

## 5. Health Monitoring

### 5.1 Health Score

Each server maintains a `health_score` from 0 to 100:

| Score Range | Status | Behavior |
|-------------|--------|----------|
| 50 - 100 | `active` | Server is healthy, receives traffic normally |
| 1 - 49 | `degraded` | Server has issues, lower routing priority |
| 0 | `inactive` | Server is down, no traffic routed |

### 5.2 Score Adjustments

| Event | Score Change |
|-------|-------------|
| Successful `refresh_server_tools()` | Reset to 100 |
| HTTP error on tool list refresh | -20 |
| Connection error on tool list refresh | -30 |
| HTTP error on tool call routing | -10 |
| Connection error on tool call routing | -20 |

All scores are clamped to the [0, 100] range via `max(0, min(100, score))`.

### 5.3 Status Transitions

```
  [active]   -- health drops below 50 -->  [degraded]
  [degraded]  -- health drops to 0 ------> [inactive]
  [inactive]  -- successful refresh ------> [active]
  [degraded]  -- successful refresh ------> [active]
```

### 5.4 Health Update Function

```python
from marketplace.services.mcp_federation_service import update_health_score

# Manually set a server's health score
await update_health_score(db, server_id="...", score=75)
```

---

## 6. Load Balancing Strategies

When multiple servers share the same namespace, the federation service selects the best server using one of four strategies:

### 6.1 `health_first` (Default)

Select the server with the highest `health_score`. This is the current production behavior used by `route_tool_call()`.

```python
server = max(servers, key=lambda s: s.health_score or 0)
```

**Best for:** Most deployments. Automatically routes away from degraded servers.

### 6.2 `round_robin`

Rotate through active servers in registration order. Ensures even distribution of load across all healthy servers regardless of health score.

**Best for:** Homogeneous server clusters where all servers have similar capacity.

### 6.3 `least_loaded`

Route to the server with the fewest in-flight requests. Requires tracking active request counts per server in the connection manager.

**Best for:** Heterogeneous clusters with varying response times.

### 6.4 `weighted`

Distribute traffic proportionally based on health scores. A server with score 80 receives twice the traffic of a server with score 40.

**Best for:** Gradual rollouts and canary deployments where you want to slowly shift traffic.

---

## 7. Merged Tools List

When an agent calls `tools/list` via MCP, the federation handler merges local and federated tools:

```python
from marketplace.mcp.federation_handler import get_federated_tools

all_tools = await get_federated_tools(db)
# Returns list of tool dicts, e.g.:
# [
#   {"name": "search_listings", "description": "Search marketplace listings"},         # local
#   {"name": "weather.get_forecast", "_namespace": "weather", "_server_id": "..."},   # federated
#   {"name": "finance.get_quote", "_namespace": "finance", "_server_id": "..."},       # federated
# ]
```

Federated tools include extra metadata fields:
- `_server_id`: UUID of the source MCP server
- `_namespace`: Namespace prefix string

The handler logs the tool count breakdown:

```
INFO: Serving 15 tools (11 local + 4 federated)
```

---

## 8. Error Handling

### 8.1 No Active Server

If no active server is found for a namespace:

```json
{"error": "No active server found for namespace 'weather'"}
```

### 8.2 HTTP Error on Tool Call

If the remote server returns an HTTP error status:

```json
{"error": "HTTP 503", "tool": "weather.get_forecast"}
```

Server health score is degraded by 10.

### 8.3 Connection Error

If the remote server is unreachable:

```json
{"error": "Connection refused", "tool": "weather.get_forecast"}
```

Server health score is degraded by 20.

### 8.4 Invalid Tool Name Format

If a tool name is passed to the federated handler without a dot separator:

```json
{"error": "Invalid namespaced tool name: weathergetforecast"}
```

### 8.5 Tool Discovery Failure

If `discover_tools()` fails for any server, it logs the error and returns an empty list for that server. Other servers' tools are still included. Local tools are always available.

---

## 9. Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_FEDERATION_ENABLED` | `true` | Enable federation features |
| `MCP_FEDERATION_REFRESH_INTERVAL` | `300` | Auto-refresh tool cache interval (seconds) |
| `MCP_FEDERATION_TOOL_CALL_TIMEOUT` | `30` | Timeout for federated tool calls (seconds) |
| `MCP_FEDERATION_REFRESH_TIMEOUT` | `15` | Timeout for tool list refresh requests (seconds) |
| `MCP_FEDERATION_MAX_SERVERS` | `50` | Maximum number of registered servers |
