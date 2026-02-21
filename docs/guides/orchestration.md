# Orchestration Engine Guide

Build and execute multi-agent workflows using DAG-based orchestration with cost tracking, budget limits, and circuit breaker protection.

---

## 1. Overview

The AgentChains Orchestration Engine enables composing multiple AI agents into pipelines defined as Directed Acyclic Graphs (DAGs). The engine handles dependency resolution via topological sorting, parallel execution within layers, per-node cost tracking, budget enforcement, and execution lifecycle management (pause, resume, cancel).

### Key Capabilities

- DAG-based workflow definitions with JSON graph format
- 6 node types: agent_call, condition, parallel_group, loop, human_approval, subworkflow
- Layer-by-layer execution with `asyncio.gather` for parallelism
- Per-execution cost tracking with budget enforcement
- Pause/resume/cancel execution lifecycle
- Cycle detection via Kahn's algorithm
- Nested subworkflow support

---

## 2. Core Concepts

### 2.1 Workflow Definition

A workflow is a persistent `WorkflowDefinition` record containing a JSON graph:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Auto-generated primary key |
| `name` | string(200) | Human-readable workflow name |
| `description` | text | Optional description |
| `graph_json` | text | JSON DAG definition (nodes + edges) |
| `owner_id` | string(36) | Agent or creator who owns the workflow |
| `version` | integer | Workflow version (default: 1) |
| `status` | string(20) | `draft`, `active`, `archived` |
| `max_budget_usd` | decimal(12,4) | Maximum allowed execution cost |

### 2.2 Workflow Execution

Each execution of a workflow creates a `WorkflowExecution` record:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Auto-generated primary key |
| `workflow_id` | UUID (FK) | Reference to the workflow definition |
| `initiated_by` | string(36) | Agent or user that started the execution |
| `status` | string(20) | `pending`, `running`, `paused`, `completed`, `failed`, `cancelled` |
| `input_json` | text | Input data for the execution |
| `output_json` | text | Final output from all nodes |
| `total_cost_usd` | decimal(12,6) | Cumulative cost across all nodes |
| `started_at` | datetime | When execution began |
| `completed_at` | datetime | When execution finished |
| `error_message` | text | Error details if failed |

### 2.3 Node Execution

Each node in the DAG creates a `WorkflowNodeExecution` record:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Auto-generated primary key |
| `execution_id` | UUID (FK) | Parent execution |
| `node_id` | string(100) | Node identifier from the graph |
| `node_type` | string(30) | Node type (agent_call, condition, etc.) |
| `status` | string(20) | `pending`, `running`, `completed`, `failed` |
| `input_json` | text | Input data passed to this node |
| `output_json` | text | Output data from this node |
| `cost_usd` | decimal(12,6) | Cost attributed to this node |
| `attempt` | integer | Retry attempt number (default: 1) |

---

## 3. Node Types

### 3.1 `agent_call`

Invokes a remote agent endpoint via HTTP POST (or GET).

**Config:**

```json
{
  "type": "agent_call",
  "config": {
    "endpoint": "https://agent.example.com/api/run",
    "method": "POST",
    "headers": {"Authorization": "Bearer sk-..."},
    "payload": {"extra_param": "value"},
    "timeout": 30.0
  }
}
```

| Config Key | Type | Default | Description |
|-----------|------|---------|-------------|
| `endpoint` | string | (required) | HTTP URL for the agent |
| `method` | string | `POST` | HTTP method (GET or POST) |
| `headers` | object | `{}` | Additional HTTP headers |
| `payload` | object | `{}` | Extra payload fields merged with node input |
| `timeout` | float | `30.0` | Request timeout in seconds |

The node input is merged with `config.payload` and sent as the request body. For GET requests, merged data is sent as query parameters.

### 3.2 `condition`

Evaluates a JSONPath-like expression on the input data to choose a branch.

**Config:**

```json
{
  "type": "condition",
  "config": {
    "field": "search.result_count",
    "operator": "gt",
    "value": 0,
    "then_branch": "process_results",
    "else_branch": "no_results_handler"
  }
}
```

| Config Key | Type | Description |
|-----------|------|-------------|
| `field` | string | Dot-notation path into input data |
| `operator` | string | Comparison operator |
| `value` | any | Expected value to compare against |
| `then_branch` | string | Node ID to activate if condition is true |
| `else_branch` | string | Node ID to activate if condition is false |

**Supported Operators:**

| Operator | Description |
|----------|-------------|
| `eq` | Equal (default) |
| `neq` | Not equal |
| `gt` | Greater than |
| `lt` | Less than |
| `gte` | Greater than or equal |
| `lte` | Less than or equal |
| `in` | Value is in the expected list |
| `contains` | Actual value contains expected |

**Output:**

```json
{
  "condition_met": true,
  "field": "search.result_count",
  "actual_value": 42,
  "selected_branch": "process_results"
}
```

### 3.3 `parallel_group`

A pass-through node that signals parallel fan-out. The actual parallelism is handled by the layer-based execution model -- nodes without mutual dependencies are automatically executed concurrently.

**Config:**

```json
{
  "type": "parallel_group",
  "config": {}
}
```

**Output:**

```json
{"status": "completed", "data": { ... }}
```

### 3.4 `loop`

Iterates over a collection in the input data, optionally calling an endpoint for each item.

**Config:**

```json
{
  "type": "loop",
  "config": {
    "iterator_field": "items",
    "body_endpoint": "https://agent.example.com/api/process",
    "max_iterations": 100
  }
}
```

| Config Key | Type | Default | Description |
|-----------|------|---------|-------------|
| `iterator_field` | string | `items` | Key in input data containing the list |
| `body_endpoint` | string | `""` | Optional endpoint to call per item |
| `max_iterations` | integer | `100` | Maximum iterations (safety limit) |

If `body_endpoint` is empty, each item is passed through as-is.

**Output:**

```json
{
  "iterations": 5,
  "results": [
    {"item": "value1", "index": 0, "response": "..."},
    {"item": "value2", "index": 1, "response": "..."}
  ]
}
```

### 3.5 `human_approval`

Pauses the execution and waits for manual approval. Sets the execution status to `paused`.

**Config:**

```json
{
  "type": "human_approval",
  "config": {
    "message": "Please review and approve the research summary."
  }
}
```

**Output:**

```json
{
  "status": "awaiting_approval",
  "message": "Please review and approve the research summary.",
  "node_id": "review_step"
}
```

To resume execution after approval, call `resume_execution()`.

### 3.6 `subworkflow`

Triggers another workflow as a nested execution.

**Config:**

```json
{
  "type": "subworkflow",
  "config": {
    "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
    "initiated_by": "system"
  }
}
```

| Config Key | Type | Description |
|-----------|------|-------------|
| `workflow_id` | string | ID of the workflow definition to execute |
| `initiated_by` | string | Identity for the sub-execution (default: `system`) |

The current node's input data is passed as input to the subworkflow.

**Output:**

```json
{
  "sub_execution_id": "uuid",
  "status": "completed",
  "output": { ... }
}
```

---

## 4. Creating Workflows via API

### 4.1 Create a Workflow

```python
import httpx

workflow_def = {
    "name": "Research Pipeline",
    "description": "Search, analyze, and summarize research findings",
    "max_budget_usd": 5.00,
    "graph_json": {
        "nodes": {
            "search": {
                "type": "agent_call",
                "config": {
                    "endpoint": "https://search-agent.example.com/api/search",
                    "timeout": 15.0
                }
            },
            "check_results": {
                "type": "condition",
                "config": {
                    "field": "search.result_count",
                    "operator": "gt",
                    "value": 0,
                    "then_branch": "analyze",
                    "else_branch": "no_results"
                },
                "depends_on": ["search"]
            },
            "analyze": {
                "type": "agent_call",
                "config": {
                    "endpoint": "https://analysis-agent.example.com/api/analyze"
                },
                "depends_on": ["check_results"]
            },
            "no_results": {
                "type": "agent_call",
                "config": {
                    "endpoint": "https://fallback-agent.example.com/api/suggest"
                },
                "depends_on": ["check_results"]
            },
            "review": {
                "type": "human_approval",
                "config": {
                    "message": "Approve the analysis report?"
                },
                "depends_on": ["analyze"]
            }
        },
        "edges": []
    }
}

async with httpx.AsyncClient(base_url="https://api.agentchains.com") as client:
    resp = await client.post(
        "/api/v3/orchestration/workflows",
        json=workflow_def,
        headers={"Authorization": f"Bearer {token}"},
    )
    workflow = resp.json()
    print(f"Created workflow: {workflow['id']}")
```

### 4.2 Execute a Workflow

```python
resp = await client.post(
    f"/api/v3/orchestration/workflows/{workflow['id']}/execute",
    json={
        "input": {"topic": "quantum computing breakthroughs 2026"},
        "initiated_by": agent_id,
    },
    headers={"Authorization": f"Bearer {token}"},
)
execution = resp.json()
print(f"Execution started: {execution['id']}")
```

### 4.3 Check Execution Status

```python
resp = await client.get(
    f"/api/v3/orchestration/executions/{execution['id']}",
    headers={"Authorization": f"Bearer {token}"},
)
status = resp.json()
print(f"Status: {status['status']}")
print(f"Cost so far: ${status['total_cost_usd']}")
```

### 4.4 Get Node-Level Details

```python
resp = await client.get(
    f"/api/v3/orchestration/executions/{execution['id']}/nodes",
    headers={"Authorization": f"Bearer {token}"},
)
nodes = resp.json()
for node in nodes:
    print(f"  {node['node_id']}: {node['status']} (${node['cost_usd']})")
```

### 4.5 Pause, Resume, and Cancel

```python
# Pause a running execution
await client.post(f"/api/v3/orchestration/executions/{exec_id}/pause")

# Resume a paused execution
await client.post(f"/api/v3/orchestration/executions/{exec_id}/resume")

# Cancel an execution
await client.post(f"/api/v3/orchestration/executions/{exec_id}/cancel")
```

---

## 5. API Endpoints

All endpoints are under `/api/v3/orchestration/`.

### Workflow Management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/workflows` | Create a workflow definition |
| GET | `/workflows` | List workflows (filter by `owner_id`, `status`) |
| GET | `/workflows/{id}` | Get a single workflow |
| PUT | `/workflows/{id}` | Update workflow definition |
| DELETE | `/workflows/{id}` | Delete workflow |

### Execution Management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/workflows/{id}/execute` | Start workflow execution |
| GET | `/executions/{id}` | Get execution status |
| POST | `/executions/{id}/pause` | Pause running execution |
| POST | `/executions/{id}/resume` | Resume paused execution |
| POST | `/executions/{id}/cancel` | Cancel execution |
| GET | `/executions/{id}/nodes` | Get per-node execution details |
| GET | `/executions/{id}/cost` | Get execution cost breakdown |

### Templates

| Method | Path | Description |
|--------|------|-------------|
| GET | `/templates` | List pre-built workflow templates |

---

## 6. Cost Tracking and Budget Limits

### 6.1 How Cost Tracking Works

Each node execution can report a cost via the `_cost` field in its output:

```json
{
  "result": "analysis complete",
  "_cost": 0.05
}
```

The orchestration engine:
1. Reads `_cost` from each node's output.
2. Stores it in `WorkflowNodeExecution.cost_usd`.
3. Sums all node costs after each layer completes.
4. Updates `WorkflowExecution.total_cost_usd`.

### 6.2 Budget Enforcement

Set `max_budget_usd` when creating a workflow definition:

```python
workflow = await create_workflow(
    db=db,
    name="Expensive Pipeline",
    graph_json=graph,
    owner_id=agent_id,
    max_budget_usd=Decimal("10.00"),
)
```

If the cumulative cost exceeds the budget after any layer completes, the execution is immediately stopped with status `failed` and an error message:

```
Budget exceeded: $10.50 > max $10.00
```

### 6.3 Cost Query

```python
from marketplace.services.orchestration_service import get_execution_cost

total = await get_execution_cost(db, execution_id)
print(f"Total cost: ${total}")
```

---

## 7. Circuit Breaker Configuration

The circuit breaker prevents cascading failures when agents are unavailable:

```
[Closed] --failure_count >= threshold--> [Open]
[Open]   --recovery_timeout elapsed----> [Half-Open]
[Half-Open] --success--> [Closed]
[Half-Open] --failure--> [Open]
```

### Configuration

```python
CircuitBreaker(
    failure_threshold=5,       # Failures before tripping open
    recovery_timeout=30.0,     # Seconds in open state before half-open
    half_open_max_calls=1,     # Test calls allowed in half-open
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `failure_threshold` | 5 | Consecutive failures before opening |
| `recovery_timeout` | 30.0 | Seconds to wait before attempting recovery |
| `half_open_max_calls` | 1 | Number of test requests in half-open state |

---

## 8. Execution Model (Internals)

### 8.1 Topological Sort

The `_topological_sort_layers()` function uses Kahn's algorithm to sort the DAG into execution layers:

1. Build in-degree map from both `edges` and `depends_on` declarations.
2. Start with all zero-in-degree nodes (first layer).
3. Process each layer, decrementing dependent nodes' in-degrees.
4. Repeat until all nodes are scheduled.
5. If any nodes remain unscheduled, raise a cycle detection error.

### 8.2 Layer Execution

Each layer is executed with `asyncio.gather()`:

```python
tasks = [_run_node(node_def) for node_def in layer]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

Nodes within the same layer have no dependencies on each other and run concurrently.

### 8.3 Data Flow

- **Workflow input**: Passed as base input to all nodes.
- **Dependency outputs**: Each node receives its dependencies' outputs via the `node_outputs` dict, keyed by node ID.
- **Merged input**: `{**workflow_input, dep_id_1: dep_output_1, dep_id_2: dep_output_2, ...}`

### 8.4 Error Handling

- If any node in a layer raises an exception, the execution is immediately marked as `failed`.
- The error message is stored in both `WorkflowExecution.error_message` and `WorkflowNodeExecution.error_message`.
- Remaining layers are not executed.

---

## 9. Examples

### 9.1 Parallel Fan-Out and Merge

```json
{
  "nodes": {
    "web_search": {
      "type": "agent_call",
      "config": {"endpoint": "https://web-search.example.com/api/search"}
    },
    "academic_search": {
      "type": "agent_call",
      "config": {"endpoint": "https://academic.example.com/api/search"}
    },
    "merge_results": {
      "type": "agent_call",
      "config": {"endpoint": "https://merger.example.com/api/merge"},
      "depends_on": ["web_search", "academic_search"]
    },
    "human_review": {
      "type": "human_approval",
      "config": {"message": "Review merged results before publishing"},
      "depends_on": ["merge_results"]
    }
  }
}
```

**Execution layers:**
1. Layer 1: `web_search` + `academic_search` (parallel)
2. Layer 2: `merge_results`
3. Layer 3: `human_review`

### 9.2 Conditional Branching

```json
{
  "nodes": {
    "classify": {
      "type": "agent_call",
      "config": {"endpoint": "https://classifier.example.com/api/classify"}
    },
    "check_category": {
      "type": "condition",
      "config": {
        "field": "classify.category",
        "operator": "eq",
        "value": "premium",
        "then_branch": "premium_handler",
        "else_branch": "standard_handler"
      },
      "depends_on": ["classify"]
    },
    "premium_handler": {
      "type": "agent_call",
      "config": {"endpoint": "https://premium.example.com/api/process"},
      "depends_on": ["check_category"]
    },
    "standard_handler": {
      "type": "agent_call",
      "config": {"endpoint": "https://standard.example.com/api/process"},
      "depends_on": ["check_category"]
    }
  }
}
```

### 9.3 Loop with Processing

```json
{
  "nodes": {
    "fetch_items": {
      "type": "agent_call",
      "config": {"endpoint": "https://data.example.com/api/list"}
    },
    "process_each": {
      "type": "loop",
      "config": {
        "iterator_field": "items",
        "body_endpoint": "https://processor.example.com/api/process",
        "max_iterations": 50
      },
      "depends_on": ["fetch_items"]
    },
    "summarize": {
      "type": "agent_call",
      "config": {"endpoint": "https://summary.example.com/api/summarize"},
      "depends_on": ["process_each"]
    }
  }
}
```

---

## 10. MCP Integration

Two MCP tools provide access to the orchestration engine:

| Tool | Description |
|------|-------------|
| `workflow_execute` | Start a workflow execution from within an MCP session |
| `workflow_status` | Check the status and cost of an execution from MCP |
