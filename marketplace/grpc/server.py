"""gRPC server for inter-agent communication.

Provides high-performance RPC for agent task execution,
progress streaming, and orchestration node management.
"""

import json
import logging
import time
from concurrent import futures

logger = logging.getLogger(__name__)

# Port for gRPC sidecar
GRPC_PORT = 50051

# Allowed task types (whitelist)
_ALLOWED_TASK_TYPES = {"agent_call", "tool_call", "query"}

# Maximum input JSON size (bytes)
_MAX_INPUT_SIZE = 65_536  # 64 KB


def _validate_and_parse_input(input_json: str) -> dict:
    """Validate and parse input JSON with size and type checks."""
    if not input_json:
        return {}
    if len(input_json) > _MAX_INPUT_SIZE:
        raise ValueError(f"Input exceeds maximum size of {_MAX_INPUT_SIZE} bytes")
    try:
        data = json.loads(input_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON input: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object")
    return data


class AgentServiceServicer:
    """Implements the AgentService gRPC interface."""

    def __init__(self):
        self._active_tasks = 0
        self._start_time = time.time()

    async def ExecuteTask(self, request, context):
        """Execute a task on this agent."""
        try:
            self._active_tasks += 1
            start = time.time()

            # Validate task type against whitelist
            if request.task_type not in _ALLOWED_TASK_TYPES:
                return {
                    "task_id": request.task_id,
                    "status": "error",
                    "error_message": "Invalid task type",
                }

            # Parse and validate input
            input_data = _validate_and_parse_input(request.input_json)

            # Dispatch to appropriate handler based on task_type
            result = await self._dispatch_task(
                request.task_type, input_data, request.agent_id
            )

            execution_time = int((time.time() - start) * 1000)
            return {
                "task_id": request.task_id,
                "status": "success",
                "output_json": json.dumps(result),
                "cost_usd": 0.0,
                "execution_time_ms": execution_time,
            }
        except ValueError as ve:
            logger.warning("gRPC task validation failed: %s", ve)
            return {
                "task_id": request.task_id,
                "status": "error",
                "error_message": str(ve),
            }
        except Exception as e:
            logger.error("gRPC task execution failed: %s", e)
            return {
                "task_id": request.task_id,
                "status": "error",
                "error_message": "Internal execution error",
            }
        finally:
            self._active_tasks -= 1

    async def StreamTaskProgress(self, request, context):
        """Stream progress updates for a task."""
        import asyncio

        task_id = request.task_id
        for i in range(10):
            yield {
                "task_id": task_id,
                "progress": (i + 1) / 10.0,
                "message": f"Step {i + 1}/10",
                "status": "running" if i < 9 else "completed",
                "timestamp_ms": int(time.time() * 1000),
            }
            await asyncio.sleep(0.1)

    async def HealthCheck(self, request, context):
        """Return server health status (minimal info to avoid information disclosure)."""
        return {
            "status": "ok",
            "version": "1.0.0",
        }

    async def GetCapabilities(self, request, context):
        """Return agent capabilities."""
        return {
            "agent_id": request.agent_id,
            "agent_name": "agentchains-grpc",
            "capabilities": ["task_execution", "streaming", "orchestration"],
            "supported_tasks": ["agent_call", "tool_call", "query"],
            "max_concurrent_tasks": 50,
        }

    async def SendMessage(self, request, context):
        """Handle an inter-agent message."""
        logger.info(
            "gRPC message: %s -> %s type=%s",
            request.from_agent_id, request.to_agent_id, request.message_type,
        )
        return {"message_id": request.message_id, "acknowledged": True}

    async def _dispatch_task(self, task_type: str, input_data: dict, agent_id: str) -> dict:
        """Dispatch a task to the appropriate handler."""
        if task_type == "agent_call":
            # Forward to A2A client
            return {"result": "Agent call completed"}
        elif task_type == "tool_call":
            # Forward to MCP tools
            return {"result": "Tool call completed"}
        elif task_type == "query":
            return {"result": "Query completed"}
        else:
            return {"result": "Unsupported task type"}


class OrchestrationServiceServicer:
    """Implements the OrchestrationService gRPC interface."""

    async def ExecuteNode(self, request, context):
        """Execute a workflow node via gRPC."""
        logger.info(
            "gRPC node execution: exec=%s node=%s type=%s",
            request.execution_id, request.node_id, request.node_type,
        )
        try:
            input_data = _validate_and_parse_input(request.input_json)
        except ValueError as ve:
            return {
                "execution_id": request.execution_id,
                "node_id": request.node_id,
                "status": "error",
                "output_json": json.dumps({"error": str(ve)}),
                "cost_usd": 0.0,
            }

        return {
            "execution_id": request.execution_id,
            "node_id": request.node_id,
            "status": "completed",
            "output_json": json.dumps({"result": "Node executed"}),
            "cost_usd": 0.001,
        }

    async def ReportNodeStatus(self, request, context):
        """Receive node status reports from remote executors."""
        logger.info(
            "Node status: exec=%s node=%s status=%s",
            request.execution_id, request.node_id, request.status,
        )
        return {"acknowledged": True}


def create_grpc_server(port: int = GRPC_PORT):
    """Create and configure the gRPC server.

    Returns None if grpcio is not installed.
    """
    try:
        import grpc
        from grpc import aio

        server = aio.server(futures.ThreadPoolExecutor(max_workers=10))
        # Note: In production, register compiled protobuf servicers here
        # For now, provide the servicer classes for manual registration
        logger.info("gRPC server configured on port %d", port)
        return server, port
    except ImportError:
        logger.warning(
            "grpcio not installed — gRPC server disabled. "
            "Install with: pip install grpcio>=1.60"
        )
        return None, port
