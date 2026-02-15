# Dual-Layer Phase 0 Baseline

Date: February 15, 2026  
Branch: `codex/dual-layer-developer-buyer-20260215`

## Current Baseline Snapshot

- Existing v1 API remains active (`/api/v1/*`) with express checkout at `POST /api/v1/express/{listing_id}`.
- Existing v2 admin, dashboard, trust, websocket, billing, payout routes are present.
- Canonical secure websocket endpoint: `/ws/v2/events`.
- Compatibility websocket endpoint: `/ws/feed` (sanitized).

## Health and Route Baseline Targets

- `GET /api/v1/health`
- `GET /docs`
- `GET /api/v1/health/cdn`
- `GET /api/v2/analytics/market/open`

## Dual-Layer Implementation Intent

- Add end-user buyer APIs and managed buyer-agent mapping.
- Add builder templates/projects/publish APIs for creators.
- Add market listings/orders/featured collection APIs for common users.
- Add explicit platform fee rows for consumer orders.
