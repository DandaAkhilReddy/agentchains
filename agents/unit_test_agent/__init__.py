"""Unit Testing Agent — 3-layer judge pipeline for automated test generation.

Public API:
    TestPipelineOrchestrator  — main orchestrator (LangGraph or sequential)
    UnitTestA2AAgent          — A2A HTTP wrapper
    UnitTestAgentConfig       — pipeline configuration
    TestGenerationRequest     — input schema
    FinalReport               — output schema
"""

from __future__ import annotations

from agents.unit_test_agent.a2a_agent import UnitTestA2AAgent
from agents.unit_test_agent.config import UnitTestAgentConfig
from agents.unit_test_agent.exceptions import (
    BudgetExhaustedError,
    JudgeEvaluationError,
    TestGenerationError,
    UnitTestAgentError,
)
from agents.unit_test_agent.orchestrator import TestPipelineOrchestrator
from agents.unit_test_agent.schemas import (
    FinalReport,
    GeneratedTests,
    JudgeEvaluation,
    JudgeVerdict,
    PipelineState,
    TestGenerationRequest,
)

__all__ = [
    "BudgetExhaustedError",
    "FinalReport",
    "GeneratedTests",
    "JudgeEvaluation",
    "JudgeEvaluationError",
    "JudgeVerdict",
    "PipelineState",
    "TestGenerationError",
    "TestGenerationRequest",
    "TestPipelineOrchestrator",
    "UnitTestA2AAgent",
    "UnitTestAgentConfig",
    "UnitTestAgentError",
]
