"""L6 Semantic Quality — LLM-based relevance scoring."""
from __future__ import annotations

import json
import os
from typing import Any

import logging

from marketplace.services.judge.base import JudgeContext, JudgeLevel, LevelVerdict

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a judge evaluating whether an AI agent's output semantically answers "
    "the given input query. Rate the relevance on a scale from 0.0 to 1.0, where "
    "1.0 means perfectly relevant and 0.0 means completely irrelevant or off-topic. "
    "Respond ONLY with a JSON object in the format: "
    '{"relevance": <float 0-1>, "reasoning": "<brief explanation>"}'
)

_REQUEST_TIMEOUT = 30.0


def _build_user_message(input_data: dict[str, Any], output_data: dict[str, Any]) -> str:
    """Build the user-facing prompt for the LLM.

    Args:
        input_data: Input dict.
        output_data: Output dict.

    Returns:
        Formatted prompt string.
    """
    query = input_data.get("query", json.dumps(input_data, default=str))
    result = output_data.get("result", json.dumps(output_data, default=str))
    return (
        f"INPUT QUERY:\n{query}\n\n"
        f"AGENT OUTPUT:\n{result}\n\n"
        "Rate the semantic relevance of the output to the input query."
    )


async def _call_openai(prompt: str) -> dict[str, Any]:
    """Call the OpenAI chat completion API.

    Args:
        prompt: User message to send.

    Returns:
        Parsed JSON response dict.

    Raises:
        RuntimeError: On API error or unparseable response.
    """
    import openai  # imported lazily so the module loads without openai installed

    client = openai.AsyncOpenAI(timeout=_REQUEST_TIMEOUT)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=200,
    )
    content = response.choices[0].message.content or "{}"
    # Strip markdown code fences if present.
    content = content.strip()
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:-1])
    return json.loads(content)


class L6Semantic(JudgeLevel):
    """Level 6: Semantic Quality.

    Uses an LLM (GPT-4o-mini) to assess whether the output semantically
    answers the input query.  Gracefully returns a ``skip`` verdict when
    ``OPENAI_API_KEY`` is not set or the LLM call fails.
    """

    @property
    def level(self) -> int:
        return 6

    @property
    def name(self) -> str:
        return "semantic_quality"

    async def evaluate(self, ctx: JudgeContext) -> LevelVerdict:
        """Rate semantic relevance of output to input using an LLM.

        Args:
            ctx: Pipeline context.

        Returns:
            LevelVerdict based on LLM-rated relevance, or skip if unavailable.
        """
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return LevelVerdict(
                verdict="skip",
                score=0.0,
                confidence=0.0,
                details={"reason": "OPENAI_API_KEY not set"},
            )

        prompt = _build_user_message(ctx.input_data, ctx.output_data)
        try:
            parsed = await _call_openai(prompt)
        except Exception as exc:
            logger.warning("L6 semantic LLM call failed: %s", exc)
            return LevelVerdict(
                verdict="skip",
                score=0.0,
                confidence=0.0,
                details={"reason": "LLM call failed", "error": str(exc)},
            )

        relevance = float(parsed.get("relevance", 0.5))
        relevance = max(0.0, min(1.0, relevance))
        reasoning = str(parsed.get("reasoning", ""))

        if relevance >= 0.7:
            verdict = "pass"
        elif relevance >= 0.4:
            verdict = "warn"
        else:
            verdict = "fail"

        return LevelVerdict(
            verdict=verdict,
            score=round(relevance, 4),
            confidence=0.75,
            details={"relevance": relevance, "reasoning": reasoning},
        )
