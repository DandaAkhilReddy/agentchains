"""Readability Scorer A2A Agent — Flesch-Kincaid analysis via the A2A protocol.

Runs on port 9012 and exposes a ``score-readability`` skill. Computes the
Flesch Reading Ease score and the Flesch-Kincaid Grade Level for a given text,
along with sentence/word/syllable statistics and a human-readable grade label.
"""

from __future__ import annotations

import re
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "score-readability",
        "name": "Score Readability",
        "description": (
            "Compute Flesch Reading Ease and Flesch-Kincaid Grade Level for a "
            "text string. Returns numeric scores, a grade label, and detailed "
            "statistics (sentence count, word count, syllable count)."
        ),
        "tags": ["nlp", "readability", "flesch-kincaid", "text-analysis"],
        "examples": [
            '{"text": "The cat sat on the mat. It was a very sunny day."}',
            '{"text": "Quantum entanglement demonstrates non-local correlations between particles."}',
        ],
    }
]

# Grade-level label thresholds (Flesch-Kincaid grade integer boundaries)
_GRADE_LABELS: list[tuple[int, str]] = [
    (5, "Elementary"),
    (8, "Middle School"),
    (12, "High School"),
    (16, "College"),
]


def _count_sentences(text: str) -> int:
    """Count sentences by splitting on terminal punctuation (.!?).

    Args:
        text: Raw input text.

    Returns:
        Number of sentences found; at least 1 to avoid division by zero.
    """
    parts = re.split(r"[.!?]+", text.strip())
    count = sum(1 for p in parts if p.strip())
    return max(count, 1)


def _count_words(text: str) -> int:
    """Count words by splitting on whitespace.

    Args:
        text: Raw input text.

    Returns:
        Number of whitespace-separated tokens; at least 1.
    """
    words = text.split()
    return max(len(words), 1)


def _count_syllables_in_word(word: str) -> int:
    """Estimate syllable count for a single word using vowel-group heuristics.

    Rules applied in order:
    1. Strip non-alphabetic characters.
    2. Convert to lowercase.
    3. Remove a silent trailing 'e' when the word ends in a consonant + 'e'.
    4. Count contiguous vowel groups (a, e, i, o, u, y).
    5. Return at least 1 (every word has at least one syllable).

    Args:
        word: A single word string, may contain punctuation.

    Returns:
        Estimated syllable count (>= 1).
    """
    cleaned = re.sub(r"[^a-zA-Z]", "", word).lower()
    if not cleaned:
        return 1

    # Remove silent trailing 'e': word ends in consonant + e (e.g. "make", "code")
    if len(cleaned) > 2 and cleaned.endswith("e") and cleaned[-2] not in "aeiou":
        cleaned = cleaned[:-1]

    vowel_groups = re.findall(r"[aeiouy]+", cleaned)
    syllables = len(vowel_groups)
    return max(syllables, 1)


def _count_syllables(text: str) -> int:
    """Count total syllables across all words in a text.

    Args:
        text: Raw input text.

    Returns:
        Total estimated syllable count.
    """
    words = text.split()
    return sum(_count_syllables_in_word(w) for w in words) if words else 0


def _grade_label(fk_grade: float) -> str:
    """Map a Flesch-Kincaid grade level to a human-readable label.

    Args:
        fk_grade: Flesch-Kincaid Grade Level score.

    Returns:
        One of: "Elementary", "Middle School", "High School", "College", "Graduate".
    """
    grade = int(fk_grade)
    for threshold, label in _GRADE_LABELS:
        if grade <= threshold:
            return label
    return "Graduate"


def _score_readability(text: str) -> dict[str, Any]:
    """Compute Flesch Reading Ease and Flesch-Kincaid Grade Level for text.

    Formulas:
        Flesch Reading Ease = 206.835 - 1.015 * (words / sentences)
                                      - 84.6 * (syllables / words)
        FK Grade Level      = 0.39  * (words / sentences)
                            + 11.8  * (syllables / words) - 15.59

    Args:
        text: The input text to analyse.

    Returns:
        Dict with ``flesch_reading_ease``, ``flesch_kincaid_grade``,
        ``grade_label``, and ``stats`` (sentences, words, syllables,
        avg_sentence_length, avg_syllables_per_word).
    """
    sentences = _count_sentences(text)
    words = _count_words(text)
    syllables = _count_syllables(text)

    avg_sentence_length = round(words / sentences, 4)
    avg_syllables_per_word = round(syllables / words, 4)

    flesch_ease = round(
        206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word,
        2,
    )
    fk_grade = round(
        0.39 * avg_sentence_length + 11.8 * avg_syllables_per_word - 15.59,
        2,
    )

    return {
        "flesch_reading_ease": flesch_ease,
        "flesch_kincaid_grade": fk_grade,
        "grade_label": _grade_label(fk_grade),
        "stats": {
            "sentences": sentences,
            "words": words,
            "syllables": syllables,
            "avg_sentence_length": avg_sentence_length,
            "avg_syllables_per_word": avg_syllables_per_word,
        },
    }


class ReadabilityScorerA2AAgent(BaseA2AAgent):
    """A2A agent that computes Flesch-Kincaid readability scores.

    Accepts a ``text`` input via the ``score-readability`` skill and returns
    the Flesch Reading Ease score, Flesch-Kincaid Grade Level, a grade label,
    and detailed text statistics.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Readability Scorer Agent",
            description=(
                "Computes Flesch Reading Ease and Flesch-Kincaid Grade Level scores "
                "for a text input. Provides sentence, word, and syllable statistics "
                "alongside a human-readable grade label. Designed for pipeline integration."
            ),
            port=9012,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming readability scoring request.

        Args:
            skill_id: Must be ``score-readability``.
            input_data: Dict with a ``text`` (str) key containing the document
                to score.

        Returns:
            Dict with ``flesch_reading_ease`` (float), ``flesch_kincaid_grade``
            (float), ``grade_label`` (str), and ``stats`` (dict containing
            ``sentences``, ``words``, ``syllables``, ``avg_sentence_length``,
            and ``avg_syllables_per_word``).
        """
        text: str = str(input_data.get("text", ""))
        if not text.strip():
            return {
                "flesch_reading_ease": 0.0,
                "flesch_kincaid_grade": 0.0,
                "grade_label": "Elementary",
                "stats": {
                    "sentences": 0,
                    "words": 0,
                    "syllables": 0,
                    "avg_sentence_length": 0.0,
                    "avg_syllables_per_word": 0.0,
                },
            }

        return _score_readability(text)


agent = ReadabilityScorerA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9012)
