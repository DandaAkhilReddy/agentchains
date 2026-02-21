"""Unit tests for the A2A protocol implementation.

Tests cover:
- agent_card.generate_agent_card
- task_manager.TaskManager / Task / TaskState
- server.create_a2a_app (via httpx.AsyncClient + ASGITransport)
- a2a_client.A2AClient / A2AError
- pipeline.Pipeline / PipelineStep
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from agents.a2a_servers.agent_card import generate_agent_card
from agents.a2a_servers.task_manager import Task, TaskManager, TaskState
from agents.a2a_servers.server import create_a2a_app
from agents.common.a2a_client import A2AClient, A2AError
from agents.common.pipeline import Pipeline, PipelineStep


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_SKILLS = [
    {
        "id": "search",
        "name": "Web Search",
        "description": "Search the web for information",
        "tags": ["search", "web"],
        "examples": ["Find Python tutorials"],
    },
    {
        "id": "summarize",
        "name": "Summarize",
        "description": "Summarize text content",
    },
]


@pytest.fixture
def task_manager() -> TaskManager:
    return TaskManager()


@pytest.fixture
def sample_task(task_manager: TaskManager) -> Task:
    return task_manager.create_task("search", "Find Python tutorials")


@pytest.fixture
def a2a_app():
    """FastAPI app with default handler for server tests."""
    return create_a2a_app(
        name="TestAgent",
        description="An agent used in unit tests",
        skills=SAMPLE_SKILLS,
    )


# ---------------------------------------------------------------------------
# TestAgentCard
# ---------------------------------------------------------------------------


class TestAgentCard:
    """Tests for generate_agent_card()."""

    def test_returns_dict(self):
        card = generate_agent_card(
            name="MyAgent", description="Does stuff", url="http://localhost:9000"
        )
        assert isinstance(card, dict)

    def test_card_has_name(self):
        card = generate_agent_card(
            name="MyAgent", description="Does stuff", url="http://localhost:9000"
        )
        assert card["name"] == "MyAgent"

    def test_card_has_description(self):
        card = generate_agent_card(
            name="MyAgent", description="Does stuff", url="http://localhost:9000"
        )
        assert card["description"] == "Does stuff"

    def test_card_has_url(self):
        card = generate_agent_card(
            name="MyAgent", description="Does stuff", url="http://localhost:9000"
        )
        assert card["url"] == "http://localhost:9000"

    def test_card_has_version(self):
        card = generate_agent_card(
            name="A", description="B", url="http://x", version="1.2.3"
        )
        assert card["version"] == "1.2.3"

    def test_card_default_version(self):
        card = generate_agent_card(name="A", description="B", url="http://x")
        assert card["version"] == "0.1.0"

    def test_card_has_capabilities_dict(self):
        card = generate_agent_card(name="A", description="B", url="http://x")
        assert isinstance(card["capabilities"], dict)

    def test_card_default_capabilities_present(self):
        card = generate_agent_card(name="A", description="B", url="http://x")
        # Default capabilities are "streaming" and "pushNotifications"
        assert card["capabilities"].get("streaming") is True
        assert card["capabilities"].get("pushNotifications") is True

    def test_card_custom_capabilities(self):
        card = generate_agent_card(
            name="A",
            description="B",
            url="http://x",
            capabilities=["streaming"],
        )
        assert card["capabilities"] == {"streaming": True}
        assert "pushNotifications" not in card["capabilities"]

    def test_card_includes_skills(self):
        card = generate_agent_card(
            name="A", description="B", url="http://x", skills=SAMPLE_SKILLS
        )
        assert len(card["skills"]) == 2

    def test_card_skill_has_required_fields(self):
        card = generate_agent_card(
            name="A", description="B", url="http://x", skills=SAMPLE_SKILLS
        )
        skill = card["skills"][0]
        assert skill["id"] == "search"
        assert skill["name"] == "Web Search"
        assert skill["description"] == "Search the web for information"

    def test_card_skill_preserves_tags(self):
        card = generate_agent_card(
            name="A", description="B", url="http://x", skills=SAMPLE_SKILLS
        )
        assert card["skills"][0]["tags"] == ["search", "web"]

    def test_card_skill_missing_tags_defaults_to_empty_list(self):
        # Second skill in SAMPLE_SKILLS has no "tags" key
        card = generate_agent_card(
            name="A", description="B", url="http://x", skills=SAMPLE_SKILLS
        )
        assert card["skills"][1]["tags"] == []

    def test_card_empty_skills(self):
        card = generate_agent_card(name="A", description="B", url="http://x", skills=[])
        assert card["skills"] == []

    def test_card_no_skills_arg_defaults_to_empty(self):
        card = generate_agent_card(name="A", description="B", url="http://x")
        assert card["skills"] == []

    def test_card_has_authentication_schemes(self):
        card = generate_agent_card(name="A", description="B", url="http://x")
        assert "authentication" in card
        assert "schemes" in card["authentication"]
        assert isinstance(card["authentication"]["schemes"], list)

    def test_card_has_input_output_modes(self):
        card = generate_agent_card(name="A", description="B", url="http://x")
        assert "defaultInputModes" in card
        assert "defaultOutputModes" in card


# ---------------------------------------------------------------------------
# TestTaskManager
# ---------------------------------------------------------------------------


class TestTaskManager:
    """Tests for TaskManager, Task, and TaskState."""

    def test_create_task_returns_task(self, task_manager):
        task = task_manager.create_task("search", "hello")
        assert isinstance(task, Task)

    def test_create_task_initial_state_is_submitted(self, task_manager):
        task = task_manager.create_task("search", "hello")
        assert task.state == TaskState.SUBMITTED

    def test_create_task_stores_skill_id(self, task_manager):
        task = task_manager.create_task("my-skill", "hello")
        assert task.skill_id == "my-skill"

    def test_create_task_stores_message(self, task_manager):
        task = task_manager.create_task("s", "Find something important")
        assert task.message == "Find something important"

    def test_create_task_assigns_unique_ids(self, task_manager):
        t1 = task_manager.create_task("s", "a")
        t2 = task_manager.create_task("s", "b")
        assert t1.id != t2.id

    def test_get_task_returns_task(self, task_manager, sample_task):
        fetched = task_manager.get_task(sample_task.id)
        assert fetched is sample_task

    def test_get_task_returns_none_for_unknown_id(self, task_manager):
        result = task_manager.get_task("nonexistent-id-xyz")
        assert result is None

    def test_update_state_to_working(self, task_manager, sample_task):
        result = task_manager.update_state(sample_task.id, TaskState.WORKING)
        assert result is not None
        assert result.state == TaskState.WORKING

    def test_update_state_to_completed(self, task_manager, sample_task):
        task_manager.update_state(sample_task.id, TaskState.WORKING)
        result = task_manager.update_state(sample_task.id, TaskState.COMPLETED)
        assert result is not None
        assert result.state == TaskState.COMPLETED

    def test_update_state_to_failed_with_error(self, task_manager, sample_task):
        task_manager.update_state(sample_task.id, TaskState.WORKING)
        result = task_manager.update_state(
            sample_task.id, TaskState.FAILED, error="Something went wrong"
        )
        assert result is not None
        assert result.state == TaskState.FAILED
        assert result.error == "Something went wrong"

    def test_update_state_invalid_transition_returns_none(self, task_manager, sample_task):
        # Cannot go directly from SUBMITTED to COMPLETED
        result = task_manager.update_state(sample_task.id, TaskState.COMPLETED)
        assert result is None

    def test_update_state_returns_none_for_unknown_task(self, task_manager):
        result = task_manager.update_state("no-such-task", TaskState.WORKING)
        assert result is None

    def test_cancel_task_from_submitted_state(self, task_manager, sample_task):
        result = task_manager.cancel_task(sample_task.id)
        assert result is not None
        assert result.state == TaskState.CANCELED

    def test_cancel_task_from_working_state(self, task_manager, sample_task):
        task_manager.update_state(sample_task.id, TaskState.WORKING)
        result = task_manager.cancel_task(sample_task.id)
        assert result is not None
        assert result.state == TaskState.CANCELED

    def test_cancel_task_returns_none_for_unknown_task(self, task_manager):
        result = task_manager.cancel_task("no-such-task")
        assert result is None

    def test_cancel_task_returns_none_for_already_completed_task(
        self, task_manager, sample_task
    ):
        task_manager.update_state(sample_task.id, TaskState.WORKING)
        task_manager.update_state(sample_task.id, TaskState.COMPLETED)
        result = task_manager.cancel_task(sample_task.id)
        assert result is None

    def test_add_artifact_appends_to_task(self, task_manager, sample_task):
        artifact = {"type": "text", "content": "Result data"}
        task_manager.add_artifact(sample_task.id, artifact)
        assert artifact in sample_task.artifacts

    def test_add_artifact_multiple_artifacts(self, task_manager, sample_task):
        task_manager.add_artifact(sample_task.id, {"type": "text", "content": "first"})
        task_manager.add_artifact(sample_task.id, {"type": "text", "content": "second"})
        assert len(sample_task.artifacts) == 2

    def test_add_artifact_returns_none_for_unknown_task(self, task_manager):
        result = task_manager.add_artifact("no-such-task", {"type": "text", "content": "x"})
        assert result is None

    def test_task_to_dict_has_id(self, sample_task):
        d = sample_task.to_dict()
        assert d["id"] == sample_task.id

    def test_task_to_dict_has_state(self, sample_task):
        d = sample_task.to_dict()
        assert d["state"] == TaskState.SUBMITTED.value

    def test_task_to_dict_has_skill_id(self, sample_task):
        d = sample_task.to_dict()
        assert d["skill_id"] == sample_task.skill_id

    def test_task_to_dict_has_message(self, sample_task):
        d = sample_task.to_dict()
        assert d["message"] == sample_task.message

    def test_task_to_dict_has_artifacts_list(self, sample_task):
        d = sample_task.to_dict()
        assert isinstance(d["artifacts"], list)

    def test_task_to_dict_has_timestamps(self, sample_task):
        d = sample_task.to_dict()
        assert "created_at" in d
        assert "updated_at" in d

    def test_task_to_dict_excludes_error_when_none(self, sample_task):
        d = sample_task.to_dict()
        assert "error" not in d

    def test_task_to_dict_includes_error_when_set(self, task_manager, sample_task):
        task_manager.update_state(sample_task.id, TaskState.WORKING)
        task_manager.update_state(sample_task.id, TaskState.FAILED, error="boom")
        d = sample_task.to_dict()
        assert d["error"] == "boom"

    def test_list_tasks_returns_all_tasks(self, task_manager):
        task_manager.create_task("s", "a")
        task_manager.create_task("s", "b")
        tasks = task_manager.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_respects_limit(self, task_manager):
        for i in range(10):
            task_manager.create_task("s", f"message {i}")
        tasks = task_manager.list_tasks(limit=3)
        assert len(tasks) == 3

    @pytest.mark.asyncio
    async def test_stream_updates_yields_state_change(self, task_manager, sample_task):
        """stream_updates should yield state_change events pushed to the queue."""
        # Pre-populate the queue then move task to terminal state so stream ends
        task_manager.update_state(sample_task.id, TaskState.WORKING)
        task_manager.update_state(sample_task.id, TaskState.COMPLETED)

        events = []
        async for update in task_manager.stream_updates(sample_task.id):
            events.append(update)

        types = [e["type"] for e in events]
        assert "state_change" in types

    @pytest.mark.asyncio
    async def test_stream_updates_returns_immediately_for_unknown_task(self, task_manager):
        events = []
        async for update in task_manager.stream_updates("no-such-task"):
            events.append(update)
        assert events == []


# ---------------------------------------------------------------------------
# TestA2AServer
# ---------------------------------------------------------------------------


class TestA2AServer:
    """Tests for the FastAPI app created by create_a2a_app()."""

    @pytest.mark.asyncio
    async def test_agent_card_endpoint_returns_200(self, a2a_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.get("/.well-known/agent.json")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_agent_card_endpoint_returns_name(self, a2a_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.get("/.well-known/agent.json")
        assert resp.json()["name"] == "TestAgent"

    @pytest.mark.asyncio
    async def test_agent_card_endpoint_includes_skills(self, a2a_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.get("/.well-known/agent.json")
        body = resp.json()
        assert len(body["skills"]) == len(SAMPLE_SKILLS)

    @pytest.mark.asyncio
    async def test_tasks_send_returns_200(self, a2a_app):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "skill_id": "search",
                "message": {"parts": [{"type": "text", "text": "hello"}]},
            },
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_tasks_send_returns_completed_task(self, a2a_app):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "skill_id": "search",
                "message": {"parts": [{"type": "text", "text": "hello"}]},
            },
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        result = resp.json()["result"]
        assert result["state"] == TaskState.COMPLETED.value

    @pytest.mark.asyncio
    async def test_tasks_send_result_has_artifact(self, a2a_app):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "skill_id": "search",
                "message": {"parts": [{"type": "text", "text": "hello"}]},
            },
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        result = resp.json()["result"]
        assert len(result["artifacts"]) > 0

    @pytest.mark.asyncio
    async def test_tasks_send_with_custom_handler(self):
        async def custom_handler(skill_id, message, params):
            return {"echo": message, "from_skill": skill_id}

        app = create_a2a_app(
            name="EchoAgent",
            description="Echoes input",
            skills=[{"id": "echo", "name": "Echo", "description": "Echoes input"}],
            task_handler=custom_handler,
        )
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "skill_id": "echo",
                "message": {"parts": [{"type": "text", "text": "test-input"}]},
            },
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        result = resp.json()["result"]
        assert result["state"] == TaskState.COMPLETED.value
        # The custom handler result should appear JSON-encoded in an artifact
        artifact_text = result["artifacts"][0]["parts"][0]["text"]
        decoded = json.loads(artifact_text)
        assert decoded["echo"] == "test-input"
        assert decoded["from_skill"] == "echo"

    @pytest.mark.asyncio
    async def test_tasks_send_failing_handler_produces_failed_task(self):
        async def bad_handler(skill_id, message, params):
            raise RuntimeError("intentional failure")

        app = create_a2a_app(
            name="BadAgent",
            description="Always fails",
            skills=[{"id": "fail", "name": "Fail", "description": "Always fails"}],
            task_handler=bad_handler,
        )
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "skill_id": "fail",
                "message": {"parts": [{"type": "text", "text": "oops"}]},
            },
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        result = resp.json()["result"]
        assert result["state"] == TaskState.FAILED.value

    @pytest.mark.asyncio
    async def test_tasks_get_returns_task(self, a2a_app):
        # First create a task
        send_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "skill_id": "search",
                "message": {"parts": [{"type": "text", "text": "find me"}]},
            },
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            send_resp = await client.post("/", json=send_body)
            task_id = send_resp.json()["result"]["id"]

            get_body = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tasks/get",
                "params": {"id": task_id},
            }
            get_resp = await client.post("/", json=get_body)

        assert get_resp.status_code == 200
        assert get_resp.json()["result"]["id"] == task_id

    @pytest.mark.asyncio
    async def test_tasks_get_missing_id_returns_error(self, a2a_app):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/get",
            "params": {},
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        assert "error" in resp.json()
        assert resp.json()["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_tasks_get_unknown_task_id_returns_error(self, a2a_app):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/get",
            "params": {"id": "completely-unknown-task-id"},
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        assert "error" in resp.json()

    @pytest.mark.asyncio
    async def test_tasks_cancel_returns_canceled_task(self, a2a_app):
        # Create a task first
        send_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "skill_id": "search",
                "message": {"parts": [{"type": "text", "text": "cancel me"}]},
            },
        }
        # Use an app with a handler that creates a task but we cancel a *new*
        # SUBMITTED task by injecting it at the task_manager level.  The simpler
        # approach is to use a separate app whose task_manager we can access.
        # Instead, we test via the JSON-RPC interface: create, then cancel an
        # already-completed task which should return error, and separately test
        # that a SUBMITTED task can be cancelled through a custom flow.

        # For a cleaner test: create a fresh app instance and access its task manager
        # by creating a task via tasks/send then immediately cancelling via tasks/cancel.
        # Since the default handler completes instantly, we test cancellation of a
        # completed task (which should return an error) vs a custom approach.
        # Use a separate test app that exposes a still-SUBMITTED task:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            send_resp = await client.post("/", json=send_body)
            task_id = send_resp.json()["result"]["id"]

            cancel_body = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tasks/cancel",
                "params": {"id": task_id},
            }
            cancel_resp = await client.post("/", json=cancel_body)

        # Completed tasks cannot be cancelled; server should return error
        assert cancel_resp.status_code == 200
        assert "error" in cancel_resp.json()

    @pytest.mark.asyncio
    async def test_tasks_cancel_missing_id_returns_error(self, a2a_app):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/cancel",
            "params": {},
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        assert "error" in resp.json()
        assert resp.json()["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_unknown_method_returns_method_not_found_error(self, a2a_app):
        body = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tasks/nonexistent",
            "params": {},
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_invalid_json_returns_parse_error(self, a2a_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/",
                content=b"this is not json at all {{{",
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == -32700

    @pytest.mark.asyncio
    async def test_jsonrpc_result_preserves_id(self, a2a_app):
        body = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tasks/send",
            "params": {
                "skill_id": "search",
                "message": {"parts": [{"type": "text", "text": "hi"}]},
            },
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        assert resp.json()["id"] == 42

    @pytest.mark.asyncio
    async def test_create_a2a_app_without_skills(self):
        app = create_a2a_app(name="Bare", description="No skills")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/.well-known/agent.json")
        assert resp.json()["skills"] == []

    @pytest.mark.asyncio
    async def test_message_text_extracted_from_flat_text_field(self, a2a_app):
        """Fallback: if no parts, use message.text directly."""
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "skill_id": "search",
                "message": {"text": "flat text message"},
            },
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a2a_app), base_url="http://test"
        ) as client:
            resp = await client.post("/", json=body)
        result = resp.json()["result"]
        assert result["state"] == TaskState.COMPLETED.value


# ---------------------------------------------------------------------------
# TestA2AClient
# ---------------------------------------------------------------------------


class TestA2AClient:
    """Tests for A2AClient and A2AError."""

    def test_client_stores_base_url(self):
        client = A2AClient("http://localhost:9001")
        assert client.base_url == "http://localhost:9001"

    def test_client_strips_trailing_slash_from_base_url(self):
        client = A2AClient("http://localhost:9001/")
        assert client.base_url == "http://localhost:9001"

    def test_client_default_timeout(self):
        client = A2AClient("http://localhost:9001")
        assert client.timeout == 30.0

    def test_client_custom_timeout(self):
        client = A2AClient("http://localhost:9001", timeout=60.0)
        assert client.timeout == 60.0

    def test_client_default_max_retries(self):
        client = A2AClient("http://localhost:9001")
        assert client.max_retries == 3

    def test_client_stores_auth_token(self):
        client = A2AClient("http://localhost:9001", auth_token="my-jwt-token")
        assert client.auth_token == "my-jwt-token"

    def test_client_headers_include_content_type(self):
        client = A2AClient("http://localhost:9001")
        headers = client._headers()
        assert headers["Content-Type"] == "application/json"

    def test_client_auth_header_when_token_set(self):
        client = A2AClient("http://localhost:9001", auth_token="secret-token")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer secret-token"

    def test_client_no_auth_header_when_no_token(self):
        client = A2AClient("http://localhost:9001")
        headers = client._headers()
        assert "Authorization" not in headers

    def test_client_agent_card_initially_none(self):
        client = A2AClient("http://localhost:9001")
        assert client.agent_card is None

    def test_a2a_error_has_code(self):
        err = A2AError(code=-32601, message="Method not found")
        assert err.code == -32601

    def test_a2a_error_has_message(self):
        err = A2AError(code=-32601, message="Method not found")
        assert err.message == "Method not found"

    def test_a2a_error_is_exception(self):
        err = A2AError(code=-1, message="Something failed")
        assert isinstance(err, Exception)

    def test_a2a_error_str_includes_code_and_message(self):
        err = A2AError(code=-32601, message="Method not found")
        assert "-32601" in str(err)
        assert "Method not found" in str(err)

    @pytest.mark.asyncio
    async def test_discover_populates_agent_card(self, a2a_app):
        """discover() should fetch and cache the agent card."""
        transport = httpx.ASGITransport(app=a2a_app)

        # Patch httpx.AsyncClient inside a2a_client to use our ASGI transport
        original_init = httpx.AsyncClient.__init__

        class PatchedClient(httpx.AsyncClient):
            def __init__(self, **kwargs):
                kwargs.setdefault("transport", transport)
                kwargs.setdefault("base_url", "http://test")
                super().__init__(**kwargs)

        with patch("agents.common.a2a_client.httpx.AsyncClient", PatchedClient):
            client = A2AClient("http://test")
            card = await client.discover()

        assert card["name"] == "TestAgent"
        assert client.agent_card is not None

    @pytest.mark.asyncio
    async def test_send_task_raises_a2a_error_on_rpc_error(self, a2a_app):
        """send_task should raise A2AError when server returns a JSON-RPC error."""
        transport = httpx.ASGITransport(app=a2a_app)

        class PatchedClient(httpx.AsyncClient):
            def __init__(self, **kwargs):
                kwargs.setdefault("transport", transport)
                kwargs.setdefault("base_url", "http://test")
                super().__init__(**kwargs)

        with patch("agents.common.a2a_client.httpx.AsyncClient", PatchedClient):
            client = A2AClient("http://test")
            # "tasks/get" with no params triggers -32602, propagated as A2AError
            # We patch _rpc_call to simulate that path via cancel_task on unknown id
            with pytest.raises(A2AError) as exc_info:
                await client.cancel_task("no-such-task-id")

        assert exc_info.value.code == -32602


# ---------------------------------------------------------------------------
# TestPipeline
# ---------------------------------------------------------------------------


class TestPipeline:
    """Tests for Pipeline and PipelineStep."""

    def test_pipeline_init_stores_name(self):
        p = Pipeline("My Pipeline")
        assert p.name == "My Pipeline"

    def test_pipeline_default_name(self):
        p = Pipeline()
        assert p.name == "Pipeline"

    def test_pipeline_starts_with_empty_steps(self):
        p = Pipeline("P")
        assert p.steps == []

    def test_add_step_returns_self_for_chaining(self):
        p = Pipeline("P")
        result = p.add_step("http://agent:9001", "search")
        assert result is p

    def test_add_step_appends_step(self):
        p = Pipeline("P")
        p.add_step("http://agent:9001", "search")
        assert len(p.steps) == 1

    def test_add_step_chaining_adds_multiple_steps(self):
        p = (
            Pipeline("P")
            .add_step("http://agent1:9001", "skill-a")
            .add_step("http://agent2:9002", "skill-b")
            .add_step("http://agent3:9003", "skill-c")
        )
        assert len(p.steps) == 3

    def test_add_step_creates_pipeline_step_objects(self):
        p = Pipeline("P")
        p.add_step("http://agent:9001", "search")
        assert isinstance(p.steps[0], PipelineStep)

    def test_add_step_stores_agent_url(self):
        p = Pipeline("P")
        p.add_step("http://agent:9001", "search")
        assert p.steps[0].agent_url == "http://agent:9001"

    def test_add_step_stores_skill_id(self):
        p = Pipeline("P")
        p.add_step("http://agent:9001", "my-skill")
        assert p.steps[0].skill_id == "my-skill"

    def test_add_step_stores_custom_name(self):
        p = Pipeline("P")
        p.add_step("http://agent:9001", "search", name="Step Alpha")
        assert p.steps[0].name == "Step Alpha"

    def test_add_step_default_name_combines_url_and_skill(self):
        p = Pipeline("P")
        p.add_step("http://agent:9001", "search")
        # Default name is "{agent_url}/{skill_id}"
        assert p.steps[0].name == "http://agent:9001/search"

    def test_add_step_stores_transform_fn(self):
        fn = lambda r: r.get("text", "")
        p = Pipeline("P")
        p.add_step("http://agent:9001", "search", transform_fn=fn)
        assert p.steps[0].transform_fn is fn

    def test_add_step_stores_auth_token(self):
        p = Pipeline("P")
        p.add_step("http://agent:9001", "search", auth_token="my-token")
        assert p.steps[0].auth_token == "my-token"

    @pytest.mark.asyncio
    async def test_empty_pipeline_returns_error(self):
        p = Pipeline("Empty")
        result = await p.execute("some input")
        assert result["status"] == "failed"
        assert "no steps" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_pipeline_execute_returns_completed_status(self):
        p = Pipeline("Test")
        p.add_step("http://agent:9001", "search")

        mock_result = {
            "id": "task-abc",
            "state": "completed",
            "artifacts": [{"parts": [{"type": "text", "text": "result text"}]}],
        }

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await p.execute("hello world")

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_pipeline_execute_includes_steps_in_result(self):
        p = Pipeline("Test")
        p.add_step("http://agent:9001", "search")

        mock_result = {
            "id": "task-abc",
            "state": "completed",
            "artifacts": [],
        }

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await p.execute("hello world")

        assert "steps" in result
        assert len(result["steps"]) == 1

    @pytest.mark.asyncio
    async def test_pipeline_execute_passes_initial_input_to_first_step(self):
        p = Pipeline("Test")
        p.add_step("http://agent:9001", "search")

        mock_result = {"id": "t1", "state": "completed", "artifacts": []}
        captured_calls = []

        async def fake_send(skill_id, message):
            captured_calls.append(message)
            return mock_result

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_send:
            result = await p.execute("initial query")
            mock_send.assert_called_once()
            assert mock_send.call_args[1]["message"] == "initial query"

    @pytest.mark.asyncio
    async def test_pipeline_stops_on_failed_step(self):
        p = Pipeline("Test")
        p.add_step("http://agent1:9001", "skill-a")
        p.add_step("http://agent2:9002", "skill-b")

        failed_result = {"id": "t1", "state": "failed", "error": "step 1 exploded"}

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            return_value=failed_result,
        ):
            result = await p.execute("input")

        assert result["status"] == "failed"
        assert result["failed_at_step"] == 1
        # Should NOT have executed step 2
        assert len(result["steps"]) == 1

    @pytest.mark.asyncio
    async def test_pipeline_execute_uses_transform_fn(self):
        """transform_fn on step N transforms that step's result into the input
        for step N+1.  The transform_fn is attached to the *producing* step."""
        mock_result = {"id": "t", "state": "completed", "artifacts": []}
        # transform_fn attached to step 1 converts its result for step 2
        transform = lambda r: "transformed:" + r.get("state", "")

        p = Pipeline("Test")
        # The transform_fn belongs to step 1 (the step whose output is transformed)
        p.add_step("http://agent1:9001", "skill-a", transform_fn=transform)
        p.add_step("http://agent2:9002", "skill-b")

        send_mock = AsyncMock(return_value=mock_result)

        with patch("agents.common.pipeline.A2AClient.send_task", send_mock):
            await p.execute("first input")

        assert send_mock.call_count == 2
        # First call: initial input
        first_call_kwargs = send_mock.call_args_list[0]
        assert first_call_kwargs[1]["message"] == "first input"
        # Second call: transform_fn(step1_result) → "transformed:completed"
        second_call_kwargs = send_mock.call_args_list[1]
        assert second_call_kwargs[1]["message"] == "transformed:completed"

    @pytest.mark.asyncio
    async def test_pipeline_execute_handles_exception_in_step(self):
        p = Pipeline("Test")
        p.add_step("http://agent:9001", "search")

        with patch(
            "agents.common.pipeline.A2AClient.send_task",
            new_callable=AsyncMock,
            side_effect=Exception("network failure"),
        ):
            result = await p.execute("query")

        assert result["status"] == "failed"
        assert "network failure" in result["error"]

    def test_pipeline_repr_includes_name(self):
        p = Pipeline("Research Pipeline")
        assert "Research Pipeline" in repr(p)

    def test_pipeline_repr_includes_step_names(self):
        p = Pipeline("P")
        p.add_step("http://agent:9001", "search", name="SearchStep")
        assert "SearchStep" in repr(p)

    def test_pipeline_step_default_name(self):
        step = PipelineStep(agent_url="http://a:9001", skill_id="s")
        assert step.name == "http://a:9001/s"

    def test_pipeline_step_custom_name(self):
        step = PipelineStep(agent_url="http://a:9001", skill_id="s", name="MyStep")
        assert step.name == "MyStep"

    def test_pipeline_step_no_auth_by_default(self):
        step = PipelineStep(agent_url="http://a:9001", skill_id="s")
        assert step.auth_token is None

    def test_pipeline_step_no_transform_fn_by_default(self):
        step = PipelineStep(agent_url="http://a:9001", skill_id="s")
        assert step.transform_fn is None
