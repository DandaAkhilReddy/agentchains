"""L8 Consensus — LLM-based agreement check across alternative outputs."""
from __future__ import annotations

import json
import os
from typing import Any

import logging

from marketplace.services.judge.base import JudgeContext, JudgeLevel, LevelVerdict

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a consensus judge comparing a primary AI agent output against alternative "
    "outputs produced for the same input. Assess the level of agreement between them. "
    "Respond ONLY with a JSON object: "
    '{"agreement_score": <float 0-1>, "consensus_verdict": "pass"|"warn"|"fail", '
    '"reasoning": "<brief explanation>"} '
    "where 1.0 means all outputs agree and 0.0 means they completely contradict each other."
)

_REQUEST_TIMEOUT = 30.0


def _build_user_message(
    primary: dict[str, Any],
    alternatives: list[Any],
) -> str:
    """Build the consensus evaluation prompt.

    Args:
        primary: The primary output_data dict.
        alternatives: List of alternative output dicts.

    Returns:
        Formatted prompt string.
    """
    primary_text = primary.get("result", json.dumps(primary, default=str))
    alt_texts = "\n".join(
        f"Alternative {i + 1}: {alt.get('result', json.dumps(alt, default=str)) if isinstance(alt, dict) else str(alt)}"
        for i, alt in enumerate(alternatives[:5])  # cap at 5 alternatives
    )
    return (
        f"PRIMARY OUTPUT:\n{primary_text}\n\n"
        f"ALTERNATIVE OUTPUTS:\n{alt_texts}\n\n"
        "Assess the level of consensus across these outputs."
    )


async def _call_openai(prompt: str) -> dict[str, Any]:
    """Call the OpenAI chat completion API for consensus evaluation.

    Args:
        prompt: User message to send.

    Returns:
        Parsed JSON response dict.

    Raises:
        RuntimeError: On API error or unparseable response.
    """
    import openai

    client = openai.AsyncOpenAI(timeout=_REQUEST_TIMEOUT)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=300,
    )
    content = response.choices[0].message.content or "{}"
    content = content.strip()
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:-1])
    return json.loads(content)


class L8Consensus(JudgeLevel):
    """Level 8: Consensus.

    Compares ``output_data`` against ``metadata["alternative_outputs"]`` using
    an LLM.  Skipped when no alternatives exist or when ``OPENAI_API_KEY`` is
    not set.  Skipped gracefully on LLM failure.
    """

    @property
    def level(self) -> int:
        return 8

    @property
    def name(self) -> str:
        return "consensus"

    async def evaluate(self, ctx: JudgeContext) -> LevelVerdict:
        """Assess agreement between primary output and alternatives.

        Args:
            ctx: Pipeline context; reads ``metadata["alternative_outputs"]``.

        Returns:
            LevelVerdict — skip if no alternatives or OPENAI_API_KEY unset.
        """
        alternatives: list[Any] = ctx.metadata.get("alternative_outputs", [])

        if not alternatives:
            return LevelVerdict(
                verdict="skip",
                score=1.0,
                confidence=1.0,
                details={"reason": "no alternative outputs provided"},
            )

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return LevelVerdict(
                verdict="skip",
                score=0.0,
                confidence=0.0,
                details={"reason": "OPENAI_API_KEY not set"},
            )

        prompt = _build_user_message(ctx.output_data, alternatives)
        try:
            parsed = await _call_openai(prompt)
        except Exception as exc:
            logger.warning("L8 consensus LLM call failed: %s", exc)
            return LevelVerdict(
                verdict="skip",
                score=0.0,
                confidence=0.0,
                details={"reason": "LLM call failed", "error": str(exc)},
            )

        agreement_score = float(parsed.get("agreement_score", 0.5))
        agreement_score = max(0.0, min(1.0, agreement_score))

        raw_verdict = str(parsed.get("consensus_verdict", "warn"))
        if raw_verdict not in {"pass", "warn", "fail"}:
            raw_verdict = "warn"

        reasoning = str(parsed.get("reasoning", ""))

        return LevelVerdict(
            verdict=raw_verdict,
            score=round(agreement_score, 4),
            confidence=0.70,
            details={
                "agreement_score": agreement_score,
                "alternatives_compared": len(alternatives),
                "reasoning": reasoning,
            },
        )
