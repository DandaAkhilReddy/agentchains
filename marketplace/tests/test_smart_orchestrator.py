"""Tests for marketplace.services.smart_orchestrator.SmartOrchestrator.

Covers:
- compose_and_execute: routes to LangGraph when graph+client present
- compose_and_execute: routes to fallback when no client configured
- _decompose_task: happy path with mocked LLM returning valid JSON
- _decompose_task: retries on bad JSON then succeeds on 2nd attempt
- _decompose_task: returns error state after max retries exhausted
- _match_agents: happy path — valid assignments returned
- _build_dag: happy path — validated graph_json returned
- _synthesize_result: happy path — human-readable text returned
- _synthesize_result: returns raw JSON when no agent outputs
- _synthesize_result: returns error message when state has error
- _call_llm: sync callable
- _call_llm: async callable
- _call_llm: OpenAI-style client (chat.completions.create)
- _call_llm: raises ValueError when no client configured
- _execute_with_fallback: extracts capabilities and maps agents
- _execute_with_fallback: returns error when no capabilities found
- _parse_json_response: plain JSON object
- _parse_json_response: markdown-fenced JSON
- _parse_json_response: raises JSONDecodeError on invalid text
- _parse_json_response: raises ValueError on JSON array (not object)
- error state propagation: _match_agents / _build_dag skip on error
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from marketplace.services.smart_orchestrator import (
    OrchestratorState,
    SmartOrchestrator,
    _parse_json_response,
)


# ---------------------------------------------------------------------------
# In-memory DB fixture (self-contained — avoids conftest import chain)
# ---------------------------------------------------------------------------


@pytest.fixture
async def db() -> AsyncSession:
    """Yield a fresh in-memory SQLite AsyncSession."""
    from marketplace.database import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Canned LLM responses
# ---------------------------------------------------------------------------

_DECOMPOSE_RESPONSE = json.dumps({
    "sub_tasks": [
        {
            "id": "t1",
            "description": "Fetch market data",
            "depends_on": [],
            "required_capability": "data",
        },
        {
            "id": "t2",
            "description": "Analyse trends",
            "depends_on": ["t1"],
            "required_capability": "analysis",
        },
    ]
})

_MATCH_RESPONSE = json.dumps({
    "assignments": [
        {
            "task_id": "t1",
            "agent_name": "DataAgent",
            "agent_id": "agent-uuid-1",
            "skill_id": "default",
            "reason": "Best data agent",
        },
        {
            "task_id": "t2",
            "agent_name": "AnalysisAgent",
            "agent_id": "agent-uuid-2",
            "skill_id": "default",
            "reason": "Best analysis agent",
        },
    ]
})

_DAG_RESPONSE = json.dumps({
    "nodes": {
        "node_t1": {
            "type": "agent_call",
            "config": {"agent_id": "agent-uuid-1", "skill_id": "default"},
            "depends_on": [],
        },
        "node_t2": {
            "type": "agent_call",
            "config": {"agent_id": "agent-uuid-2", "skill_id": "default"},
            "depends_on": ["node_t1"],
        },
    },
    "edges": [],
})

_SYNTHESIZE_RESPONSE = "Here is the synthesized market analysis report."


def _make_llm(responses: list[str]) -> MagicMock:
    """Return a sync callable that pops responses in order."""
    responses_iter = iter(responses)

    def _call(prompt: str) -> str:
        return next(responses_iter)

    return _call


def _make_async_llm(responses: list[str]) -> AsyncMock:
    """Return an async callable that pops responses in order."""
    responses_iter = iter(responses)

    async def _call(prompt: str) -> str:
        return next(responses_iter)

    return _call


# ---------------------------------------------------------------------------
# _parse_json_response (pure helper — no fixtures needed)
# ---------------------------------------------------------------------------


class TestParseJsonResponse:
    """Tests for the _parse_json_response module-level helper."""

    def test_plain_json_object(self) -> None:
        raw = '{"sub_tasks": []}'
        result = _parse_json_response(raw)
        assert result == {"sub_tasks": []}

    def test_markdown_fenced_json(self) -> None:
        raw = '```json\n{"sub_tasks": [1, 2]}\n```'
        result = _parse_json_response(raw)
        assert result == {"sub_tasks": [1, 2]}

    def test_markdown_fenced_no_language_tag(self) -> None:
        raw = '```\n{"key": "value"}\n```'
        result = _parse_json_response(raw)
        assert result == {"key": "value"}

    def test_raises_json_decode_error_on_invalid_text(self) -> None:
        import json

        with pytest.raises(json.JSONDecodeError):
            _parse_json_response("this is not json at all")

    def test_raises_value_error_on_json_array(self) -> None:
        with pytest.raises(ValueError, match="Expected JSON object"):
            _parse_json_response("[1, 2, 3]")

    def test_strips_whitespace_around_fences(self) -> None:
        raw = '  ```json\n{"ok": true}\n```  '
        result = _parse_json_response(raw)
        assert result == {"ok": True}


# ---------------------------------------------------------------------------
# SmartOrchestrator._call_llm
# ---------------------------------------------------------------------------


class TestCallLlm:
    """Tests for the _call_llm LLM client abstraction."""

    async def test_sync_callable(self, db: AsyncSession) -> None:
        llm = lambda prompt: "sync response"  # noqa: E731
        orch = SmartOrchestrator(db=db, llm_client=llm)
        result = await orch._call_llm("test prompt")
        assert result == "sync response"

    async def test_async_callable(self, db: AsyncSession) -> None:
        async def _async_llm(prompt: str) -> str:
            return "async response"

        orch = SmartOrchestrator(db=db, llm_client=_async_llm)
        result = await orch._call_llm("test prompt")
        assert result == "async response"

    async def test_openai_style_client(self, db: AsyncSession) -> None:
        """_call_llm uses chat.completions.create for OpenAI-compatible clients."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "openai response"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        orch = SmartOrchestrator(db=db, llm_client=mock_client)
        result = await orch._call_llm("test prompt")

        assert result == "openai response"
        mock_client.chat.completions.create.assert_awaited_once()
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4"
        assert call_kwargs.kwargs["messages"][0]["content"] == "test prompt"

    async def test_raises_when_no_client_configured(self, db: AsyncSession) -> None:
        orch = SmartOrchestrator(db=db, llm_client=None)
        with pytest.raises(ValueError, match="No LLM client configured"):
            await orch._call_llm("test prompt")

    async def test_raises_for_unsupported_client_type(self, db: AsyncSession) -> None:
        """A non-callable, non-OpenAI object raises ValueError."""
        orch = SmartOrchestrator(db=db, llm_client=42)
        with pytest.raises(ValueError, match="llm_client must be"):
            await orch._call_llm("test prompt")


# ---------------------------------------------------------------------------
# SmartOrchestrator._decompose_task
# ---------------------------------------------------------------------------


class TestDecomposeTask:
    """Tests for the _decompose_task LangGraph node."""

    async def test_happy_path_returns_sub_tasks(self, db: AsyncSession) -> None:
        llm = _make_llm([_DECOMPOSE_RESPONSE])
        orch = SmartOrchestrator(db=db, llm_client=llm)
        state: OrchestratorState = {
            "task_description": "Analyse market trends and generate report",
            "retry_count": 0,
        }
        result = await orch._decompose_task(state)

        assert "sub_tasks" in result
        assert len(result["sub_tasks"]) == 2
        assert result["sub_tasks"][0]["id"] == "t1"
        assert result["sub_tasks"][1]["required_capability"] == "analysis"
        assert "error" not in result or result.get("error") == ""

    async def test_retry_on_bad_json_then_succeeds(self, db: AsyncSession) -> None:
        """First call returns bad JSON, second call returns valid JSON."""
        llm = _make_llm(["not json at all", _DECOMPOSE_RESPONSE])
        orch = SmartOrchestrator(db=db, llm_client=llm)
        state: OrchestratorState = {
            "task_description": "Analyse market trends",
            "retry_count": 0,
        }
        result = await orch._decompose_task(state)

        assert "sub_tasks" in result
        assert len(result["sub_tasks"]) == 2
        # retry_count should have incremented
        assert result.get("retry_count", 0) >= 1

    async def test_returns_error_after_max_retries(self, db: AsyncSession) -> None:
        """All three attempts return bad JSON — error state emitted."""
        llm = _make_llm(["bad", "also bad", "still bad"])
        orch = SmartOrchestrator(db=db, llm_client=llm)
        state: OrchestratorState = {
            "task_description": "Analyse market trends",
            "retry_count": 0,
        }
        result = await orch._decompose_task(state)

        assert result.get("error", "") != ""
        assert "decompose_task failed" in result["error"]
        assert result.get("sub_tasks") == []

    async def test_empty_sub_tasks_triggers_retry(self, db: AsyncSession) -> None:
        """LLM returns valid JSON but empty sub_tasks — treated as failure."""
        empty_response = json.dumps({"sub_tasks": []})
        llm = _make_llm([empty_response, empty_response, empty_response])
        orch = SmartOrchestrator(db=db, llm_client=llm)
        state: OrchestratorState = {
            "task_description": "Do nothing",
            "retry_count": 0,
        }
        result = await orch._decompose_task(state)

        assert result.get("error", "") != ""


# ---------------------------------------------------------------------------
# SmartOrchestrator._match_agents
# ---------------------------------------------------------------------------


class TestMatchAgents:
    """Tests for the _match_agents LangGraph node."""

    async def test_happy_path_returns_assignments(self, db: AsyncSession) -> None:
        llm = _make_llm([_MATCH_RESPONSE])
        orch = SmartOrchestrator(db=db, llm_client=llm)

        sub_tasks = [
            {
                "id": "t1",
                "description": "Fetch data",
                "depends_on": [],
                "required_capability": "data",
            }
        ]
        state: OrchestratorState = {"sub_tasks": sub_tasks, "error": ""}

        with patch(
            "marketplace.services.auto_chain_service.suggest_agents_for_capability",
            new=AsyncMock(return_value=[{"agent_id": "agent-uuid-1", "name": "DataAgent"}]),
        ):
            result = await orch._match_agents(state)

        assert "assignments" in result
        assert len(result["assignments"]) >= 1

    async def test_skips_when_error_in_state(self, db: AsyncSession) -> None:
        """If state already has an error, _match_agents returns empty dict."""
        orch = SmartOrchestrator(db=db, llm_client=_make_llm([]))
        state: OrchestratorState = {
            "sub_tasks": [],
            "error": "decompose_task failed: something went wrong",
        }
        result = await orch._match_agents(state)
        assert result == {}

    async def test_returns_error_when_no_sub_tasks(self, db: AsyncSession) -> None:
        """Empty sub_tasks list → error state, no LLM call."""
        orch = SmartOrchestrator(db=db, llm_client=_make_llm([]))
        state: OrchestratorState = {"sub_tasks": [], "error": ""}
        result = await orch._match_agents(state)
        assert result.get("error", "") != ""
        assert result.get("assignments") == []

    async def test_returns_error_after_max_retries(self, db: AsyncSession) -> None:
        """All LLM responses are invalid JSON — error state after retries."""
        llm = _make_llm(["bad", "bad", "bad"])
        orch = SmartOrchestrator(db=db, llm_client=llm)
        sub_tasks = [
            {"id": "t1", "description": "x", "depends_on": [], "required_capability": "data"}
        ]
        state: OrchestratorState = {"sub_tasks": sub_tasks, "error": ""}

        with patch(
            "marketplace.services.auto_chain_service.suggest_agents_for_capability",
            new=AsyncMock(return_value=[]),
        ):
            result = await orch._match_agents(state)

        assert "match_agents failed" in result.get("error", "")
        assert result.get("assignments") == []


# ---------------------------------------------------------------------------
# SmartOrchestrator._build_dag
# ---------------------------------------------------------------------------


class TestBuildDag:
    """Tests for the _build_dag LangGraph node."""

    async def test_happy_path_returns_graph_json(self, db: AsyncSession) -> None:
        llm = _make_llm([_DAG_RESPONSE])
        orch = SmartOrchestrator(db=db, llm_client=llm)

        assignments = [
            {
                "task_id": "t1",
                "agent_id": "agent-uuid-1",
                "skill_id": "default",
                "agent_name": "DataAgent",
                "reason": "best match",
            }
        ]
        sub_tasks = [
            {"id": "t1", "description": "Fetch", "depends_on": [], "required_capability": "data"}
        ]
        state: OrchestratorState = {
            "assignments": assignments,
            "sub_tasks": sub_tasks,
            "error": "",
        }
        result = await orch._build_dag(state)

        assert "graph_json" in result
        dag = json.loads(result["graph_json"])
        assert "nodes" in dag
        assert "node_t1" in dag["nodes"]
        assert "node_t2" in dag["nodes"]

    async def test_skips_when_error_in_state(self, db: AsyncSession) -> None:
        orch = SmartOrchestrator(db=db, llm_client=_make_llm([]))
        state: OrchestratorState = {
            "assignments": [],
            "sub_tasks": [],
            "error": "previous node failed",
        }
        result = await orch._build_dag(state)
        assert result == {}

    async def test_returns_error_when_no_assignments(self, db: AsyncSession) -> None:
        orch = SmartOrchestrator(db=db, llm_client=_make_llm([]))
        state: OrchestratorState = {
            "assignments": [],
            "sub_tasks": [],
            "error": "",
        }
        result = await orch._build_dag(state)
        assert result.get("error", "") != ""
        assert result.get("graph_json") == "{}"

    async def test_returns_error_after_max_retries(self, db: AsyncSession) -> None:
        llm = _make_llm(["bad", "bad", "bad"])
        orch = SmartOrchestrator(db=db, llm_client=llm)
        state: OrchestratorState = {
            "assignments": [{"task_id": "t1", "agent_id": "x", "skill_id": "default"}],
            "sub_tasks": [{"id": "t1"}],
            "error": "",
        }
        result = await orch._build_dag(state)
        assert "build_dag failed" in result.get("error", "")

    async def test_cyclic_dag_triggers_retry(self, db: AsyncSession) -> None:
        """A cyclic DAG fails topological sort validation and triggers retry."""
        cyclic_dag = json.dumps({
            "nodes": {
                "node_t1": {
                    "type": "agent_call",
                    "config": {"agent_id": "a1", "skill_id": "default"},
                    "depends_on": ["node_t2"],  # creates cycle
                },
                "node_t2": {
                    "type": "agent_call",
                    "config": {"agent_id": "a2", "skill_id": "default"},
                    "depends_on": ["node_t1"],
                },
            },
            "edges": [],
        })
        # All attempts return a cyclic DAG → error after retries
        llm = _make_llm([cyclic_dag, cyclic_dag, cyclic_dag])
        orch = SmartOrchestrator(db=db, llm_client=llm)
        state: OrchestratorState = {
            "assignments": [{"task_id": "t1", "agent_id": "a1", "skill_id": "default"}],
            "sub_tasks": [{"id": "t1"}],
            "error": "",
        }
        result = await orch._build_dag(state)
        assert result.get("error", "") != ""


# ---------------------------------------------------------------------------
# SmartOrchestrator._synthesize_result
# ---------------------------------------------------------------------------


class TestSynthesizeResult:
    """Tests for the _synthesize_result LangGraph node."""

    async def test_happy_path_returns_llm_text(self, db: AsyncSession) -> None:
        llm = _make_llm([_SYNTHESIZE_RESPONSE])
        orch = SmartOrchestrator(db=db, llm_client=llm)
        state: OrchestratorState = {
            "task_description": "Analyse markets",
            "agent_outputs": {"node_t1": {"data": "AAPL: $150"}},
            "error": "",
        }
        result = await orch._synthesize_result(state)
        assert result["final_result"] == _SYNTHESIZE_RESPONSE

    async def test_returns_no_output_message_when_empty(self, db: AsyncSession) -> None:
        orch = SmartOrchestrator(db=db, llm_client=_make_llm([]))
        state: OrchestratorState = {
            "task_description": "Analyse markets",
            "agent_outputs": {},
            "error": "",
        }
        result = await orch._synthesize_result(state)
        assert result["final_result"] == "No agent outputs were produced."

    async def test_returns_error_message_when_state_has_error(self, db: AsyncSession) -> None:
        orch = SmartOrchestrator(db=db, llm_client=_make_llm([]))
        state: OrchestratorState = {
            "task_description": "Analyse markets",
            "agent_outputs": {},
            "error": "build_dag failed: cycle detected",
        }
        result = await orch._synthesize_result(state)
        assert "build_dag failed" in result["final_result"]
        assert "Execution stopped due to error" in result["final_result"]

    async def test_falls_back_to_raw_json_on_llm_failure(self, db: AsyncSession) -> None:
        """If the LLM call fails, raw agent_outputs JSON is returned."""
        async def _boom(prompt: str) -> str:
            raise RuntimeError("LLM unavailable")

        orch = SmartOrchestrator(db=db, llm_client=_boom)
        outputs = {"node_t1": "some result"}
        state: OrchestratorState = {
            "task_description": "Analyse markets",
            "agent_outputs": outputs,
            "error": "",
        }
        result = await orch._synthesize_result(state)
        # Should fall back to serialised agent outputs
        parsed = json.loads(result["final_result"])
        assert parsed == outputs


# ---------------------------------------------------------------------------
# SmartOrchestrator._execute_with_fallback
# ---------------------------------------------------------------------------


class TestExecuteWithFallback:
    """Tests for the keyword-based fallback path."""

    async def test_extracts_capabilities_and_maps_agents(self, db: AsyncSession) -> None:
        orch = SmartOrchestrator(db=db, llm_client=None)
        fake_agent = {"agent_id": "agent-uuid-1", "name": "WebSearchAgent"}

        with (
            patch(
                "marketplace.services.auto_chain_service.extract_capabilities",
                return_value=["data", "analysis"],
            ),
            patch(
                "marketplace.services.auto_chain_service.suggest_agents_for_capability",
                new=AsyncMock(return_value=[fake_agent]),
            ),
        ):
            result = await orch._execute_with_fallback(
                "search data and analyse trends", "test-user"
            )

        assert result["method"] == "fallback"
        assert "data" in result["capabilities"]
        assert "analysis" in result["capabilities"]
        assert len(result["assignments"]) == 2
        assert result["error"] == ""

    async def test_returns_error_when_no_capabilities_extracted(self, db: AsyncSession) -> None:
        orch = SmartOrchestrator(db=db, llm_client=None)

        with patch(
            "marketplace.services.auto_chain_service.extract_capabilities",
            return_value=[],
        ):
            result = await orch._execute_with_fallback("", "test-user")

        assert result["method"] == "fallback"
        assert result["error"] != ""
        assert result["assignments"] == []

    async def test_returns_error_when_no_agents_found(self, db: AsyncSession) -> None:
        """Capabilities extracted but no agents exist for any of them."""
        orch = SmartOrchestrator(db=db, llm_client=None)

        with (
            patch(
                "marketplace.services.auto_chain_service.extract_capabilities",
                return_value=["data"],
            ),
            patch(
                "marketplace.services.auto_chain_service.suggest_agents_for_capability",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await orch._execute_with_fallback("fetch some data", "test-user")

        assert result["method"] == "fallback"
        assert result["error"] == "No agents found for any capability"
        assert result["assignments"] == []

    async def test_partial_agent_match_still_succeeds(self, db: AsyncSession) -> None:
        """Some capabilities have agents, some do not — partial assignments returned."""
        orch = SmartOrchestrator(db=db, llm_client=None)
        fake_agent = {"agent_id": "agent-1", "name": "DataAgent"}

        async def _suggest(db: Any, cap: str, max_results: int = 1) -> list[dict]:
            return [fake_agent] if cap == "data" else []

        with (
            patch(
                "marketplace.services.auto_chain_service.extract_capabilities",
                return_value=["data", "output"],
            ),
            patch(
                "marketplace.services.auto_chain_service.suggest_agents_for_capability",
                new=AsyncMock(side_effect=_suggest),
            ),
        ):
            result = await orch._execute_with_fallback("fetch and export data", "test-user")

        assert result["method"] == "fallback"
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["capability"] == "data"
        assert result["error"] == ""  # at least one assignment exists


# ---------------------------------------------------------------------------
# SmartOrchestrator.compose_and_execute
# ---------------------------------------------------------------------------


class TestComposeAndExecute:
    """Integration-style tests for the top-level public API."""

    async def test_routes_to_fallback_when_no_llm_client(self, db: AsyncSession) -> None:
        """compose_and_execute uses fallback path when llm_client=None."""
        orch = SmartOrchestrator(db=db, llm_client=None)

        with (
            patch(
                "marketplace.services.auto_chain_service.extract_capabilities",
                return_value=["data"],
            ),
            patch(
                "marketplace.services.auto_chain_service.suggest_agents_for_capability",
                new=AsyncMock(
                    return_value=[{"agent_id": "agent-1", "name": "DataAgent"}]
                ),
            ),
        ):
            result = await orch.compose_and_execute("fetch market data", "user-1")

        assert result["method"] == "fallback"

    async def test_compose_and_execute_with_langgraph(self, db: AsyncSession) -> None:
        """When LangGraph is available and llm_client provided, use LangGraph path."""
        from marketplace.services import smart_orchestrator as _mod

        if not _mod.LANGGRAPH_AVAILABLE:
            pytest.skip("LangGraph not installed — skipping LangGraph path test")

        # Build a sync LLM that serves responses in the right order
        responses = [
            _DECOMPOSE_RESPONSE,   # decompose_task
            _MATCH_RESPONSE,       # match_agents
            _DAG_RESPONSE,         # build_dag
            _SYNTHESIZE_RESPONSE,  # synthesize_result
        ]
        llm = _make_llm(responses)

        orch = SmartOrchestrator(db=db, llm_client=llm, auto_approve=True)
        assert orch._graph is not None, "LangGraph graph should be built"

        with (
            patch(
                "marketplace.services.auto_chain_service.suggest_agents_for_capability",
                new=AsyncMock(
                    return_value=[{"agent_id": "agent-uuid-1", "name": "DataAgent"}]
                ),
            ),
            patch(
                "marketplace.services.orchestration_service.create_workflow",
                new=AsyncMock(return_value=MagicMock(id="wf-1")),
            ),
            patch(
                "marketplace.services.orchestration_service.execute_workflow",
                new=AsyncMock(
                    return_value=MagicMock(
                        id="wfexec-1", status="completed", output_json="{}"
                    )
                ),
            ),
        ):
            result = await orch.compose_and_execute(
                "Fetch market data and analyse trends", "user-1"
            )

        assert result["method"] == "langgraph"
        assert result["task_description"] == "Fetch market data and analyse trends"

    async def test_langgraph_exception_returns_error_result(self, db: AsyncSession) -> None:
        """If the LangGraph graph.ainvoke raises, a structured error dict is returned."""
        from marketplace.services import smart_orchestrator as _mod

        if not _mod.LANGGRAPH_AVAILABLE:
            pytest.skip("LangGraph not installed")

        llm = _make_llm([_DECOMPOSE_RESPONSE])
        orch = SmartOrchestrator(db=db, llm_client=llm)
        assert orch._graph is not None

        orch._graph = MagicMock()
        orch._graph.ainvoke = AsyncMock(side_effect=RuntimeError("graph boom"))

        result = await orch.compose_and_execute("do something", "user-1")

        assert result["method"] == "langgraph"
        assert "graph boom" in result["error"]
        assert result["final_result"] == ""


# ---------------------------------------------------------------------------
# Error-state propagation
# ---------------------------------------------------------------------------


class TestErrorStatePropagation:
    """Verify that downstream nodes skip processing when error is set."""

    async def test_match_agents_skips_on_error(self, db: AsyncSession) -> None:
        orch = SmartOrchestrator(db=db, llm_client=_make_llm([]))
        state: OrchestratorState = {
            "sub_tasks": [{"id": "t1", "required_capability": "data"}],
            "error": "decompose_task failed: something",
        }
        result = await orch._match_agents(state)
        # Must be an empty dict — not a new error, not an assignment
        assert result == {}

    async def test_build_dag_skips_on_error(self, db: AsyncSession) -> None:
        orch = SmartOrchestrator(db=db, llm_client=_make_llm([]))
        state: OrchestratorState = {
            "assignments": [{"task_id": "t1"}],
            "sub_tasks": [{"id": "t1"}],
            "error": "match_agents failed: something",
        }
        result = await orch._build_dag(state)
        assert result == {}

    async def test_execute_chain_skips_on_error(self, db: AsyncSession) -> None:
        orch = SmartOrchestrator(db=db, llm_client=_make_llm([]))
        state: OrchestratorState = {
            "graph_json": _DAG_RESPONSE,
            "task_description": "test",
            "error": "build_dag failed: something",
        }
        result = await orch._execute_chain(state)
        assert result == {}

    async def test_synthesize_result_returns_error_message_on_error(
        self, db: AsyncSession
    ) -> None:
        orch = SmartOrchestrator(db=db, llm_client=_make_llm([]))
        error_msg = "match_agents failed: LLM returned empty assignments"
        state: OrchestratorState = {
            "task_description": "test",
            "agent_outputs": {},
            "error": error_msg,
        }
        result = await orch._synthesize_result(state)
        assert error_msg in result["final_result"]
        assert "Execution stopped due to error" in result["final_result"]
