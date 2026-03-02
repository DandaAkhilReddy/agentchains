"""Document Summarizer A2A Agent — extractive summarization via the A2A protocol.

Runs on port 9003 and exposes a ``summarize`` skill. Uses a frequency-based
extractive algorithm: sentences are scored by how often their words appear in
the document, and the top-N highest-scoring sentences form the summary.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "summarize",
        "name": "Summarize Document",
        "description": (
            "Extractive summarization of a text document. Returns a summary, "
            "key points, and length metadata."
        ),
        "tags": ["nlp", "summarization", "text-analysis", "extraction"],
        "examples": [
            '{"text": "Long document text here...", "max_sentences": 3}',
            '{"text": "Article body..."}',
        ],
    }
]

_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "over", "out",
    "up", "down", "off", "about", "not", "no", "nor", "or", "and", "but",
    "if", "then", "than", "too", "very", "just", "only", "also", "that",
    "this", "these", "those", "it", "its", "i", "me", "my", "we", "our",
    "you", "your", "he", "she", "they", "their", "them", "him", "her",
    "what", "which", "who", "when", "where", "how", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "many",
})


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation boundaries.

    Args:
        text: Raw document text.

    Returns:
        List of non-empty sentence strings with surrounding whitespace stripped.
    """
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if s.strip()]


def _word_tokens(text: str) -> list[str]:
    """Extract lowercase alphabetic word tokens from text.

    Args:
        text: Raw text.

    Returns:
        List of lowercase word strings.
    """
    return [w.lower() for w in re.findall(r"\b[a-zA-Z]+\b", text)]


def _content_words(tokens: list[str]) -> list[str]:
    """Filter stop words from a token list.

    Args:
        tokens: Lowercase word tokens.

    Returns:
        Tokens that are not in the stop-word list.
    """
    return [t for t in tokens if t not in _STOP_WORDS]


def _score_sentences(
    sentences: list[str], word_freq: Counter[str]
) -> list[tuple[float, int, str]]:
    """Assign a frequency-based score to each sentence.

    Score is the sum of each content word's document frequency, normalised
    by the number of content words in the sentence to avoid bias toward long
    sentences.

    Args:
        sentences: List of sentence strings.
        word_freq: Counter of content-word frequencies across the document.

    Returns:
        List of (score, original_index, sentence) tuples.
    """
    scored: list[tuple[float, int, str]] = []
    for idx, sentence in enumerate(sentences):
        tokens = _content_words(_word_tokens(sentence))
        if not tokens:
            scored.append((0.0, idx, sentence))
            continue
        score = sum(word_freq[t] for t in tokens) / len(tokens)
        scored.append((score, idx, sentence))
    return scored


def _extract_summary(text: str, max_sentences: int) -> dict[str, Any]:
    """Produce an extractive summary of a document.

    Args:
        text: Full document text.
        max_sentences: Maximum number of sentences to include in the summary.

    Returns:
        Dict with ``summary``, ``key_points``, ``original_length``, and
        ``summary_length`` keys.
    """
    sentences = _split_sentences(text)
    all_tokens = _word_tokens(text)
    content_tokens = _content_words(all_tokens)

    word_freq: Counter[str] = Counter(content_tokens)

    original_length = len(all_tokens)

    if not sentences:
        return {
            "summary": "",
            "key_points": [],
            "original_length": original_length,
            "summary_length": 0,
        }

    # Score and pick top sentences, then restore original order
    scored = _score_sentences(sentences, word_freq)
    n = max(1, min(max_sentences, len(sentences)))
    top = sorted(scored, key=lambda x: x[0], reverse=True)[:n]
    top_in_order = sorted(top, key=lambda x: x[1])
    summary = " ".join(s for _, _, s in top_in_order)

    # Key points: top-5 most frequent content words
    key_points = [word for word, _ in word_freq.most_common(5)]

    summary_length = len(_word_tokens(summary))

    return {
        "summary": summary,
        "key_points": key_points,
        "original_length": original_length,
        "summary_length": summary_length,
    }


class DocSummarizerA2AAgent(BaseA2AAgent):
    """A2A agent that performs extractive document summarization.

    Accepts a text document via the ``summarize`` skill and returns an
    extractive summary, key points, and length statistics.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Document Summarizer Agent",
            description=(
                "Extractive summarization of text documents using word-frequency "
                "scoring. Returns a summary, key points, and length metadata. "
                "Designed for pipeline integration before report generation."
            ),
            port=9003,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming summarization request.

        Args:
            skill_id: Must be ``summarize``.
            input_data: Dict with ``text`` (str) and optional ``max_sentences`` (int).

        Returns:
            Dict with ``summary``, ``key_points``, ``original_length``, and
            ``summary_length``.
        """
        text: str = input_data.get("text", "")
        if not text:
            return {
                "summary": "",
                "key_points": [],
                "original_length": 0,
                "summary_length": 0,
            }

        max_sentences: int = int(input_data.get("max_sentences", 3))
        return _extract_summary(text, max_sentences)


agent = DocSummarizerA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9003)
