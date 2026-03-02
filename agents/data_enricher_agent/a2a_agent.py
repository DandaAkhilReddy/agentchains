"""Data Enricher A2A Agent — URL metadata extraction via the A2A protocol.

Runs on port 9006 and exposes an ``enrich-data`` skill. Accepts one or more
URLs (as a list, a single string, or embedded in free text) and returns
enriched metadata for each: domain, protocol, path, query parameters,
content-type guess, and a human-readable category label.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "enrich-data",
        "name": "Enrich Data",
        "description": (
            "Parse and enrich one or more URLs with domain metadata, path "
            "components, query parameters, content-type guesses, and category "
            "labels (documentation, news, social, research, general)."
        ),
        "tags": ["url", "metadata", "enrichment", "parsing"],
        "examples": [
            '{"urls": ["https://docs.python.org/3/library/os.html", "https://arxiv.org/abs/2301.00001"]}',
            '{"url": "https://github.com/example/repo"}',
            '{"text": "Check out https://news.ycombinator.com for tech news"}',
        ],
    }
]

# Patterns for URL extraction from free text
_URL_PATTERN: re.Pattern[str] = re.compile(
    r"https?://[^\s\"'<>)}\]]+",
    re.IGNORECASE,
)

# Domain fragments mapped to categories (checked via substring matching)
_DOCUMENTATION_SIGNALS: tuple[str, ...] = (
    "docs.", "documentation.", "wiki.", "readthedocs.", "rtfd.", "devdocs.",
    "developer.", "reference.", "manual.", "api.",
)
_NEWS_SIGNALS: tuple[str, ...] = (
    "news.", "nytimes.", "bbc.", "cnn.", "reuters.", "theguardian.",
    "washingtonpost.", "ycombinator.", "techcrunch.", "wired.", "bloomberg.",
    "forbes.", "medium.", "substack.",
)
_SOCIAL_SIGNALS: tuple[str, ...] = (
    "twitter.", "x.com", "facebook.", "instagram.", "linkedin.", "reddit.",
    "tiktok.", "youtube.", "pinterest.", "snapchat.",
)
_RESEARCH_SIGNALS: tuple[str, ...] = (
    "arxiv.", "scholar.google.", "semanticscholar.", "pubmed.", "ncbi.",
    "researchgate.", "jstor.", "springer.", "ieee.", "acm.", "nature.",
    "science.", "cell.", "doi.",
)

# Extension to MIME-type guesses
_EXT_CONTENT_TYPES: dict[str, str] = {
    ".html": "text/html",
    ".htm": "text/html",
    ".json": "application/json",
    ".xml": "application/xml",
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".js": "application/javascript",
    ".css": "text/css",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".zip": "application/zip",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
}


def _guess_content_type(path: str) -> str:
    """Infer a MIME type from a URL path's file extension.

    Args:
        path: The path component of a URL (e.g. ``/docs/guide.html``).

    Returns:
        A MIME type string, or ``"text/html"`` as the default.
    """
    # Find last extension
    dot_pos = path.rfind(".")
    if dot_pos == -1:
        return "text/html"
    ext = path[dot_pos:].lower().split("?")[0]
    return _EXT_CONTENT_TYPES.get(ext, "text/html")


def _categorise(domain: str, path: str) -> str:
    """Assign a human-readable category to a URL based on domain and path signals.

    Args:
        domain: The netloc of the URL in lowercase.
        path: The path component of the URL in lowercase.

    Returns:
        One of ``"documentation"``, ``"news"``, ``"social"``, ``"research"``,
        or ``"general"``.
    """
    combined = domain + path
    if any(sig in combined for sig in _DOCUMENTATION_SIGNALS):
        return "documentation"
    if any(sig in combined for sig in _RESEARCH_SIGNALS):
        return "research"
    if any(sig in combined for sig in _NEWS_SIGNALS):
        return "news"
    if any(sig in combined for sig in _SOCIAL_SIGNALS):
        return "social"
    return "general"


def _enrich_url(raw_url: str) -> dict[str, Any]:
    """Extract and enrich metadata from a single URL string.

    Args:
        raw_url: A raw URL string (may include trailing punctuation).

    Returns:
        Dict with ``original_url``, ``domain``, ``protocol``, ``path``,
        ``query_params``, ``content_type_guess``, and ``category``.
        If the URL cannot be parsed, returns an error record with
        ``parse_error`` set to ``True``.
    """
    # Strip common trailing punctuation added by prose text
    cleaned = raw_url.rstrip(".,;:!?)\"'")
    try:
        parsed = urlparse(cleaned)
    except ValueError as exc:
        return {
            "original_url": raw_url,
            "parse_error": True,
            "error_detail": str(exc),
        }

    domain = parsed.netloc.lower()
    path = parsed.path or "/"
    protocol = parsed.scheme.lower()
    query_params: dict[str, list[str]] = parse_qs(parsed.query)
    content_type = _guess_content_type(path)
    category = _categorise(domain, path.lower())

    return {
        "original_url": cleaned,
        "domain": domain,
        "protocol": protocol,
        "path": path,
        "query_params": query_params,
        "content_type_guess": content_type,
        "category": category,
    }


def _extract_urls_from_text(text: str) -> list[str]:
    """Extract all HTTP/HTTPS URLs embedded in arbitrary text.

    Args:
        text: Free-form text that may contain URLs.

    Returns:
        List of URL strings found in the text. Empty list if none found.
    """
    return _URL_PATTERN.findall(text)


class DataEnricherA2AAgent(BaseA2AAgent):
    """A2A agent that enriches URLs with domain metadata and category labels.

    Accepts ``urls`` (list), ``url`` (single string), or ``text`` (free-form
    text containing URLs) and returns enriched records for each URL found.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Data Enricher Agent",
            description=(
                "Parses and enriches URLs with domain metadata, path components, "
                "query parameters, content-type guesses, and category labels. "
                "Accepts URL lists, single URLs, or free text containing URLs."
            ),
            port=9006,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming data-enrichment request.

        Args:
            skill_id: Must be ``enrich-data``.
            input_data: Dict with one of:
                - ``urls``: list of URL strings
                - ``url``: a single URL string
                - ``text``: free-form text from which URLs are extracted

        Returns:
            Dict with ``enriched`` list, each item containing ``original_url``,
            ``domain``, ``protocol``, ``path``, ``query_params``,
            ``content_type_guess``, and ``category``.
        """
        raw_urls: list[str]

        if isinstance(input_data.get("urls"), list):
            raw_urls = [str(u) for u in input_data["urls"]]
        elif isinstance(input_data.get("url"), str):
            raw_urls = [input_data["url"]]
        else:
            text: str = input_data.get("text", "")
            raw_urls = _extract_urls_from_text(text)

        if not raw_urls:
            return {"enriched": []}

        enriched = [_enrich_url(u) for u in raw_urls]
        return {"enriched": enriched}


agent = DataEnricherA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9006)
