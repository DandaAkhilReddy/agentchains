"""Seed pre-built chain templates into the AgentChains marketplace.

Defines five canonical chain templates as valid DAG graph_json documents and
optionally publishes them to the marketplace API via an authenticated agent.

Usage
-----
Print templates only (no network calls)::

    python scripts/seed_chain_templates.py

Publish to a running marketplace (requires SEED_AGENT_TOKEN env var)::

    SEED_AGENT_TOKEN=<jwt> python scripts/seed_chain_templates.py --publish

The script exits 0 on success, 1 if any publish call fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

# Allow running from repo root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE_URL = "http://localhost:8000/api/v5"

# ---------------------------------------------------------------------------
# Template graph_json definitions
# ---------------------------------------------------------------------------
# Each graph_json follows the orchestration engine's expected format:
#
#   {
#     "nodes": {
#       "<node_id>": {
#         "type": "agent_call",
#         "config": {
#           "agent_id": "<placeholder>",
#           "skill_id": "<skill-name>"
#         },
#         "depends_on": ["<dep_node_id>", ...]
#       }
#     },
#     "edges": []
#   }
#
# agent_id values are set to the agent's registry key (e.g. "web_search")
# as placeholders.  When a creator publishes a chain they replace these with
# the real marketplace agent UUIDs.
# ---------------------------------------------------------------------------


def _graph(nodes: dict[str, dict[str, Any]]) -> str:
    """Serialise a nodes dict to a canonical graph_json string.

    Args:
        nodes: Mapping of node_id to node definition dicts.  Each definition
            must contain ``type``, ``config``, and ``depends_on`` keys.

    Returns:
        JSON string representing the full graph with an empty ``edges`` list.
    """
    return json.dumps({"nodes": nodes, "edges": []}, indent=2)


# ── 1. Research Pipeline ──────────────────────────────────────────────────
# paper_finder → doc_summarizer → sentiment_analyzer → report_generator
_RESEARCH_PIPELINE_GRAPH = _graph(
    {
        "find_papers": {
            "type": "agent_call",
            "config": {
                "agent_id": "paper_finder",
                "skill_id": "find-papers",
            },
            "depends_on": [],
        },
        "summarize_papers": {
            "type": "agent_call",
            "config": {
                "agent_id": "doc_summarizer",
                "skill_id": "summarize",
            },
            "depends_on": ["find_papers"],
        },
        "analyze_sentiment": {
            "type": "agent_call",
            "config": {
                "agent_id": "sentiment_analyzer",
                "skill_id": "analyze-sentiment",
            },
            "depends_on": ["summarize_papers"],
        },
        "generate_report": {
            "type": "agent_call",
            "config": {
                "agent_id": "report_generator",
                "skill_id": "generate-report",
            },
            "depends_on": ["analyze_sentiment"],
        },
    }
)

# ── 2. Content Localization ───────────────────────────────────────────────
# web_search → language_detector → message_translator → doc_summarizer
_CONTENT_LOCALIZATION_GRAPH = _graph(
    {
        "search_content": {
            "type": "agent_call",
            "config": {
                "agent_id": "web_search",
                "skill_id": "web-search",
            },
            "depends_on": [],
        },
        "detect_language": {
            "type": "agent_call",
            "config": {
                "agent_id": "language_detector",
                "skill_id": "detect-language",
            },
            "depends_on": ["search_content"],
        },
        "translate_content": {
            "type": "agent_call",
            "config": {
                "agent_id": "message_translator",
                "skill_id": "translate",
            },
            "depends_on": ["detect_language"],
        },
        "summarize_translation": {
            "type": "agent_call",
            "config": {
                "agent_id": "doc_summarizer",
                "skill_id": "summarize",
            },
            "depends_on": ["translate_content"],
        },
    }
)

# ── 3. Data Quality ───────────────────────────────────────────────────────
# data_enricher → json_normalizer → schema_validator → report_generator
_DATA_QUALITY_GRAPH = _graph(
    {
        "enrich_urls": {
            "type": "agent_call",
            "config": {
                "agent_id": "data_enricher",
                "skill_id": "enrich-data",
            },
            "depends_on": [],
        },
        "normalize_json": {
            "type": "agent_call",
            "config": {
                "agent_id": "json_normalizer",
                "skill_id": "normalize-json",
            },
            "depends_on": ["enrich_urls"],
        },
        "validate_schema": {
            "type": "agent_call",
            "config": {
                "agent_id": "schema_validator",
                "skill_id": "validate-schema",
            },
            "depends_on": ["normalize_json"],
        },
        "generate_quality_report": {
            "type": "agent_call",
            "config": {
                "agent_id": "report_generator",
                "skill_id": "generate-report",
            },
            "depends_on": ["validate_schema"],
        },
    }
)

# ── 4. Content Analysis ───────────────────────────────────────────────────
# web_search → [ner_extractor, sentiment_analyzer, text_classifier]
#            → tag_generator → report_generator
#
# The three analysis nodes run in parallel (all depend on search, none on each
# other). tag_generator fans in from all three.
_CONTENT_ANALYSIS_GRAPH = _graph(
    {
        "search_content": {
            "type": "agent_call",
            "config": {
                "agent_id": "web_search",
                "skill_id": "web-search",
            },
            "depends_on": [],
        },
        "extract_entities": {
            "type": "agent_call",
            "config": {
                "agent_id": "ner_extractor",
                "skill_id": "extract-entities",
            },
            "depends_on": ["search_content"],
        },
        "analyze_sentiment": {
            "type": "agent_call",
            "config": {
                "agent_id": "sentiment_analyzer",
                "skill_id": "analyze-sentiment",
            },
            "depends_on": ["search_content"],
        },
        "classify_text": {
            "type": "agent_call",
            "config": {
                "agent_id": "text_classifier",
                "skill_id": "classify-text",
            },
            "depends_on": ["search_content"],
        },
        "generate_tags": {
            "type": "agent_call",
            "config": {
                "agent_id": "tag_generator",
                "skill_id": "generate-tags",
            },
            "depends_on": ["extract_entities", "analyze_sentiment", "classify_text"],
        },
        "generate_report": {
            "type": "agent_call",
            "config": {
                "agent_id": "report_generator",
                "skill_id": "generate-report",
            },
            "depends_on": ["generate_tags"],
        },
    }
)

# ── 5. Privacy Compliance ─────────────────────────────────────────────────
# ner_extractor → pii_redactor → schema_validator → report_generator
_PRIVACY_COMPLIANCE_GRAPH = _graph(
    {
        "extract_entities": {
            "type": "agent_call",
            "config": {
                "agent_id": "ner_extractor",
                "skill_id": "extract-entities",
            },
            "depends_on": [],
        },
        "redact_pii": {
            "type": "agent_call",
            "config": {
                "agent_id": "pii_redactor",
                "skill_id": "redact-pii",
            },
            "depends_on": ["extract_entities"],
        },
        "validate_output": {
            "type": "agent_call",
            "config": {
                "agent_id": "schema_validator",
                "skill_id": "validate-schema",
            },
            "depends_on": ["redact_pii"],
        },
        "generate_compliance_report": {
            "type": "agent_call",
            "config": {
                "agent_id": "report_generator",
                "skill_id": "generate-report",
            },
            "depends_on": ["validate_output"],
        },
    }
)

# ---------------------------------------------------------------------------
# Template manifest
# ---------------------------------------------------------------------------

CHAIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Research Pipeline",
        "description": (
            "Searches academic databases for papers on a topic, "
            "produces an extractive summary of the findings, runs sentiment "
            "analysis on the summarized text, and composes a final Markdown "
            "report.  Ideal for literature reviews and competitive intelligence."
        ),
        "category": "research",
        "tags": ["research", "academic", "summarization", "sentiment", "report"],
        "graph_json": _RESEARCH_PIPELINE_GRAPH,
        "max_budget_usd": 0.10,
    },
    {
        "name": "Content Localization",
        "description": (
            "Fetches web content on a topic, detects the source language, "
            "translates it to the target language, then summarizes the "
            "translated text. Useful for monitoring foreign-language news and "
            "research sources."
        ),
        "category": "localization",
        "tags": ["localization", "translation", "language", "web-search", "summarization"],
        "graph_json": _CONTENT_LOCALIZATION_GRAPH,
        "max_budget_usd": 0.05,
    },
    {
        "name": "Data Quality",
        "description": (
            "Enriches a set of URLs with domain metadata, normalizes the "
            "enriched records to flat dot-notation JSON, validates the "
            "structure against a JSON Schema, and generates a data-quality "
            "report.  Suitable for data pipeline validation and auditing."
        ),
        "category": "data-quality",
        "tags": ["data-quality", "enrichment", "normalization", "validation", "compliance"],
        "graph_json": _DATA_QUALITY_GRAPH,
        "max_budget_usd": 0.05,
    },
    {
        "name": "Content Analysis",
        "description": (
            "Searches the web for content on a topic, then runs three "
            "parallel analysis agents (NER extraction, sentiment analysis, "
            "text classification) whose results are merged into keyword tags "
            "before a final report is generated.  Good for content auditing "
            "and market research."
        ),
        "category": "analysis",
        "tags": ["analysis", "ner", "sentiment", "classification", "tagging", "report"],
        "graph_json": _CONTENT_ANALYSIS_GRAPH,
        "max_budget_usd": 0.15,
    },
    {
        "name": "Privacy Compliance",
        "description": (
            "Extracts named entities from raw text, redacts any personally "
            "identifiable information found, validates the redacted output "
            "against a compliance schema, and produces a detailed compliance "
            "report.  Designed for GDPR / HIPAA readiness workflows."
        ),
        "category": "compliance",
        "tags": ["compliance", "pii", "redaction", "privacy", "gdpr", "hipaa"],
        "graph_json": _PRIVACY_COMPLIANCE_GRAPH,
        "max_budget_usd": 0.05,
    },
]


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------


def _print_templates() -> None:
    """Pretty-print all chain template definitions to stdout."""
    separator = "=" * 72
    for idx, tmpl in enumerate(CHAIN_TEMPLATES, start=1):
        print(f"\n{separator}")
        print(f"  Template {idx}: {tmpl['name']}")
        print(separator)
        print(f"  Category   : {tmpl['category']}")
        print(f"  Max budget : ${tmpl['max_budget_usd']:.2f} USD")
        print(f"  Tags       : {', '.join(tmpl['tags'])}")
        print(f"\n  Description:\n    {tmpl['description']}\n")
        print("  Graph JSON:")
        # Re-indent graph for readability with two extra spaces
        graph = json.loads(tmpl["graph_json"])
        pretty = json.dumps(graph, indent=4)
        for line in pretty.splitlines():
            print(f"    {line}")
    print(f"\n{separator}\n")


# ---------------------------------------------------------------------------
# Publish helpers
# ---------------------------------------------------------------------------


async def _publish_templates(token: str) -> int:
    """POST each template to the chain-templates endpoint.

    Args:
        token: Bearer JWT token for an agent that has T2 trust or higher.

    Returns:
        Exit code: 0 if all succeeded, 1 if any failed.
    """
    headers = {"Authorization": f"Bearer {token}"}
    exit_code = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for tmpl in CHAIN_TEMPLATES:
            payload = {
                "name": tmpl["name"],
                "description": tmpl["description"],
                "category": tmpl["category"],
                "graph_json": tmpl["graph_json"],
                "tags": tmpl["tags"],
                "max_budget_usd": tmpl["max_budget_usd"],
            }
            resp = await client.post(
                f"{BASE_URL}/chain-templates",
                json=payload,
                headers=headers,
            )
            if resp.status_code == 201:
                data = resp.json()
                print(
                    f"  [OK] Published '{tmpl['name']}' "
                    f"(id: {data.get('id', '?')[:8]}...)"
                )
            else:
                print(
                    f"  [FAIL] '{tmpl['name']}' — "
                    f"HTTP {resp.status_code}: {resp.text[:120]}"
                )
                exit_code = 1

    return exit_code


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list to parse (defaults to ``sys.argv[1:]``).

    Returns:
        Parsed namespace with a ``publish`` boolean attribute.
    """
    parser = argparse.ArgumentParser(
        description="Print and optionally publish AgentChains seed chain templates.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        default=False,
        help=(
            "Publish templates to the marketplace API. "
            "Requires SEED_AGENT_TOKEN environment variable."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"Base URL for the marketplace API (default: {BASE_URL})",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    """Run the seed script.

    Args:
        argv: Optional argument list for testing; defaults to ``sys.argv[1:]``.

    Returns:
        Exit code (0 = success, 1 = at least one publish failure).
    """
    args = _parse_args(argv)

    print(f"\n=== AgentChains — Seed Chain Templates ({len(CHAIN_TEMPLATES)} templates) ===")
    _print_templates()

    if not args.publish:
        print("Tip: pass --publish to register templates with the marketplace API.\n")
        return 0

    token = os.environ.get("SEED_AGENT_TOKEN", "")
    if not token:
        print(
            "ERROR: SEED_AGENT_TOKEN environment variable is required for --publish.\n"
            "       Set it to a valid agent JWT token with T2 trust or higher.",
            file=sys.stderr,
        )
        return 1

    # Allow base URL override from CLI
    global BASE_URL  # noqa: PLW0603
    BASE_URL = args.base_url

    print(f"Publishing to {BASE_URL} ...\n")
    exit_code = await _publish_templates(token)

    if exit_code == 0:
        print(f"\nAll {len(CHAIN_TEMPLATES)} templates published successfully.")
    else:
        print("\nSome templates failed to publish — see errors above.", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
