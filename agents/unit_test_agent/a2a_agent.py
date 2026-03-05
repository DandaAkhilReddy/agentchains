"""A2A wrapper for the Unit Testing Agent.

Exposes the test pipeline as a single A2A skill on port 9020.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from agents.common.base_agent import BaseA2AAgent
from agents.common.model_agent import ModelAgent
from agents.unit_test_agent.config import UnitTestAgentConfig
from agents.unit_test_agent.orchestrator import TestPipelineOrchestrator
from agents.unit_test_agent.schemas import TestGenerationRequest

logger = structlog.get_logger(__name__)

_DEFAULT_PORT = 9020


class UnitTestA2AAgent(BaseA2AAgent):
    """A2A agent that generates and validates unit tests.

    Wraps TestPipelineOrchestrator as a single A2A skill.

    Args:
        model_agent: Provider-agnostic LLM client.
        config: Pipeline configuration.
        port: HTTP port for the A2A server.
    """

    def __init__(
        self,
        model_agent: ModelAgent,
        config: UnitTestAgentConfig | None = None,
        port: int = _DEFAULT_PORT,
    ) -> None:
        super().__init__(
            name="Unit Test Agent",
            description=(
                "Generates unit tests for source code and validates them "
                "through a 3-layer judge pipeline (coverage, quality, adversarial)."
            ),
            port=port,
            skills=[
                {
                    "id": "generate_unit_tests",
                    "name": "Generate Unit Tests",
                    "description": (
                        "Generate and validate unit tests for a source file. "
                        "Input: {source_code, source_path, language, framework, context}"
                    ),
                    "tags": ["testing", "unit-tests", "code-quality"],
                }
            ],
        )
        self._orchestrator = TestPipelineOrchestrator(
            model_agent, config or UnitTestAgentConfig()
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Process a skill invocation.

        Args:
            skill_id: Must be "generate_unit_tests".
            input_data: Dict with source_code, source_path, and optional fields.

        Returns:
            Dict with test_code, test_count, evaluations, iterations, passed.
        """
        if skill_id != "generate_unit_tests":
            return {"error": f"Unknown skill: {skill_id}"}

        request = TestGenerationRequest(
            source_code=input_data.get("source_code", ""),
            source_path=input_data.get("source_path", "unknown"),
            language=input_data.get("language", "python"),
            framework=input_data.get("framework", "pytest"),
            context=input_data.get("context", ""),
        )

        if not request.source_code:
            return {"error": "source_code is required"}

        logger.info(
            "unit_test_skill_invoked",
            source_path=request.source_path,
            language=request.language,
        )

        report = await self._orchestrator.run(request)

        evaluations_data = [
            {
                "judge_name": e.judge_name,
                "passed": e.verdict.passed,
                "score": e.verdict.score,
                "issues": list(e.verdict.issues),
                "suggestions": list(e.verdict.suggestions),
                "iteration": e.iteration,
            }
            for e in report.evaluations
        ]

        return {
            "test_code": report.test_code,
            "test_count": report.test_count,
            "evaluations": evaluations_data,
            "iterations": report.iterations,
            "passed": report.passed,
        }
