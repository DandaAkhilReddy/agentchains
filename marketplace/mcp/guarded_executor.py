"""Guarded Tool Executor — authorization, validation, timeout, and metrics.

Wraps tool execution with policy enforcement:
1. Authorize — check agent allowlist
2. Validate — input size against policy
3. Timeout — asyncio.wait_for() with per-tool timeout
4. Metrics — emit latency/success counters
5. Execute — delegate to existing execute_tool()
"""

from __future__ import annotations

import asyncio
import json
import time

import structlog
from prometheus_client import Counter, Histogram
from sqlalchemy.ext.asyncio import AsyncSession

from marketplace.mcp.tool_registry import ToolRegistry

logger = structlog.get_logger(__name__)

# Tool-level metrics
TOOL_CALL_COUNT = Counter(
    "mcp_tool_calls_total",
    "Total MCP tool calls",
    ["tool_name", "status"],
)

TOOL_CALL_LATENCY = Histogram(
    "mcp_tool_call_duration_seconds",
    "MCP tool call latency in seconds",
    ["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)


class GuardedToolExecutor:
    """Executes MCP tools with policy enforcement.

    Checks authorization, validates input size, enforces timeouts,
    and emits Prometheus metrics around every tool call.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def execute(
        self,
        tool_name: str,
        arguments: dict,
        agent_id: str,
        db: AsyncSession | None = None,
    ) -> dict:
        """Execute a tool call with full policy enforcement."""
        from marketplace.mcp.tools import execute_tool

        # 1. Authorize
        if not self._registry.authorize_tool_call(agent_id, tool_name):
            TOOL_CALL_COUNT.labels(tool_name=tool_name, status="denied").inc()
            return {"error": f"Tool '{tool_name}' not authorized for agent '{agent_id}'"}

        # 2. Get policy
        policy = self._registry.get_policy(tool_name)
        timeout = policy.timeout_seconds if policy else 30.0
        max_input_size = policy.max_input_size_bytes if policy else 1_048_576

        # 3. Validate input size
        input_json = json.dumps(arguments)
        if len(input_json.encode("utf-8")) > max_input_size:
            TOOL_CALL_COUNT.labels(tool_name=tool_name, status="input_too_large").inc()
            return {
                "error": f"Input exceeds maximum size "
                f"({len(input_json)} > {max_input_size} bytes)",
            }

        # 4. Check consent for high-risk tools
        if policy and policy.requires_consent:
            if not arguments.get("consent", False):
                TOOL_CALL_COUNT.labels(tool_name=tool_name, status="consent_required").inc()
                return {
                    "error": f"Tool '{tool_name}' requires explicit consent. "
                    "Set consent=true to proceed.",
                }

        # 5. Execute with timeout + metrics
        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                execute_tool(tool_name, arguments, agent_id, db=db),
                timeout=timeout,
            )
            duration = time.perf_counter() - start
            TOOL_CALL_COUNT.labels(tool_name=tool_name, status="success").inc()
            TOOL_CALL_LATENCY.labels(tool_name=tool_name).observe(duration)

            logger.info(
                "tool_executed",
                tool_name=tool_name,
                agent_id=agent_id,
                duration_ms=round(duration * 1000, 1),
            )
            return result

        except asyncio.TimeoutError:
            duration = time.perf_counter() - start
            TOOL_CALL_COUNT.labels(tool_name=tool_name, status="timeout").inc()
            TOOL_CALL_LATENCY.labels(tool_name=tool_name).observe(duration)
            logger.error(
                "tool_timeout",
                tool_name=tool_name,
                agent_id=agent_id,
                timeout_seconds=timeout,
            )
            return {"error": f"Tool '{tool_name}' timed out after {timeout}s"}

        except Exception as exc:
            duration = time.perf_counter() - start
            TOOL_CALL_COUNT.labels(tool_name=tool_name, status="error").inc()
            TOOL_CALL_LATENCY.labels(tool_name=tool_name).observe(duration)
            logger.error(
                "tool_execution_failed",
                tool_name=tool_name,
                agent_id=agent_id,
                error=str(exc),
            )
            raise
