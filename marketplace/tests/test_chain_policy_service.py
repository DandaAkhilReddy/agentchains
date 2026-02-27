"""Tests for chain_policy_service — CRUD, validation, and policy evaluation.

Covers:
- create_policy: valid creation, invalid JSON, invalid policy_type, invalid enforcement
- list_policies: filtering by owner, type, status; pagination
- get_policy: existing and missing
- check_jurisdiction_policy: pass, violations, empty jurisdictions
- check_cost_policy: within/exceeding budget, edge at boundary
- evaluate_chain_policies: full evaluation pipeline with jurisdiction, cost_limit,
  data_residency, missing template, missing policy, disabled policy, block enforcement
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.agent import RegisteredAgent
from marketplace.models.chain_policy import ChainPolicy
from marketplace.models.chain_template import ChainTemplate
from marketplace.services.chain_policy_service import (
    check_cost_policy,
    check_jurisdiction_policy,
    create_policy,
    evaluate_chain_policies,
    get_policy,
    list_policies,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


async def _make_agent(
    db: AsyncSession,
    name: str | None = None,
    agent_card_json: str = "{}",
) -> RegisteredAgent:
    agent = RegisteredAgent(
        id=_id(),
        name=name or f"agent-{_id()[:8]}",
        agent_type="both",
        public_key="ssh-rsa AAAA_test",
        status="active",
        agent_card_json=agent_card_json,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def _make_template(
    db: AsyncSession,
    graph_json: str,
    author_id: str | None = None,
    max_budget_usd: Decimal | None = None,
    avg_cost_usd: Decimal | None = None,
) -> ChainTemplate:
    template = ChainTemplate(
        id=_id(),
        name=f"template-{_id()[:6]}",
        graph_json=graph_json,
        author_id=author_id,
        max_budget_usd=max_budget_usd,
        avg_cost_usd=avg_cost_usd,
        status="active",
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


# ---------------------------------------------------------------------------
# create_policy
# ---------------------------------------------------------------------------


class TestCreatePolicy:
    async def test_create_valid_jurisdiction_policy(self, db: AsyncSession):
        owner = await _make_agent(db)
        rules = json.dumps({"allowed_jurisdictions": ["US", "EU"]})
        policy = await create_policy(
            db, name="US-EU only", policy_type="jurisdiction",
            rules_json=rules, owner_id=owner.id,
        )
        assert policy.id is not None
        assert policy.name == "US-EU only"
        assert policy.policy_type == "jurisdiction"
        assert policy.enforcement == "block"
        assert policy.scope == "chain"
        assert policy.status == "active"
        assert policy.owner_id == owner.id

    async def test_create_cost_limit_policy(self, db: AsyncSession):
        owner = await _make_agent(db)
        rules = json.dumps({"max_cost_usd": 50})
        policy = await create_policy(
            db, name="budget cap", policy_type="cost_limit",
            rules_json=rules, owner_id=owner.id, enforcement="warn",
        )
        assert policy.policy_type == "cost_limit"
        assert policy.enforcement == "warn"

    async def test_create_data_residency_policy(self, db: AsyncSession):
        owner = await _make_agent(db)
        rules = json.dumps({"allowed_regions": ["eu-west-1", "eu-central-1"]})
        policy = await create_policy(
            db, name="EU residency", policy_type="data_residency",
            rules_json=rules, owner_id=owner.id, enforcement="log",
        )
        assert policy.policy_type == "data_residency"
        assert policy.enforcement == "log"

    async def test_invalid_json_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="valid JSON"):
            await create_policy(
                db, name="bad", policy_type="jurisdiction",
                rules_json="not json", owner_id="owner1",
            )

    async def test_none_json_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="valid JSON"):
            await create_policy(
                db, name="bad", policy_type="jurisdiction",
                rules_json=None, owner_id="owner1",
            )

    async def test_invalid_policy_type_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Invalid policy_type"):
            await create_policy(
                db, name="bad", policy_type="unknown_type",
                rules_json="{}", owner_id="owner1",
            )

    async def test_invalid_enforcement_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Invalid enforcement"):
            await create_policy(
                db, name="bad", policy_type="jurisdiction",
                rules_json="{}", owner_id="owner1", enforcement="deny",
            )

    async def test_custom_scope(self, db: AsyncSession):
        owner = await _make_agent(db)
        policy = await create_policy(
            db, name="node-level", policy_type="cost_limit",
            rules_json='{"max_cost_usd": 10}', owner_id=owner.id,
            scope="node",
        )
        assert policy.scope == "node"

    async def test_description_defaults_empty(self, db: AsyncSession):
        owner = await _make_agent(db)
        policy = await create_policy(
            db, name="no desc", policy_type="cost_limit",
            rules_json='{"max_cost_usd": 10}', owner_id=owner.id,
        )
        assert policy.description == ""

    async def test_description_saved(self, db: AsyncSession):
        owner = await _make_agent(db)
        policy = await create_policy(
            db, name="with desc", policy_type="cost_limit",
            rules_json='{"max_cost_usd": 10}', owner_id=owner.id,
            description="Budget cap for staging chains",
        )
        assert policy.description == "Budget cap for staging chains"


# ---------------------------------------------------------------------------
# list_policies
# ---------------------------------------------------------------------------


class TestListPolicies:
    async def test_list_empty(self, db: AsyncSession):
        policies, total = await list_policies(db)
        assert policies == []
        assert total == 0

    async def test_list_returns_created(self, db: AsyncSession):
        owner = await _make_agent(db)
        await create_policy(
            db, name="p1", policy_type="jurisdiction",
            rules_json='{"allowed_jurisdictions": ["US"]}', owner_id=owner.id,
        )
        policies, total = await list_policies(db)
        assert total == 1
        assert len(policies) == 1
        assert policies[0].name == "p1"

    async def test_filter_by_owner(self, db: AsyncSession):
        owner_a = await _make_agent(db, name="owner-a")
        owner_b = await _make_agent(db, name="owner-b")
        await create_policy(
            db, name="a-policy", policy_type="jurisdiction",
            rules_json='{}', owner_id=owner_a.id,
        )
        await create_policy(
            db, name="b-policy", policy_type="jurisdiction",
            rules_json='{}', owner_id=owner_b.id,
        )
        policies, total = await list_policies(db, owner_id=owner_a.id)
        assert total == 1
        assert policies[0].name == "a-policy"

    async def test_filter_by_policy_type(self, db: AsyncSession):
        owner = await _make_agent(db)
        await create_policy(
            db, name="j-policy", policy_type="jurisdiction",
            rules_json='{}', owner_id=owner.id,
        )
        await create_policy(
            db, name="c-policy", policy_type="cost_limit",
            rules_json='{"max_cost_usd": 100}', owner_id=owner.id,
        )
        policies, total = await list_policies(db, policy_type="cost_limit")
        assert total == 1
        assert policies[0].name == "c-policy"

    async def test_filter_by_status(self, db: AsyncSession):
        owner = await _make_agent(db)
        p = await create_policy(
            db, name="active-p", policy_type="jurisdiction",
            rules_json='{}', owner_id=owner.id,
        )
        # Manually disable one
        p.status = "disabled"
        await db.commit()

        policies, total = await list_policies(db, status="disabled")
        assert total == 1
        assert policies[0].status == "disabled"

    async def test_pagination(self, db: AsyncSession):
        owner = await _make_agent(db)
        for i in range(5):
            await create_policy(
                db, name=f"p-{i}", policy_type="jurisdiction",
                rules_json='{}', owner_id=owner.id,
            )
        policies, total = await list_policies(db, limit=2, offset=0)
        assert total == 5
        assert len(policies) == 2

        policies2, _ = await list_policies(db, limit=2, offset=2)
        assert len(policies2) == 2

        policies3, _ = await list_policies(db, limit=2, offset=4)
        assert len(policies3) == 1


# ---------------------------------------------------------------------------
# get_policy
# ---------------------------------------------------------------------------


class TestGetPolicy:
    async def test_existing(self, db: AsyncSession):
        owner = await _make_agent(db)
        created = await create_policy(
            db, name="find-me", policy_type="jurisdiction",
            rules_json='{}', owner_id=owner.id,
        )
        found = await get_policy(db, created.id)
        assert found is not None
        assert found.name == "find-me"

    async def test_missing_returns_none(self, db: AsyncSession):
        result = await get_policy(db, _id())
        assert result is None


# ---------------------------------------------------------------------------
# check_jurisdiction_policy (pure function)
# ---------------------------------------------------------------------------


class TestCheckJurisdictionPolicy:
    def test_all_allowed(self):
        agents = [
            {"id": "a1", "name": "Agent1", "jurisdictions": ["US", "EU"]},
            {"id": "a2", "name": "Agent2", "jurisdictions": ["US"]},
        ]
        result = check_jurisdiction_policy(agents, ["US", "EU"])
        assert result["passed"] is True
        assert result["violations"] == []

    def test_disallowed_jurisdiction(self):
        agents = [
            {"id": "a1", "name": "Agent1", "jurisdictions": ["US", "CN"]},
        ]
        result = check_jurisdiction_policy(agents, ["US", "EU"])
        assert result["passed"] is False
        assert len(result["violations"]) == 1
        assert result["violations"][0]["agent_id"] == "a1"
        assert "CN" in result["violations"][0]["disallowed_jurisdictions"]

    def test_empty_jurisdictions_skipped(self):
        agents = [
            {"id": "a1", "name": "Agent1", "jurisdictions": []},
            {"id": "a2", "name": "Agent2"},  # no jurisdictions key
        ]
        result = check_jurisdiction_policy(agents, ["US"])
        assert result["passed"] is True

    def test_multiple_violations(self):
        agents = [
            {"id": "a1", "name": "Agent1", "jurisdictions": ["CN"]},
            {"id": "a2", "name": "Agent2", "jurisdictions": ["RU"]},
        ]
        result = check_jurisdiction_policy(agents, ["US"])
        assert result["passed"] is False
        assert len(result["violations"]) == 2

    def test_empty_agent_list(self):
        result = check_jurisdiction_policy([], ["US"])
        assert result["passed"] is True
        assert result["violations"] == []

    def test_missing_agent_id_defaults_unknown(self):
        agents = [{"jurisdictions": ["CN"]}]
        result = check_jurisdiction_policy(agents, ["US"])
        assert result["violations"][0]["agent_id"] == "unknown"
        assert result["violations"][0]["agent_name"] == "unknown"


# ---------------------------------------------------------------------------
# check_cost_policy (pure function)
# ---------------------------------------------------------------------------


class TestCheckCostPolicy:
    def test_within_budget(self):
        result = check_cost_policy(10.0, 50.0)
        assert result["passed"] is True
        assert result["estimated_cost"] == 10.0
        assert result["max_allowed"] == 50.0

    def test_exceeds_budget(self):
        result = check_cost_policy(100.0, 50.0)
        assert result["passed"] is False

    def test_exactly_at_budget(self):
        result = check_cost_policy(50.0, 50.0)
        assert result["passed"] is True

    def test_decimal_inputs(self):
        result = check_cost_policy(Decimal("9.99"), Decimal("10.00"))
        assert result["passed"] is True

    def test_zero_cost(self):
        result = check_cost_policy(0, 100)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# evaluate_chain_policies
# ---------------------------------------------------------------------------


class TestEvaluateChainPolicies:
    async def test_missing_template_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Chain template not found"):
            await evaluate_chain_policies(db, _id(), [])

    async def test_evaluate_jurisdiction_policy_passes(self, db: AsyncSession):
        """Agent with allowed jurisdictions passes the policy."""
        card_json = json.dumps({
            "capabilities": {
                "extensions": [{
                    "params": {"jurisdictions": ["US", "EU"]},
                }],
            },
        })
        agent = await _make_agent(db, name="us-agent", agent_card_json=card_json)

        graph = {"nodes": {
            "n1": {"type": "agent_call", "config": {"agent_id": agent.id}},
        }, "edges": []}
        template = await _make_template(db, json.dumps(graph), author_id=agent.id)

        owner = await _make_agent(db, name="policy-owner")
        rules = json.dumps({"allowed_jurisdictions": ["US", "EU"]})
        policy = await create_policy(
            db, name="us-eu-only", policy_type="jurisdiction",
            rules_json=rules, owner_id=owner.id,
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is True
        assert report["chain_template_id"] == template.id
        assert len(report["policy_results"]) == 1
        assert report["policy_results"][0]["passed"] is True

    async def test_evaluate_jurisdiction_policy_blocks(self, db: AsyncSession):
        """Agent with disallowed jurisdictions triggers a block."""
        card_json = json.dumps({
            "capabilities": {
                "extensions": [{
                    "params": {"jurisdictions": ["CN"]},
                }],
            },
        })
        agent = await _make_agent(db, name="cn-agent", agent_card_json=card_json)

        graph = {"nodes": {
            "n1": {"type": "agent_call", "config": {"agent_id": agent.id}},
        }, "edges": []}
        template = await _make_template(db, json.dumps(graph))

        owner = await _make_agent(db, name="policy-owner-2")
        rules = json.dumps({"allowed_jurisdictions": ["US"]})
        policy = await create_policy(
            db, name="us-only", policy_type="jurisdiction",
            rules_json=rules, owner_id=owner.id,
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is False
        assert len(report["block_reasons"]) == 1
        assert "us-only" in report["block_reasons"][0]

    async def test_evaluate_cost_limit_passes(self, db: AsyncSession):
        agent = await _make_agent(db)
        graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
        template = await _make_template(
            db, json.dumps(graph), max_budget_usd=Decimal("10.00"),
        )

        owner = await _make_agent(db, name="cost-owner")
        rules = json.dumps({"max_cost_usd": 50})
        policy = await create_policy(
            db, name="budget-cap", policy_type="cost_limit",
            rules_json=rules, owner_id=owner.id,
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is True
        assert report["policy_results"][0]["passed"] is True
        assert report["policy_results"][0]["details"]["estimated_cost"] == 10.0

    async def test_evaluate_cost_limit_fails(self, db: AsyncSession):
        agent = await _make_agent(db)
        graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
        template = await _make_template(
            db, json.dumps(graph), max_budget_usd=Decimal("100.00"),
        )

        owner = await _make_agent(db, name="cost-owner-2")
        rules = json.dumps({"max_cost_usd": 50})
        policy = await create_policy(
            db, name="budget-cap-strict", policy_type="cost_limit",
            rules_json=rules, owner_id=owner.id,
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is False
        assert report["policy_results"][0]["passed"] is False

    async def test_evaluate_cost_uses_avg_cost_when_no_budget(self, db: AsyncSession):
        """Falls back to avg_cost_usd when max_budget_usd is None."""
        agent = await _make_agent(db)
        graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
        template = await _make_template(
            db, json.dumps(graph),
            max_budget_usd=None, avg_cost_usd=Decimal("5.00"),
        )

        owner = await _make_agent(db, name="cost-fallback-owner")
        rules = json.dumps({"max_cost_usd": 10})
        policy = await create_policy(
            db, name="budget-fallback", policy_type="cost_limit",
            rules_json=rules, owner_id=owner.id,
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["policy_results"][0]["passed"] is True
        assert report["policy_results"][0]["details"]["estimated_cost"] == 5.0

    async def test_missing_policy_marks_not_found(self, db: AsyncSession):
        agent = await _make_agent(db)
        graph = {"nodes": {}, "edges": []}
        template = await _make_template(db, json.dumps(graph))

        report = await evaluate_chain_policies(db, template.id, [_id()])
        assert report["overall_passed"] is False
        assert report["policy_results"][0]["status"] == "not_found"

    async def test_disabled_policy_is_skipped(self, db: AsyncSession):
        agent = await _make_agent(db)
        graph = {"nodes": {}, "edges": []}
        template = await _make_template(db, json.dumps(graph))

        owner = await _make_agent(db, name="disabled-owner")
        policy = await create_policy(
            db, name="disabled-p", policy_type="jurisdiction",
            rules_json='{}', owner_id=owner.id,
        )
        policy.status = "disabled"
        await db.commit()

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is True
        assert report["policy_results"][0]["status"] == "disabled"
        assert report["policy_results"][0]["passed"] is True

    async def test_warn_enforcement_does_not_block(self, db: AsyncSession):
        """A failed policy with enforcement='warn' should not set overall_passed to False."""
        card_json = json.dumps({
            "capabilities": {"extensions": [{"params": {"jurisdictions": ["CN"]}}]},
        })
        agent = await _make_agent(db, name="warn-agent", agent_card_json=card_json)
        graph = {"nodes": {
            "n1": {"type": "agent_call", "config": {"agent_id": agent.id}},
        }, "edges": []}
        template = await _make_template(db, json.dumps(graph))

        owner = await _make_agent(db, name="warn-owner")
        rules = json.dumps({"allowed_jurisdictions": ["US"]})
        policy = await create_policy(
            db, name="warn-only", policy_type="jurisdiction",
            rules_json=rules, owner_id=owner.id, enforcement="warn",
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        # The individual policy fails but enforcement is warn, not block
        assert report["policy_results"][0]["passed"] is False
        assert report["overall_passed"] is True
        assert report["block_reasons"] == []

    async def test_data_residency_policy_evaluation(self, db: AsyncSession):
        card_json = json.dumps({
            "capabilities": {"extensions": [{"params": {"jurisdictions": ["us-east-1"]}}]},
        })
        agent = await _make_agent(db, name="residency-agent", agent_card_json=card_json)
        graph = {"nodes": {
            "n1": {"type": "agent_call", "config": {"agent_id": agent.id}},
        }, "edges": []}
        template = await _make_template(db, json.dumps(graph))

        owner = await _make_agent(db, name="residency-owner")
        rules = json.dumps({"allowed_regions": ["eu-west-1"]})
        policy = await create_policy(
            db, name="eu-residency", policy_type="data_residency",
            rules_json=rules, owner_id=owner.id,
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is False
        assert report["policy_results"][0]["passed"] is False

    async def test_template_with_no_agent_nodes(self, db: AsyncSession):
        """Graph with no agent_call nodes means no agents to check."""
        graph = {"nodes": {"n1": {"type": "decision", "config": {}}}, "edges": []}
        template = await _make_template(db, json.dumps(graph))

        owner = await _make_agent(db, name="no-agents-owner")
        rules = json.dumps({"allowed_jurisdictions": ["US"]})
        policy = await create_policy(
            db, name="empty-check", policy_type="jurisdiction",
            rules_json=rules, owner_id=owner.id,
        )

        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is True

    async def test_multiple_policies_mixed_results(self, db: AsyncSession):
        """One policy passes, another blocks -- overall is blocked."""
        card_json = json.dumps({
            "capabilities": {"extensions": [{"params": {"jurisdictions": ["US"]}}]},
        })
        agent = await _make_agent(db, name="multi-agent", agent_card_json=card_json)
        graph = {"nodes": {
            "n1": {"type": "agent_call", "config": {"agent_id": agent.id}},
        }, "edges": []}
        template = await _make_template(
            db, json.dumps(graph), max_budget_usd=Decimal("200.00"),
        )

        owner = await _make_agent(db, name="multi-owner")

        # Jurisdiction passes
        j_policy = await create_policy(
            db, name="j-pass", policy_type="jurisdiction",
            rules_json=json.dumps({"allowed_jurisdictions": ["US"]}),
            owner_id=owner.id,
        )
        # Cost limit blocks
        c_policy = await create_policy(
            db, name="c-block", policy_type="cost_limit",
            rules_json=json.dumps({"max_cost_usd": 50}),
            owner_id=owner.id,
        )

        report = await evaluate_chain_policies(
            db, template.id, [j_policy.id, c_policy.id],
        )
        assert report["overall_passed"] is False
        assert len(report["policy_results"]) == 2
        # Jurisdiction should pass
        j_result = next(r for r in report["policy_results"] if r["policy_type"] == "jurisdiction")
        assert j_result["passed"] is True
        # Cost should fail
        c_result = next(r for r in report["policy_results"] if r["policy_type"] == "cost_limit")
        assert c_result["passed"] is False

    async def test_agent_with_bad_card_json_handled(self, db: AsyncSession):
        """Agent with unparseable agent_card_json should not crash evaluation."""
        agent = await _make_agent(db, name="bad-card", agent_card_json="not-json")
        graph = {"nodes": {
            "n1": {"type": "agent_call", "config": {"agent_id": agent.id}},
        }, "edges": []}
        template = await _make_template(db, json.dumps(graph))

        owner = await _make_agent(db, name="bad-card-owner")
        rules = json.dumps({"allowed_jurisdictions": ["US"]})
        policy = await create_policy(
            db, name="bad-card-check", policy_type="jurisdiction",
            rules_json=rules, owner_id=owner.id,
        )

        # Should not raise; agent with bad JSON gets empty jurisdictions
        report = await evaluate_chain_policies(db, template.id, [policy.id])
        assert report["overall_passed"] is True
