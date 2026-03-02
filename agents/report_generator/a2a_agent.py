"""Report Generator A2A Agent — markdown report composition via the A2A protocol.

Runs on port 9004 and exposes a ``generate-report`` skill. Accepts arbitrary
upstream data (web-search results, summarizer output, sentiment results, or
any combination) and composes a structured Markdown report from it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "generate-report",
        "name": "Generate Report",
        "description": (
            "Compose a structured Markdown report from upstream agent data. "
            "Accepts web-search results, summarizer output, sentiment analysis "
            "results, or any combination of structured inputs."
        ),
        "tags": ["reporting", "markdown", "synthesis", "composition"],
        "examples": [
            '{"title": "AI Market Analysis", "query": "AI industry trends"}',
            '{"results": [...], "summary": "...", "sentiment": [...]}',
        ],
    }
]


def _auto_title(input_data: dict[str, Any]) -> str:
    """Derive a report title from available input fields.

    Checks common keys that upstream agents typically populate.

    Args:
        input_data: Raw input dict from the caller.

    Returns:
        A human-readable title string.
    """
    # Web search agent populates ``query``
    if "query" in input_data:
        return f"Report: {input_data['query'].title()}"
    # Summarizer populates ``summary``
    if "summary" in input_data:
        summary: str = str(input_data["summary"])
        excerpt = summary[:60].rstrip()
        return f"Report: {excerpt}..." if len(summary) > 60 else f"Report: {excerpt}"
    # Arbitrary text key
    if "text" in input_data:
        text: str = str(input_data["text"])
        excerpt = text[:60].rstrip()
        return f"Report: {excerpt}..." if len(text) > 60 else f"Report: {excerpt}"
    return "Generated Report"


def _format_search_section(results_data: dict[str, Any]) -> str:
    """Render a web-search result dict as a Markdown section body.

    Args:
        results_data: Dict as returned by the web-search agent.

    Returns:
        Markdown string with query header and numbered result list.
    """
    query = results_data.get("query", "")
    results: list[dict[str, Any]] = results_data.get("results", [])
    total = results_data.get("total_results", len(results))

    lines: list[str] = []
    if query:
        lines.append(f"**Query:** {query}  ")
        lines.append(f"**Total results:** {total}  ")
        lines.append("")
    for i, r in enumerate(results, start=1):
        title = r.get("title", f"Result {i}")
        url = r.get("url", "")
        snippet = r.get("snippet", "")
        lines.append(f"{i}. **[{title}]({url})**  ")
        if snippet:
            lines.append(f"   {snippet}  ")
        lines.append("")
    return "\n".join(lines)


def _format_sentiment_section(sentiment_data: list[dict[str, Any]]) -> str:
    """Render a list of sentiment results as a Markdown section body.

    Args:
        sentiment_data: List of dicts as returned by the sentiment-analyzer agent.

    Returns:
        Markdown string with a table of text, label, score, and confidence.
    """
    lines: list[str] = ["| Text | Sentiment | Score | Confidence |", "| --- | --- | --- | --- |"]
    for item in sentiment_data:
        text = str(item.get("text", ""))
        excerpt = text[:80].replace("|", "\\|") + ("..." if len(text) > 80 else "")
        label = item.get("sentiment", "neutral")
        score = item.get("score", 0.0)
        confidence = item.get("confidence", 0.0)
        lines.append(f"| {excerpt} | {label} | {score:.4f} | {confidence:.4f} |")
    return "\n".join(lines)


def _format_summary_section(summary_data: dict[str, Any]) -> str:
    """Render a summarizer output dict as a Markdown section body.

    Args:
        summary_data: Dict as returned by the doc-summarizer agent.

    Returns:
        Markdown string with the summary text and key points bullet list.
    """
    summary = summary_data.get("summary", "")
    key_points: list[str] = summary_data.get("key_points", [])
    orig_len = summary_data.get("original_length", 0)
    summ_len = summary_data.get("summary_length", 0)

    lines: list[str] = []
    if summary:
        lines.append(summary)
        lines.append("")
    if orig_len or summ_len:
        lines.append(f"*Original: {orig_len} words → Summary: {summ_len} words*  ")
        lines.append("")
    if key_points:
        lines.append("**Key terms:** " + ", ".join(key_points))
    return "\n".join(lines)


def _compose_report(title: str, input_data: dict[str, Any]) -> dict[str, Any]:
    """Build a complete Markdown report from structured upstream data.

    Detects which upstream agents contributed data and creates a tailored
    section for each. Falls back to a generic data dump when the schema is
    unrecognised.

    Args:
        title: Report title string.
        input_data: Merged dict from all upstream agent outputs.

    Returns:
        Dict with ``title``, ``format``, ``content``, ``sections``, and
        ``generated_at`` keys.
    """
    generated_at = datetime.now(tz=timezone.utc).isoformat()

    # Detect upstream data types
    has_search = "results" in input_data and isinstance(input_data.get("results"), list)
    # Distinguish search results (list of dicts with title/url) from sentiment results
    raw_results: list[Any] = input_data.get("results", [])
    is_search_results = has_search and all(
        isinstance(r, dict) and "url" in r for r in raw_results
    )
    is_sentiment_results = has_search and all(
        isinstance(r, dict) and "sentiment" in r for r in raw_results
    )

    has_summary = "summary" in input_data and isinstance(input_data.get("summary"), str)
    has_key_points = "key_points" in input_data

    # Also handle direct sentiment_results wrapper key from orchestrators
    sentiment_list: list[dict[str, Any]] | None = None
    if "sentiment_results" in input_data and isinstance(input_data["sentiment_results"], list):
        sentiment_list = input_data["sentiment_results"]
    elif is_sentiment_results:
        sentiment_list = raw_results  # type: ignore[assignment]

    sections_used: list[str] = []
    body_parts: list[str] = []

    # ── Executive Summary ────────────────────────────────────────
    sections_used.append("Executive Summary")
    exec_lines: list[str] = [f"# {title}", "", "## Executive Summary", ""]

    source_labels: list[str] = []
    if is_search_results:
        query = input_data.get("query", "")
        label = f"web search results for **{query}**" if query else "web search results"
        source_labels.append(label)
    if has_summary:
        source_labels.append("document summarization")
    if sentiment_list is not None:
        source_labels.append("sentiment analysis")

    if source_labels:
        exec_lines.append(
            f"This report synthesises data from: {', '.join(source_labels)}. "
            "Key findings are presented in the sections below."
        )
    else:
        exec_lines.append(
            "This report presents an analysis of the supplied data. "
            "Refer to individual sections for detailed findings."
        )
    exec_lines.append("")
    body_parts.append("\n".join(exec_lines))

    # ── Data Sources ─────────────────────────────────────────────
    sections_used.append("Data Sources")
    ds_lines: list[str] = ["## Data Sources", ""]
    data_keys = [k for k in input_data if k not in {"title"}]
    if data_keys:
        for key in data_keys:
            value = input_data[key]
            type_label = type(value).__name__
            ds_lines.append(f"- `{key}` ({type_label})")
    else:
        ds_lines.append("- No structured data sources detected.")
    ds_lines.append("")
    body_parts.append("\n".join(ds_lines))

    # ── Analysis ─────────────────────────────────────────────────
    sections_used.append("Analysis")
    analysis_lines: list[str] = ["## Analysis", ""]

    if is_search_results:
        analysis_lines.append("### Web Search Results")
        analysis_lines.append("")
        analysis_lines.append(_format_search_section(input_data))

    if has_summary or has_key_points:
        analysis_lines.append("### Document Summary")
        analysis_lines.append("")
        summary_data = {
            "summary": input_data.get("summary", ""),
            "key_points": input_data.get("key_points", []),
            "original_length": input_data.get("original_length", 0),
            "summary_length": input_data.get("summary_length", 0),
        }
        analysis_lines.append(_format_summary_section(summary_data))
        analysis_lines.append("")

    if sentiment_list is not None:
        analysis_lines.append("### Sentiment Analysis")
        analysis_lines.append("")
        analysis_lines.append(_format_sentiment_section(sentiment_list))
        analysis_lines.append("")

    if not (is_search_results or has_summary or has_key_points or sentiment_list is not None):
        # Generic data dump
        try:
            pretty = json.dumps(input_data, indent=2, default=str)
        except (TypeError, ValueError):
            pretty = str(input_data)
        analysis_lines.append("```json")
        analysis_lines.append(pretty)
        analysis_lines.append("```")
        analysis_lines.append("")

    body_parts.append("\n".join(analysis_lines))

    # ── Key Findings ──────────────────────────────────────────────
    sections_used.append("Key Findings")
    findings_lines: list[str] = ["## Key Findings", ""]

    if is_search_results:
        num_results = len(raw_results)
        findings_lines.append(f"- Retrieved **{num_results}** web search results.")
        if raw_results:
            top_title = raw_results[0].get("title", "")
            findings_lines.append(f"- Top result: *{top_title}*")

    if has_key_points:
        kp: list[str] = input_data.get("key_points", [])
        if kp:
            findings_lines.append(f"- Key terms identified: {', '.join(kp)}")

    if has_summary:
        orig = input_data.get("original_length", 0)
        summ = input_data.get("summary_length", 0)
        if orig > 0 and summ > 0:
            ratio = round(summ / orig * 100, 1)
            findings_lines.append(
                f"- Document compressed from {orig} to {summ} words ({ratio}% of original)."
            )

    if sentiment_list is not None:
        pos = sum(1 for r in sentiment_list if r.get("sentiment") == "positive")
        neg = sum(1 for r in sentiment_list if r.get("sentiment") == "negative")
        neu = sum(1 for r in sentiment_list if r.get("sentiment") == "neutral")
        findings_lines.append(
            f"- Sentiment breakdown: {pos} positive, {neg} negative, {neu} neutral."
        )
        if sentiment_list:
            avg_score = sum(float(r.get("score", 0)) for r in sentiment_list) / len(sentiment_list)
            findings_lines.append(f"- Average sentiment score: {avg_score:.4f}")

    if len(findings_lines) == 2:  # only header + blank
        findings_lines.append("- Report generated from supplied input data.")

    findings_lines.append("")
    body_parts.append("\n".join(findings_lines))

    # ── Conclusion ────────────────────────────────────────────────
    sections_used.append("Conclusion")
    conclusion_lines: list[str] = [
        "## Conclusion",
        "",
        f"This report was automatically composed at `{generated_at}` by the "
        "AgentChains Report Generator. All data was provided by upstream agents "
        "in the processing pipeline. Review individual sections for full details.",
        "",
        "---",
        f"*Generated by AgentChains Report Generator v0.1.0 · {generated_at}*",
    ]
    body_parts.append("\n".join(conclusion_lines))

    content = "\n\n".join(body_parts)

    return {
        "title": title,
        "format": "markdown",
        "content": content,
        "sections": sections_used,
        "generated_at": generated_at,
    }


class ReportGeneratorA2AAgent(BaseA2AAgent):
    """A2A agent that composes structured Markdown reports from upstream data.

    The ``generate-report`` skill accepts arbitrary structured inputs — typically
    the merged outputs of a web-search, summarizer, and sentiment-analyzer agent —
    and produces a complete Markdown document with standard sections.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Report Generator Agent",
            description=(
                "Composes structured Markdown reports from upstream agent data. "
                "Handles web-search results, document summaries, and sentiment "
                "analysis output. Designed as the final step in a multi-agent chain."
            ),
            port=9004,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming report-generation request.

        Args:
            skill_id: Must be ``generate-report``.
            input_data: Arbitrary dict. Optional ``title`` key overrides the
                auto-generated title. All other keys are treated as upstream data.

        Returns:
            Dict with a ``report`` key containing ``title``, ``format``,
            ``content``, ``sections``, and ``generated_at``.
        """
        title: str = input_data.get("title") or _auto_title(input_data)
        report = _compose_report(title, input_data)
        return {"report": report}


agent = ReportGeneratorA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9004)
