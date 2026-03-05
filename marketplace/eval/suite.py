"""Eval Suite — runs multiple evaluators across test cases."""

from __future__ import annotations

from typing import Any

import structlog

from marketplace.eval.base import BaseEvaluator
from marketplace.eval.types import EvalResult, EvalSuiteResult, EvalVerdict

logger = structlog.get_logger(__name__)


class EvalSuite:
    """Runs a set of evaluators across test cases and aggregates results."""

    def __init__(self, name: str, evaluators: list[BaseEvaluator]) -> None:
        self.name = name
        self._evaluators = evaluators

    async def run(
        self,
        test_cases: list[dict[str, Any]],
    ) -> EvalSuiteResult:
        """Run all evaluators across all test cases.

        Each test case should have:
        - input: dict
        - output: dict
        - expected: dict (optional)
        """
        all_results: list[EvalResult] = []

        for case_idx, case in enumerate(test_cases):
            input_data = case.get("input", {})
            output_data = case.get("output", {})
            expected = case.get("expected")

            for evaluator in self._evaluators:
                try:
                    result = await evaluator.evaluate(input_data, output_data, expected)
                    all_results.append(result)
                except Exception as exc:
                    logger.error(
                        "evaluator_failed",
                        evaluator=evaluator.name,
                        case_index=case_idx,
                        error=str(exc),
                    )
                    all_results.append(EvalResult(
                        eval_name=evaluator.name,
                        verdict=EvalVerdict.SKIP,
                        details={"error": str(exc), "case_index": case_idx},
                    ))

        suite_result = EvalSuiteResult(
            suite_name=self.name,
            results=all_results,
        )
        suite_result.compute_overall()

        logger.info(
            "eval_suite_completed",
            suite=self.name,
            total_evals=len(all_results),
            overall_verdict=suite_result.overall_verdict.value,
            overall_score=round(suite_result.overall_score, 3),
        )

        return suite_result

    async def run_on_workflow_output(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        expected: dict[str, Any] | None = None,
    ) -> EvalSuiteResult:
        """Run evaluators on a single workflow's input/output."""
        return await self.run([{
            "input": input_data,
            "output": output_data,
            "expected": expected,
        }])
