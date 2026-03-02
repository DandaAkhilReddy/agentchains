"""Paper Finder A2A Agent — mock academic paper search via the A2A protocol.

Runs on port 9005 and exposes a ``find-papers`` skill. Accepts a search query
or free-form text and returns a list of realistic-looking academic papers
generated deterministically from query keywords. Designed as a research-data
source in multi-agent pipelines.
"""

from __future__ import annotations

import hashlib
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "find-papers",
        "name": "Find Papers",
        "description": (
            "Search a mock academic database and return structured paper records "
            "with titles, authors, abstracts, DOIs, and citation counts. "
            "Results are deterministic for a given query."
        ),
        "tags": ["research", "academic", "papers", "information-retrieval"],
        "examples": [
            '{"query": "transformer models in NLP", "max_results": 5}',
            '{"text": "reinforcement learning robotics"}',
        ],
    }
]

_AUTHOR_FIRST_NAMES: list[str] = [
    "Alice", "Bob", "Carlos", "Diana", "Ethan", "Fiona", "George",
    "Hannah", "Ivan", "Julia", "Kevin", "Laura", "Marcus", "Nina",
    "Oscar", "Priya", "Quentin", "Rachel", "Samuel", "Tina",
]

_AUTHOR_LAST_NAMES: list[str] = [
    "Anderson", "Brown", "Chen", "Davis", "Evans", "Fischer", "Garcia",
    "Huang", "Ibrahim", "Johnson", "Kumar", "Liu", "Martinez", "Nakamura",
    "O'Brien", "Patel", "Quinn", "Rodriguez", "Singh", "Thompson",
    "Ueda", "Vasquez", "Wang", "Xu", "Yang", "Zhang",
]

_VENUES: list[str] = [
    "NeurIPS", "ICML", "ICLR", "ACL", "CVPR", "EMNLP", "AAAI",
    "IJCAI", "ECCV", "NAACL", "ACM CCS", "SIGKDD", "WWW", "SIGIR",
]

_TITLE_TEMPLATES: list[str] = [
    "Towards Efficient {topic}: A Scalable Approach",
    "Deep Learning for {topic}: Methods and Applications",
    "A Survey of {topic} Techniques in Modern Systems",
    "Benchmarking {topic}: Lessons from Large-Scale Experiments",
    "Self-Supervised {topic} with Contrastive Objectives",
    "Robust {topic} Under Distribution Shift",
    "Multi-Modal {topic}: Bridging Vision and Language",
    "Attention-Based {topic} for Sequence Modelling",
    "On the Limitations of {topic} in Low-Resource Settings",
    "Federated Learning Approaches to {topic}",
]

_ABSTRACT_TEMPLATES: list[str] = [
    (
        "We present a novel approach to {topic} that achieves state-of-the-art "
        "performance on standard benchmarks. Our method leverages a combination "
        "of self-attention mechanisms and auxiliary objectives to improve "
        "generalisation. Extensive experiments on five datasets demonstrate "
        "significant gains over prior work, with up to {gain}% improvement."
    ),
    (
        "This paper surveys recent advances in {topic}, categorising existing "
        "methods along three axes: architecture, training strategy, and "
        "evaluation protocol. We identify open challenges and propose a "
        "unified evaluation framework to facilitate fair comparison across "
        "methods. Our meta-analysis covers {papers} papers published 2020-2025."
    ),
    (
        "We study the problem of {topic} under distribution shift and show that "
        "existing methods degrade significantly when tested out-of-distribution. "
        "To address this, we propose a regularisation scheme that improves "
        "robustness by {gain}% on adversarial benchmarks while retaining "
        "in-distribution performance."
    ),
    (
        "Large-scale pre-training has transformed {topic}, yet the computational "
        "cost remains prohibitive for most practitioners. We introduce a "
        "parameter-efficient fine-tuning strategy that matches full fine-tuning "
        "with only {gain}% of the trainable parameters, enabling deployment on "
        "commodity hardware."
    ),
    (
        "We propose {topic}-Net, an end-to-end trainable architecture that unifies "
        "perception and reasoning for {topic}. The model is pre-trained on a "
        "curated corpus of {papers}K samples and fine-tuned with {gain}% fewer "
        "labels than comparable methods, demonstrating strong few-shot capability."
    ),
]


def _int_hash(text: str, mod: int) -> int:
    """Return a deterministic integer hash of *text* modulo *mod*.

    Args:
        text: Input string to hash.
        mod: Modulus for the result.

    Returns:
        Non-negative integer in ``[0, mod)``.
    """
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16) % mod  # noqa: S324


def _make_authors(seed: int, count: int) -> list[str]:
    """Generate a list of plausible academic author names.

    Args:
        seed: Numeric seed controlling name selection.
        count: Number of authors to generate (1–4).

    Returns:
        List of ``"First Last"`` name strings.
    """
    authors: list[str] = []
    for i in range(count):
        first = _AUTHOR_FIRST_NAMES[(seed + i * 3) % len(_AUTHOR_FIRST_NAMES)]
        last = _AUTHOR_LAST_NAMES[(seed + i * 7) % len(_AUTHOR_LAST_NAMES)]
        authors.append(f"{first} {last}")
    return authors


def _topic_from_query(query: str) -> str:
    """Extract a short topic label from a search query.

    Takes up to three content words from the query, capitalised, for use
    inside title and abstract templates.

    Args:
        query: The raw search query string.

    Returns:
        Capitalised topic phrase (2–3 words).
    """
    stopwords = {"a", "an", "the", "of", "in", "for", "on", "and", "or", "to", "with"}
    words = [w for w in query.lower().split() if w.isalpha() and w not in stopwords]
    topic_words = words[:3] if words else ["research"]
    return " ".join(w.capitalize() for w in topic_words)


def _generate_papers(query: str, max_results: int) -> list[dict[str, Any]]:
    """Produce a deterministic list of mock academic papers for a query.

    Papers are fully reproducible for a given (query, count) pair, making
    them safe to use in pipeline tests.

    Args:
        query: The search query driving paper generation.
        max_results: Maximum number of papers to return (clamped to 1–10).

    Returns:
        List of paper dicts, each with ``title``, ``authors``, ``year``,
        ``abstract``, ``doi``, and ``citations``.
    """
    count = max(1, min(max_results, 10))
    seed = _int_hash(query, 10_000)
    topic = _topic_from_query(query)

    papers: list[dict[str, Any]] = []
    for i in range(count):
        paper_seed = seed + i * 31

        title_tmpl = _TITLE_TEMPLATES[paper_seed % len(_TITLE_TEMPLATES)]
        abstract_tmpl = _ABSTRACT_TEMPLATES[paper_seed % len(_ABSTRACT_TEMPLATES)]
        venue = _VENUES[(paper_seed + 5) % len(_VENUES)]
        year = 2020 + (paper_seed % 6)  # 2020-2025
        num_authors = 2 + (paper_seed % 2)  # 2-3 authors
        authors = _make_authors(paper_seed, num_authors)
        gain = 5 + (paper_seed % 30)  # percentage improvement 5-34
        num_papers_ref = 50 + (paper_seed % 200)  # survey coverage
        doi_hash = hashlib.md5(f"{query}{i}".encode()).hexdigest()[:10]  # noqa: S324
        doi = f"10.1234/mock.{doi_hash}"
        citations = (paper_seed * 17) % 500

        title = title_tmpl.format(topic=topic)
        abstract = abstract_tmpl.format(topic=topic.lower(), gain=gain, papers=num_papers_ref)

        papers.append(
            {
                "title": title,
                "authors": authors,
                "year": year,
                "venue": venue,
                "abstract": abstract,
                "doi": doi,
                "citations": citations,
            }
        )

    return papers


class PaperFinderA2AAgent(BaseA2AAgent):
    """A2A agent that returns mock academic paper records for a query.

    Exposes a ``find-papers`` skill. Input may be a JSON object with a
    ``query`` field (and optional ``max_results``), or a plain text string
    routed via the ``text`` key by the base class.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Paper Finder Agent",
            description=(
                "Searches a mock academic database and returns structured paper "
                "records including titles, authors, abstracts, DOIs, and citation "
                "counts. Results are deterministic and suitable for pipeline testing."
            ),
            port=9005,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming paper-search request.

        Args:
            skill_id: Must be ``find-papers``.
            input_data: Dict with ``query`` (str) and optional ``max_results``
                (int, default 5). Falls back to ``text`` key if ``query`` absent.

        Returns:
            Dict with ``query`` and ``papers`` list, each paper containing
            ``title``, ``authors``, ``year``, ``venue``, ``abstract``, ``doi``,
            and ``citations``.
        """
        query: str = input_data.get("query") or input_data.get("text", "")
        if not query:
            query = "general research"

        max_results: int = int(input_data.get("max_results", 5))
        papers = _generate_papers(query, max_results)

        return {
            "query": query,
            "papers": papers,
        }


agent = PaperFinderA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9005)
