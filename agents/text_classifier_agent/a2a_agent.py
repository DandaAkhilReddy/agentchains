"""Text Classifier A2A Agent — TF-IDF-inspired keyword scoring via the A2A protocol.

Runs on port 9010 and exposes a ``classify-text`` skill. Accepts a text string
and an optional list of target categories, scores each category using keyword
frequency normalised by document length, and returns the top-3 matches.
"""

from __future__ import annotations

import re
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "classify-text",
        "name": "Classify Text",
        "description": (
            "Classify a text string into one or more predefined categories using "
            "TF-IDF-inspired keyword scoring. Returns the top-3 matching categories "
            "with scores and matching keywords."
        ),
        "tags": ["nlp", "classification", "text-analysis", "tfidf"],
        "examples": [
            '{"text": "Machine learning algorithms are transforming cloud platforms."}',
            '{"text": "The team scored three goals in the championship match.", "categories": ["sports", "entertainment"]}',
        ],
    }
]

_DEFAULT_CATEGORIES: list[str] = [
    "technology",
    "science",
    "business",
    "health",
    "education",
    "politics",
    "entertainment",
    "sports",
]

# Keyword sets per category — lowercase for case-insensitive matching
_CATEGORY_KEYWORDS: dict[str, frozenset[str]] = {
    "technology": frozenset({
        "ai", "software", "algorithm", "data", "computer", "programming", "api",
        "cloud", "digital", "machine", "neural", "database", "automation", "cyber",
        "code", "tech", "silicon", "hardware", "network", "platform",
    }),
    "science": frozenset({
        "research", "experiment", "hypothesis", "theory", "quantum", "physics",
        "chemistry", "biology", "molecule", "genome", "evolution", "particle",
        "laboratory", "discovery", "scientific", "atom", "cell", "organism",
        "dna", "equation",
    }),
    "business": frozenset({
        "market", "revenue", "profit", "startup", "enterprise", "investment",
        "ceo", "stock", "finance", "strategy", "growth", "customer", "sales",
        "supply", "trade", "corporate", "capital", "merger", "acquisition",
        "economy",
    }),
    "health": frozenset({
        "medical", "disease", "treatment", "patient", "clinical", "therapy",
        "diagnosis", "wellness", "fitness", "nutrition", "pharmaceutical",
        "hospital", "doctor", "symptom", "vaccine", "mental", "chronic",
        "surgery", "prescription", "healthcare",
    }),
    "education": frozenset({
        "learning", "school", "university", "student", "curriculum", "teaching",
        "academic", "degree", "course", "classroom", "exam", "scholarship",
        "tutor", "professor", "knowledge", "literacy", "research", "study",
        "campus", "enrollment",
    }),
    "politics": frozenset({
        "government", "policy", "election", "vote", "democrat", "republican",
        "congress", "senate", "legislation", "campaign", "debate", "reform",
        "diplomat", "regulation", "party", "law", "constitution", "president",
        "democracy", "political",
    }),
    "entertainment": frozenset({
        "movie", "music", "game", "show", "celebrity", "film", "artist",
        "concert", "streaming", "theater", "festival", "award", "comedy",
        "drama", "performance", "acting", "director", "album", "series",
        "audience",
    }),
    "sports": frozenset({
        "team", "player", "championship", "score", "coach", "league", "match",
        "tournament", "athlete", "stadium", "victory", "training", "fitness",
        "medal", "competition", "season", "referee", "record", "draft", "goal",
    }),
}


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase word tokens, stripping non-alphabetic characters.

    Args:
        text: Raw input text.

    Returns:
        List of lowercase word strings.
    """
    return [w.lower() for w in re.findall(r"\b[a-zA-Z]+\b", text)]


def _score_category(
    tokens: list[str], category: str, keywords: frozenset[str]
) -> dict[str, Any]:
    """Score a single category against a token list.

    Score is the count of matching keywords normalised by the total number of
    tokens (capped to prevent division-by-zero on empty input).

    Args:
        tokens: Lowercase word tokens from the input text.
        category: Category name string.
        keywords: Frozenset of lowercase keyword strings for this category.

    Returns:
        Dict with ``category``, ``score``, and ``matching_keywords`` keys.
    """
    matching = [t for t in tokens if t in keywords]
    unique_matches = list(dict.fromkeys(matching))  # preserve insertion order, deduplicate
    total = max(len(tokens), 1)
    score = round(len(matching) / total, 6)
    return {
        "category": category,
        "score": score,
        "matching_keywords": unique_matches,
    }


def _classify(text: str, categories: list[str]) -> dict[str, Any]:
    """Classify text against a list of categories using keyword scoring.

    Args:
        text: The input text to classify.
        categories: Category names to score against. Unknown names are skipped
            gracefully (no score entry is produced).

    Returns:
        Dict with ``text_excerpt``, ``classifications`` (top-3 by score), and
        ``top_category``.
    """
    tokens = _tokenize(text)
    text_excerpt = text[:200].rstrip() + ("..." if len(text) > 200 else "")

    scored: list[dict[str, Any]] = []
    for cat in categories:
        kw = _CATEGORY_KEYWORDS.get(cat)
        if kw is None:
            continue
        scored.append(_score_category(tokens, cat, kw))

    # Sort descending by score, take top-3
    scored.sort(key=lambda x: x["score"], reverse=True)
    top3 = scored[:3]

    top_category = top3[0]["category"] if top3 else "unknown"

    return {
        "text_excerpt": text_excerpt,
        "classifications": top3,
        "top_category": top_category,
    }


class TextClassifierA2AAgent(BaseA2AAgent):
    """A2A agent that classifies text into predefined categories.

    Uses TF-IDF-inspired keyword frequency scoring. Accepts a ``text`` input
    and an optional ``categories`` list to restrict classification scope.
    Returns the top-3 matching categories with normalised scores.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Text Classifier Agent",
            description=(
                "TF-IDF-inspired keyword scoring to classify text into one of eight "
                "default categories (technology, science, business, health, education, "
                "politics, entertainment, sports). Supports custom category lists. "
                "Returns top-3 matches with scores and matching keywords."
            ),
            port=9010,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming text classification request.

        Args:
            skill_id: Must be ``classify-text``.
            input_data: Dict with ``text`` (str) and optional ``categories`` (list[str]).
                Unknown category names are silently ignored. If ``categories`` is omitted
                or empty, all eight default categories are used.

        Returns:
            Dict with ``text_excerpt``, ``classifications`` (list of up to 3 items each
            containing ``category``, ``score``, and ``matching_keywords``), and
            ``top_category``.
        """
        text: str = str(input_data.get("text", ""))
        if not text.strip():
            return {
                "text_excerpt": "",
                "classifications": [],
                "top_category": "unknown",
            }

        raw_cats = input_data.get("categories")
        if isinstance(raw_cats, list) and raw_cats:
            categories = [str(c).lower() for c in raw_cats]
        else:
            categories = _DEFAULT_CATEGORIES

        return _classify(text, categories)


agent = TextClassifierA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9010)
