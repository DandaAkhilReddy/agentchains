"""Comprehensive tests for chain_policy_service and chain_settlement_service.

Coverage:
    chain_policy_service  : create_policy, list_policies, get_policy,
                            check_jurisdiction_policy, check_cost_policy,
                            evaluate_chain_policies
    chain_settlement_service : _get_platform_price, settle_chain_execution,
                               estimate_chain_cost, get_settlement_report
"""

from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.action_listing import ActionListing
from marketplace.models.catalog import DataCatalogEntry
from marketplace.models.chain_template import ChainExecution, ChainTemplate
from marketplace.models.listing import DataListing
from marketplace.models.token_account import TokenLedger
from marketplace.models.workflow import WorkflowDefinition, WorkflowNodeExecution, WorkflowExecution
from marketplace.services import chain_policy_service, chain_settlement_service
from marketplace.services.chain_policy_service import (
    check_jurisdiction_policy,
    check_cost_policy,
    create_policy,
    evaluate_chain_policies,
    get_policy,
    list_policies,
)
from marketplace.services.chain_settlement_service import (
    _get_platform_price,
    estimate_chain_cost,
    get_settlement_report,
    settle_chain_execution,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_id() -> str:
    return str(uuid.uuid4())


def _graph_json(agent_ids: list[str]) -> str:
    """Build a minimal valid graph JSON with one agent_call node per agent."""
    nodes: dict = {}
    for i, aid in enumerate(agent_ids):
        nodes[f"node_{i}"] = {
            "type": "agent_call",
            "config": {"agent_id": aid},
        }
    return json.dumps({"nodes": nodes, "edges": []})


async def _make_template(db: AsyncSession, agent_id: str, agent_ids: list[str] | None = None) -> ChainTemplate:
    """Create a minimal WorkflowDefinition + ChainTemplate in the test DB."""
    graph = _graph_json(agent_ids or [agent_id])
    workflow = WorkflowDefinition(
        id=_new_id(),
        name="test-wf",
        graph_json=graph,
        owner_id=agent_id,
    )
    db.add(workflow)
    await db.commit()

    template = ChainTemplate(
        id=_new_id(),
        name="test-chain",
        workflow_id=workflow.id,
        graph_json=graph,
        author_id=agent_id,
        status="active",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def _make_chain_execution(
    db: AsyncSession,
    template: ChainTemplate,
    initiated_by: str,
    status: str = "completed",
    workflow_execution_id: str | None = None,
) -> ChainExecution:
    """Create a ChainExecution row."""
    wf_exec_id = workflow_execution_id or _new_id()

    # Also create a stub WorkflowExecution so FK is satisfied
    wf = WorkflowExecution(
        id=wf_exec_id,
        workflow_id=template.workflow_id,
        initiated_by=initiated_by,
        status="completed",
    )
    db.add(wf)
    await db.commit()

    exec_ = ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        workflow_execution_id=wf_exec_id,
        initiated_by=initiated_by,
        status=status,
    )
    db.add(exec_)
    await db.commit()
    await db.refresh(exec_)
    return exec_


async def _make_node_execution(
    db: AsyncSession,
    workflow_execution_id: str,
    node_id: str,
    agent_id: str,
    node_type: str = "agent_call",
    status: str = "completed",
) -> WorkflowNodeExecution:
    """Create a WorkflowNodeExecution row with agent_id encoded in input_json."""
    ne = WorkflowNodeExecution(
        id=_new_id(),
        execution_id=workflow_execution_id,
        node_id=node_id,
        node_type=node_type,
        status=status,
        input_json=json.dumps({"agent_id": agent_id}),
    )
    db.add(ne)
    await db.commit()
    await db.refresh(ne)
    return ne


# ============================================================================
# chain_policy_service — CRUD
# ============================================================================


class TestCreatePolicy:
    async def test_create_jurisdiction_policy(self, db: AsyncSession, make_agent):
        """Happy path: jurisdiction policy is created and persisted."""
        agent, _ = await make_agent("policy-owner")
        rules = json.dumps({"allowed_jurisdictions": ["US", "IN"]})

        policy = await create_policy(
            db,
            name="US-IN Only",
            policy_type="jurisdiction",
            rules_json=rules,
            owner_id=agent.id,
        )

        assert policy.id is not None
        assert policy.name == "US-IN Only"
        assert policy.policy_type == "jurisdiction"
        assert policy.enforcement == "block"
        assert policy.status == "active"
        assert policy.owner_id == agent.id

    async def test_create_cost_limit_policy(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        rules = json.dumps({"max_cost_usd": 5.0})

        policy = await create_policy(
            db,
            name="Budget Cap",
            policy_type="cost_limit",
            rules_json=rules,
            owner_id=agent.id,
            enforcement="warn",
        )

        assert policy.policy_type == "cost_limit"
        assert policy.enforcement == "warn"

    async def test_create_data_residency_policy(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        rules = json.dumps({"allowed_regions": ["EU", "US"]})

        policy = await create_policy(
            db,
            name="EU Residency",
            policy_type="data_residency",
            rules_json=rules,
            owner_id=agent.id,
        )

        assert policy.policy_type == "data_residency"

    async def test_create_policy_custom_enforcement_log(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        policy = await create_policy(
            db,
            name="Log Policy",
            policy_type="jurisdiction",
            rules_json=json.dumps({"allowed_jurisdictions": ["CH"]}),
            owner_id=agent.id,
            enforcement="log",
        )
        assert policy.enforcement == "log"

    async def test_create_policy_invalid_json_raises(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        with pytest.raises(ValueError, match="rules_json must be valid JSON"):
            await create_policy(
                db,
                name="Bad JSON",
                policy_type="jurisdiction",
                rules_json="not-valid-json{{{",
                owner_id=agent.id,
            )

    async def test_create_policy_invalid_type_raises(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        with pytest.raises(ValueError, match="Invalid policy_type"):
            await create_policy(
                db,
                name="Bad Type",
                policy_type="nonexistent_type",
                rules_json=json.dumps({}),
                owner_id=agent.id,
            )

    async def test_create_policy_invalid_enforcement_raises(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        with pytest.raises(ValueError, match="Invalid enforcement"):
            await create_policy(
                db,
                name="Bad Enforcement",
                policy_type="jurisdiction",
                rules_json=json.dumps({"allowed_jurisdictions": []}),
                owner_id=agent.id,
                enforcement="destroy",
            )


class TestListPolicies:
    async def test_list_returns_all_when_no_filters(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        for i in range(3):
            await create_policy(
                db,
                name=f"Policy {i}",
                policy_type="jurisdiction",
                rules_json=json.dumps({"allowed_jurisdictions": ["US"]}),
                owner_id=agent.id,
            )

        policies, total = await list_policies(db)
        assert total == 3
        assert len(policies) == 3

    async def test_list_filter_by_owner(self, db: AsyncSession, make_agent):
        owner_a, _ = await make_agent("owner-a")
        owner_b, _ = await make_agent("owner-b")

        await create_policy(
            db, "P-A", "jurisdiction", json.dumps({"allowed_jurisdictions": ["US"]}), owner_a.id
        )
        await create_policy(
            db, "P-B", "jurisdiction", json.dumps({"allowed_jurisdictions": ["IN"]}), owner_b.id
        )

        policies, total = await list_policies(db, owner_id=owner_a.id)
        assert total == 1
        assert policies[0].owner_id == owner_a.id

    async def test_list_filter_by_policy_type(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        await create_policy(
            db, "J-Policy", "jurisdiction", json.dumps({"allowed_jurisdictions": ["US"]}), agent.id
        )
        await create_policy(
            db, "C-Policy", "cost_limit", json.dumps({"max_cost_usd": 10}), agent.id
        )

        policies, total = await list_policies(db, policy_type="jurisdiction")
        assert total == 1
        assert policies[0].policy_type == "jurisdiction"

    async def test_list_filter_by_status(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        p = await create_policy(
            db, "Active P", "jurisdiction", json.dumps({"allowed_jurisdictions": ["US"]}), agent.id
        )
        # Manually disable it
        p.status = "disabled"
        await db.commit()

        active_policies, active_total = await list_policies(db, status="active")
        disabled_policies, disabled_total = await list_policies(db, status="disabled")

        assert active_total == 0
        assert disabled_total == 1

    async def test_list_pagination_limit(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        for i in range(5):
            await create_policy(
                db, f"P{i}", "jurisdiction", json.dumps({"allowed_jurisdictions": ["US"]}), agent.id
            )

        policies, total = await list_policies(db, limit=2)
        assert total == 5
        assert len(policies) == 2

    async def test_list_pagination_offset(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        for i in range(5):
            await create_policy(
                db, f"P{i}", "jurisdiction", json.dumps({"allowed_jurisdictions": ["US"]}), agent.id
            )

        policies, total = await list_policies(db, offset=3, limit=10)
        assert total == 5
        assert len(policies) == 2

    async def test_list_empty_returns_zero(self, db: AsyncSession):
        policies, total = await list_policies(db)
        assert total == 0
        assert policies == []


class TestGetPolicy:
    async def test_get_policy_found(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        p = await create_policy(
            db, "Find Me", "jurisdiction", json.dumps({"allowed_jurisdictions": ["US"]}), agent.id
        )

        fetched = await get_policy(db, p.id)
        assert fetched is not None
        assert fetched.id == p.id
        assert fetched.name == "Find Me"

    async def test_get_policy_not_found_returns_none(self, db: AsyncSession):
        result = await get_policy(db, _new_id())
        assert result is None


# ============================================================================
# chain_policy_service — Pure-function checks
# ============================================================================


class TestCheckJurisdictionPolicy:
    def test_all_agents_within_allowed(self):
        agents = [
            {"id": "a1", "name": "A1", "jurisdictions": ["US", "IN"]},
            {"id": "a2", "name": "A2", "jurisdictions": ["US"]},
        ]
        result = check_jurisdiction_policy(agents, ["US", "IN", "CH"])
        assert result["passed"] is True
        assert result["violations"] == []

    def test_one_agent_outside_allowed(self):
        agents = [
            {"id": "a1", "name": "A1", "jurisdictions": ["US"]},
            {"id": "a2", "name": "A2", "jurisdictions": ["CN"]},   # not in allowed
        ]
        result = check_jurisdiction_policy(agents, ["US", "IN"])
        assert result["passed"] is False
        assert len(result["violations"]) == 1
        assert result["violations"][0]["agent_id"] == "a2"
        assert "CN" in result["violations"][0]["disallowed_jurisdictions"]

    def test_agent_without_jurisdictions_is_skipped(self):
        agents = [
            {"id": "a1", "name": "A1"},   # no jurisdictions key
            {"id": "a2", "name": "A2", "jurisdictions": []},
        ]
        result = check_jurisdiction_policy(agents, ["US"])
        assert result["passed"] is True
        assert result["violations"] == []

    def test_multiple_violations(self):
        agents = [
            {"id": "a1", "name": "A1", "jurisdictions": ["CN", "RU"]},
            {"id": "a2", "name": "A2", "jurisdictions": ["KP"]},
        ]
        result = check_jurisdiction_policy(agents, ["US"])
        assert result["passed"] is False
        assert len(result["violations"]) == 2

    def test_empty_agent_list_passes(self):
        result = check_jurisdiction_policy([], ["US", "IN"])
        assert result["passed"] is True


class TestCheckCostPolicy:
    def test_within_budget(self):
        result = check_cost_policy(Decimal("3.50"), Decimal("5.00"))
        assert result["passed"] is True
        assert result["estimated_cost"] == 3.5
        assert result["max_allowed"] == 5.0

    def test_exactly_at_limit(self):
        result = check_cost_policy(5.0, 5.0)
        assert result["passed"] is True

    def test_over_budget(self):
        result = check_cost_policy(Decimal("10.00"), Decimal("5.00"))
        assert result["passed"] is False
        assert result["estimated_cost"] == 10.0

    def test_zero_cost_passes(self):
        result = check_cost_policy(0, 1.0)
        assert result["passed"] is True

    def test_float_inputs(self):
        result = check_cost_policy(4.99, 5.00)
        assert result["passed"] is True


# ============================================================================
# chain_policy_service — evaluate_chain_policies (async, DB-backed)
# ============================================================================


class TestEvaluatePolicies:
    async def test_evaluate_jurisdiction_pass(self, db: AsyncSession, make_agent):
        """Jurisdiction policy passes when agents' jurisdictions are allowed."""
        agent, _ = await make_agent()
        # Agent has no jurisdictions in card → policy passes (no violation)
        template = await _make_template(db, agent.id)

        policy = await create_policy(
            db,
            name="US Only",
            policy_type="jurisdiction",
            rules_json=json.dumps({"allowed_jurisdictions": ["US"]}),
            owner_id=agent.id,
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is True
        assert len(report["policy_results"]) == 1
        assert report["policy_results"][0]["passed"] is True

    async def test_evaluate_cost_limit_pass(self, db: AsyncSession, make_agent):
        """Cost limit policy passes when template budget is within limit."""
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)
        # avg_cost_usd defaults to 0, max_budget_usd is None → estimated = 0
        policy = await create_policy(
            db,
            name="Budget Policy",
            policy_type="cost_limit",
            rules_json=json.dumps({"max_cost_usd": 100}),
            owner_id=agent.id,
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is True
        assert report["policy_results"][0]["passed"] is True

    async def test_evaluate_cost_limit_fail_blocks(self, db: AsyncSession, make_agent):
        """Cost limit policy fails and blocks when budget exceeds max."""
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)
        # Set a high avg cost on the template
        template.avg_cost_usd = Decimal("50.00")
        await db.commit()

        policy = await create_policy(
            db,
            name="Tight Budget",
            policy_type="cost_limit",
            rules_json=json.dumps({"max_cost_usd": 1.0}),
            owner_id=agent.id,
            enforcement="block",
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is False
        assert len(report["block_reasons"]) == 1
        assert report["policy_results"][0]["passed"] is False

    async def test_evaluate_disabled_policy_skipped(self, db: AsyncSession, make_agent):
        """Disabled policy is not enforced but overall_passed stays True."""
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)
        policy = await create_policy(
            db,
            name="Disabled",
            policy_type="jurisdiction",
            rules_json=json.dumps({"allowed_jurisdictions": []}),
            owner_id=agent.id,
        )
        policy.status = "disabled"
        await db.commit()

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is True
        assert report["policy_results"][0]["status"] == "disabled"
        assert report["policy_results"][0]["passed"] is True

    async def test_evaluate_nonexistent_policy_fails(self, db: AsyncSession, make_agent):
        """A policy_id that doesn't exist causes overall_passed=False."""
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)
        fake_id = _new_id()

        report = await evaluate_chain_policies(db, template.id, [fake_id])
        assert report["overall_passed"] is False
        assert report["policy_results"][0]["status"] == "not_found"

    async def test_evaluate_template_not_found_raises(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        policy = await create_policy(
            db,
            name="P",
            policy_type="jurisdiction",
            rules_json=json.dumps({"allowed_jurisdictions": ["US"]}),
            owner_id=agent.id,
        )
        with pytest.raises(ValueError, match="Chain template not found"):
            await evaluate_chain_policies(db, _new_id(), [policy.id])

    async def test_evaluate_warn_enforcement_does_not_block(self, db: AsyncSession, make_agent):
        """Failed policy with enforcement='warn' does not set overall_passed=False."""
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)
        template.avg_cost_usd = Decimal("99.99")
        await db.commit()

        policy = await create_policy(
            db,
            name="Warn Policy",
            policy_type="cost_limit",
            rules_json=json.dumps({"max_cost_usd": 0.01}),
            owner_id=agent.id,
            enforcement="warn",
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        # warn does not set overall_passed to False
        assert report["overall_passed"] is True
        assert report["policy_results"][0]["passed"] is False
        assert report["block_reasons"] == []

    async def test_evaluate_data_residency_policy(self, db: AsyncSession, make_agent):
        """data_residency policy reuses jurisdiction check logic."""
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)
        policy = await create_policy(
            db,
            name="EU Residency",
            policy_type="data_residency",
            rules_json=json.dumps({"allowed_regions": ["EU", "US"]}),
            owner_id=agent.id,
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["policy_results"][0]["policy_type"] == "data_residency"
        assert report["policy_results"][0]["passed"] is True

    async def test_evaluate_multiple_policies_all_pass(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)

        p1 = await create_policy(
            db, "P1", "jurisdiction", json.dumps({"allowed_jurisdictions": ["US"]}), agent.id
        )
        p2 = await create_policy(
            db, "P2", "cost_limit", json.dumps({"max_cost_usd": 999}), agent.id
        )

        report = await evaluate_chain_policies(db, template.id, [p1.id, p2.id])
        assert report["overall_passed"] is True
        assert len(report["policy_results"]) == 2
        assert all(r["passed"] for r in report["policy_results"])

    async def test_evaluate_empty_policy_list(self, db: AsyncSession, make_agent):
        """Zero policies → overall_passed=True, empty results."""
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)

        report = await evaluate_chain_policies(db, template.id, [])
        assert report["overall_passed"] is True
        assert report["policy_results"] == []


# ============================================================================
# chain_settlement_service — _get_platform_price
# ============================================================================


class TestGetPlatformPrice:
    async def test_returns_data_listing_price(self, db: AsyncSession, make_agent, make_listing):
        """DataListing price is returned first."""
        agent, _ = await make_agent()
        listing = await make_listing(agent.id, price_usdc=2.50)

        price = await _get_platform_price(db, agent.id)
        assert price == Decimal("2.50")

    async def test_returns_action_listing_price_when_no_data_listing(self, db: AsyncSession, make_agent, make_creator):
        """Falls back to ActionListing when no DataListing exists."""
        from marketplace.models.action_listing import ActionListing
        from marketplace.models.webmcp_tool import WebMCPTool

        agent, _ = await make_agent()
        creator, _ = await make_creator()

        # WebMCPTool requires creator_id, domain, category
        tool = WebMCPTool(
            id=_new_id(),
            name="test-tool",
            domain="example.com",
            endpoint_url="https://example.com/tool",
            creator_id=creator.id,
            agent_id=agent.id,
            category="research",
            status="active",
        )
        db.add(tool)
        await db.commit()

        action_listing = ActionListing(
            id=_new_id(),
            tool_id=tool.id,
            seller_id=agent.id,
            title="Test Action",
            price_per_execution=Decimal("1.75"),
            status="active",
        )
        db.add(action_listing)
        await db.commit()

        price = await _get_platform_price(db, agent.id)
        assert price == Decimal("1.75")

    async def test_returns_catalog_price_as_last_resort(self, db: AsyncSession, make_agent, make_catalog_entry):
        """Falls back to DataCatalogEntry price_range_min."""
        agent, _ = await make_agent()
        await make_catalog_entry(agent.id, price_range_min=0.005)

        price = await _get_platform_price(db, agent.id)
        assert price == Decimal("0.005")

    async def test_returns_zero_when_no_listing(self, db: AsyncSession, make_agent):
        """Returns Decimal('0') when no pricing source found."""
        agent, _ = await make_agent()
        price = await _get_platform_price(db, agent.id)
        assert price == Decimal("0")

    async def test_returns_zero_for_unknown_agent(self, db: AsyncSession):
        """No listing for unknown agent → returns 0."""
        price = await _get_platform_price(db, _new_id())
        assert price == Decimal("0")


# ============================================================================
# chain_settlement_service — settle_chain_execution
# ============================================================================


class TestSettleChainExecution:
    async def test_settle_happy_path(self, db: AsyncSession, make_agent, make_listing, make_token_account, seed_platform):
        """Happy path: single node settled, transfer recorded."""
        buyer, _ = await make_agent("buyer")
        seller, _ = await make_agent("seller")
        await make_token_account(buyer.id, 1000)
        await make_token_account(seller.id, 0)

        listing = await make_listing(seller.id, price_usdc=5.0)

        template = await _make_template(db, buyer.id, agent_ids=[seller.id])
        chain_exec = await _make_chain_execution(db, template, buyer.id)

        node_id = f"node_0"
        await _make_node_execution(
            db,
            chain_exec.workflow_execution_id,
            node_id,
            seller.id,
        )

        with patch(
            "marketplace.services.chain_settlement_service.get_execution_nodes",
        ) as mock_get_nodes:
            from marketplace.models.workflow import WorkflowNodeExecution
            ne = WorkflowNodeExecution(
                id=_new_id(),
                execution_id=chain_exec.workflow_execution_id,
                node_id=node_id,
                node_type="agent_call",
                status="completed",
                input_json=json.dumps({"agent_id": seller.id}),
            )
            mock_get_nodes.return_value = [ne]

            result = await settle_chain_execution(db, chain_exec.id)

        assert result["status"] == "settled"
        assert len(result["transfers"]) == 1
        assert result["transfers"][0]["agent_id"] == seller.id
        assert result["transfers"][0]["amount_usd"] == pytest.approx(5.0)
        assert result["errors"] == []
        assert result["total_settled_usd"] == pytest.approx(5.0)

    async def test_settle_execution_not_found_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Chain execution not found"):
            await settle_chain_execution(db, _new_id())

    async def test_settle_not_completed_raises(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)
        chain_exec = await _make_chain_execution(db, template, agent.id, status="running")

        with pytest.raises(ValueError, match="Cannot settle execution"):
            await settle_chain_execution(db, chain_exec.id)

    async def test_settle_no_workflow_execution_raises(self, db: AsyncSession, make_agent):
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)

        # Create execution without workflow_execution_id
        exec_ = ChainExecution(
            id=_new_id(),
            chain_template_id=template.id,
            workflow_execution_id=None,
            initiated_by=agent.id,
            status="completed",
        )
        db.add(exec_)
        await db.commit()

        with pytest.raises(ValueError, match="no associated workflow execution"):
            await settle_chain_execution(db, exec_.id)

    async def test_settle_skips_zero_price_agents(self, db: AsyncSession, make_agent, make_token_account, seed_platform):
        """Agents with price=0 are silently skipped (no transfer)."""
        buyer, _ = await make_agent("buyer")
        free_agent, _ = await make_agent("free-agent")
        await make_token_account(buyer.id, 100)
        await make_token_account(free_agent.id, 0)
        # No listing → price = 0

        template = await _make_template(db, buyer.id, agent_ids=[free_agent.id])
        chain_exec = await _make_chain_execution(db, template, buyer.id)

        ne = WorkflowNodeExecution(
            id=_new_id(),
            execution_id=chain_exec.workflow_execution_id,
            node_id="node_0",
            node_type="agent_call",
            status="completed",
            input_json=json.dumps({"agent_id": free_agent.id}),
        )

        with patch(
            "marketplace.services.chain_settlement_service.get_execution_nodes",
            return_value=[ne],
        ):
            result = await settle_chain_execution(db, chain_exec.id)

        assert result["total_settled_usd"] == 0.0
        assert result["transfers"] == []
        assert result["errors"] == []

    async def test_settle_skips_non_agent_call_nodes(self, db: AsyncSession, make_agent, make_token_account, seed_platform):
        """condition/loop nodes are not settled."""
        buyer, _ = await make_agent("buyer")
        await make_token_account(buyer.id, 100)

        template = await _make_template(db, buyer.id)
        chain_exec = await _make_chain_execution(db, template, buyer.id)

        condition_node = WorkflowNodeExecution(
            id=_new_id(),
            execution_id=chain_exec.workflow_execution_id,
            node_id="cond_node",
            node_type="condition",
            status="completed",
            input_json="{}",
        )

        with patch(
            "marketplace.services.chain_settlement_service.get_execution_nodes",
            return_value=[condition_node],
        ):
            result = await settle_chain_execution(db, chain_exec.id)

        assert result["transfers"] == []
        assert result["total_settled_usd"] == 0.0

    async def test_settle_idempotency_key_format(self, db: AsyncSession, make_agent, make_listing, make_token_account, seed_platform):
        """Idempotency key follows chn-{exec_id[:16]}-{sha256(node_id)[:16]} format."""
        buyer, _ = await make_agent("buyer")
        seller, _ = await make_agent("seller")
        await make_token_account(buyer.id, 1000)
        await make_token_account(seller.id, 0)
        await make_listing(seller.id, price_usdc=1.0)

        template = await _make_template(db, buyer.id, agent_ids=[seller.id])
        chain_exec = await _make_chain_execution(db, template, buyer.id)
        node_id = "node_0"

        ne = WorkflowNodeExecution(
            id=_new_id(),
            execution_id=chain_exec.workflow_execution_id,
            node_id=node_id,
            node_type="agent_call",
            status="completed",
            input_json=json.dumps({"agent_id": seller.id}),
        )

        with patch(
            "marketplace.services.chain_settlement_service.get_execution_nodes",
            return_value=[ne],
        ):
            result = await settle_chain_execution(db, chain_exec.id)

        expected_node_hash = hashlib.sha256(node_id.encode()).hexdigest()[:16]
        expected_key = f"chn-{chain_exec.id[:16]}-{expected_node_hash}"
        assert result["transfers"][0]["idempotency_key"] == expected_key

    async def test_settle_transfer_error_recorded_as_partial(self, db: AsyncSession, make_agent, make_listing, make_token_account, seed_platform):
        """When token_service.transfer raises ValueError, error is captured and status='partial'."""
        buyer, _ = await make_agent("buyer")
        seller, _ = await make_agent("seller")
        await make_token_account(buyer.id, 0)   # insufficient
        await make_token_account(seller.id, 0)
        await make_listing(seller.id, price_usdc=5.0)

        template = await _make_template(db, buyer.id, agent_ids=[seller.id])
        chain_exec = await _make_chain_execution(db, template, buyer.id)

        ne = WorkflowNodeExecution(
            id=_new_id(),
            execution_id=chain_exec.workflow_execution_id,
            node_id="node_0",
            node_type="agent_call",
            status="completed",
            input_json=json.dumps({"agent_id": seller.id}),
        )

        with patch(
            "marketplace.services.chain_settlement_service.get_execution_nodes",
            return_value=[ne],
        ):
            result = await settle_chain_execution(db, chain_exec.id)

        # Buyer had no balance → transfer fails → partial
        assert result["status"] == "partial"
        assert len(result["errors"]) == 1
        assert result["errors"][0]["agent_id"] == seller.id
        assert result["total_settled_usd"] == 0.0

    async def test_settle_agent_id_from_graph_when_not_in_input(self, db: AsyncSession, make_agent, make_listing, make_token_account, seed_platform):
        """agent_id resolved from template graph when not present in input_json."""
        buyer, _ = await make_agent("buyer")
        seller, _ = await make_agent("seller")
        await make_token_account(buyer.id, 1000)
        await make_token_account(seller.id, 0)
        await make_listing(seller.id, price_usdc=3.0)

        template = await _make_template(db, buyer.id, agent_ids=[seller.id])
        chain_exec = await _make_chain_execution(db, template, buyer.id)

        # Node input has NO agent_id → service must look up graph
        ne = WorkflowNodeExecution(
            id=_new_id(),
            execution_id=chain_exec.workflow_execution_id,
            node_id="node_0",   # matches graph node "node_0"
            node_type="agent_call",
            status="completed",
            input_json="{}",
        )

        with patch(
            "marketplace.services.chain_settlement_service.get_execution_nodes",
            return_value=[ne],
        ):
            result = await settle_chain_execution(db, chain_exec.id)

        assert len(result["transfers"]) == 1
        assert result["transfers"][0]["agent_id"] == seller.id


# ============================================================================
# chain_settlement_service — estimate_chain_cost
# ============================================================================


class TestEstimateChainCost:
    async def test_estimate_with_data_listing_prices(self, db: AsyncSession, make_agent, make_listing):
        """Estimates correctly from DataListing prices for each agent node."""
        owner, _ = await make_agent("owner")
        agent_a, _ = await make_agent("agent-a")
        agent_b, _ = await make_agent("agent-b")
        await make_listing(agent_a.id, price_usdc=2.0)
        await make_listing(agent_b.id, price_usdc=3.0)

        template = await _make_template(db, owner.id, agent_ids=[agent_a.id, agent_b.id])

        result = await estimate_chain_cost(db, template.id)

        assert result["chain_template_id"] == template.id
        assert result["estimated_total_usd"] == pytest.approx(5.0)
        assert len(result["agent_costs"]) == 2

    async def test_estimate_zero_for_unpriced_agents(self, db: AsyncSession, make_agent):
        """Agents with no listing contribute 0 to the estimate."""
        owner, _ = await make_agent("owner")
        unpriced, _ = await make_agent("unpriced")

        template = await _make_template(db, owner.id, agent_ids=[unpriced.id])
        result = await estimate_chain_cost(db, template.id)

        assert result["estimated_total_usd"] == 0.0
        assert result["agent_costs"][0]["estimated_cost_usd"] == 0.0

    async def test_estimate_includes_historical_avg(self, db: AsyncSession, make_agent):
        """historical_avg_usd is populated from completed chain executions."""
        owner, _ = await make_agent("owner")
        template = await _make_template(db, owner.id)

        # Add completed executions with known costs
        for cost in [10.0, 20.0]:
            exec_ = ChainExecution(
                id=_new_id(),
                chain_template_id=template.id,
                workflow_execution_id=_new_id(),
                initiated_by=owner.id,
                status="completed",
                total_cost_usd=Decimal(str(cost)),
            )
            db.add(exec_)
        await db.commit()

        result = await estimate_chain_cost(db, template.id)
        assert result["historical_avg_usd"] == pytest.approx(15.0)

    async def test_estimate_historical_avg_none_when_no_executions(self, db: AsyncSession, make_agent):
        owner, _ = await make_agent("owner")
        template = await _make_template(db, owner.id)

        result = await estimate_chain_cost(db, template.id)
        assert result["historical_avg_usd"] is None

    async def test_estimate_template_not_found_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Chain template not found"):
            await estimate_chain_cost(db, _new_id())

    async def test_estimate_skips_non_agent_call_nodes(self, db: AsyncSession, make_agent, make_listing):
        """Condition/loop nodes are excluded from cost estimate."""
        owner, _ = await make_agent("owner")
        agent_a, _ = await make_agent("agent-a")
        await make_listing(agent_a.id, price_usdc=2.0)

        # Build graph with mixed node types
        graph = {
            "nodes": {
                "n0": {"type": "agent_call", "config": {"agent_id": agent_a.id}},
                "n1": {"type": "condition", "config": {}},
                "n2": {"type": "loop", "config": {}},
            },
            "edges": [],
        }
        workflow = WorkflowDefinition(
            id=_new_id(), name="mixed-wf", graph_json=json.dumps(graph), owner_id=owner.id
        )
        db.add(workflow)
        await db.commit()
        template = ChainTemplate(
            id=_new_id(), name="mixed-chain", workflow_id=workflow.id,
            graph_json=json.dumps(graph), author_id=owner.id, status="active",
        )
        db.add(template)
        await db.commit()

        result = await estimate_chain_cost(db, template.id)
        # Only the agent_call node contributes cost
        assert result["estimated_total_usd"] == pytest.approx(2.0)
        assert len(result["agent_costs"]) == 1

    async def test_estimate_returns_all_required_keys(self, db: AsyncSession, make_agent):
        owner, _ = await make_agent("owner")
        template = await _make_template(db, owner.id)

        result = await estimate_chain_cost(db, template.id)
        assert "chain_template_id" in result
        assert "estimated_total_usd" in result
        assert "agent_costs" in result
        assert "historical_avg_usd" in result


# ============================================================================
# chain_settlement_service — get_settlement_report
# ============================================================================


class TestGetSettlementReport:
    async def test_report_no_settlements(self, db: AsyncSession, make_agent):
        """A completed execution with no ledger entries returns zero totals."""
        agent, _ = await make_agent()
        template = await _make_template(db, agent.id)
        chain_exec = await _make_chain_execution(db, template, agent.id)

        report = await get_settlement_report(db, chain_exec.id)
        assert report["chain_execution_id"] == chain_exec.id
        assert report["total_paid_usd"] == 0.0
        assert report["total_fees_usd"] == 0.0
        assert report["payments"] == []

    async def test_report_with_ledger_entries(self, db: AsyncSession, make_agent, make_listing, make_token_account, seed_platform):
        """Report correctly aggregates existing ledger entries for the execution."""
        buyer, _ = await make_agent("buyer")
        seller, _ = await make_agent("seller")
        await make_token_account(buyer.id, 500)
        await make_token_account(seller.id, 0)
        await make_listing(seller.id, price_usdc=10.0)

        template = await _make_template(db, buyer.id, agent_ids=[seller.id])
        chain_exec = await _make_chain_execution(db, template, buyer.id)

        ne = WorkflowNodeExecution(
            id=_new_id(),
            execution_id=chain_exec.workflow_execution_id,
            node_id="node_0",
            node_type="agent_call",
            status="completed",
            input_json=json.dumps({"agent_id": seller.id}),
        )

        with patch(
            "marketplace.services.chain_settlement_service.get_execution_nodes",
            return_value=[ne],
        ):
            settle_result = await settle_chain_execution(db, chain_exec.id)

        report = await get_settlement_report(db, chain_exec.id)
        assert report["chain_execution_id"] == chain_exec.id
        assert report["execution_status"] == "completed"
        assert report["total_paid_usd"] == pytest.approx(10.0)
        assert len(report["payments"]) == 1
        assert "ledger_id" in report["payments"][0]
        assert "amount_usd" in report["payments"][0]
        assert "fee_usd" in report["payments"][0]
        assert "idempotency_key" in report["payments"][0]

    async def test_report_execution_not_found_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Chain execution not found"):
            await get_settlement_report(db, _new_id())

    async def test_report_totals_are_decimal_accurate(self, db: AsyncSession, make_agent, make_listing, make_token_account, seed_platform):
        """Verify Decimal arithmetic is used — no floating-point drift."""
        buyer, _ = await make_agent("buyer")
        seller_a, _ = await make_agent("seller-a")
        seller_b, _ = await make_agent("seller-b")
        await make_token_account(buyer.id, 500)
        await make_token_account(seller_a.id, 0)
        await make_token_account(seller_b.id, 0)
        await make_listing(seller_a.id, price_usdc=7.77)
        await make_listing(seller_b.id, price_usdc=3.33)

        template = await _make_template(db, buyer.id, agent_ids=[seller_a.id, seller_b.id])
        chain_exec = await _make_chain_execution(db, template, buyer.id)

        nodes = [
            WorkflowNodeExecution(
                id=_new_id(), execution_id=chain_exec.workflow_execution_id,
                node_id=f"node_{i}", node_type="agent_call", status="completed",
                input_json=json.dumps({"agent_id": sid}),
            )
            for i, sid in enumerate([seller_a.id, seller_b.id])
        ]

        with patch(
            "marketplace.services.chain_settlement_service.get_execution_nodes",
            return_value=nodes,
        ):
            await settle_chain_execution(db, chain_exec.id)

        report = await get_settlement_report(db, chain_exec.id)
        # 7.77 + 3.33 = 11.10  (2% fee = 0.22 total)
        assert report["total_paid_usd"] == pytest.approx(11.10, abs=0.01)

    async def test_report_only_chain_settlement_entries(self, db: AsyncSession, make_agent, make_listing, make_token_account, seed_platform):
        """Report ignores ledger entries with other tx_types."""
        buyer, _ = await make_agent("buyer")
        seller, _ = await make_agent("seller")
        await make_token_account(buyer.id, 500)
        await make_token_account(seller.id, 0)
        await make_listing(seller.id, price_usdc=5.0)

        template = await _make_template(db, buyer.id, agent_ids=[seller.id])
        chain_exec = await _make_chain_execution(db, template, buyer.id)

        # Inject a foreign ledger entry with wrong tx_type
        from marketplace.services import token_service
        buyer_acct = await token_service.create_account(db, buyer.id)
        seller_acct = await token_service.create_account(db, seller.id)

        foreign_entry = TokenLedger(
            id=_new_id(),
            from_account_id=buyer_acct.id,
            to_account_id=seller_acct.id,
            amount=Decimal("99.99"),
            fee_amount=Decimal("0"),
            tx_type="purchase",                   # NOT chain_settlement
            reference_id=chain_exec.id,           # same reference_id though
            reference_type="chain_execution",
        )
        db.add(foreign_entry)
        await db.commit()

        report = await get_settlement_report(db, chain_exec.id)
        # The foreign purchase entry must NOT appear
        assert report["payments"] == []
        assert report["total_paid_usd"] == 0.0
