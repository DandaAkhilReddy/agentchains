"""LangGraph-powered test pipeline orchestrator.

Runs: generate -> judge_coverage -> judge_quality -> judge_adversarial -> report
with conditional retry routing back to generate on judge failures.

Falls back to a sequential loop if LangGraph is not installed.
"""

from __future__ import annotations

import structlog

from agents.common.model_agent import ModelAgent
from agents.unit_test_agent.config import UnitTestAgentConfig
from agents.unit_test_agent.exceptions import BudgetExhaustedError
from agents.unit_test_agent.generator import TestGeneratorAgent
from agents.unit_test_agent.judges import (
    AdversarialJudge,
    BaseJudge,
    CoverageJudge,
    QualityJudge,
)
from agents.unit_test_agent.schemas import (
    FinalReport,
    JudgeEvaluation,
    JudgeVerdict,
    PipelineState,
    TestGenerationRequest,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Optional LangGraph import — graceful fallback
# ---------------------------------------------------------------------------

try:
    from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None  # type: ignore[assignment,misc]
    END = None  # type: ignore[assignment]


class TestPipelineOrchestrator:
    """Orchestrates the generate-judge-retry pipeline.

    Uses LangGraph StateGraph when available for conditional routing.
    Falls back to a sequential loop with the same retry logic otherwise.

    Args:
        model_agent: Provider-agnostic LLM client.
        config: Pipeline configuration with retry limits and thresholds.
    """

    def __init__(
        self,
        model_agent: ModelAgent,
        config: UnitTestAgentConfig | None = None,
    ) -> None:
        self._config = config or UnitTestAgentConfig()
        self._generator = TestGeneratorAgent(model_agent, self._config)
        self._coverage_judge = CoverageJudge(model_agent, self._config)
        self._quality_judge = QualityJudge(model_agent, self._config)
        self._adversarial_judge = AdversarialJudge(model_agent, self._config)
        self._graph = self._build_graph() if LANGGRAPH_AVAILABLE else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, request: TestGenerationRequest) -> FinalReport:
        """Execute the full test generation and evaluation pipeline.

        Args:
            request: Source code and metadata to generate tests for.

        Returns:
            FinalReport with test code, evaluations, and pass/fail status.

        Raises:
            BudgetExhaustedError: If total iterations exceed the budget.
        """
        if self._graph is not None:
            return await self._run_with_langgraph(request)
        return await self._run_sequential(request)

    # ------------------------------------------------------------------
    # LangGraph path
    # ------------------------------------------------------------------

    def _build_graph(self) -> object | None:
        """Build and compile the LangGraph StateGraph."""
        if not LANGGRAPH_AVAILABLE or StateGraph is None:
            return None

        graph: object = StateGraph(PipelineState)

        graph.add_node("generate_tests", self._node_generate)  # type: ignore[union-attr]
        graph.add_node("judge_coverage", self._node_judge_coverage)  # type: ignore[union-attr]
        graph.add_node("judge_quality", self._node_judge_quality)  # type: ignore[union-attr]
        graph.add_node("judge_adversarial", self._node_judge_adversarial)  # type: ignore[union-attr]
        graph.add_node("build_report", self._node_build_report)  # type: ignore[union-attr]

        graph.set_entry_point("generate_tests")  # type: ignore[union-attr]
        graph.add_edge("generate_tests", "judge_coverage")  # type: ignore[union-attr]

        graph.add_conditional_edges(  # type: ignore[union-attr]
            "judge_coverage",
            self._route_after_coverage,
            {
                "retry": "generate_tests",
                "next": "judge_quality",
                "stop": "build_report",
            },
        )

        graph.add_conditional_edges(  # type: ignore[union-attr]
            "judge_quality",
            self._route_after_quality,
            {
                "retry": "generate_tests",
                "next": "judge_adversarial",
                "stop": "build_report",
            },
        )

        graph.add_conditional_edges(  # type: ignore[union-attr]
            "judge_adversarial",
            self._route_after_adversarial,
            {
                "retry": "generate_tests",
                "next": "build_report",
                "stop": "build_report",
            },
        )

        graph.add_edge("build_report", END)  # type: ignore[union-attr]

        return graph.compile()  # type: ignore[union-attr]

    async def _run_with_langgraph(
        self, request: TestGenerationRequest
    ) -> FinalReport:
        """Execute via LangGraph."""
        initial_state: PipelineState = {
            "source_code": request.source_code,
            "source_path": request.source_path,
            "language": request.language,
            "framework": request.framework,
            "context": request.context,
            "test_code": "",
            "test_count": 0,
            "imports": [],
            "evaluations": [],
            "current_judge": "",
            "iteration": 0,
            "coverage_retries": 0,
            "quality_retries": 0,
            "adversarial_retries": 0,
            "total_iterations": 0,
            "passed": False,
            "error": "",
        }

        result: PipelineState = await self._graph.ainvoke(initial_state)  # type: ignore[union-attr]
        return self._state_to_report(result)

    # ------------------------------------------------------------------
    # LangGraph nodes
    # ------------------------------------------------------------------

    async def _node_generate(self, state: PipelineState) -> dict:
        """Generate or improve tests based on current state."""
        request = self._state_to_request(state)
        total = state.get("total_iterations", 0)

        if total >= self._config.total_max_iterations:
            return {"error": "budget_exhausted", "passed": False}

        if state.get("test_code") and state.get("evaluations"):
            # Improvement pass — aggregate feedback from failed judges
            issues, suggestions = self._aggregate_feedback(state)
            result = await self._generator.improve(
                request, state["test_code"], issues, suggestions
            )
        else:
            result = await self._generator.generate(request)

        return {
            "test_code": result.test_code,
            "test_count": result.test_count,
            "imports": list(result.imports),
            "total_iterations": total + 1,
            "iteration": state.get("iteration", 0) + 1,
        }

    async def _node_judge_coverage(self, state: PipelineState) -> dict:
        """Run coverage judge."""
        return await self._run_judge(state, self._coverage_judge, "coverage")

    async def _node_judge_quality(self, state: PipelineState) -> dict:
        """Run quality judge."""
        return await self._run_judge(state, self._quality_judge, "quality")

    async def _node_judge_adversarial(self, state: PipelineState) -> dict:
        """Run adversarial judge."""
        return await self._run_judge(
            state, self._adversarial_judge, "adversarial"
        )

    async def _node_build_report(self, state: PipelineState) -> dict:
        """Build final report from state."""
        evaluations = state.get("evaluations", [])
        all_passed = all(
            e.get("passed", False) for e in evaluations
            if e.get("judge_name") in ("coverage", "quality", "adversarial")
        )
        # Check if we have at least one evaluation from each judge
        judge_names = {e.get("judge_name") for e in evaluations}
        complete = {"coverage", "quality", "adversarial"}.issubset(judge_names)
        passed = all_passed and complete

        return {"passed": passed}

    # ------------------------------------------------------------------
    # LangGraph routing
    # ------------------------------------------------------------------

    def _route_after_coverage(self, state: PipelineState) -> str:
        """Route after coverage judge."""
        return self._route_after_judge(
            state, "coverage", "coverage_retries",
            self._config.coverage_max_retries,
        )

    def _route_after_quality(self, state: PipelineState) -> str:
        """Route after quality judge."""
        return self._route_after_judge(
            state, "quality", "quality_retries",
            self._config.quality_max_retries,
        )

    def _route_after_adversarial(self, state: PipelineState) -> str:
        """Route after adversarial judge."""
        return self._route_after_judge(
            state, "adversarial", "adversarial_retries",
            self._config.adversarial_max_retries,
        )

    def _route_after_judge(
        self,
        state: PipelineState,
        judge_name: str,
        retry_key: str,
        max_retries: int,
    ) -> str:
        """Common routing logic after any judge.

        Returns "retry", "next", or "stop".
        """
        # Budget guard
        if state.get("total_iterations", 0) >= self._config.total_max_iterations:
            return "stop"

        # Find latest evaluation for this judge
        evaluations = state.get("evaluations", [])
        latest = None
        for e in reversed(evaluations):
            if e.get("judge_name") == judge_name:
                latest = e
                break

        if latest is None:
            return "stop"

        if latest.get("passed", False):
            return "next"

        retries = state.get(retry_key, 0)  # type: ignore[arg-type]
        if retries < max_retries:
            return "retry"

        return "stop"

    # ------------------------------------------------------------------
    # Sequential fallback path
    # ------------------------------------------------------------------

    async def _run_sequential(
        self, request: TestGenerationRequest
    ) -> FinalReport:
        """Fallback pipeline without LangGraph — sequential loop."""
        evaluations: list[JudgeEvaluation] = []
        test_code = ""
        test_count = 0
        total_iterations = 0
        imports: list[str] = []

        judges: list[tuple[BaseJudge, str, int]] = [
            (self._coverage_judge, "coverage", self._config.coverage_max_retries),
            (self._quality_judge, "quality", self._config.quality_max_retries),
            (self._adversarial_judge, "adversarial", self._config.adversarial_max_retries),
        ]

        # Initial generation
        result = await self._generator.generate(request)
        test_code = result.test_code
        test_count = result.test_count
        imports = list(result.imports)
        total_iterations += 1

        all_passed = True

        for judge, judge_name, max_retries in judges:
            retries = 0
            judge_passed = False

            while retries <= max_retries:
                if total_iterations >= self._config.total_max_iterations:
                    logger.warning(
                        "budget_exhausted",
                        total_iterations=total_iterations,
                    )
                    all_passed = False
                    break

                verdict = await judge.evaluate(
                    request.source_code, test_code
                )
                evaluation = JudgeEvaluation(
                    judge_name=judge_name,
                    verdict=verdict,
                    iteration=total_iterations,
                )
                evaluations.append(evaluation)

                if verdict.passed:
                    judge_passed = True
                    break

                retries += 1
                if retries <= max_retries and total_iterations < self._config.total_max_iterations:
                    # Improve tests with feedback
                    improved = await self._generator.improve(
                        request,
                        test_code,
                        verdict.issues,
                        verdict.suggestions,
                    )
                    test_code = improved.test_code
                    test_count = improved.test_count
                    imports = list(improved.imports)
                    total_iterations += 1

            if not judge_passed:
                all_passed = False
                break  # Stop pipeline on judge failure after retries

        return FinalReport(
            test_code=test_code,
            test_count=test_count,
            evaluations=evaluations,
            iterations=total_iterations,
            passed=all_passed,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _run_judge(
        self, state: PipelineState, judge: BaseJudge, judge_name: str
    ) -> dict:
        """Run a judge and append the evaluation to state."""
        source_code = state.get("source_code", "")
        test_code = state.get("test_code", "")
        iteration = state.get("iteration", 0)

        verdict = await judge.evaluate(source_code, test_code)

        evaluation = {
            "judge_name": judge_name,
            "passed": verdict.passed,
            "score": verdict.score,
            "issues": list(verdict.issues),
            "suggestions": list(verdict.suggestions),
            "iteration": iteration,
        }

        existing = list(state.get("evaluations", []))
        existing.append(evaluation)

        retry_key = f"{judge_name}_retries"
        retries = state.get(retry_key, 0)  # type: ignore[arg-type]
        if not verdict.passed:
            retries += 1

        return {
            "evaluations": existing,
            "current_judge": judge_name,
            retry_key: retries,
        }

    def _aggregate_feedback(
        self, state: PipelineState
    ) -> tuple[list[str], list[str]]:
        """Aggregate issues and suggestions from the latest failed evaluations."""
        issues: list[str] = []
        suggestions: list[str] = []

        for e in state.get("evaluations", []):
            if not e.get("passed", True):
                issues.extend(e.get("issues", []))
                suggestions.extend(e.get("suggestions", []))

        return issues, suggestions

    def _state_to_request(self, state: PipelineState) -> TestGenerationRequest:
        """Convert pipeline state back to a TestGenerationRequest."""
        return TestGenerationRequest(
            source_code=state.get("source_code", ""),
            source_path=state.get("source_path", ""),
            language=state.get("language", "python"),
            framework=state.get("framework", "pytest"),
            context=state.get("context", ""),
        )

    def _state_to_report(self, state: PipelineState) -> FinalReport:
        """Convert final pipeline state to a FinalReport."""
        evaluations: list[JudgeEvaluation] = []
        for e in state.get("evaluations", []):
            evaluations.append(
                JudgeEvaluation(
                    judge_name=e.get("judge_name", ""),
                    verdict=JudgeVerdict(
                        passed=e.get("passed", False),
                        score=e.get("score", 0.0),
                        issues=e.get("issues", []),
                        suggestions=e.get("suggestions", []),
                    ),
                    iteration=e.get("iteration", 0),
                )
            )

        return FinalReport(
            test_code=state.get("test_code", ""),
            test_count=state.get("test_count", 0),
            evaluations=evaluations,
            iterations=state.get("total_iterations", 0),
            passed=state.get("passed", False),
        )
