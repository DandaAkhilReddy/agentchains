"""Tool Registry — per-tool policies, agent-scoped allowlists, authorization.

Provides centralized tool governance: timeouts, input size limits,
risk levels, rate limiting, and per-agent tool allowlists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class RiskLevel(str, Enum):
    """Risk classification for tools."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ToolPolicy:
    """Execution policy for a single tool."""

    name: str
    timeout_seconds: float = 30.0
    max_input_size_bytes: int = 1_048_576  # 1 MB
    requires_consent: bool = False
    risk_level: RiskLevel = RiskLevel.MEDIUM
    rate_limit_per_minute: int = 60


@dataclass
class AgentToolAllowlist:
    """Per-agent tool access restrictions."""

    agent_id: str
    allowed_tools: set[str] = field(default_factory=set)  # empty = all allowed
    denied_tools: set[str] = field(default_factory=set)
    max_concurrent_calls: int = 10


class ToolRegistry:
    """Central registry for tool definitions, policies, and agent allowlists."""

    def __init__(self) -> None:
        self._tools: dict[str, dict] = {}
        self._policies: dict[str, ToolPolicy] = {}
        self._allowlists: dict[str, AgentToolAllowlist] = {}

    def register_tool(self, definition: dict, policy: ToolPolicy | None = None) -> None:
        """Register a tool definition with an optional policy."""
        name = definition["name"]
        self._tools[name] = definition
        if policy:
            self._policies[name] = policy
        else:
            self._policies[name] = ToolPolicy(name=name)

    def set_agent_allowlist(self, allowlist: AgentToolAllowlist) -> None:
        """Set per-agent tool restrictions."""
        self._allowlists[allowlist.agent_id] = allowlist

    def get_policy(self, tool_name: str) -> ToolPolicy | None:
        """Get the policy for a tool."""
        return self._policies.get(tool_name)

    def authorize_tool_call(self, agent_id: str, tool_name: str) -> bool:
        """Check if an agent is authorized to call a tool.

        Returns True if allowed, False if denied.
        """
        if tool_name not in self._tools:
            logger.warning("tool_not_found", tool_name=tool_name, agent_id=agent_id)
            return False

        allowlist = self._allowlists.get(agent_id)
        if allowlist is None:
            return True  # No restrictions for this agent

        # Check denied list first (deny takes precedence)
        if tool_name in allowlist.denied_tools:
            logger.warning(
                "tool_denied",
                tool_name=tool_name,
                agent_id=agent_id,
            )
            return False

        # If allowed_tools is non-empty, only those are permitted
        if allowlist.allowed_tools and tool_name not in allowlist.allowed_tools:
            logger.warning(
                "tool_not_in_allowlist",
                tool_name=tool_name,
                agent_id=agent_id,
            )
            return False

        return True

    def get_tools_for_agent(self, agent_id: str) -> list[dict]:
        """Return the filtered list of tool definitions for an agent."""
        return [
            defn for name, defn in self._tools.items()
            if self.authorize_tool_call(agent_id, name)
        ]

    def list_all_tools(self) -> list[dict]:
        """Return all registered tool definitions."""
        return list(self._tools.values())
