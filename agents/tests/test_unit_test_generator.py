"""Tests for TestGeneratorAgent — generation, improvement, and parse fallbacks."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.unit_test_agent.config import UnitTestAgentConfig
from agents.unit_test_agent.exceptions import TestGenerationError
from agents.unit_test_agent.generator import TestGeneratorAgent
from agents.unit_test_agent.schemas import TestGenerationRequest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_completion_response(content: str) -> MagicMock:
    """Create a mock CompletionResponse with the given content."""
    resp = MagicMock()
    resp.content = content
    resp.completion_tokens = 100
    return resp


def _make_model_agent(content: str) -> MagicMock:
    """Create a mock ModelAgent that returns the given content."""
    model = MagicMock()
    model.complete = AsyncMock(return_value=_make_completion_response(content))
    return model


@pytest.fixture
def config() -> UnitTestAgentConfig:
    return UnitTestAgentConfig()


@pytest.fixture
def request_obj() -> TestGenerationRequest:
    return TestGenerationRequest(
        source_code="def add(a, b): return a + b",
        source_path="math_utils.py",
    )


# ---------------------------------------------------------------------------
# Generation tests
# ---------------------------------------------------------------------------


class TestGenerate:
    """Tests for the generate() method."""

    @pytest.mark.asyncio
    async def test_json_response(
        self, config: UnitTestAgentConfig, request_obj: TestGenerationRequest
    ) -> None:
        payload = json.dumps({
            "test_code": "def test_add(): assert add(1, 2) == 3",
            "test_count": 1,
            "imports": ["pytest"],
        })
        model = _make_model_agent(payload)
        gen = TestGeneratorAgent(model, config)

        result = await gen.generate(request_obj)
        assert result.test_code == "def test_add(): assert add(1, 2) == 3"
        assert result.test_count == 1
        assert result.imports == ["pytest"]

    @pytest.mark.asyncio
    async def test_json_with_markdown_fences(
        self, config: UnitTestAgentConfig, request_obj: TestGenerationRequest
    ) -> None:
        payload = '```json\n' + json.dumps({
            "test_code": "def test_x(): pass",
            "test_count": 1,
            "imports": [],
        }) + '\n```'
        model = _make_model_agent(payload)
        gen = TestGeneratorAgent(model, config)

        result = await gen.generate(request_obj)
        assert result.test_code == "def test_x(): pass"

    @pytest.mark.asyncio
    async def test_fallback_code_block_extraction(
        self, config: UnitTestAgentConfig, request_obj: TestGenerationRequest
    ) -> None:
        raw = "Here are the tests:\n```python\ndef test_add():\n    assert add(1, 2) == 3\n```"
        model = _make_model_agent(raw)
        gen = TestGeneratorAgent(model, config)

        result = await gen.generate(request_obj)
        assert "def test_add" in result.test_code
        assert result.test_count == 1

    @pytest.mark.asyncio
    async def test_fallback_raw_code(
        self, config: UnitTestAgentConfig, request_obj: TestGenerationRequest
    ) -> None:
        raw = "import pytest\n\ndef test_add():\n    assert add(1, 2) == 3\n\ndef test_sub():\n    assert sub(3, 1) == 2"
        model = _make_model_agent(raw)
        gen = TestGeneratorAgent(model, config)

        result = await gen.generate(request_obj)
        assert result.test_count == 2

    @pytest.mark.asyncio
    async def test_unparseable_response_raises(
        self, config: UnitTestAgentConfig, request_obj: TestGenerationRequest
    ) -> None:
        model = _make_model_agent("I cannot generate tests for this code.")
        gen = TestGeneratorAgent(model, config)

        with pytest.raises(TestGenerationError):
            await gen.generate(request_obj)

    @pytest.mark.asyncio
    async def test_with_context(self, config: UnitTestAgentConfig) -> None:
        req = TestGenerationRequest(
            source_code="class Calc: pass",
            source_path="calc.py",
            context="This is a calculator class.",
        )
        payload = json.dumps({
            "test_code": "def test_calc(): pass",
            "test_count": 1,
            "imports": [],
        })
        model = _make_model_agent(payload)
        gen = TestGeneratorAgent(model, config)

        result = await gen.generate(req)
        assert result.test_code == "def test_calc(): pass"

        # Verify the context was included in the prompt
        call_args = model.complete.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "calculator class" in user_msg["content"]


# ---------------------------------------------------------------------------
# Improvement tests
# ---------------------------------------------------------------------------


class TestImprove:
    """Tests for the improve() method."""

    @pytest.mark.asyncio
    async def test_improve_with_feedback(
        self, config: UnitTestAgentConfig, request_obj: TestGenerationRequest
    ) -> None:
        payload = json.dumps({
            "test_code": "def test_add_edge(): assert add(0, 0) == 0",
            "test_count": 1,
            "imports": ["pytest"],
        })
        model = _make_model_agent(payload)
        gen = TestGeneratorAgent(model, config)

        result = await gen.improve(
            request_obj,
            current_tests="def test_add(): pass",
            issues=["Missing edge case for zero"],
            suggestions=["Add test for zero inputs"],
        )
        assert "test_add_edge" in result.test_code

        # Verify feedback was included in the prompt
        call_args = model.complete.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "Missing edge case" in user_msg["content"]

    @pytest.mark.asyncio
    async def test_improve_unparseable_raises(
        self, config: UnitTestAgentConfig, request_obj: TestGenerationRequest
    ) -> None:
        model = _make_model_agent("Sorry, cannot improve.")
        gen = TestGeneratorAgent(model, config)

        with pytest.raises(TestGenerationError):
            await gen.improve(
                request_obj,
                current_tests="...",
                issues=["issue"],
                suggestions=["suggestion"],
            )


# ---------------------------------------------------------------------------
# Parse edge cases
# ---------------------------------------------------------------------------


class TestParseResponse:
    """Tests for the _parse_response edge cases."""

    def test_json_without_test_code_key(self, config: UnitTestAgentConfig) -> None:
        model = MagicMock()
        gen = TestGeneratorAgent(model, config)

        # JSON that doesn't have test_code falls to fallback
        with pytest.raises(TestGenerationError):
            gen._parse_response('{"result": "something"}')

    def test_empty_string_raises(self, config: UnitTestAgentConfig) -> None:
        model = MagicMock()
        gen = TestGeneratorAgent(model, config)

        with pytest.raises(TestGenerationError):
            gen._parse_response("")

    def test_async_def_test_counted(self, config: UnitTestAgentConfig) -> None:
        model = MagicMock()
        gen = TestGeneratorAgent(model, config)

        raw = "async def test_async_op():\n    result = await op()\n    assert result"
        result = gen._parse_response(raw)
        assert result.test_count == 1
