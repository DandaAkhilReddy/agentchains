"""SmartOrchestrator — LangGraph-powered natural-language-to-agent-chain executor.

Architecture (LangGraph path):
    task_description
        → decompose_task   (LLM: break into sub-tasks)
        → match_agents     (LLM: assign best agent per sub-task)
        → build_dag        (LLM: produce DAG graph_json)
        → execute_chain    (orchestration_service: create workflow + execute)
        → synthesize_result (LLM: merge outputs into final answer)

Fallback path (no LangGraph or no LLM client):
    Uses keyword-based capability extraction from auto_chain_service.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.services.orchestrator_prompts import (
    BUILD_DAG_PROMPT,
    DECOMPOSE_TASK_PROMPT,
    MATCH_AGENTS_PROMPT,
    SYNTHESIZE_RESULT_PROMPT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional LangGraph import — graceful fallback if not installed
# ---------------------------------------------------------------------------

try:
    from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None  # type: ignore[assignment,misc]
    END = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class OrchestratorState(TypedDict, total=False):
    """Mutable state threaded through every LangGraph node."""

    task_description: str
    sub_tasks: list[dict]
    available_agents: list[dict]
    assignments: list[dict]
    graph_json: str
    plan_approved: bool
    chain_execution_id: str
    agent_outputs: dict
    final_result: str
    error: str
    retry_count: int


# ---------------------------------------------------------------------------
# SmartOrchestrator
# ---------------------------------------------------------------------------


class SmartOrchestrator:
    """LangGraph-powered orchestrator that decomposes natural language tasks
    into agent chains and executes them.

    Falls back to keyword-based matching if LangGraph is not installed or
    no LLM client is provided.

    Args:
        db: SQLAlchemy async session used for agent lookups and workflow CRUD.
        llm_client: Optional LLM client.  Accepts:
            - An OpenAI-compatible client with ``client.chat.completions.create``.
            - A plain async callable ``async def f(prompt: str) -> str``.
            - A plain sync callable ``def f(prompt: str) -> str``.
        auto_approve: When True the plan is automatically approved without a
            human-in-the-loop ``approve_plan`` node.
    """

    def __init__(
        self,
        db: AsyncSession,
        llm_client: Any = None,
        auto_approve: bool = True,
    ) -> None:
        self.db = db
        self.llm_client = llm_client
        self.auto_approve = auto_approve
        self._graph = self._build_graph() if LANGGRAPH_AVAILABLE and llm_client else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def compose_and_execute(
        self,
        task_description: str,
        initiated_by: str = "system",
    ) -> dict[str, Any]:
        """Main entry point: natural language task → agent chain → result.

        Args:
            task_description: Free-text description of the task to execute.
            initiated_by: ID of the agent or system entity initiating the task.

        Returns:
            A dict containing sub_tasks, assignments, graph_json, final_result,
            error (if any), and method ("langgraph" or "fallback").
        """
        if self._graph and self.llm_client:
            return await self._execute_with_langgraph(task_description, initiated_by)
        return await self._execute_with_fallback(task_description, initiated_by)

    # ------------------------------------------------------------------
    # LangGraph graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> Any:
        """Build and compile the LangGraph StateGraph.

        Returns:
            A compiled LangGraph graph, or None if LangGraph is unavailable.
        """
        if not LANGGRAPH_AVAILABLE or StateGraph is None:
            return None

        graph: Any = StateGraph(OrchestratorState)

        graph.add_node("decompose_task", self._decompose_task)
        graph.add_node("match_agents", self._match_agents)
        graph.add_node("build_dag", self._build_dag)
        graph.add_node("execute_chain", self._execute_chain)
        graph.add_node("synthesize_result", self._synthesize_result)

        graph.set_entry_point("decompose_task")
        graph.add_edge("decompose_task", "match_agents")
        graph.add_edge("match_agents", "build_dag")
        graph.add_edge("build_dag", "execute_chain")
        graph.add_edge("execute_chain", "synthesize_result")
        graph.add_edge("synthesize_result", END)

        return graph.compile()

    # ------------------------------------------------------------------
    # LangGraph nodes
    # ------------------------------------------------------------------

    async def _decompose_task(self, state: OrchestratorState) -> dict[str, Any]:
        """LLM node: decompose a task description into ordered sub-tasks.

        Retries up to 2 additional times on JSON parse failure.

        Returns:
            Partial state update with ``sub_tasks`` (list of dicts) or
            ``error`` (str) if all attempts fail.
        """
        task_description: str = state.get("task_description", "")
        retry_count: int = state.get("retry_count", 0)
        max_retries: int = 2

        prompt = DECOMPOSE_TASK_PROMPT.format(task_description=task_description)

        for attempt in range(max_retries + 1):
            try:
                raw = await self._call_llm(prompt)
                data = _parse_json_response(raw)
                sub_tasks: list[dict] = data.get("sub_tasks", [])
                if not sub_tasks:
                    raise ValueError("LLM returned empty sub_tasks list")
                logger.info(
                    "decompose_task: extracted %d sub-tasks (attempt %d)",
                    len(sub_tasks),
                    attempt + 1,
                )
                return {"sub_tasks": sub_tasks, "retry_count": retry_count + attempt}
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                logger.warning(
                    "decompose_task attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt == max_retries:
                    return {
                        "error": f"decompose_task failed after {max_retries + 1} attempts: {exc}",
                        "sub_tasks": [],
                    }

        return {"sub_tasks": [], "error": "decompose_task: unexpected exit"}

    async def _match_agents(self, state: OrchestratorState) -> dict[str, Any]:
        """LLM node: match available agents to each sub-task.

        Loads candidate agents from the registry for each required capability,
        then asks the LLM to make the optimal assignment.

        Returns:
            Partial state update with ``assignments`` and ``available_agents``.
        """
        if state.get("error"):
            return {}

        sub_tasks: list[dict] = state.get("sub_tasks", [])
        if not sub_tasks:
            return {"error": "match_agents: no sub_tasks to match", "assignments": []}

        # Discover candidate agents for each required capability
        from marketplace.services.auto_chain_service import suggest_agents_for_capability

        capabilities: set[str] = {t.get("required_capability", "") for t in sub_tasks}
        available_agents: list[dict] = []
        seen_ids: set[str] = set()

        for cap in capabilities:
            if not cap:
                continue
            try:
                agents = await suggest_agents_for_capability(
                    self.db, cap, max_results=3
                )
                for agent in agents:
                    if agent["agent_id"] not in seen_ids:
                        agent["capability_match"] = cap
                        available_agents.append(agent)
                        seen_ids.add(agent["agent_id"])
            except Exception as exc:
                logger.warning("match_agents: agent discovery for '%s' failed: %s", cap, exc)

        max_retries: int = 2
        for attempt in range(max_retries + 1):
            try:
                prompt = MATCH_AGENTS_PROMPT.format(
                    sub_tasks_json=json.dumps(sub_tasks, indent=2),
                    agents_json=json.dumps(available_agents, indent=2),
                )
                raw = await self._call_llm(prompt)
                data = _parse_json_response(raw)
                assignments: list[dict] = data.get("assignments", [])
                if not assignments:
                    raise ValueError("LLM returned empty assignments list")
                logger.info(
                    "match_agents: produced %d assignments (attempt %d)",
                    len(assignments),
                    attempt + 1,
                )
                return {
                    "assignments": assignments,
                    "available_agents": available_agents,
                }
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                logger.warning(
                    "match_agents attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt == max_retries:
                    return {
                        "error": f"match_agents failed after {max_retries + 1} attempts: {exc}",
                        "assignments": [],
                        "available_agents": available_agents,
                    }

        return {"assignments": [], "error": "match_agents: unexpected exit"}

    async def _build_dag(self, state: OrchestratorState) -> dict[str, Any]:
        """LLM node: build a validated DAG from task assignments.

        Returns:
            Partial state update with ``graph_json`` (serialised DAG dict).
        """
        if state.get("error"):
            return {}

        assignments: list[dict] = state.get("assignments", [])
        sub_tasks: list[dict] = state.get("sub_tasks", [])

        if not assignments:
            return {"error": "build_dag: no assignments to build DAG from", "graph_json": "{}"}

        max_retries: int = 2
        for attempt in range(max_retries + 1):
            try:
                prompt = BUILD_DAG_PROMPT.format(
                    assignments_json=json.dumps(assignments, indent=2),
                    sub_tasks_json=json.dumps(sub_tasks, indent=2),
                )
                raw = await self._call_llm(prompt)
                dag = _parse_json_response(raw)

                # Validate DAG structure (detects cycles and missing nodes)
                from marketplace.services.orchestration_service import (
                    _topological_sort_layers,
                )

                _topological_sort_layers(dag)

                graph_json = json.dumps(dag)
                logger.info(
                    "build_dag: DAG with %d nodes validated (attempt %d)",
                    len(dag.get("nodes", {})),
                    attempt + 1,
                )
                return {"graph_json": graph_json}

            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                logger.warning(
                    "build_dag attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt == max_retries:
                    return {
                        "error": f"build_dag failed after {max_retries + 1} attempts: {exc}",
                        "graph_json": "{}",
                    }

        return {"graph_json": "{}", "error": "build_dag: unexpected exit"}

    async def _execute_chain(self, state: OrchestratorState) -> dict[str, Any]:
        """Execute the DAG via the orchestration service.

        Creates a transient WorkflowDefinition and executes it inline.
        Agent outputs are collected from the completed workflow execution.

        Returns:
            Partial state update with ``chain_execution_id`` and ``agent_outputs``.
        """
        if state.get("error"):
            return {}

        graph_json: str = state.get("graph_json", "{}")
        initiated_by: str = "smart_orchestrator"

        dag = json.loads(graph_json) if graph_json else {}
        if not dag.get("nodes"):
            return {
                "error": "execute_chain: empty DAG — nothing to execute",
                "chain_execution_id": "",
                "agent_outputs": {},
            }

        from marketplace.services.orchestration_service import (
            create_workflow,
            execute_workflow,
        )

        try:
            workflow = await create_workflow(
                self.db,
                name=f"smart-compose:{state.get('task_description', '')[:60]}",
                graph_json=graph_json,
                owner_id=initiated_by,
                description="Auto-generated workflow from SmartOrchestrator",
            )

            wf_execution = await execute_workflow(
                self.db,
                workflow_id=workflow.id,
                initiated_by=initiated_by,
                input_data={"task_description": state.get("task_description", "")},
            )

            # Parse node outputs from the completed workflow execution
            agent_outputs: dict = {}
            if wf_execution.output_json:
                try:
                    agent_outputs = json.loads(wf_execution.output_json)
                except (json.JSONDecodeError, TypeError):
                    agent_outputs = {}

            logger.info(
                "execute_chain: workflow %s finished with status=%s",
                wf_execution.id,
                wf_execution.status,
            )
            return {
                "chain_execution_id": wf_execution.id,
                "agent_outputs": agent_outputs,
            }

        except Exception as exc:
            logger.error("execute_chain: workflow execution failed: %s", exc)
            return {
                "error": f"execute_chain failed: {exc}",
                "chain_execution_id": "",
                "agent_outputs": {},
            }

    async def _synthesize_result(self, state: OrchestratorState) -> dict[str, Any]:
        """LLM node: synthesize agent outputs into a coherent final answer.

        Returns:
            Partial state update with ``final_result`` (str).
        """
        if state.get("error"):
            return {"final_result": f"Execution stopped due to error: {state['error']}"}

        agent_outputs: dict = state.get("agent_outputs", {})
        task_description: str = state.get("task_description", "")

        if not agent_outputs:
            return {"final_result": "No agent outputs were produced."}

        try:
            prompt = SYNTHESIZE_RESULT_PROMPT.format(
                task_description=task_description,
                outputs_json=json.dumps(agent_outputs, indent=2, default=str),
            )
            final_result = await self._call_llm(prompt)
            logger.info("synthesize_result: produced %d chars", len(final_result))
            return {"final_result": final_result}
        except Exception as exc:
            logger.error("synthesize_result: LLM call failed: %s", exc)
            # Return raw JSON as fallback
            return {
                "final_result": json.dumps(agent_outputs, indent=2, default=str)
            }

    # ------------------------------------------------------------------
    # Execution paths
    # ------------------------------------------------------------------

    async def _execute_with_langgraph(
        self,
        task_description: str,
        initiated_by: str,
    ) -> dict[str, Any]:
        """Execute the full LangGraph pipeline.

        Args:
            task_description: Free-text task to orchestrate.
            initiated_by: Caller identity for audit purposes.

        Returns:
            Structured result dict with sub_tasks, assignments, graph_json,
            final_result, error, and method="langgraph".
        """
        initial_state: OrchestratorState = {
            "task_description": task_description,
            "sub_tasks": [],
            "available_agents": [],
            "assignments": [],
            "graph_json": "",
            "plan_approved": self.auto_approve,
            "chain_execution_id": "",
            "agent_outputs": {},
            "final_result": "",
            "error": "",
            "retry_count": 0,
        }

        try:
            result: OrchestratorState = await self._graph.ainvoke(initial_state)
        except Exception as exc:
            logger.error("LangGraph execution failed: %s", exc)
            return {
                "task_description": task_description,
                "sub_tasks": [],
                "assignments": [],
                "graph_json": "",
                "final_result": "",
                "error": str(exc),
                "method": "langgraph",
            }

        return {
            "task_description": task_description,
            "sub_tasks": result.get("sub_tasks", []),
            "assignments": result.get("assignments", []),
            "graph_json": result.get("graph_json", ""),
            "chain_execution_id": result.get("chain_execution_id", ""),
            "final_result": result.get("final_result", ""),
            "error": result.get("error", ""),
            "method": "langgraph",
        }

    async def _execute_with_fallback(
        self,
        task_description: str,
        initiated_by: str,
    ) -> dict[str, Any]:
        """Fallback path: keyword-based capability extraction via auto_chain_service.

        This path works without LangGraph or an LLM client.

        Args:
            task_description: Free-text task description.
            initiated_by: Caller identity.

        Returns:
            Structured result dict with capabilities, assignments, and method="fallback".
        """
        from marketplace.services.auto_chain_service import (
            extract_capabilities,
            suggest_agents_for_capability,
        )

        capabilities = extract_capabilities(task_description)
        if not capabilities:
            logger.warning(
                "fallback: no capabilities extracted from task description"
            )
            return {
                "task_description": task_description,
                "capabilities": [],
                "assignments": [],
                "error": "Could not extract capabilities from task description",
                "method": "fallback",
            }

        assignments: list[dict] = []
        for cap in capabilities:
            try:
                agents = await suggest_agents_for_capability(
                    self.db, cap, max_results=1
                )
                if agents:
                    assignments.append(
                        {
                            "capability": cap,
                            "agent": agents[0],
                        }
                    )
                else:
                    logger.debug("fallback: no agents found for capability '%s'", cap)
            except Exception as exc:
                logger.warning(
                    "fallback: agent lookup for capability '%s' failed: %s", cap, exc
                )

        logger.info(
            "fallback: matched %d/%d capabilities to agents",
            len(assignments),
            len(capabilities),
        )
        return {
            "task_description": task_description,
            "capabilities": capabilities,
            "assignments": assignments,
            "error": "" if assignments else "No agents found for any capability",
            "method": "fallback",
        }

    # ------------------------------------------------------------------
    # LLM client abstraction
    # ------------------------------------------------------------------

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM client and return the response text.

        Supports:
        - OpenAI-compatible clients (``client.chat.completions.create``).
        - Async callables: ``async def f(prompt: str) -> str``.
        - Sync callables: ``def f(prompt: str) -> str``.

        Args:
            prompt: The full prompt string to send to the LLM.

        Returns:
            Raw text response from the model.

        Raises:
            ValueError: If no valid LLM client is configured.
        """
        if self.llm_client is None:
            raise ValueError("No LLM client configured")

        # OpenAI-style client
        if hasattr(self.llm_client, "chat") and hasattr(
            self.llm_client.chat, "completions"
        ):
            response = await self.llm_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return str(response.choices[0].message.content)

        # Async callable
        if callable(self.llm_client):
            if asyncio.iscoroutinefunction(self.llm_client):
                result = await self.llm_client(prompt)
            else:
                result = self.llm_client(prompt)
            return str(result)

        raise ValueError(
            "llm_client must be an OpenAI-compatible client or a callable"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_json_response(raw: str) -> dict:
    """Parse a JSON string from an LLM response, stripping markdown fences.

    Args:
        raw: Raw string returned by the LLM, possibly wrapped in ```json ... ```.

    Returns:
        Parsed dict.

    Raises:
        json.JSONDecodeError: If the response is not valid JSON after stripping.
        ValueError: If the parsed value is not a dict.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop opening fence (```json or ```) and closing fence (```)
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")
    return parsed
