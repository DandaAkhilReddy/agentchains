"""Web Search A2A Agent — simulated web search exposed via the A2A protocol.

Runs on port 9001 and exposes a single ``web-search`` skill that accepts a
query string and returns a list of realistic-looking simulated search results.
Designed for use as the first link in a multi-agent pipeline.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "web-search",
        "name": "Web Search",
        "description": "Search the web and return structured results with titles, URLs, and snippets.",
        "tags": ["search", "web", "information-retrieval"],
        "examples": [
            '{"query": "Python async best practices"}',
            '{"query": "machine learning trends 2025", "num_results": 3}',
        ],
    }
]


def _slugify(text: str) -> str:
    """Convert arbitrary text to a URL-safe slug.

    Args:
        text: Raw text to slugify.

    Returns:
        Lowercase hyphen-separated slug with non-alphanumeric characters removed.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return slug.strip("-")[:60]


def _generate_results(query: str, num_results: int) -> list[dict[str, str]]:
    """Produce a deterministic set of simulated search results for a query.

    Results are deterministic (keyed by query hash) so repeated calls with
    the same query always return identical output — useful for testing chains.

    Args:
        query: The search query string.
        num_results: How many results to return (clamped to 1–10).

    Returns:
        List of result dicts, each with ``title``, ``url``, and ``snippet``.
    """
    count = max(1, min(num_results, 10))
    slug = _slugify(query)
    # Deterministic seed so results are reproducible
    seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)  # noqa: S324

    domains = [
        "docs.example.com",
        "guide.example.org",
        "learn.example.net",
        "wiki.example.io",
        "blog.example.com",
        "research.example.org",
        "tutorials.example.net",
        "reference.example.com",
        "news.example.io",
        "forum.example.org",
    ]

    templates = [
        ("Complete Guide to {query}", "A comprehensive overview of {query}, covering fundamentals, advanced techniques, and practical examples."),
        ("{query} — Official Documentation", "Official reference documentation for {query}. Includes API references, tutorials, and migration guides."),
        ("Understanding {query}: A Deep Dive", "In-depth analysis of {query} with real-world case studies, benchmarks, and expert recommendations."),
        ("{query} Best Practices 2025", "Industry-standard best practices for {query} compiled from production deployments and community feedback."),
        ("Getting Started with {query}", "Step-by-step beginner guide to {query}. Set up your environment and build your first project in minutes."),
        ("{query} vs Alternatives: Comparison", "Detailed comparison of {query} against popular alternatives, covering performance, usability, and cost."),
        ("Troubleshooting {query} Common Issues", "Solutions to the most frequently encountered problems when working with {query}, with debugging tips."),
        ("Advanced {query} Patterns", "Expert-level patterns and idioms for {query} used in high-scale production systems."),
        ("{query} Community Forum — Top Threads", "Active community discussions about {query} including Q&A, tips, and announcements."),
        ("{query} Security Considerations", "Security analysis of {query}: known vulnerabilities, hardening guides, and threat modelling."),
    ]

    results: list[dict[str, str]] = []
    for i in range(count):
        idx = (seed + i) % len(templates)
        title_tmpl, snippet_tmpl = templates[idx]
        domain = domains[(seed + i * 3) % len(domains)]
        path_suffix = (seed + i * 7) % 9999

        title = title_tmpl.format(query=query.title())
        snippet = snippet_tmpl.format(query=query)
        url = f"https://{domain}/{slug}-{path_suffix}"

        results.append({"title": title, "url": url, "snippet": snippet})

    return results


class WebSearchA2AAgent(BaseA2AAgent):
    """A2A agent that performs simulated web searches.

    Exposes a ``web-search`` skill. Input may be a JSON object with a
    ``query`` field or a plain text string which is used as the query.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Web Search Agent",
            description=(
                "Performs simulated web searches and returns structured results "
                "with titles, URLs, and snippets. Suitable for chaining as a "
                "data-gathering step before summarization or report generation."
            ),
            port=9001,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming skill invocation.

        Args:
            skill_id: Must be ``web-search``.
            input_data: Dict with ``query`` (str) and optional ``num_results`` (int).
                        Falls back to ``text`` key if ``query`` is absent.

        Returns:
            Dict with ``query``, ``total_results``, and ``results`` list.
        """
        query: str = input_data.get("query") or input_data.get("text", "")
        if not query:
            query = "general information"

        num_results: int = int(input_data.get("num_results", 5))
        results = _generate_results(query, num_results)

        return {
            "query": query,
            "total_results": len(results),
            "results": results,
        }


agent = WebSearchA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9001)
