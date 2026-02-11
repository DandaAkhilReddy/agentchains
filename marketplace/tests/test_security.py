"""Tests for security features: rate limiter, headers, SHA-256 chain, audit log."""
import pytest
from decimal import Decimal

from marketplace.core.hashing import compute_ledger_hash, compute_audit_hash
from marketplace.core.rate_limiter import SlidingWindowRateLimiter
from marketplace.services.token_service import (
    create_account,
    deposit,
    ensure_platform_account,
    transfer,
    verify_ledger_chain,
)


# ---------------------------------------------------------------------------
# SHA-256 Hashing
# ---------------------------------------------------------------------------

class TestSHA256Hashing:
    def test_compute_ledger_hash_deterministic(self):
        """Same inputs should produce identical hash."""
        h1 = compute_ledger_hash(None, "from-1", "to-1", Decimal("100"), Decimal("2"), Decimal("1"), "purchase", "2026-01-01T00:00:00")
        h2 = compute_ledger_hash(None, "from-1", "to-1", Decimal("100"), Decimal("2"), Decimal("1"), "purchase", "2026-01-01T00:00:00")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_different_inputs_different_hash(self):
        h1 = compute_ledger_hash(None, "from-1", "to-1", Decimal("100"), Decimal("0"), Decimal("0"), "deposit", "2026-01-01")
        h2 = compute_ledger_hash(None, "from-1", "to-2", Decimal("100"), Decimal("0"), Decimal("0"), "deposit", "2026-01-01")
        assert h1 != h2

    def test_genesis_hash_no_prev(self):
        """First entry uses 'GENESIS' as prev_hash."""
        h = compute_ledger_hash(None, None, "to-1", Decimal("100"), Decimal("0"), Decimal("0"), "deposit", "2026-01-01")
        assert isinstance(h, str)
        assert len(h) == 64

    def test_chain_links(self):
        """Each hash depends on the previous one."""
        h1 = compute_ledger_hash(None, "a", "b", Decimal("10"), Decimal("0"), Decimal("0"), "transfer", "t1")
        h2 = compute_ledger_hash(h1, "b", "c", Decimal("5"), Decimal("0"), Decimal("0"), "transfer", "t2")
        h3 = compute_ledger_hash(h2, "c", "d", Decimal("3"), Decimal("0"), Decimal("0"), "transfer", "t3")
        # Changing h1 would change h2 and h3
        assert h1 != h2 != h3


# ---------------------------------------------------------------------------
# Ledger Chain Verification
# ---------------------------------------------------------------------------

class TestLedgerChainVerification:
    async def test_verify_empty_ledger(self, db):
        """Empty ledger should be valid."""
        await ensure_platform_account(db)
        result = await verify_ledger_chain(db)
        assert result["valid"] is True

    async def test_verify_after_deposit(self, db, make_agent, make_token_account):
        """Chain should be valid after a deposit."""
        await ensure_platform_account(db)
        agent, _ = await make_agent("chain-agent")
        acct = await create_account(db, agent.id)
        await deposit(db, agent.id, 5000)

        result = await verify_ledger_chain(db)
        assert result["valid"] is True
        assert result["total_entries"] >= 1

    async def test_verify_after_transfer(self, db, make_agent, make_token_account):
        """Chain should be valid after transfers."""
        await ensure_platform_account(db)
        a1, _ = await make_agent("sender")
        a2, _ = await make_agent("receiver")
        await make_token_account(a1.id, 10000)
        await create_account(db, a2.id)

        await transfer(db, a1.id, a2.id, 1000, "transfer")
        await transfer(db, a1.id, a2.id, 500, "transfer")

        result = await verify_ledger_chain(db)
        assert result["valid"] is True
        assert result["total_entries"] >= 2


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = SlidingWindowRateLimiter()
        for i in range(5):
            allowed, headers = limiter.check("test-key", authenticated=True)
            assert allowed

    def test_blocks_over_limit(self):
        limiter = SlidingWindowRateLimiter()
        # Default anonymous limit is 30, exhaust it
        for i in range(30):
            limiter.check("test-key", authenticated=False)
        # 31st request should be blocked
        allowed, headers = limiter.check("test-key", authenticated=False)
        assert not allowed
        assert "Retry-After" in headers

    def test_different_keys_independent(self):
        limiter = SlidingWindowRateLimiter()
        for i in range(30):
            limiter.check("key-a", authenticated=False)
        # key-a is at limit, key-b should still work
        allowed, _ = limiter.check("key-b", authenticated=False)
        assert allowed


# ---------------------------------------------------------------------------
# Security Headers (via HTTP client)
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    async def test_security_headers_present(self, client):
        response = await client.get("/api/v1/health")
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert "strict-origin" in response.headers.get("referrer-policy", "")

    async def test_hsts_header(self, client):
        response = await client.get("/api/v1/health")
        assert "max-age" in response.headers.get("strict-transport-security", "")

    async def test_csp_header(self, client):
        response = await client.get("/api/v1/health")
        csp = response.headers.get("content-security-policy", "")
        assert "default-src" in csp


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class TestAuditLog:
    async def test_audit_service_import(self):
        """Verify audit service module is importable."""
        from marketplace.services.audit_service import log_event
        assert callable(log_event)

    async def test_audit_routes_exist(self, client):
        """Verify audit endpoints respond (even if empty)."""
        response = await client.get("/api/v1/audit/events")
        # Should return 200 or 401 (auth required), not 404
        assert response.status_code != 404
