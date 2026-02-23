"""Unit tests for the chain_provenance_service module."""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from marketplace.models.chain_provenance import ChainProvenanceEntry
from marketplace.models.chain_template import ChainExecution, ChainTemplate
from marketplace.models.workflow import WorkflowDefinition
from marketplace.services import chain_provenance_service
from marketplace.services.chain_provenance_service import make_provenance_callback


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Setup helper: seed a minimal chain execution for provenance tests
# ---------------------------------------------------------------------------


async def _seed_chain_execution(db, make_agent):
    """Create an agent, template, and execution for testing provenance."""
    agent, token = await make_agent()

    workflow = WorkflowDefinition(
        id=_new_id(),
        name="test-wf",
        graph_json=json.dumps({
            "nodes": {
                "n0": {"type": "agent_call", "config": {"agent_id": agent.id}}
            },
            "edges": [],
        }),
        owner_id=agent.id,
    )
    db.add(workflow)
    await db.commit()

    template = ChainTemplate(
        id=_new_id(),
        name="test-chain",
        workflow_id=workflow.id,
        graph_json=workflow.graph_json,
        author_id=agent.id,
        status="active",
    )
    db.add(template)
    await db.commit()

    execution = ChainExecution(
        id=_new_id(),
        chain_template_id=template.id,
        initiated_by=agent.id,
        status="completed",
        input_json="{}",
        output_json="{}",
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    return agent, template, execution


# ---------------------------------------------------------------------------
# make_provenance_callback tests
#
# The callback creates its own DB session via async_session. In tests,
# we monkeypatch async_session to use the test session factory so the
# callback writes to the same in-memory database as the test fixture.
# ---------------------------------------------------------------------------


class TestMakeProvenanceCallback:
    @pytest.mark.asyncio
    async def test_callback_creates_started_entry(self, db, make_agent):
        from marketplace.tests.conftest import _test_sessionmaker

        agent, template, execution = await _seed_chain_execution(db, make_agent)

        with patch(
            "marketplace.database.async_session",
            new=_test_sessionmaker,
        ):
            callback = make_provenance_callback(execution.id)
            await callback("node_started", "n0", "agent_call", agent_id=agent.id)

        entries, total = await chain_provenance_service.get_provenance_entries(
            db, execution.id
        )
        assert total >= 1
        started = [e for e in entries if e.event_type == "node_started"]
        assert len(started) >= 1
        assert started[0].node_id == "n0"
        assert started[0].status == "running"

    @pytest.mark.asyncio
    async def test_callback_creates_completed_entry(self, db, make_agent):
        from marketplace.tests.conftest import _test_sessionmaker

        agent, template, execution = await _seed_chain_execution(db, make_agent)

        with patch(
            "marketplace.database.async_session",
            new=_test_sessionmaker,
        ):
            callback = make_provenance_callback(execution.id)
            await callback(
                "node_completed", "n0", "agent_call",
                agent_id=agent.id,
                input_json='{"query": "test"}',
                output_json='{"result": "ok"}',
                cost_usd=Decimal("0.05"),
                duration_ms=150,
            )

        entries, total = await chain_provenance_service.get_provenance_entries(
            db, execution.id, event_type="node_completed"
        )
        assert total >= 1
        completed = entries[0]
        assert completed.status == "completed"
        assert completed.duration_ms == 150
        assert completed.input_hash_sha256 is not None
        assert completed.output_hash_sha256 is not None

    @pytest.mark.asyncio
    async def test_callback_creates_failed_entry(self, db, make_agent):
        from marketplace.tests.conftest import _test_sessionmaker

        agent, template, execution = await _seed_chain_execution(db, make_agent)

        with patch(
            "marketplace.database.async_session",
            new=_test_sessionmaker,
        ):
            callback = make_provenance_callback(execution.id)
            await callback(
                "node_failed", "n0", "agent_call",
                agent_id=agent.id,
                error_message="Connection timeout",
            )

        entries, _ = await chain_provenance_service.get_provenance_entries(
            db, execution.id, event_type="node_failed"
        )
        assert len(entries) >= 1
        assert entries[0].error_message == "Connection timeout"
        assert entries[0].status == "failed"


# ---------------------------------------------------------------------------
# get_provenance_entries tests
# ---------------------------------------------------------------------------


class TestGetProvenanceEntries:
    @pytest.mark.asyncio
    async def test_empty_when_no_entries(self, db, make_agent):
        _, _, execution = await _seed_chain_execution(db, make_agent)
        entries, total = await chain_provenance_service.get_provenance_entries(
            db, execution.id
        )
        assert entries == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_filter_by_event_type(self, db, make_agent):
        agent, _, execution = await _seed_chain_execution(db, make_agent)

        # Insert entries directly
        for event_type in ["node_started", "node_completed", "node_failed"]:
            entry = ChainProvenanceEntry(
                chain_execution_id=execution.id,
                node_id="n0",
                event_type=event_type,
                node_type="agent_call",
                status=event_type.split("_")[1],
            )
            db.add(entry)
        await db.commit()

        # Filter for completed only
        entries, total = await chain_provenance_service.get_provenance_entries(
            db, execution.id, event_type="node_completed"
        )
        assert total == 1
        assert entries[0].event_type == "node_completed"

    @pytest.mark.asyncio
    async def test_pagination(self, db, make_agent):
        _, _, execution = await _seed_chain_execution(db, make_agent)

        for i in range(5):
            entry = ChainProvenanceEntry(
                chain_execution_id=execution.id,
                node_id=f"n{i}",
                event_type="node_completed",
                node_type="agent_call",
                status="completed",
            )
            db.add(entry)
        await db.commit()

        entries, total = await chain_provenance_service.get_provenance_entries(
            db, execution.id, limit=2, offset=0
        )
        assert total == 5
        assert len(entries) == 2


# ---------------------------------------------------------------------------
# get_provenance_timeline tests
# ---------------------------------------------------------------------------


class TestGetProvenanceTimeline:
    @pytest.mark.asyncio
    async def test_timeline_ordered_by_timestamp(self, db, make_agent):
        _, _, execution = await _seed_chain_execution(db, make_agent)

        for i, event_type in enumerate(["node_started", "node_completed"]):
            entry = ChainProvenanceEntry(
                chain_execution_id=execution.id,
                node_id="n0",
                event_type=event_type,
                node_type="agent_call",
                status="running" if i == 0 else "completed",
                duration_ms=100 if i == 1 else None,
                cost_usd=Decimal("0.01") if i == 1 else Decimal("0"),
            )
            db.add(entry)
        await db.commit()

        timeline = await chain_provenance_service.get_provenance_timeline(
            db, execution.id
        )
        assert len(timeline) == 2
        assert timeline[0]["event_type"] == "node_started"
        assert timeline[1]["event_type"] == "node_completed"
        assert timeline[1]["duration_ms"] == 100

    @pytest.mark.asyncio
    async def test_timeline_empty_when_no_entries(self, db, make_agent):
        _, _, execution = await _seed_chain_execution(db, make_agent)
        timeline = await chain_provenance_service.get_provenance_timeline(
            db, execution.id
        )
        assert timeline == []
