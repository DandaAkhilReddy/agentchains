"""Agent registry package — central catalog of all A2A agents with metadata."""

from __future__ import annotations

from agents.registry.agent_registry import (
    AGENTS,
    get_agent,
    get_agent_url,
    get_agents_by_category,
    list_all_agents,
)

__all__ = [
    "AGENTS",
    "get_agent",
    "get_agent_url",
    "get_agents_by_category",
    "list_all_agents",
]
