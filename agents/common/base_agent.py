"""BaseA2AAgent — abstract base class for chainable A2A agents.

Wraps the A2A server with marketplace registration and provides a
simple interface for subclasses: implement ``handle_skill()`` and
the rest (HTTP server, agent card, task lifecycle) is handled automatically.

Usage:
    class MyAgent(BaseA2AAgent):
        async def handle_skill(self, skill_id, input_data):
            return {"result": "processed"}

    agent = MyAgent(name="My Agent", port=9001, skills=[...])
    app = agent.build_app()
    # Run with: uvicorn module:app --port 9001
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from agents.a2a_servers.server import TaskHandler, create_a2a_app

logger = logging.getLogger(__name__)


class BaseA2AAgent(ABC):
    """Abstract base for chainable A2A agents.

    Subclasses implement ``handle_skill(skill_id, input_data)`` which receives
    parsed JSON input and returns a dict that becomes the task artifact.
    """

    def __init__(
        self,
        name: str,
        description: str,
        port: int = 9000,
        skills: list[dict[str, Any]] | None = None,
        version: str = "0.1.0",
    ) -> None:
        self.name = name
        self.description = description
        self.port = port
        self.skills = skills or []
        self.version = version
        self._app = None

    @abstractmethod
    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Process a skill invocation and return a result dict.

        Args:
            skill_id: The skill being invoked (matches a skill id from self.skills).
            input_data: Parsed JSON input from the caller. For A2A messages,
                this is the decoded text part. For orchestration, this is the
                merged upstream outputs.

        Returns:
            A dict that will be serialized as the task artifact.
        """

    async def _task_handler(
        self, skill_id: str, message: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Bridge between A2A server's TaskHandler signature and handle_skill."""
        # Try to parse message as JSON for structured input
        try:
            input_data = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            input_data = {"text": message}

        logger.info(
            "Agent '%s' handling skill '%s'",
            self.name,
            skill_id,
        )

        result = await self.handle_skill(skill_id, input_data)

        logger.info(
            "Agent '%s' completed skill '%s'",
            self.name,
            skill_id,
        )
        return result

    def build_app(self):
        """Build and return the FastAPI application for this agent.

        Returns:
            FastAPI app ready to run with uvicorn.
        """
        self._app = create_a2a_app(
            name=self.name,
            description=self.description,
            skills=self.skills,
            task_handler=self._task_handler,
            host="0.0.0.0",
            port=self.port,
        )
        return self._app

    @property
    def base_url(self) -> str:
        """The local base URL for this agent."""
        return f"http://localhost:{self.port}"

    def agent_info(self) -> dict[str, Any]:
        """Return a summary dict for registry/discovery."""
        return {
            "name": self.name,
            "description": self.description,
            "url": self.base_url,
            "port": self.port,
            "skills": [s.get("id", f"skill-{i}") for i, s in enumerate(self.skills)],
            "version": self.version,
        }
