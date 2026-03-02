"""Diamond DAG demo — orchestrates all four agents in a branching pipeline.

Topology::

    web_search ──┬──> sentiment_analyzer ──┬──> report_generator
                 └──> doc_summarizer ───────┘

Steps
-----
1. Call ``web-search`` with a fixed query.
2. In parallel: send snippets to ``sentiment_analyzer`` AND ``doc_summarizer``.
3. Merge the parallel results and call ``report_generator``.
4. Print each step's result as pretty JSON.
5. Print the final Markdown report.
6. Print a provenance / timing summary.

Usage:
    python scripts/demo_chain.py

The four agent servers must be running (use ``scripts/run_agent_servers.py``).
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEARCH_QUERY: str = "artificial intelligence trends 2025"

AGENT_URLS: dict[str, str] = {
    "web-search":        "http://localhost:9001",
    "analyze-sentiment": "http://localhost:9002",
    "summarize":         "http://localhost:9003",
    "generate-report":   "http://localhost:9004",
}

RPC_TIMEOUT_SECONDS: float = 30.0


# ---------------------------------------------------------------------------
# Provenance tracking
# ---------------------------------------------------------------------------

@dataclass
class StepRecord:
    """Timing and identity record for one pipeline step.

    Attributes:
        agent: Human-readable agent label.
        skill: Skill ID that was invoked.
        elapsed_ms: Wall-clock duration of the call in milliseconds.
        state: Final task state reported by the agent.
    """

    agent: str
    skill: str
    elapsed_ms: float
    state: str


@dataclass
class Provenance:
    """Accumulated provenance for the full chain run.

    Attributes:
        steps: Ordered list of step records.
        total_elapsed_ms: Wall-clock duration of the entire chain.
    """

    steps: list[StepRecord] = field(default_factory=list)
    total_elapsed_ms: float = 0.0


# ---------------------------------------------------------------------------
# Low-level A2A call
# ---------------------------------------------------------------------------

async def _send_task(
    base_url: str,
    skill_id: str,
    message: str,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    """Send a ``tasks/send`` JSON-RPC request and return the parsed result dict.

    The A2A server wraps the handler's return value as a JSON string inside
    ``result.artifacts[0].parts[0].text``.  This helper unwraps that envelope
    so callers receive the plain handler payload.

    Args:
        base_url: Agent root URL (e.g. ``http://localhost:9001``).
        skill_id: Skill to invoke.
        message: Plain-text or JSON-encoded input for the skill.
        client: Shared ``httpx.AsyncClient`` instance.

    Returns:
        Unwrapped handler result dict.

    Raises:
        httpx.ConnectError: If the agent server is not reachable.
        ValueError: If the JSON-RPC response contains an error or the artifact
            payload cannot be decoded.
    """
    rpc_body: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tasks/send",
        "params": {
            "skill_id": skill_id,
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": message}],
            },
        },
    }

    response = await client.post(
        base_url,
        json=rpc_body,
        headers={"Content-Type": "application/json"},
        timeout=RPC_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    envelope = response.json()
    if "error" in envelope:
        err = envelope["error"]
        raise ValueError(f"A2A RPC error {err.get('code')}: {err.get('message')}")

    task: dict[str, Any] = envelope.get("result", {})
    return _unwrap_artifact(task)


def _unwrap_artifact(task: dict[str, Any]) -> dict[str, Any]:
    """Extract the handler payload from an A2A task dict.

    The server stores the handler's return dict as a JSON string in
    ``artifacts[0].parts[0].text``.  Returns the raw task dict when
    no artifact is present (e.g. on failure).

    Args:
        task: Raw task dict from ``result`` of a ``tasks/send`` response.

    Returns:
        Decoded handler payload dict, or the raw task dict on fallback.
    """
    artifacts: list[dict[str, Any]] = task.get("artifacts", [])
    if not artifacts:
        return task

    parts: list[dict[str, Any]] = artifacts[0].get("parts", [])
    for part in parts:
        if part.get("type") == "text":
            raw_text: str = part.get("text", "")
            try:
                return json.loads(raw_text)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError):
                return {"text": raw_text}

    return task


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

async def step_web_search(
    client: httpx.AsyncClient,
    provenance: Provenance,
) -> dict[str, Any]:
    """Invoke the web-search agent and return its result payload.

    Args:
        client: Shared HTTP client.
        provenance: Provenance collector to record timing into.

    Returns:
        Web-search result dict with ``query``, ``total_results``, and ``results``.
    """
    print("=" * 60)
    print("STEP 1 — Web Search")
    print("=" * 60)
    print(f"Query: {SEARCH_QUERY!r}\n")

    t0 = time.monotonic()
    result = await _send_task(
        base_url=AGENT_URLS["web-search"],
        skill_id="web-search",
        message=json.dumps({"query": SEARCH_QUERY, "num_results": 5}),
        client=client,
    )
    elapsed = (time.monotonic() - t0) * 1000

    provenance.steps.append(
        StepRecord(
            agent="Web Search Agent",
            skill="web-search",
            elapsed_ms=round(elapsed, 1),
            state="completed",
        )
    )

    print(json.dumps(result, indent=2))
    print()
    return result


async def step_sentiment(
    snippets: list[str],
    client: httpx.AsyncClient,
    provenance: Provenance,
) -> dict[str, Any]:
    """Invoke the sentiment-analyzer agent on search snippets.

    Args:
        snippets: List of snippet strings extracted from web-search results.
        client: Shared HTTP client.
        provenance: Provenance collector.

    Returns:
        Sentiment result dict with a ``results`` list.
    """
    print("STEP 2a — Sentiment Analysis")
    print("-" * 40)

    t0 = time.monotonic()
    result = await _send_task(
        base_url=AGENT_URLS["analyze-sentiment"],
        skill_id="analyze-sentiment",
        message=json.dumps({"texts": snippets}),
        client=client,
    )
    elapsed = (time.monotonic() - t0) * 1000

    provenance.steps.append(
        StepRecord(
            agent="Sentiment Analyzer Agent",
            skill="analyze-sentiment",
            elapsed_ms=round(elapsed, 1),
            state="completed",
        )
    )

    print(json.dumps(result, indent=2))
    print()
    return result


async def step_summarize(
    text: str,
    client: httpx.AsyncClient,
    provenance: Provenance,
) -> dict[str, Any]:
    """Invoke the doc-summarizer agent on concatenated search snippets.

    Args:
        text: Concatenated snippet text to summarize.
        client: Shared HTTP client.
        provenance: Provenance collector.

    Returns:
        Summarizer result dict with ``summary``, ``key_points``, and length fields.
    """
    print("STEP 2b — Document Summarization")
    print("-" * 40)

    t0 = time.monotonic()
    result = await _send_task(
        base_url=AGENT_URLS["summarize"],
        skill_id="summarize",
        message=json.dumps({"text": text, "max_sentences": 3}),
        client=client,
    )
    elapsed = (time.monotonic() - t0) * 1000

    provenance.steps.append(
        StepRecord(
            agent="Document Summarizer Agent",
            skill="summarize",
            elapsed_ms=round(elapsed, 1),
            state="completed",
        )
    )

    print(json.dumps(result, indent=2))
    print()
    return result


async def step_report(
    search_result: dict[str, Any],
    sentiment_result: dict[str, Any],
    summary_result: dict[str, Any],
    client: httpx.AsyncClient,
    provenance: Provenance,
) -> dict[str, Any]:
    """Invoke the report-generator agent with merged upstream data.

    Merges all three upstream payloads into a single dict so the report
    generator can detect all three data sources and render the corresponding
    sections (web search, document summary, sentiment analysis).

    Args:
        search_result: Web-search payload.
        sentiment_result: Sentiment-analyzer payload.
        summary_result: Summarizer payload.
        client: Shared HTTP client.
        provenance: Provenance collector.

    Returns:
        Report-generator result dict with a nested ``report`` key.
    """
    print("=" * 60)
    print("STEP 3 — Report Generation")
    print("=" * 60)

    # Merge upstream payloads.  The report generator recognises:
    #   - ``results`` (list with url keys)  → web-search section
    #   - ``summary`` / ``key_points``      → document-summary section
    #   - ``sentiment_results``             → sentiment section
    merged: dict[str, Any] = {
        **search_result,                                       # query, total_results, results
        "summary":           summary_result.get("summary", ""),
        "key_points":        summary_result.get("key_points", []),
        "original_length":   summary_result.get("original_length", 0),
        "summary_length":    summary_result.get("summary_length", 0),
        "sentiment_results": sentiment_result.get("results", []),
        "title":             f"AI Trends Report: {SEARCH_QUERY.title()}",
    }

    t0 = time.monotonic()
    result = await _send_task(
        base_url=AGENT_URLS["generate-report"],
        skill_id="generate-report",
        message=json.dumps(merged),
        client=client,
    )
    elapsed = (time.monotonic() - t0) * 1000

    provenance.steps.append(
        StepRecord(
            agent="Report Generator Agent",
            skill="generate-report",
            elapsed_ms=round(elapsed, 1),
            state="completed",
        )
    )

    return result


# ---------------------------------------------------------------------------
# Provenance display
# ---------------------------------------------------------------------------

def _print_provenance(provenance: Provenance) -> None:
    """Print a formatted provenance / timing table.

    Args:
        provenance: Completed provenance object.
    """
    print("=" * 60)
    print("PROVENANCE SUMMARY")
    print("=" * 60)

    col_agent = 32
    col_skill = 22
    col_ms    = 10
    col_state = 10

    sep = (
        f"+{'-' * col_agent}+{'-' * col_skill}+{'-' * col_ms}+{'-' * col_state}+"
    )
    header = (
        f"| {'Agent':<{col_agent - 2}} "
        f"| {'Skill':<{col_skill - 2}} "
        f"| {'ms':>{col_ms - 2}} "
        f"| {'State':<{col_state - 2}} |"
    )

    print(sep)
    print(header)
    print(sep)
    for step in provenance.steps:
        print(
            f"| {step.agent:<{col_agent - 2}} "
            f"| {step.skill:<{col_skill - 2}} "
            f"| {step.elapsed_ms:>{col_ms - 2}.1f} "
            f"| {step.state:<{col_state - 2}} |"
        )
    print(sep)
    print(
        f"\nTotal wall-clock time: {provenance.total_elapsed_ms:.1f} ms  "
        f"({len(provenance.steps)} agent calls)\n"
    )

    contributing = [s.agent for s in provenance.steps]
    print("Contributing agents (in call order):")
    for i, name in enumerate(contributing, start=1):
        print(f"  {i}. {name}")
    print()


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

async def run_diamond_pipeline() -> None:
    """Execute the full diamond DAG pipeline and print all outputs."""
    provenance = Provenance()
    chain_start = time.monotonic()

    async with httpx.AsyncClient() as client:
        # ── Step 1: Web Search ──────────────────────────────────────
        try:
            search_result = await step_web_search(client, provenance)
        except httpx.ConnectError:
            print(
                "ERROR: Web Search Agent (port 9001) is not reachable.\n"
                "Start all servers first:  python scripts/run_agent_servers.py\n"
            )
            return

        # Extract snippets for the parallel steps
        raw_results: list[dict[str, Any]] = search_result.get("results", [])
        snippets: list[str] = [r["snippet"] for r in raw_results if "snippet" in r]
        combined_text: str = "  ".join(snippets)

        # ── Step 2: Parallel branches ───────────────────────────────
        print("=" * 60)
        print("STEP 2 — Parallel: Sentiment + Summarization")
        print("=" * 60)
        print()

        sentiment_task = step_sentiment(snippets, client, provenance)
        summarize_task  = step_summarize(combined_text, client, provenance)

        try:
            sentiment_result, summary_result = await asyncio.gather(
                sentiment_task,
                summarize_task,
            )
        except httpx.ConnectError as exc:
            print(f"ERROR: A parallel agent is not reachable — {exc}\n")
            return

        # ── Step 3: Report Generation ───────────────────────────────
        try:
            report_result = await step_report(
                search_result=search_result,
                sentiment_result=sentiment_result,
                summary_result=summary_result,
                client=client,
                provenance=provenance,
            )
        except httpx.ConnectError:
            print("ERROR: Report Generator Agent (port 9004) is not reachable.\n")
            return

    provenance.total_elapsed_ms = (time.monotonic() - chain_start) * 1000

    # ── Final report ────────────────────────────────────────────────
    report: dict[str, Any] = report_result.get("report", report_result)
    markdown_content: str = report.get("content", "")

    print()
    print("=" * 60)
    print("FINAL MARKDOWN REPORT")
    print("=" * 60)
    print(markdown_content)
    print()

    _print_provenance(provenance)


def main() -> None:
    """Entry point — run the diamond pipeline and exit."""
    asyncio.run(run_diamond_pipeline())


if __name__ == "__main__":
    main()
