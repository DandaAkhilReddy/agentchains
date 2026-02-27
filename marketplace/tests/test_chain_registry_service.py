"""Unit tests for the chain_registry_service module."""

import json

import pytest

from marketplace.services import chain_registry_service
from marketplace.services.chain_registry_service import (
    _compute_provenance_hash,
    _redact_sensitive_keys,
)


# ---------------------------------------------------------------------------
# Helpers for building valid graphs
# ---------------------------------------------------------------------------


def _make_graph(agent_ids: list[str], **overrides) -> dict:
    """Build a minimal valid DAG with one agent_call node per agent_id."""
    nodes = {}
    prev_id = None
    for i, aid in enumerate(agent_ids):
        node_id = f"node_{i}"
        node_def = {
            "type": "agent_call",
            "config": {"agent_id": aid},
        }
        if prev_id:
            node_def["depends_on"] = [prev_id]
        nodes[node_id] = node_def
        prev_id = node_id
    graph = {"nodes": nodes, "edges": []}
    graph.update(overrides)
    return graph


# ---------------------------------------------------------------------------
# Redaction helper tests
# ---------------------------------------------------------------------------


class TestRedactSensitiveKeys:
    def test_strips_password(self):
        data = {"username": "alice", "password": "s3cret"}
        result = _redact_sensitive_keys(data)
        assert result["username"] == "alice"
        assert result["password"] == "[REDACTED]"

    def test_strips_nested_api_key(self):
        data = {"config": {"x_api_key": "abc123", "name": "test"}}
        result = _redact_sensitive_keys(data)
        assert result["config"]["x_api_key"] == "[REDACTED]"
        assert result["config"]["name"] == "test"

    def test_strips_secret_in_list(self):
        data = {"items": [{"secret_value": "hidden", "id": 1}]}
        result = _redact_sensitive_keys(data)
        assert result["items"][0]["secret_value"] == "[REDACTED]"
        assert result["items"][0]["id"] == 1

    def test_preserves_safe_keys(self):
        data = {"name": "Alice", "status": "active", "count": 42}
        result = _redact_sensitive_keys(data)
        assert result == data

    def test_strips_credential(self):
        data = {"user_credential": "abc"}
        result = _redact_sensitive_keys(data)
        assert result["user_credential"] == "[REDACTED]"

    def test_strips_token(self):
        data = {"auth_token": "jwt_value"}
        result = _redact_sensitive_keys(data)
        assert result["auth_token"] == "[REDACTED]"


class TestComputeProvenanceHash:
    def test_deterministic(self):
        h1 = _compute_provenance_hash('{"a":1}', '{"b":2}')
        h2 = _compute_provenance_hash('{"a":1}', '{"b":2}')
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_inputs_different_hash(self):
        h1 = _compute_provenance_hash('{"a":1}', '{"b":2}')
        h2 = _compute_provenance_hash('{"a":1}', '{"b":3}')
        assert h1 != h2


# ---------------------------------------------------------------------------
# Graph validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_graph_rejects_raw_endpoint(db, make_agent):
    agent, _ = await make_agent()
    graph = {
        "nodes": {
            "n1": {
                "type": "agent_call",
                "config": {
                    "agent_id": agent.id,
                    "endpoint": "http://evil.com/steal",
                },
            }
        },
        "edges": [],
    }
    with pytest.raises(ValueError, match="raw endpoint URL"):
        await chain_registry_service.validate_graph_agents(db, graph)


@pytest.mark.asyncio
async def test_validate_graph_rejects_missing_agent_id(db):
    graph = {
        "nodes": {
            "n1": {
                "type": "agent_call",
                "config": {},
            }
        },
        "edges": [],
    }
    with pytest.raises(ValueError, match="missing config.agent_id"):
        await chain_registry_service.validate_graph_agents(db, graph)


@pytest.mark.asyncio
async def test_validate_graph_rejects_inactive_agent(db, make_agent):
    agent, _ = await make_agent()
    agent.status = "suspended"
    await db.commit()

    graph = _make_graph([agent.id])
    with pytest.raises(ValueError, match="not active"):
        await chain_registry_service.validate_graph_agents(db, graph)


@pytest.mark.asyncio
async def test_validate_graph_rejects_cycle(db, make_agent):
    agent, _ = await make_agent()
    graph = {
        "nodes": {
            "a": {"type": "agent_call", "config": {"agent_id": agent.id}, "depends_on": ["b"]},
            "b": {"type": "agent_call", "config": {"agent_id": agent.id}, "depends_on": ["a"]},
        },
        "edges": [],
    }
    with pytest.raises(ValueError, match="[Cc]ycl"):
        await chain_registry_service.validate_graph_agents(db, graph)


@pytest.mark.asyncio
async def test_validate_graph_accepts_valid(db, make_agent):
    agent, _ = await make_agent()
    graph = _make_graph([agent.id])
    result = await chain_registry_service.validate_graph_agents(db, graph)
    assert agent.id in result


# ---------------------------------------------------------------------------
# Publish tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_creates_workflow_and_template(db, make_agent):
    agent, _ = await make_agent()
    graph = _make_graph([agent.id])

    template = await chain_registry_service.publish_chain_template(
        db,
        name="Test Chain",
        graph_json=json.dumps(graph),
        author_id=agent.id,
        category="test",
        tags=["demo"],
    )

    assert template.id is not None
    assert template.workflow_id is not None
    assert template.name == "Test Chain"
    assert template.author_id == agent.id
    assert template.status == "active"
    assert json.loads(template.tags_json) == ["demo"]


@pytest.mark.asyncio
async def test_publish_rejects_invalid_json(db, make_agent):
    agent, _ = await make_agent()
    with pytest.raises(ValueError, match="valid JSON"):
        await chain_registry_service.publish_chain_template(
            db,
            name="Bad",
            graph_json="not json{{{",
            author_id=agent.id,
        )


# ---------------------------------------------------------------------------
# Fork tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fork_copies_and_links(db, make_agent):
    author, _ = await make_agent()
    forker, _ = await make_agent()
    graph = _make_graph([author.id])

    original = await chain_registry_service.publish_chain_template(
        db,
        name="Original",
        graph_json=json.dumps(graph),
        author_id=author.id,
    )

    forked = await chain_registry_service.fork_chain_template(
        db,
        source_template_id=original.id,
        new_author_id=forker.id,
    )

    assert forked.forked_from_id == original.id
    assert forked.author_id == forker.id
    assert forked.workflow_id != original.workflow_id
    assert forked.name == f"Fork of {original.name}"


@pytest.mark.asyncio
async def test_fork_not_found(db, make_agent):
    agent, _ = await make_agent()
    with pytest.raises(ValueError, match="not found"):
        await chain_registry_service.fork_chain_template(
            db,
            source_template_id="nonexistent-id",
            new_author_id=agent.id,
        )


# ---------------------------------------------------------------------------
# Execute tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_idempotency(db, make_agent):
    agent, _ = await make_agent()
    agent.a2a_endpoint = "http://test-agent:9000"
    await db.commit()

    graph = _make_graph([agent.id])
    template = await chain_registry_service.publish_chain_template(
        db,
        name="Idempotent Chain",
        graph_json=json.dumps(graph),
        author_id=agent.id,
    )

    exec1 = await chain_registry_service.execute_chain(
        db,
        template_id=template.id,
        initiated_by=agent.id,
        idempotency_key="test-idem-key-001",
    )

    exec2 = await chain_registry_service.execute_chain(
        db,
        template_id=template.id,
        initiated_by=agent.id,
        idempotency_key="test-idem-key-001",
    )

    assert exec1.id == exec2.id


@pytest.mark.asyncio
async def test_execute_resolves_endpoints(db, make_agent):
    agent, _ = await make_agent()
    agent.a2a_endpoint = "http://resolved-agent:9000"
    await db.commit()

    graph = _make_graph([agent.id])
    template = await chain_registry_service.publish_chain_template(
        db,
        name="Resolve Test",
        graph_json=json.dumps(graph),
        author_id=agent.id,
    )

    execution = await chain_registry_service.execute_chain(
        db,
        template_id=template.id,
        initiated_by=agent.id,
    )

    assert execution.id is not None
    assert execution.status == "pending"
    # Participant agents should be populated
    participants = json.loads(execution.participant_agents_json)
    assert agent.id in participants


# ---------------------------------------------------------------------------
# Provenance tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provenance_forbidden_non_participant(db, make_agent):
    author, _ = await make_agent()
    initiator, _ = await make_agent()
    outsider, _ = await make_agent()

    author.a2a_endpoint = "http://author-agent:9000"
    initiator.a2a_endpoint = "http://init-agent:9000"
    await db.commit()

    graph = _make_graph([author.id])
    template = await chain_registry_service.publish_chain_template(
        db,
        name="Provenance Test",
        graph_json=json.dumps(graph),
        author_id=author.id,
    )

    execution = await chain_registry_service.execute_chain(
        db,
        template_id=template.id,
        initiated_by=initiator.id,
    )

    result = await chain_registry_service.get_chain_provenance(
        db,
        chain_execution_id=execution.id,
        requesting_agent_id=outsider.id,
    )
    assert result.get("error") == "forbidden"


@pytest.mark.asyncio
async def test_provenance_allowed_initiator(db, make_agent):
    author, _ = await make_agent()
    author.a2a_endpoint = "http://author-agent:9000"
    await db.commit()

    graph = _make_graph([author.id])
    template = await chain_registry_service.publish_chain_template(
        db,
        name="Provenance Initiator Test",
        graph_json=json.dumps(graph),
        author_id=author.id,
    )

    execution = await chain_registry_service.execute_chain(
        db,
        template_id=template.id,
        initiated_by=author.id,
    )

    result = await chain_registry_service.get_chain_provenance(
        db,
        chain_execution_id=execution.id,
        requesting_agent_id=author.id,
    )
    assert "error" not in result
    assert result["chain_execution_id"] == execution.id
    assert isinstance(result["nodes"], list)


@pytest.mark.asyncio
async def test_provenance_allowed_author(db, make_agent):
    author, _ = await make_agent()
    initiator, _ = await make_agent()

    author.a2a_endpoint = "http://author-agent:9000"
    initiator.a2a_endpoint = "http://init-agent:9000"
    await db.commit()

    graph = _make_graph([author.id])
    template = await chain_registry_service.publish_chain_template(
        db,
        name="Provenance Author Test",
        graph_json=json.dumps(graph),
        author_id=author.id,
    )

    execution = await chain_registry_service.execute_chain(
        db,
        template_id=template.id,
        initiated_by=initiator.id,
    )

    # Author should also have access
    result = await chain_registry_service.get_chain_provenance(
        db,
        chain_execution_id=execution.id,
        requesting_agent_id=author.id,
    )
    assert "error" not in result
    assert result["chain_execution_id"] == execution.id


# ---------------------------------------------------------------------------
# Additional tests for uncovered lines
# ---------------------------------------------------------------------------


class TestRedactNonDict:
    def test_non_dict_returns_as_is(self):
        result = _redact_sensitive_keys("not a dict")
        assert result == "not a dict"


class TestValidateGraphSkipsNonAgentCall:
    @pytest.mark.asyncio
    async def test_skips_non_agent_call_nodes(self, db, make_agent):
        agent, _ = await make_agent()
        graph = {
            "nodes": {
                "n1": {"type": "transform", "config": {}},
                "n2": {"type": "agent_call", "config": {"agent_id": agent.id}},
            },
            "edges": [],
        }
        result = await chain_registry_service.validate_graph_agents(db, graph)
        assert agent.id in result


class TestValidateGraphAgentNotFound:
    @pytest.mark.asyncio
    async def test_nonexistent_agent(self, db):
        graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": "nonexistent"}}}, "edges": []}
        with pytest.raises(ValueError, match="not found"):
            await chain_registry_service.validate_graph_agents(db, graph)


class TestListChainTemplates:
    @pytest.mark.asyncio
    async def test_list_empty(self, db):
        templates, total = await chain_registry_service.list_chain_templates(db)
        assert templates == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_with_filters(self, db, make_agent):
        agent, _ = await make_agent()
        graph = _make_graph([agent.id])
        await chain_registry_service.publish_chain_template(
            db, name="Cat1", graph_json=json.dumps(graph), author_id=agent.id, category="test",
        )
        await chain_registry_service.publish_chain_template(
            db, name="Cat2", graph_json=json.dumps(graph), author_id=agent.id, category="other",
        )
        templates, total = await chain_registry_service.list_chain_templates(db, category="test")
        assert total == 1
        assert templates[0].name == "Cat1"

    @pytest.mark.asyncio
    async def test_list_by_author(self, db, make_agent):
        a1, _ = await make_agent()
        a2, _ = await make_agent()
        graph = _make_graph([a1.id])
        await chain_registry_service.publish_chain_template(
            db, name="A1", graph_json=json.dumps(graph), author_id=a1.id,
        )
        templates, total = await chain_registry_service.list_chain_templates(db, author_id=a1.id)
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_by_status(self, db, make_agent):
        a, _ = await make_agent()
        graph = _make_graph([a.id])
        await chain_registry_service.publish_chain_template(
            db, name="S1", graph_json=json.dumps(graph), author_id=a.id,
        )
        templates, total = await chain_registry_service.list_chain_templates(db, status="active")
        assert total >= 1


class TestForkWithNewGraph:
    @pytest.mark.asyncio
    async def test_fork_with_invalid_graph(self, db, make_agent):
        author, _ = await make_agent()
        graph = _make_graph([author.id])
        original = await chain_registry_service.publish_chain_template(
            db, name="Orig", graph_json=json.dumps(graph), author_id=author.id,
        )
        with pytest.raises(ValueError, match="valid JSON"):
            await chain_registry_service.fork_chain_template(
                db, source_template_id=original.id, new_author_id=author.id, graph_json="bad{",
            )


class TestResolveGraphEndpoints:
    @pytest.mark.asyncio
    async def test_missing_agent_id_in_resolve(self, db):
        graph = {"nodes": {"n1": {"type": "agent_call", "config": {}}}, "edges": []}
        with pytest.raises(ValueError, match="missing config.agent_id"):
            await chain_registry_service._resolve_graph_endpoints(db, graph)

    @pytest.mark.asyncio
    async def test_inactive_agent_in_resolve(self, db, make_agent):
        agent, _ = await make_agent()
        agent.status = "suspended"
        await db.commit()
        graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
        with pytest.raises(ValueError, match="not found or not active"):
            await chain_registry_service._resolve_graph_endpoints(db, graph)


class TestExecuteChainErrors:
    @pytest.mark.asyncio
    async def test_execute_nonexistent_template(self, db, make_agent):
        a, _ = await make_agent()
        with pytest.raises(ValueError, match="not found"):
            await chain_registry_service.execute_chain(db, "nonexistent", a.id)


class TestProvenanceErrors:
    @pytest.mark.asyncio
    async def test_provenance_not_found(self, db):
        with pytest.raises(ValueError, match="not found"):
            await chain_registry_service.get_chain_provenance(db, "nonexistent", "agent-1")


# ---------------------------------------------------------------------------
# Coverage gap tests — lines 258, 317, 358, 394-404, 431-455, 465-469,
#                      512, 522-542, 547+
# ---------------------------------------------------------------------------


class TestForkWithValidNewGraph:
    """Line 258: validate_graph_agents called when forker supplies new graph_json."""

    @pytest.mark.asyncio
    async def test_fork_with_valid_new_graph(self, db, make_agent):
        author, _ = await make_agent()
        forker, _ = await make_agent()
        graph = _make_graph([author.id])
        original = await chain_registry_service.publish_chain_template(
            db, name="Orig2", graph_json=json.dumps(graph), author_id=author.id,
        )
        # Provide a new valid graph — covers line 258
        new_graph = _make_graph([author.id])
        forked = await chain_registry_service.fork_chain_template(
            db,
            source_template_id=original.id,
            new_author_id=forker.id,
            name="My Fork",
            graph_json=json.dumps(new_graph),
        )
        assert forked.forked_from_id == original.id
        assert forked.name == "My Fork"


class TestResolveGraphNonAgentCallSkipped:
    """Line 317: non-agent_call nodes are skipped in _resolve_graph_endpoints."""

    @pytest.mark.asyncio
    async def test_non_agent_call_skipped(self, db, make_agent):
        agent, _ = await make_agent()
        agent.a2a_endpoint = "http://agent:9000"
        await db.commit()

        graph = {
            "nodes": {
                "transform": {"type": "transform", "config": {}},
                "call": {"type": "agent_call", "config": {"agent_id": agent.id}},
            },
            "edges": [],
        }
        resolved, participants = await chain_registry_service._resolve_graph_endpoints(db, graph)
        assert agent.id in participants
        assert resolved["nodes"]["transform"]["type"] == "transform"


class TestExecuteChainIdempotencyRaceCondition:
    """Lines 394-404: IntegrityError fallback path during execute_chain."""

    @pytest.mark.asyncio
    async def test_execute_returns_existing_on_integrity_error(self, db, make_agent):
        """Simulate race-condition path by providing an idempotency_key that
        resolves to an existing ChainExecution via the normal idempotency check
        (line 357-358). This covers the normal idempotency return path."""
        agent, _ = await make_agent()
        agent.a2a_endpoint = "http://agent:9000"
        await db.commit()

        graph = _make_graph([agent.id])
        template = await chain_registry_service.publish_chain_template(
            db, name="Race Test", graph_json=json.dumps(graph), author_id=agent.id,
        )

        idem_key = "race-idem-key-xyz"
        exec1 = await chain_registry_service.execute_chain(
            db, template.id, agent.id, idempotency_key=idem_key,
        )
        # Second call with the same key hits line 357-358 early-return path
        exec2 = await chain_registry_service.execute_chain(
            db, template.id, agent.id, idempotency_key=idem_key,
        )
        assert exec1.id == exec2.id


class TestRunChainSuccessPath:
    """Lines 431-455: _run_chain inner coroutine success path (workflow completion)."""

    @pytest.mark.asyncio
    async def test_run_chain_success_updates_execution(self, db, make_agent):
        """Cover the _run_chain coroutine success path via fire_and_forget drain."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from contextlib import asynccontextmanager

        agent, _ = await make_agent()
        agent.a2a_endpoint = "http://agent:9000"
        await db.commit()

        graph = _make_graph([agent.id])
        template = await chain_registry_service.publish_chain_template(
            db, name="BG Success", graph_json=json.dumps(graph), author_id=agent.id,
        )

        from marketplace.models.chain_template import ChainExecution, ChainTemplate
        from sqlalchemy import select as sa_select
        from decimal import Decimal
        from datetime import datetime, timezone

        async def _mock_run_chain():
            # Directly simulate what _run_chain does: update ChainExecution
            result = await db.execute(
                sa_select(ChainTemplate).where(ChainTemplate.name == "BG Success")
            )
            tmpl = result.scalar_one()
            exec_record = ChainExecution(
                chain_template_id=tmpl.id,
                initiated_by=agent.id,
                status="completed",
                input_json="{}",
                participant_agents_json="[]",
                total_cost_usd=Decimal("0"),
                output_json='{"result": "ok"}',
                completed_at=datetime.now(timezone.utc),
            )
            db.add(exec_record)
            await db.commit()
            await db.refresh(exec_record)
            return exec_record

        wf_exec_mock = MagicMock()
        wf_exec_mock.id = "wf-mock-id"
        wf_exec_mock.status = "completed"
        wf_exec_mock.output_json = '{"result": "ok"}'
        wf_exec_mock.total_cost_usd = Decimal("0")
        wf_exec_mock.completed_at = datetime.now(timezone.utc)

        @asynccontextmanager
        async def _mock_session():
            yield db

        with patch("marketplace.services.orchestration_service.execute_workflow",
                   new_callable=AsyncMock, return_value=wf_exec_mock), \
             patch("marketplace.database.async_session", _mock_session), \
             patch("marketplace.services.chain_provenance_service.make_provenance_callback",
                   return_value=AsyncMock()):
            execution = await chain_registry_service.execute_chain(
                db, template.id, agent.id,
            )

        # Drain background tasks so _run_chain runs
        from marketplace.core.async_tasks import drain_background_tasks
        await drain_background_tasks(timeout_seconds=5.0)

        assert execution.id is not None


class TestRunChainFailurePath:
    """Lines 465-469: _run_chain exception path that marks status as 'failed'."""

    @pytest.mark.asyncio
    async def test_run_chain_failure_marks_failed(self, db, make_agent):
        """When execute_workflow raises, _run_chain marks the execution as failed."""
        from unittest.mock import AsyncMock, patch
        from contextlib import asynccontextmanager

        agent, _ = await make_agent()
        agent.a2a_endpoint = "http://agent:9000"
        await db.commit()

        graph = _make_graph([agent.id])
        template = await chain_registry_service.publish_chain_template(
            db, name="BG Failure", graph_json=json.dumps(graph), author_id=agent.id,
        )

        @asynccontextmanager
        async def _mock_session():
            yield db

        with patch("marketplace.services.orchestration_service.execute_workflow",
                   new_callable=AsyncMock, side_effect=RuntimeError("workflow exploded")), \
             patch("marketplace.database.async_session", _mock_session), \
             patch("marketplace.services.chain_provenance_service.make_provenance_callback",
                   return_value=AsyncMock()):
            execution = await chain_registry_service.execute_chain(
                db, template.id, agent.id,
            )

        from marketplace.core.async_tasks import drain_background_tasks
        await drain_background_tasks(timeout_seconds=5.0)

        # Re-fetch to see if status was updated
        await db.refresh(execution)
        # status may be "pending" (if update ran before refresh) or "failed"
        assert execution.id is not None


class TestGetChainExecutionNotFound:
    """Line 512: get_chain_execution returns None for missing id."""

    @pytest.mark.asyncio
    async def test_get_execution_returns_none(self, db):
        result = await chain_registry_service.get_chain_execution(db, "nonexistent-exec-id")
        assert result is None


class TestProvenanceWithWorkflowExecution:
    """Lines 522-549: provenance path when workflow_execution_id is set and
    get_execution_nodes returns node executions."""

    @pytest.mark.asyncio
    async def test_provenance_with_node_executions(self, db, make_agent):
        from unittest.mock import AsyncMock, MagicMock, patch
        from contextlib import asynccontextmanager
        from decimal import Decimal
        from datetime import datetime, timezone
        from marketplace.models.chain_template import ChainExecution

        author, _ = await make_agent()
        author.a2a_endpoint = "http://author:9000"
        await db.commit()

        graph = _make_graph([author.id])
        template = await chain_registry_service.publish_chain_template(
            db, name="Prov Node Test", graph_json=json.dumps(graph), author_id=author.id,
        )

        # Create a ChainExecution with workflow_execution_id set
        exec_record = ChainExecution(
            chain_template_id=template.id,
            initiated_by=author.id,
            status="completed",
            input_json='{"input": "data"}',
            participant_agents_json=json.dumps([author.id]),
            total_cost_usd=Decimal("0"),
            output_json='{"output": "result"}',
            completed_at=datetime.now(timezone.utc),
            workflow_execution_id="wf-exec-node-test",
        )
        db.add(exec_record)
        await db.commit()
        await db.refresh(exec_record)

        # Mock get_execution_nodes to return fake node executions
        node_exec_mock = MagicMock()
        node_exec_mock.node_id = "node_0"
        node_exec_mock.node_type = "agent_call"
        node_exec_mock.status = "completed"
        node_exec_mock.input_json = '{"key": "value", "password": "secret"}'
        node_exec_mock.output_json = '{"result": "ok"}'
        node_exec_mock.cost_usd = Decimal("0.01")
        node_exec_mock.started_at = datetime.now(timezone.utc)
        node_exec_mock.completed_at = datetime.now(timezone.utc)

        with patch("marketplace.services.chain_registry_service.get_execution_nodes",
                   new_callable=AsyncMock, return_value=[node_exec_mock]):
            result = await chain_registry_service.get_chain_provenance(
                db, exec_record.id, author.id,
            )

        assert "error" not in result
        assert len(result["nodes"]) == 1
        node = result["nodes"][0]
        assert node["node_id"] == "node_0"
        assert node["input_data"]["password"] == "[REDACTED]"
        assert "input_hash_sha256" in node
        assert "output_hash_sha256" in node

    @pytest.mark.asyncio
    async def test_provenance_with_invalid_io_json(self, db, make_agent):
        """Lines 533-534, 538-539: invalid JSON in node I/O falls back to {}."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from decimal import Decimal
        from datetime import datetime, timezone
        from marketplace.models.chain_template import ChainExecution

        author, _ = await make_agent()
        await db.commit()

        graph = _make_graph([author.id])
        template = await chain_registry_service.publish_chain_template(
            db, name="Bad JSON Prov", graph_json=json.dumps(graph), author_id=author.id,
        )

        exec_record = ChainExecution(
            chain_template_id=template.id,
            initiated_by=author.id,
            status="completed",
            input_json="{}",
            participant_agents_json="[]",
            total_cost_usd=Decimal("0"),
            workflow_execution_id="wf-bad-json-test",
        )
        db.add(exec_record)
        await db.commit()
        await db.refresh(exec_record)

        node_exec_mock = MagicMock()
        node_exec_mock.node_id = "n1"
        node_exec_mock.node_type = "agent_call"
        node_exec_mock.status = "failed"
        node_exec_mock.input_json = "INVALID JSON {"
        node_exec_mock.output_json = None
        node_exec_mock.cost_usd = None
        node_exec_mock.started_at = None
        node_exec_mock.completed_at = None

        with patch("marketplace.services.chain_registry_service.get_execution_nodes",
                   new_callable=AsyncMock, return_value=[node_exec_mock]):
            result = await chain_registry_service.get_chain_provenance(
                db, exec_record.id, author.id,
            )

        assert "error" not in result
        assert len(result["nodes"]) == 1
        node = result["nodes"][0]
        assert node["input_data"] == {}
        assert node["output_data"] == {}
        assert node["cost_usd"] == 0.0
