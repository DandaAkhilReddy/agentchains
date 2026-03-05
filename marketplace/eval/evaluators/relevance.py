"""Relevance evaluator — LLM-as-judge for output relevance scoring."""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from marketplace.eval.base import BaseEvaluator
from marketplace.eval.types import EvalResult, EvalVerdict
from marketplace.model_layer.router import ModelRouter
from marketplace.model_layer.types import CompletionRequest

logger = structlog.get_logger(__name__)

_JUDGE_PROMPT = """You are an evaluation judge. Score the relevance of the output to the input.

INPUT:
{input_text}

OUTPUT:
{output_text}

Rate the relevance on a scale of 0-10 where:
- 0: Completely irrelevant
- 5: Partially relevant
- 10: Perfectly relevant and comprehensive

Respond with ONLY a JSON object:
{{"score": <0-10>, "reasoning": "<brief explanation>"}}"""


class RelevanceEvaluator(BaseEvaluator):
    """LLM-as-judge evaluator that scores output relevance 0-10."""

    name = "relevance"

    def __init__(self, model_router: ModelRouter) -> None:
        self._router = model_router

    async def evaluate(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        expected: dict[str, Any] | None = None,
    ) -> EvalResult:
        input_text = json.dumps(input_data, default=str)[:2000]
        output_text = json.dumps(output_data, default=str)[:2000]

        prompt = _JUDGE_PROMPT.format(input_text=input_text, output_text=output_text)

        start = time.perf_counter()
        try:
            response = await self._router.complete(CompletionRequest(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=256,
            ))
            duration_ms = (time.perf_counter() - start) * 1000

            # Parse judge response
            content = response.content.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content)
            score = float(result.get("score", 0)) / 10.0  # Normalize to 0-1
            reasoning = result.get("reasoning", "")

            if score >= 0.7:
                verdict = EvalVerdict.PASS
            elif score >= 0.4:
                verdict = EvalVerdict.WARN
            else:
                verdict = EvalVerdict.FAIL

            return EvalResult(
                eval_name=self.name,
                verdict=verdict,
                score=score,
                details={"reasoning": reasoning, "raw_score": result.get("score", 0)},
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error("relevance_eval_failed", error=str(exc))
            return EvalResult(
                eval_name=self.name,
                verdict=EvalVerdict.SKIP,
                score=0.0,
                details={"error": str(exc)},
                duration_ms=duration_ms,
            )
