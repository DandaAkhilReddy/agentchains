"""Judge classes — 3-layer evaluation pipeline for generated tests.

Each judge evaluates tests against the source code using an LLM,
returning a structured JudgeVerdict with pass/fail, score, issues,
and suggestions.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

import structlog

from agents.common.model_agent import ModelAgent
from agents.unit_test_agent.config import UnitTestAgentConfig
from agents.unit_test_agent.exceptions import JudgeEvaluationError
from agents.unit_test_agent.prompts import (
    ADVERSARIAL_JUDGE_SYSTEM_PROMPT,
    ADVERSARIAL_JUDGE_USER_PROMPT,
    COVERAGE_JUDGE_SYSTEM_PROMPT,
    COVERAGE_JUDGE_USER_PROMPT,
    QUALITY_JUDGE_SYSTEM_PROMPT,
    QUALITY_JUDGE_USER_PROMPT,
)
from agents.unit_test_agent.schemas import JudgeVerdict

logger = structlog.get_logger(__name__)


class BaseJudge(ABC):
    """Abstract judge that evaluates test quality via LLM.

    Subclasses set their own prompts and threshold.

    Args:
        model_agent: Provider-agnostic LLM client.
        config: Pipeline configuration.
    """

    judge_name: str = "base"

    def __init__(
        self,
        model_agent: ModelAgent,
        config: UnitTestAgentConfig,
    ) -> None:
        self._model = model_agent
        self._config = config

    @property
    @abstractmethod
    def threshold(self) -> float:
        """Minimum score to pass this judge."""

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Return the system prompt for this judge."""

    @abstractmethod
    def _get_user_prompt(self, source_code: str, test_code: str) -> str:
        """Return the user prompt for this judge."""

    async def evaluate(self, source_code: str, test_code: str) -> JudgeVerdict:
        """Evaluate test code against source code.

        Args:
            source_code: The original source code being tested.
            test_code: The generated test code to evaluate.

        Returns:
            JudgeVerdict with pass/fail, score, issues, and suggestions.

        Raises:
            JudgeEvaluationError: If the LLM response cannot be parsed.
        """
        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(source_code, test_code)
        data = await self._call_llm(system_prompt, user_prompt)

        score = float(data.get("score", 0))
        passed = score >= self.threshold

        verdict = JudgeVerdict(
            passed=passed,
            score=score,
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
        )

        logger.info(
            "judge_evaluation",
            judge=self.judge_name,
            score=score,
            passed=passed,
            issue_count=len(verdict.issues),
        )
        return verdict

    async def _call_llm(
        self, system_prompt: str, user_prompt: str
    ) -> dict:
        """Send prompts to LLM and parse JSON response.

        Args:
            system_prompt: System prompt for the judge.
            user_prompt: User prompt with source/test code.

        Returns:
            Parsed dict from LLM JSON response.

        Raises:
            JudgeEvaluationError: If JSON parsing fails.
        """
        response = await self._model.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self._config.model or None,
            temperature=0.2,
            max_tokens=self._config.max_tokens,
        )

        text = response.content.strip()

        # Strip markdown fences
        if text.startswith("```"):
            lines = text.splitlines()
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[start:end]).strip()

        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict, got {type(data).__name__}")
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            raise JudgeEvaluationError(
                f"{self.judge_name} failed to parse LLM response: {exc}"
            ) from exc


class CoverageJudge(BaseJudge):
    """Layer 1 — evaluates code coverage completeness."""

    judge_name: str = "coverage"

    @property
    def threshold(self) -> float:
        return self._config.coverage_threshold

    def _get_system_prompt(self) -> str:
        return COVERAGE_JUDGE_SYSTEM_PROMPT.format(threshold=self.threshold)

    def _get_user_prompt(self, source_code: str, test_code: str) -> str:
        return COVERAGE_JUDGE_USER_PROMPT.format(
            source_code=source_code,
            test_code=test_code,
            threshold=self.threshold,
        )


class QualityJudge(BaseJudge):
    """Layer 2 — evaluates test quality and best practices."""

    judge_name: str = "quality"

    @property
    def threshold(self) -> float:
        return self._config.quality_threshold

    def _get_system_prompt(self) -> str:
        return QUALITY_JUDGE_SYSTEM_PROMPT.format(threshold=self.threshold)

    def _get_user_prompt(self, source_code: str, test_code: str) -> str:
        return QUALITY_JUDGE_USER_PROMPT.format(
            source_code=source_code,
            test_code=test_code,
            threshold=self.threshold,
        )


class AdversarialJudge(BaseJudge):
    """Layer 3 — adversarial mutation analysis."""

    judge_name: str = "adversarial"

    @property
    def threshold(self) -> float:
        return self._config.adversarial_threshold

    def _get_system_prompt(self) -> str:
        return ADVERSARIAL_JUDGE_SYSTEM_PROMPT.format(threshold=self.threshold)

    def _get_user_prompt(self, source_code: str, test_code: str) -> str:
        return ADVERSARIAL_JUDGE_USER_PROMPT.format(
            source_code=source_code,
            test_code=test_code,
            threshold=self.threshold,
        )
