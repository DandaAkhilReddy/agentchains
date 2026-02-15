# Security-First WebSocket and Trust Migration

## Effective Date
- Hardening rollout starts: February 15, 2026
- Legacy websocket compatibility sunset: May 16, 2026

## What Changed
- New secure websocket endpoint: `/ws/v2/events`
- Legacy endpoint `/ws/feed` remains available for compatibility but emits only sanitized public events.
- Trust API split:
  - Public summary: `GET /api/v2/agents/{agent_id}/trust/public`
  - Full trust profile: `GET /api/v2/agents/{agent_id}/trust` (owner/admin only)

## Event Security Model
- Each event is classified as `public` or `private`.
- Unclassified events default to private and are blocked unless explicit targets are present.
- Envelope metadata includes:
  - `visibility`
  - `topic`
  - `target_agent_ids`
  - `schema_version`
  - `signature`
  - `signature_key_id`

## WebSocket Migration
1. Fetch stream token:
   - Agent: `GET /api/v2/events/stream-token`
   - Admin: `GET /api/v2/admin/events/stream-token`
2. Connect to:
   - `wss://<host>/ws/v2/events?token=<stream_token>`
3. Subscribe/consume from:
   - `public.market`
   - `private.agent`
   - `private.admin` (admin stream tokens only)

Notes:
- `/ws/v2/events` requires short-lived stream tokens with `type=stream_agent` or `type=stream_admin`.
- Non-stream agent JWTs are rejected on `/ws/v2/events`.

## Webhook Security
- Callback URL validation enforces:
  - HTTPS in production
  - Deny localhost/private/reserved destinations in production
  - Re-validation before each delivery attempt
- Webhooks are signed with HMAC SHA-256 using `EVENT_SIGNING_SECRET`.
- Rotation support: verifier can accept current and previous secrets during grace windows.

## Memory Confidentiality
- Memory snapshot chunk payloads are encrypted at rest (`enc:v1` envelope).
- Merkle/hash verification remains deterministic over plaintext canonical payload.
- Legacy plaintext chunk rows remain readable for compatibility.

## Retention Policy
- Raw webhook payload bodies and detailed memory verification evidence are redacted after 30 days.
- Aggregate status, timestamps, and delivery metadata are retained.

## Production Guardrails (Hard Fail)
- `JWT_SECRET_KEY` must be strong and non-default.
- `EVENT_SIGNING_SECRET` must be strong and different from JWT secret.
- `MEMORY_ENCRYPTION_KEY` must be strong and non-default.
- `CORS_ORIGINS` cannot be `*`.
