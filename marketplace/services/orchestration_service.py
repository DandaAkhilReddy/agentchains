"""Orchestration Engine — DAG-based workflow execution for multi-agent pipelines.

Provides workflow CRUD, topological-sort execution with per-layer parallelism,
cost tracking with budget enforcement, and execution lifecycle management.
"""

import asyncio
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.models.workflow import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowNodeExecution,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------

async def create_workflow(
    db: AsyncSession,
    name: str,
    graph_json: str,
    owner_id: str,
    description: str = "",
    max_budget_usd: Decimal | None = None,
) -> WorkflowDefinition:
    """Create a new workflow definition."""
    workflow = WorkflowDefinition(
        name=name,
        graph_json=graph_json,
        owner_id=owner_id,
        description=description,
        max_budget_usd=max_budget_usd,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    logger.info("Created workflow '%s' (id=%s) for owner '%s'", name, workflow.id, owner_id)
    return workflow


async def get_workflow(db: AsyncSession, workflow_id: str) -> WorkflowDefinition | None:
    """Get a workflow definition by ID."""
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
    )
    return result.scalar_one_or_none()


async def list_workflows(
    db: AsyncSession,
    owner_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[WorkflowDefinition]:
    """List workflow definitions with optional filters."""
    query = select(WorkflowDefinition)
    if owner_id:
        query = query.where(WorkflowDefinition.owner_id == owner_id)
    if status:
        query = query.where(WorkflowDefinition.status == status)
    query = query.limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Execution lifecycle
# ---------------------------------------------------------------------------

async def execute_workflow(
    db: AsyncSession,
    workflow_id: str,
    initiated_by: str,
    input_data: dict | None = None,
) -> WorkflowExecution:
    """Start executing a workflow. Creates an execution record and runs the DAG."""
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        raise ValueError(f"Workflow not found: {workflow_id}")

    execution = WorkflowExecution(
        workflow_id=workflow_id,
        initiated_by=initiated_by,
        status="pending",
        input_json=json.dumps(input_data or {}),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    logger.info("Created execution '%s' for workflow '%s'", execution.id, workflow_id)

    # Run the DAG asynchronously
    try:
        await _run_dag(db, execution, workflow)
    except Exception as exc:
        execution.status = "failed"
        execution.error_message = str(exc)
        execution.completed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.error("Workflow execution '%s' failed: %s", execution.id, exc)

    return execution


async def get_execution(db: AsyncSession, execution_id: str) -> WorkflowExecution | None:
    """Get a workflow execution by ID."""
    result = await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
    )
    return result.scalar_one_or_none()


async def get_execution_nodes(
    db: AsyncSession, execution_id: str
) -> list[WorkflowNodeExecution]:
    """Get all node executions for a workflow execution."""
    result = await db.execute(
        select(WorkflowNodeExecution)
        .where(WorkflowNodeExecution.execution_id == execution_id)
        .order_by(WorkflowNodeExecution.started_at)
    )
    return list(result.scalars().all())


async def pause_execution(db: AsyncSession, execution_id: str) -> bool:
    """Pause a running execution."""
    execution = await get_execution(db, execution_id)
    if not execution or execution.status != "running":
        return False
    execution.status = "paused"
    await db.commit()
    logger.info("Paused execution '%s'", execution_id)
    return True


async def resume_execution(db: AsyncSession, execution_id: str) -> bool:
    """Resume a paused execution."""
    execution = await get_execution(db, execution_id)
    if not execution or execution.status != "paused":
        return False
    execution.status = "running"
    await db.commit()
    logger.info("Resumed execution '%s'", execution_id)
    return True


async def cancel_execution(db: AsyncSession, execution_id: str) -> bool:
    """Cancel a pending or running execution."""
    execution = await get_execution(db, execution_id)
    if not execution or execution.status not in ("pending", "running", "paused"):
        return False
    execution.status = "cancelled"
    execution.completed_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("Cancelled execution '%s'", execution_id)
    return True


async def get_execution_cost(db: AsyncSession, execution_id: str) -> Decimal:
    """Get the total cost of a workflow execution from its node executions."""
    result = await db.execute(
        select(WorkflowNodeExecution)
        .where(WorkflowNodeExecution.execution_id == execution_id)
    )
    nodes = list(result.scalars().all())
    return sum((node.cost_usd or Decimal("0")) for node in nodes)


# ---------------------------------------------------------------------------
# DAG execution internals
# ---------------------------------------------------------------------------

def _topological_sort_layers(graph: dict) -> list[list[dict]]:
    """Parse a DAG graph into execution layers using Kahn's algorithm.

    Each layer contains nodes whose dependencies are all in previous layers,
    enabling parallel execution within a layer.

    Expected graph format:
    {
        "nodes": {
            "node_id": {"type": "agent_call", "config": {...}, "depends_on": ["other_node_id"]}
        },
        "edges": [{"from": "a", "to": "b"}]  // optional, deps can also be in nodes
    }
    """
    nodes: dict[str, dict] = graph.get("nodes", {})
    edges: list[dict] = graph.get("edges", [])

    # Build adjacency and in-degree from both edges and depends_on
    in_degree: dict[str, int] = {nid: 0 for nid in nodes}
    dependents: dict[str, list[str]] = defaultdict(list)

    # Process explicit edges
    for edge in edges:
        src, dst = edge["from"], edge["to"]
        in_degree[dst] = in_degree.get(dst, 0) + 1
        dependents[src].append(dst)

    # Process depends_on within node definitions
    for nid, ndef in nodes.items():
        for dep in ndef.get("depends_on", []):
            if dep in nodes:
                in_degree[nid] = in_degree.get(nid, 0) + 1
                dependents[dep].append(nid)

    # Kahn's algorithm — layer by layer
    layers: list[list[dict]] = []
    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)

    while queue:
        layer_ids = list(queue)
        queue.clear()

        layer: list[dict] = []
        for nid in layer_ids:
            node_def = dict(nodes[nid])
            node_def["_node_id"] = nid
            layer.append(node_def)

            for dependent in dependents.get(nid, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        layers.append(layer)

    # Check for cycles
    total_scheduled = sum(len(layer) for layer in layers)
    if total_scheduled < len(nodes):
        unvisited = [nid for nid in nodes if in_degree.get(nid, 0) > 0]
        raise ValueError(f"Cycle detected in workflow DAG. Unresolved nodes: {unvisited}")

    return layers


async def _run_dag(
    db: AsyncSession,
    execution: WorkflowExecution,
    workflow: WorkflowDefinition,
) -> None:
    """Internal: parse the workflow graph and execute layer-by-layer."""
    execution.status = "running"
    execution.started_at = datetime.now(timezone.utc)
    await db.commit()

    graph = json.loads(workflow.graph_json)
    layers = _topological_sort_layers(graph)

    max_budget = Decimal(str(workflow.max_budget_usd)) if workflow.max_budget_usd else None
    total_cost = Decimal("0")
    node_outputs: dict[str, dict] = {}  # node_id -> output_data

    input_data = json.loads(execution.input_json) if execution.input_json else {}

    for layer_idx, layer in enumerate(layers):
        # Check if execution was paused or cancelled
        await db.refresh(execution)
        if execution.status in ("paused", "cancelled"):
            logger.info("Execution '%s' is %s, stopping DAG", execution.id, execution.status)
            return

        logger.info(
            "Executing layer %d/%d (%d nodes) for execution '%s'",
            layer_idx + 1,
            len(layers),
            len(layer),
            execution.id,
        )

        # Build input for each node from its dependencies' outputs
        async def _run_node(node_def: dict) -> tuple[str, dict]:
            node_id = node_def["_node_id"]
            deps = node_def.get("depends_on", [])

            # Merge workflow input with dependency outputs
            node_input = dict(input_data)
            for dep_id in deps:
                if dep_id in node_outputs:
                    node_input[dep_id] = node_outputs[dep_id]

            result = await _execute_node(db, execution.id, node_def, node_input)
            return node_id, result

        # Execute all nodes in this layer concurrently
        tasks = [_run_node(node_def) for node_def in layer]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                execution.status = "failed"
                execution.error_message = str(result)
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()
                raise result

            node_id, output = result
            node_outputs[node_id] = output

        # Update total cost and check budget
        total_cost = await get_execution_cost(db, execution.id)
        execution.total_cost_usd = total_cost
        await db.commit()

        if max_budget and total_cost > max_budget:
            execution.status = "failed"
            execution.error_message = (
                f"Budget exceeded: ${total_cost} > max ${max_budget}"
            )
            execution.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.warning("Execution '%s' exceeded budget", execution.id)
            return

    # All layers completed successfully
    execution.status = "completed"
    execution.output_json = json.dumps(node_outputs, default=str)
    execution.total_cost_usd = total_cost
    execution.completed_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("Execution '%s' completed. Total cost: $%s", execution.id, total_cost)


async def _execute_node(
    db: AsyncSession,
    execution_id: str,
    node_def: dict,
    input_data: dict,
) -> dict:
    """Dispatch a single node execution based on its type.

    Supported node types:
    - agent_call: HTTP POST to an agent's endpoint
    - condition: Evaluate a JSONPath-like expression
    - parallel_group: Execute sub-nodes in parallel (handled by layer structure)
    - loop: Iterate over input data
    - human_approval: Pause execution for manual approval
    - subworkflow: Trigger another workflow
    """
    node_id = node_def["_node_id"]
    node_type = node_def.get("type", "agent_call")
    config = node_def.get("config", {})

    # Create node execution record
    node_exec = WorkflowNodeExecution(
        execution_id=execution_id,
        node_id=node_id,
        node_type=node_type,
        status="running",
        input_json=json.dumps(input_data, default=str),
        started_at=datetime.now(timezone.utc),
    )
    db.add(node_exec)
    await db.commit()
    await db.refresh(node_exec)

    try:
        if node_type == "agent_call":
            result = await _execute_agent_call(config, input_data)

        elif node_type == "condition":
            result = _execute_condition(config, input_data)

        elif node_type == "human_approval":
            result = await _execute_human_approval(db, execution_id, node_id, config)

        elif node_type == "loop":
            result = await _execute_loop(db, execution_id, config, input_data)

        elif node_type == "subworkflow":
            result = await _execute_subworkflow(db, config, input_data)

        elif node_type == "parallel_group":
            # Parallel groups are handled by the layer structure; treat as pass-through
            result = {"status": "completed", "data": input_data}

        else:
            result = {"error": f"Unknown node type: {node_type}"}

        node_exec.status = "completed"
        node_exec.output_json = json.dumps(result, default=str)
        node_exec.cost_usd = Decimal(str(result.get("_cost", 0)))
        node_exec.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return result

    except Exception as exc:
        node_exec.status = "failed"
        node_exec.error_message = str(exc)
        node_exec.completed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.error("Node '%s' in execution '%s' failed: %s", node_id, execution_id, exc)
        raise


async def _execute_agent_call(config: dict, input_data: dict) -> dict:
    """Call a remote agent endpoint via HTTP POST."""
    endpoint = config.get("endpoint", "")
    method = config.get("method", "POST").upper()
    headers = config.get("headers", {})
    timeout = config.get("timeout", 30.0)

    if not endpoint:
        return {"error": "No endpoint configured for agent_call node"}

    payload = {**input_data, **config.get("payload", {})}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                resp = await client.get(endpoint, headers=headers, params=payload)
            else:
                resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    except httpx.HTTPStatusError as exc:
        return {"error": f"Agent call failed: HTTP {exc.response.status_code}"}
    except (httpx.RequestError, Exception) as exc:
        return {"error": f"Agent call failed: {exc}"}


def _execute_condition(config: dict, input_data: dict) -> dict:
    """Evaluate a simple JSONPath-like condition expression.

    Config format:
    {
        "field": "some.nested.field",
        "operator": "eq" | "neq" | "gt" | "lt" | "gte" | "lte" | "in" | "contains",
        "value": <expected_value>,
        "then_branch": "node_id_if_true",
        "else_branch": "node_id_if_false"
    }
    """
    field_path = config.get("field", "")
    operator = config.get("operator", "eq")
    expected = config.get("value")

    # Resolve the field value from input_data using dot notation
    actual = input_data
    for key in field_path.split("."):
        if isinstance(actual, dict):
            actual = actual.get(key)
        else:
            actual = None
            break

    # Evaluate the condition
    operators = {
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
        "gt": lambda a, b: a is not None and b is not None and a > b,
        "lt": lambda a, b: a is not None and b is not None and a < b,
        "gte": lambda a, b: a is not None and b is not None and a >= b,
        "lte": lambda a, b: a is not None and b is not None and a <= b,
        "in": lambda a, b: a in b if b is not None else False,
        "contains": lambda a, b: b in a if a is not None else False,
    }

    evaluator = operators.get(operator, operators["eq"])
    condition_met = evaluator(actual, expected)

    return {
        "condition_met": condition_met,
        "field": field_path,
        "actual_value": actual,
        "selected_branch": config.get("then_branch") if condition_met else config.get("else_branch"),
    }


async def _execute_human_approval(
    db: AsyncSession,
    execution_id: str,
    node_id: str,
    config: dict,
) -> dict:
    """Pause execution and wait for human approval.

    In a real system this would send a notification and wait for a callback.
    For now, it sets the execution to paused.
    """
    execution = await get_execution(db, execution_id)
    if execution:
        execution.status = "paused"
        await db.commit()

    return {
        "status": "awaiting_approval",
        "message": config.get("message", "Human approval required"),
        "node_id": node_id,
    }


async def _execute_loop(
    db: AsyncSession,
    execution_id: str,
    config: dict,
    input_data: dict,
) -> dict:
    """Execute a loop node that iterates over a collection in the input data.

    Config format:
    {
        "iterator_field": "items",
        "body_endpoint": "http://...",
        "max_iterations": 100
    }
    """
    iterator_field = config.get("iterator_field", "items")
    items = input_data.get(iterator_field, [])
    max_iterations = config.get("max_iterations", 100)
    body_endpoint = config.get("body_endpoint", "")

    if not isinstance(items, list):
        return {"error": f"Iterator field '{iterator_field}' is not a list"}

    results = []
    for i, item in enumerate(items[:max_iterations]):
        if body_endpoint:
            result = await _execute_agent_call(
                {"endpoint": body_endpoint},
                {"item": item, "index": i},
            )
        else:
            result = {"item": item, "index": i}
        results.append(result)

    return {"iterations": len(results), "results": results}


async def _execute_subworkflow(
    db: AsyncSession,
    config: dict,
    input_data: dict,
) -> dict:
    """Trigger another workflow as a sub-execution.

    Config format:
    {
        "workflow_id": "...",
        "initiated_by": "..."
    }
    """
    sub_workflow_id = config.get("workflow_id")
    initiated_by = config.get("initiated_by", "system")

    if not sub_workflow_id:
        return {"error": "No workflow_id configured for subworkflow node"}

    sub_execution = await execute_workflow(
        db,
        sub_workflow_id,
        initiated_by,
        input_data=input_data,
    )
    return {
        "sub_execution_id": sub_execution.id,
        "status": sub_execution.status,
        "output": json.loads(sub_execution.output_json) if sub_execution.output_json else {},
    }


class OrchestrationService:
    """Class wrapper for orchestration service functions."""

    async def create_workflow(self, db, **kwargs):
        return await create_workflow(db, **kwargs)

    async def execute_workflow(self, db, **kwargs):
        return await execute_workflow(db, **kwargs)

    async def get_execution(self, db, execution_id):
        return await get_execution(db, execution_id)
