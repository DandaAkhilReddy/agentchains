"""Agent registry — central catalog of all 16 A2A agents.

Maps agent names to their runtime metadata: port, module path, skills,
category, and a human-readable description sourced directly from each
agent's docstring.  Use the utility functions below to look up agents
rather than accessing AGENTS directly.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Canonical catalog
# ---------------------------------------------------------------------------

AGENTS: dict[str, dict[str, Any]] = {
    # ── Data agents ──────────────────────────────────────────────────────
    "web_search": {
        "name": "Web Search Agent",
        "port": 9001,
        "module": "agents.web_search_agent.a2a_agent",
        "skills": ["web-search"],
        "category": "data",
        "description": (
            "Performs simulated web searches and returns structured results "
            "with titles, URLs, and snippets. Suitable for chaining as a "
            "data-gathering step before summarization or report generation."
        ),
    },
    "paper_finder": {
        "name": "Paper Finder Agent",
        "port": 9005,
        "module": "agents.paper_finder_agent.a2a_agent",
        "skills": ["find-papers"],
        "category": "data",
        "description": (
            "Searches a mock academic database and returns structured paper "
            "records including titles, authors, abstracts, DOIs, and citation "
            "counts. Results are deterministic and suitable for pipeline testing."
        ),
    },
    "data_enricher": {
        "name": "Data Enricher Agent",
        "port": 9006,
        "module": "agents.data_enricher_agent.a2a_agent",
        "skills": ["enrich-data"],
        "category": "data",
        "description": (
            "Parses and enriches URLs with domain metadata, path components, "
            "query parameters, content-type guesses, and category labels "
            "(documentation, news, social, research, general). Accepts URL "
            "lists, single URLs, or free-form text containing URLs."
        ),
    },
    # ── Analysis agents ───────────────────────────────────────────────────
    "sentiment_analyzer": {
        "name": "Sentiment Analyzer Agent",
        "port": 9002,
        "module": "agents.sentiment_analyzer.a2a_agent",
        "skills": ["analyze-sentiment"],
        "category": "analysis",
        "description": (
            "Keyword-based sentiment analysis for one or more text inputs. "
            "Returns positive/negative/neutral labels with numeric scores in "
            "[-1, 1] and confidence values. Designed for pipeline integration."
        ),
    },
    "text_classifier": {
        "name": "Text Classifier Agent",
        "port": 9010,
        "module": "agents.text_classifier_agent.a2a_agent",
        "skills": ["classify-text"],
        "category": "analysis",
        "description": (
            "TF-IDF-inspired keyword scoring classifier. Accepts text and an "
            "optional list of target categories, scores each by keyword "
            "frequency normalised by document length, and returns top-3 "
            "category matches with confidence scores."
        ),
    },
    "ner_extractor": {
        "name": "NER Extractor Agent",
        "port": 9011,
        "module": "agents.ner_extractor_agent.a2a_agent",
        "skills": ["extract-entities"],
        "category": "analysis",
        "description": (
            "Regex-based named entity recognition. Identifies PERSON, "
            "ORGANIZATION, DATE, EMAIL, PHONE, URL, MONEY, and PERCENTAGE "
            "entities within a text string, returning typed entity lists and "
            "per-type counts."
        ),
    },
    "readability_scorer": {
        "name": "Readability Scorer Agent",
        "port": 9012,
        "module": "agents.readability_scorer_agent.a2a_agent",
        "skills": ["score-readability"],
        "category": "analysis",
        "description": (
            "Computes Flesch Reading Ease and Flesch-Kincaid Grade Level for "
            "text, along with sentence, word, and syllable statistics and a "
            "human-readable grade label (e.g. 'College', 'High School')."
        ),
    },
    # ── Transform agents ──────────────────────────────────────────────────
    "doc_summarizer": {
        "name": "Document Summarizer Agent",
        "port": 9003,
        "module": "agents.doc_summarizer_agent.a2a_agent",
        "skills": ["summarize"],
        "category": "transform",
        "description": (
            "Extractive summarization of text documents using word-frequency "
            "scoring. Returns a summary, key points, and length metadata "
            "(original vs. summary word count). Designed for pipeline "
            "integration before report generation."
        ),
    },
    "language_detector": {
        "name": "Language Detector Agent",
        "port": 9007,
        "module": "agents.language_detector_agent.a2a_agent",
        "skills": ["detect-language"],
        "category": "transform",
        "description": (
            "Detects the natural language and writing script of one or more "
            "text strings using trigram frequency analysis and Unicode block "
            "detection. Returns BCP-47 language codes, script names, and "
            "confidence scores."
        ),
    },
    "json_normalizer": {
        "name": "JSON Normalizer Agent",
        "port": 9008,
        "module": "agents.json_normalizer_agent.a2a_agent",
        "skills": ["normalize-json"],
        "category": "transform",
        "description": (
            "Flattens arbitrary nested JSON dicts or lists to dot-notation "
            "keys, optionally filtering to a requested field set. Returns the "
            "flat representation alongside structural metadata such as depth, "
            "key count, and array presence."
        ),
    },
    "message_translator": {
        "name": "Message Translator Agent",
        "port": 9009,
        "module": "agents.message_translator_agent.a2a_agent",
        "skills": ["translate"],
        "category": "transform",
        "description": (
            "Dictionary-based word-for-word translation from English to a "
            "target language (default Spanish). Unsupported language pairs "
            "pass through unchanged with an explanatory note. Designed for "
            "lightweight localisation tasks in pipelines."
        ),
    },
    # ── Compliance agents ─────────────────────────────────────────────────
    "pii_redactor": {
        "name": "PII Redactor Agent",
        "port": 9013,
        "module": "agents.pii_redactor_agent.a2a_agent",
        "skills": ["redact-pii"],
        "category": "compliance",
        "description": (
            "Regex-based PII detection and redaction. Handles emails, phone "
            "numbers, SSNs, credit card numbers, IPv4 addresses, and "
            "date-of-birth patterns. Returns redacted text and per-type "
            "redaction counts for audit purposes."
        ),
    },
    "schema_validator": {
        "name": "Schema Validator Agent",
        "port": 9014,
        "module": "agents.schema_validator_agent.a2a_agent",
        "skills": ["validate-schema"],
        "category": "compliance",
        "description": (
            "Recursive JSON Schema validator supporting type, required, "
            "properties, items, minimum, maximum, minLength, maxLength, "
            "pattern, and enum keywords. Collects all validation errors "
            "rather than failing fast; returns a validity flag and full "
            "error report."
        ),
    },
    # ── Output agents ─────────────────────────────────────────────────────
    "report_generator": {
        "name": "Report Generator Agent",
        "port": 9004,
        "module": "agents.report_generator.a2a_agent",
        "skills": ["generate-report"],
        "category": "output",
        "description": (
            "Composes structured Markdown reports from upstream agent data. "
            "Handles web-search results, document summaries, sentiment "
            "analysis output, entity lists, and text classifications. "
            "Designed as the final sink in a multi-agent chain."
        ),
    },
    "tag_generator": {
        "name": "Tag Generator Agent",
        "port": 9015,
        "module": "agents.tag_generator_agent.a2a_agent",
        "skills": ["generate-tags"],
        "category": "output",
        "description": (
            "TF-IDF-inspired keyword and bigram extraction from text. Scores "
            "candidate tags by frequency weighted by inverse word length, "
            "and includes repeated two-word phrases. Returns top-N scored "
            "tags suitable for content tagging and search indexing."
        ),
    },
    "headline_generator": {
        "name": "Headline Generator Agent",
        "port": 9016,
        "module": "agents.headline_generator_agent.a2a_agent",
        "skills": ["generate-headline"],
        "category": "output",
        "description": (
            "Extractive headline generation from text without an LLM. Scores "
            "candidates using first-sentence extraction, named-entity "
            "detection, and topic-word frequency. Supports news, academic, "
            "and casual style options with configurable max length."
        ),
    },
}

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def get_agent(name: str) -> dict[str, Any] | None:
    """Return the registry entry for a named agent, or None if not found.

    Args:
        name: The agent key as defined in AGENTS (e.g. ``"web_search"``).

    Returns:
        A copy of the agent metadata dict, or ``None`` when the name is not
        registered.
    """
    entry = AGENTS.get(name)
    if entry is None:
        return None
    return {"key": name, **entry}


def get_agents_by_category(category: str) -> list[dict[str, Any]]:
    """Return all agents belonging to a given category.

    Args:
        category: One of ``"data"``, ``"analysis"``, ``"transform"``,
            ``"compliance"``, or ``"output"``.

    Returns:
        List of agent metadata dicts (each augmented with a ``"key"`` field)
        whose ``"category"`` matches the requested value. Empty list when
        no agents match.
    """
    return [
        {"key": name, **entry}
        for name, entry in AGENTS.items()
        if entry["category"] == category
    ]


def get_agent_url(name: str) -> str:
    """Build the local base URL for a named agent.

    Args:
        name: The agent key as defined in AGENTS (e.g. ``"web_search"``).

    Returns:
        URL string of the form ``http://localhost:<port>``.

    Raises:
        KeyError: If *name* is not found in the registry.
    """
    entry = AGENTS[name]
    return f"http://localhost:{entry['port']}"


def list_all_agents() -> list[dict[str, Any]]:
    """Return metadata for every registered agent.

    Returns:
        List of all agent metadata dicts, each augmented with a ``"key"``
        field containing the agent's registry key. Order follows the
        insertion order of AGENTS.
    """
    return [{"key": name, **entry} for name, entry in AGENTS.items()]
