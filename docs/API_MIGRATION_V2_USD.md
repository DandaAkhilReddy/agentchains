# API Migration Guide: v1 to v2 (USD-First)

## Dates
- Deprecation start: **February 15, 2026**
- Sunset target: **May 16, 2026**

All legacy v1 wallet/redemption responses now include:
- `Deprecation: true`
- `Sunset: Sat, 16 May 2026 00:00:00 GMT`
- `Link: <https://github.com/DandaAkhilReddy/agentchains/blob/master/docs/API_MIGRATION_V2_USD.md>; rel="deprecation"`

## Canonical v2 Endpoints

### Billing
- `GET /api/v2/billing/accounts/me`
- `GET /api/v2/billing/ledger/me`
- `POST /api/v2/billing/deposits`
- `POST /api/v2/billing/deposits/{deposit_id}/confirm`
- `POST /api/v2/billing/transfers`

### Payouts
- `POST /api/v2/payouts/requests`
- `GET /api/v2/payouts/requests`
- `POST /api/v2/payouts/requests/{request_id}/cancel`
- `POST /api/v2/payouts/requests/{request_id}/approve`
- `POST /api/v2/payouts/requests/{request_id}/reject`

### Seller earnings
- `GET /api/v2/sellers/me/earnings`

### Trust verification
- `GET /api/v2/verification/listings/{listing_id}`
- `POST /api/v2/verification/listings/{listing_id}/run`
- `POST /api/v2/verification/listings/{listing_id}/receipts`

## Endpoint Mapping

1. `GET /api/v1/wallet/balance` -> `GET /api/v2/billing/accounts/me`
2. `GET /api/v1/wallet/history` -> `GET /api/v2/billing/ledger/me`
3. `POST /api/v1/wallet/deposit` -> `POST /api/v2/billing/deposits`
4. `POST /api/v1/wallet/deposit/{deposit_id}/confirm` -> `POST /api/v2/billing/deposits/{deposit_id}/confirm`
5. `POST /api/v1/wallet/transfer` -> `POST /api/v2/billing/transfers`
6. `POST /api/v1/redemptions` -> `POST /api/v2/payouts/requests`
7. `GET /api/v1/redemptions` -> `GET /api/v2/payouts/requests`
8. `POST /api/v1/redemptions/admin/{id}/approve|reject` -> `POST /api/v2/payouts/requests/{id}/approve|reject`
9. `GET /api/v1/creators/me/wallet` -> `GET /api/v2/sellers/me/earnings`

## Field Normalization
- Keep `price_usdc` for backward compatibility.
- Add `price_usd` in listing/discovery responses.
- v2 billing and payout responses use `_usd` field suffixes for monetary values.

## Migration Notes
- Existing integrations continue to work on v1 during the deprecation window.
- New integrations should use only `/api/v2/...` paths and USD field names.
- Trust badge (`verified_secure_data`) is strict and requires all verification stages to pass.

