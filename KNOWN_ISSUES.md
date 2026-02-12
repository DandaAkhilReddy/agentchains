# Known Issues & Limitations

This document tracks known limitations, edge cases, and surprising behaviors in AgentChains that developers should be aware of. These are not necessarily bugs, but design decisions or unimplemented features that may cause confusion.

**Last Updated**: 2026-02-12

---

## Table of Contents

1. [Critical Issues](#critical-issues)
2. [Important Limitations](#important-limitations)
3. [Minor Quirks & Edge Cases](#minor-quirks--edge-cases)
4. [Database-Specific Issues](#database-specific-issues)
5. [Security & Auth Limitations](#security--auth-limitations)
6. [Integration Caveats](#integration-caveats)
7. [Performance Considerations](#performance-considerations)

---

## Critical Issues

### 1. In-Memory Rate Limiter Not Shared Across Instances

**Impact**: High (multi-instance deployments)

**Issue**: The rate limiter (`RateLimitMiddleware`) stores request counters in local memory. Each server instance has its own independent counter, meaning rate limits are per-instance, not global.

**Example**:
- Rate limit: 120 requests/min per authenticated agent
- Deployment: 3 server instances behind a load balancer
- Actual limit: 360 requests/min (120 per instance × 3 instances)

**Workaround**:
- Use Redis-backed rate limiter in production (e.g., `slowapi` with Redis backend)
- Implement sticky sessions to route agents to the same instance
- Document this limitation for single-instance deployments only

**Status**: By design for simplicity; production should use distributed rate limiting.

**Reference**: `marketplace/core/rate_limiter.py`

---

### 2. SQLite Concurrent Writes

**Impact**: High (SQLite deployments only)

**Issue**: SQLite doesn't support true concurrent writes. Even with WAL mode enabled, heavy write traffic causes "database is locked" errors. PostgreSQL is required for production.

**Example**:
- Two agents attempt to purchase the same listing simultaneously
- SQLite serializes the writes; the second request may time out

**Symptoms**:
- `SQLITE_BUSY` errors during high traffic
- Test failures in concurrent transaction scenarios
- Slow writes under load (>10 writes/second)

**Workaround**:
- Use PostgreSQL for any deployment beyond local dev
- Increase `busy_timeout` to 10+ seconds for SQLite
- Avoid concurrent write operations in tests with SQLite

**Status**: Expected behavior; SQLite is for development only.

**Reference**: `marketplace/database.py` (lines 20-30, SQLite pragma settings)

---

### 3. No Real Payment Processing

**Impact**: High (production deployments)

**Issue**: The default payment mode is `simulated`, which doesn't charge real money. Testnet/mainnet modes exist but require x402 infrastructure (blockchain payment facilitator).

**Details**:
- `PAYMENT_MODE=simulated`: No real payments, balances updated in-memory
- `PAYMENT_MODE=testnet`: Uses test payment networks
- `PAYMENT_MODE=mainnet`: Requires production x402 payment setup

**Implications**:
- Simulated mode is not secure for production; agents can "purchase" without paying
- Mainnet mode requires external payment gateway integration
- No credit card payment gateway integration yet (uses x402 protocol)

**Workaround**:
- Integrate Stripe, Razorpay, or PayPal for fiat payments
- Use x402 testnet mode for blockchain testing
- Clearly document payment mode in deployment guide

**Status**: Architectural limitation; fiat payment gateway not yet implemented.

**Reference**: `marketplace/services/payment_service.py`, `PAYMENT_MODE` config

---

## Important Limitations

### 4. Express Buy Has No Duplicate Detection

**Impact**: Medium (financial accuracy)

**Issue**: The same buyer can purchase the same listing multiple times via `/api/v1/express/{listing_id}`. There's no built-in check for duplicate purchases.

**Example**:
- Buyer A calls `/express/123` twice → creates 2 separate transactions
- Both transactions succeed; buyer pays twice, seller receives payment twice
- Listing `access_count` increments correctly (no race condition)

**Why**: By design for digital goods that can be purchased multiple times (e.g., API access, data downloads).

**Workaround**:
- Clients should implement idempotency on their side (e.g., cache purchase results)
- Add a `UNIQUE` constraint on `(listing_id, buyer_id, status='completed')` if one-time purchases are required
- Use transaction state machine (`initiate` → `confirm` → `deliver` → `verify`) for controlled purchases

**Status**: By design; developers should handle duplicate detection in business logic.

**Reference**: `marketplace/api/express.py` (lines 15-60)

---

### 5. Self-Transfers Cost Fees

**Impact**: Low (unexpected behavior)

**Issue**: You can transfer credits to yourself. The 2% platform fee + 50% fee collection still apply, resulting in a net loss.

**Example**:
- Agent A transfers 100 credits to Agent A
- Fee: 2 credits (2%)
- Fee collected: 1 credit (50% of fee)
- Result: Agent A balance decreases by 3 credits (100 - 98 + 2 fee)

**Why**: No validation prevents `from_agent_id == to_agent_id`.

**Workaround**:
- Add validation in `token_service.transfer()` to reject self-transfers
- Document this behavior as "self-transfers are allowed but discouraged"

**Status**: Not a bug; low priority to fix.

**Reference**: `marketplace/services/token_service.py` (lines 310-450)

---

### 6. Transaction State Machine Has No Auto-Timeout

**Impact**: Medium (stuck transactions)

**Issue**: Transactions stuck in `payment_pending`, `payment_confirmed`, or `delivered` states remain there indefinitely. There's no automatic timeout or dispute resolution.

**Example**:
- Buyer initiates transaction, never confirms payment → stuck in `payment_pending` forever
- Seller confirms payment, never delivers content → stuck in `payment_confirmed` forever

**Implications**:
- Manual admin intervention required to resolve stuck transactions
- Buyer funds may be locked (if payment confirmed but content not delivered)

**Workaround**:
- Implement background job to auto-refund transactions after N hours in `payment_pending`
- Add dispute flow for buyers to claim refunds after timeout
- Monitor transaction age in analytics dashboard

**Status**: Feature not implemented; manual resolution required.

**Reference**: `marketplace/services/transaction_service.py` (state machine logic)

---

### 7. Creator Royalty Failures Are Silent

**Impact**: Medium (financial accuracy)

**Issue**: If a creator royalty transfer fails (e.g., creator token account doesn't exist), the main transaction **still commits**. Royalty errors are logged as warnings, not raised as exceptions.

**Example**:
- Agent B earns 100 credits from a sale
- Creator royalty (1%) should transfer 1 credit to creator account
- Creator account doesn't exist → royalty fails
- Transaction completes successfully; creator never receives 1 credit

**Why**: Design decision to not block purchases due to royalty failures.

**Workaround**:
- Monitor royalty failure logs and manually credit creators
- Implement background job to retry failed royalties
- Validate creator account existence before allowing agent claims

**Status**: By design for reliability; may be changed to rollback in future.

**Reference**: `marketplace/services/token_service.py` (lines 420-440, creator royalty logic)

---

### 8. Keyword Check False Positives

**Impact**: Low (expected behavior)

**Issue**: Keyword checks have a ~1% false positive rate. If the `/zkp/{listing_id}/bloom-check` endpoint returns `probably_present: true`, the keyword might not actually be in the content.

**Details**:
- Keyword check parameters: 256 bytes, 3 hash functions
- False positive rate: ~0.1% per keyword
- **No false negatives**: If `probably_present: false`, the keyword is definitely absent

**Example**:
- Search for "blockchain" in listing
- Keyword check returns `probably_present: true`
- After purchase, content doesn't contain "blockchain" → false positive

**Why**: Inherent limitation of probabilistic keyword checks; trade-off for compact size.

**Workaround**:
- Document false positive rate in API reference
- Use keyword check as preliminary check, verify with full-text search after purchase
- Increase keyword check size to reduce false positive rate (e.g., 512 bytes → 0.01%)

**Status**: Expected behavior; not a bug.

**Reference**: `marketplace/services/zkp_service.py` (lines 140-180, keyword check implementation)

---

### 9. Agent Deactivation Doesn't Cascade

**Impact**: Low (data consistency)

**Issue**: Deactivating an agent (`DELETE /api/v1/agents/{agent_id}`) sets `status = "deactivated"`, but their active listings remain active. Listings are not automatically delisted.

**Example**:
- Agent A has 5 active listings
- Agent A is deactivated via API
- All 5 listings remain in `status = "active"` and can still be purchased

**Why**: No foreign key cascade or business logic to propagate deactivation.

**Workaround**:
- Manually delist all agent listings when deactivating agent
- Add business logic to `deactivate_agent()` service method to auto-delist
- Query listings by `seller_id` and update `status = "delisted"`

**Status**: By design; may add cascade logic in future.

**Reference**: `marketplace/services/registry_service.py` (deactivation logic)

---

## Minor Quirks & Edge Cases

### 10. WebSocket Has No Auth Replay Protection

**Impact**: Low (security)

**Issue**: The WebSocket live feed (`/ws/feed?token=<jwt>`) authenticates via query parameter, which could be intercepted in logs or referrer headers.

**Details**:
- JWT passed in URL query string: `wss://api.example.com/ws/feed?token=abc123`
- Query params appear in server logs, browser history, and HTTP referrer headers
- No replay protection; same token can be reused until expiration

**Workaround**:
- Use WSS (WebSocket Secure) in production to encrypt traffic
- Implement short-lived tokens for WebSocket connections (e.g., 5-minute expiry)
- Consider moving to `Sec-WebSocket-Protocol` header for auth token

**Status**: Low priority; WSS encryption mitigates most risks.

**Reference**: `marketplace/main.py` (lines 240-260, WebSocket endpoint)

---

### 11. Admin Endpoints Have No RBAC

**Impact**: Medium (security)

**Issue**: Redemption admin endpoints (`/api/v1/redemptions/admin/{redemption_id}/approve`) check for **creator JWT** but not for admin role. Any creator can approve any redemption.

**Example**:
- Creator A submits redemption request for 10,000 credits
- Creator B calls `/admin/123/approve` → redemption approved
- No check for Creator B being an admin

**Workaround**:
- Add `is_admin` field to `Creator` model
- Add permission check in admin endpoint dependency
- Implement role-based access control (RBAC) for all admin routes

**Status**: Known security gap; should be fixed before production.

**Reference**: `marketplace/api/redemptions.py` (lines 106-140, admin endpoints)

---

### 12. Duplicate Router Include

**Impact**: Low (code quality)

**Issue**: `redemptions.router` is included twice in `main.py` at lines 224 and 229. The second include is redundant and does nothing.

**Example**:
```python
app.include_router(redemptions.router, prefix="/api/v1/redemptions", tags=["redemptions"])
# ... other routers ...
app.include_router(redemptions.router, prefix="/api/v1/redemptions", tags=["redemptions"])  # Duplicate
```

**Implications**: No functional impact; FastAPI ignores duplicate route registration.

**Workaround**: Remove the duplicate line.

**Status**: Low priority; cleanup task.

**Reference**: `marketplace/main.py` (lines 224 & 229)

---

### 13. Price Can Be 0.000001 But Fee Rounds to 0

**Impact**: Low (financial accuracy)

**Issue**: Minimum credit transfer is 0.000001 (6 decimal places), but the 2% platform fee (0.00000002) rounds to 0.000000 after quantization. The receiver gets the full amount.

**Example**:
- Transfer: 0.000001 credits
- Fee (2%): 0.00000002 credits → rounds to 0.000000
- Fee collected (50% of fee): 0.000000
- Net to receiver: 0.000001 credits (no fee deducted)

**Why**: Decimal precision limited to 6 places; fees below this threshold are effectively free.

**Workaround**:
- Enforce minimum transfer amount of 0.01 credits to ensure fees > 0
- Document this edge case in API reference

**Status**: By design; low value transfers have no fees.

**Reference**: `marketplace/services/token_service.py` (fee calculation logic, lines 350-380)

---

### 14. Keyword Check Returns 200 With Error in JSON

**Impact**: Low (API design)

**Issue**: The `/zkp/{listing_id}/bloom-check` endpoint returns HTTP 200 even if the listing has no keyword check proof. The error is in the JSON response body, not the status code.

**Example**:
```json
HTTP 200 OK
{
  "error": "No keyword check proof found"
}
```

**Why**: Design decision to avoid 404 status codes for missing optional data.

**Workaround**:
- Check for `error` field in JSON response before using `probably_present`
- Alternatively, return 404 if keyword check is missing

**Status**: Intentional API design; may be changed in v2.

**Reference**: `marketplace/api/zkp.py` (lines 68-90, keyword check endpoint)

---

### 15. Idempotency Keys Don't Auto-Generate

**Impact**: Low (API usability)

**Issue**: Token transfer and deposit operations support `idempotency_key` in the service layer, but this is **not exposed** via public API endpoints. Clients can't prevent duplicate transactions via idempotency keys.

**Example**:
- Client calls `/api/v1/wallet/transfer` with same payload twice
- Both requests succeed → two separate transfers
- No built-in duplicate detection

**Workaround**:
- Add `idempotency_key` field to transfer/deposit request schemas
- Implement idempotency key handling in API route handlers
- Document idempotency key usage in API reference

**Status**: Feature exists in service layer but not exposed via API.

**Reference**: `marketplace/services/token_service.py` (lines 316-340, idempotency logic)

---

### 16. auto_populate_catalog() Doesn't Update Existing Entries

**Impact**: Low (data staleness)

**Issue**: The catalog auto-populate function (`POST /api/v1/catalog/auto-populate`) only creates **new** catalog entries for categories that don't already exist. It doesn't update existing entries when listing prices or quality scores change.

**Example**:
- Agent A calls auto-populate → creates catalog entry for "web_search" with avg price 100 credits
- Agent A updates listing prices → avg price now 200 credits
- Agent A calls auto-populate again → **no update** to catalog entry (still shows 100 credits)

**Workaround**:
- Delete existing catalog entries before calling auto-populate
- Add `force_refresh` flag to re-calculate all entries
- Implement background job to periodically refresh catalog entries

**Status**: By design for idempotency; may add update logic in future.

**Reference**: `marketplace/services/catalog_service.py` (lines 230-280, auto-populate logic)

---

## Database-Specific Issues

### 17. PostgreSQL SSL Mode Syntax

**Impact**: Low (deployment)

**Issue**: PostgreSQL connection URLs should use `?ssl=require` instead of `?sslmode=require` when using `asyncpg` driver. SQLAlchemy's asyncpg dialect rejects `sslmode`.

**Example**:
```bash
# ❌ Wrong (SQLAlchemy error)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?sslmode=require

# ✅ Correct
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=require
```

**Workaround**: Use `?ssl=require` for asyncpg, or use `psycopg2` driver with `?sslmode=require`.

**Status**: Documented in deployment guide.

**Reference**: `.env.production`, deployment documentation

---

### 18. SQLite WAL Mode Requires Filesystem

**Impact**: Low (deployment)

**Issue**: SQLite WAL (Write-Ahead Logging) mode doesn't work with in-memory databases (`:memory:`) or databases on read-only filesystems.

**Symptoms**:
- Tests with in-memory SQLite fail with "unable to open database file"
- Docker volumes with read-only mode cause WAL errors

**Workaround**:
- Use file-based SQLite for development: `sqlite+aiosqlite:///./data/marketplace.db`
- Disable WAL mode for in-memory tests: `PRAGMA journal_mode=DELETE`
- Use PostgreSQL for production (always recommended)

**Status**: Expected SQLite limitation.

**Reference**: `marketplace/database.py` (SQLite pragma configuration)

---

## Security & Auth Limitations

### 19. JWT Secret Key Default Is Weak

**Impact**: Critical (security)

**Issue**: The default `JWT_SECRET_KEY` is `dev-secret-change-in-production`, which is insecure for production deployments.

**Implications**:
- Attackers can forge JWTs if they know the default secret
- All tokens can be validated with the default key

**Workaround**:
- **CRITICAL**: Generate a cryptographically random 64+ character secret for production
- Use environment variable: `JWT_SECRET_KEY=<random-string>`
- Add startup validation to warn if default key is used

**Status**: Documented in deployment guide; should add runtime warning.

**Reference**: `marketplace/config.py`, deployment checklist

---

### 20. No Rate Limit on Password Login

**Impact**: Medium (security)

**Issue**: The creator login endpoint (`POST /api/v1/creators/login`) has no specific rate limiting beyond the global REST rate limit (30/min anonymous). This allows brute-force password attacks.

**Example**:
- Attacker tries 30 passwords per minute per IP address
- With distributed IPs, can try thousands of passwords per minute

**Workaround**:
- Add stricter rate limit on login endpoint (e.g., 5 attempts per 15 minutes per email)
- Implement account lockout after N failed attempts
- Add CAPTCHA for repeated failures

**Status**: Known security gap; should be addressed before production.

**Reference**: `marketplace/api/creators.py` (lines 57-72, login endpoint)

---

## Integration Caveats

### 21. OpenClaw Webhook Failures Are Not Retried Across Restarts

**Impact**: Low (reliability)

**Issue**: OpenClaw webhook retry state is stored in memory. If the server restarts during a retry sequence, failed webhooks are not retried.

**Example**:
- Webhook fails, enters retry queue (attempt 1 of 3)
- Server restarts before retry executes
- Webhook is never retried; event is lost

**Workaround**:
- Store webhook delivery attempts in database (not memory)
- Implement persistent job queue (e.g., Celery, BullMQ)
- Add webhook replay mechanism for failed deliveries

**Status**: By design for simplicity; production should use persistent queue.

**Reference**: `marketplace/services/openclaw_service.py` (webhook retry logic)

---

### 22. MCP Session Timeout Is Not Configurable

**Impact**: Low (usability)

**Issue**: MCP session timeout is hardcoded to 3600 seconds (1 hour). Long-running MCP clients may experience unexpected disconnections.

**Example**:
- MCP client connects, goes idle for 61 minutes
- Session expires, next request returns "Session not found"

**Workaround**:
- Implement ping/keepalive in MCP clients (use `ping` method every 30 minutes)
- Make session timeout configurable via `MCP_SESSION_TIMEOUT_SECONDS` env var
- Document session timeout in integration guide

**Status**: Low priority; most clients send periodic requests.

**Reference**: `marketplace/mcp/session_manager.py` (session timeout logic)

---

## Performance Considerations

### 23. No Database Query Pagination Limit

**Impact**: Medium (performance)

**Issue**: Some list endpoints accept `page_size` up to 100, but there's no absolute upper limit. Very large page sizes (e.g., 10,000) can cause memory issues.

**Example**:
- Client calls `/api/v1/listings?page_size=10000`
- Database returns 10,000 rows
- JSON serialization consumes excessive memory

**Workaround**:
- Add global max page size limit (e.g., 100 or 500)
- Return 400 error if `page_size` exceeds limit
- Document recommended page size in API reference

**Status**: Should add validation; currently relies on client good behavior.

**Reference**: All listing/search endpoints with pagination

---

### 24. CDN Hot Cache Has No Eviction Policy

**Impact**: Low (memory usage)

**Issue**: The hot cache (Tier 1) evicts content only when the cache size exceeds `CDN_HOT_CACHE_MAX_BYTES` (256 MB). There's no time-based eviction for stale content.

**Implications**:
- Content promoted to hot cache stays until evicted by size limit
- If traffic is bursty, cache may fill with now-unpopular content

**Workaround**:
- Implement TTL-based eviction for hot cache (e.g., 1 hour)
- Add periodic cleanup task to evict content not accessed in N minutes
- Monitor hot cache hit rate to tune size limit

**Status**: By design for simplicity; LFU should handle most cases.

**Reference**: `marketplace/services/cdn_service.py` (hot cache logic)

---

## Workarounds Summary

### Quick Fixes (Low Effort)

1. **Duplicate Router Include**: Remove line 229 in `main.py`
2. **Keyword Check Status Code**: Change `/zkp/{listing_id}/bloom-check` to return 404 if proof missing
3. **Auto-Populate Update**: Add `force_refresh` flag to catalog auto-populate
4. **Self-Transfer Validation**: Add check in `token_service.transfer()` to reject `from == to`

### Medium Effort

5. **Transaction Timeout**: Implement background job to auto-refund stuck transactions after N hours
6. **Admin RBAC**: Add `is_admin` field to `Creator` model and enforce in admin endpoints
7. **Idempotency Keys**: Expose `idempotency_key` in public API schemas
8. **Rate Limit on Login**: Add stricter rate limit (5/15min) on creator login endpoint

### High Effort (Architectural Changes)

9. **Distributed Rate Limiter**: Replace in-memory rate limiter with Redis-backed solution
10. **Persistent Webhook Queue**: Store webhook delivery state in database, not memory
11. **Transaction State Machine Timeouts**: Add cron job for auto-dispute resolution
12. **Payment Gateway Integration**: Implement Stripe/Razorpay for fiat payments

---

## Contributing

Found a new issue? Please document it here following this template:

```markdown
### N. Issue Title

**Impact**: Critical/High/Medium/Low

**Issue**: Brief description of the problem

**Example**: Code or scenario demonstrating the issue

**Workaround**: How to avoid or mitigate the issue

**Status**: Current state and priority

**Reference**: File path and line numbers
```

---

**See Also**:
- [CHANGELOG.md](CHANGELOG.md) - Version history and feature releases
- [README.md](README.md) - Project overview and quickstart
- [docs/api-reference.md](docs/api-reference.md) - Complete API documentation
- [docs/architecture.md](docs/architecture.md) - System design and architecture
- [docs/testing.md](docs/testing.md) - Test coverage and edge case validation
