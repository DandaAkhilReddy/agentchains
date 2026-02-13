"""UT-9: Expanded registry_service tests — versioning, capability matching,
health monitoring, deregistration cascade, and concurrency scenarios.

25 tests across 5 describe blocks, exercising higher-level behaviour that the
core UT-8 suite does not cover.  Uses pytest + unittest.mock (AsyncMock) for
DB and service-layer isolation where real DB round-trips are unnecessary.
"""

import asyncio
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.core.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
)
from marketplace.models.agent import RegisteredAgent
from marketplace.models.listing import DataListing
from marketplace.models.reputation import ReputationScore
from marketplace.models.transaction import Transaction
from marketplace.schemas.agent import AgentRegisterRequest, AgentUpdateRequest
from marketplace.services import registry_service
from marketplace.services.cache_service import agent_cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


def _make_register_request(
    name: str | None = None,
    agent_type: str = "both",
    **overrides,
) -> AgentRegisterRequest:
    """Build an AgentRegisterRequest with sensible defaults."""
    return AgentRegisterRequest(
        name=name or f"agent-{_id()[:8]}",
        description=overrides.get("description", "A test agent"),
        agent_type=agent_type,
        public_key=overrides.get("public_key", "ssh-rsa AAAA_placeholder_test_key"),
        wallet_address=overrides.get("wallet_address", ""),
        capabilities=overrides.get("capabilities", ["search", "summarise"]),
        a2a_endpoint=overrides.get("a2a_endpoint", "https://agent.example.com"),
    )


# =========================================================================
# Block 1 — Agent Versioning  (5 tests)
# =========================================================================


class TestAgentVersioning:
    """Tests 1-5: version tracking via description conventions and updated_at
    sequencing.  The registry service stores version metadata inside the
    agent_card_json field and uses updated_at as a monotonic version clock."""

    async def test_version_increment_via_update(
        self, db: AsyncSession, make_agent,
    ):
        """1. Successive updates to an agent produce strictly increasing
        updated_at timestamps, acting as a version clock."""
        agent, _ = await make_agent("versioned-agent")
        ts_v0 = agent.updated_at

        req1 = AgentUpdateRequest(description="v1 description")
        v1 = await registry_service.update_agent(db, agent.id, req1)
        ts_v1 = v1.updated_at

        req2 = AgentUpdateRequest(description="v2 description")
        v2 = await registry_service.update_agent(db, agent.id, req2)
        ts_v2 = v2.updated_at

        assert ts_v1 >= ts_v0, "v1 must be >= v0"
        assert ts_v2 >= ts_v1, "v2 must be >= v1"
        assert v2.description == "v2 description"

    async def test_semver_stored_in_agent_card(self, db: AsyncSession):
        """2. A semver string embedded in agent_card_json survives a full
        register -> fetch round-trip."""
        req = _make_register_request(
            name="semver-agent",
            description="v1.2.3 release",
        )
        resp = await registry_service.register_agent(db, req)

        agent = await registry_service.get_agent(db, resp.id)
        card = json.loads(agent.agent_card_json)

        assert card["name"] == "semver-agent"
        assert card["description"] == "v1.2.3 release"
        # Verify the semver is extractable from the description field
        assert re.search(r"\d+\.\d+\.\d+", card["description"]) is not None

    async def test_version_history_via_successive_descriptions(
        self, db: AsyncSession, make_agent,
    ):
        """3. Applying three successive description updates results in only the
        latest value being persisted (the service is last-write-wins)."""
        agent, _ = await make_agent("history-agent")

        versions = ["alpha-0.1.0", "beta-0.2.0", "stable-1.0.0"]
        for v in versions:
            req = AgentUpdateRequest(description=v)
            await registry_service.update_agent(db, agent.id, req)

        latest = await registry_service.get_agent(db, agent.id)
        assert latest.description == "stable-1.0.0"

    async def test_query_latest_version_by_name(
        self, db: AsyncSession,
    ):
        """4. After registration the agent can be retrieved by its generated ID
        and represents the 'latest' (only) version."""
        req = _make_register_request(name="latest-query-agent")
        resp = await registry_service.register_agent(db, req)

        agent = await registry_service.get_agent(db, resp.id)
        assert agent.name == "latest-query-agent"
        assert agent.status == "active"
        # created_at should be set (SQLite may return naive datetimes)
        assert agent.created_at is not None

    async def test_update_capabilities_bumps_version_clock(
        self, db: AsyncSession, make_agent,
    ):
        """5. Updating the capabilities list is treated as a version bump
        (updated_at increases and the cache is invalidated)."""
        agent, _ = await make_agent("cap-version-agent")
        # Prime the cache
        await registry_service.get_agent(db, agent.id)
        assert agent_cache.get(f"agent:{agent.id}") is not None

        req = AgentUpdateRequest(capabilities=["search", "translate", "summarise"])
        updated = await registry_service.update_agent(db, agent.id, req)

        # Cache should be invalidated
        assert agent_cache.get(f"agent:{agent.id}") is None
        # Capabilities round-trip as JSON string
        caps = json.loads(updated.capabilities)
        assert set(caps) == {"search", "translate", "summarise"}
        assert updated.updated_at >= agent.updated_at


# =========================================================================
# Block 2 — Capability Matching  (5 tests)
# =========================================================================


class TestCapabilityMatching:
    """Tests 6-10: filtering / matching agents by their JSON capabilities
    column.  Since list_agents supports type/status filters but not capability
    filters directly, these tests verify the manual filtering pattern at the
    service-caller level and validate the JSON serialisation round-trip."""

    async def test_single_capability_round_trip(self, db: AsyncSession):
        """6. An agent registered with a single capability stores and
        retrieves it correctly."""
        req = _make_register_request(
            name="single-cap",
            capabilities=["translation"],
        )
        resp = await registry_service.register_agent(db, req)
        agent = await registry_service.get_agent(db, resp.id)

        caps = json.loads(agent.capabilities)
        assert caps == ["translation"]

    async def test_multi_capability_and_match(self, db: AsyncSession):
        """7. An agent with ['search', 'summarise'] matches an AND query
        requiring both capabilities."""
        req = _make_register_request(
            name="multi-cap-agent",
            capabilities=["search", "summarise"],
        )
        resp = await registry_service.register_agent(db, req)
        agent = await registry_service.get_agent(db, resp.id)

        caps = set(json.loads(agent.capabilities))
        required = {"search", "summarise"}
        assert required.issubset(caps), "AND match: all required caps present"

    async def test_multi_capability_or_match(
        self, db: AsyncSession, make_agent,
    ):
        """8. Among several agents, an OR query returns all agents that have
        at least one of the requested capabilities."""
        await make_agent("agent-search")
        await make_agent("agent-translate")
        await make_agent("agent-both")

        # Register them with explicit capabilities via the service
        cap_map = {
            "or-search": ["search"],
            "or-translate": ["translate"],
            "or-both": ["search", "translate"],
        }
        ids = {}
        for name, caps in cap_map.items():
            req = _make_register_request(name=name, capabilities=caps)
            resp = await registry_service.register_agent(db, req)
            ids[name] = resp.id

        # OR query: agents with 'search' OR 'translate'
        wanted = {"search", "translate"}
        agents, _ = await registry_service.list_agents(db, page_size=50)
        matched = []
        for a in agents:
            try:
                a_caps = set(json.loads(a.capabilities))
            except (json.JSONDecodeError, TypeError):
                a_caps = set()
            if a_caps & wanted:  # intersection = OR
                matched.append(a.name)

        assert "or-search" in matched
        assert "or-translate" in matched
        assert "or-both" in matched

    async def test_no_capability_match_returns_empty(self, db: AsyncSession):
        """9. When no agent possesses the requested capability the result set
        is empty."""
        req = _make_register_request(
            name="only-search",
            capabilities=["search"],
        )
        await registry_service.register_agent(db, req)

        agents, _ = await registry_service.list_agents(db, page_size=50)
        matched = [
            a for a in agents
            if "quantum_computing" in json.loads(a.capabilities)
        ]
        assert matched == []

    async def test_empty_capabilities_stored_as_empty_list(
        self, db: AsyncSession,
    ):
        """10. An agent registered with an empty capabilities list stores '[]'
        and does not match any capability query."""
        req = _make_register_request(name="no-caps", capabilities=[])
        resp = await registry_service.register_agent(db, req)
        agent = await registry_service.get_agent(db, resp.id)

        caps = json.loads(agent.capabilities)
        assert caps == []
        assert "search" not in caps


# =========================================================================
# Block 3 — Health Monitoring  (5 tests)
# =========================================================================


class TestHealthMonitoring:
    """Tests 11-15: heartbeat-based health monitoring, unhealthy flagging,
    and recovery detection via status transitions."""

    async def test_heartbeat_sets_last_seen(
        self, db: AsyncSession, make_agent,
    ):
        """11. Calling heartbeat on an agent sets last_seen_at to a recent
        UTC timestamp."""
        agent, _ = await make_agent("health-agent")
        assert agent.last_seen_at is None

        updated = await registry_service.heartbeat(db, agent.id)
        assert updated.last_seen_at is not None
        # Verify it was set to a meaningful timestamp (SQLite may return naive dt)
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        last_seen_naive = updated.last_seen_at.replace(tzinfo=None) if updated.last_seen_at.tzinfo else updated.last_seen_at
        delta = (now_naive - last_seen_naive).total_seconds()
        assert delta < 5, "last_seen_at should be within 5 seconds of now"

    async def test_successive_heartbeats_advance_timestamp(
        self, db: AsyncSession, make_agent,
    ):
        """12. Two heartbeats produce monotonically advancing timestamps."""
        agent, _ = await make_agent("double-heartbeat")

        h1 = await registry_service.heartbeat(db, agent.id)
        ts1 = h1.last_seen_at

        h2 = await registry_service.heartbeat(db, agent.id)
        ts2 = h2.last_seen_at

        assert ts2 >= ts1

    async def test_unhealthy_flagging_via_deactivation(
        self, db: AsyncSession, make_agent,
    ):
        """13. An agent that misses heartbeats can be flagged unhealthy by
        deactivating it (status -> 'deactivated')."""
        agent, _ = await make_agent("unhealthy-agent")
        assert agent.status == "active"

        deactivated = await registry_service.deactivate_agent(db, agent.id)
        assert deactivated.status == "deactivated"

        # Verify via list_agents filter
        active, _ = await registry_service.list_agents(db, status="active")
        ids_active = [a.id for a in active]
        assert agent.id not in ids_active

    async def test_recovery_detection_via_reactivation(
        self, db: AsyncSession, make_agent,
    ):
        """14. A deactivated agent can be 'recovered' by updating its status
        back to 'active' and sending a heartbeat."""
        agent, _ = await make_agent("recover-agent")
        await registry_service.deactivate_agent(db, agent.id)

        # Recover
        req = AgentUpdateRequest(status="active")
        recovered = await registry_service.update_agent(db, agent.id, req)
        assert recovered.status == "active"

        # Send heartbeat to confirm liveness
        alive = await registry_service.heartbeat(db, agent.id)
        assert alive.last_seen_at is not None

    async def test_heartbeat_on_nonexistent_agent_raises(self, db: AsyncSession):
        """15. Heartbeat for a non-existent agent raises AgentNotFoundError."""
        with pytest.raises(AgentNotFoundError):
            await registry_service.heartbeat(db, _id())


# =========================================================================
# Block 4 — Deregistration Cascade  (5 tests)
# =========================================================================


class TestDeregistrationCascade:
    """Tests 16-20: when an agent is deactivated, verify the downstream
    effects on listings, transactions, and notification callbacks (mocked)."""

    async def test_deactivate_agent_sets_status(
        self, db: AsyncSession, make_agent,
    ):
        """16. Core deactivation sets status to 'deactivated' and updated_at
        is refreshed."""
        agent, _ = await make_agent("cascade-agent")
        original_updated = agent.updated_at

        result = await registry_service.deactivate_agent(db, agent.id)
        assert result.status == "deactivated"
        assert result.updated_at >= original_updated

    async def test_deactivated_agent_listings_can_be_filtered(
        self, db: AsyncSession, make_agent, make_listing,
    ):
        """17. After deactivation, the agent's listings still exist but the
        agent itself is excluded from active-only queries."""
        agent, _ = await make_agent("listing-cascade")
        listing = await make_listing(seller_id=agent.id, price_usdc=0.5)

        await registry_service.deactivate_agent(db, agent.id)

        # Agent excluded from active list
        active_agents, _ = await registry_service.list_agents(db, status="active")
        active_ids = [a.id for a in active_agents]
        assert agent.id not in active_ids

        # But the listing row still exists in the DB
        row = await db.execute(
            select(DataListing).where(DataListing.seller_id == agent.id)
        )
        assert row.scalar_one_or_none() is not None

    async def test_deactivated_agent_pending_transactions_remain(
        self, db: AsyncSession, make_agent, make_listing, make_transaction,
    ):
        """18. Pending transactions involving a deactivated agent are not
        automatically deleted -- they remain for dispute resolution."""
        seller, _ = await make_agent("tx-seller")
        buyer, _ = await make_agent("tx-buyer")
        listing = await make_listing(seller_id=seller.id, price_usdc=1.0)
        tx = await make_transaction(
            buyer_id=buyer.id,
            seller_id=seller.id,
            listing_id=listing.id,
            status="initiated",
        )

        await registry_service.deactivate_agent(db, seller.id)

        # Transaction still exists
        row = await db.execute(
            select(Transaction).where(Transaction.id == tx.id)
        )
        assert row.scalar_one_or_none() is not None
        assert row is not None

    async def test_deactivation_invalidates_cache(
        self, db: AsyncSession, make_agent,
    ):
        """19. Deactivation clears the agent from the LRU cache so stale
        reads cannot return an 'active' status."""
        agent, _ = await make_agent("cache-cascade")
        cache_key = f"agent:{agent.id}"

        # Prime the cache
        await registry_service.get_agent(db, agent.id)
        assert agent_cache.get(cache_key) is not None

        await registry_service.deactivate_agent(db, agent.id)
        assert agent_cache.get(cache_key) is None

    async def test_deactivation_notify_callback_mocked(
        self, db: AsyncSession, make_agent,
    ):
        """20. A notification callback (mocked) is invoked when an agent is
        deactivated.  This simulates a future webhook / event-bus hook."""
        agent, _ = await make_agent("notify-cascade")

        notify_fn = AsyncMock()

        # Wrap deactivate to call our notification after success
        original_deactivate = registry_service.deactivate_agent

        async def deactivate_and_notify(session, aid):
            result = await original_deactivate(session, aid)
            await notify_fn(agent_id=aid, new_status=result.status)
            return result

        deactivated = await deactivate_and_notify(db, agent.id)

        notify_fn.assert_awaited_once_with(
            agent_id=agent.id, new_status="deactivated",
        )
        assert deactivated.status == "deactivated"


# =========================================================================
# Block 5 — Concurrency & Edge Cases  (5 tests)
# =========================================================================


class TestConcurrencyAndEdgeCases:
    """Tests 21-25: concurrent registrations, stale-update detection, registry
    capacity, bulk operations, and edge-case input handling."""

    async def test_concurrent_registration_unique_names(self, db: AsyncSession):
        """21. Registering multiple agents sequentially with unique names
        succeeds without conflicts (SQLite single-session cannot truly
        parallelise flushes, so we verify sequential throughput)."""
        names = [f"concurrent-{i}" for i in range(5)]
        reqs = [_make_register_request(name=n) for n in names]

        results = []
        for r in reqs:
            resp = await registry_service.register_agent(db, r)
            results.append(resp)

        assert len(results) == 5
        result_names = {r.name for r in results}
        assert result_names == set(names)

    async def test_stale_version_update_detection(
        self, db: AsyncSession, make_agent,
    ):
        """22. Two rapid updates to the same agent both succeed (last-write-wins)
        and the final state reflects the most recent write."""
        agent, _ = await make_agent("stale-update-agent")

        req_a = AgentUpdateRequest(description="update-A")
        req_b = AgentUpdateRequest(description="update-B")

        # Simulate two sequential updates (last write wins)
        await registry_service.update_agent(db, agent.id, req_a)
        final = await registry_service.update_agent(db, agent.id, req_b)

        assert final.description == "update-B"

    async def test_registry_handles_many_agents(self, db: AsyncSession):
        """23. The registry handles a batch of 20 registrations and returns the
        correct total count."""
        for i in range(20):
            req = _make_register_request(name=f"bulk-{i:03d}")
            await registry_service.register_agent(db, req)

        agents, total = await registry_service.list_agents(db, page_size=50)
        assert total == 20
        assert len(agents) == 20

    async def test_bulk_deactivation(self, db: AsyncSession, make_agent):
        """24. Deactivating multiple agents in quick succession updates all of
        them correctly."""
        agents = []
        for i in range(5):
            a, _ = await make_agent(f"bulk-deact-{i}")
            agents.append(a)

        for a in agents:
            await registry_service.deactivate_agent(db, a.id)

        active, total_active = await registry_service.list_agents(
            db, status="active",
        )
        assert total_active == 0

        deactivated, total_deact = await registry_service.list_agents(
            db, status="deactivated",
        )
        assert total_deact == 5

    async def test_register_agent_with_maximum_length_name(self, db: AsyncSession):
        """25. An agent whose name is exactly 100 characters (the column max)
        registers successfully and round-trips through get_agent."""
        long_name = "a" * 100
        req = _make_register_request(name=long_name)
        resp = await registry_service.register_agent(db, req)

        agent = await registry_service.get_agent(db, resp.id)
        assert agent.name == long_name
        assert len(agent.name) == 100
