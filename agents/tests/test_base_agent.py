"""Tests for BaseA2AAgent — subclassing, app construction, and request routing."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from agents.a2a_servers.server import create_a2a_app
from agents.a2a_servers.task_manager import TaskState
from agents.common.base_agent import BaseA2AAgent


# ---------------------------------------------------------------------------
# Concrete test subclass
# ---------------------------------------------------------------------------


class EchoAgent(BaseA2AAgent):
    """Minimal concrete agent that echoes input_data back."""

    def __init__(self, port: int = 8888) -> None:
        super().__init__(
            name="Echo Agent",
            description="Returns the input data unchanged.",
            port=port,
            skills=[
                {
                    "id": "echo",
                    "name": "Echo",
                    "description": "Echoes the input.",
                    "tags": ["echo"],
                }
            ],
            version="0.2.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        return {"echo": input_data}


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def echo_agent() -> EchoAgent:
    return EchoAgent()


@pytest.fixture
def echo_app(echo_agent: EchoAgent):
    return echo_agent.build_app()


# ---------------------------------------------------------------------------
# TestBaseA2AAgentSubclassing
# ---------------------------------------------------------------------------


class TestBaseA2AAgentSubclassing:
    """Verify that concrete subclasses integrate correctly with BaseA2AAgent."""

    def test_subclass_stores_name(self, echo_agent: EchoAgent) -> None:
        assert echo_agent.name == "Echo Agent"

    def test_subclass_stores_description(self, echo_agent: EchoAgent) -> None:
        assert echo_agent.description == "Returns the input data unchanged."

    def test_subclass_stores_port(self, echo_agent: EchoAgent) -> None:
        assert echo_agent.port == 8888

    def test_subclass_stores_version(self, echo_agent: EchoAgent) -> None:
        assert echo_agent.version == "0.2.0"

    def test_subclass_stores_skills(self, echo_agent: EchoAgent) -> None:
        assert len(echo_agent.skills) == 1
        assert echo_agent.skills[0]["id"] == "echo"

    def test_subclass_base_url_uses_port(self, echo_agent: EchoAgent) -> None:
        assert echo_agent.base_url == "http://localhost:8888"

    def test_abstractmethod_prevents_bare_instantiation(self) -> None:
        with pytest.raises(TypeError):
            BaseA2AAgent(  # type: ignore[abstract]
                name="X",
                description="Y",
            )


# ---------------------------------------------------------------------------
# TestBuildApp
# ---------------------------------------------------------------------------


class TestBuildApp:
    """Tests for BaseA2AAgent.build_app()."""

    def test_build_app_returns_fastapi_app(self, echo_agent: EchoAgent) -> None:
        from fastapi import FastAPI

        app = echo_agent.build_app()
        assert isinstance(app, FastAPI)

    def test_build_app_caches_on_instance(self, echo_agent: EchoAgent) -> None:
        app1 = echo_agent.build_app()
        app2 = echo_agent.build_app()
        # Both calls return the same object (second call rebuilds, but _app is set)
        assert app1 is not None
        assert app2 is not None

    def test_build_app_title_contains_agent_name(self, echo_agent: EchoAgent) -> None:
        app = echo_agent.build_app()
        assert "Echo Agent" in app.title


# ---------------------------------------------------------------------------
# TestAgentInfo
# ---------------------------------------------------------------------------


class TestAgentInfo:
    """Tests for BaseA2AAgent.agent_info()."""

    def test_agent_info_has_name(self, echo_agent: EchoAgent) -> None:
        info = echo_agent.agent_info()
        assert info["name"] == "Echo Agent"

    def test_agent_info_has_port(self, echo_agent: EchoAgent) -> None:
        info = echo_agent.agent_info()
        assert info["port"] == 8888

    def test_agent_info_has_url(self, echo_agent: EchoAgent) -> None:
        info = echo_agent.agent_info()
        assert info["url"] == "http://localhost:8888"

    def test_agent_info_has_description(self, echo_agent: EchoAgent) -> None:
        info = echo_agent.agent_info()
        assert info["description"] == "Returns the input data unchanged."

    def test_agent_info_has_version(self, echo_agent: EchoAgent) -> None:
        info = echo_agent.agent_info()
        assert info["version"] == "0.2.0"

    def test_agent_info_skills_contains_ids(self, echo_agent: EchoAgent) -> None:
        info = echo_agent.agent_info()
        assert "echo" in info["skills"]

    def test_agent_info_skills_uses_index_fallback_when_no_id(self) -> None:
        class NoIdAgent(BaseA2AAgent):
            def __init__(self) -> None:
                super().__init__(
                    name="NoId",
                    description="No skill id",
                    port=9999,
                    skills=[{"name": "Anon"}],
                )

            async def handle_skill(self, skill_id: str, input_data: dict) -> dict:
                return {}

        agent = NoIdAgent()
        info = agent.agent_info()
        assert info["skills"] == ["skill-0"]

    def test_agent_info_no_skills_is_empty_list(self) -> None:
        class EmptyAgent(BaseA2AAgent):
            def __init__(self) -> None:
                super().__init__(name="Empty", description="No skills", port=9990)

            async def handle_skill(self, skill_id: str, input_data: dict) -> dict:
                return {}

        agent = EmptyAgent()
        assert agent.agent_info()["skills"] == []


# ---------------------------------------------------------------------------
# TestTaskHandlerBridge
# ---------------------------------------------------------------------------


class TestTaskHandlerBridge:
    """Tests for the _task_handler bridge: JSON parsing and plain-text fallback."""

    async def test_json_message_is_parsed_into_dict(self, echo_agent: EchoAgent) -> None:
        payload = {"query": "hello", "num_results": 3}
        result = await echo_agent._task_handler(
            skill_id="echo",
            message=json.dumps(payload),
            params={},
        )
        assert result["echo"] == payload

    async def test_plain_text_message_becomes_text_key(self, echo_agent: EchoAgent) -> None:
        result = await echo_agent._task_handler(
            skill_id="echo",
            message="plain text message",
            params={},
        )
        assert result["echo"] == {"text": "plain text message"}

    async def test_empty_string_message_becomes_text_key_empty(
        self, echo_agent: EchoAgent
    ) -> None:
        result = await echo_agent._task_handler(
            skill_id="echo",
            message="",
            params={},
        )
        assert result["echo"] == {"text": ""}

    async def test_malformed_json_falls_back_to_text_key(
        self, echo_agent: EchoAgent
    ) -> None:
        result = await echo_agent._task_handler(
            skill_id="echo",
            message="{not valid json",
            params={},
        )
        assert result["echo"] == {"text": "{not valid json"}

    async def test_skill_id_is_forwarded_to_handle_skill(self) -> None:
        received_skill_ids: list[str] = []

        class CapturingAgent(BaseA2AAgent):
            def __init__(self) -> None:
                super().__init__(name="Cap", description="Captures skill_id", port=9997)

            async def handle_skill(self, skill_id: str, input_data: dict) -> dict:
                received_skill_ids.append(skill_id)
                return {}

        agent = CapturingAgent()
        await agent._task_handler(skill_id="my-special-skill", message="test", params={})
        assert received_skill_ids == ["my-special-skill"]


# ---------------------------------------------------------------------------
# TestA2AEndpointViaASGITransport
# ---------------------------------------------------------------------------


class TestA2AEndpointViaASGITransport:
    """End-to-end tests through the full FastAPI app using ASGITransport."""

    async def test_tasks_send_returns_200(self, echo_app) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=echo_app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tasks/send",
                    "params": {
                        "skill_id": "echo",
                        "message": {
                            "parts": [{"type": "text", "text": json.dumps({"key": "val"})}]
                        },
                    },
                },
            )
        assert resp.status_code == 200

    async def test_tasks_send_result_state_is_completed(self, echo_app) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=echo_app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tasks/send",
                    "params": {
                        "skill_id": "echo",
                        "message": {
                            "parts": [{"type": "text", "text": json.dumps({"x": 1})}]
                        },
                    },
                },
            )
        assert resp.json()["result"]["state"] == TaskState.COMPLETED.value

    async def test_tasks_send_result_contains_artifact_with_echo(self, echo_app) -> None:
        payload = {"hello": "world"}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=echo_app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tasks/send",
                    "params": {
                        "skill_id": "echo",
                        "message": {
                            "parts": [{"type": "text", "text": json.dumps(payload)}]
                        },
                    },
                },
            )
        artifact_text = resp.json()["result"]["artifacts"][0]["parts"][0]["text"]
        decoded = json.loads(artifact_text)
        assert decoded["echo"] == payload

    async def test_tasks_get_retrieves_task_by_id(self, echo_app) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=echo_app),
            base_url="http://test",
        ) as client:
            send_resp = await client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tasks/send",
                    "params": {
                        "skill_id": "echo",
                        "message": {"parts": [{"type": "text", "text": "hi"}]},
                    },
                },
            )
            task_id = send_resp.json()["result"]["id"]

            get_resp = await client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tasks/get",
                    "params": {"id": task_id},
                },
            )

        assert get_resp.json()["result"]["id"] == task_id

    async def test_well_known_agent_json_returns_agent_name(self, echo_app) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=echo_app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/.well-known/agent.json")
        assert resp.json()["name"] == "Echo Agent"

    async def test_plain_text_message_routed_via_asgi(self, echo_app) -> None:
        """Plain text messages (no parts) must arrive in handle_skill as {"text": ...}."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=echo_app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tasks/send",
                    "params": {
                        "skill_id": "echo",
                        "message": {"text": "raw plain text"},
                    },
                },
            )
        artifact_text = resp.json()["result"]["artifacts"][0]["parts"][0]["text"]
        decoded = json.loads(artifact_text)
        assert decoded["echo"] == {"text": "raw plain text"}
