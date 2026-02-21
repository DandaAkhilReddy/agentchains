# A2UI Protocol Specification

**Version:** 2026-02-20
**Status:** Stable
**Transport:** WebSocket at `/ws/v4/a2ui`
**Message Format:** JSON-RPC 2.0

---

## 1. Overview

A2UI (Agent-to-UI) is a real-time protocol that enables AI agents to push interactive UI components to end users. Built on WebSocket transport with JSON-RPC 2.0 message framing, A2UI supports rendering cards, tables, forms, charts, and other widgets, requesting user input, streaming progress updates, and managing approval workflows.

A2UI is part of the AgentChains v1.0 protocol suite alongside MCP, A2A, and WebMCP.

---

## 2. Transport

| Property | Value |
|----------|-------|
| Protocol | WebSocket (WSS in production, WS in development) |
| Path | `/ws/v4/a2ui?token=<stream_token>` |
| Token type | `stream_a2ui` |
| Token acquisition | `POST /api/v4/stream-token` with `token_type: "stream_a2ui"` |
| Token lifetime | Configurable via `STREAM_TOKEN_EXPIRE_MINUTES` (default: 30 min) |
| Message encoding | UTF-8 JSON |
| Max message size | 1 MB |

### 2.1 Connection Flow

```
Client                                Server
  |                                      |
  |  GET /api/v4/stream-token            |
  |  { token_type: "stream_a2ui" }       |
  |------------------------------------->|
  |  { token: "eyJ..." }                 |
  |<-------------------------------------|
  |                                      |
  |  WS /ws/v4/a2ui?token=eyJ...         |
  |------------------------------------->|
  |  Connection Established              |
  |<-------------------------------------|
  |                                      |
  |  a2ui.init { client_info, caps }     |
  |------------------------------------->|
  |  { session_id, server_caps }         |
  |<-------------------------------------|
  |                                      |
  |  (bidirectional messages)            |
  |<------------------------------------>|
```

---

## 3. Message Format

All messages follow JSON-RPC 2.0:

```json
{
  "jsonrpc": "2.0",
  "method": "<method_name>",
  "params": { ... },
  "id": "<optional_request_id>"
}
```

- **Notifications** (no `id`): fire-and-forget messages; no response expected.
- **Requests** (with `id`): expect a JSON-RPC response with matching `id`.

---

## 4. Message Types

### 4.1 Agent to UI (7 methods)

#### `ui.render`

Push a new UI component to the client.

```json
{
  "jsonrpc": "2.0",
  "method": "ui.render",
  "params": {
    "component_id": "uuid",
    "component_type": "card | table | form | chart | markdown | code | image | alert | steps",
    "data": {
      "title": "string",
      "content": "object (type-specific)"
    },
    "metadata": {
      "priority": "normal | high | low",
      "ttl_seconds": 300,
      "position": "main | sidebar | overlay"
    }
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `component_id` | string (UUID) | Yes | Unique identifier for the component |
| `component_type` | string (enum) | Yes | One of the 9 supported component types |
| `data` | object | Yes | Type-specific component data |
| `metadata` | object | No | Rendering hints (priority, TTL, position) |

#### `ui.update`

Patch an existing component without re-rendering.

```json
{
  "jsonrpc": "2.0",
  "method": "ui.update",
  "params": {
    "component_id": "uuid",
    "operation": "replace | merge | append",
    "data": { ... }
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `component_id` | string (UUID) | Yes | ID of the component to update |
| `operation` | string (enum) | Yes | `replace` (full), `merge` (shallow), `append` (list) |
| `data` | object | Yes | Patch payload |

#### `ui.request_input`

Request input from the user. The server-side creates an `asyncio.Future` that resolves when the user responds via `user.respond`.

```json
{
  "jsonrpc": "2.0",
  "method": "ui.request_input",
  "params": {
    "request_id": "uuid",
    "input_type": "text | select | number | date | file",
    "prompt": "What is the target price?",
    "options": ["$10", "$20", "$50"],
    "validation": {
      "min": 1,
      "max": 1000,
      "pattern": "^\\d+$",
      "required": true
    }
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string (UUID) | Yes | Correlation ID for the response |
| `input_type` | string (enum) | Yes | Input widget type |
| `prompt` | string | Yes | Human-readable prompt (HTML-sanitized) |
| `options` | string[] | No | Choices for `select` type |
| `validation` | object | No | Validation rules for the input |

#### `ui.confirm`

Request explicit approval from the user with severity indication.

```json
{
  "jsonrpc": "2.0",
  "method": "ui.confirm",
  "params": {
    "request_id": "uuid",
    "title": "Confirm Purchase",
    "description": "This will charge $50.00 to your account.",
    "severity": "info | warning | critical",
    "timeout_seconds": 30
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string (UUID) | Yes | Correlation ID for the response |
| `title` | string | Yes | Confirmation title (HTML-sanitized) |
| `description` | string | No | Detailed description (HTML-sanitized) |
| `severity` | string (enum) | No | `info` (default), `warning`, or `critical` |
| `timeout_seconds` | integer | No | Auto-reject timeout (default: 30) |

#### `ui.progress`

Stream task progress to the client.

```json
{
  "jsonrpc": "2.0",
  "method": "ui.progress",
  "params": {
    "task_id": "uuid",
    "progress_type": "determinate | indeterminate | streaming",
    "value": 45,
    "total": 100,
    "message": "Processing step 3 of 5..."
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | Yes | Identifier for the task |
| `progress_type` | string (enum) | Yes | Progress bar style |
| `value` | number | No | Current progress (for determinate) |
| `total` | number | No | Total progress (for determinate) |
| `message` | string | No | Status text (HTML-sanitized) |

#### `ui.navigate`

Redirect the user to a URL.

```json
{
  "jsonrpc": "2.0",
  "method": "ui.navigate",
  "params": {
    "url": "https://example.com/results",
    "new_tab": false
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string (URL) | Yes | Destination URL |
| `new_tab` | boolean | No | Open in new tab (default: false) |

#### `ui.notify`

Show a toast notification overlay.

```json
{
  "jsonrpc": "2.0",
  "method": "ui.notify",
  "params": {
    "level": "info | success | warning | error",
    "title": "Task Complete",
    "message": "Your report has been generated.",
    "duration_ms": 5000
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `level` | string (enum) | Yes | Notification severity |
| `title` | string | Yes | Notification title (HTML-sanitized) |
| `message` | string | No | Body text (HTML-sanitized) |
| `duration_ms` | integer | No | Auto-dismiss time (default: 5000) |

---

### 4.2 UI to Agent (4 methods)

#### `a2ui.init`

Initialize the A2UI session. Sent by the client immediately after WebSocket connection.

```json
{
  "jsonrpc": "2.0",
  "method": "a2ui.init",
  "id": "1",
  "params": {
    "client_info": {
      "name": "AgentChains Web UI",
      "version": "1.0.0",
      "viewport": { "width": 1920, "height": 1080 }
    },
    "capabilities": {
      "supported_components": ["card", "table", "form", "chart", "markdown"],
      "max_concurrent_components": 20,
      "supports_file_upload": true
    }
  }
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "session_id": "uuid",
    "server_capabilities": {
      "max_payload_size": 1048576,
      "supported_components": ["card", "table", "form", "chart", "markdown", "code", "image", "alert", "steps"],
      "rate_limit_per_minute": 60
    }
  }
}
```

#### `user.respond`

Send user input in response to a `ui.request_input` message.

```json
{
  "jsonrpc": "2.0",
  "method": "user.respond",
  "params": {
    "request_id": "uuid",
    "value": "user input value"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string (UUID) | Yes | Must match the `request_id` from `ui.request_input` |
| `value` | any | Yes | User's input value |

#### `user.approve`

Respond to a `ui.confirm` message with approval or rejection.

```json
{
  "jsonrpc": "2.0",
  "method": "user.approve",
  "params": {
    "request_id": "uuid",
    "approved": true,
    "reason": "Looks good to proceed."
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string (UUID) | Yes | Must match the `request_id` from `ui.confirm` |
| `approved` | boolean | Yes | User's decision |
| `reason` | string | No | Optional reason text |

#### `user.cancel`

Cancel an in-progress operation.

```json
{
  "jsonrpc": "2.0",
  "method": "user.cancel",
  "params": {
    "task_id": "uuid",
    "reason": "User requested cancellation"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | Yes | ID of the task to cancel |
| `reason` | string | No | Cancellation reason |

---

## 5. Component Types

### 5.1 `card`

General-purpose content container.

```json
{
  "title": "Agent Summary",
  "description": "Performance overview for the last 7 days.",
  "sections": [
    { "label": "Total Calls", "value": "1,247" },
    { "label": "Success Rate", "value": "99.2%" }
  ],
  "actions": [
    { "label": "View Details", "action": "navigate", "url": "/agents/abc" }
  ]
}
```

### 5.2 `table`

Tabular data with optional sorting.

```json
{
  "headers": [
    { "key": "name", "label": "Agent Name", "sortable": true },
    { "key": "calls", "label": "API Calls", "sortable": true },
    { "key": "status", "label": "Status" }
  ],
  "rows": [
    { "name": "WeatherBot", "calls": 5420, "status": "active" },
    { "name": "DataMiner", "calls": 3180, "status": "active" }
  ]
}
```

### 5.3 `form`

Interactive form with validation schema.

```json
{
  "fields": [
    { "name": "query", "type": "text", "label": "Search Query", "required": true },
    { "name": "max_price", "type": "number", "label": "Max Price (USD)", "min": 0, "max": 1000 },
    { "name": "category", "type": "select", "label": "Category", "options": ["research", "trading", "analytics"] }
  ],
  "submit_label": "Search",
  "cancel_label": "Reset"
}
```

### 5.4 `chart`

Data visualization.

```json
{
  "chart_type": "bar | line | pie",
  "title": "API Usage Over Time",
  "x_axis": { "label": "Date", "values": ["Mon", "Tue", "Wed", "Thu", "Fri"] },
  "y_axis": { "label": "Calls" },
  "series": [
    { "name": "Successful", "data": [120, 150, 180, 160, 200] },
    { "name": "Failed", "data": [5, 3, 8, 2, 4] }
  ]
}
```

### 5.5 `markdown`

Rendered markdown content.

```json
{
  "content": "## Analysis Report\n\nThe agent identified **3 key findings**:\n\n1. Market demand is rising\n2. Supply gap exists in the `research` category\n3. Price elasticity suggests a $0.05 optimal price point"
}
```

### 5.6 `code`

Syntax-highlighted code block.

```json
{
  "language": "python",
  "code": "import httpx\n\nasync with httpx.AsyncClient() as client:\n    resp = await client.get('https://api.example.com/data')\n    print(resp.json())",
  "title": "API Request Example"
}
```

### 5.7 `image`

Image with alt text and caption.

```json
{
  "url": "https://cdn.example.com/chart-output.png",
  "alt": "Generated chart showing market trends",
  "caption": "Market trends for Q1 2026",
  "width": 800,
  "height": 400
}
```

### 5.8 `alert`

Severity-based alert banner.

```json
{
  "severity": "info | success | warning | error",
  "title": "Budget Warning",
  "message": "This workflow has consumed 80% of its allocated budget ($40.00 / $50.00).",
  "dismissible": true
}
```

### 5.9 `steps`

Multi-step progress indicator.

```json
{
  "steps": [
    { "label": "Data Collection", "status": "completed" },
    { "label": "Analysis", "status": "active" },
    { "label": "Report Generation", "status": "pending" },
    { "label": "Review", "status": "pending" }
  ],
  "current_step": 1
}
```

---

## 6. Session Lifecycle

### 6.1 States

```
[Disconnected] --> [Connected] --> [Initialized] --> [Active] --> [Closed]
                       |                                |
                       +--- auth failure ----> [Rejected]
                                                        |
                                         [Timed Out] <--+
```

### 6.2 Lifecycle Steps

1. **Connect**: Client opens WebSocket to `/ws/v4/a2ui?token=<stream_token>`. Server validates the `stream_a2ui` token.
2. **Initialize**: Client sends `a2ui.init` with client info and capabilities. Server returns `session_id` and server capabilities.
3. **Active**: Agent pushes UI components; user responds to input and confirmation requests. Session is tracked in `A2UISessionLog`.
4. **Consent**: Data collection consent is tracked via `A2UIConsentRecord` (type, granted, timestamp).
5. **Close**: Session ends on WebSocket disconnect, explicit close, or inactivity timeout (1 hour).

### 6.3 Session Tracking

| Metric | Description |
|--------|-------------|
| `message_count` | Total messages exchanged in the session |
| `components_rendered` | Number of `ui.render` calls |
| `inputs_requested` | Number of `ui.request_input` and `ui.confirm` calls |

---

## 7. Rate Limiting

| Limit | Value |
|-------|-------|
| Requests per minute per session | 60 |
| Session inactivity timeout | 1 hour |
| Maximum concurrent sessions per agent | 10 |
| Maximum payload size | 1 MB (1,048,576 bytes) |

---

## 8. Security

### 8.1 XSS Sanitization

All text content passed through `ui.render`, `ui.request_input`, `ui.confirm`, `ui.progress`, and `ui.notify` is processed by `sanitize_html()` before transmission. This strips script tags, event handlers, and other potentially dangerous HTML constructs.

### 8.2 Payload Size Limits

Every message payload is validated against the 1 MB maximum via `validate_payload_size()`. Messages exceeding this limit are rejected with an error.

### 8.3 Token Isolation

- `stream_a2ui` tokens can only be used for A2UI WebSocket connections.
- They cannot be used for REST API endpoints (enforced by `decode_token()`).
- Regular API tokens cannot be used for WebSocket streams (enforced by `decode_stream_token()`).

### 8.4 Consent Tracking

All data collection activities within an A2UI session are tracked via `A2UIConsentRecord`:

| Field | Description |
|-------|-------------|
| `consent_type` | Category of consent (e.g., "data_collection", "ui_interaction") |
| `granted` | Boolean indicating whether consent was given |
| `granted_at` | Timestamp when consent was recorded |
| `revoked_at` | Timestamp when consent was revoked (null if still active) |

---

## 9. Error Codes

| Code | Message | Description |
|------|---------|-------------|
| -32700 | Parse error | Invalid JSON |
| -32600 | Invalid request | Missing required JSON-RPC fields |
| -32601 | Method not found | Unknown method name |
| -32602 | Invalid params | Invalid or missing parameters |
| -32603 | Internal error | Server-side error |
| -32000 | Session not found | Invalid or expired session_id |
| -32001 | Rate limit exceeded | More than 60 requests/minute |
| -32002 | Payload too large | Message exceeds 1 MB limit |
| -32003 | Component not found | Referenced component_id does not exist |
| -32004 | Request timeout | Input or confirmation request timed out |
| -32005 | Session expired | Session inactive for more than 1 hour |
| -32006 | Auth failed | Invalid or expired stream token |
| -32007 | Max sessions exceeded | Agent has 10+ concurrent sessions |

---

## 10. Wire Examples

### Full Session Example

```json
// 1. Client -> Server: Initialize
{"jsonrpc":"2.0","method":"a2ui.init","id":"1","params":{"client_info":{"name":"WebUI","version":"1.0"},"capabilities":{"supported_components":["card","table","markdown"]}}}

// 2. Server -> Client: Session established
{"jsonrpc":"2.0","id":"1","result":{"session_id":"550e8400-e29b-41d4-a716-446655440000","server_capabilities":{"max_payload_size":1048576,"rate_limit_per_minute":60}}}

// 3. Server -> Client: Render a card
{"jsonrpc":"2.0","method":"ui.render","params":{"component_id":"c1","component_type":"card","data":{"title":"Welcome","description":"Your agent is ready."}}}

// 4. Server -> Client: Request input
{"jsonrpc":"2.0","method":"ui.request_input","params":{"request_id":"r1","input_type":"text","prompt":"What would you like to search for?"}}

// 5. Client -> Server: User responds
{"jsonrpc":"2.0","method":"user.respond","params":{"request_id":"r1","value":"machine learning datasets"}}

// 6. Server -> Client: Progress update
{"jsonrpc":"2.0","method":"ui.progress","params":{"task_id":"t1","progress_type":"determinate","value":50,"total":100,"message":"Searching..."}}

// 7. Server -> Client: Render results
{"jsonrpc":"2.0","method":"ui.render","params":{"component_id":"c2","component_type":"table","data":{"headers":[{"key":"name","label":"Dataset"},{"key":"price","label":"Price"}],"rows":[{"name":"ImageNet-2026","price":"$0.05"},{"name":"NLP-Commons","price":"$0.02"}]}}}

// 8. Server -> Client: Notify completion
{"jsonrpc":"2.0","method":"ui.notify","params":{"level":"success","title":"Search Complete","message":"Found 2 results.","duration_ms":3000}}
```
