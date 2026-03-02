"""NER Extractor A2A Agent — regex-based named entity recognition via the A2A protocol.

Runs on port 9011 and exposes an ``extract-entities`` skill. Applies a suite of
compiled regular expressions to identify PERSON, ORGANIZATION, DATE, EMAIL,
PHONE, URL, MONEY, and PERCENTAGE entities within a text string.
"""

from __future__ import annotations

import re
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "extract-entities",
        "name": "Extract Named Entities",
        "description": (
            "Regex-based named entity recognition. Detects PERSON, ORGANIZATION, "
            "DATE, EMAIL, PHONE, URL, MONEY, and PERCENTAGE entities in text. "
            "Returns entity spans with start/end offsets."
        ),
        "tags": ["nlp", "ner", "entity-extraction", "text-analysis"],
        "examples": [
            '{"text": "Elon Musk founded SpaceX Inc. on March 14, 2002."}',
            '{"text": "Contact us at info@example.com or call (555) 123-4567."}',
        ],
    }
]

# ── Compiled entity patterns ──────────────────────────────────────────────────

# PERSON: Two consecutive title-case words (e.g., "John Smith")
_RE_PERSON = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b")

# ORGANIZATION: Title-case word(s) followed by a corporate suffix, OR an
# all-caps acronym of 2–5 letters that stands alone.
_RE_ORG_SUFFIX = re.compile(
    r"\b(?:[A-Z][a-zA-Z&]*\s+)*[A-Z][a-zA-Z&]*\s+"
    r"(?:Inc|Corp|Ltd|LLC|Foundation|University|Institute)\.?\b"
)
_RE_ORG_ACRONYM = re.compile(r"\b[A-Z]{2,5}\b")

# DATE: "January 15, 2024" / "Jan 2024" / "2024-01-15" / "15/01/2024"
_RE_DATE = re.compile(
    r"\b(?:"
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},\s+\d{4}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}/\d{1,2}/\d{4}"
    r")\b"
)

# EMAIL
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# PHONE: (xxx) xxx-xxxx  |  xxx-xxx-xxxx  |  +1xxxxxxxxxx
_RE_PHONE = re.compile(
    r"(?:\(\d{3}\)\s*\d{3}-\d{4}|\d{3}-\d{3}-\d{4}|\+1\d{10})"
)

# URL
_RE_URL = re.compile(r"https?://[^\s,\"'<>\)\]]+")

# MONEY: $xxx.xx  |  USD xxx  |  EUR xxx
_RE_MONEY = re.compile(
    r"(?:\$\d[\d,]*(?:\.\d{1,2})?|(?:USD|EUR)\s+\d[\d,]*(?:\.\d{1,2})?)"
)

# PERCENTAGE
_RE_PERCENTAGE = re.compile(r"\b\d+(?:\.\d+)?%")

# Ordered list of (entity_type, pattern) pairs
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", _RE_EMAIL),          # before URL to avoid partial URL matches
    ("URL", _RE_URL),
    ("PHONE", _RE_PHONE),
    ("MONEY", _RE_MONEY),
    ("PERCENTAGE", _RE_PERCENTAGE),
    ("DATE", _RE_DATE),
    ("ORG_SUFFIX", _RE_ORG_SUFFIX),
    ("ORG_ACRONYM", _RE_ORG_ACRONYM),
    ("PERSON", _RE_PERSON),
]

# Acronyms that are not organizations (common English words / abbreviations)
_ACRONYM_STOPLIST: frozenset[str] = frozenset({
    "I", "A", "OK", "AM", "PM", "US", "UK", "EU", "UN", "IT", "TV", "PC",
    "AI", "ML", "AR", "VR", "HR", "PR", "CEO", "CTO", "CFO",
})


def _extract_entities(text: str) -> dict[str, Any]:
    """Run all entity patterns against the input text and return deduplicated results.

    Entities are deduplicated by (text, type) pair. When two spans with the same
    text and type are found, only the first occurrence is retained.

    Args:
        text: The input text to scan for named entities.

    Returns:
        Dict with ``entities`` (list of {text, type, start, end}),
        ``entity_counts`` (counts per type), and ``total_entities``.
    """
    seen: set[tuple[str, str]] = set()
    entities: list[dict[str, Any]] = []

    # Track character ranges that have already been claimed so that less-specific
    # patterns do not re-capture sub-spans of an already found entity.
    claimed: list[tuple[int, int]] = []

    def _is_claimed(start: int, end: int) -> bool:
        for cs, ce in claimed:
            if start < ce and end > cs:
                return True
        return False

    for entity_type, pattern in _PATTERNS:
        # Normalize internal types
        normalized_type = "ORGANIZATION" if entity_type.startswith("ORG") else entity_type

        for match in pattern.finditer(text):
            span_text = match.group()
            start, end = match.start(), match.end()

            # Skip acronym stop-list entries
            if entity_type == "ORG_ACRONYM" and span_text in _ACRONYM_STOPLIST:
                continue

            if _is_claimed(start, end):
                continue

            key = (span_text, normalized_type)
            if key in seen:
                continue

            seen.add(key)
            claimed.append((start, end))
            entities.append({
                "text": span_text,
                "type": normalized_type,
                "start": start,
                "end": end,
            })

    # Sort by appearance order
    entities.sort(key=lambda e: e["start"])

    # Build count map
    entity_counts: dict[str, int] = {
        "PERSON": 0,
        "ORGANIZATION": 0,
        "DATE": 0,
        "EMAIL": 0,
        "PHONE": 0,
        "URL": 0,
        "MONEY": 0,
        "PERCENTAGE": 0,
    }
    for e in entities:
        etype: str = e["type"]
        entity_counts[etype] = entity_counts.get(etype, 0) + 1

    return {
        "entities": entities,
        "entity_counts": entity_counts,
        "total_entities": len(entities),
    }


class NERExtractorA2AAgent(BaseA2AAgent):
    """A2A agent that performs regex-based named entity recognition.

    Exposes the ``extract-entities`` skill which scans input text for eight
    entity types: PERSON, ORGANIZATION, DATE, EMAIL, PHONE, URL, MONEY, and
    PERCENTAGE. Results are deduplicated and sorted by occurrence order.
    """

    def __init__(self) -> None:
        super().__init__(
            name="NER Extractor Agent",
            description=(
                "Regex-based named entity recognition covering PERSON, ORGANIZATION, "
                "DATE, EMAIL, PHONE, URL, MONEY, and PERCENTAGE entities. Returns "
                "entity spans with offsets, per-type counts, and a total count. "
                "Designed for pipeline integration."
            ),
            port=9011,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming entity extraction request.

        Args:
            skill_id: Must be ``extract-entities``.
            input_data: Dict with a ``text`` (str) key containing the document to scan.

        Returns:
            Dict with ``entities`` (list of {text, type, start, end}),
            ``entity_counts`` (dict of type → count), and ``total_entities`` (int).
        """
        text: str = str(input_data.get("text", ""))
        if not text.strip():
            return {
                "entities": [],
                "entity_counts": {
                    "PERSON": 0,
                    "ORGANIZATION": 0,
                    "DATE": 0,
                    "EMAIL": 0,
                    "PHONE": 0,
                    "URL": 0,
                    "MONEY": 0,
                    "PERCENTAGE": 0,
                },
                "total_entities": 0,
            }

        return _extract_entities(text)


agent = NERExtractorA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9011)
