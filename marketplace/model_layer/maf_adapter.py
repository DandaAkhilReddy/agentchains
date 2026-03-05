"""Microsoft Agent Framework (MAF) adapter.

Bridges MAF agent manifests and runtime abstractions to the AgentChains
ModelRouter for unified model access.
"""

from __future__ import annotations

from typing import Any

import structlog

from marketplace.model_layer.router import ModelRouter
from marketplace.model_layer.types import CompletionRequest, CompletionResponse

logger = structlog.get_logger(__name__)


class MAFAgentManifest:
    """Parsed MAF agent manifest."""

    def __init__(self, manifest: dict[str, Any]) -> None:
        self.name: str = manifest.get("name", "")
        self.description: str = manifest.get("description", "")
        self.version: str = manifest.get("version", "1.0.0")
        self.skills: list[dict[str, Any]] = manifest.get("skills", [])
        self.model_preferences: dict[str, Any] = manifest.get("model_preferences", {})
        self.tools: list[dict[str, Any]] = manifest.get("tools", [])
        self._raw = manifest


class MAFAdapter:
    """Adapts MAF agent runtime calls to use AgentChains ModelRouter."""

    def __init__(self, model_router: ModelRouter) -> None:
        self._router = model_router
        self._agents: dict[str, MAFAgentManifest] = {}

    def register_manifest(self, agent_id: str, manifest: dict[str, Any]) -> MAFAgentManifest:
        """Parse and register a MAF agent manifest."""
        parsed = MAFAgentManifest(manifest)
        self._agents[agent_id] = parsed
        logger.info(
            "maf_agent_registered",
            agent_id=agent_id,
            name=parsed.name,
            skills=len(parsed.skills),
        )
        return parsed

    def get_manifest(self, agent_id: str) -> MAFAgentManifest | None:
        """Retrieve a registered MAF agent manifest."""
        return self._agents.get(agent_id)

    async def invoke(
        self,
        agent_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> CompletionResponse:
        """Invoke a MAF agent using the ModelRouter.

        Respects model preferences from the agent's manifest.
        """
        manifest = self._agents.get(agent_id)
        model = ""
        if manifest and manifest.model_preferences:
            model = manifest.model_preferences.get("model", "")

        merged_tools = tools or []
        if manifest:
            merged_tools = [*manifest.tools, *(tools or [])]

        request = CompletionRequest(
            messages=messages,
            model=model,
            tools=merged_tools if merged_tools else None,
        )
        return await self._router.complete(request)

    def list_agents(self) -> list[dict[str, Any]]:
        """List all registered MAF agents."""
        return [
            {
                "agent_id": agent_id,
                "name": manifest.name,
                "description": manifest.description,
                "version": manifest.version,
                "skills": len(manifest.skills),
            }
            for agent_id, manifest in self._agents.items()
        ]
