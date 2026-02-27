"""Tests for ChainTemplate and ChainExecution models.

Covers: creation, defaults, field types, constraints, queries.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from marketplace.models.chain_template import ChainExecution, ChainTemplate, utcnow


def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# ChainTemplate
# ---------------------------------------------------------------------------


class TestChainTemplateModel:
    async def test_create_with_defaults(self, db):
        template = ChainTemplate(
            id=_uid(),
            name="Research Pipeline",
            graph_json='{"nodes": [], "edges": []}',
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)

        assert template.name == "Research Pipeline"
        assert template.description == ""
        assert template.category == "general"
        assert template.version == 1
        assert template.status == "draft"
        assert template.tags_json == "[]"
        assert template.required_capabilities_json == "[]"
        assert template.execution_count == 0
        assert template.avg_cost_usd == Decimal("0")
        assert template.avg_duration_ms == 0
        assert template.trust_score == 0
        assert template.max_budget_usd is None
        assert template.created_at is not None
        assert template.updated_at is not None

    async def test_create_with_all_fields(self, db, make_agent):
        agent, _ = await make_agent()
        template = ChainTemplate(
            id=_uid(),
            name="Advanced Analysis Chain",
            description="Multi-stage data analysis pipeline",
            category="analytics",
            graph_json='{"nodes": [{"id": "n1", "type": "tool"}], "edges": []}',
            author_id=agent.id,
            version=3,
            status="active",
            tags_json='["analytics", "ml", "data"]',
            required_capabilities_json='["web_search", "nlp"]',
            execution_count=150,
            avg_cost_usd=Decimal("0.045000"),
            avg_duration_ms=3200,
            trust_score=87,
            max_budget_usd=Decimal("5.0000"),
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)

        assert template.category == "analytics"
        assert template.author_id == agent.id
        assert template.version == 3
        assert template.status == "active"
        assert template.execution_count == 150
        assert template.trust_score == 87
        assert template.max_budget_usd == Decimal("5.0000")

    async def test_forked_template(self, db, make_agent):
        agent, _ = await make_agent()
        parent = ChainTemplate(
            id=_uid(),
            name="Original Template",
            graph_json='{"nodes": []}',
            author_id=agent.id,
        )
        db.add(parent)
        await db.commit()

        fork = ChainTemplate(
            id=_uid(),
            name="Forked Template",
            graph_json='{"nodes": []}',
            author_id=agent.id,
            forked_from_id=parent.id,
        )
        db.add(fork)
        await db.commit()
        await db.refresh(fork)

        assert fork.forked_from_id == parent.id

    async def test_status_values(self, db):
        for status in ("draft", "active", "archived"):
            template = ChainTemplate(
                id=_uid(),
                name=f"Template {status}",
                graph_json="{}",
                status=status,
            )
            db.add(template)
        await db.commit()

        result = await db.execute(
            select(ChainTemplate).where(ChainTemplate.status == "active")
        )
        active = list(result.scalars().all())
        assert len(active) == 1

    async def test_query_by_category(self, db):
        for cat in ("general", "analytics", "analytics", "security"):
            template = ChainTemplate(
                id=_uid(),
                name=f"Template {cat}",
                graph_json="{}",
                category=cat,
            )
            db.add(template)
        await db.commit()

        result = await db.execute(
            select(ChainTemplate).where(ChainTemplate.category == "analytics")
        )
        found = list(result.scalars().all())
        assert len(found) == 2

    async def test_query_by_author(self, db, make_agent):
        agent1, _ = await make_agent()
        agent2, _ = await make_agent()

        for i in range(3):
            template = ChainTemplate(
                id=_uid(),
                name=f"Agent1 Template {i}",
                graph_json="{}",
                author_id=agent1.id,
            )
            db.add(template)

        template_other = ChainTemplate(
            id=_uid(),
            name="Agent2 Template",
            graph_json="{}",
            author_id=agent2.id,
        )
        db.add(template_other)
        await db.commit()

        result = await db.execute(
            select(ChainTemplate).where(ChainTemplate.author_id == agent1.id)
        )
        found = list(result.scalars().all())
        assert len(found) == 3

    async def test_trust_score_range(self, db):
        """trust_score should support 0-100."""
        for score in (0, 50, 100):
            template = ChainTemplate(
                id=_uid(),
                name=f"Score {score}",
                graph_json="{}",
                trust_score=score,
            )
            db.add(template)
        await db.commit()

        result = await db.execute(
            select(ChainTemplate).where(ChainTemplate.trust_score >= 50)
        )
        found = list(result.scalars().all())
        assert len(found) == 2


# ---------------------------------------------------------------------------
# ChainExecution
# ---------------------------------------------------------------------------


class TestChainExecutionModel:
    async def test_create_with_defaults(self, db):
        template = ChainTemplate(
            id=_uid(),
            name="Test Template",
            graph_json="{}",
        )
        db.add(template)
        await db.commit()

        execution = ChainExecution(
            id=_uid(),
            chain_template_id=template.id,
            initiated_by="agent-1",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        assert execution.status == "pending"
        assert execution.input_json == "{}"
        assert execution.output_json == "{}"
        assert execution.total_cost_usd == Decimal("0")
        assert execution.participant_agents_json == "[]"
        assert execution.provenance_hash is None
        assert execution.idempotency_key is None
        assert execution.completed_at is None
        assert execution.created_at is not None

    async def test_completed_execution(self, db):
        template = ChainTemplate(
            id=_uid(),
            name="Test Template",
            graph_json="{}",
        )
        db.add(template)
        await db.commit()

        execution = ChainExecution(
            id=_uid(),
            chain_template_id=template.id,
            initiated_by="agent-1",
            status="completed",
            input_json='{"query": "test"}',
            output_json='{"result": "success"}',
            total_cost_usd=Decimal("0.025000"),
            participant_agents_json='["agent-1", "agent-2"]',
            provenance_hash="abc123" + "0" * 58,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        assert execution.status == "completed"
        assert execution.total_cost_usd == Decimal("0.025000")
        assert execution.completed_at is not None

    async def test_idempotency_key_unique(self, db):
        template = ChainTemplate(
            id=_uid(),
            name="Template",
            graph_json="{}",
        )
        db.add(template)
        await db.commit()

        key = "idem-" + _uid()
        exec1 = ChainExecution(
            id=_uid(),
            chain_template_id=template.id,
            initiated_by="a1",
            idempotency_key=key,
        )
        db.add(exec1)
        await db.commit()

        exec2 = ChainExecution(
            id=_uid(),
            chain_template_id=template.id,
            initiated_by="a2",
            idempotency_key=key,
        )
        db.add(exec2)
        with pytest.raises(Exception):  # unique constraint violation
            await db.commit()
        await db.rollback()

    async def test_query_by_template(self, db):
        template = ChainTemplate(
            id=_uid(),
            name="Template",
            graph_json="{}",
        )
        db.add(template)
        await db.commit()

        for _ in range(3):
            execution = ChainExecution(
                id=_uid(),
                chain_template_id=template.id,
                initiated_by="agent-1",
            )
            db.add(execution)
        await db.commit()

        result = await db.execute(
            select(ChainExecution).where(ChainExecution.chain_template_id == template.id)
        )
        found = list(result.scalars().all())
        assert len(found) == 3

    async def test_query_by_status(self, db):
        template = ChainTemplate(
            id=_uid(),
            name="Template",
            graph_json="{}",
        )
        db.add(template)
        await db.commit()

        for status in ("pending", "running", "completed", "failed", "pending"):
            execution = ChainExecution(
                id=_uid(),
                chain_template_id=template.id,
                initiated_by="agent-1",
                status=status,
            )
            db.add(execution)
        await db.commit()

        result = await db.execute(
            select(ChainExecution).where(ChainExecution.status == "pending")
        )
        found = list(result.scalars().all())
        assert len(found) == 2
