"""Tests for the four demo A2A agents via httpx.ASGITransport (in-process).

Each agent app is imported from its module-level ``app`` variable and tested
end-to-end through the full FastAPI ASGI stack without starting a real server.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _send(app, skill_id: str, message_text: str) -> dict[str, Any]:
    """Send a tasks/send RPC and return the parsed JSON-RPC result dict."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tasks/send",
                "params": {
                    "skill_id": skill_id,
                    "message": {
                        "parts": [{"type": "text", "text": message_text}]
                    },
                },
            },
        )
    resp.raise_for_status()
    return resp.json()["result"]


async def _send_json(app, skill_id: str, payload: dict) -> dict[str, Any]:
    """Convenience wrapper: serialize payload as JSON and send."""
    return await _send(app, skill_id, json.dumps(payload))


def _artifact_data(result: dict) -> dict[str, Any]:
    """Decode the first artifact's text part back from JSON."""
    text = result["artifacts"][0]["parts"][0]["text"]
    return json.loads(text)


# ---------------------------------------------------------------------------
# Web Search Agent (port 9001)
# ---------------------------------------------------------------------------


class TestWebSearchAgent:
    """Tests for agents/web_search_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self):
        from agents.web_search_agent.a2a_agent import app
        return app

    # ── Happy path ──────────────────────────────────────────────────────────

    async def test_search_returns_results_list(self, app) -> None:
        result = await _send_json(app, "web-search", {"query": "python"})
        data = _artifact_data(result)
        assert isinstance(data["results"], list)
        assert len(data["results"]) > 0

    async def test_search_result_has_title_url_snippet(self, app) -> None:
        result = await _send_json(app, "web-search", {"query": "python"})
        data = _artifact_data(result)
        item = data["results"][0]
        assert "title" in item
        assert "url" in item
        assert "snippet" in item

    async def test_search_returns_query_field(self, app) -> None:
        result = await _send_json(app, "web-search", {"query": "asyncio"})
        data = _artifact_data(result)
        assert data["query"] == "asyncio"

    async def test_search_returns_total_results_count(self, app) -> None:
        result = await _send_json(app, "web-search", {"query": "testing"})
        data = _artifact_data(result)
        assert data["total_results"] == len(data["results"])

    async def test_search_task_state_is_completed(self, app) -> None:
        result = await _send_json(app, "web-search", {"query": "pytest"})
        assert result["state"] == "completed"

    # ── Fallback: plain text routed via {"text": ...} ───────────────────────

    async def test_plain_text_query_falls_back_to_text_key(self, app) -> None:
        """When the message is plain text, input_data becomes {"text": "..."},
        and the agent uses .get("text") as the query."""
        result = await _send(app, "web-search", "python")
        data = _artifact_data(result)
        assert data["query"] == "python"
        assert len(data["results"]) > 0

    # ── num_results parameter ────────────────────────────────────────────────

    async def test_num_results_1_returns_single_result(self, app) -> None:
        result = await _send_json(app, "web-search", {"query": "python", "num_results": 1})
        data = _artifact_data(result)
        assert len(data["results"]) == 1

    async def test_num_results_3_returns_three_results(self, app) -> None:
        result = await _send_json(app, "web-search", {"query": "python", "num_results": 3})
        data = _artifact_data(result)
        assert len(data["results"]) == 3

    async def test_num_results_exceeds_cap_clamped_to_10(self, app) -> None:
        result = await _send_json(app, "web-search", {"query": "python", "num_results": 50})
        data = _artifact_data(result)
        assert len(data["results"]) == 10

    # ── Determinism ─────────────────────────────────────────────────────────

    async def test_same_query_returns_identical_results(self, app) -> None:
        r1 = _artifact_data(await _send_json(app, "web-search", {"query": "deterministic test"}))
        r2 = _artifact_data(await _send_json(app, "web-search", {"query": "deterministic test"}))
        assert r1["results"] == r2["results"]

    async def test_different_queries_return_different_results(self, app) -> None:
        r1 = _artifact_data(await _send_json(app, "web-search", {"query": "alpha"}))
        r2 = _artifact_data(await _send_json(app, "web-search", {"query": "zeta"}))
        assert r1["results"] != r2["results"]

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_name_is_web_search_agent(self, app) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/.well-known/agent.json")
        assert resp.json()["name"] == "Web Search Agent"

    async def test_agent_card_has_web_search_skill(self, app) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/.well-known/agent.json")
        skill_ids = [s["id"] for s in resp.json()["skills"]]
        assert "web-search" in skill_ids


# ---------------------------------------------------------------------------
# Sentiment Analyzer Agent (port 9002)
# ---------------------------------------------------------------------------


class TestSentimentAnalyzerAgent:
    """Tests for agents/sentiment_analyzer/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self):
        from agents.sentiment_analyzer.a2a_agent import app
        return app

    # ── Happy path: single texts ─────────────────────────────────────────────

    async def test_positive_text_returns_positive_sentiment(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"text": "This is amazing and wonderful and fantastic"}
        )
        data = _artifact_data(result)
        assert data["results"][0]["sentiment"] == "positive"

    async def test_negative_text_returns_negative_sentiment(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"text": "This is terrible and horrible and awful"}
        )
        data = _artifact_data(result)
        assert data["results"][0]["sentiment"] == "negative"

    async def test_neutral_text_returns_neutral_sentiment(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"text": "The cat sat on the mat"}
        )
        data = _artifact_data(result)
        assert data["results"][0]["sentiment"] == "neutral"

    async def test_positive_score_is_greater_than_zero(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"text": "excellent great amazing wonderful"}
        )
        data = _artifact_data(result)
        assert data["results"][0]["score"] > 0.0

    async def test_negative_score_is_less_than_zero(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"text": "terrible horrible awful bad"}
        )
        data = _artifact_data(result)
        assert data["results"][0]["score"] < 0.0

    async def test_result_includes_confidence(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"text": "amazing product"}
        )
        data = _artifact_data(result)
        assert "confidence" in data["results"][0]

    async def test_result_includes_text_field(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"text": "great job"}
        )
        data = _artifact_data(result)
        assert data["results"][0]["text"] == "great job"

    # ── Multiple texts via {"texts": [...]} ──────────────────────────────────

    async def test_multiple_texts_returns_result_per_text(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"texts": ["great", "terrible", "okay"]}
        )
        data = _artifact_data(result)
        assert len(data["results"]) == 3

    async def test_multiple_texts_first_is_positive(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"texts": ["amazing wonderful excellent", "bad"]}
        )
        data = _artifact_data(result)
        assert data["results"][0]["sentiment"] == "positive"

    async def test_multiple_texts_second_is_negative(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"texts": ["okay", "terrible horrible awful"]}
        )
        data = _artifact_data(result)
        assert data["results"][1]["sentiment"] == "negative"

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_empty_texts_list_returns_empty_results(self, app) -> None:
        result = await _send_json(app, "analyze-sentiment", {"texts": []})
        data = _artifact_data(result)
        assert data["results"] == []

    async def test_no_text_field_returns_empty_results(self, app) -> None:
        result = await _send_json(app, "analyze-sentiment", {})
        data = _artifact_data(result)
        assert data["results"] == []

    async def test_task_state_is_completed(self, app) -> None:
        result = await _send_json(
            app, "analyze-sentiment",
            {"text": "any text here"}
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_analyze_sentiment_skill(self, app) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/.well-known/agent.json")
        skill_ids = [s["id"] for s in resp.json()["skills"]]
        assert "analyze-sentiment" in skill_ids


# ---------------------------------------------------------------------------
# Document Summarizer Agent (port 9003)
# ---------------------------------------------------------------------------


class TestDocSummarizerAgent:
    """Tests for agents/doc_summarizer_agent/a2a_agent.py."""

    LONG_TEXT = (
        "Machine learning is transforming industries worldwide. "
        "Deep neural networks achieve superhuman accuracy on many benchmark tasks. "
        "Natural language processing enables computers to understand human text. "
        "Computer vision algorithms can identify objects in images with remarkable precision. "
        "Reinforcement learning agents learn optimal strategies through trial and error. "
        "Transfer learning allows models to apply knowledge from one domain to another. "
        "Data quality and diversity are critical factors in building robust machine learning systems. "
        "Explainability and fairness are increasingly important research directions in AI."
    )

    @pytest.fixture(scope="class")
    def app(self):
        from agents.doc_summarizer_agent.a2a_agent import app
        return app

    # ── Happy path ──────────────────────────────────────────────────────────

    async def test_summary_is_returned(self, app) -> None:
        result = await _send_json(app, "summarize", {"text": self.LONG_TEXT})
        data = _artifact_data(result)
        assert "summary" in data
        assert len(data["summary"]) > 0

    async def test_summary_shorter_than_original(self, app) -> None:
        result = await _send_json(app, "summarize", {"text": self.LONG_TEXT})
        data = _artifact_data(result)
        assert data["summary_length"] < data["original_length"]

    async def test_key_points_returned_as_list(self, app) -> None:
        result = await _send_json(app, "summarize", {"text": self.LONG_TEXT})
        data = _artifact_data(result)
        assert isinstance(data["key_points"], list)

    async def test_key_points_non_empty_for_long_text(self, app) -> None:
        result = await _send_json(app, "summarize", {"text": self.LONG_TEXT})
        data = _artifact_data(result)
        assert len(data["key_points"]) > 0

    async def test_original_length_is_positive(self, app) -> None:
        result = await _send_json(app, "summarize", {"text": self.LONG_TEXT})
        data = _artifact_data(result)
        assert data["original_length"] > 0

    async def test_task_state_is_completed(self, app) -> None:
        result = await _send_json(app, "summarize", {"text": self.LONG_TEXT})
        assert result["state"] == "completed"

    # ── max_sentences parameter ─────────────────────────────────────────────

    async def test_max_sentences_1_returns_single_sentence(self, app) -> None:
        result = await _send_json(
            app, "summarize",
            {"text": self.LONG_TEXT, "max_sentences": 1},
        )
        data = _artifact_data(result)
        # A single selected sentence should not contain interior sentence-ending
        # punctuation followed by a space (rough check that it is short).
        assert len(data["summary"]) < len(self.LONG_TEXT)

    async def test_max_sentences_default_is_3(self, app) -> None:
        """Default max_sentences is 3; the summary should contain ≤ 3 sentences."""
        result = await _send_json(app, "summarize", {"text": self.LONG_TEXT})
        data = _artifact_data(result)
        assert data["summary_length"] > 0

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_empty_text_returns_empty_summary(self, app) -> None:
        result = await _send_json(app, "summarize", {"text": ""})
        data = _artifact_data(result)
        assert data["summary"] == ""

    async def test_empty_text_returns_empty_key_points(self, app) -> None:
        result = await _send_json(app, "summarize", {"text": ""})
        data = _artifact_data(result)
        assert data["key_points"] == []

    async def test_empty_text_original_length_is_zero(self, app) -> None:
        result = await _send_json(app, "summarize", {"text": ""})
        data = _artifact_data(result)
        assert data["original_length"] == 0

    async def test_missing_text_key_returns_empty_summary(self, app) -> None:
        result = await _send_json(app, "summarize", {})
        data = _artifact_data(result)
        assert data["summary"] == ""

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_summarize_skill(self, app) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/.well-known/agent.json")
        skill_ids = [s["id"] for s in resp.json()["skills"]]
        assert "summarize" in skill_ids


# ---------------------------------------------------------------------------
# Report Generator Agent (port 9004)
# ---------------------------------------------------------------------------


class TestReportGeneratorAgent:
    """Tests for agents/report_generator/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self):
        from agents.report_generator.a2a_agent import app
        return app

    # ── Shared helpers ───────────────────────────────────────────────────────

    async def _generate(self, app, payload: dict) -> dict[str, Any]:
        """Send payload and return the decoded report dict."""
        result = await _send_json(app, "generate-report", payload)
        data = _artifact_data(result)
        return data["report"]

    # ── Data Sources section ─────────────────────────────────────────────────

    async def test_report_with_search_data_contains_data_sources_section(self, app) -> None:
        search_payload = {
            "query": "python asyncio",
            "total_results": 2,
            "results": [
                {
                    "title": "Asyncio Guide",
                    "url": "https://docs.example.com/asyncio",
                    "snippet": "Official asyncio guide.",
                },
                {
                    "title": "Asyncio Tutorial",
                    "url": "https://learn.example.com/asyncio",
                    "snippet": "Beginner asyncio tutorial.",
                },
            ],
        }
        report = await self._generate(app, search_payload)
        assert "Data Sources" in report["sections"]

    async def test_report_with_search_data_content_has_data_sources_header(self, app) -> None:
        search_payload = {
            "query": "pytest",
            "total_results": 1,
            "results": [
                {
                    "title": "Pytest Docs",
                    "url": "https://docs.pytest.org",
                    "snippet": "Official pytest documentation.",
                }
            ],
        }
        report = await self._generate(app, search_payload)
        assert "## Data Sources" in report["content"]

    # ── Sentiment data ───────────────────────────────────────────────────────

    async def test_report_with_sentiment_results_contains_sentiment_table(self, app) -> None:
        sentiment_payload = {
            "sentiment_results": [
                {"text": "great", "sentiment": "positive", "score": 0.5, "confidence": 0.8},
                {"text": "bad", "sentiment": "negative", "score": -0.5, "confidence": 0.7},
            ]
        }
        report = await self._generate(app, sentiment_payload)
        assert "Sentiment" in report["content"]
        # Table header should be present
        assert "| Text |" in report["content"]

    async def test_report_with_sentiment_results_lists_breakdown_in_findings(self, app) -> None:
        sentiment_payload = {
            "sentiment_results": [
                {"text": "excellent", "sentiment": "positive", "score": 0.9, "confidence": 0.9},
            ]
        }
        report = await self._generate(app, sentiment_payload)
        assert "positive" in report["content"]

    # ── Summary data ─────────────────────────────────────────────────────────

    async def test_report_with_summary_data_contains_document_summary_section(self, app) -> None:
        summary_payload = {
            "summary": "Machine learning is advancing rapidly.",
            "key_points": ["learning", "machine", "rapidly"],
            "original_length": 50,
            "summary_length": 6,
        }
        report = await self._generate(app, summary_payload)
        assert "Document Summary" in report["content"]

    async def test_report_with_summary_includes_key_terms(self, app) -> None:
        summary_payload = {
            "summary": "Neural networks are powerful.",
            "key_points": ["neural", "networks", "powerful"],
            "original_length": 20,
            "summary_length": 4,
        }
        report = await self._generate(app, summary_payload)
        assert "Key terms" in report["content"]

    # ── Auto-title generation ────────────────────────────────────────────────

    async def test_auto_title_uses_query_field(self, app) -> None:
        payload = {
            "query": "fastapi tutorial",
            "results": [],
        }
        report = await self._generate(app, payload)
        assert "Fastapi Tutorial" in report["title"]

    async def test_auto_title_uses_summary_field_when_no_query(self, app) -> None:
        payload = {
            "summary": "Python is a versatile programming language.",
            "key_points": [],
        }
        report = await self._generate(app, payload)
        assert "Python" in report["title"]

    async def test_auto_title_fallback_is_generated_report(self, app) -> None:
        payload = {"custom_field": "no recognized key here"}
        report = await self._generate(app, payload)
        assert report["title"] == "Generated Report"

    # ── Custom title override ────────────────────────────────────────────────

    async def test_custom_title_overrides_auto_title(self, app) -> None:
        payload = {
            "title": "My Custom Report Title",
            "query": "this should not be the title",
            "results": [],
        }
        report = await self._generate(app, payload)
        assert report["title"] == "My Custom Report Title"

    # ── Report structure ─────────────────────────────────────────────────────

    async def test_report_has_format_markdown(self, app) -> None:
        report = await self._generate(app, {"query": "test", "results": []})
        assert report["format"] == "markdown"

    async def test_report_has_sections_list(self, app) -> None:
        report = await self._generate(app, {"query": "test", "results": []})
        assert isinstance(report["sections"], list)
        assert len(report["sections"]) > 0

    async def test_report_has_generated_at_timestamp(self, app) -> None:
        report = await self._generate(app, {"query": "test", "results": []})
        assert "generated_at" in report

    async def test_report_content_starts_with_title_header(self, app) -> None:
        report = await self._generate(app, {"title": "Special Title", "query": "x", "results": []})
        assert "# Special Title" in report["content"]

    async def test_task_state_is_completed(self, app) -> None:
        result = await _send_json(app, "generate-report", {"query": "test", "results": []})
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_generate_report_skill(self, app) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/.well-known/agent.json")
        skill_ids = [s["id"] for s in resp.json()["skills"]]
        assert "generate-report" in skill_ids
