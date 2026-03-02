"""Tag Generator A2A Agent — TF-IDF-inspired keyword and bigram extraction via A2A protocol.

Runs on port 9015 and exposes a ``generate-tags`` skill. Tokenizes input text,
removes stop words, scores remaining terms by frequency weighted by word length,
and also detects two-word phrases (bigrams) that appear at least twice. Returns
the top N tags sorted by score.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "generate-tags",
        "name": "Generate Tags",
        "description": (
            "TF-IDF-inspired keyword extraction from text. Returns scored tags "
            "including unigrams and repeated bigrams. Useful for content tagging, "
            "search indexing, and topic classification."
        ),
        "tags": ["nlp", "tagging", "keywords", "tfidf", "text-analysis"],
        "examples": [
            '{"text": "Machine learning models require large datasets and GPU compute."}',
            '{"text": "Python is great for data science", "max_tags": 5}',
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

_DEFAULT_MAX_TAGS: int = 10


def _tokenize(text: str) -> list[str]:
    """Extract lowercase alphabetic word tokens from text.

    Args:
        text: Raw input text.

    Returns:
        List of lowercase word strings (alphabetic only, no punctuation).
    """
    return [w.lower() for w in re.findall(r"\b[a-zA-Z]+\b", text)]


def _content_tokens(tokens: list[str]) -> list[str]:
    """Filter stop words and single-character tokens from a token list.

    Args:
        tokens: Lowercase word tokens.

    Returns:
        Tokens that are not in the stop-word list and have length > 1.
    """
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _score_word(word: str, frequency: int) -> float:
    """Compute a TF-IDF-inspired score for a single word.

    Shorter words that appear frequently score lower than longer, specific
    words at the same frequency. The length bonus uses ``log(1 + 1/len(word))``
    which decreases as word length increases (favouring medium-length terms).

    Args:
        word: The candidate tag word.
        frequency: How many times the word appears in the document.

    Returns:
        Non-negative float score.
    """
    return frequency * math.log(1.0 + 1.0 / len(word))


def _extract_bigrams(tokens: list[str]) -> list[tuple[str, str]]:
    """Produce consecutive token pairs (bigrams) from a token list.

    Args:
        tokens: Ordered list of content tokens.

    Returns:
        List of (word1, word2) tuples for each adjacent pair.
    """
    return [(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)]


def _generate_tags(text: str, max_tags: int) -> dict[str, Any]:
    """Extract scored keyword tags from text using frequency and length heuristics.

    Unigrams are scored by frequency * log(1 + 1/len). Bigrams that appear
    at least twice are included with their combined score. Tags are sorted by
    score descending and the top ``max_tags`` entries are returned.

    Args:
        text: The source text to extract tags from.
        max_tags: Maximum number of tags to return.

    Returns:
        Dict with ``tags`` (list of ``{tag, score, frequency}`` dicts),
        ``total_unique_words``, and ``text_length``.
    """
    all_tokens = _tokenize(text)
    content = _content_tokens(all_tokens)

    if not content:
        return {
            "tags": [],
            "total_unique_words": 0,
            "text_length": len(all_tokens),
        }

    word_freq: Counter[str] = Counter(content)
    total_unique = len(word_freq)

    # Score unigrams
    tag_scores: dict[str, tuple[float, int]] = {}  # tag → (score, freq)
    for word, freq in word_freq.items():
        tag_scores[word] = (_score_word(word, freq), freq)

    # Score bigrams — only include those occurring 2+ times
    bigrams = _extract_bigrams(content)
    bigram_freq: Counter[tuple[str, str]] = Counter(bigrams)
    for (w1, w2), freq in bigram_freq.items():
        if freq >= 2:
            phrase = f"{w1} {w2}"
            # Bigram score: sum of individual word scores for the combined frequency
            phrase_score = _score_word(w1, freq) + _score_word(w2, freq)
            tag_scores[phrase] = (phrase_score, freq)

    # Sort by score descending, then alphabetically for determinism
    sorted_tags = sorted(
        tag_scores.items(),
        key=lambda item: (-item[1][0], item[0]),
    )

    top_tags = [
        {"tag": tag, "score": round(score, 6), "frequency": freq}
        for tag, (score, freq) in sorted_tags[:max_tags]
    ]

    return {
        "tags": top_tags,
        "total_unique_words": total_unique,
        "text_length": len(all_tokens),
    }


class TagGeneratorA2AAgent(BaseA2AAgent):
    """A2A agent that generates keyword tags from text using TF-IDF-inspired scoring.

    Accepts a ``text`` field via the ``generate-tags`` skill and returns a ranked
    list of tags. Both single-word terms and two-word phrases (bigrams appearing
    2+ times) are considered. An optional ``max_tags`` parameter controls the
    maximum number of results returned (default 10).
    """

    def __init__(self) -> None:
        super().__init__(
            name="Tag Generator Agent",
            description=(
                "TF-IDF-inspired keyword and bigram extraction from text. "
                "Scores candidate tags by frequency weighted by inverse word length, "
                "and includes repeated two-word phrases. Returns top N scored tags."
            ),
            port=9015,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming tag generation request.

        Args:
            skill_id: Must be ``generate-tags``.
            input_data: Dict with ``text`` (str) and optional ``max_tags`` (int,
                default 10).

        Returns:
            Dict with ``tags`` (list of ``{tag, score, frequency}`` dicts),
            ``total_unique_words``, and ``text_length``.
        """
        text: str = str(input_data.get("text", ""))
        if not text:
            return {
                "tags": [],
                "total_unique_words": 0,
                "text_length": 0,
            }

        max_tags: int = int(input_data.get("max_tags", _DEFAULT_MAX_TAGS))
        max_tags = max(1, max_tags)
        return _generate_tags(text, max_tags)


agent = TagGeneratorA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9015)
