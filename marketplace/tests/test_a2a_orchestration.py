"""Tests for the A2A protocol wiring inside _execute_agent_call.

All HTTP calls are intercepted with unittest.mock.patch / AsyncMock so no
real network connections are made.  Tests use the service-layer functions
directly (no FastAPI route layer) with a self-contained in-memory SQLite DB
via a minimal conftest-free fixture pattern.
"""
from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Target under test
# ---------------------------------------------------------------------------

from marketplace.services.orchestration_service import _execute_agent_call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rpc_response(payload: dict) -> MagicMock:
    """Build a mock httpx Response that returns payload from .json()."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _a2a_config(
    endpoint: str = "http://agent:9001",
    skill_id: str = "web-search",
    timeout: float = 30.0,
) -> dict:
    return {
        "protocol": "a2a",
        "endpoint": endpoint,
        "skill_id": skill_id,
        "timeout": timeout,
    }


def _plain_config(
    endpoint: str = "http://agent:8080/api",
    method: str = "POST",
) -> dict:
    return {
        "endpoint": endpoint,
        "method": method,
    }


def _artifact_rpc_response(inner_data: dict) -> dict:
    """A valid A2A JSON-RPC response containing inner_data encoded in artifact."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "id": "task-abc",
            "state": "completed",
            "artifacts": [
                {
                    "type": "text",
                    "parts": [{"type": "text", "text": json.dumps(inner_data)}],
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# TestExecuteAgentCallA2AProtocol
# ---------------------------------------------------------------------------


class TestExecuteAgentCallA2AProtocol:
    """Tests for _execute_agent_call with protocol=a2a."""

    async def test_sends_json_rpc_tasks_send_method(self) -> None:
        mock_resp = _make_rpc_response(_artifact_rpc_response({"ok": True}))
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            await _execute_agent_call(_a2a_config(), {"query": "python"})

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        body = call_kwargs[1]["json"]
        assert body["method"] == "tasks/send"
        assert body["jsonrpc"] == "2.0"

    async def test_sends_correct_skill_id_in_params(self) -> None:
        mock_resp = _make_rpc_response(_artifact_rpc_response({"ok": True}))
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            await _execute_agent_call(
                _a2a_config(skill_id="analyze-sentiment"), {"text": "hello"}
            )

        body = mock_post.call_args[1]["json"]
        assert body["params"]["skill_id"] == "analyze-sentiment"

    async def test_serializes_input_data_into_message_part(self) -> None:
        mock_resp = _make_rpc_response(_artifact_rpc_response({"ok": True}))
        mock_post = AsyncMock(return_value=mock_resp)

        input_data = {"query": "asyncio tutorial", "num_results": 5}

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            await _execute_agent_call(_a2a_config(), input_data)

        body = mock_post.call_args[1]["json"]
        parts = body["params"]["message"]["parts"]
        assert len(parts) == 1
        assert parts[0]["type"] == "text"
        decoded = json.loads(parts[0]["text"])
        assert decoded == input_data

    async def test_extracts_and_parses_artifact_text(self) -> None:
        inner = {"results": [{"title": "Test", "url": "http://example.com"}]}
        mock_resp = _make_rpc_response(_artifact_rpc_response(inner))
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            result = await _execute_agent_call(_a2a_config(), {})

        assert result == inner

    async def test_posts_to_correct_endpoint(self) -> None:
        endpoint = "http://custom-agent:9005"
        mock_resp = _make_rpc_response(_artifact_rpc_response({}))
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            await _execute_agent_call(_a2a_config(endpoint=endpoint), {})

        call_args = mock_post.call_args
        assert call_args[0][0] == endpoint

    async def test_fallback_when_artifact_extraction_fails(self) -> None:
        """When the artifact path is absent, return result dict directly."""
        rpc_response_no_artifact = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"id": "t1", "state": "completed", "artifacts": []},
        }
        mock_resp = _make_rpc_response(rpc_response_no_artifact)
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            result = await _execute_agent_call(_a2a_config(), {})

        # Fallback: returns the inner result dict
        assert result["state"] == "completed"

    async def test_fallback_when_artifact_text_is_not_valid_json(self) -> None:
        """When artifact text is not JSON, return the outer result dict."""
        rpc_response_bad_json = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "id": "t1",
                "state": "completed",
                "artifacts": [
                    {"parts": [{"type": "text", "text": "not-json-at-all"}]}
                ],
            },
        }
        mock_resp = _make_rpc_response(rpc_response_bad_json)
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            result = await _execute_agent_call(_a2a_config(), {})

        assert "state" in result

    async def test_http_status_error_returns_error_dict(self) -> None:
        import httpx as _httpx

        mock_post = AsyncMock(
            side_effect=_httpx.HTTPStatusError(
                "404 Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404),
            )
        )

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            result = await _execute_agent_call(_a2a_config(), {})

        assert "error" in result
        assert "404" in result["error"]

    async def test_request_error_returns_error_dict(self) -> None:
        import httpx as _httpx

        mock_post = AsyncMock(
            side_effect=_httpx.RequestError("Connection refused", request=MagicMock())
        )

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            result = await _execute_agent_call(_a2a_config(), {})

        assert "error" in result

    async def test_empty_endpoint_returns_error_dict_without_http_call(self) -> None:
        config = {"protocol": "a2a", "endpoint": "", "skill_id": "x"}
        result = await _execute_agent_call(config, {"input": "data"})
        assert "error" in result


# ---------------------------------------------------------------------------
# TestExecuteAgentCallPlainHTTP
# ---------------------------------------------------------------------------


class TestExecuteAgentCallPlainHTTP:
    """Tests for _execute_agent_call WITHOUT protocol=a2a (plain HTTP POST)."""

    async def test_plain_post_sends_merged_input_and_payload(self) -> None:
        response_body = {"status": "ok"}
        mock_resp = _make_rpc_response(response_body)
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            result = await _execute_agent_call(
                _plain_config(),
                {"user_input": "hello"},
            )

        mock_post.assert_called_once()
        sent_json = mock_post.call_args[1]["json"]
        assert "user_input" in sent_json

    async def test_plain_post_returns_response_json(self) -> None:
        response_body = {"processed": True, "items": [1, 2, 3]}
        mock_resp = _make_rpc_response(response_body)
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            result = await _execute_agent_call(_plain_config(), {})

        assert result == response_body

    async def test_plain_get_uses_get_method(self) -> None:
        response_body = {"data": "fetched"}
        mock_resp = _make_rpc_response(response_body)
        mock_get = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = mock_get
            mock_client.post = AsyncMock()  # should NOT be called
            mock_cls.return_value = mock_client

            await _execute_agent_call(_plain_config(method="GET"), {"param": "val"})

        mock_get.assert_called_once()

    async def test_plain_post_http_error_returns_error_dict(self) -> None:
        import httpx as _httpx

        mock_post = AsyncMock(
            side_effect=_httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )
        )

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            result = await _execute_agent_call(_plain_config(), {})

        assert "error" in result
        assert "500" in result["error"]

    async def test_plain_no_endpoint_returns_error_dict(self) -> None:
        result = await _execute_agent_call({"method": "POST", "endpoint": ""}, {})
        assert "error" in result

    async def test_plain_post_config_payload_merged_with_input_data(self) -> None:
        response_body = {"ok": 1}
        mock_resp = _make_rpc_response(response_body)
        mock_post = AsyncMock(return_value=mock_resp)

        config = {
            "endpoint": "http://agent:8080",
            "method": "POST",
            "payload": {"extra_key": "extra_value"},
        }

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            await _execute_agent_call(config, {"input_key": "input_value"})

        sent_json = mock_post.call_args[1]["json"]
        assert sent_json.get("extra_key") == "extra_value"
        assert sent_json.get("input_key") == "input_value"


# ---------------------------------------------------------------------------
# TestExecuteAgentCallRpcEnvelope
# ---------------------------------------------------------------------------


class TestExecuteAgentCallRpcEnvelope:
    """Verify the exact structure of the JSON-RPC envelope sent by A2A calls."""

    async def test_rpc_envelope_has_jsonrpc_version_2(self) -> None:
        mock_resp = _make_rpc_response(_artifact_rpc_response({}))
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            await _execute_agent_call(_a2a_config(), {})

        body = mock_post.call_args[1]["json"]
        assert body["jsonrpc"] == "2.0"

    async def test_rpc_envelope_has_id_field(self) -> None:
        mock_resp = _make_rpc_response(_artifact_rpc_response({}))
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            await _execute_agent_call(_a2a_config(), {})

        body = mock_post.call_args[1]["json"]
        assert "id" in body

    async def test_rpc_envelope_message_has_parts_array(self) -> None:
        mock_resp = _make_rpc_response(_artifact_rpc_response({}))
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            await _execute_agent_call(_a2a_config(), {"x": 1})

        body = mock_post.call_args[1]["json"]
        message = body["params"]["message"]
        assert "parts" in message
        assert isinstance(message["parts"], list)

    async def test_rpc_envelope_part_type_is_text(self) -> None:
        mock_resp = _make_rpc_response(_artifact_rpc_response({}))
        mock_post = AsyncMock(return_value=mock_resp)

        with patch("marketplace.services.orchestration_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_cls.return_value = mock_client

            await _execute_agent_call(_a2a_config(), {"x": 1})

        body = mock_post.call_args[1]["json"]
        part = body["params"]["message"]["parts"][0]
        assert part["type"] == "text"
