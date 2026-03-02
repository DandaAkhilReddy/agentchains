"""Headline Generator A2A Agent — extractive headline generation via the A2A protocol.

Runs on port 9016 and exposes a ``generate-headline`` skill. Produces concise
headlines from text without using an LLM: extracts the first sentence, identifies
key entities (capitalized words) and topic terms, scores candidate headlines, and
adapts phrasing to the requested style (news, academic, or casual).
"""

from __future__ import annotations

import re
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "generate-headline",
        "name": "Generate Headline",
        "description": (
            "Extractive headline generation from text without an LLM. Scores "
            "candidate headlines using first-sentence extraction and key entity "
            "detection. Supports news, academic, and casual style options."
        ),
        "tags": ["nlp", "headline", "summarization", "extraction", "content"],
        "examples": [
            '{"text": "Scientists at MIT have discovered a new material that can store energy..."}',
            '{"text": "The market fell sharply...", "style": "news", "max_length": 60}',
        ],
    }
]

_DEFAULT_MAX_LENGTH: int = 80

_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "it", "its", "i", "me", "my", "we", "our",
    "you", "your", "he", "she", "they", "their", "them", "him", "her",
    "that", "this", "these", "those", "and", "but", "or", "nor", "not",
})

_STYLE_PREFIXES: dict[str, str] = {
    "news": "",
    "academic": "Study Finds: ",
    "casual": "Here's the thing — ",
}


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences at punctuation boundaries.

    Args:
        text: Raw input text.

    Returns:
        List of non-empty, stripped sentence strings.
    """
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if s.strip()]


def _extract_entities(text: str) -> list[str]:
    """Find capitalized words that are likely proper nouns or named entities.

    Skips the very first word of the text (which is capitalized by convention)
    unless it appears capitalised elsewhere too.

    Args:
        text: The full source text.

    Returns:
        Deduplicated list of capitalised word strings, preserving first-seen order.
    """
    # Words that start with uppercase but are not at the start of a sentence
    # — use a negative lookbehind on sentence starters
    tokens = re.findall(r"(?<![.!?]\s)(?<![.!?\n])\b[A-Z][a-z]{1,}\b", text)
    seen: dict[str, None] = {}
    for t in tokens:
        if t.lower() not in _STOP_WORDS:
            seen[t] = None
    return list(seen.keys())


def _extract_topic_words(text: str, max_words: int = 5) -> list[str]:
    """Extract the most frequent non-stop-word tokens from text.

    Args:
        text: Raw source text.
        max_words: How many topic words to return.

    Returns:
        Up to ``max_words`` lowercase word strings ordered by frequency descending.
    """
    tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", text)]
    filtered = [t for t in tokens if t not in _STOP_WORDS]

    freq: dict[str, int] = {}
    for t in filtered:
        freq[t] = freq.get(t, 0) + 1

    sorted_words = sorted(freq.keys(), key=lambda w: -freq[w])
    return sorted_words[:max_words]


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to at most max_length characters, breaking at a word boundary.

    Args:
        text: Source string.
        max_length: Maximum allowed character count.

    Returns:
        String of at most ``max_length`` characters. If truncated, ends with ``...``.
    """
    if len(text) <= max_length:
        return text
    truncated = text[: max_length - 3].rsplit(" ", 1)[0]
    return truncated + "..."


def _apply_style(text: str, style: str) -> str:
    """Apply a style-specific prefix to a candidate headline.

    Args:
        text: Raw headline candidate.
        style: One of ``news``, ``academic``, or ``casual``.

    Returns:
        Styled headline string.
    """
    prefix = _STYLE_PREFIXES.get(style, "")
    return f"{prefix}{text}"


def _score_candidate(candidate: str, topic_words: list[str], entities: list[str]) -> float:
    """Score a headline candidate based on entity and topic coverage.

    Args:
        candidate: Candidate headline string.
        topic_words: Extracted topic words from the source text.
        entities: Named entities extracted from the source text.

    Returns:
        Non-negative float score. Higher is better.
    """
    lower = candidate.lower()
    score = 0.0
    for word in topic_words:
        if word in lower:
            score += 2.0
    for entity in entities:
        if entity in candidate:
            score += 3.0
    # Slight penalty for very short or very long candidates
    length = len(candidate)
    if 20 <= length <= 80:
        score += 1.0
    return score


def _generate_headline(text: str, style: str, max_length: int) -> dict[str, Any]:
    """Produce a headline and alternatives from source text.

    Candidate headlines are: the first sentence (truncated), a key-phrase
    combination using entities and topic words, and a topic-word summary.
    Candidates are scored and the highest-scoring one becomes the primary headline.

    Args:
        text: Full source text.
        style: Headline style — ``news``, ``academic``, or ``casual``.
        max_length: Maximum character count for the primary headline.

    Returns:
        Dict with ``headline``, ``style``, ``alternatives`` (list of str),
        ``source_length``, and ``key_terms`` (list of str).
    """
    sentences = _split_sentences(text)
    entities = _extract_entities(text)
    topic_words = _extract_topic_words(text)

    key_terms: list[str] = list(dict.fromkeys(entities[:3] + topic_words[:4]))

    # Build candidates
    candidates: list[str] = []

    # 1. First sentence
    if sentences:
        first = sentences[0]
        if len(first) > 10:
            candidates.append(first)

    # 2. Entity + topic phrase
    if entities and topic_words:
        phrase_parts: list[str] = entities[:2] + topic_words[:2]
        phrase = " ".join(phrase_parts).title()
        if phrase and phrase not in candidates:
            candidates.append(phrase)

    # 3. Topic-word summary
    if topic_words:
        summary = " ".join(w.title() for w in topic_words[:4])
        if summary not in candidates:
            candidates.append(summary)

    # 4. Fallback
    if not candidates:
        candidates.append(text[:max_length].strip())

    # Score candidates and pick the best
    scored = [
        (cand, _score_candidate(cand, topic_words, entities))
        for cand in candidates
    ]
    scored.sort(key=lambda x: -x[1])

    best_raw = scored[0][0]
    styled = _apply_style(best_raw, style)
    headline = _truncate(styled, max_length)

    # Alternatives: remaining candidates styled and truncated
    alternatives: list[str] = []
    for cand, _ in scored[1:]:
        alt = _truncate(_apply_style(cand, style), max_length)
        if alt != headline and alt not in alternatives:
            alternatives.append(alt)

    return {
        "headline": headline,
        "style": style,
        "alternatives": alternatives,
        "source_length": len(text),
        "key_terms": key_terms,
    }


class HeadlineGeneratorA2AAgent(BaseA2AAgent):
    """A2A agent that generates extractive headlines from text without an LLM.

    Accepts a ``text`` field via the ``generate-headline`` skill and returns a
    primary headline, style-specific alternatives, and extracted key terms. The
    optional ``style`` parameter selects among ``news`` (default), ``academic``,
    and ``casual`` formats. The optional ``max_length`` parameter caps the headline
    character count (default 80).
    """

    def __init__(self) -> None:
        super().__init__(
            name="Headline Generator Agent",
            description=(
                "Extractive headline generation from text. Scores candidates using "
                "first-sentence extraction, named-entity detection, and topic-word "
                "frequency. Supports news, academic, and casual style options."
            ),
            port=9016,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming headline generation request.

        Args:
            skill_id: Must be ``generate-headline``.
            input_data: Dict with ``text`` (str), optional ``style`` (str, one of
                ``news``, ``academic``, ``casual``; default ``news``), and optional
                ``max_length`` (int; default 80).

        Returns:
            Dict with ``headline``, ``style``, ``alternatives`` (list of str),
            ``source_length``, and ``key_terms`` (list of str).
        """
        text: str = str(input_data.get("text", ""))
        if not text:
            return {
                "headline": "",
                "style": "news",
                "alternatives": [],
                "source_length": 0,
                "key_terms": [],
            }

        raw_style: str = str(input_data.get("style", "news")).lower()
        style = raw_style if raw_style in _STYLE_PREFIXES else "news"

        max_length: int = int(input_data.get("max_length", _DEFAULT_MAX_LENGTH))
        max_length = max(10, max_length)

        return _generate_headline(text, style, max_length)


agent = HeadlineGeneratorA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9016)
