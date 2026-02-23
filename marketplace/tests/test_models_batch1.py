"""Comprehensive unit tests for SQLAlchemy model defaults, constraints, and nullable fields.

Models covered:
  - ActionExecution    (marketplace/models/action_execution.py)
  - ActionListing      (marketplace/models/action_listing.py)
  - AgentStats         (marketplace/models/agent_stats.py)
  - AuditLog           (marketplace/models/audit_log.py)
  - ChainPolicy        (marketplace/models/chain_policy.py)
  - ChainTemplate      (marketplace/models/chain_template.py)
  - ChainExecution     (marketplace/models/chain_template.py)
  - DemandSignal       (marketplace/models/demand_signal.py)
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.action_execution import ActionExecution
from marketplace.models.action_listing import ActionListing
from marketplace.models.agent_stats import AgentStats
from marketplace.models.audit_log import AuditLog
from marketplace.models.chain_policy import ChainPolicy
from marketplace.models.chain_template import ChainExecution, ChainTemplate
from marketplace.models.demand_signal import DemandSignal

# Related models needed for FK-constrained rows
from marketplace.models.agent import RegisteredAgent
from marketplace.models.creator import Creator
from marketplace.models.webmcp_tool import WebMCPTool
from marketplace.models.workflow import WorkflowDefinition, WorkflowExecution

from marketplace.tests.conftest import _new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_creator() -> Creator:
    return Creator(
        id=_new_id(),
        email=f"creator-{_new_id()[:8]}@test.com",
        password_hash="hashed_placeholder",
        display_name="Test Creator",
    )


def _make_agent() -> RegisteredAgent:
    return RegisteredAgent(
        id=_new_id(),
        name=f"agent-{_new_id()[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test_key_placeholder",
    )


def _make_tool(creator_id: str) -> WebMCPTool:
    return WebMCPTool(
        id=_new_id(),
        name=f"tool-{_new_id()[:8]}",
        domain="example.com",
        endpoint_url="https://example.com/mcp",
        creator_id=creator_id,
        category="research",
    )


def _make_action_listing(tool_id: str, seller_id: str) -> ActionListing:
    return ActionListing(
        id=_new_id(),
        tool_id=tool_id,
        seller_id=seller_id,
        title="Test Action Listing",
        price_per_execution=Decimal("0.50"),
    )


# ===========================================================================
# AuditLog Tests
# ===========================================================================


async def test_audit_log_creation_required_fields(db: AsyncSession):
    """AuditLog persists when only required fields are provided."""
    log = AuditLog(
        id=_new_id(),
        event_type="agent.registered",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.id is not None
    assert log.event_type == "agent.registered"


async def test_audit_log_severity_default_info(db: AsyncSession):
    """severity column must default to 'info'."""
    log = AuditLog(
        id=_new_id(),
        event_type="listing.created",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.severity == "info"


async def test_audit_log_details_default_empty_json(db: AsyncSession):
    """details column must default to '{}'."""
    log = AuditLog(
        id=_new_id(),
        event_type="transaction.initiated",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.details == "{}"


async def test_audit_log_user_agent_default_empty_string(db: AsyncSession):
    """user_agent column must default to ''."""
    log = AuditLog(
        id=_new_id(),
        event_type="auth.login",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.user_agent == ""


async def test_audit_log_nullable_fields_accept_none(db: AsyncSession):
    """agent_id, creator_id, ip_address, prev_hash, and entry_hash are nullable."""
    log = AuditLog(
        id=_new_id(),
        event_type="system.startup",
        agent_id=None,
        creator_id=None,
        ip_address=None,
        prev_hash=None,
        entry_hash=None,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.agent_id is None
    assert log.creator_id is None
    assert log.ip_address is None
    assert log.prev_hash is None
    assert log.entry_hash is None


async def test_audit_log_created_at_populated(db: AsyncSession):
    """created_at must be populated automatically on insert."""
    log = AuditLog(
        id=_new_id(),
        event_type="test.event",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.created_at is not None


async def test_audit_log_explicit_severity(db: AsyncSession):
    """Explicit severity values ('warn', 'critical') are stored correctly."""
    for severity in ("warn", "critical", "info"):
        log = AuditLog(
            id=_new_id(),
            event_type=f"security.event.{severity}",
            severity=severity,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        assert log.severity == severity


async def test_audit_log_hash_chain_fields(db: AsyncSession):
    """prev_hash and entry_hash can hold 64-char hex strings."""
    prev_hash = "a" * 64
    entry_hash = "b" * 64
    log = AuditLog(
        id=_new_id(),
        event_type="hash.chain.test",
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    assert log.prev_hash == prev_hash
    assert log.entry_hash == entry_hash


# ===========================================================================
# DemandSignal Tests
# ===========================================================================


async def test_demand_signal_creation_required_fields(db: AsyncSession):
    """DemandSignal persists when only required fields are provided."""
    signal = DemandSignal(
        id=_new_id(),
        query_pattern="python tutorial",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    assert signal.id is not None
    assert signal.query_pattern == "python tutorial"


async def test_demand_signal_search_count_default_one(db: AsyncSession):
    """search_count must default to 1."""
    signal = DemandSignal(
        id=_new_id(),
        query_pattern=f"query-{_new_id()[:8]}",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    assert signal.search_count == 1


async def test_demand_signal_unique_requesters_default_one(db: AsyncSession):
    """unique_requesters must default to 1."""
    signal = DemandSignal(
        id=_new_id(),
        query_pattern=f"query-{_new_id()[:8]}",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    assert signal.unique_requesters == 1


async def test_demand_signal_is_gap_default_zero(db: AsyncSession):
    """is_gap must default to 0."""
    signal = DemandSignal(
        id=_new_id(),
        query_pattern=f"query-{_new_id()[:8]}",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    assert signal.is_gap == 0


async def test_demand_signal_velocity_default_zero(db: AsyncSession):
    """velocity must default to 0.0."""
    signal = DemandSignal(
        id=_new_id(),
        query_pattern=f"query-{_new_id()[:8]}",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    assert float(signal.velocity) == 0.0


async def test_demand_signal_fulfillment_rate_default_zero(db: AsyncSession):
    """fulfillment_rate must default to 0.0."""
    signal = DemandSignal(
        id=_new_id(),
        query_pattern=f"query-{_new_id()[:8]}",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    assert float(signal.fulfillment_rate) == 0.0


async def test_demand_signal_conversion_rate_default_zero(db: AsyncSession):
    """conversion_rate must default to 0.0."""
    signal = DemandSignal(
        id=_new_id(),
        query_pattern=f"query-{_new_id()[:8]}",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    assert float(signal.conversion_rate) == 0.0


async def test_demand_signal_nullable_fields(db: AsyncSession):
    """category and avg_max_price are nullable."""
    signal = DemandSignal(
        id=_new_id(),
        query_pattern=f"query-{_new_id()[:8]}",
        category=None,
        avg_max_price=None,
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    assert signal.category is None
    assert signal.avg_max_price is None


async def test_demand_signal_query_pattern_unique(db: AsyncSession):
    """Two DemandSignals with the same query_pattern trigger an IntegrityError."""
    pattern = f"duplicate-pattern-{_new_id()[:8]}"
    db.add(DemandSignal(id=_new_id(), query_pattern=pattern))
    await db.commit()

    db.add(DemandSignal(id=_new_id(), query_pattern=pattern))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_demand_signal_explicit_values(db: AsyncSession):
    """All numeric fields persist explicit values correctly."""
    signal = DemandSignal(
        id=_new_id(),
        query_pattern=f"explicit-{_new_id()[:8]}",
        category="web_search",
        search_count=42,
        unique_requesters=10,
        avg_max_price=Decimal("2.500000"),
        fulfillment_rate=Decimal("0.750"),
        conversion_rate=Decimal("0.250"),
        velocity=Decimal("5.50"),
        is_gap=1,
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    assert signal.category == "web_search"
    assert signal.search_count == 42
    assert signal.unique_requesters == 10
    assert float(signal.avg_max_price) == pytest.approx(2.5)
    assert float(signal.fulfillment_rate) == pytest.approx(0.75)
    assert float(signal.conversion_rate) == pytest.approx(0.25)
    assert float(signal.velocity) == pytest.approx(5.5)
    assert signal.is_gap == 1


async def test_demand_signal_timestamps_auto_populated(db: AsyncSession):
    """first_searched_at, last_searched_at, and updated_at are set on insert."""
    signal = DemandSignal(
        id=_new_id(),
        query_pattern=f"ts-test-{_new_id()[:8]}",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    assert signal.first_searched_at is not None
    assert signal.last_searched_at is not None
    assert signal.updated_at is not None


# ===========================================================================
# AgentStats Tests
# ===========================================================================


async def test_agent_stats_creation_required_fields(db: AsyncSession):
    """AgentStats persists with only agent_id provided."""
    agent_id = _new_id()
    stats = AgentStats(
        id=_new_id(),
        agent_id=agent_id,
    )
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert stats.id is not None
    assert stats.agent_id == agent_id


async def test_agent_stats_helpfulness_metrics_default_zero(db: AsyncSession):
    """Helpfulness metric counters default to 0."""
    stats = AgentStats(id=_new_id(), agent_id=_new_id())
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert stats.unique_buyers_served == 0
    assert stats.total_listings_created == 0
    assert stats.total_cache_hits == 0
    assert stats.category_count == 0


async def test_agent_stats_financial_metrics_default_zero(db: AsyncSession):
    """Financial metric columns default to 0.0."""
    stats = AgentStats(id=_new_id(), agent_id=_new_id())
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert float(stats.total_earned_usdc) == 0.0
    assert float(stats.total_spent_usdc) == 0.0


async def test_agent_stats_contribution_metrics_default_zero(db: AsyncSession):
    """Contribution metric columns default to 0."""
    stats = AgentStats(id=_new_id(), agent_id=_new_id())
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert stats.demand_gaps_filled == 0
    assert stats.total_data_bytes_contributed == 0


async def test_agent_stats_helpfulness_score_default(db: AsyncSession):
    """helpfulness_score defaults to 0.500."""
    stats = AgentStats(id=_new_id(), agent_id=_new_id())
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert float(stats.helpfulness_score) == pytest.approx(0.5, abs=1e-3)


async def test_agent_stats_avg_listing_quality_default(db: AsyncSession):
    """avg_listing_quality defaults to 0.5."""
    stats = AgentStats(id=_new_id(), agent_id=_new_id())
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert float(stats.avg_listing_quality) == pytest.approx(0.5, abs=1e-2)


async def test_agent_stats_categories_json_default(db: AsyncSession):
    """categories_json defaults to '[]'."""
    stats = AgentStats(id=_new_id(), agent_id=_new_id())
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert stats.categories_json == "[]"


async def test_agent_stats_earnings_by_category_default(db: AsyncSession):
    """earnings_by_category_json defaults to '{}'."""
    stats = AgentStats(id=_new_id(), agent_id=_new_id())
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert stats.earnings_by_category_json == "{}"


async def test_agent_stats_specialization_tags_json_default(db: AsyncSession):
    """specialization_tags_json defaults to '[]'."""
    stats = AgentStats(id=_new_id(), agent_id=_new_id())
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert stats.specialization_tags_json == "[]"


async def test_agent_stats_nullable_rank_fields(db: AsyncSession):
    """helpfulness_rank, earnings_rank, and primary_specialization are nullable."""
    stats = AgentStats(
        id=_new_id(),
        agent_id=_new_id(),
        helpfulness_rank=None,
        earnings_rank=None,
        primary_specialization=None,
    )
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert stats.helpfulness_rank is None
    assert stats.earnings_rank is None
    assert stats.primary_specialization is None


async def test_agent_stats_agent_id_unique(db: AsyncSession):
    """Two AgentStats rows for the same agent_id trigger an IntegrityError."""
    agent_id = _new_id()
    db.add(AgentStats(id=_new_id(), agent_id=agent_id))
    await db.commit()

    db.add(AgentStats(id=_new_id(), agent_id=agent_id))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_agent_stats_explicit_values(db: AsyncSession):
    """All explicitly set values are stored and retrieved correctly."""
    stats = AgentStats(
        id=_new_id(),
        agent_id=_new_id(),
        unique_buyers_served=5,
        total_listings_created=10,
        total_earned_usdc=Decimal("100.500000"),
        helpfulness_score=Decimal("0.875"),
        helpfulness_rank=3,
        earnings_rank=7,
        primary_specialization="data_extraction",
    )
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert stats.unique_buyers_served == 5
    assert stats.total_listings_created == 10
    assert float(stats.total_earned_usdc) == pytest.approx(100.5)
    assert float(stats.helpfulness_score) == pytest.approx(0.875, abs=1e-3)
    assert stats.helpfulness_rank == 3
    assert stats.earnings_rank == 7
    assert stats.primary_specialization == "data_extraction"


async def test_agent_stats_last_calculated_at_populated(db: AsyncSession):
    """last_calculated_at must be populated automatically on insert."""
    stats = AgentStats(id=_new_id(), agent_id=_new_id())
    db.add(stats)
    await db.commit()
    await db.refresh(stats)

    assert stats.last_calculated_at is not None


# ===========================================================================
# ChainPolicy Tests
# ===========================================================================


async def test_chain_policy_creation_required_fields(db: AsyncSession):
    """ChainPolicy persists when name, policy_type, and rules_json are provided."""
    policy = ChainPolicy(
        id=_new_id(),
        name="No PII Policy",
        policy_type="jurisdiction",
        rules_json='{"allow": ["US", "EU"]}',
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.id is not None
    assert policy.name == "No PII Policy"
    assert policy.policy_type == "jurisdiction"


async def test_chain_policy_description_default_empty_string(db: AsyncSession):
    """description defaults to empty string."""
    policy = ChainPolicy(
        id=_new_id(),
        name="Cost Limit Policy",
        policy_type="cost_limit",
        rules_json='{"max_usd": 5.0}',
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.description == ""


async def test_chain_policy_enforcement_default_block(db: AsyncSession):
    """enforcement defaults to 'block'."""
    policy = ChainPolicy(
        id=_new_id(),
        name="Block Policy",
        policy_type="data_residency",
        rules_json="{}",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.enforcement == "block"


async def test_chain_policy_scope_default_chain(db: AsyncSession):
    """scope defaults to 'chain'."""
    policy = ChainPolicy(
        id=_new_id(),
        name="Scoped Policy",
        policy_type="jurisdiction",
        rules_json="{}",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.scope == "chain"


async def test_chain_policy_status_default_active(db: AsyncSession):
    """status defaults to 'active'."""
    policy = ChainPolicy(
        id=_new_id(),
        name="Active Policy",
        policy_type="cost_limit",
        rules_json="{}",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.status == "active"


async def test_chain_policy_owner_id_nullable(db: AsyncSession):
    """owner_id can be None (global policy with no specific owner)."""
    policy = ChainPolicy(
        id=_new_id(),
        name="Global Policy",
        policy_type="jurisdiction",
        rules_json="{}",
        owner_id=None,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.owner_id is None


async def test_chain_policy_timestamps_auto_populated(db: AsyncSession):
    """created_at and updated_at are set on insert."""
    policy = ChainPolicy(
        id=_new_id(),
        name="Timestamped Policy",
        policy_type="jurisdiction",
        rules_json="{}",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.created_at is not None
    assert policy.updated_at is not None


async def test_chain_policy_explicit_enforcement_warn(db: AsyncSession):
    """Explicit enforcement='warn' is stored correctly."""
    policy = ChainPolicy(
        id=_new_id(),
        name="Warn Policy",
        policy_type="data_residency",
        rules_json='{"regions": ["EU"]}',
        enforcement="warn",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.enforcement == "warn"


async def test_chain_policy_explicit_scope_global(db: AsyncSession):
    """Explicit scope='global' is stored correctly."""
    policy = ChainPolicy(
        id=_new_id(),
        name="Global Scope Policy",
        policy_type="cost_limit",
        rules_json='{"max": 1000}',
        scope="global",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.scope == "global"


async def test_chain_policy_disabled_status(db: AsyncSession):
    """Explicit status='disabled' is stored correctly."""
    policy = ChainPolicy(
        id=_new_id(),
        name="Disabled Policy",
        policy_type="jurisdiction",
        rules_json="{}",
        status="disabled",
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    assert policy.status == "disabled"


async def test_chain_policy_query_by_type(db: AsyncSession):
    """ChainPolicy can be queried by policy_type."""
    policy = ChainPolicy(
        id=_new_id(),
        name="Query Test Policy",
        policy_type="cost_limit",
        rules_json="{}",
    )
    db.add(policy)
    await db.commit()

    result = await db.execute(
        select(ChainPolicy).where(ChainPolicy.policy_type == "cost_limit")
    )
    found = result.scalars().first()
    assert found is not None
    assert found.name == "Query Test Policy"


# ===========================================================================
# ChainTemplate Tests
# ===========================================================================


async def test_chain_template_creation_required_fields(db: AsyncSession):
    """ChainTemplate persists when name and graph_json are provided."""
    template = ChainTemplate(
        id=_new_id(),
        name="Research Pipeline",
        graph_json='{"nodes": [], "edges": []}',
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.id is not None
    assert template.name == "Research Pipeline"


async def test_chain_template_description_default_empty(db: AsyncSession):
    """description defaults to empty string."""
    template = ChainTemplate(
        id=_new_id(),
        name="Template A",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.description == ""


async def test_chain_template_category_default_general(db: AsyncSession):
    """category defaults to 'general'."""
    template = ChainTemplate(
        id=_new_id(),
        name="Template B",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.category == "general"


async def test_chain_template_version_default_one(db: AsyncSession):
    """version defaults to 1."""
    template = ChainTemplate(
        id=_new_id(),
        name="Template C",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.version == 1


async def test_chain_template_status_default_draft(db: AsyncSession):
    """status defaults to 'draft'."""
    template = ChainTemplate(
        id=_new_id(),
        name="Template D",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.status == "draft"


async def test_chain_template_execution_count_default_zero(db: AsyncSession):
    """execution_count defaults to 0."""
    template = ChainTemplate(
        id=_new_id(),
        name="Template E",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.execution_count == 0


async def test_chain_template_avg_cost_default_zero(db: AsyncSession):
    """avg_cost_usd defaults to 0."""
    template = ChainTemplate(
        id=_new_id(),
        name="Template F",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert float(template.avg_cost_usd) == 0.0


async def test_chain_template_avg_duration_default_zero(db: AsyncSession):
    """avg_duration_ms defaults to 0."""
    template = ChainTemplate(
        id=_new_id(),
        name="Template G",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.avg_duration_ms == 0


async def test_chain_template_trust_score_default_zero(db: AsyncSession):
    """trust_score defaults to 0."""
    template = ChainTemplate(
        id=_new_id(),
        name="Template H",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.trust_score == 0


async def test_chain_template_tags_json_default(db: AsyncSession):
    """tags_json defaults to '[]'."""
    template = ChainTemplate(
        id=_new_id(),
        name="Template I",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.tags_json == "[]"


async def test_chain_template_required_capabilities_default(db: AsyncSession):
    """required_capabilities_json defaults to '[]'."""
    template = ChainTemplate(
        id=_new_id(),
        name="Template J",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.required_capabilities_json == "[]"


async def test_chain_template_nullable_fields(db: AsyncSession):
    """workflow_id, author_id, forked_from_id, and max_budget_usd are nullable."""
    template = ChainTemplate(
        id=_new_id(),
        name="Nullable Template",
        graph_json="{}",
        workflow_id=None,
        author_id=None,
        forked_from_id=None,
        max_budget_usd=None,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.workflow_id is None
    assert template.author_id is None
    assert template.forked_from_id is None
    assert template.max_budget_usd is None


async def test_chain_template_forked_from_self_ref(db: AsyncSession):
    """forked_from_id can reference another ChainTemplate (self-referential FK)."""
    original = ChainTemplate(
        id=_new_id(),
        name="Original Template",
        graph_json='{"nodes": ["a"]}',
    )
    db.add(original)
    await db.commit()
    await db.refresh(original)

    fork = ChainTemplate(
        id=_new_id(),
        name="Forked Template",
        graph_json='{"nodes": ["a", "b"]}',
        forked_from_id=original.id,
    )
    db.add(fork)
    await db.commit()
    await db.refresh(fork)

    assert fork.forked_from_id == original.id


async def test_chain_template_timestamps_auto_populated(db: AsyncSession):
    """created_at and updated_at are set on insert."""
    template = ChainTemplate(
        id=_new_id(),
        name="Timestamps Template",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.created_at is not None
    assert template.updated_at is not None


async def test_chain_template_explicit_active_status(db: AsyncSession):
    """Explicit status='active' is stored correctly."""
    template = ChainTemplate(
        id=_new_id(),
        name="Active Template",
        graph_json="{}",
        status="active",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    assert template.status == "active"


# ===========================================================================
# ChainExecution Tests
# ===========================================================================


async def test_chain_execution_creation_required_fields(db: AsyncSession):
    """ChainExecution persists with chain_template_id and initiated_by."""
    template = ChainTemplate(
        id=_new_id(),
        name="Exec Template",
        graph_json="{}",
    )
    db.add(template)
    await db.commit()

    execution = ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        initiated_by=_new_id(),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.id is not None
    assert execution.chain_template_id == template.id


async def test_chain_execution_status_default_pending(db: AsyncSession):
    """status defaults to 'pending'."""
    template = ChainTemplate(id=_new_id(), name="Status Exec Template", graph_json="{}")
    db.add(template)
    await db.commit()

    execution = ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        initiated_by=_new_id(),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.status == "pending"


async def test_chain_execution_input_output_default_empty_json(db: AsyncSession):
    """input_json and output_json default to '{}'."""
    template = ChainTemplate(id=_new_id(), name="IO Exec Template", graph_json="{}")
    db.add(template)
    await db.commit()

    execution = ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        initiated_by=_new_id(),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.input_json == "{}"
    assert execution.output_json == "{}"


async def test_chain_execution_total_cost_default_zero(db: AsyncSession):
    """total_cost_usd defaults to 0."""
    template = ChainTemplate(id=_new_id(), name="Cost Exec Template", graph_json="{}")
    db.add(template)
    await db.commit()

    execution = ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        initiated_by=_new_id(),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert float(execution.total_cost_usd) == 0.0


async def test_chain_execution_participant_agents_default(db: AsyncSession):
    """participant_agents_json defaults to '[]'."""
    template = ChainTemplate(id=_new_id(), name="Agents Exec Template", graph_json="{}")
    db.add(template)
    await db.commit()

    execution = ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        initiated_by=_new_id(),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.participant_agents_json == "[]"


async def test_chain_execution_nullable_fields(db: AsyncSession):
    """workflow_execution_id, provenance_hash, idempotency_key, completed_at are nullable."""
    template = ChainTemplate(id=_new_id(), name="Nullable Exec Template", graph_json="{}")
    db.add(template)
    await db.commit()

    execution = ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        initiated_by=_new_id(),
        workflow_execution_id=None,
        provenance_hash=None,
        idempotency_key=None,
        completed_at=None,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.workflow_execution_id is None
    assert execution.provenance_hash is None
    assert execution.idempotency_key is None
    assert execution.completed_at is None


async def test_chain_execution_idempotency_key_unique(db: AsyncSession):
    """Two ChainExecutions with the same idempotency_key trigger an IntegrityError."""
    template = ChainTemplate(id=_new_id(), name="Idem Template", graph_json="{}")
    db.add(template)
    await db.commit()

    idem_key = f"idem-{_new_id()[:16]}"
    db.add(ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        initiated_by=_new_id(),
        idempotency_key=idem_key,
    ))
    await db.commit()

    db.add(ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        initiated_by=_new_id(),
        idempotency_key=idem_key,
    ))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


async def test_chain_execution_created_at_auto_populated(db: AsyncSession):
    """created_at is set on insert."""
    template = ChainTemplate(id=_new_id(), name="TS Exec Template", graph_json="{}")
    db.add(template)
    await db.commit()

    execution = ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        initiated_by=_new_id(),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.created_at is not None


# ===========================================================================
# ActionListing Tests
# ===========================================================================


async def test_action_listing_creation_required_fields(db: AsyncSession):
    """ActionListing persists with tool_id, seller_id, title, and price_per_execution."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = ActionListing(
        id=_new_id(),
        tool_id=tool.id,
        seller_id=agent.id,
        title="Search the Web",
        price_per_execution=Decimal("0.100000"),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.id is not None
    assert listing.title == "Search the Web"
    assert float(listing.price_per_execution) == pytest.approx(0.1)


async def test_action_listing_currency_default_usd(db: AsyncSession):
    """currency defaults to 'USD'."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.currency == "USD"


async def test_action_listing_status_default_active(db: AsyncSession):
    """status defaults to 'active'."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.status == "active"


async def test_action_listing_access_count_default_zero(db: AsyncSession):
    """access_count defaults to 0."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.access_count == 0


async def test_action_listing_max_executions_per_hour_default(db: AsyncSession):
    """max_executions_per_hour defaults to 60."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.max_executions_per_hour == 60


async def test_action_listing_requires_consent_default_true(db: AsyncSession):
    """requires_consent defaults to True."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.requires_consent is True


async def test_action_listing_description_default_empty(db: AsyncSession):
    """description defaults to ''."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.description == ""


async def test_action_listing_default_parameters_empty_json(db: AsyncSession):
    """default_parameters defaults to '{}'."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.default_parameters == "{}"


async def test_action_listing_domain_lock_default_empty_array(db: AsyncSession):
    """domain_lock defaults to '[]'."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.domain_lock == "[]"


async def test_action_listing_tags_default_empty_array(db: AsyncSession):
    """tags defaults to '[]'."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.tags == "[]"


async def test_action_listing_timestamps_auto_populated(db: AsyncSession):
    """created_at and updated_at are set on insert."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.created_at is not None
    assert listing.updated_at is not None


async def test_action_listing_paused_status(db: AsyncSession):
    """Explicit status='paused' is stored correctly."""
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = ActionListing(
        id=_new_id(),
        tool_id=tool.id,
        seller_id=agent.id,
        title="Paused Listing",
        price_per_execution=Decimal("1.0"),
        status="paused",
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    assert listing.status == "paused"


# ===========================================================================
# ActionExecution Tests
# ===========================================================================


async def _setup_action_listing_deps(db: AsyncSession):
    """Create and persist Creator, WebMCPTool, RegisteredAgent, and ActionListing.

    Returns (agent, tool, listing) so tests can create ActionExecution rows.
    """
    creator = _make_creator()
    db.add(creator)
    await db.commit()

    tool = _make_tool(creator.id)
    db.add(tool)
    await db.commit()

    agent = _make_agent()
    db.add(agent)
    await db.commit()

    listing = _make_action_listing(tool.id, agent.id)
    db.add(listing)
    await db.commit()

    return agent, tool, listing


async def test_action_execution_creation_required_fields(db: AsyncSession):
    """ActionExecution persists with all required FK fields and amount_usdc."""
    agent, tool, listing = await _setup_action_listing_deps(db)

    execution = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.100000"),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.id is not None
    assert execution.action_listing_id == listing.id
    assert execution.buyer_id == agent.id
    assert execution.tool_id == tool.id
    assert float(execution.amount_usdc) == pytest.approx(0.1)


async def test_action_execution_status_default_pending(db: AsyncSession):
    """status defaults to 'pending'."""
    agent, tool, listing = await _setup_action_listing_deps(db)

    execution = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.5"),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.status == "pending"


async def test_action_execution_payment_status_default_held(db: AsyncSession):
    """payment_status defaults to 'held'."""
    agent, tool, listing = await _setup_action_listing_deps(db)

    execution = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.5"),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.payment_status == "held"


async def test_action_execution_proof_verified_default_false(db: AsyncSession):
    """proof_verified defaults to False."""
    agent, tool, listing = await _setup_action_listing_deps(db)

    execution = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.5"),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.proof_verified is False


async def test_action_execution_parameters_default_empty_json(db: AsyncSession):
    """parameters defaults to '{}'."""
    agent, tool, listing = await _setup_action_listing_deps(db)

    execution = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.5"),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.parameters == "{}"


async def test_action_execution_result_default_empty_json(db: AsyncSession):
    """result defaults to '{}'."""
    agent, tool, listing = await _setup_action_listing_deps(db)

    execution = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.5"),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.result == "{}"


async def test_action_execution_nullable_fields(db: AsyncSession):
    """error_message, execution_time_ms, proof_of_execution, started_at, completed_at are nullable."""
    agent, tool, listing = await _setup_action_listing_deps(db)

    execution = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.5"),
        error_message=None,
        execution_time_ms=None,
        proof_of_execution=None,
        started_at=None,
        completed_at=None,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.error_message is None
    assert execution.execution_time_ms is None
    assert execution.proof_of_execution is None
    assert execution.started_at is None
    assert execution.completed_at is None


async def test_action_execution_created_at_auto_populated(db: AsyncSession):
    """created_at is set automatically on insert."""
    agent, tool, listing = await _setup_action_listing_deps(db)

    execution = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.5"),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.created_at is not None


async def test_action_execution_completed_status(db: AsyncSession):
    """Explicit status='completed' and payment_status='captured' are stored correctly."""
    agent, tool, listing = await _setup_action_listing_deps(db)
    from datetime import datetime, timezone

    execution = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("1.0"),
        status="completed",
        payment_status="captured",
        proof_verified=True,
        execution_time_ms=350,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    assert execution.status == "completed"
    assert execution.payment_status == "captured"
    assert execution.proof_verified is True
    assert execution.execution_time_ms == 350
    assert execution.completed_at is not None


async def test_action_execution_query_by_status(db: AsyncSession):
    """ActionExecution rows can be queried by status."""
    agent, tool, listing = await _setup_action_listing_deps(db)

    ex1 = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.1"),
        status="pending",
    )
    ex2 = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.2"),
        status="failed",
    )
    db.add_all([ex1, ex2])
    await db.commit()

    result = await db.execute(
        select(ActionExecution).where(ActionExecution.status == "failed")
    )
    found = result.scalars().all()
    assert len(found) == 1
    assert found[0].id == ex2.id


async def test_action_execution_relationship_to_listing(db: AsyncSession):
    """ActionExecution.action_listing relationship resolves to the parent ActionListing."""
    agent, tool, listing = await _setup_action_listing_deps(db)

    execution = ActionExecution(
        id=_new_id(),
        action_listing_id=listing.id,
        buyer_id=agent.id,
        tool_id=tool.id,
        amount_usdc=Decimal("0.5"),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # The lazy="selectin" relationship should auto-load
    assert execution.action_listing is not None
    assert execution.action_listing.id == listing.id
    assert execution.action_listing.title == "Test Action Listing"
