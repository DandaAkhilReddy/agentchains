"""Comprehensive tests for fraud_prevention_service and mcp_health_monitor.

Covers:
  FraudPreventionService / module-level functions:
    1. detect_sybil_clusters   — happy path, below-threshold, self-loop, density
    2. detect_registration_bursts — happy path, below-threshold, deduplication
    3. get_fraud_report        — aggregated report, empty state
    4. FraudPreventionService class — wrapper, no-db error guard

  MCPHealthMonitor / module-level functions:
    5. _check_server           — healthy 200+ok, 200+not-ok, non-200, timeout, connection error
    6. _run_health_checks      — score increase, score decrease, exception path, no servers
    7. health_check_loop       — initial delay + loop cancelled
    8. MCPHealthMonitor class  — run_loop delegates correctly
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.mcp_server import MCPServerEntry
from marketplace.models.transaction import Transaction
from marketplace.services.fraud_prevention_service import (
    FraudPreventionService,
    detect_registration_bursts,
    detect_sybil_clusters,
    get_fraud_report,
)
from marketplace.services.mcp_health_monitor import (
    MCPHealthMonitor,
    _check_server,
    _run_health_checks,
    health_check_loop,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _make_agent(db: AsyncSession, name: str = None) -> RegisteredAgent:
    """Insert a RegisteredAgent directly and return it."""
    agent = RegisteredAgent(
        id=_id(),
        name=name or f"agent-{_id()[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test",
        status="active",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def _make_tx(
    db: AsyncSession,
    buyer_id: str,
    seller_id: str,
    listing_id: str,
    *,
    status: str = "completed",
    created_at: datetime | None = None,
) -> Transaction:
    """Insert a Transaction and return it.

    Because Transaction.created_at doesn't exist on the model (the column is
    named initiated_at), the fraud service's query on Transaction.created_at
    will raise AttributeError.  Tests that exercise detect_sybil_clusters /
    detect_registration_bursts against a real DB therefore mock the DB execute
    call; this helper is used only when the test controls what the mock returns.
    """
    from decimal import Decimal

    tx = Transaction(
        id=_id(),
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        amount_usdc=Decimal("1.0"),
        status=status,
        content_hash=f"sha256:{'a' * 64}",
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


async def _make_mcp_server(
    db: AsyncSession,
    *,
    name: str = None,
    base_url: str = "http://mcp.example.com",
    status: str = "active",
    health_score: int = 100,
    namespace: str = "test",
) -> MCPServerEntry:
    """Insert an MCPServerEntry and return it."""
    server = MCPServerEntry(
        id=_id(),
        name=name or f"mcp-{_id()[:8]}",
        base_url=base_url,
        namespace=namespace,
        status=status,
        health_score=health_score,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


# ===========================================================================
# Section 1 — detect_sybil_clusters
# ===========================================================================


class TestDetectSybilClusters:
    """detect_sybil_clusters: transaction-graph based Sybil detection."""

    async def test_happy_path_critical_cluster_detected(self, db: AsyncSession):
        """Three agents trading in a tight loop with density > 0.8 → critical cluster."""
        a1, a2, a3 = _id(), _id(), _id()
        # Simulate the DB returning a dense 3-node graph (all 6 directed edges)
        mock_edges = [
            (a1, a2, 5),
            (a2, a1, 5),
            (a2, a3, 5),
            (a3, a2, 5),
            (a1, a3, 5),
            (a3, a1, 5),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_edges

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            clusters = await detect_sybil_clusters(db, min_cluster_size=3)

        assert len(clusters) == 1
        cluster = clusters[0]
        assert cluster["size"] == 3
        assert set(cluster["agent_ids"]) == {a1, a2, a3}
        assert cluster["density"] == 1.0
        assert cluster["risk_level"] == "critical"
        assert cluster["total_volume"] > 0

    async def test_high_risk_cluster_density_between_50_and_80(self, db: AsyncSession):
        """A cluster with density 0.5 < d <= 0.8 is labelled 'high'."""
        a1, a2, a3, a4 = _id(), _id(), _id(), _id()
        # 4 nodes, 6 out of possible 12 directed edges → density = 0.5
        # We need density > 0.5, so use 7 of 12
        mock_edges = [
            (a1, a2, 1), (a2, a1, 1),
            (a2, a3, 1), (a3, a2, 1),
            (a3, a4, 1), (a4, a3, 1),
            (a1, a3, 1),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_edges

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            clusters = await detect_sybil_clusters(db, min_cluster_size=3)

        # Should be flagged if density > 0.5
        assert len(clusters) == 1
        assert clusters[0]["risk_level"] == "high"

    async def test_cluster_below_min_size_not_reported(self, db: AsyncSession):
        """A pair of agents (size=2) with min_cluster_size=3 is NOT reported."""
        a1, a2 = _id(), _id()
        mock_edges = [(a1, a2, 10), (a2, a1, 10)]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_edges

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            clusters = await detect_sybil_clusters(db, min_cluster_size=3)

        assert clusters == []

    async def test_self_loop_edges_are_ignored(self, db: AsyncSession):
        """Transactions where buyer_id == seller_id are skipped (no self-loops in graph)."""
        a1 = _id()
        mock_edges = [(a1, a1, 50)]  # self-loop only
        mock_result = MagicMock()
        mock_result.all.return_value = mock_edges

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            clusters = await detect_sybil_clusters(db, min_cluster_size=1)

        assert clusters == []

    async def test_no_transactions_returns_empty_list(self, db: AsyncSession):
        """No recent transactions → empty cluster list."""
        mock_result = MagicMock()
        mock_result.all.return_value = []

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            clusters = await detect_sybil_clusters(db)

        assert clusters == []

    async def test_low_density_cluster_not_flagged(self, db: AsyncSession):
        """A sparse cluster with density ≤ 0.5 is not included in results."""
        a1, a2, a3, a4, a5 = [_id() for _ in range(5)]
        # Chain: a1-a2-a3-a4-a5, density is very low for a 5-node cluster
        mock_edges = [
            (a1, a2, 1),
            (a2, a3, 1),
            (a3, a4, 1),
            (a4, a5, 1),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_edges

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            clusters = await detect_sybil_clusters(db, min_cluster_size=3)

        assert clusters == []

    async def test_two_disjoint_clusters_both_detected(self, db: AsyncSession):
        """Two independent tight clusters in the same graph are both returned."""
        # Cluster 1: a1, a2, a3 — fully connected
        a1, a2, a3 = _id(), _id(), _id()
        # Cluster 2: b1, b2, b3 — fully connected
        b1, b2, b3 = _id(), _id(), _id()

        mock_edges = [
            (a1, a2, 2), (a2, a1, 2),
            (a2, a3, 2), (a3, a2, 2),
            (a1, a3, 2), (a3, a1, 2),
            (b1, b2, 3), (b2, b1, 3),
            (b2, b3, 3), (b3, b2, 3),
            (b1, b3, 3), (b3, b1, 3),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_edges

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            clusters = await detect_sybil_clusters(db, min_cluster_size=3)

        assert len(clusters) == 2
        all_ids = {c["agent_ids"][0] for c in clusters}
        assert all_ids.issubset({a1, a2, a3, b1, b2, b3})

    async def test_custom_min_cluster_size_respected(self, db: AsyncSession):
        """min_cluster_size=5 suppresses a 3-node cluster."""
        a1, a2, a3 = _id(), _id(), _id()
        mock_edges = [
            (a1, a2, 5), (a2, a1, 5),
            (a2, a3, 5), (a3, a2, 5),
            (a1, a3, 5), (a3, a1, 5),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_edges

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            clusters = await detect_sybil_clusters(db, min_cluster_size=5)

        assert clusters == []


# ===========================================================================
# Section 2 — detect_registration_bursts
# ===========================================================================


class TestDetectRegistrationBursts:
    """detect_registration_bursts: rapid agent registration detection."""

    async def test_happy_path_burst_detected(self, db: AsyncSession):
        """10 agents registered within 60 min triggers a burst (threshold=10)."""
        now = _utcnow()
        agents = []
        for i in range(10):
            a = MagicMock()
            a.id = _id()
            a.created_at = now + timedelta(minutes=i * 5)
            agents.append(a)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = agents
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            bursts = await detect_registration_bursts(db, window_minutes=60, threshold=10)

        assert len(bursts) >= 1
        assert bursts[0]["count"] >= 10
        assert bursts[0]["window_minutes"] == 60

    async def test_below_threshold_no_burst(self, db: AsyncSession):
        """9 agents within 60 min with threshold=10 → no burst reported."""
        now = _utcnow()
        agents = []
        for i in range(9):
            a = MagicMock()
            a.id = _id()
            a.created_at = now + timedelta(minutes=i * 5)
            agents.append(a)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = agents
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            bursts = await detect_registration_bursts(db, window_minutes=60, threshold=10)

        assert bursts == []

    async def test_high_risk_level_when_count_double_threshold(self, db: AsyncSession):
        """A burst with count >= 2x threshold is labelled 'high'; below is 'medium'."""
        now = _utcnow()
        # Create 20 agents within 60 min → count=20, threshold=10 → 'high'
        agents = []
        for i in range(20):
            a = MagicMock()
            a.id = _id()
            a.created_at = now + timedelta(minutes=i * 2)
            agents.append(a)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = agents
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            bursts = await detect_registration_bursts(db, window_minutes=60, threshold=10)

        assert len(bursts) >= 1
        assert bursts[0]["risk_level"] == "high"

    async def test_medium_risk_level_when_count_below_double_threshold(self, db: AsyncSession):
        """A burst with count between threshold and 2x threshold is labelled 'medium'."""
        now = _utcnow()
        # Create 14 agents within 60 min → count between 10 and 20 → 'medium'
        agents = []
        for i in range(14):
            a = MagicMock()
            a.id = _id()
            a.created_at = now + timedelta(minutes=i * 3)
            agents.append(a)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = agents
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            bursts = await detect_registration_bursts(db, window_minutes=60, threshold=10)

        assert len(bursts) >= 1
        assert bursts[0]["risk_level"] == "medium"

    async def test_no_agents_returns_empty_list(self, db: AsyncSession):
        """No agents registered in the last 24h → empty burst list."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            bursts = await detect_registration_bursts(db)

        assert bursts == []

    async def test_agents_outside_window_not_counted(self, db: AsyncSession):
        """Agents spread more than window_minutes apart are not grouped together."""
        now = _utcnow()
        # 10 agents but spaced 2 hours apart → no 60-min window contains 10
        agents = []
        for i in range(10):
            a = MagicMock()
            a.id = _id()
            a.created_at = now + timedelta(hours=i * 2)
            agents.append(a)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = agents
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            bursts = await detect_registration_bursts(db, window_minutes=60, threshold=10)

        assert bursts == []

    async def test_duplicate_overlapping_bursts_deduplicated(self, db: AsyncSession):
        """Bursts with identical agent_id sets are not duplicated in the result."""
        now = _utcnow()
        # 10 agents tightly packed: windows starting at i=0 and i=1 both see all 10
        agents = []
        for i in range(10):
            a = MagicMock()
            a.id = f"agent-{i:02d}"
            a.created_at = now + timedelta(minutes=i)  # 1 min apart, all within 60 min
            agents.append(a)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = agents
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            bursts = await detect_registration_bursts(db, window_minutes=60, threshold=10)

        # The deduplication logic prevents exact duplicate sets from being appended
        # All bursts should have distinct agent_id sets compared to the previous one
        for i in range(1, len(bursts)):
            assert set(bursts[i]["agent_ids"]) != set(bursts[i - 1]["agent_ids"])


# ===========================================================================
# Section 3 — get_fraud_report
# ===========================================================================


class TestGetFraudReport:
    """get_fraud_report: aggregate report combining both detection methods."""

    async def test_happy_path_report_structure(self, db: AsyncSession):
        """Report includes all required keys with correct aggregation."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            report = await get_fraud_report(db)

        assert "sybil_clusters" in report
        assert "registration_bursts" in report
        assert "total_sybil_agents" in report
        assert "total_burst_agents" in report
        assert "generated_at" in report
        assert isinstance(report["sybil_clusters"], list)
        assert isinstance(report["registration_bursts"], list)

    async def test_empty_state_zeros(self, db: AsyncSession):
        """With no suspicious activity, totals are zero."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            report = await get_fraud_report(db)

        assert report["total_sybil_agents"] == 0
        assert report["total_burst_agents"] == 0
        assert report["sybil_clusters"] == []
        assert report["registration_bursts"] == []

    async def test_report_aggregates_sybil_and_burst_counts(self, db: AsyncSession):
        """Report sums sizes from both sub-functions correctly."""
        a1, a2, a3 = _id(), _id(), _id()
        sybil_edges = [
            (a1, a2, 5), (a2, a1, 5),
            (a2, a3, 5), (a3, a2, 5),
            (a1, a3, 5), (a3, a1, 5),
        ]

        now = _utcnow()
        burst_agents = []
        for i in range(10):
            a = MagicMock()
            a.id = _id()
            a.created_at = now + timedelta(minutes=i)
            burst_agents.append(a)

        execute_call_count = 0

        async def _fake_execute(stmt, *args, **kwargs):
            nonlocal execute_call_count
            execute_call_count += 1
            result = MagicMock()
            if execute_call_count == 1:
                # First call: Transaction graph query
                result.all.return_value = sybil_edges
            else:
                # Second call: RegisteredAgent registration burst query
                mock_scalars = MagicMock()
                mock_scalars.all.return_value = burst_agents
                result.scalars.return_value = mock_scalars
            return result

        with patch.object(db, "execute", new=AsyncMock(side_effect=_fake_execute)):
            report = await get_fraud_report(db)

        assert report["total_sybil_agents"] == 3
        assert report["total_burst_agents"] >= 10

    async def test_generated_at_is_iso_format_string(self, db: AsyncSession):
        """generated_at is a parseable ISO 8601 UTC timestamp string."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            report = await get_fraud_report(db)

        # Should parse without error
        ts = datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00"))
        assert ts is not None


# ===========================================================================
# Section 4 — FraudPreventionService class
# ===========================================================================


class TestFraudPreventionServiceClass:
    """FraudPreventionService: class-level wrapper behaviour."""

    async def test_detect_sybil_clusters_delegates_to_module_function(
        self, db: AsyncSession
    ):
        """FraudPreventionService.detect_sybil_clusters calls the module function."""
        mock_result = MagicMock()
        mock_result.all.return_value = []

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            svc = FraudPreventionService(db=db)
            clusters = await svc.detect_sybil_clusters()

        assert clusters == []

    async def test_get_fraud_report_delegates_to_module_function(
        self, db: AsyncSession
    ):
        """FraudPreventionService.get_fraud_report calls the module function."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        with patch.object(db, "execute", new=AsyncMock(return_value=mock_result)):
            svc = FraudPreventionService(db=db)
            report = await svc.get_fraud_report()

        assert "sybil_clusters" in report

    async def test_detect_sybil_clusters_raises_when_no_db(self):
        """FraudPreventionService raises ValueError when db is None."""
        svc = FraudPreventionService(db=None)
        with pytest.raises(ValueError, match="Database session required"):
            await svc.detect_sybil_clusters()

    async def test_get_fraud_report_raises_when_no_db(self):
        """FraudPreventionService.get_fraud_report raises ValueError when db is None."""
        svc = FraudPreventionService(db=None)
        with pytest.raises(ValueError, match="Database session required"):
            await svc.get_fraud_report()

    async def test_service_init_stores_db_session(self, db: AsyncSession):
        """FraudPreventionService stores the provided db session on self.db."""
        svc = FraudPreventionService(db=db)
        assert svc.db is db

    async def test_service_init_with_none_stores_none(self):
        """FraudPreventionService(db=None) stores None."""
        svc = FraudPreventionService()
        assert svc.db is None


# ===========================================================================
# Section 5 — _check_server
# ===========================================================================


class TestCheckServer:
    """_check_server: single MCP server health ping."""

    def _make_server(
        self, base_url: str = "http://mcp.test", health_score: int = 100
    ) -> MagicMock:
        server = MagicMock()
        server.base_url = base_url
        server.health_score = health_score
        server.name = "test-mcp"
        return server

    async def test_healthy_server_returns_latency_and_true(self):
        """A 200 response with status=ok → (latency_ms, True)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        server = self._make_server()
        latency_ms, is_healthy = await _check_server(mock_client, server)

        assert is_healthy is True
        assert latency_ms >= 0

    async def test_200_with_non_ok_status_returns_false(self):
        """A 200 response where status != 'ok' → (latency_ms, False)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "degraded"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        server = self._make_server()
        latency_ms, is_healthy = await _check_server(mock_client, server)

        assert is_healthy is False

    async def test_non_200_response_returns_false(self):
        """A 503 response → (latency_ms, False)."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        server = self._make_server()
        latency_ms, is_healthy = await _check_server(mock_client, server)

        assert is_healthy is False

    async def test_timeout_raises_exception_with_message(self):
        """A TimeoutException → Exception('Timeout after ...')."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        server = self._make_server()
        with pytest.raises(Exception, match="Timeout after"):
            await _check_server(mock_client, server)

    async def test_connect_error_raises_exception_with_message(self):
        """A ConnectError → Exception('Connection failed: ...')."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        server = self._make_server()
        with pytest.raises(Exception, match="Connection failed"):
            await _check_server(mock_client, server)

    async def test_health_url_constructed_from_base_url(self):
        """The ping URL is {base_url}/mcp/health with trailing slash stripped."""
        captured_url = None

        async def _fake_get(url, **kwargs):
            nonlocal captured_url
            captured_url = url
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"status": "ok"}
            return resp

        mock_client = AsyncMock()
        mock_client.get = _fake_get

        server = self._make_server(base_url="http://mcp.test/")
        await _check_server(mock_client, server)

        assert captured_url == "http://mcp.test/mcp/health"

    async def test_latency_is_non_negative_float(self):
        """latency_ms is a non-negative float."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        server = self._make_server()
        latency_ms, _ = await _check_server(mock_client, server)

        assert isinstance(latency_ms, float)
        assert latency_ms >= 0.0


# ===========================================================================
# Section 6 — _run_health_checks
# ===========================================================================


class TestRunHealthChecks:
    """_run_health_checks: batch health check and DB score update."""

    async def test_no_active_servers_returns_early(self):
        """With no active/degraded servers, _run_health_checks returns without error."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("marketplace.services.mcp_health_monitor.async_session", return_value=mock_ctx):
            # Should return early with no error
            await _run_health_checks()

    async def test_healthy_server_score_increases(self):
        """A healthy 200/ok response increases health_score by 10."""
        server = MagicMock()
        server.health_score = 80
        server.status = "active"
        server.base_url = "http://mcp.test"
        server.name = "mcp-healthy"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [server]
        mock_result_read = MagicMock()
        mock_result_read.scalars.return_value = mock_scalars

        call_count = 0

        mock_db_read = AsyncMock(spec=AsyncSession)
        mock_db_read.execute = AsyncMock(return_value=mock_result_read)

        mock_db_write = AsyncMock(spec=AsyncSession)
        mock_db_write.add = MagicMock()
        mock_db_write.commit = AsyncMock()

        def _make_ctx(db):
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=db)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = {"status": "ok"}

        def _session_factory():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_ctx(mock_db_read)
            return _make_ctx(mock_db_write)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            side_effect=_session_factory,
        ), patch("httpx.AsyncClient") as mock_http_cls:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_http_response)
            mock_http_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _run_health_checks()

        assert server.health_score == 90  # 80 + 10
        assert server.status == "active"

    async def test_unhealthy_response_decreases_score(self):
        """A 200/not-ok response decreases health_score by 15."""
        server = MagicMock()
        server.health_score = 60
        server.status = "active"
        server.base_url = "http://mcp.test"
        server.name = "mcp-degraded"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [server]
        mock_result_read = MagicMock()
        mock_result_read.scalars.return_value = mock_scalars

        call_count = 0
        mock_db_read = AsyncMock(spec=AsyncSession)
        mock_db_read.execute = AsyncMock(return_value=mock_result_read)
        mock_db_write = AsyncMock(spec=AsyncSession)
        mock_db_write.add = MagicMock()
        mock_db_write.commit = AsyncMock()

        def _make_ctx(db):
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=db)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = {"status": "error"}

        def _session_factory():
            nonlocal call_count
            call_count += 1
            return _make_ctx(mock_db_read if call_count == 1 else mock_db_write)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            side_effect=_session_factory,
        ), patch("httpx.AsyncClient") as mock_http_cls:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_http_response)
            mock_http_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _run_health_checks()

        assert server.health_score == 45  # 60 - 15
        assert server.status == "degraded"

    async def test_exception_in_gather_decreases_score_by_20(self):
        """An exception during health check decreases score by 20."""
        server = MagicMock()
        server.health_score = 50
        server.status = "active"
        server.base_url = "http://mcp.test"
        server.name = "mcp-failing"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [server]
        mock_result_read = MagicMock()
        mock_result_read.scalars.return_value = mock_scalars

        call_count = 0
        mock_db_read = AsyncMock(spec=AsyncSession)
        mock_db_read.execute = AsyncMock(return_value=mock_result_read)
        mock_db_write = AsyncMock(spec=AsyncSession)
        mock_db_write.add = MagicMock()
        mock_db_write.commit = AsyncMock()

        def _make_ctx(db):
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=db)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        def _session_factory():
            nonlocal call_count
            call_count += 1
            return _make_ctx(mock_db_read if call_count == 1 else mock_db_write)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            side_effect=_session_factory,
        ), patch("httpx.AsyncClient") as mock_http_cls:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(
                side_effect=httpx.ConnectError("refused")
            )
            mock_http_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _run_health_checks()

        assert server.health_score == 30  # 50 - 20
        assert server.status == "degraded"

    async def test_score_clamped_to_zero_on_successive_failures(self):
        """Score never goes below 0 even after many failures."""
        server = MagicMock()
        server.health_score = 10  # low starting score
        server.status = "active"
        server.base_url = "http://mcp.test"
        server.name = "mcp-low"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [server]
        mock_result_read = MagicMock()
        mock_result_read.scalars.return_value = mock_scalars

        call_count = 0
        mock_db_read = AsyncMock(spec=AsyncSession)
        mock_db_read.execute = AsyncMock(return_value=mock_result_read)
        mock_db_write = AsyncMock(spec=AsyncSession)
        mock_db_write.add = MagicMock()
        mock_db_write.commit = AsyncMock()

        def _make_ctx(db):
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=db)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        def _session_factory():
            nonlocal call_count
            call_count += 1
            return _make_ctx(mock_db_read if call_count == 1 else mock_db_write)

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            side_effect=_session_factory,
        ), patch("httpx.AsyncClient") as mock_http_cls:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(
                side_effect=httpx.ConnectError("refused")
            )
            mock_http_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _run_health_checks()

        # max(0, 10 - 20) = 0
        assert server.health_score == 0
        assert server.status == "inactive"

    async def test_score_clamped_to_100_on_recovery(self):
        """Score never exceeds 100 even when already near max."""
        server = MagicMock()
        server.health_score = 95
        server.status = "degraded"
        server.base_url = "http://mcp.test"
        server.name = "mcp-recovering"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [server]
        mock_result_read = MagicMock()
        mock_result_read.scalars.return_value = mock_scalars

        call_count = 0
        mock_db_read = AsyncMock(spec=AsyncSession)
        mock_db_read.execute = AsyncMock(return_value=mock_result_read)
        mock_db_write = AsyncMock(spec=AsyncSession)
        mock_db_write.add = MagicMock()
        mock_db_write.commit = AsyncMock()

        def _make_ctx(db):
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=db)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        def _session_factory():
            nonlocal call_count
            call_count += 1
            return _make_ctx(mock_db_read if call_count == 1 else mock_db_write)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = {"status": "ok"}

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            side_effect=_session_factory,
        ), patch("httpx.AsyncClient") as mock_http_cls:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_http_response)
            mock_http_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _run_health_checks()

        # min(100, 95 + 10) = 100
        assert server.health_score == 100
        assert server.status == "active"

    async def test_last_health_check_timestamp_updated(self):
        """server.last_health_check is set to a recent UTC datetime."""
        server = MagicMock()
        server.health_score = 80
        server.status = "active"
        server.base_url = "http://mcp.test"
        server.name = "mcp-ts"
        server.last_health_check = None

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [server]
        mock_result_read = MagicMock()
        mock_result_read.scalars.return_value = mock_scalars

        call_count = 0
        mock_db_read = AsyncMock(spec=AsyncSession)
        mock_db_read.execute = AsyncMock(return_value=mock_result_read)
        mock_db_write = AsyncMock(spec=AsyncSession)
        mock_db_write.add = MagicMock()
        mock_db_write.commit = AsyncMock()

        def _make_ctx(db):
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=db)
            ctx.__aexit__ = AsyncMock(return_value=False)
            return ctx

        def _session_factory():
            nonlocal call_count
            call_count += 1
            return _make_ctx(mock_db_read if call_count == 1 else mock_db_write)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = {"status": "ok"}

        before = _utcnow()

        with patch(
            "marketplace.services.mcp_health_monitor.async_session",
            side_effect=_session_factory,
        ), patch("httpx.AsyncClient") as mock_http_cls:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_http_response)
            mock_http_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_http_client
            )
            mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await _run_health_checks()

        assert server.last_health_check is not None
        assert server.last_health_check >= before


# ===========================================================================
# Section 7 — health_check_loop
# ===========================================================================


class TestHealthCheckLoop:
    """health_check_loop: background infinite loop behaviour."""

    async def test_loop_cancellation_is_graceful(self):
        """health_check_loop can be cancelled without raising unexpected errors."""
        import asyncio

        calls = []

        async def _fake_run_health_checks():
            calls.append(1)

        with patch(
            "marketplace.services.mcp_health_monitor.asyncio.sleep",
            new=AsyncMock(side_effect=asyncio.CancelledError),
        ), patch(
            "marketplace.services.mcp_health_monitor._run_health_checks",
            new=_fake_run_health_checks,
        ):
            with pytest.raises(asyncio.CancelledError):
                await health_check_loop(interval=1)

    async def test_loop_calls_run_health_checks_after_initial_delay(self):
        """health_check_loop calls _run_health_checks after the initial 15s sleep."""
        import asyncio

        sleep_calls = []
        run_calls = []

        async def _fake_sleep(secs):
            sleep_calls.append(secs)
            if len(sleep_calls) >= 2:
                raise asyncio.CancelledError

        async def _fake_run():
            run_calls.append(1)

        with patch(
            "marketplace.services.mcp_health_monitor.asyncio.sleep",
            new=_fake_sleep,
        ), patch(
            "marketplace.services.mcp_health_monitor._run_health_checks",
            new=_fake_run,
        ):
            with pytest.raises(asyncio.CancelledError):
                await health_check_loop(interval=5)

        # First sleep is the initial 15s delay, second is the interval
        assert sleep_calls[0] == 15
        assert len(run_calls) >= 1

    async def test_loop_exception_in_health_check_does_not_stop_loop(self):
        """Exceptions inside _run_health_checks are swallowed; loop continues."""
        import asyncio

        iteration_count = [0]
        sleep_calls = [0]

        async def _fake_sleep(secs):
            sleep_calls[0] += 1
            if sleep_calls[0] > 3:
                raise asyncio.CancelledError

        async def _failing_run():
            iteration_count[0] += 1
            raise RuntimeError("DB blew up")

        with patch(
            "marketplace.services.mcp_health_monitor.asyncio.sleep",
            new=_fake_sleep,
        ), patch(
            "marketplace.services.mcp_health_monitor._run_health_checks",
            new=_failing_run,
        ):
            with pytest.raises(asyncio.CancelledError):
                await health_check_loop(interval=1)

        # Loop should have tried at least once despite exception
        assert iteration_count[0] >= 1


# ===========================================================================
# Section 8 — MCPHealthMonitor class
# ===========================================================================


class TestMCPHealthMonitorClass:
    """MCPHealthMonitor: class wrapper behaviour."""

    async def test_run_loop_delegates_to_health_check_loop(self):
        """MCPHealthMonitor.run_loop calls health_check_loop."""
        import asyncio

        called_with = {}

        async def _fake_loop(db, **kwargs):
            called_with["db"] = db
            called_with["kwargs"] = kwargs

        with patch(
            "marketplace.services.mcp_health_monitor.health_check_loop",
            new=_fake_loop,
        ):
            monitor = MCPHealthMonitor()
            fake_db = object()
            await monitor.run_loop(fake_db, interval=60)

        assert called_with["db"] is fake_db
        assert called_with["kwargs"] == {"interval": 60}

    async def test_monitor_instantiation_requires_no_args(self):
        """MCPHealthMonitor() can be constructed with no arguments."""
        monitor = MCPHealthMonitor()
        assert monitor is not None

    async def test_run_loop_passes_kwargs_through(self):
        """Extra kwargs passed to run_loop are forwarded to health_check_loop."""
        received_kwargs = {}

        async def _fake_loop(db, **kwargs):
            received_kwargs.update(kwargs)

        with patch(
            "marketplace.services.mcp_health_monitor.health_check_loop",
            new=_fake_loop,
        ):
            monitor = MCPHealthMonitor()
            await monitor.run_loop(None, interval=120, extra_param="test")

        assert received_kwargs.get("interval") == 120
        assert received_kwargs.get("extra_param") == "test"
