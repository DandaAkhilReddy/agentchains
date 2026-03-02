"""PII Redactor A2A Agent — regex-based PII detection and redaction via the A2A protocol.

Runs on port 9013 and exposes a ``redact-pii`` skill. Uses regular expressions to
detect and redact personally identifiable information including emails, phone numbers,
SSNs, credit card numbers, IP addresses, and date-of-birth patterns.
"""

from __future__ import annotations

import re
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "redact-pii",
        "name": "Redact PII",
        "description": (
            "Regex-based detection and redaction of personally identifiable information "
            "from text. Handles emails, phone numbers, SSNs, credit cards, IP addresses, "
            "and date-of-birth patterns."
        ),
        "tags": ["pii", "redaction", "compliance", "privacy", "security"],
        "examples": [
            '{"text": "Contact john@example.com or call (555) 123-4567"}',
            '{"text": "SSN: 123-45-6789", "redaction_char": "*"}',
        ],
    }
]

# Ordered list of (pii_type, compiled_pattern, placeholder) tuples.
# Order matters: more specific patterns should precede ambiguous ones.
_PII_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "SSN",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[SSN_REDACTED]",
    ),
    (
        "CreditCard",
        re.compile(
            r"\b(?:\d{4}[-\s]){3}\d{4}\b"
        ),
        "[CC_REDACTED]",
    ),
    (
        "Email",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL_REDACTED]",
    ),
    (
        "Phone",
        re.compile(
            r"(?:\+1[-.\s]?)?"
            r"(?:\(\d{3}\)[-.\s]?|\d{3}[-.\s])"
            r"\d{3}[-.\s]\d{4}\b"
        ),
        "[PHONE_REDACTED]",
    ),
    (
        "IPAddress",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
        "[IP_REDACTED]",
    ),
    (
        "DateOfBirth",
        re.compile(
            r"(?:"
            r"DOB\s*:\s*\d{1,2}/\d{1,2}/\d{4}"
            r"|born\s+on\s+\d{1,2}/\d{1,2}/\d{4}"
            r")",
            re.IGNORECASE,
        ),
        "[DOB_REDACTED]",
    ),
]


def _redact_text(text: str) -> dict[str, Any]:
    """Apply all PII redaction patterns to text and collect redaction statistics.

    Each pattern type is applied in sequence. Matches are replaced with their
    corresponding placeholder string. Counts of each redaction type are tracked.

    Args:
        text: Raw input text that may contain PII.

    Returns:
        Dict with ``redacted_text``, ``redactions`` (list of type/count dicts),
        ``original_length``, and ``total_redactions``.
    """
    redacted = text
    redaction_counts: dict[str, int] = {}

    for pii_type, pattern, placeholder in _PII_PATTERNS:
        matches = pattern.findall(redacted)
        if matches:
            redaction_counts[pii_type] = len(matches)
            redacted = pattern.sub(placeholder, redacted)

    redactions = [
        {"type": pii_type, "count": count}
        for pii_type, count in redaction_counts.items()
    ]
    total = sum(r["count"] for r in redactions)

    return {
        "original_length": len(text),
        "redacted_text": redacted,
        "redactions": redactions,
        "total_redactions": total,
    }


class PIIRedactorA2AAgent(BaseA2AAgent):
    """A2A agent that detects and redacts PII from text using regular expressions.

    Accepts a ``text`` field via the ``redact-pii`` skill and returns the redacted
    text together with counts of each PII type found. An optional ``redaction_char``
    parameter is accepted for interface compatibility but the current implementation
    uses fixed placeholder tokens for clear, auditable redaction.
    """

    def __init__(self) -> None:
        super().__init__(
            name="PII Redactor Agent",
            description=(
                "Regex-based PII detection and redaction. Handles emails, phone numbers, "
                "SSNs, credit card numbers, IPv4 addresses, and date-of-birth patterns. "
                "Returns redacted text and per-type redaction counts."
            ),
            port=9013,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming PII redaction request.

        Args:
            skill_id: Must be ``redact-pii``.
            input_data: Dict with ``text`` (str) and optional ``redaction_char`` (str,
                accepted but unused — placeholder tokens are always used).

        Returns:
            Dict with ``original_length``, ``redacted_text``, ``redactions``
            (list of ``{type, count}`` dicts), and ``total_redactions``.
        """
        text: str = str(input_data.get("text", ""))
        if not text:
            return {
                "original_length": 0,
                "redacted_text": "",
                "redactions": [],
                "total_redactions": 0,
            }

        return _redact_text(text)


agent = PIIRedactorA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9013)
