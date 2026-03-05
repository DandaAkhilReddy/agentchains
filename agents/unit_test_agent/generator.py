"""Test generator — produces unit tests from source code via LLM.

Uses ModelAgent for provider-agnostic completions. Supports initial
generation and iterative improvement based on judge feedback.
"""

from __future__ import annotations

import json
import re

import structlog

from agents.common.model_agent import ModelAgent
from agents.unit_test_agent.config import UnitTestAgentConfig
from agents.unit_test_agent.exceptions import TestGenerationError
from agents.unit_test_agent.prompts import (
    GENERATOR_IMPROVE_PROMPT,
    GENERATOR_SYSTEM_PROMPT,
    GENERATOR_USER_PROMPT,
)
from agents.unit_test_agent.schemas import GeneratedTests, TestGenerationRequest

logger = structlog.get_logger(__name__)


class TestGeneratorAgent:
    """Generates unit tests from source code using an LLM.

    Args:
        model_agent: Provider-agnostic LLM client.
        config: Pipeline configuration with model/token settings.
    """

    def __init__(
        self,
        model_agent: ModelAgent,
        config: UnitTestAgentConfig,
    ) -> None:
        self._model = model_agent
        self._config = config

    async def generate(self, request: TestGenerationRequest) -> GeneratedTests:
        """Generate an initial test suite for the given source code.

        Args:
            request: Source code and metadata to generate tests for.

        Returns:
            Generated test code, count, and imports.

        Raises:
            TestGenerationError: If the LLM response cannot be parsed.
        """
        context_section = (
            f"Additional context:\n{request.context}" if request.context else ""
        )
        user_prompt = GENERATOR_USER_PROMPT.format(
            language=request.language,
            framework=request.framework,
            source_path=request.source_path,
            context_section=context_section,
            source_code=request.source_code,
        )

        response = await self._model.complete(
            messages=[
                {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=self._config.model or None,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )

        logger.info(
            "test_generation_complete",
            source_path=request.source_path,
            tokens=response.completion_tokens,
        )
        return self._parse_response(response.content)

    async def improve(
        self,
        request: TestGenerationRequest,
        current_tests: str,
        issues: list[str],
        suggestions: list[str],
    ) -> GeneratedTests:
        """Improve existing tests based on judge feedback.

        Args:
            request: Original source code and metadata.
            current_tests: The current test code to improve.
            issues: List of issues identified by judges.
            suggestions: List of improvement suggestions from judges.

        Returns:
            Improved test code, count, and imports.

        Raises:
            TestGenerationError: If the LLM response cannot be parsed.
        """
        user_prompt = GENERATOR_IMPROVE_PROMPT.format(
            language=request.language,
            framework=request.framework,
            source_path=request.source_path,
            source_code=request.source_code,
            current_tests=current_tests,
            issues="\n".join(f"- {issue}" for issue in issues),
            suggestions="\n".join(f"- {s}" for s in suggestions),
        )

        response = await self._model.complete(
            messages=[
                {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=self._config.model or None,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )

        logger.info(
            "test_improvement_complete",
            source_path=request.source_path,
            tokens=response.completion_tokens,
        )
        return self._parse_response(response.content)

    def _parse_response(self, raw: str) -> GeneratedTests:
        """Parse LLM response into GeneratedTests.

        Tries JSON first, falls back to regex code-block extraction.

        Args:
            raw: Raw LLM response string.

        Returns:
            Parsed GeneratedTests.

        Raises:
            TestGenerationError: If no test code can be extracted.
        """
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[start:end]).strip()

        # Try JSON parse
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "test_code" in data:
                return GeneratedTests(
                    test_code=data["test_code"],
                    test_count=data.get("test_count", 0),
                    imports=data.get("imports", []),
                )
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

        # Fallback: extract code blocks via regex
        code_match = re.search(
            r"```(?:python)?\s*\n(.*?)```", raw, re.DOTALL
        )
        if code_match:
            test_code = code_match.group(1).strip()
            test_count = len(re.findall(r"^\s*(?:def|async def) test_", test_code, re.MULTILINE))
            return GeneratedTests(test_code=test_code, test_count=test_count)

        # Last resort: if raw looks like code (contains def test_), use it directly
        if "def test_" in raw:
            test_count = len(re.findall(r"^\s*(?:def|async def) test_", raw, re.MULTILINE))
            return GeneratedTests(test_code=raw.strip(), test_count=test_count)

        raise TestGenerationError(
            "Failed to extract test code from LLM response"
        )
