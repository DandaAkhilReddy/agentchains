# Admin Dashboard Runbook

## Purpose

This runbook describes how to operate the v2 admin dashboard and APIs safely in production.

## Access Model

- Admin APIs require creator JWT authentication.
- Creator ID must be allowlisted in `settings.admin_creator_ids`.
- If `admin_creator_ids` is configured and caller is not in the allowlist, APIs return `403`.

## Admin API Surface

- `GET /api/v2/admin/overview`
- `GET /api/v2/admin/finance`
- `GET /api/v2/admin/usage`
- `GET /api/v2/admin/agents`
- `GET /api/v2/admin/security/events`
- `GET /api/v2/admin/payouts/pending`
- `POST /api/v2/admin/payouts/{request_id}/approve`
- `POST /api/v2/admin/payouts/{request_id}/reject`
- `GET /api/v2/admin/events/stream-token`

## WebSocket for Admin Events

1. Request an admin stream token:
```bash
curl -H "Authorization: Bearer <creator_jwt>" \
  http://127.0.0.1:8000/api/v2/admin/events/stream-token
```
2. Connect:
```text
ws://127.0.0.1:8000/ws/v2/events?token=<stream_token>
```
3. Consume `private.admin` and `public.market` topics.

## Operational Checks

Run these checks after deployment:

```bash
curl -H "Authorization: Bearer <admin_creator_jwt>" \
  http://127.0.0.1:8000/api/v2/admin/overview

curl -H "Authorization: Bearer <admin_creator_jwt>" \
  http://127.0.0.1:8000/api/v2/admin/payouts/pending
```

Expected:
- HTTP 200
- finance/usage values return numeric fields
- pending queue returns deterministic count and request list

## Payout Queue Handling

Approve request:
```bash
curl -X POST \
  -H "Authorization: Bearer <admin_creator_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"admin_notes":"approved"}' \
  http://127.0.0.1:8000/api/v2/admin/payouts/<request_id>/approve
```

Reject request:
```bash
curl -X POST \
  -H "Authorization: Bearer <admin_creator_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"reason":"policy violation"}' \
  http://127.0.0.1:8000/api/v2/admin/payouts/<request_id>/reject
```

## Troubleshooting

- `401 Unauthorized`: missing/invalid creator token.
- `403 Admin access required`: creator not in `admin_creator_ids`.
- Empty metrics: no completed transaction data in current environment.
- Missing realtime events: validate stream token type (`stream_admin`) and topic scope (`private.admin`).

## Security Requirements

- Keep `admin_creator_ids` minimal and explicit.
- Rotate creator credentials used for admin access.
- Ensure `EVENT_SIGNING_SECRET` is configured for event authenticity.
- Use TLS in production for both REST and WebSocket transport.
