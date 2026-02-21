"""Sandbox lifecycle management for isolated WebMCP execution.

Manages ephemeral container sessions for running WebMCP actions
in isolated environments with network and resource limits.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class SandboxState(str, Enum):
    CREATING = "creating"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class SandboxConfig:
    """Configuration for a sandbox container."""

    image: str = "mcr.microsoft.com/playwright:latest"
    memory_limit_mb: int = 512
    cpu_limit: float = 0.5
    timeout_seconds: int = 120
    network_enabled: bool = True
    allowed_domains: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxSession:
    """Represents an active sandbox session."""

    session_id: str
    agent_id: str
    action_id: str
    state: SandboxState = SandboxState.CREATING
    config: SandboxConfig = field(default_factory=SandboxConfig)
    container_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: dict = field(default_factory=dict)
    error: str | None = None


class SandboxManager:
    """Manages sandbox container lifecycle.

    In production, this delegates to Azure Container Apps dynamic sessions
    or Azure Container Instances. For development, it simulates execution.
    """

    def __init__(self, mode: str = "simulated"):
        self._mode = mode  # simulated | docker | azure_aci | azure_aca
        self._sessions: dict[str, SandboxSession] = {}
        self._max_concurrent = 10

    async def create_session(
        self,
        agent_id: str,
        action_id: str,
        config: SandboxConfig | None = None,
    ) -> SandboxSession:
        """Create a new sandbox session."""
        if len(self._sessions) >= self._max_concurrent:
            raise RuntimeError(
                f"Maximum concurrent sandboxes ({self._max_concurrent}) reached"
            )

        session = SandboxSession(
            session_id=str(uuid.uuid4()),
            agent_id=agent_id,
            action_id=action_id,
            config=config or SandboxConfig(),
        )
        self._sessions[session.session_id] = session
        logger.info(
            "Sandbox created: session=%s agent=%s action=%s mode=%s",
            session.session_id, agent_id, action_id, self._mode,
        )
        return session

    async def execute(
        self, session_id: str, command: str, input_data: dict | None = None
    ) -> dict:
        """Execute a command in a sandbox session."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Sandbox session not found: {session_id}")

        session.state = SandboxState.RUNNING
        session.started_at = datetime.now(timezone.utc)

        try:
            if self._mode == "simulated":
                result = await self._execute_simulated(session, command, input_data)
            elif self._mode == "docker":
                result = await self._execute_docker(session, command, input_data)
            else:
                result = await self._execute_simulated(session, command, input_data)

            session.state = SandboxState.COMPLETED
            session.completed_at = datetime.now(timezone.utc)
            session.output = result
            return result

        except Exception as e:
            session.state = SandboxState.FAILED
            session.completed_at = datetime.now(timezone.utc)
            session.error = str(e)
            logger.error("Sandbox execution failed: %s — %s", session_id, e)
            raise

    async def _execute_simulated(
        self, session: SandboxSession, command: str, input_data: dict | None
    ) -> dict:
        """Simulated execution for development."""
        return {
            "status": "success",
            "output": f"Simulated execution of: {command}",
            "input_data": input_data or {},
            "execution_time_ms": 150,
            "sandbox_id": session.session_id,
            "simulated": True,
        }

    async def _execute_docker(
        self, session: SandboxSession, command: str, input_data: dict | None
    ) -> dict:
        """Execute in a local Docker container."""
        # Requires docker SDK
        try:
            import docker

            client = docker.from_env()
            container = client.containers.run(
                session.config.image,
                command=command,
                detach=False,
                mem_limit=f"{session.config.memory_limit_mb}m",
                nano_cpus=int(session.config.cpu_limit * 1e9),
                network_disabled=not session.config.network_enabled,
                environment=session.config.environment,
                remove=True,
                stdout=True,
                stderr=True,
            )
            return {
                "status": "success",
                "output": container.decode("utf-8") if isinstance(container, bytes) else str(container),
                "simulated": False,
            }
        except ImportError:
            logger.warning("docker package not installed, falling back to simulation")
            return await self._execute_simulated(session, command, input_data)

    async def destroy_session(self, session_id: str) -> bool:
        """Destroy a sandbox session and clean up resources."""
        session = self._sessions.pop(session_id, None)
        if session:
            logger.info("Sandbox destroyed: %s", session_id)
            return True
        return False

    def get_session(self, session_id: str) -> SandboxSession | None:
        """Get sandbox session details."""
        return self._sessions.get(session_id)

    def list_sessions(self, agent_id: str | None = None) -> list[SandboxSession]:
        """List active sandbox sessions."""
        sessions = list(self._sessions.values())
        if agent_id:
            sessions = [s for s in sessions if s.agent_id == agent_id]
        return sessions


# Singleton
sandbox_manager = SandboxManager()
