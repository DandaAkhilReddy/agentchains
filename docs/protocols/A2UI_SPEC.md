# A2UI Protocol Specification

**Version:** 2026-02-20
**Transport:** WebSocket at `/ws/v4/a2ui`
**Message Format:** JSON-RPC 2.0

## Overview

A2UI (Agent-to-UI) is a protocol for AI agents to push interactive UI components to users in real-time. It enables agents to render cards, tables, forms, charts, and other widgets, request user input, stream progress, and manage confirmations.

## Transport

- WebSocket connection at `/ws/v4/a2ui?token=<stream_token>`
- Token type: `stream_a2ui` (obtained via `POST /api/v4/stream-token`)
- Messages use JSON-RPC 2.0 envelope format

## Message Types

### Agent → UI (7 methods)

| Method | Purpose |
|--------|---------|
| `ui.render` | Push a new UI component |
| `ui.update` | Patch an existing component |
| `ui.request_input` | Ask user for text/select/number/date/file input |
| `ui.confirm` | Request approval with severity level |
| `ui.progress` | Stream task progress (determinate/indeterminate/streaming) |
| `ui.navigate` | Redirect user to a URL |
| `ui.notify` | Show toast notification |

### UI → Agent (3 methods)

| Method | Purpose |
|--------|---------|
| `a2ui.init` | Initialize session, receive session_id + capabilities |
| `user.respond` | Send input value (resolves server-side Future) |
| `user.approve` | Approve or reject confirmation request |
| `user.cancel` | Cancel in-progress operation |

## Component Types

- `card` — Title, description, content sections, optional actions
- `table` — Headers and rows, sortable columns
- `form` — Input fields with validation schema
- `chart` — Data visualization (bar, line, pie)
- `markdown` — Rendered markdown content
- `code` — Syntax-highlighted code block with language
- `image` — Image with alt text and caption
- `alert` — Severity-based alert message
- `steps` — Multi-step progress indicator

## Session Lifecycle

1. Client connects to WebSocket with `stream_a2ui` token
2. Client sends `a2ui.init` with client info and capabilities
3. Server returns `session_id` and server capabilities
4. Agent pushes UI updates; user responds to input/confirm requests
5. Session closes on WebSocket disconnect or explicit close

## Rate Limiting

- 60 requests per minute per session
- Sessions timeout after 1 hour of inactivity
- Maximum 10 concurrent sessions per agent

## Security

- All text content is HTML-sanitized (XSS prevention)
- Payload size limited to 1MB per message
- Consent tracking for data collection and UI interactions
