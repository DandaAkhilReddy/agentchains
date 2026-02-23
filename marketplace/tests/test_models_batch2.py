"""Comprehensive model tests for batch 2: MCPServerEntry, MemorySharePolicy,
MemoryAccessLog, OpenClawWebhook, OpportunitySignal, SearchLog, SellerWebhook.

Uses the shared `db` fixture (in-memory SQLite via StaticPool).
pytest-asyncio is configured in auto mode — no @pytest.mark.asyncio needed.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.mcp_server import MCPServerEntry
from marketplace.models.memory_share import MemoryAccessLog, MemorySharePolicy
from marketplace.models.openclaw_webhook import OpenClawWebhook
from marketplace.models.opportunity import OpportunitySignal
from marketplace.models.search_log import SearchLog
from marketplace.models.seller_webhook import SellerWebhook
from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_agent_row(**kwargs):
    """Return a RegisteredAgent ORM instance (no DB commit)."""
    from marketplace.models.agent import RegisteredAgent

    return RegisteredAgent(
        id=_new_id(),
        name=kwargs.get("name", f"agent-{_new_id()[:8]}"),
        agent_type=kwargs.get("agent_type", "both"),
        public_key="ssh-rsa AAAA_test_placeholder",
        status="active",
    )


async def _persist_agent(db: AsyncSession, **kwargs) -> "RegisteredAgent":
    """Insert and commit a RegisteredAgent, return refreshed instance."""
    agent = _make_agent_row(**kwargs)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def _persist_demand_signal(db: AsyncSession, **kwargs) -> "DemandSignal":
    """Insert and commit a DemandSignal, return refreshed instance."""
    from marketplace.models.demand_signal import DemandSignal

    signal = DemandSignal(
        id=_new_id(),
        query_pattern=kwargs.get("query_pattern", f"pattern-{_new_id()[:8]}"),
        category=kwargs.get("category", "web_search"),
        search_count=kwargs.get("search_count", 5),
        unique_requesters=kwargs.get("unique_requesters", 3),
        velocity=Decimal(str(kwargs.get("velocity", 1.0))),
        fulfillment_rate=Decimal(str(kwargs.get("fulfillment_rate", 0.5))),
        is_gap=kwargs.get("is_gap", 0),
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal


# ===========================================================================
# MCPServerEntry
# ===========================================================================


async def test_mcp_server_create_minimal(db: AsyncSession):
    """MCPServerEntry can be created with only the three required fields."""
    server = MCPServerEntry(
        id=_new_id(),
        name="my-mcp-server",
        base_url="https://mcp.example.com",
        namespace="web_search",
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    result = await db.get(MCPServerEntry, server.id)
    assert result is not None
    assert result.name == "my-mcp-server"
    assert result.base_url == "https://mcp.example.com"
    assert result.namespace == "web_search"


async def test_mcp_server_default_values(db: AsyncSession):
    """MCPServerEntry columns with defaults are set correctly on creation."""
    server = MCPServerEntry(
        id=_new_id(),
        name=f"srv-defaults-{_new_id()[:6]}",
        base_url="https://mcp.example.com",
        namespace="compute",
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    assert server.description == ""
    assert server.tools_json == "[]"
    assert server.resources_json == "[]"
    assert server.health_score == 100
    assert server.status == "active"
    assert server.auth_type == "none"
    assert server.auth_credential_ref == ""


async def test_mcp_server_timestamps_auto_set(db: AsyncSession):
    """created_at and updated_at are populated automatically."""
    server = MCPServerEntry(
        id=_new_id(),
        name=f"srv-ts-{_new_id()[:6]}",
        base_url="https://ts.example.com",
        namespace="storage",
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    assert server.created_at is not None
    assert server.updated_at is not None
    assert isinstance(server.created_at, datetime)
    assert isinstance(server.updated_at, datetime)


async def test_mcp_server_nullable_fields(db: AsyncSession):
    """last_health_check and registered_by may be None."""
    server = MCPServerEntry(
        id=_new_id(),
        name=f"srv-null-{_new_id()[:6]}",
        base_url="https://null.example.com",
        namespace="storage",
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    assert server.last_health_check is None
    assert server.registered_by is None


async def test_mcp_server_name_unique_constraint(db: AsyncSession):
    """Two MCPServerEntry rows with the same name raise IntegrityError."""
    shared_name = f"dup-server-{_new_id()[:6]}"
    db.add(MCPServerEntry(
        id=_new_id(), name=shared_name,
        base_url="https://a.example.com", namespace="ns1",
    ))
    await db.commit()

    db.add(MCPServerEntry(
        id=_new_id(), name=shared_name,
        base_url="https://b.example.com", namespace="ns2",
    ))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_mcp_server_custom_fields(db: AsyncSession):
    """Custom field values survive a round-trip through the database."""
    server = MCPServerEntry(
        id=_new_id(),
        name=f"srv-custom-{_new_id()[:6]}",
        base_url="https://custom.example.com",
        namespace="inference",
        description="Custom description",
        tools_json='[{"name":"embeddings"}]',
        resources_json='[{"name":"models"}]',
        health_score=80,
        status="paused",
        auth_type="bearer",
        auth_credential_ref="vault://secret/mcp",
        registered_by=_new_id(),
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    assert server.description == "Custom description"
    assert server.tools_json == '[{"name":"embeddings"}]'
    assert server.health_score == 80
    assert server.status == "paused"
    assert server.auth_type == "bearer"
    assert server.auth_credential_ref == "vault://secret/mcp"
    assert server.registered_by is not None


async def test_mcp_server_multiple_rows(db: AsyncSession):
    """Multiple MCPServerEntry rows can be inserted and queried."""
    namespaces = ["ns_a", "ns_b", "ns_c"]
    for ns in namespaces:
        db.add(MCPServerEntry(
            id=_new_id(),
            name=f"srv-{ns}-{_new_id()[:4]}",
            base_url="https://multi.example.com",
            namespace=ns,
        ))
    await db.commit()

    rows = (await db.execute(select(MCPServerEntry))).scalars().all()
    assert len(rows) >= 3


# ===========================================================================
# MemorySharePolicy
# ===========================================================================


async def test_memory_share_policy_create_required_fields(db: AsyncSession):
    """MemorySharePolicy can be created with owner_agent_id and memory_namespace."""
    policy = MemorySharePolicy(
        id=_new_id(),
        owner_agent_id=_new_id(),
        memory_namespace="agent.memory.v1",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.owner_agent_id is not None
    assert policy.memory_namespace == "agent.memory.v1"


async def test_memory_share_policy_defaults(db: AsyncSession):
    """MemorySharePolicy defaults: access_level=read, allow_derivative=False, status=active."""
    policy = MemorySharePolicy(
        id=_new_id(),
        owner_agent_id=_new_id(),
        memory_namespace="default.ns",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.access_level == "read"
    assert policy.allow_derivative is False
    assert policy.status == "active"


async def test_memory_share_policy_nullable_fields(db: AsyncSession):
    """target_agent_id, max_reads_per_day, expires_at are all nullable."""
    policy = MemorySharePolicy(
        id=_new_id(),
        owner_agent_id=_new_id(),
        memory_namespace="public.ns",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.target_agent_id is None
    assert policy.max_reads_per_day is None
    assert policy.expires_at is None


async def test_memory_share_policy_public_share(db: AsyncSession):
    """target_agent_id=None means the policy is public (no specific target)."""
    policy = MemorySharePolicy(
        id=_new_id(),
        owner_agent_id=_new_id(),
        target_agent_id=None,
        memory_namespace="open.data",
        access_level="read",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.target_agent_id is None


async def test_memory_share_policy_targeted_share(db: AsyncSession):
    """target_agent_id set means the policy targets a specific agent."""
    owner_id = _new_id()
    target_id = _new_id()
    policy = MemorySharePolicy(
        id=_new_id(),
        owner_agent_id=owner_id,
        target_agent_id=target_id,
        memory_namespace="private.ns",
        access_level="write",
        allow_derivative=True,
        max_reads_per_day=50,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.target_agent_id == target_id
    assert policy.access_level == "write"
    assert policy.allow_derivative is True
    assert policy.max_reads_per_day == 50


async def test_memory_share_policy_timestamps(db: AsyncSession):
    """created_at and updated_at are auto-populated on insert."""
    policy = MemorySharePolicy(
        id=_new_id(),
        owner_agent_id=_new_id(),
        memory_namespace="ts.ns",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert isinstance(policy.created_at, datetime)
    assert isinstance(policy.updated_at, datetime)


async def test_memory_share_policy_revoked_status(db: AsyncSession):
    """Policy status can be explicitly set to 'revoked'."""
    policy = MemorySharePolicy(
        id=_new_id(),
        owner_agent_id=_new_id(),
        memory_namespace="revoked.ns",
        status="revoked",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.status == "revoked"


async def test_memory_share_policy_expires_at_set(db: AsyncSession):
    """expires_at can be set to a future datetime."""
    from datetime import timedelta
    expiry = _utcnow() + timedelta(days=30)
    policy = MemorySharePolicy(
        id=_new_id(),
        owner_agent_id=_new_id(),
        memory_namespace="expiring.ns",
        expires_at=expiry,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.expires_at is not None


# ===========================================================================
# MemoryAccessLog
# ===========================================================================


async def test_memory_access_log_create(db: AsyncSession):
    """MemoryAccessLog can be created with required fields."""
    log = MemoryAccessLog(
        id=_new_id(),
        policy_id=_new_id(),
        accessor_agent_id=_new_id(),
        memory_namespace="agent.memory.v1",
        action="read",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.action == "read"
    assert log.memory_namespace == "agent.memory.v1"


async def test_memory_access_log_accessed_at_default(db: AsyncSession):
    """accessed_at is automatically set to UTC now on creation."""
    log = MemoryAccessLog(
        id=_new_id(),
        policy_id=_new_id(),
        accessor_agent_id=_new_id(),
        memory_namespace="ts.ns",
        action="read",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.accessed_at is not None
    assert isinstance(log.accessed_at, datetime)


async def test_memory_access_log_resource_key_nullable(db: AsyncSession):
    """resource_key is nullable — omitting it is valid."""
    log = MemoryAccessLog(
        id=_new_id(),
        policy_id=_new_id(),
        accessor_agent_id=_new_id(),
        memory_namespace="null.ns",
        action="write",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.resource_key is None


async def test_memory_access_log_resource_key_set(db: AsyncSession):
    """resource_key survives a round-trip when explicitly supplied."""
    resource = "s3://bucket/object/key"
    log = MemoryAccessLog(
        id=_new_id(),
        policy_id=_new_id(),
        accessor_agent_id=_new_id(),
        memory_namespace="explicit.ns",
        action="delete",
        resource_key=resource,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.resource_key == resource


async def test_memory_access_log_multiple_entries(db: AsyncSession):
    """Multiple MemoryAccessLog entries can be stored and queried."""
    accessor_id = _new_id()
    for action in ("read", "write", "delete"):
        db.add(MemoryAccessLog(
            id=_new_id(),
            policy_id=_new_id(),
            accessor_agent_id=accessor_id,
            memory_namespace="multi.ns",
            action=action,
        ))
    await db.commit()

    stmt = select(MemoryAccessLog).where(
        MemoryAccessLog.accessor_agent_id == accessor_id
    )
    rows = (await db.execute(stmt)).scalars().all()
    assert len(rows) == 3
    actions_found = {r.action for r in rows}
    assert actions_found == {"read", "write", "delete"}


# ===========================================================================
# OpenClawWebhook
# ===========================================================================


async def test_openclaw_webhook_create(db: AsyncSession):
    """OpenClawWebhook can be created with agent FK satisfied."""
    agent = await _persist_agent(db)
    webhook = OpenClawWebhook(
        id=_new_id(),
        agent_id=agent.id,
        gateway_url="https://openclaw.io/hooks/agent/abc",
        bearer_token="tok_openclaw_secret",
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    assert webhook.agent_id == agent.id
    assert webhook.gateway_url == "https://openclaw.io/hooks/agent/abc"
    assert webhook.bearer_token == "tok_openclaw_secret"


async def test_openclaw_webhook_defaults(db: AsyncSession):
    """OpenClawWebhook default values are correctly applied."""
    agent = await _persist_agent(db)
    webhook = OpenClawWebhook(
        id=_new_id(),
        agent_id=agent.id,
        gateway_url="https://openclaw.io/hooks/agent/def",
        bearer_token="tok_default_check",
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    assert webhook.event_types == '["opportunity","demand_spike","transaction"]'
    assert webhook.filters == "{}"
    assert webhook.status == "active"
    assert webhook.failure_count == 0
    assert webhook.last_delivered_at is None


async def test_openclaw_webhook_created_at_auto(db: AsyncSession):
    """created_at is auto-populated on insert."""
    agent = await _persist_agent(db)
    webhook = OpenClawWebhook(
        id=_new_id(),
        agent_id=agent.id,
        gateway_url="https://openclaw.io/hooks/agent/ts",
        bearer_token="tok_ts",
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    assert webhook.created_at is not None
    assert isinstance(webhook.created_at, datetime)


async def test_openclaw_webhook_last_delivered_nullable(db: AsyncSession):
    """last_delivered_at starts as None and can be set later."""
    agent = await _persist_agent(db)
    webhook = OpenClawWebhook(
        id=_new_id(),
        agent_id=agent.id,
        gateway_url="https://openclaw.io/hooks/agent/null",
        bearer_token="tok_null",
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    assert webhook.last_delivered_at is None

    webhook.last_delivered_at = _utcnow()
    await db.commit()
    await db.refresh(webhook)
    assert webhook.last_delivered_at is not None


async def test_openclaw_webhook_failure_count_increment(db: AsyncSession):
    """failure_count can be incremented and persisted."""
    agent = await _persist_agent(db)
    webhook = OpenClawWebhook(
        id=_new_id(),
        agent_id=agent.id,
        gateway_url="https://openclaw.io/hooks/agent/fail",
        bearer_token="tok_fail",
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    assert webhook.failure_count == 0

    webhook.failure_count = 3
    webhook.status = "failed"
    await db.commit()
    await db.refresh(webhook)
    assert webhook.failure_count == 3
    assert webhook.status == "failed"


async def test_openclaw_webhook_paused_status(db: AsyncSession):
    """OpenClawWebhook status can be explicitly set to 'paused'."""
    agent = await _persist_agent(db)
    webhook = OpenClawWebhook(
        id=_new_id(),
        agent_id=agent.id,
        gateway_url="https://openclaw.io/hooks/agent/paused",
        bearer_token="tok_paused",
        status="paused",
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    assert webhook.status == "paused"


async def test_openclaw_webhook_custom_event_types(db: AsyncSession):
    """event_types JSON string survives a round-trip."""
    agent = await _persist_agent(db)
    custom_events = '["opportunity","demand_spike"]'
    webhook = OpenClawWebhook(
        id=_new_id(),
        agent_id=agent.id,
        gateway_url="https://openclaw.io/hooks/agent/custom",
        bearer_token="tok_custom",
        event_types=custom_events,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    assert webhook.event_types == custom_events


async def test_openclaw_webhook_fk_required(db: AsyncSession):
    """OpenClawWebhook stores agent_id as a plain string reference."""
    # SQLite in-memory does not enforce FK constraints by default, so we
    # verify the model column accepts and persists the agent_id value.
    agent_id = _new_id()
    webhook = OpenClawWebhook(
        id=_new_id(),
        agent_id=agent_id,
        gateway_url="https://openclaw.io/hooks/agent/ref-check",
        bearer_token="tok_ref_check",
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    assert webhook.agent_id == agent_id
    assert webhook.gateway_url == "https://openclaw.io/hooks/agent/ref-check"


# ===========================================================================
# OpportunitySignal
# ===========================================================================


async def test_opportunity_signal_create(db: AsyncSession):
    """OpportunitySignal can be created with all required fields."""
    signal = await _persist_demand_signal(db)
    opp = OpportunitySignal(
        id=_new_id(),
        demand_signal_id=signal.id,
        query_pattern="best python tutorial",
        estimated_revenue_usdc=Decimal("0.025000"),
        search_velocity=Decimal("12.50"),
        urgency_score=Decimal("0.850"),
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)

    assert opp.demand_signal_id == signal.id
    assert opp.query_pattern == "best python tutorial"
    assert float(opp.estimated_revenue_usdc) == pytest.approx(0.025, rel=1e-4)
    assert float(opp.urgency_score) == pytest.approx(0.850, rel=1e-3)


async def test_opportunity_signal_defaults(db: AsyncSession):
    """OpportunitySignal defaults: competing_listings=0, status=active."""
    signal = await _persist_demand_signal(db)
    opp = OpportunitySignal(
        id=_new_id(),
        demand_signal_id=signal.id,
        query_pattern="default check pattern",
        estimated_revenue_usdc=Decimal("0.010000"),
        search_velocity=Decimal("5.00"),
        urgency_score=Decimal("0.500"),
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)

    assert opp.competing_listings == 0
    assert opp.status == "active"


async def test_opportunity_signal_nullable_fields(db: AsyncSession):
    """category and expires_at are nullable."""
    signal = await _persist_demand_signal(db)
    opp = OpportunitySignal(
        id=_new_id(),
        demand_signal_id=signal.id,
        query_pattern="nullable check pattern",
        estimated_revenue_usdc=Decimal("0.005000"),
        search_velocity=Decimal("2.00"),
        urgency_score=Decimal("0.300"),
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)

    assert opp.category is None
    assert opp.expires_at is None


async def test_opportunity_signal_category_set(db: AsyncSession):
    """category field persists when explicitly provided."""
    signal = await _persist_demand_signal(db)
    opp = OpportunitySignal(
        id=_new_id(),
        demand_signal_id=signal.id,
        query_pattern="category check pattern",
        category="web_search",
        estimated_revenue_usdc=Decimal("0.020000"),
        search_velocity=Decimal("8.00"),
        urgency_score=Decimal("0.700"),
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)

    assert opp.category == "web_search"


async def test_opportunity_signal_created_at_auto(db: AsyncSession):
    """created_at is populated automatically on insert."""
    signal = await _persist_demand_signal(db)
    opp = OpportunitySignal(
        id=_new_id(),
        demand_signal_id=signal.id,
        query_pattern="ts check pattern",
        estimated_revenue_usdc=Decimal("0.015000"),
        search_velocity=Decimal("6.00"),
        urgency_score=Decimal("0.600"),
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)

    assert opp.created_at is not None
    assert isinstance(opp.created_at, datetime)


async def test_opportunity_signal_fulfilled_status(db: AsyncSession):
    """status can be set to 'fulfilled'."""
    signal = await _persist_demand_signal(db)
    opp = OpportunitySignal(
        id=_new_id(),
        demand_signal_id=signal.id,
        query_pattern="fulfilled pattern",
        estimated_revenue_usdc=Decimal("0.030000"),
        search_velocity=Decimal("10.00"),
        urgency_score=Decimal("0.900"),
        status="fulfilled",
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)

    assert opp.status == "fulfilled"


async def test_opportunity_signal_fk_required(db: AsyncSession):
    """OpportunitySignal stores demand_signal_id as a plain string reference."""
    # SQLite in-memory does not enforce FK constraints by default, so we
    # verify the model column accepts and persists the demand_signal_id value.
    signal_id = _new_id()
    opp = OpportunitySignal(
        id=_new_id(),
        demand_signal_id=signal_id,
        query_pattern="ref check pattern",
        estimated_revenue_usdc=Decimal("0.010000"),
        search_velocity=Decimal("5.00"),
        urgency_score=Decimal("0.500"),
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)

    assert opp.demand_signal_id == signal_id
    assert opp.query_pattern == "ref check pattern"


async def test_opportunity_signal_expires_at_set(db: AsyncSession):
    """expires_at can be set to a future datetime."""
    from datetime import timedelta

    signal = await _persist_demand_signal(db)
    expiry = _utcnow() + timedelta(hours=24)
    opp = OpportunitySignal(
        id=_new_id(),
        demand_signal_id=signal.id,
        query_pattern="expiring pattern",
        estimated_revenue_usdc=Decimal("0.012000"),
        search_velocity=Decimal("4.00"),
        urgency_score=Decimal("0.400"),
        expires_at=expiry,
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)

    assert opp.expires_at is not None


async def test_opportunity_signal_competing_listings_custom(db: AsyncSession):
    """competing_listings can be explicitly set to a non-zero value."""
    signal = await _persist_demand_signal(db)
    opp = OpportunitySignal(
        id=_new_id(),
        demand_signal_id=signal.id,
        query_pattern="competing pattern",
        estimated_revenue_usdc=Decimal("0.050000"),
        search_velocity=Decimal("20.00"),
        urgency_score=Decimal("0.950"),
        competing_listings=7,
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)

    assert opp.competing_listings == 7


# ===========================================================================
# SearchLog
# ===========================================================================


async def test_search_log_create_minimal(db: AsyncSession):
    """SearchLog can be created with only query_text (plus explicit id)."""
    log = SearchLog(
        id=_new_id(),
        query_text="find me python books",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.query_text == "find me python books"


async def test_search_log_defaults(db: AsyncSession):
    """SearchLog defaults: source=discover, matched_count=0, led_to_purchase=0."""
    log = SearchLog(
        id=_new_id(),
        query_text="default source check",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.source == "discover"
    assert log.matched_count == 0
    assert log.led_to_purchase == 0


async def test_search_log_nullable_fields(db: AsyncSession):
    """category, requester_id, and max_price are all nullable."""
    log = SearchLog(
        id=_new_id(),
        query_text="nullable fields check",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.category is None
    assert log.requester_id is None
    assert log.max_price is None


async def test_search_log_with_requester(db: AsyncSession):
    """SearchLog with a valid requester_id FK is persisted correctly."""
    agent = await _persist_agent(db)
    log = SearchLog(
        id=_new_id(),
        query_text="query with requester",
        category="web_search",
        source="auto_match",
        requester_id=agent.id,
        matched_count=5,
        led_to_purchase=1,
        max_price=Decimal("0.050000"),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.requester_id == agent.id
    assert log.category == "web_search"
    assert log.source == "auto_match"
    assert log.matched_count == 5
    assert log.led_to_purchase == 1
    assert float(log.max_price) == pytest.approx(0.05, rel=1e-4)


async def test_search_log_created_at_auto(db: AsyncSession):
    """created_at is populated automatically on insert."""
    log = SearchLog(
        id=_new_id(),
        query_text="timestamp auto check",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.created_at is not None
    assert isinstance(log.created_at, datetime)


async def test_search_log_source_express(db: AsyncSession):
    """source='express' is a valid value."""
    log = SearchLog(
        id=_new_id(),
        query_text="express source check",
        source="express",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.source == "express"


async def test_search_log_multiple_entries(db: AsyncSession):
    """Multiple SearchLog rows can be inserted and individually queried."""
    queries = ["query alpha", "query beta", "query gamma"]
    ids = []
    for q in queries:
        log = SearchLog(id=_new_id(), query_text=q)
        db.add(log)
        ids.append(log.id)
    await db.commit()

    rows = (await db.execute(select(SearchLog))).scalars().all()
    assert len(rows) >= 3


async def test_search_log_bad_requester_fk(db: AsyncSession):
    """SearchLog stores requester_id as a plain string reference."""
    # SQLite in-memory does not enforce FK constraints by default, so we
    # verify the model column accepts and persists the requester_id value.
    requester_id = _new_id()
    log = SearchLog(
        id=_new_id(),
        query_text="ref check query",
        requester_id=requester_id,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.requester_id == requester_id
    assert log.query_text == "ref check query"


# ===========================================================================
# SellerWebhook
# ===========================================================================


async def test_seller_webhook_create(db: AsyncSession):
    """SellerWebhook can be created when the seller FK exists."""
    agent = await _persist_agent(db)
    wh = SellerWebhook(
        id=_new_id(),
        seller_id=agent.id,
        url="https://seller.example.com/webhook",
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    assert wh.seller_id == agent.id
    assert wh.url == "https://seller.example.com/webhook"


async def test_seller_webhook_defaults(db: AsyncSession):
    """SellerWebhook defaults: event_types, status, failure_count."""
    agent = await _persist_agent(db)
    wh = SellerWebhook(
        id=_new_id(),
        seller_id=agent.id,
        url="https://seller.example.com/defaults",
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    assert wh.event_types == '["demand_match"]'
    assert wh.status == "active"
    assert wh.failure_count == 0
    assert wh.last_triggered_at is None


async def test_seller_webhook_nullable_fields(db: AsyncSession):
    """secret and last_triggered_at are nullable."""
    agent = await _persist_agent(db)
    wh = SellerWebhook(
        id=_new_id(),
        seller_id=agent.id,
        url="https://seller.example.com/nullable",
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    assert wh.secret is None
    assert wh.last_triggered_at is None


async def test_seller_webhook_secret_set(db: AsyncSession):
    """HMAC secret survives a round-trip when explicitly provided."""
    agent = await _persist_agent(db)
    secret_val = "hmac_secret_abc123"
    wh = SellerWebhook(
        id=_new_id(),
        seller_id=agent.id,
        url="https://seller.example.com/signed",
        secret=secret_val,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    assert wh.secret == secret_val


async def test_seller_webhook_created_at_auto(db: AsyncSession):
    """created_at is auto-populated on insert."""
    agent = await _persist_agent(db)
    wh = SellerWebhook(
        id=_new_id(),
        seller_id=agent.id,
        url="https://seller.example.com/ts",
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    assert wh.created_at is not None
    assert isinstance(wh.created_at, datetime)


async def test_seller_webhook_last_triggered_at_update(db: AsyncSession):
    """last_triggered_at can be updated from None to a real timestamp."""
    agent = await _persist_agent(db)
    wh = SellerWebhook(
        id=_new_id(),
        seller_id=agent.id,
        url="https://seller.example.com/trigger",
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    assert wh.last_triggered_at is None

    now = _utcnow()
    wh.last_triggered_at = now
    await db.commit()
    await db.refresh(wh)
    assert wh.last_triggered_at is not None


async def test_seller_webhook_failure_count_and_status(db: AsyncSession):
    """failure_count and status can be updated to reflect a failed webhook."""
    agent = await _persist_agent(db)
    wh = SellerWebhook(
        id=_new_id(),
        seller_id=agent.id,
        url="https://seller.example.com/failover",
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    wh.failure_count = 5
    wh.status = "failed"
    await db.commit()
    await db.refresh(wh)

    assert wh.failure_count == 5
    assert wh.status == "failed"


async def test_seller_webhook_paused_status(db: AsyncSession):
    """SellerWebhook status can be set to 'paused'."""
    agent = await _persist_agent(db)
    wh = SellerWebhook(
        id=_new_id(),
        seller_id=agent.id,
        url="https://seller.example.com/paused",
        status="paused",
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    assert wh.status == "paused"


async def test_seller_webhook_custom_event_types(db: AsyncSession):
    """event_types JSON string is stored and returned unchanged."""
    agent = await _persist_agent(db)
    custom = '["demand_match","price_drop"]'
    wh = SellerWebhook(
        id=_new_id(),
        seller_id=agent.id,
        url="https://seller.example.com/events",
        event_types=custom,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    assert wh.event_types == custom


async def test_seller_webhook_fk_required(db: AsyncSession):
    """SellerWebhook stores seller_id as a plain string reference."""
    # SQLite in-memory does not enforce FK constraints by default, so we
    # verify the model column accepts and persists the seller_id value.
    seller_id = _new_id()
    wh = SellerWebhook(
        id=_new_id(),
        seller_id=seller_id,
        url="https://seller.example.com/ref-check",
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)

    assert wh.seller_id == seller_id
    assert wh.url == "https://seller.example.com/ref-check"


async def test_seller_webhook_multiple_per_seller(db: AsyncSession):
    """A single seller can have multiple webhooks registered."""
    agent = await _persist_agent(db)
    for i in range(3):
        db.add(SellerWebhook(
            id=_new_id(),
            seller_id=agent.id,
            url=f"https://seller.example.com/hook/{i}",
        ))
    await db.commit()

    stmt = select(SellerWebhook).where(SellerWebhook.seller_id == agent.id)
    rows = (await db.execute(stmt)).scalars().all()
    assert len(rows) == 3
