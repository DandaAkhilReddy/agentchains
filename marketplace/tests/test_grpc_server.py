"""Tests for grpc/server.py."""

import json
import time
from types import SimpleNamespace

import pytest

from marketplace.grpc.server import (
    GRPC_PORT,
    AgentServiceServicer,
    OrchestrationServiceServicer,
    _ALLOWED_TASK_TYPES,
    _MAX_INPUT_SIZE,
    _validate_and_parse_input,
    create_grpc_server,
)


class TestValidateAndParseInput:
    def test_empty_string(self):
        assert _validate_and_parse_input("") == {}

    def test_valid_json(self):
        assert _validate_and_parse_input(json.dumps({"a": 1})) == {"a": 1}

    def test_exceeds_size(self):
        big = json.dumps({"x": "a" * (_MAX_INPUT_SIZE + 1)})
        with pytest.raises(ValueError, match="exceeds maximum size"):
            _validate_and_parse_input(big)

    def test_invalid_json(self):
        with pytest.raises(ValueError, match="Invalid JSON input"):
            _validate_and_parse_input("not-json")

    def test_non_dict(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            _validate_and_parse_input("[1, 2]")

def _req(**kwargs):
    return SimpleNamespace(**kwargs)


class TestAgentExecuteTask:
    @pytest.fixture()
    def svc(self):
        return AgentServiceServicer()

    async def test_agent_call(self, svc):
        req = _req(task_id="t1", task_type="agent_call", input_json="{}", agent_id="a1")
        res = await svc.ExecuteTask(req, None)
        assert res["status"] == "success"
        assert res["task_id"] == "t1"
        out = json.loads(res["output_json"])
        assert "Agent call" in out["result"]

    async def test_tool_call(self, svc):
        req = _req(task_id="t2", task_type="tool_call", input_json="{}", agent_id="a1")
        res = await svc.ExecuteTask(req, None)
        assert res["status"] == "success"
        assert "Tool call" in json.loads(res["output_json"])["result"]

    async def test_query(self, svc):
        req = _req(task_id="t3", task_type="query", input_json="{}", agent_id="a1")
        res = await svc.ExecuteTask(req, None)
        assert res["status"] == "success"
        assert "Query" in json.loads(res["output_json"])["result"]

    async def test_invalid_task_type(self, svc):
        req = _req(task_id="t4", task_type="bad_type", input_json="{}", agent_id="a1")
        res = await svc.ExecuteTask(req, None)
        assert res["status"] == "error"
        assert "Invalid task type" in res["error_message"]

    async def test_bad_input_json(self, svc):
        req = _req(task_id="t5", task_type="agent_call", input_json="broken", agent_id="a1")
        res = await svc.ExecuteTask(req, None)
        assert res["status"] == "error"
        assert "Invalid JSON" in res["error_message"]

    async def test_oversized_input(self, svc):
        req = _req(task_id="t6", task_type="agent_call", input_json="a" * (_MAX_INPUT_SIZE + 2), agent_id="a1")
        res = await svc.ExecuteTask(req, None)
        assert res["status"] == "error"
        assert "exceeds" in res["error_message"]

    async def test_execution_time_positive(self, svc):
        req = _req(task_id="t7", task_type="query", input_json="{}", agent_id="a1")
        res = await svc.ExecuteTask(req, None)
        assert res["execution_time_ms"] >= 0

    async def test_active_tasks_counter(self, svc):
        assert svc._active_tasks == 0
        req = _req(task_id="t8", task_type="query", input_json="{}", agent_id="a1")
        await svc.ExecuteTask(req, None)
        assert svc._active_tasks == 0

    async def test_empty_input_json(self, svc):
        req = _req(task_id="t9", task_type="query", input_json="", agent_id="a1")
        res = await svc.ExecuteTask(req, None)
        assert res["status"] == "success"

    async def test_non_dict_input(self, svc):
        req = _req(task_id="t10", task_type="query", input_json="[1]", agent_id="a1")
        res = await svc.ExecuteTask(req, None)
        assert res["status"] == "error"
        assert "must be a JSON object" in res["error_message"]

    async def test_cost_usd_zero(self, svc):
        req = _req(task_id="t11", task_type="agent_call", input_json="{}", agent_id="a1")
        res = await svc.ExecuteTask(req, None)
        assert res["cost_usd"] == 0.0


class TestAgentStreamProgress:
    async def test_stream_yields_10(self):
        svc = AgentServiceServicer()
        req = _req(task_id="sp1")
        items = [item async for item in svc.StreamTaskProgress(req, None)]
        assert len(items) == 10
        assert items[0]["status"] == "running"
        assert items[-1]["status"] == "completed"
        assert items[-1]["progress"] == 1.0

    async def test_stream_progress_increments(self):
        svc = AgentServiceServicer()
        req = _req(task_id="sp2")
        items = [item async for item in svc.StreamTaskProgress(req, None)]
        for i, item in enumerate(items):
            assert abs(item["progress"] - (i + 1) / 10.0) < 1e-9

    async def test_stream_has_timestamp(self):
        svc = AgentServiceServicer()
        req = _req(task_id="sp3")
        items = [item async for item in svc.StreamTaskProgress(req, None)]
        assert all("timestamp_ms" in it for it in items)


class TestAgentHealthCheck:
    async def test_health_ok(self):
        svc = AgentServiceServicer()
        res = await svc.HealthCheck(_req(), None)
        assert res["status"] == "ok"
        assert "version" in res

    async def test_health_no_secrets(self):
        svc = AgentServiceServicer()
        res = await svc.HealthCheck(_req(), None)
        assert "uptime" not in res
        assert "active_tasks" not in res


class TestAgentCapabilities:
    async def test_caps(self):
        svc = AgentServiceServicer()
        res = await svc.GetCapabilities(_req(agent_id="x"), None)
        assert res["agent_id"] == "x"
        assert "task_execution" in res["capabilities"]
        assert set(res["supported_tasks"]) == {"agent_call", "tool_call", "query"}
        assert res["max_concurrent_tasks"] == 50


class TestAgentSendMessage:
    async def test_ack(self):
        svc = AgentServiceServicer()
        req = _req(message_id="m1", from_agent_id="a", to_agent_id="b", message_type="text")
        res = await svc.SendMessage(req, None)
        assert res["acknowledged"] is True
        assert res["message_id"] == "m1"


class TestDispatch:
    async def test_unsupported(self):
        svc = AgentServiceServicer()
        r = await svc._dispatch_task("unknown", {}, "a")
        assert "Unsupported" in r["result"]


class TestOrchExecuteNode:
    async def test_success(self):
        svc = OrchestrationServiceServicer()
        req = _req(execution_id="e1", node_id="n1", node_type="task", input_json="{}")
        res = await svc.ExecuteNode(req, None)
        assert res["status"] == "completed"
        assert res["cost_usd"] == 0.001

    async def test_invalid_input(self):
        svc = OrchestrationServiceServicer()
        req = _req(execution_id="e2", node_id="n2", node_type="task", input_json="bad")
        res = await svc.ExecuteNode(req, None)
        assert res["status"] == "error"

    async def test_empty_input(self):
        svc = OrchestrationServiceServicer()
        req = _req(execution_id="e3", node_id="n3", node_type="task", input_json="")
        res = await svc.ExecuteNode(req, None)
        assert res["status"] == "completed"


class TestOrchReportStatus:
    async def test_ack(self):
        svc = OrchestrationServiceServicer()
        req = _req(execution_id="e1", node_id="n1", status="running")
        res = await svc.ReportNodeStatus(req, None)
        assert res["acknowledged"] is True


class TestConstants:
    def test_port(self):
        assert GRPC_PORT == 50051

    def test_task_types(self):
        assert _ALLOWED_TASK_TYPES == {"agent_call", "tool_call", "query"}

    def test_max_input_size(self):
        assert _MAX_INPUT_SIZE == 65_536


class TestCreateServer:
    def test_returns_tuple(self):
        result = create_grpc_server()
        assert isinstance(result, tuple)
        assert result[1] == GRPC_PORT

    def test_custom_port(self):
        result = create_grpc_server(port=9999)
        assert result[1] == 9999

