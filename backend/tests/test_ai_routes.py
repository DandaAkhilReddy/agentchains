"""Tests for AI insights routes (/api/ai/*)."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# explain-loan
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestExplainLoan:
    async def test_explain_loan_success(self, async_client, mock_loan):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_loan)

        mock_ai = MagicMock()
        mock_ai.explain_loan = AsyncMock(return_value=("This is a home loan explanation.", {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}))

        with (
            patch("app.api.routes.ai_insights.LoanRepository", return_value=mock_repo),
            patch("app.api.routes.ai_insights.AIService", return_value=mock_ai),
            patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock),
        ):
            resp = await async_client.post("/api/ai/explain-loan", json={
                "loan_id": str(mock_loan.id),
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "This is a home loan explanation."
        assert data["language"] == "en"

    async def test_explain_loan_not_found(self, async_client):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with patch("app.api.routes.ai_insights.LoanRepository", return_value=mock_repo):
            resp = await async_client.post("/api/ai/explain-loan", json={
                "loan_id": "00000000-0000-4000-a000-000000000099",
            })

        assert resp.status_code == 404

    async def test_explain_loan_translates_for_hindi_user(self, async_client, mock_user, mock_loan):
        original_lang = mock_user.preferred_language
        mock_user.preferred_language = "hi"
        try:
            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_loan)

            mock_ai = MagicMock()
            mock_ai.explain_loan = AsyncMock(return_value=("English explanation", {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}))

            mock_translator = MagicMock()
            mock_translator.translate = AsyncMock(return_value="Hindi explanation")

            with (
                patch("app.api.routes.ai_insights.LoanRepository", return_value=mock_repo),
                patch("app.api.routes.ai_insights.AIService", return_value=mock_ai),
                patch("app.api.routes.ai_insights.TranslatorService", return_value=mock_translator),
                patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock),
            ):
                resp = await async_client.post("/api/ai/explain-loan", json={
                    "loan_id": str(mock_loan.id),
                })

            assert resp.status_code == 200
            data = resp.json()
            assert data["text"] == "Hindi explanation"
            assert data["language"] == "hi"
            mock_translator.translate.assert_called_once_with("English explanation", "hi")
        finally:
            mock_user.preferred_language = original_lang


# ---------------------------------------------------------------------------
# explain-strategy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestExplainStrategy:
    async def test_explain_strategy_success(self, async_client):
        mock_ai = MagicMock()
        mock_ai.explain_strategy = AsyncMock(return_value=("Avalanche pays least interest.", {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120}))

        with (
            patch("app.api.routes.ai_insights.AIService", return_value=mock_ai),
            patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock),
        ):
            resp = await async_client.post("/api/ai/explain-strategy", json={
                "strategy_name": "avalanche",
                "num_loans": 3,
                "extra": 10000.0,
                "interest_saved": 245000.0,
                "months_saved": 18,
                "payoff_order": ["HDFC Personal", "SBI Home", "Axis Car"],
            })

        assert resp.status_code == 200
        assert resp.json()["text"] == "Avalanche pays least interest."


# ---------------------------------------------------------------------------
# ask (RAG Q&A)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAsk:
    async def test_ask_success(self, async_client):
        mock_embed_svc = MagicMock()
        mock_embed_svc.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

        mock_result = MagicMock()
        mock_result.chunk_text = "RBI says 0% penalty on floating rate."

        mock_embed_repo = MagicMock()
        mock_embed_repo.similarity_search = AsyncMock(return_value=[mock_result])

        mock_ai = MagicMock()
        mock_ai.ask_with_context = AsyncMock(return_value=("No penalty for floating rate prepayment.", {"prompt_tokens": 200, "completion_tokens": 60, "total_tokens": 260}))

        with (
            patch("app.api.routes.ai_insights.EmbeddingService", return_value=mock_embed_svc),
            patch("app.api.routes.ai_insights.EmbeddingRepository", return_value=mock_embed_repo),
            patch("app.api.routes.ai_insights.AIService", return_value=mock_ai),
            patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock),
        ):
            resp = await async_client.post("/api/ai/ask", json={
                "question": "What is RBI rule on prepayment?",
            })

        assert resp.status_code == 200
        assert "floating" in resp.json()["text"].lower()


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTTS:
    async def test_tts_english(self, async_client):
        mock_tts = MagicMock()
        mock_tts.generate_audio = AsyncMock(return_value="base64audiodata==")

        with patch("app.api.routes.ai_insights.TTSService", return_value=mock_tts):
            resp = await async_client.post("/api/ai/tts", json={
                "text": "Hello world",
                "language": "en",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_base64"] == "base64audiodata=="
        assert data["language"] == "en"

    async def test_tts_hindi(self, async_client):
        mock_tts = MagicMock()
        mock_tts.generate_audio = AsyncMock(return_value="hindiAudio==")

        with patch("app.api.routes.ai_insights.TTSService", return_value=mock_tts):
            resp = await async_client.post("/api/ai/tts", json={
                "text": "Namaste",
                "language": "hi",
            })

        assert resp.status_code == 200
        assert resp.json()["language"] == "hi"

    async def test_tts_null_audio(self, async_client):
        mock_tts = MagicMock()
        mock_tts.generate_audio = AsyncMock(return_value=None)

        with patch("app.api.routes.ai_insights.TTSService", return_value=mock_tts):
            resp = await async_client.post("/api/ai/tts", json={
                "text": "Hello",
                "language": "en",
            })

        assert resp.status_code == 200
        assert resp.json()["audio_base64"] is None


# ---------------------------------------------------------------------------
# chat (conversational RAG)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestChat:
    async def test_chat_success(self, async_client):
        mock_embed_svc = MagicMock()
        mock_embed_svc.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

        mock_result = MagicMock()
        mock_result.chunk_text = "Prepayment of floating rate loans has no penalty."

        mock_embed_repo = MagicMock()
        mock_embed_repo.similarity_search = AsyncMock(return_value=[mock_result])

        mock_ai = MagicMock()
        mock_ai.chat_with_history = AsyncMock(return_value=("You can prepay without penalty.", {"prompt_tokens": 150, "completion_tokens": 40, "total_tokens": 190}))

        with (
            patch("app.api.routes.ai_insights.EmbeddingService", return_value=mock_embed_svc),
            patch("app.api.routes.ai_insights.EmbeddingRepository", return_value=mock_embed_repo),
            patch("app.api.routes.ai_insights.AIService", return_value=mock_ai),
            patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock),
        ):
            resp = await async_client.post("/api/ai/chat", json={
                "message": "Can I prepay my home loan?",
                "history": [],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "You can prepay without penalty."
        assert data["language"] == "en"

    async def test_chat_with_history(self, async_client):
        mock_embed_svc = MagicMock()
        mock_embed_svc.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

        mock_embed_repo = MagicMock()
        mock_embed_repo.similarity_search = AsyncMock(return_value=[])

        mock_ai = MagicMock()
        mock_ai.chat_with_history = AsyncMock(return_value=("Follow-up answer.", {"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250}))

        with (
            patch("app.api.routes.ai_insights.EmbeddingService", return_value=mock_embed_svc),
            patch("app.api.routes.ai_insights.EmbeddingRepository", return_value=mock_embed_repo),
            patch("app.api.routes.ai_insights.AIService", return_value=mock_ai),
            patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock),
        ):
            resp = await async_client.post("/api/ai/chat", json={
                "message": "What about fixed rate?",
                "history": [
                    {"role": "user", "content": "Can I prepay?"},
                    {"role": "assistant", "content": "Yes, floating rate has no penalty."},
                ],
            })

        assert resp.status_code == 200
        assert resp.json()["text"] == "Follow-up answer."
        mock_ai.chat_with_history.assert_called_once_with(
            message="What about fixed rate?",
            history=[("user", "Can I prepay?"), ("assistant", "Yes, floating rate has no penalty.")],
            context_chunks=[],
            country="IN",
        )

    async def test_chat_translates_hindi(self, async_client, mock_user):
        original_lang = mock_user.preferred_language
        mock_user.preferred_language = "hi"
        try:
            mock_embed_svc = MagicMock()
            mock_embed_svc.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            mock_embed_repo = MagicMock()
            mock_embed_repo.similarity_search = AsyncMock(return_value=[])

            mock_ai = MagicMock()
            mock_ai.chat_with_history = AsyncMock(return_value=("English chat answer.", {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}))

            mock_translator = MagicMock()
            mock_translator.translate = AsyncMock(return_value="Hindi chat answer.")

            with (
                patch("app.api.routes.ai_insights.EmbeddingService", return_value=mock_embed_svc),
                patch("app.api.routes.ai_insights.EmbeddingRepository", return_value=mock_embed_repo),
                patch("app.api.routes.ai_insights.AIService", return_value=mock_ai),
                patch("app.api.routes.ai_insights.TranslatorService", return_value=mock_translator),
                patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock),
            ):
                resp = await async_client.post("/api/ai/chat", json={
                    "message": "Tell me about home loans",
                    "history": [],
                })

            assert resp.status_code == 200
            data = resp.json()
            assert data["text"] == "Hindi chat answer."
            assert data["language"] == "hi"
            mock_translator.translate.assert_called_once_with("English chat answer.", "hi")
        finally:
            mock_user.preferred_language = original_lang

    async def test_chat_translates_telugu(self, async_client, mock_user):
        original_lang = mock_user.preferred_language
        mock_user.preferred_language = "te"
        try:
            mock_embed_svc = MagicMock()
            mock_embed_svc.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            mock_embed_repo = MagicMock()
            mock_embed_repo.similarity_search = AsyncMock(return_value=[])

            mock_ai = MagicMock()
            mock_ai.chat_with_history = AsyncMock(return_value=("English chat answer.", {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}))

            mock_translator = MagicMock()
            mock_translator.translate = AsyncMock(return_value="Telugu chat answer.")

            with (
                patch("app.api.routes.ai_insights.EmbeddingService", return_value=mock_embed_svc),
                patch("app.api.routes.ai_insights.EmbeddingRepository", return_value=mock_embed_repo),
                patch("app.api.routes.ai_insights.AIService", return_value=mock_ai),
                patch("app.api.routes.ai_insights.TranslatorService", return_value=mock_translator),
                patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock),
            ):
                resp = await async_client.post("/api/ai/chat", json={
                    "message": "Tell me about car loans",
                    "history": [],
                })

            assert resp.status_code == 200
            data = resp.json()
            assert data["text"] == "Telugu chat answer."
            assert data["language"] == "te"
            mock_translator.translate.assert_called_once_with("English chat answer.", "te")
        finally:
            mock_user.preferred_language = original_lang

    async def test_chat_empty_message(self, async_client):
        resp = await async_client.post("/api/ai/chat", json={
            "message": "",
            "history": [],
        })

        assert resp.status_code == 422

    async def test_chat_long_history(self, async_client):
        mock_embed_svc = MagicMock()
        mock_embed_svc.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

        mock_embed_repo = MagicMock()
        mock_embed_repo.similarity_search = AsyncMock(return_value=[])

        mock_ai = MagicMock()
        mock_ai.chat_with_history = AsyncMock(return_value=("Trimmed history answer.", {"prompt_tokens": 300, "completion_tokens": 60, "total_tokens": 360}))

        long_history = [
            {"role": "user", "content": f"Question {i}"}
            if i % 2 == 0
            else {"role": "assistant", "content": f"Answer {i}"}
            for i in range(10)
        ]

        with (
            patch("app.api.routes.ai_insights.EmbeddingService", return_value=mock_embed_svc),
            patch("app.api.routes.ai_insights.EmbeddingRepository", return_value=mock_embed_repo),
            patch("app.api.routes.ai_insights.AIService", return_value=mock_ai),
            patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock),
        ):
            resp = await async_client.post("/api/ai/chat", json={
                "message": "Latest question",
                "history": long_history,
            })

        assert resp.status_code == 200
        assert resp.json()["text"] == "Trimmed history answer."

        # Verify only last 6 history items were sent to AI
        call_kwargs = mock_ai.chat_with_history.call_args.kwargs
        assert len(call_kwargs["history"]) == 6
        # Last 6 items correspond to indices 4..9 of the original 10-item list
        expected_history = [
            ("user", "Question 4"),
            ("assistant", "Answer 5"),
            ("user", "Question 6"),
            ("assistant", "Answer 7"),
            ("user", "Question 8"),
            ("assistant", "Answer 9"),
        ]
        assert call_kwargs["history"] == expected_history
