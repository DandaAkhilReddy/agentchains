"""Tests for uncovered lines in marketplace/a2ui/session_manager.py."""

import asyncio
import time
import pytest
from marketplace.a2ui.session_manager import A2UISessionManager, A2UISession


@pytest.fixture
def mgr():
    return A2UISessionManager(rate_limit_per_minute=10, session_timeout=2.0)


class TestSessionTimeout:
    def test_expired_session_returns_none(self, mgr):
        session = mgr.create_session('agent-1', 'user-1')
        # Manually set last_activity far in the past
        session.last_activity = time.monotonic() - 10.0
        result = mgr.get_session(session.session_id)
        assert result is None

    def test_active_session_not_expired(self, mgr):
        session = mgr.create_session('agent-1', 'user-1')
        result = mgr.get_session(session.session_id)
        assert result is not None


class TestRateLimitWindowReset:
    def test_rate_limit_resets_after_window(self, mgr):
        session = mgr.create_session('agent-1', 'user-1')
        for _ in range(10):
            mgr.check_rate_limit(session)
        assert mgr.check_rate_limit(session) is False
        # Simulate window reset by moving window_start back
        session.window_start = time.monotonic() - 61
        session.request_count = 0
        assert mgr.check_rate_limit(session) is True


class TestCleanupExpired:
    def test_cleanup_removes_expired(self, mgr):
        s1 = mgr.create_session('agent-1', 'user-1')
        s2 = mgr.create_session('agent-2', 'user-2')
        # Expire s1
        s1.last_activity = time.monotonic() - 10.0
        mgr.cleanup_expired()
        assert mgr.get_session(s1.session_id) is None
        assert mgr.get_session(s2.session_id) is not None

    def test_cleanup_preserves_active(self, mgr):
        s = mgr.create_session('agent-1', 'user-1')
        mgr.cleanup_expired()
        assert mgr.get_session(s.session_id) is not None


class TestPendingInputFutures:
    @pytest.mark.asyncio
    async def test_set_pending_input(self, mgr):
        session = mgr.create_session('agent-1', 'user-1')
        future = mgr.set_pending_input(session.session_id, 'req-1')
        assert isinstance(future, asyncio.Future)
        assert 'req-1' in session.pending_inputs

    @pytest.mark.asyncio
    async def test_resolve_pending_input(self, mgr):
        session = mgr.create_session('agent-1', 'user-1')
        future = mgr.set_pending_input(session.session_id, 'req-2')
        ok = mgr.resolve_pending_input(session.session_id, 'req-2', 'answer')
        assert ok is True
        assert future.result() == 'answer'

    @pytest.mark.asyncio
    async def test_resolve_already_done(self, mgr):
        session = mgr.create_session('agent-1', 'user-1')
        future = mgr.set_pending_input(session.session_id, 'req-3')
        future.set_result('first')
        ok = mgr.resolve_pending_input(session.session_id, 'req-3', 'second')
        assert ok is False

    @pytest.mark.asyncio
    async def test_set_pending_input_invalid_session(self, mgr):
        with pytest.raises(ValueError, match='not found'):
            mgr.set_pending_input('nonexistent', 'req-1')


class TestCloseSessionCancelsFutures:
    @pytest.mark.asyncio
    async def test_close_cancels_pending(self, mgr):
        session = mgr.create_session('agent-1', 'user-1')
        future = mgr.set_pending_input(session.session_id, 'req-1')
        mgr.close_session(session.session_id)
        assert future.cancelled()


class TestSessionCapabilities:
    def test_create_with_capabilities(self):
        mgr = A2UISessionManager()
        caps = {'streaming': True, 'file_upload': False}
        session = mgr.create_session('agent-1', capabilities=caps)
        assert session.capabilities == caps

    def test_create_without_capabilities(self):
        mgr = A2UISessionManager()
        session = mgr.create_session('agent-1')
        assert session.capabilities == {}


class TestActiveComponents:
    def test_active_components_tracking(self, mgr):
        session = mgr.create_session('agent-1', 'user-1')
        session.active_components.add('chart-1')
        session.active_components.add('table-1')
        assert len(session.active_components) == 2
