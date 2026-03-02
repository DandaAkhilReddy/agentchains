"""Sentiment Analyzer A2A Agent — keyword-based sentiment analysis via A2A protocol.

Runs on port 9002 and exposes an ``analyze-sentiment`` skill. Accepts one or
more text strings and returns a sentiment label (positive, negative, neutral),
a numeric score in [-1, 1], and a confidence value for each input.
"""

from __future__ import annotations

from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "analyze-sentiment",
        "name": "Analyze Sentiment",
        "description": (
            "Analyze sentiment of one or more text strings. Returns a label "
            "(positive/negative/neutral), numeric score [-1, 1], and confidence."
        ),
        "tags": ["nlp", "sentiment", "text-analysis"],
        "examples": [
            '{"texts": ["This product is amazing!", "Terrible experience."]}',
            '{"text": "The results were outstanding and exceeded all expectations."}',
        ],
    }
]

_POSITIVE_WORDS: frozenset[str] = frozenset({
    "great", "good", "excellent", "amazing", "wonderful", "fantastic",
    "love", "best", "happy", "positive", "successful", "awesome",
    "brilliant", "outstanding", "perfect",
})

_NEGATIVE_WORDS: frozenset[str] = frozenset({
    "bad", "terrible", "awful", "horrible", "worst", "hate", "poor",
    "fail", "sad", "negative", "disaster", "ugly", "boring", "broken",
    "useless",
})


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens, stripping punctuation.

    Args:
        text: Raw input text.

    Returns:
        List of lowercase word strings with no leading/trailing punctuation.
    """
    return [
        word.strip(".,!?;:\"'()[]{}").lower()
        for word in text.split()
        if word.strip(".,!?;:\"'()[]{}").isalpha()
    ]


def _analyze_single(text: str) -> dict[str, Any]:
    """Compute sentiment for a single text string.

    Sentiment is derived from keyword matching against curated positive and
    negative word lists. Score is clamped to [-1, 1].

    Args:
        text: The input text to analyse.

    Returns:
        Dict with ``text``, ``sentiment``, ``score``, and ``confidence`` keys.
    """
    tokens = _tokenize(text)
    total_words = len(tokens)

    if total_words == 0:
        return {
            "text": text,
            "sentiment": "neutral",
            "score": 0.0,
            "confidence": 0.0,
        }

    positive_count = sum(1 for t in tokens if t in _POSITIVE_WORDS)
    negative_count = sum(1 for t in tokens if t in _NEGATIVE_WORDS)

    raw_score = (positive_count - negative_count) / total_words
    score = max(-1.0, min(1.0, raw_score))

    confidence = min(0.95, (positive_count + negative_count) / max(total_words, 1))

    if score > 0.0:
        sentiment = "positive"
    elif score < 0.0:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return {
        "text": text,
        "sentiment": sentiment,
        "score": round(score, 4),
        "confidence": round(confidence, 4),
    }


class SentimentAnalyzerA2AAgent(BaseA2AAgent):
    """A2A agent that performs keyword-based sentiment analysis.

    Accepts a list of texts (``texts`` key) or a single text (``text`` key)
    and returns a sentiment result for each one.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Sentiment Analyzer Agent",
            description=(
                "Keyword-based sentiment analysis for one or more text inputs. "
                "Returns positive/negative/neutral labels with numeric scores and "
                "confidence values. Designed for pipeline integration."
            ),
            port=9002,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming sentiment analysis request.

        Args:
            skill_id: Must be ``analyze-sentiment``.
            input_data: Dict with ``texts`` (list of str) or ``text`` (single str).

        Returns:
            Dict with a ``results`` list, each item containing ``text``,
            ``sentiment``, ``score``, and ``confidence``.
        """
        texts: list[str]

        raw_texts = input_data.get("texts")
        if isinstance(raw_texts, list):
            texts = [str(t) for t in raw_texts]
        else:
            single = input_data.get("text", "")
            texts = [str(single)] if single else []

        if not texts:
            return {"results": []}

        results = [_analyze_single(t) for t in texts]
        return {"results": results}


agent = SentimentAnalyzerA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9002)
