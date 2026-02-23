"""Unit tests for the chain_analytics_service module."""

import json
import uuid
from decimal import Decimal

import pytest

from marketplace.models.chain_provenance import ChainProvenanceEntry
from marketplace.models.chain_template import ChainExecution, ChainTemplate
from marketplace.models.workflow import WorkflowDefinition
from marketplace.services import chain_analytics_service


def _new_id() -> str:
    return str(uuid.uuid4())


async def _seed_template(db, agent_id, name="test-chain", execution_count=0):
    """Create a workflow + chain template."""
    wf = WorkflowDefinition(
        id=_new_id(),
        name=f"wf-{name}",
        graph_json=json.dumps({
            "nodes": {
                "n0": {"type": "agent_call", "config": {"agent_id": agent_id}}
            },
            "edges": [],
        }),
        owner_id=agent_id,
    )
    db.add(wf)
    await db.commit()

    tmpl = ChainTemplate(
        id=_new_id(),
        name=name,
        workflow_id=wf.id,
        graph_json=wf.graph_json,
        author_id=agent_id,
        status="active",
        execution_count=execution_count,
    )
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


async def _seed_execution(db, template_id, initiated_by, status="completed", cost=Decimal("0.10")):
    """Create a chain execution."""
    ex = ChainExecution(
        id=_new_id(),
        chain_template_id=template_id,
        initiated_by=initiated_by,
        status=status,
        total_cost_usd=cost,
        participant_agents_json=json.dumps([initiated_by]),
    )
    db.add(ex)
    await db.commit()
    await db.refresh(ex)
    return ex


# ---------------------------------------------------------------------------
# get_chain_performance tests
# ---------------------------------------------------------------------------


class TestGetChainPerformance:
    @pytest.mark.asyncio
    async def test_no_executions(self, db, make_agent):
        agent, _ = await make_agent()
        tmpl = await _seed_template(db, agent.id)

        perf = await chain_analytics_service.get_chain_performance(db, tmpl.id)
        assert perf["execution_count"] == 0
        assert perf["success_rate"] == 0.0
        assert perf["avg_cost_usd"] == 0.0
        assert perf["unique_initiators"] == 0

    @pytest.mark.asyncio
    async def test_with_executions(self, db, make_agent):
        agent, _ = await make_agent()
        tmpl = await _seed_template(db, agent.id)

        await _seed_execution(db, tmpl.id, agent.id, "completed", Decimal("0.20"))
        await _seed_execution(db, tmpl.id, agent.id, "completed", Decimal("0.40"))
        await _seed_execution(db, tmpl.id, agent.id, "failed", Decimal("0"))

        perf = await chain_analytics_service.get_chain_performance(db, tmpl.id)
        assert perf["execution_count"] == 3
        assert perf["success_rate"] == pytest.approx(66.67, abs=0.01)
        assert perf["avg_cost_usd"] == pytest.approx(0.30, abs=0.01)
        assert perf["unique_initiators"] == 1

    @pytest.mark.asyncio
    async def test_multiple_initiators(self, db, make_agent):
        agent1, _ = await make_agent()
        agent2, _ = await make_agent()
        tmpl = await _seed_template(db, agent1.id)

        await _seed_execution(db, tmpl.id, agent1.id)
        await _seed_execution(db, tmpl.id, agent2.id)

        perf = await chain_analytics_service.get_chain_performance(db, tmpl.id)
        assert perf["unique_initiators"] == 2


# ---------------------------------------------------------------------------
# get_popular_chains tests
# ---------------------------------------------------------------------------


class TestGetPopularChains:
    @pytest.mark.asyncio
    async def test_ordered_by_execution_count(self, db, make_agent):
        agent, _ = await make_agent()

        await _seed_template(db, agent.id, "low-usage", execution_count=5)
        await _seed_template(db, agent.id, "high-usage", execution_count=50)
        await _seed_template(db, agent.id, "mid-usage", execution_count=20)

        popular = await chain_analytics_service.get_popular_chains(db, limit=3)
        assert len(popular) == 3
        assert popular[0]["execution_count"] == 50
        assert popular[1]["execution_count"] == 20
        assert popular[2]["execution_count"] == 5

    @pytest.mark.asyncio
    async def test_filter_by_category(self, db, make_agent):
        agent, _ = await make_agent()

        tmpl1 = await _seed_template(db, agent.id, "chain-a", execution_count=10)
        tmpl1.category = "compliance"
        await db.commit()

        tmpl2 = await _seed_template(db, agent.id, "chain-b", execution_count=20)
        tmpl2.category = "analysis"
        await db.commit()

        popular = await chain_analytics_service.get_popular_chains(
            db, category="compliance"
        )
        assert len(popular) == 1
        assert popular[0]["category"] == "compliance"

    @pytest.mark.asyncio
    async def test_empty_results(self, db):
        popular = await chain_analytics_service.get_popular_chains(db)
        assert popular == []


# ---------------------------------------------------------------------------
# get_agent_chain_stats tests
# ---------------------------------------------------------------------------


class TestGetAgentChainStats:
    @pytest.mark.asyncio
    async def test_no_activity(self, db, make_agent):
        agent, _ = await make_agent()
        stats = await chain_analytics_service.get_agent_chain_stats(db, agent.id)
        assert stats["chains_authored"] == 0
        assert stats["executions_as_participant"] == 0
        assert stats["executions_initiated"] == 0
        assert stats["total_earnings_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_with_authored_chains(self, db, make_agent):
        agent, _ = await make_agent()
        await _seed_template(db, agent.id, "my-chain-1")
        await _seed_template(db, agent.id, "my-chain-2")

        stats = await chain_analytics_service.get_agent_chain_stats(db, agent.id)
        assert stats["chains_authored"] == 2

    @pytest.mark.asyncio
    async def test_with_initiated_executions(self, db, make_agent):
        agent, _ = await make_agent()
        tmpl = await _seed_template(db, agent.id)

        await _seed_execution(db, tmpl.id, agent.id)
        await _seed_execution(db, tmpl.id, agent.id)

        stats = await chain_analytics_service.get_agent_chain_stats(db, agent.id)
        assert stats["executions_initiated"] == 2
        assert stats["executions_as_participant"] == 2

    @pytest.mark.asyncio
    async def test_earnings_from_provenance(self, db, make_agent):
        agent, _ = await make_agent()
        tmpl = await _seed_template(db, agent.id)
        ex = await _seed_execution(db, tmpl.id, agent.id)

        # Add provenance entries with cost
        entry = ChainProvenanceEntry(
            chain_execution_id=ex.id,
            node_id="n0",
            event_type="node_completed",
            node_type="agent_call",
            agent_id=agent.id,
            cost_usd=Decimal("0.25"),
            status="completed",
        )
        db.add(entry)
        await db.commit()

        stats = await chain_analytics_service.get_agent_chain_stats(db, agent.id)
        assert stats["total_earnings_usd"] == pytest.approx(0.25)
