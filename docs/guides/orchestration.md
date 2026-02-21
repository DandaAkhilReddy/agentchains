# Orchestration Engine Guide

## Overview

The AgentChains Orchestration Engine enables multi-agent workflow execution using DAG (Directed Acyclic Graph) definitions. Workflows compose multiple agents into pipelines with parallel fan-out, conditional branching, loops, and human-in-the-loop approvals.

## Concepts

### Workflow Definition

A workflow is a JSON DAG containing nodes and edges:

```json
{
  "name": "Research Pipeline",
  "description": "Multi-agent research workflow",
  "nodes": [
    {
      "id": "search",
      "type": "agent_call",
      "agent_id": "agent-search-001",
      "config": { "query": "{{input.topic}}" }
    },
    {
      "id": "summarize",
      "type": "agent_call",
      "agent_id": "agent-summary-001",
      "config": { "max_length": 500 }
    },
    {
      "id": "review",
      "type": "human_approval",
      "config": { "message": "Approve research summary?" }
    }
  ],
  "edges": [
    { "from": "search", "to": "summarize" },
    { "from": "summarize", "to": "review" }
  ]
}
```

### Node Types

| Type | Description |
|------|-------------|
| `agent_call` | Invokes an agent via the A2A protocol |
| `condition` | Evaluates JSONPath expression to choose a branch |
| `parallel_group` | Fans out to multiple nodes concurrently |
| `loop` | Repeats nodes until a condition is met |
| `human_approval` | Pauses and emits a WebSocket event for user approval |
| `subworkflow` | Invokes another workflow definition |

### Execution Model

1. **Parse**: Validate DAG structure, detect cycles
2. **Topological Sort**: Order nodes by dependency layers
3. **Execute Per Layer**: Use `asyncio.gather` for parallel nodes in the same layer
4. **Persist State**: Save node results after each execution
5. **Cost Tracking**: Accumulate token/compute costs, abort if budget exceeded
6. **Circuit Breaker**: Per-agent circuit breaker (closed → open → half-open)

## API Endpoints

All endpoints are under `/api/v3/orchestration/`.

### Workflow Management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/workflows` | Create a workflow definition |
| GET | `/workflows` | List all workflow definitions |
| GET | `/workflows/{id}` | Get workflow definition |
| PUT | `/workflows/{id}` | Update workflow definition |
| DELETE | `/workflows/{id}` | Delete workflow definition |

### Execution

| Method | Path | Description |
|--------|------|-------------|
| POST | `/workflows/{id}/execute` | Start workflow execution |
| GET | `/executions/{id}` | Get execution status |
| POST | `/executions/{id}/pause` | Pause running execution |
| POST | `/executions/{id}/resume` | Resume paused execution |
| POST | `/executions/{id}/cancel` | Cancel execution |
| GET | `/executions/{id}/nodes` | Get per-node statuses |
| GET | `/executions/{id}/cost` | Get execution cost breakdown |
| GET | `/templates` | List workflow templates |

## Circuit Breaker

The circuit breaker prevents cascading failures:

- **Closed** (normal): Requests pass through, failures are counted
- **Open** (tripped): All requests fail immediately for `recovery_timeout` seconds
- **Half-Open** (testing): One request allowed through to test recovery

Configuration:
```python
CircuitBreaker(
    failure_threshold=5,       # failures before opening
    recovery_timeout=30.0,     # seconds in open state
    half_open_max_calls=1      # test calls in half-open
)
```

## Example: Parallel Research

```python
import httpx

workflow = {
    "name": "Parallel Research",
    "nodes": [
        {"id": "web", "type": "agent_call", "agent_id": "web-search"},
        {"id": "academic", "type": "agent_call", "agent_id": "academic-search"},
        {"id": "merge", "type": "agent_call", "agent_id": "summarizer"},
        {"id": "approve", "type": "human_approval", "config": {"message": "Publish?"}}
    ],
    "edges": [
        {"from": "web", "to": "merge"},
        {"from": "academic", "to": "merge"},
        {"from": "merge", "to": "approve"}
    ]
}

async with httpx.AsyncClient() as client:
    # Create workflow
    r = await client.post("/api/v3/orchestration/workflows", json=workflow)
    wf_id = r.json()["id"]

    # Execute with input
    r = await client.post(
        f"/api/v3/orchestration/workflows/{wf_id}/execute",
        json={"input": {"topic": "quantum computing"}, "max_budget": 1.00}
    )
    exec_id = r.json()["execution_id"]

    # Check status
    r = await client.get(f"/api/v3/orchestration/executions/{exec_id}")
    print(r.json()["status"])  # "running" | "paused" | "completed"
```

## Cost Control

Set `max_budget` when executing a workflow. The engine tracks cumulative costs across all node executions and aborts if the budget is exceeded.

## MCP Integration

Two MCP tools integrate with the orchestration engine:

- `workflow_execute` — Start a workflow from MCP
- `workflow_status` — Check execution status from MCP
