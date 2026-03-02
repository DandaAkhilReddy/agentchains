"""Tests for the 12 Phase 2 A2A agents via httpx.ASGITransport (in-process).

Each agent app is imported from its module-level ``app`` variable and driven
end-to-end through the full FastAPI ASGI stack without starting a real server.

Agents tested (ports 9005–9016):
  PaperFinder, DataEnricher, LanguageDetector, JsonNormalizer,
  MessageTranslator, TextClassifier, NERExtractor, ReadabilityScorer,
  PIIRedactor, SchemaValidator, TagGenerator, HeadlineGenerator
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest


# ---------------------------------------------------------------------------
# Shared helpers  (same pattern as test_demo_agents.py)
# ---------------------------------------------------------------------------


async def _send(app: Any, skill_id: str, message_text: str) -> dict[str, Any]:
    """Send a tasks/send JSON-RPC call and return the result dict."""
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


async def _send_json(app: Any, skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Serialize payload as JSON, send it, and return the result dict."""
    return await _send(app, skill_id, json.dumps(payload))


def _data(result: dict[str, Any]) -> dict[str, Any]:
    """Decode the first artifact's text part back from JSON."""
    text = result["artifacts"][0]["parts"][0]["text"]
    return json.loads(text)


async def _get_card(app: Any) -> dict[str, Any]:
    """Fetch the agent card from /.well-known/agent.json."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/.well-known/agent.json")
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Paper Finder Agent  (port 9005)
# ---------------------------------------------------------------------------


class TestPaperFinder:
    """Tests for agents/paper_finder_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.paper_finder_agent.a2a_agent import app
        return app

    # ── Happy path ──────────────────────────────────────────────────────────

    async def test_find_papers_returns_papers_list(self, app: Any) -> None:
        result = await _send_json(app, "find-papers", {"query": "neural networks"})
        data = _data(result)
        assert isinstance(data["papers"], list)
        assert len(data["papers"]) > 0

    async def test_find_papers_echoes_query(self, app: Any) -> None:
        result = await _send_json(app, "find-papers", {"query": "quantum computing"})
        data = _data(result)
        assert data["query"] == "quantum computing"

    async def test_paper_has_required_fields(self, app: Any) -> None:
        result = await _send_json(app, "find-papers", {"query": "machine learning"})
        data = _data(result)
        paper = data["papers"][0]
        for field in ("title", "authors", "year", "doi"):
            assert field in paper, f"Missing field: {field}"

    async def test_paper_authors_is_list_of_strings(self, app: Any) -> None:
        result = await _send_json(app, "find-papers", {"query": "deep learning"})
        data = _data(result)
        authors = data["papers"][0]["authors"]
        assert isinstance(authors, list)
        assert all(isinstance(a, str) for a in authors)

    async def test_paper_year_is_between_2020_and_2025(self, app: Any) -> None:
        result = await _send_json(app, "find-papers", {"query": "nlp transformers"})
        data = _data(result)
        for paper in data["papers"]:
            assert 2020 <= paper["year"] <= 2025

    # ── max_results parameter ────────────────────────────────────────────────

    async def test_max_results_1_returns_one_paper(self, app: Any) -> None:
        result = await _send_json(app, "find-papers", {"query": "python", "max_results": 1})
        data = _data(result)
        assert len(data["papers"]) == 1

    async def test_max_results_3_returns_three_papers(self, app: Any) -> None:
        result = await _send_json(app, "find-papers", {"query": "python", "max_results": 3})
        data = _data(result)
        assert len(data["papers"]) == 3

    async def test_max_results_exceeds_cap_clamped_to_10(self, app: Any) -> None:
        result = await _send_json(app, "find-papers", {"query": "ai", "max_results": 50})
        data = _data(result)
        assert len(data["papers"]) == 10

    # ── Determinism ─────────────────────────────────────────────────────────

    async def test_same_query_returns_identical_papers(self, app: Any) -> None:
        r1 = _data(await _send_json(app, "find-papers", {"query": "deterministic test"}))
        r2 = _data(await _send_json(app, "find-papers", {"query": "deterministic test"}))
        assert r1["papers"] == r2["papers"]

    async def test_different_queries_return_different_papers(self, app: Any) -> None:
        r1 = _data(await _send_json(app, "find-papers", {"query": "biology"}))
        r2 = _data(await _send_json(app, "find-papers", {"query": "cryptography"}))
        assert r1["papers"] != r2["papers"]

    # ── Text key fallback ────────────────────────────────────────────────────

    async def test_text_key_falls_back_as_query(self, app: Any) -> None:
        result = await _send_json(app, "find-papers", {"text": "robotics"})
        data = _data(result)
        assert len(data["papers"]) > 0

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(app, "find-papers", {"query": "test"})
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_name(self, app: Any) -> None:
        card = await _get_card(app)
        assert card["name"] == "Paper Finder Agent"

    async def test_agent_card_has_find_papers_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "find-papers" in skill_ids


# ---------------------------------------------------------------------------
# Data Enricher Agent  (port 9006)
# ---------------------------------------------------------------------------


class TestDataEnricher:
    """Tests for agents/data_enricher_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.data_enricher_agent.a2a_agent import app
        return app

    # ── Single URL via ``url`` key ───────────────────────────────────────────

    async def test_single_url_returns_one_enriched_item(self, app: Any) -> None:
        result = await _send_json(
            app, "enrich-data",
            {"url": "https://docs.python.org/3/library/os.html"},
        )
        data = _data(result)
        assert len(data["enriched"]) == 1

    async def test_enriched_item_has_domain(self, app: Any) -> None:
        result = await _send_json(
            app, "enrich-data",
            {"url": "https://docs.python.org/3/library/os.html"},
        )
        item = _data(result)["enriched"][0]
        assert item["domain"] == "docs.python.org"

    async def test_enriched_item_has_protocol_https(self, app: Any) -> None:
        result = await _send_json(
            app, "enrich-data",
            {"url": "https://docs.python.org/3/library/os.html"},
        )
        item = _data(result)["enriched"][0]
        assert item["protocol"] == "https"

    async def test_enriched_item_has_path(self, app: Any) -> None:
        result = await _send_json(
            app, "enrich-data",
            {"url": "https://docs.python.org/3/library/os.html"},
        )
        item = _data(result)["enriched"][0]
        assert item["path"] == "/3/library/os.html"

    # ── URL list via ``urls`` key ────────────────────────────────────────────

    async def test_url_list_returns_one_item_per_url(self, app: Any) -> None:
        result = await _send_json(
            app, "enrich-data",
            {"urls": [
                "https://docs.python.org/",
                "https://arxiv.org/abs/2301.00001",
            ]},
        )
        data = _data(result)
        assert len(data["enriched"]) == 2

    # ── Category detection ───────────────────────────────────────────────────

    async def test_docs_url_categorised_as_documentation(self, app: Any) -> None:
        result = await _send_json(
            app, "enrich-data",
            {"url": "https://docs.python.org/3/library/os.html"},
        )
        item = _data(result)["enriched"][0]
        assert item["category"] == "documentation"

    async def test_arxiv_url_categorised_as_research(self, app: Any) -> None:
        result = await _send_json(
            app, "enrich-data",
            {"url": "https://arxiv.org/abs/2301.00001"},
        )
        item = _data(result)["enriched"][0]
        assert item["category"] == "research"

    async def test_news_url_categorised_as_news(self, app: Any) -> None:
        result = await _send_json(
            app, "enrich-data",
            {"url": "https://news.ycombinator.com/item?id=12345"},
        )
        item = _data(result)["enriched"][0]
        assert item["category"] == "news"

    # ── Free text extraction ─────────────────────────────────────────────────

    async def test_text_with_embedded_url_is_extracted(self, app: Any) -> None:
        result = await _send_json(
            app, "enrich-data",
            {"text": "Check out https://docs.python.org for docs."},
        )
        data = _data(result)
        assert len(data["enriched"]) >= 1

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_no_urls_returns_empty_enriched(self, app: Any) -> None:
        result = await _send_json(app, "enrich-data", {"text": "no urls here"})
        data = _data(result)
        assert data["enriched"] == []

    # ── Task state and agent card ────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "enrich-data",
            {"url": "https://example.com"},
        )
        assert result["state"] == "completed"

    async def test_agent_card_has_enrich_data_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "enrich-data" in skill_ids


# ---------------------------------------------------------------------------
# Language Detector Agent  (port 9007)
# ---------------------------------------------------------------------------


class TestLanguageDetector:
    """Tests for agents/language_detector_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.language_detector_agent.a2a_agent import app
        return app

    # ── English detection ────────────────────────────────────────────────────

    async def test_english_text_detected_as_en(self, app: Any) -> None:
        result = await _send_json(
            app, "detect-language",
            {"text": "the quick brown fox jumps over the lazy dog and all that"},
        )
        data = _data(result)
        assert data["results"][0]["language_code"] == "en"

    async def test_english_detected_language_name_is_english(self, app: Any) -> None:
        result = await _send_json(
            app, "detect-language",
            {"text": "the quick brown fox jumps over the lazy dog"},
        )
        data = _data(result)
        assert data["results"][0]["detected_language"] == "English"

    # ── Spanish detection ────────────────────────────────────────────────────

    async def test_spanish_text_detected_as_es(self, app: Any) -> None:
        # Contains several high-weight Spanish trigrams from the profile
        result = await _send_json(
            app, "detect-language",
            {"text": "que los ción del para las con una por ados los que nte"},
        )
        data = _data(result)
        assert data["results"][0]["language_code"] == "es"

    # ── French detection ────────────────────────────────────────────────────

    async def test_french_text_detected_as_fr(self, app: Any) -> None:
        result = await _send_json(
            app, "detect-language",
            {"text": "les des une est que ent par sur tion ons ait ous eur ment"},
        )
        data = _data(result)
        assert data["results"][0]["language_code"] == "fr"

    # ── Single text via ``text`` key ─────────────────────────────────────────

    async def test_single_text_key_returns_one_result(self, app: Any) -> None:
        result = await _send_json(
            app, "detect-language",
            {"text": "hello world"},
        )
        data = _data(result)
        assert len(data["results"]) == 1

    # ── Batch via ``texts`` key ──────────────────────────────────────────────

    async def test_batch_texts_returns_one_result_per_text(self, app: Any) -> None:
        result = await _send_json(
            app, "detect-language",
            {"texts": ["hello world", "hola mundo", "bonjour monde"]},
        )
        data = _data(result)
        assert len(data["results"]) == 3

    # ── Result structure ─────────────────────────────────────────────────────

    async def test_result_has_confidence_field(self, app: Any) -> None:
        result = await _send_json(
            app, "detect-language",
            {"text": "the fox and the dog"},
        )
        data = _data(result)
        assert "confidence" in data["results"][0]

    async def test_result_has_script_field(self, app: Any) -> None:
        result = await _send_json(
            app, "detect-language",
            {"text": "hello world"},
        )
        data = _data(result)
        assert "script" in data["results"][0]

    async def test_result_has_text_excerpt(self, app: Any) -> None:
        result = await _send_json(
            app, "detect-language",
            {"text": "test input"},
        )
        data = _data(result)
        assert "text_excerpt" in data["results"][0]

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_empty_texts_list_returns_empty_results(self, app: Any) -> None:
        result = await _send_json(app, "detect-language", {"texts": []})
        data = _data(result)
        assert data["results"] == []

    async def test_missing_text_returns_empty_results(self, app: Any) -> None:
        result = await _send_json(app, "detect-language", {})
        data = _data(result)
        assert data["results"] == []

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "detect-language",
            {"text": "hello world"},
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_detect_language_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "detect-language" in skill_ids


# ---------------------------------------------------------------------------
# JSON Normalizer Agent  (port 9008)
# ---------------------------------------------------------------------------


class TestJsonNormalizer:
    """Tests for agents/json_normalizer_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.json_normalizer_agent.a2a_agent import app
        return app

    # ── Flattening ───────────────────────────────────────────────────────────

    async def test_nested_dict_produces_dot_notation_keys(self, app: Any) -> None:
        result = await _send_json(
            app, "normalize-json",
            {"data": {"user": {"name": "Alice", "age": 30}}},
        )
        data = _data(result)
        normalized = data["normalized"]
        assert "user.name" in normalized
        assert "user.age" in normalized

    async def test_dot_notation_value_equals_original(self, app: Any) -> None:
        result = await _send_json(
            app, "normalize-json",
            {"data": {"user": {"name": "Alice"}}},
        )
        data = _data(result)
        assert data["normalized"]["user.name"] == "Alice"

    async def test_flat_dict_is_unchanged(self, app: Any) -> None:
        result = await _send_json(
            app, "normalize-json",
            {"data": {"name": "Bob", "score": 42}},
        )
        data = _data(result)
        assert data["normalized"]["name"] == "Bob"
        assert data["normalized"]["score"] == 42

    # ── List indexing ────────────────────────────────────────────────────────

    async def test_list_items_indexed_with_dot_notation(self, app: Any) -> None:
        result = await _send_json(
            app, "normalize-json",
            {"data": [{"name": "Alice"}, {"name": "Bob"}]},
        )
        data = _data(result)
        assert "0.name" in data["normalized"]
        assert "1.name" in data["normalized"]

    async def test_list_item_zero_name_value(self, app: Any) -> None:
        result = await _send_json(
            app, "normalize-json",
            {"data": [{"name": "Alice"}, {"name": "Bob"}]},
        )
        data = _data(result)
        assert data["normalized"]["0.name"] == "Alice"

    # ── extract_fields parameter ─────────────────────────────────────────────

    async def test_extract_fields_filters_to_requested_path(self, app: Any) -> None:
        result = await _send_json(
            app, "normalize-json",
            {
                "data": {"user": {"name": "Carol", "age": 25}, "org": {"id": 7}},
                "extract_fields": ["user"],
            },
        )
        data = _data(result)
        normalized = data["normalized"]
        assert all(k.startswith("user") for k in normalized)
        assert "org.id" not in normalized

    async def test_extract_fields_exact_path_match(self, app: Any) -> None:
        result = await _send_json(
            app, "normalize-json",
            {
                "data": {"a": {"b": 1, "c": 2}},
                "extract_fields": ["a.b"],
            },
        )
        data = _data(result)
        assert "a.b" in data["normalized"]
        assert "a.c" not in data["normalized"]

    # ── field_count and original_depth metadata ──────────────────────────────

    async def test_field_count_matches_number_of_keys(self, app: Any) -> None:
        result = await _send_json(
            app, "normalize-json",
            {"data": {"x": 1, "y": 2, "z": 3}},
        )
        data = _data(result)
        assert data["field_count"] == 3

    async def test_original_depth_reflects_nesting(self, app: Any) -> None:
        result = await _send_json(
            app, "normalize-json",
            {"data": {"a": {"b": {"c": 1}}}},
        )
        data = _data(result)
        assert data["original_depth"] >= 3

    # ── No data key ─────────────────────────────────────────────────────────

    async def test_missing_data_returns_empty_normalized(self, app: Any) -> None:
        result = await _send_json(app, "normalize-json", {})
        data = _data(result)
        assert data["normalized"] == {}
        assert data["field_count"] == 0

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "normalize-json",
            {"data": {"k": "v"}},
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_normalize_json_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "normalize-json" in skill_ids


# ---------------------------------------------------------------------------
# Message Translator Agent  (port 9009)
# ---------------------------------------------------------------------------


class TestMessageTranslator:
    """Tests for agents/message_translator_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.message_translator_agent.a2a_agent import app
        return app

    # ── English → Spanish ────────────────────────────────────────────────────

    async def test_en_to_es_hello_translates(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello world", "target_language": "es"},
        )
        data = _data(result)
        assert "hola" in data["translated"].lower()

    async def test_en_to_es_method_is_dictionary(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello world", "target_language": "es"},
        )
        data = _data(result)
        assert data["method"] == "dictionary"

    async def test_en_to_es_translated_count_greater_than_zero(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello world the day", "target_language": "es"},
        )
        data = _data(result)
        assert data["translated_count"] > 0

    async def test_en_to_es_target_language_label_is_spanish(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello", "target_language": "es"},
        )
        data = _data(result)
        assert data["target_language"] == "Spanish"

    # ── English → French ─────────────────────────────────────────────────────

    async def test_en_to_fr_hello_translates_to_bonjour(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello world", "target_language": "fr"},
        )
        data = _data(result)
        assert "bonjour" in data["translated"].lower()

    async def test_en_to_fr_target_language_label_is_french(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello", "target_language": "fr"},
        )
        data = _data(result)
        assert data["target_language"] == "French"

    # ── Passthrough for unsupported language ─────────────────────────────────

    async def test_unsupported_lang_method_is_passthrough(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello world", "target_language": "ja"},
        )
        data = _data(result)
        assert data["method"] == "passthrough"

    async def test_unsupported_lang_returns_original_text(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello world", "target_language": "ja"},
        )
        data = _data(result)
        assert data["translated"] == "hello world"

    async def test_unsupported_lang_includes_note(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello", "target_language": "zh"},
        )
        data = _data(result)
        assert "note" in data

    # ── Result structure ─────────────────────────────────────────────────────

    async def test_result_includes_original_text(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "good morning", "target_language": "es"},
        )
        data = _data(result)
        assert data["original"] == "good morning"

    async def test_result_includes_word_count(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello world today", "target_language": "es"},
        )
        data = _data(result)
        assert data["word_count"] == 3

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_empty_text_returns_empty_translated(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "", "target_language": "es"},
        )
        data = _data(result)
        assert data["translated"] == ""

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "translate",
            {"text": "hello", "target_language": "es"},
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_translate_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "translate" in skill_ids


# ---------------------------------------------------------------------------
# Text Classifier Agent  (port 9010)
# ---------------------------------------------------------------------------


class TestTextClassifier:
    """Tests for agents/text_classifier_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.text_classifier_agent.a2a_agent import app
        return app

    # ── Happy path ──────────────────────────────────────────────────────────

    async def test_technology_text_top_category(self, app: Any) -> None:
        result = await _send_json(
            app, "classify-text",
            {"text": "AI software algorithm machine learning neural network code platform"},
        )
        data = _data(result)
        assert data["top_category"] == "technology"

    async def test_health_text_top_category(self, app: Any) -> None:
        result = await _send_json(
            app, "classify-text",
            {
                "text": (
                    "The patient received a clinical diagnosis and medical treatment. "
                    "The doctor prescribed a pharmaceutical therapy and vaccine."
                )
            },
        )
        data = _data(result)
        assert data["top_category"] == "health"

    async def test_sports_text_top_category(self, app: Any) -> None:
        result = await _send_json(
            app, "classify-text",
            {"text": "The team scored a goal in the championship match league tournament."},
        )
        data = _data(result)
        assert data["top_category"] == "sports"

    # ── Classifications list structure ───────────────────────────────────────

    async def test_classifications_list_has_up_to_three_entries(self, app: Any) -> None:
        result = await _send_json(
            app, "classify-text",
            {"text": "science research experiment hypothesis theory"},
        )
        data = _data(result)
        assert 1 <= len(data["classifications"]) <= 3

    async def test_classification_entry_has_score(self, app: Any) -> None:
        result = await _send_json(
            app, "classify-text",
            {"text": "science research experiment"},
        )
        data = _data(result)
        assert "score" in data["classifications"][0]

    async def test_classification_entry_has_matching_keywords(self, app: Any) -> None:
        result = await _send_json(
            app, "classify-text",
            {"text": "science research experiment"},
        )
        data = _data(result)
        assert "matching_keywords" in data["classifications"][0]

    # ── Custom categories parameter ──────────────────────────────────────────

    async def test_custom_categories_restricts_classification(self, app: Any) -> None:
        result = await _send_json(
            app, "classify-text",
            {
                "text": "team player championship match goal",
                "categories": ["sports", "entertainment"],
            },
        )
        data = _data(result)
        returned_cats = [c["category"] for c in data["classifications"]]
        for cat in returned_cats:
            assert cat in ("sports", "entertainment")

    async def test_custom_categories_unknown_name_ignored(self, app: Any) -> None:
        result = await _send_json(
            app, "classify-text",
            {
                "text": "science research experiment",
                "categories": ["science", "nonexistent_category"],
            },
        )
        data = _data(result)
        returned_cats = [c["category"] for c in data["classifications"]]
        assert "nonexistent_category" not in returned_cats

    # ── Text excerpt ─────────────────────────────────────────────────────────

    async def test_text_excerpt_is_returned(self, app: Any) -> None:
        result = await _send_json(
            app, "classify-text",
            {"text": "machine learning software code"},
        )
        data = _data(result)
        assert "text_excerpt" in data

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_empty_text_top_category_unknown(self, app: Any) -> None:
        result = await _send_json(app, "classify-text", {"text": ""})
        data = _data(result)
        assert data["top_category"] == "unknown"

    async def test_empty_text_classifications_empty(self, app: Any) -> None:
        result = await _send_json(app, "classify-text", {"text": ""})
        data = _data(result)
        assert data["classifications"] == []

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "classify-text",
            {"text": "machine learning"},
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_classify_text_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "classify-text" in skill_ids


# ---------------------------------------------------------------------------
# NER Extractor Agent  (port 9011)
# ---------------------------------------------------------------------------


class TestNERExtractor:
    """Tests for agents/ner_extractor_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.ner_extractor_agent.a2a_agent import app
        return app

    # ── PERSON detection ─────────────────────────────────────────────────────

    async def test_person_entity_detected(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "John Smith attended the meeting."},
        )
        data = _data(result)
        person_types = [e["type"] for e in data["entities"]]
        assert "PERSON" in person_types

    async def test_person_entity_text_is_correct(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "John Smith attended the meeting."},
        )
        data = _data(result)
        persons = [e["text"] for e in data["entities"] if e["type"] == "PERSON"]
        assert "John Smith" in persons

    # ── EMAIL detection ──────────────────────────────────────────────────────

    async def test_email_entity_detected(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "Contact us at info@example.com for details."},
        )
        data = _data(result)
        email_types = [e["type"] for e in data["entities"]]
        assert "EMAIL" in email_types

    async def test_email_entity_text_is_correct(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "Contact us at info@example.com for details."},
        )
        data = _data(result)
        emails = [e["text"] for e in data["entities"] if e["type"] == "EMAIL"]
        assert "info@example.com" in emails

    # ── PHONE detection ──────────────────────────────────────────────────────

    async def test_phone_entity_detected(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "Call us at (555) 123-4567 for support."},
        )
        data = _data(result)
        phone_types = [e["type"] for e in data["entities"]]
        assert "PHONE" in phone_types

    # ── entity_counts structure ──────────────────────────────────────────────

    async def test_entity_counts_dict_is_returned(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "John Smith emailed info@example.com"},
        )
        data = _data(result)
        assert isinstance(data["entity_counts"], dict)

    async def test_entity_counts_has_all_standard_types(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "sample text"},
        )
        data = _data(result)
        expected_types = {"PERSON", "ORGANIZATION", "DATE", "EMAIL", "PHONE", "URL", "MONEY", "PERCENTAGE"}
        assert expected_types.issubset(set(data["entity_counts"].keys()))

    async def test_entity_count_person_matches_entities_list(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "John Smith and Jane Doe attended the event."},
        )
        data = _data(result)
        person_count_from_list = sum(1 for e in data["entities"] if e["type"] == "PERSON")
        assert data["entity_counts"]["PERSON"] == person_count_from_list

    # ── total_entities ───────────────────────────────────────────────────────

    async def test_total_entities_matches_entities_list_length(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "John Smith emailed info@example.com on March 14, 2024."},
        )
        data = _data(result)
        assert data["total_entities"] == len(data["entities"])

    # ── Span offsets ─────────────────────────────────────────────────────────

    async def test_entity_has_start_and_end_offsets(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "info@example.com is the contact"},
        )
        data = _data(result)
        entity = data["entities"][0]
        assert "start" in entity
        assert "end" in entity
        assert entity["end"] > entity["start"]

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_empty_text_returns_no_entities(self, app: Any) -> None:
        result = await _send_json(app, "extract-entities", {"text": ""})
        data = _data(result)
        assert data["entities"] == []
        assert data["total_entities"] == 0

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "extract-entities",
            {"text": "John Smith"},
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_extract_entities_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "extract-entities" in skill_ids


# ---------------------------------------------------------------------------
# Readability Scorer Agent  (port 9012)
# ---------------------------------------------------------------------------


class TestReadabilityScorer:
    """Tests for agents/readability_scorer_agent/a2a_agent.py."""

    SIMPLE_TEXT = "The cat sat on the mat. It was sunny. The dog ran fast."
    COMPLEX_TEXT = (
        "Epistemological considerations regarding the multifaceted implications "
        "of interdisciplinary neurobiological research demonstrate extraordinarily "
        "sophisticated methodological frameworks. Phenomenological interpretations "
        "necessitate comprehensive understanding of contemporary philosophical paradigms."
    )

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.readability_scorer_agent.a2a_agent import app
        return app

    # ── Simple text ──────────────────────────────────────────────────────────

    async def test_simple_text_returns_scores(self, app: Any) -> None:
        result = await _send_json(
            app, "score-readability",
            {"text": self.SIMPLE_TEXT},
        )
        data = _data(result)
        assert "flesch_reading_ease" in data
        assert "flesch_kincaid_grade" in data

    async def test_simple_text_has_low_grade_level(self, app: Any) -> None:
        result = await _send_json(
            app, "score-readability",
            {"text": self.SIMPLE_TEXT},
        )
        data = _data(result)
        # Simple text should be elementary or middle school
        assert data["flesch_kincaid_grade"] < 8.0

    async def test_complex_text_has_higher_grade_level(self, app: Any) -> None:
        result = await _send_json(
            app, "score-readability",
            {"text": self.COMPLEX_TEXT},
        )
        data = _data(result)
        assert data["flesch_kincaid_grade"] > 8.0

    # ── Simple vs complex ordering ───────────────────────────────────────────

    async def test_simple_text_easier_than_complex(self, app: Any) -> None:
        r_simple = _data(await _send_json(
            app, "score-readability", {"text": self.SIMPLE_TEXT}
        ))
        r_complex = _data(await _send_json(
            app, "score-readability", {"text": self.COMPLEX_TEXT}
        ))
        # Higher Flesch ease = easier to read
        assert r_simple["flesch_reading_ease"] > r_complex["flesch_reading_ease"]

    async def test_complex_text_has_higher_fk_grade_than_simple(self, app: Any) -> None:
        r_simple = _data(await _send_json(
            app, "score-readability", {"text": self.SIMPLE_TEXT}
        ))
        r_complex = _data(await _send_json(
            app, "score-readability", {"text": self.COMPLEX_TEXT}
        ))
        assert r_complex["flesch_kincaid_grade"] > r_simple["flesch_kincaid_grade"]

    # ── Stats returned ───────────────────────────────────────────────────────

    async def test_stats_contains_sentences_key(self, app: Any) -> None:
        result = await _send_json(
            app, "score-readability",
            {"text": self.SIMPLE_TEXT},
        )
        data = _data(result)
        assert "sentences" in data["stats"]

    async def test_stats_contains_words_key(self, app: Any) -> None:
        result = await _send_json(
            app, "score-readability",
            {"text": self.SIMPLE_TEXT},
        )
        data = _data(result)
        assert "words" in data["stats"]

    async def test_stats_contains_syllables_key(self, app: Any) -> None:
        result = await _send_json(
            app, "score-readability",
            {"text": self.SIMPLE_TEXT},
        )
        data = _data(result)
        assert "syllables" in data["stats"]

    async def test_stats_sentence_count_is_positive(self, app: Any) -> None:
        result = await _send_json(
            app, "score-readability",
            {"text": self.SIMPLE_TEXT},
        )
        data = _data(result)
        assert data["stats"]["sentences"] > 0

    async def test_grade_label_is_string(self, app: Any) -> None:
        result = await _send_json(
            app, "score-readability",
            {"text": self.SIMPLE_TEXT},
        )
        data = _data(result)
        assert isinstance(data["grade_label"], str)
        assert len(data["grade_label"]) > 0

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_empty_text_returns_zero_scores(self, app: Any) -> None:
        result = await _send_json(app, "score-readability", {"text": ""})
        data = _data(result)
        assert data["flesch_reading_ease"] == 0.0
        assert data["flesch_kincaid_grade"] == 0.0

    async def test_empty_text_grade_label_is_elementary(self, app: Any) -> None:
        result = await _send_json(app, "score-readability", {"text": ""})
        data = _data(result)
        assert data["grade_label"] == "Elementary"

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "score-readability",
            {"text": self.SIMPLE_TEXT},
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_score_readability_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "score-readability" in skill_ids


# ---------------------------------------------------------------------------
# PII Redactor Agent  (port 9013)
# ---------------------------------------------------------------------------


class TestPIIRedactor:
    """Tests for agents/pii_redactor_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.pii_redactor_agent.a2a_agent import app
        return app

    # ── Email redaction ──────────────────────────────────────────────────────

    async def test_email_is_redacted(self, app: Any) -> None:
        result = await _send_json(
            app, "redact-pii",
            {"text": "Contact john@example.com for support."},
        )
        data = _data(result)
        assert "john@example.com" not in data["redacted_text"]

    async def test_email_placeholder_present(self, app: Any) -> None:
        result = await _send_json(
            app, "redact-pii",
            {"text": "Email: john@example.com"},
        )
        data = _data(result)
        assert "[EMAIL_REDACTED]" in data["redacted_text"]

    async def test_email_redaction_counted(self, app: Any) -> None:
        result = await _send_json(
            app, "redact-pii",
            {"text": "Email me at john@example.com or jane@test.org"},
        )
        data = _data(result)
        email_count = next(
            (r["count"] for r in data["redactions"] if r["type"] == "Email"), 0
        )
        assert email_count == 2

    # ── Phone redaction ──────────────────────────────────────────────────────

    async def test_phone_is_redacted(self, app: Any) -> None:
        result = await _send_json(
            app, "redact-pii",
            {"text": "Call us at (555) 123-4567."},
        )
        data = _data(result)
        assert "(555) 123-4567" not in data["redacted_text"]

    async def test_phone_placeholder_present(self, app: Any) -> None:
        result = await _send_json(
            app, "redact-pii",
            {"text": "Phone: (555) 123-4567"},
        )
        data = _data(result)
        assert "[PHONE_REDACTED]" in data["redacted_text"]

    # ── SSN redaction ────────────────────────────────────────────────────────

    async def test_ssn_is_redacted(self, app: Any) -> None:
        result = await _send_json(
            app, "redact-pii",
            {"text": "My SSN is 123-45-6789."},
        )
        data = _data(result)
        assert "123-45-6789" not in data["redacted_text"]

    async def test_ssn_placeholder_present(self, app: Any) -> None:
        result = await _send_json(
            app, "redact-pii",
            {"text": "SSN: 123-45-6789"},
        )
        data = _data(result)
        assert "[SSN_REDACTED]" in data["redacted_text"]

    # ── total_redactions ─────────────────────────────────────────────────────

    async def test_total_redactions_sums_all_types(self, app: Any) -> None:
        result = await _send_json(
            app, "redact-pii",
            {"text": "Email john@example.com and SSN 123-45-6789 and phone (555) 123-4567."},
        )
        data = _data(result)
        expected_total = sum(r["count"] for r in data["redactions"])
        assert data["total_redactions"] == expected_total

    async def test_no_pii_returns_zero_redactions(self, app: Any) -> None:
        result = await _send_json(
            app, "redact-pii",
            {"text": "The quick brown fox jumps over the lazy dog."},
        )
        data = _data(result)
        assert data["total_redactions"] == 0

    async def test_original_length_is_correct(self, app: Any) -> None:
        text = "Contact john@example.com"
        result = await _send_json(app, "redact-pii", {"text": text})
        data = _data(result)
        assert data["original_length"] == len(text)

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_empty_text_returns_zero_redactions(self, app: Any) -> None:
        result = await _send_json(app, "redact-pii", {"text": ""})
        data = _data(result)
        assert data["total_redactions"] == 0
        assert data["redacted_text"] == ""

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "redact-pii",
            {"text": "hello world"},
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_redact_pii_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "redact-pii" in skill_ids


# ---------------------------------------------------------------------------
# Schema Validator Agent  (port 9014)
# ---------------------------------------------------------------------------


class TestSchemaValidator:
    """Tests for agents/schema_validator_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.schema_validator_agent.a2a_agent import app
        return app

    # ── Valid data ───────────────────────────────────────────────────────────

    async def test_valid_data_returns_valid_true(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": {"name": "Alice", "age": 30},
                "schema": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                },
            },
        )
        data = _data(result)
        assert data["valid"] is True

    async def test_valid_data_returns_no_errors(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": {"name": "Alice"},
                "schema": {"type": "object", "required": ["name"]},
            },
        )
        data = _data(result)
        assert data["errors"] == []

    async def test_valid_data_checked_fields_is_populated(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": {"name": "Alice"},
                "schema": {"type": "object", "required": ["name"]},
            },
        )
        data = _data(result)
        assert len(data["checked_fields"]) > 0

    # ── Missing required field ───────────────────────────────────────────────

    async def test_missing_required_field_returns_valid_false(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": {"age": 30},
                "schema": {"type": "object", "required": ["name"]},
            },
        )
        data = _data(result)
        assert data["valid"] is False

    async def test_missing_required_field_error_message_mentions_field(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": {},
                "schema": {"type": "object", "required": ["email"]},
            },
        )
        data = _data(result)
        assert any("email" in e["message"] for e in data["errors"])

    # ── Wrong type ───────────────────────────────────────────────────────────

    async def test_wrong_type_returns_valid_false(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": "not an object",
                "schema": {"type": "object"},
            },
        )
        data = _data(result)
        assert data["valid"] is False

    async def test_wrong_type_error_mentions_expected_type(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": 123,
                "schema": {"type": "string"},
            },
        )
        data = _data(result)
        assert any("string" in e["message"] for e in data["errors"])

    # ── Numeric constraints ──────────────────────────────────────────────────

    async def test_value_below_minimum_returns_error(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": {"score": -5},
                "schema": {
                    "type": "object",
                    "properties": {"score": {"type": "integer", "minimum": 0}},
                },
            },
        )
        data = _data(result)
        assert data["valid"] is False

    async def test_value_above_maximum_returns_error(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": {"score": 200},
                "schema": {
                    "type": "object",
                    "properties": {"score": {"type": "integer", "maximum": 100}},
                },
            },
        )
        data = _data(result)
        assert data["valid"] is False

    async def test_value_within_range_is_valid(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": {"score": 50},
                "schema": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer", "minimum": 0, "maximum": 100}
                    },
                },
            },
        )
        data = _data(result)
        assert data["valid"] is True

    # ── Array validation ─────────────────────────────────────────────────────

    async def test_array_with_wrong_item_type_returns_error(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": [1, 2, "three"],
                "schema": {"type": "array", "items": {"type": "integer"}},
            },
        )
        data = _data(result)
        assert data["valid"] is False

    async def test_array_with_correct_item_types_is_valid(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": [1, 2, 3],
                "schema": {"type": "array", "items": {"type": "integer"}},
            },
        )
        data = _data(result)
        assert data["valid"] is True

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "validate-schema",
            {
                "data": {"x": 1},
                "schema": {"type": "object"},
            },
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_validate_schema_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "validate-schema" in skill_ids


# ---------------------------------------------------------------------------
# Tag Generator Agent  (port 9015)
# ---------------------------------------------------------------------------


class TestTagGenerator:
    """Tests for agents/tag_generator_agent/a2a_agent.py."""

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.tag_generator_agent.a2a_agent import app
        return app

    # ── Happy path ──────────────────────────────────────────────────────────

    async def test_generates_tags_list(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-tags",
            {"text": "Machine learning models require large datasets and GPU compute."},
        )
        data = _data(result)
        assert isinstance(data["tags"], list)
        assert len(data["tags"]) > 0

    async def test_tag_entry_has_tag_score_frequency(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-tags",
            {"text": "Python programming language data science machine learning"},
        )
        data = _data(result)
        tag = data["tags"][0]
        assert "tag" in tag
        assert "score" in tag
        assert "frequency" in tag

    async def test_tag_score_is_positive(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-tags",
            {"text": "Python data science machine learning algorithms"},
        )
        data = _data(result)
        assert all(t["score"] > 0 for t in data["tags"])

    async def test_stop_words_excluded_from_tags(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-tags",
            {"text": "the quick brown fox jumps over the lazy dog"},
        )
        data = _data(result)
        tag_words = [t["tag"] for t in data["tags"]]
        stop_words = {"the", "a", "an", "is", "are", "in", "on", "for", "with"}
        for stop in stop_words:
            assert stop not in tag_words

    # ── max_tags parameter ───────────────────────────────────────────────────

    async def test_max_tags_1_returns_at_most_one_tag(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-tags",
            {
                "text": "Python programming language data science machine learning models",
                "max_tags": 1,
            },
        )
        data = _data(result)
        assert len(data["tags"]) == 1

    async def test_max_tags_3_returns_at_most_three_tags(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-tags",
            {
                "text": "Python programming language data science machine learning models networks",
                "max_tags": 3,
            },
        )
        data = _data(result)
        assert len(data["tags"]) <= 3

    # ── Metadata fields ──────────────────────────────────────────────────────

    async def test_total_unique_words_is_returned(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-tags",
            {"text": "machine learning models datasets"},
        )
        data = _data(result)
        assert "total_unique_words" in data

    async def test_text_length_is_returned(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-tags",
            {"text": "machine learning models"},
        )
        data = _data(result)
        assert "text_length" in data

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_empty_text_returns_empty_tags(self, app: Any) -> None:
        result = await _send_json(app, "generate-tags", {"text": ""})
        data = _data(result)
        assert data["tags"] == []

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-tags",
            {"text": "machine learning"},
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_generate_tags_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "generate-tags" in skill_ids


# ---------------------------------------------------------------------------
# Headline Generator Agent  (port 9016)
# ---------------------------------------------------------------------------


class TestHeadlineGenerator:
    """Tests for agents/headline_generator_agent/a2a_agent.py."""

    SAMPLE_TEXT = (
        "Scientists at MIT have discovered a new material that can store solar energy "
        "for months at a time and release it on demand as heat. The breakthrough could "
        "transform how we heat homes and buildings in cold climates."
    )

    @pytest.fixture(scope="class")
    def app(self) -> Any:
        from agents.headline_generator_agent.a2a_agent import app
        return app

    # ── Happy path ──────────────────────────────────────────────────────────

    async def test_generates_non_empty_headline(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT},
        )
        data = _data(result)
        assert isinstance(data["headline"], str)
        assert len(data["headline"]) > 0

    async def test_headline_within_default_max_length(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT},
        )
        data = _data(result)
        assert len(data["headline"]) <= 80

    async def test_source_length_matches_input_text(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT},
        )
        data = _data(result)
        assert data["source_length"] == len(self.SAMPLE_TEXT)

    # ── Style parameter ──────────────────────────────────────────────────────

    async def test_news_style_is_echoed_in_result(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT, "style": "news"},
        )
        data = _data(result)
        assert data["style"] == "news"

    async def test_academic_style_prefix_in_headline(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT, "style": "academic"},
        )
        data = _data(result)
        assert data["style"] == "academic"
        assert "Study Finds" in data["headline"]

    async def test_casual_style_prefix_in_headline(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT, "style": "casual"},
        )
        data = _data(result)
        assert data["style"] == "casual"
        assert "Here's the thing" in data["headline"]

    async def test_unknown_style_defaults_to_news(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT, "style": "pirate"},
        )
        data = _data(result)
        assert data["style"] == "news"

    # ── Alternatives ────────────────────────────────────────────────────────

    async def test_alternatives_is_list(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT},
        )
        data = _data(result)
        assert isinstance(data["alternatives"], list)

    async def test_alternatives_are_distinct_from_headline(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT},
        )
        data = _data(result)
        for alt in data["alternatives"]:
            assert alt != data["headline"]

    # ── max_length parameter ─────────────────────────────────────────────────

    async def test_custom_max_length_respected(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT, "max_length": 30},
        )
        data = _data(result)
        assert len(data["headline"]) <= 30

    # ── key_terms ────────────────────────────────────────────────────────────

    async def test_key_terms_is_list(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT},
        )
        data = _data(result)
        assert isinstance(data["key_terms"], list)

    # ── Empty input ──────────────────────────────────────────────────────────

    async def test_empty_text_returns_empty_headline(self, app: Any) -> None:
        result = await _send_json(app, "generate-headline", {"text": ""})
        data = _data(result)
        assert data["headline"] == ""

    async def test_empty_text_alternatives_empty(self, app: Any) -> None:
        result = await _send_json(app, "generate-headline", {"text": ""})
        data = _data(result)
        assert data["alternatives"] == []

    # ── Task state ───────────────────────────────────────────────────────────

    async def test_task_state_is_completed(self, app: Any) -> None:
        result = await _send_json(
            app, "generate-headline",
            {"text": self.SAMPLE_TEXT},
        )
        assert result["state"] == "completed"

    # ── Agent card ───────────────────────────────────────────────────────────

    async def test_agent_card_has_generate_headline_skill(self, app: Any) -> None:
        card = await _get_card(app)
        skill_ids = [s["id"] for s in card["skills"]]
        assert "generate-headline" in skill_ids
