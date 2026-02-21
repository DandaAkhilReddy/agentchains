"""Tests for A2UI session manager — session lifecycle, rate limiting, pending inputs."""

import uuid
from unittest.mock import patch

import pytest

from marketplace.a2ui.session_manager import A2UISessionManager


@pytest.fixture
def session_manager():
    return A2UISessionManager()


class TestSessionCreation:
    def test_create_session(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        assert session is not None
        assert session.agent_id == "agent-1"
        assert session.user_id == "user-1"

    def test_create_session_generates_id(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        assert hasattr(session, "session_id")
        assert len(session.session_id) > 0

    def test_create_session_unique_ids(self, session_manager):
        s1 = session_manager.create_session("agent-1", "user-1")
        s2 = session_manager.create_session("agent-1", "user-1")
        assert s1.session_id != s2.session_id

    def test_create_session_has_expected_fields(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        # A2UISession is a dataclass with these fields
        assert hasattr(session, "session_id")
        assert hasattr(session, "agent_id")
        assert hasattr(session, "user_id")
        assert hasattr(session, "created_at")

    def test_create_multiple_sessions_for_same_agent(self, session_manager):
        s1 = session_manager.create_session("agent-1", "user-1")
        s2 = session_manager.create_session("agent-1", "user-2")
        assert s1.session_id != s2.session_id

    def test_create_session_stores_in_manager(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        retrieved = session_manager.get_session(session.session_id)
        assert retrieved is not None


class TestSessionRetrieval:
    def test_get_existing_session(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        retrieved = session_manager.get_session(session.session_id)
        assert retrieved.agent_id == "agent-1"

    def test_get_nonexistent_session_returns_none(self, session_manager):
        result = session_manager.get_session("nonexistent-id")
        assert result is None

    def test_get_session_after_close_returns_none(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        session_manager.close_session(session.session_id)
        result = session_manager.get_session(session.session_id)
        assert result is None


class TestSessionClose:
    def test_close_session(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        result = session_manager.close_session(session.session_id)
        # close_session returns None (no return statement)
        assert result is None

    def test_close_nonexistent_session(self, session_manager):
        result = session_manager.close_session("nonexistent-id")
        # Should not raise; returns None
        assert result is None

    def test_close_session_removes_from_manager(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        session_manager.close_session(session.session_id)
        assert session_manager.get_session(session.session_id) is None


class TestSessionRateLimiting:
    def test_rate_limit_allows_initial_requests(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        # check_rate_limit takes an A2UISession object, not a string
        allowed = session_manager.check_rate_limit(session)
        assert allowed is True

    def test_rate_limit_allows_multiple_requests(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        for _ in range(10):
            allowed = session_manager.check_rate_limit(session)
            assert allowed is True

    def test_rate_limit_rejects_after_exceeding_limit(self, session_manager):
        mgr = A2UISessionManager(rate_limit_per_minute=5)
        session = mgr.create_session("agent-1", "user-1")
        for _ in range(5):
            mgr.check_rate_limit(session)
        # 6th request should be rejected
        assert mgr.check_rate_limit(session) is False


class TestSessionPendingInputs:
    def test_pending_inputs_initially_empty(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        assert len(session.pending_inputs) == 0

    def test_resolve_pending_input_returns_false_for_nonexistent(self, session_manager):
        session = session_manager.create_session("agent-1", "user-1")
        result = session_manager.resolve_pending_input(session.session_id, "nonexistent", "val")
        assert result is False

    def test_resolve_pending_input_returns_false_for_unknown_session(self, session_manager):
        result = session_manager.resolve_pending_input("nonexistent-sid", "req-1", "val")
        assert result is False


class TestConcurrentSessions:
    def test_many_sessions(self, session_manager):
        sessions = []
        for i in range(100):
            s = session_manager.create_session(f"agent-{i % 10}", f"user-{i}")
            sessions.append(s)
        assert len(sessions) == 100
        # All sessions should be retrievable
        for s in sessions:
            assert session_manager.get_session(s.session_id) is not None

    def test_close_all_sessions(self, session_manager):
        sessions = []
        for i in range(20):
            s = session_manager.create_session("agent-1", f"user-{i}")
            sessions.append(s)
        for s in sessions:
            session_manager.close_session(s.session_id)
        for s in sessions:
            assert session_manager.get_session(s.session_id) is None

    def test_mixed_create_and_close(self, session_manager):
        s1 = session_manager.create_session("agent-1", "user-1")
        s2 = session_manager.create_session("agent-1", "user-2")
        session_manager.close_session(s1.session_id)
        assert session_manager.get_session(s1.session_id) is None
        assert session_manager.get_session(s2.session_id) is not None

    def test_active_count(self, session_manager):
        session_manager.create_session("agent-1", "user-1")
        session_manager.create_session("agent-1", "user-2")
        assert session_manager.active_count == 2
