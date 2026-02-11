"""End-to-end integration tests for /api/ai/* routes.

Tests the full route-to-service flow with mocked external services:
- AIService (OpenAI GPT-4o-mini)
- EmbeddingService (OpenAI text-embedding-3-small)
- TranslatorService (OpenAI-based translation)
- TTSService (stub — browser Web Speech API)

Coverage:
1. Create loan -> explain loan -> verify response
2. Explain optimizer strategy -> verify response
3. RAG Q&A via /api/ai/ask -> verify context-aware response
4. Chat conversation with history maintained across 3 messages
5. TTS: explain loan -> convert to speech -> verify base64 audio
6. Batch explain: 3 loans -> batch explain -> verify all insights
7. Hindi translation: user language=hi -> verify translated response
"""

import uuid
import base64
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.db.models import Loan, DocumentEmbedding
from tests.conftest import MOCK_USER_ID

MOCK_LOAN_ID_1 = uuid.UUID("00000000-0000-4000-a000-000000000050")
MOCK_LOAN_ID_2 = uuid.UUID("00000000-0000-4000-a000-000000000051")
MOCK_LOAN_ID_3 = uuid.UUID("00000000-0000-4000-a000-000000000052")


def _make_mock_loan(**overrides) -> MagicMock:
    """Create a mock Loan ORM object for AI integration tests."""
    loan = MagicMock(spec=Loan)
    defaults = dict(
        id=MOCK_LOAN_ID_1,
        user_id=MOCK_USER_ID,
        bank_name="SBI",
        loan_type="home",
        principal_amount=5000000.0,
        outstanding_principal=4500000.0,
        interest_rate=8.5,
        interest_rate_type="floating",
        tenure_months=240,
        remaining_tenure_months=220,
        emi_amount=43391.0,
        emi_due_date=5,
        prepayment_penalty_pct=0.0,
        foreclosure_charges_pct=0.0,
        eligible_80c=True,
        eligible_24b=True,
        eligible_80e=False,
        eligible_80eea=False,
        eligible_mortgage_deduction=False,
        eligible_student_loan_deduction=False,
        disbursement_date=None,
        status="active",
        source="manual",
        source_scan_id=None,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(loan, k, v)
    return loan


def _make_mock_embedding_result(chunk_text: str) -> MagicMock:
    """Create a mock DocumentEmbedding for similarity search results."""
    result = MagicMock(spec=DocumentEmbedding)
    result.chunk_text = chunk_text
    result.source_type = "rbi_guideline"
    result.source_id = "prepayment_2014"
    result.embedding = [0.0] * 1536
    return result


# ---------------------------------------------------------------------------
# 1. Create Loan -> Explain Loan -> Verify Response
# ---------------------------------------------------------------------------


class TestExplainLoan:
    """Tests for POST /api/ai/explain-loan — full route->service flow."""

    @pytest.mark.asyncio
    async def test_explain_loan_returns_ai_explanation(self, async_client: AsyncClient):
        """Create a loan via mock, then explain it via /api/ai/explain-loan."""
        mock_loan = _make_mock_loan(id=MOCK_LOAN_ID_1)
        mock_explanation = (
            "Your SBI home loan of Rs 50,00,000 has Rs 45,00,000 outstanding at 8.5% "
            "floating rate. Your EMI of Rs 43,391 currently pays mostly interest. "
            "Tip: Make extra payments to reduce your interest burden significantly."
        )
        mock_usage = {"prompt_tokens": 250, "completion_tokens": 80, "total_tokens": 330}

        with patch("app.api.routes.ai_insights.LoanRepository") as MockLoanRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_loan)
            MockLoanRepo.return_value = mock_repo

            mock_ai = MagicMock()
            mock_ai.explain_loan = AsyncMock(return_value=(mock_explanation, mock_usage))
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/explain-loan",
                headers={"Authorization": "Bearer token"},
                json={"loan_id": str(MOCK_LOAN_ID_1)},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == mock_explanation
        assert data["language"] == "en"

        # Verify the loan was fetched with correct params
        mock_repo.get_by_id.assert_called_once()
        call_args = mock_repo.get_by_id.call_args
        assert call_args.args[0] == MOCK_LOAN_ID_1
        assert call_args.args[1] == MOCK_USER_ID

        # Verify AI service received correct loan details
        mock_ai.explain_loan.assert_called_once()
        ai_kwargs = mock_ai.explain_loan.call_args.kwargs
        assert ai_kwargs["bank_name"] == "SBI"
        assert ai_kwargs["loan_type"] == "home"
        assert ai_kwargs["principal"] == 5000000.0
        assert ai_kwargs["outstanding"] == 4500000.0
        assert ai_kwargs["rate"] == 8.5
        assert ai_kwargs["rate_type"] == "floating"
        assert ai_kwargs["emi"] == 43391.0
        assert ai_kwargs["remaining_months"] == 220

    @pytest.mark.asyncio
    async def test_explain_loan_not_found_returns_404(self, async_client: AsyncClient):
        """Explain-loan with non-existent loan_id returns 404."""
        with patch("app.api.routes.ai_insights.LoanRepository") as MockLoanRepo:
            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            MockLoanRepo.return_value = mock_repo

            resp = await async_client.post(
                "/api/ai/explain-loan",
                headers={"Authorization": "Bearer token"},
                json={"loan_id": str(MOCK_LOAN_ID_1)},
            )

        assert resp.status_code == 404
        assert "Loan not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_explain_loan_tracks_usage(self, async_client: AsyncClient):
        """Explain-loan calls track_usage when usage data is returned."""
        mock_loan = _make_mock_loan(id=MOCK_LOAN_ID_1)
        mock_usage = {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}

        with patch("app.api.routes.ai_insights.LoanRepository") as MockLoanRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock) as mock_track:

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_loan)
            MockLoanRepo.return_value = mock_repo

            mock_ai = MagicMock()
            mock_ai.explain_loan = AsyncMock(return_value=("Explanation text", mock_usage))
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/explain-loan",
                headers={"Authorization": "Bearer token"},
                json={"loan_id": str(MOCK_LOAN_ID_1)},
            )

        assert resp.status_code == 200
        mock_track.assert_called_once()
        track_args = mock_track.call_args
        assert track_args.args[1] == "openai"
        assert track_args.args[2] == "chat"
        assert track_args.args[3] == MOCK_USER_ID


# ---------------------------------------------------------------------------
# 2. Explain Strategy -> Verify Response
# ---------------------------------------------------------------------------


class TestExplainStrategy:
    """Tests for POST /api/ai/explain-strategy — optimizer strategy explanation."""

    @pytest.mark.asyncio
    async def test_explain_strategy_returns_explanation(self, async_client: AsyncClient):
        """Explain an avalanche strategy with savings metrics."""
        mock_explanation = (
            "The Avalanche strategy focuses on paying off the highest-interest loan first. "
            "With an extra Rs 10,000/month, you'll save Rs 4,50,000 in interest and "
            "be debt-free 18 months sooner. Pay off: HDFC Personal -> ICICI Car -> SBI Home."
        )
        mock_usage = {"prompt_tokens": 180, "completion_tokens": 90, "total_tokens": 270}

        with patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_ai = MagicMock()
            mock_ai.explain_strategy = AsyncMock(return_value=(mock_explanation, mock_usage))
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/explain-strategy",
                headers={"Authorization": "Bearer token"},
                json={
                    "strategy_name": "avalanche",
                    "num_loans": 3,
                    "extra": 10000.0,
                    "interest_saved": 450000.0,
                    "months_saved": 18,
                    "payoff_order": ["HDFC Personal", "ICICI Car", "SBI Home"],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == mock_explanation
        assert data["language"] == "en"

        # Verify AI service received correct strategy params
        mock_ai.explain_strategy.assert_called_once()
        ai_kwargs = mock_ai.explain_strategy.call_args.kwargs
        assert ai_kwargs["strategy_name"] == "avalanche"
        assert ai_kwargs["num_loans"] == 3
        assert ai_kwargs["extra"] == 10000.0
        assert ai_kwargs["interest_saved"] == 450000.0
        assert ai_kwargs["months_saved"] == 18
        assert ai_kwargs["payoff_order"] == ["HDFC Personal", "ICICI Car", "SBI Home"]

    @pytest.mark.asyncio
    async def test_explain_strategy_snowball(self, async_client: AsyncClient):
        """Explain a snowball strategy (smallest balance first)."""
        mock_explanation = "Snowball strategy: Pay off smallest loan first for quick wins."
        mock_usage = {"prompt_tokens": 150, "completion_tokens": 60, "total_tokens": 210}

        with patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_ai = MagicMock()
            mock_ai.explain_strategy = AsyncMock(return_value=(mock_explanation, mock_usage))
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/explain-strategy",
                headers={"Authorization": "Bearer token"},
                json={
                    "strategy_name": "snowball",
                    "num_loans": 2,
                    "extra": 5000.0,
                    "interest_saved": 150000.0,
                    "months_saved": 8,
                    "payoff_order": ["ICICI Car", "SBI Home"],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == mock_explanation
        assert data["language"] == "en"


# ---------------------------------------------------------------------------
# 3. RAG Q&A via /api/ai/ask -> Verify Context-Aware Response
# ---------------------------------------------------------------------------


class TestAskRAG:
    """Tests for POST /api/ai/ask — RAG-powered Q&A with embeddings."""

    @pytest.mark.asyncio
    async def test_ask_returns_context_aware_answer(self, async_client: AsyncClient):
        """Ask a question -> embeddings retrieved -> AI answers with context."""
        mock_question = "Can I prepay my floating rate home loan without penalty?"
        mock_embedding = [0.1] * 1536
        mock_context_results = [
            _make_mock_embedding_result(
                "RBI Circular 2014: Banks cannot charge prepayment penalty on floating rate loans."
            ),
            _make_mock_embedding_result(
                "Floating rate loans include home, personal, car, and education loans."
            ),
            _make_mock_embedding_result(
                "Fixed rate loans may still have foreclosure charges (typically 2-5%)."
            ),
        ]
        mock_answer = (
            "Yes! As per RBI's 2014 circular, banks cannot charge any prepayment penalty "
            "on floating rate loans. Since your home loan is on a floating rate, you can "
            "make extra payments or foreclose at any time without any charges."
        )
        mock_usage = {"prompt_tokens": 350, "completion_tokens": 70, "total_tokens": 420}

        with patch("app.api.routes.ai_insights.EmbeddingService") as MockEmbed, \
             patch("app.api.routes.ai_insights.EmbeddingRepository") as MockEmbedRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_embed_svc = MagicMock()
            mock_embed_svc.generate_embedding = AsyncMock(return_value=mock_embedding)
            MockEmbed.return_value = mock_embed_svc

            mock_embed_repo = MagicMock()
            mock_embed_repo.similarity_search = AsyncMock(return_value=mock_context_results)
            MockEmbedRepo.return_value = mock_embed_repo

            mock_ai = MagicMock()
            mock_ai.ask_with_context = AsyncMock(return_value=(mock_answer, mock_usage))
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/ask",
                headers={"Authorization": "Bearer token"},
                json={"question": mock_question},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == mock_answer
        assert data["language"] == "en"

        # Verify embedding was generated from the question
        mock_embed_svc.generate_embedding.assert_called_once_with(mock_question)

        # Verify similarity search was called with the embedding
        mock_embed_repo.similarity_search.assert_called_once_with(mock_embedding, limit=3)

        # Verify AI received the context chunks
        mock_ai.ask_with_context.assert_called_once()
        ai_args = mock_ai.ask_with_context.call_args.args
        assert ai_args[0] == mock_question
        assert len(ai_args[1]) == 3
        assert "RBI Circular 2014" in ai_args[1][0]

    @pytest.mark.asyncio
    async def test_ask_with_no_matching_context(self, async_client: AsyncClient):
        """Ask question when no matching context is found -> AI still responds."""
        mock_embedding = [0.0] * 1536
        mock_answer = (
            "I don't have specific information about that, but here's what I know "
            "about Indian loans in general..."
        )

        with patch("app.api.routes.ai_insights.EmbeddingService") as MockEmbed, \
             patch("app.api.routes.ai_insights.EmbeddingRepository") as MockEmbedRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_embed_svc = MagicMock()
            mock_embed_svc.generate_embedding = AsyncMock(return_value=mock_embedding)
            MockEmbed.return_value = mock_embed_svc

            mock_embed_repo = MagicMock()
            mock_embed_repo.similarity_search = AsyncMock(return_value=[])
            MockEmbedRepo.return_value = mock_embed_repo

            mock_ai = MagicMock()
            mock_ai.ask_with_context = AsyncMock(return_value=(mock_answer, {}))
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/ask",
                headers={"Authorization": "Bearer token"},
                json={"question": "What is the best cryptocurrency to invest in?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == mock_answer
        # Even with no context, the AI should respond gracefully
        assert len(data["text"]) > 0


# ---------------------------------------------------------------------------
# 4. Chat Conversation: 3 Messages -> Verify History Maintained
# ---------------------------------------------------------------------------


class TestChatConversation:
    """Tests for POST /api/ai/chat — conversational RAG with history."""

    @pytest.mark.asyncio
    async def test_chat_first_message_no_history(self, async_client: AsyncClient):
        """First chat message with empty history works correctly."""
        mock_embedding = [0.2] * 1536
        mock_context = [
            _make_mock_embedding_result("EMI stands for Equated Monthly Installment.")
        ]
        mock_answer = "EMI is a fixed monthly payment you make to repay your loan."
        mock_usage = {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}

        with patch("app.api.routes.ai_insights.EmbeddingService") as MockEmbed, \
             patch("app.api.routes.ai_insights.EmbeddingRepository") as MockEmbedRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_embed_svc = MagicMock()
            mock_embed_svc.generate_embedding = AsyncMock(return_value=mock_embedding)
            MockEmbed.return_value = mock_embed_svc

            mock_embed_repo = MagicMock()
            mock_embed_repo.similarity_search = AsyncMock(return_value=mock_context)
            MockEmbedRepo.return_value = mock_embed_repo

            mock_ai = MagicMock()
            mock_ai.chat_with_history = AsyncMock(return_value=(mock_answer, mock_usage))
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/chat",
                headers={"Authorization": "Bearer token"},
                json={
                    "message": "What is EMI?",
                    "history": [],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == mock_answer
        assert data["language"] == "en"

        # Verify chat_with_history received empty history
        mock_ai.chat_with_history.assert_called_once()
        call_kwargs = mock_ai.chat_with_history.call_args.kwargs
        assert call_kwargs["message"] == "What is EMI?"
        assert call_kwargs["history"] == []
        assert call_kwargs["country"] == "IN"

    @pytest.mark.asyncio
    async def test_chat_three_messages_history_maintained(self, async_client: AsyncClient):
        """Send 3 sequential chat messages, verify history is passed correctly."""
        mock_embedding = [0.3] * 1536
        mock_context = [_make_mock_embedding_result("Loan context chunk")]

        # Message 1: No history
        answer_1 = "Your SBI home loan has an EMI of Rs 43,391."
        # Message 2: 1 exchange in history
        answer_2 = "To reduce EMI, you can make prepayments on the principal."
        # Message 3: 2 exchanges in history
        answer_3 = "Based on your SBI loan at 8.5%, a Rs 1 lakh prepayment would save Rs 2.5 lakh in interest."

        with patch("app.api.routes.ai_insights.EmbeddingService") as MockEmbed, \
             patch("app.api.routes.ai_insights.EmbeddingRepository") as MockEmbedRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_embed_svc = MagicMock()
            mock_embed_svc.generate_embedding = AsyncMock(return_value=mock_embedding)
            MockEmbed.return_value = mock_embed_svc

            mock_embed_repo = MagicMock()
            mock_embed_repo.similarity_search = AsyncMock(return_value=mock_context)
            MockEmbedRepo.return_value = mock_embed_repo

            mock_ai = MagicMock()
            mock_ai.chat_with_history = AsyncMock(
                side_effect=[
                    (answer_1, {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}),
                    (answer_2, {"prompt_tokens": 150, "completion_tokens": 40, "total_tokens": 190}),
                    (answer_3, {"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250}),
                ]
            )
            MockAI.return_value = mock_ai

            # --- Message 1: no history ---
            resp1 = await async_client.post(
                "/api/ai/chat",
                headers={"Authorization": "Bearer token"},
                json={
                    "message": "Tell me about my SBI home loan",
                    "history": [],
                },
            )
            assert resp1.status_code == 200
            assert resp1.json()["text"] == answer_1

            # --- Message 2: 1 exchange in history ---
            resp2 = await async_client.post(
                "/api/ai/chat",
                headers={"Authorization": "Bearer token"},
                json={
                    "message": "How can I reduce the EMI?",
                    "history": [
                        {"role": "user", "content": "Tell me about my SBI home loan"},
                        {"role": "assistant", "content": answer_1},
                    ],
                },
            )
            assert resp2.status_code == 200
            assert resp2.json()["text"] == answer_2

            # --- Message 3: 2 exchanges in history ---
            resp3 = await async_client.post(
                "/api/ai/chat",
                headers={"Authorization": "Bearer token"},
                json={
                    "message": "How much would a 1 lakh prepayment save?",
                    "history": [
                        {"role": "user", "content": "Tell me about my SBI home loan"},
                        {"role": "assistant", "content": answer_1},
                        {"role": "user", "content": "How can I reduce the EMI?"},
                        {"role": "assistant", "content": answer_2},
                    ],
                },
            )
            assert resp3.status_code == 200
            assert resp3.json()["text"] == answer_3

        # Verify chat_with_history was called 3 times with increasing history
        assert mock_ai.chat_with_history.call_count == 3

        # Verify first call had empty history
        first_call_kwargs = mock_ai.chat_with_history.call_args_list[0].kwargs
        assert first_call_kwargs["history"] == []

        # Verify second call had 1 exchange (2 messages)
        second_call_kwargs = mock_ai.chat_with_history.call_args_list[1].kwargs
        assert len(second_call_kwargs["history"]) == 2
        assert second_call_kwargs["history"][0] == ("user", "Tell me about my SBI home loan")
        assert second_call_kwargs["history"][1] == ("assistant", answer_1)

        # Verify third call had 2 exchanges (4 messages)
        third_call_kwargs = mock_ai.chat_with_history.call_args_list[2].kwargs
        assert len(third_call_kwargs["history"]) == 4
        assert third_call_kwargs["message"] == "How much would a 1 lakh prepayment save?"

    @pytest.mark.asyncio
    async def test_chat_history_truncated_to_last_6(self, async_client: AsyncClient):
        """Chat with >6 history items truncates to last 6 entries."""
        mock_embedding = [0.4] * 1536
        mock_context = [_make_mock_embedding_result("Context chunk")]
        mock_answer = "Here is my response."

        # Build 10 history items (5 exchanges)
        long_history = []
        for i in range(5):
            long_history.append({"role": "user", "content": f"Question {i+1}"})
            long_history.append({"role": "assistant", "content": f"Answer {i+1}"})

        with patch("app.api.routes.ai_insights.EmbeddingService") as MockEmbed, \
             patch("app.api.routes.ai_insights.EmbeddingRepository") as MockEmbedRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_embed_svc = MagicMock()
            mock_embed_svc.generate_embedding = AsyncMock(return_value=mock_embedding)
            MockEmbed.return_value = mock_embed_svc

            mock_embed_repo = MagicMock()
            mock_embed_repo.similarity_search = AsyncMock(return_value=mock_context)
            MockEmbedRepo.return_value = mock_embed_repo

            mock_ai = MagicMock()
            mock_ai.chat_with_history = AsyncMock(
                return_value=(mock_answer, {"prompt_tokens": 300, "completion_tokens": 20, "total_tokens": 320})
            )
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/chat",
                headers={"Authorization": "Bearer token"},
                json={
                    "message": "Next question",
                    "history": long_history,
                },
            )

        assert resp.status_code == 200

        # Route code truncates history to last 6: req.history[-6:]
        call_kwargs = mock_ai.chat_with_history.call_args.kwargs
        assert len(call_kwargs["history"]) == 6


# ---------------------------------------------------------------------------
# 5. TTS: Explain Loan -> Convert to Speech -> Verify Base64 Audio
# ---------------------------------------------------------------------------


class TestTTS:
    """Tests for POST /api/ai/tts — text-to-speech conversion."""

    @pytest.mark.asyncio
    async def test_tts_returns_base64_audio(self, async_client: AsyncClient):
        """TTS endpoint returns valid base64-encoded audio data."""
        # Simulate MP3 audio bytes encoded as base64
        fake_audio_bytes = b"fake mp3 audio content for testing"
        fake_audio_base64 = base64.b64encode(fake_audio_bytes).decode("utf-8")

        with patch("app.api.routes.ai_insights.TTSService") as MockTTS:
            mock_tts = MagicMock()
            mock_tts.generate_audio = AsyncMock(return_value=fake_audio_base64)
            MockTTS.return_value = mock_tts

            resp = await async_client.post(
                "/api/ai/tts",
                headers={"Authorization": "Bearer token"},
                json={
                    "text": "Your SBI home loan EMI is Rs 43,391 per month.",
                    "language": "en",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_base64"] == fake_audio_base64
        assert data["language"] == "en"

        # Verify the base64 is decodable
        decoded = base64.b64decode(data["audio_base64"])
        assert decoded == fake_audio_bytes

        # Verify TTS service was called with correct params
        mock_tts.generate_audio.assert_called_once_with(
            "Your SBI home loan EMI is Rs 43,391 per month.", "en"
        )

    @pytest.mark.asyncio
    async def test_tts_hindi_audio(self, async_client: AsyncClient):
        """TTS in Hindi language generates audio with correct language param."""
        fake_audio_base64 = base64.b64encode(b"hindi mp3 content").decode("utf-8")

        with patch("app.api.routes.ai_insights.TTSService") as MockTTS:
            mock_tts = MagicMock()
            mock_tts.generate_audio = AsyncMock(return_value=fake_audio_base64)
            MockTTS.return_value = mock_tts

            resp = await async_client.post(
                "/api/ai/tts",
                headers={"Authorization": "Bearer token"},
                json={
                    "text": "Aapka ghar ka loan ka EMI Rs 43,391 hai.",
                    "language": "hi",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_base64"] == fake_audio_base64
        assert data["language"] == "hi"

        mock_tts.generate_audio.assert_called_once_with(
            "Aapka ghar ka loan ka EMI Rs 43,391 hai.", "hi"
        )

    @pytest.mark.asyncio
    async def test_tts_service_failure_returns_null_audio(self, async_client: AsyncClient):
        """TTS service returning None (failure) is handled gracefully."""
        with patch("app.api.routes.ai_insights.TTSService") as MockTTS:
            mock_tts = MagicMock()
            mock_tts.generate_audio = AsyncMock(return_value=None)
            MockTTS.return_value = mock_tts

            resp = await async_client.post(
                "/api/ai/tts",
                headers={"Authorization": "Bearer token"},
                json={
                    "text": "Some text to speak",
                    "language": "en",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_base64"] is None
        assert data["language"] == "en"

    @pytest.mark.asyncio
    async def test_tts_explain_then_speak_flow(self, async_client: AsyncClient):
        """E2E flow: explain loan -> take text -> convert to speech."""
        mock_loan = _make_mock_loan(id=MOCK_LOAN_ID_1)
        explanation_text = "Your home loan at SBI has Rs 45 lakh outstanding."
        mock_usage = {"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250}
        fake_audio = base64.b64encode(b"synthesized audio").decode("utf-8")

        # Step 1: Get explanation
        with patch("app.api.routes.ai_insights.LoanRepository") as MockLoanRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_loan)
            MockLoanRepo.return_value = mock_repo

            mock_ai = MagicMock()
            mock_ai.explain_loan = AsyncMock(return_value=(explanation_text, mock_usage))
            MockAI.return_value = mock_ai

            explain_resp = await async_client.post(
                "/api/ai/explain-loan",
                headers={"Authorization": "Bearer token"},
                json={"loan_id": str(MOCK_LOAN_ID_1)},
            )

        assert explain_resp.status_code == 200
        returned_text = explain_resp.json()["text"]

        # Step 2: Convert explanation to speech
        with patch("app.api.routes.ai_insights.TTSService") as MockTTS:
            mock_tts = MagicMock()
            mock_tts.generate_audio = AsyncMock(return_value=fake_audio)
            MockTTS.return_value = mock_tts

            tts_resp = await async_client.post(
                "/api/ai/tts",
                headers={"Authorization": "Bearer token"},
                json={"text": returned_text, "language": "en"},
            )

        assert tts_resp.status_code == 200
        tts_data = tts_resp.json()
        assert tts_data["audio_base64"] == fake_audio
        assert tts_data["language"] == "en"

        # Verify the text passed to TTS matches the explanation
        mock_tts.generate_audio.assert_called_once_with(explanation_text, "en")


# ---------------------------------------------------------------------------
# 6. Batch Explain: 3 Loans -> Batch Explain -> Verify All Insights
# ---------------------------------------------------------------------------


class TestBatchExplain:
    """Tests for POST /api/ai/explain-loans-batch — parallel batch explanations."""

    @pytest.mark.asyncio
    async def test_batch_explain_three_loans(self, async_client: AsyncClient):
        """Batch explain 3 loans returns insights for all 3."""
        loan_1 = _make_mock_loan(
            id=MOCK_LOAN_ID_1, bank_name="SBI", loan_type="home",
            outstanding_principal=4500000.0, interest_rate=8.5,
        )
        loan_2 = _make_mock_loan(
            id=MOCK_LOAN_ID_2, bank_name="HDFC", loan_type="personal",
            outstanding_principal=900000.0, interest_rate=12.0,
        )
        loan_3 = _make_mock_loan(
            id=MOCK_LOAN_ID_3, bank_name="ICICI", loan_type="car",
            outstanding_principal=700000.0, interest_rate=9.5,
        )

        explanations = {
            str(MOCK_LOAN_ID_1): "SBI home loan: Rs 45 lakh at 8.5%, good rate for home loan.",
            str(MOCK_LOAN_ID_2): "HDFC personal loan: Rs 9 lakh at 12%, consider prepaying.",
            str(MOCK_LOAN_ID_3): "ICICI car loan: Rs 7 lakh at 9.5%, moderate interest burden.",
        }
        mock_usage = {"prompt_tokens": 200, "completion_tokens": 60, "total_tokens": 260}

        # The route calls repo.get_by_id for each loan_id individually
        loan_map = {
            MOCK_LOAN_ID_1: loan_1,
            MOCK_LOAN_ID_2: loan_2,
            MOCK_LOAN_ID_3: loan_3,
        }

        async def mock_get_by_id(loan_id, user_id):
            return loan_map.get(loan_id)

        # ai.explain_loan is called once per loan; we use side_effect
        async def mock_explain_loan(**kwargs):
            bank = kwargs["bank_name"]
            if bank == "SBI":
                return explanations[str(MOCK_LOAN_ID_1)], mock_usage
            elif bank == "HDFC":
                return explanations[str(MOCK_LOAN_ID_2)], mock_usage
            else:
                return explanations[str(MOCK_LOAN_ID_3)], mock_usage

        with patch("app.api.routes.ai_insights.LoanRepository") as MockLoanRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(side_effect=mock_get_by_id)
            MockLoanRepo.return_value = mock_repo

            mock_ai = MagicMock()
            mock_ai.explain_loan = AsyncMock(side_effect=mock_explain_loan)
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/explain-loans-batch",
                headers={"Authorization": "Bearer token"},
                json={
                    "loan_ids": [
                        str(MOCK_LOAN_ID_1),
                        str(MOCK_LOAN_ID_2),
                        str(MOCK_LOAN_ID_3),
                    ],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["language"] == "en"
        assert len(data["insights"]) == 3

        # Verify each loan has its insight
        insights_by_id = {i["loan_id"]: i["text"] for i in data["insights"]}
        assert str(MOCK_LOAN_ID_1) in insights_by_id
        assert str(MOCK_LOAN_ID_2) in insights_by_id
        assert str(MOCK_LOAN_ID_3) in insights_by_id

        assert "SBI home loan" in insights_by_id[str(MOCK_LOAN_ID_1)]
        assert "HDFC personal loan" in insights_by_id[str(MOCK_LOAN_ID_2)]
        assert "ICICI car loan" in insights_by_id[str(MOCK_LOAN_ID_3)]

    @pytest.mark.asyncio
    async def test_batch_explain_missing_loan_returns_not_found_text(self, async_client: AsyncClient):
        """Batch explain with a non-existent loan returns 'Loan not found' for that entry."""
        loan_1 = _make_mock_loan(id=MOCK_LOAN_ID_1, bank_name="SBI")
        non_existent_id = uuid.UUID("00000000-0000-4000-a000-999999999999")
        mock_usage = {"prompt_tokens": 200, "completion_tokens": 60, "total_tokens": 260}

        async def mock_get_by_id(loan_id, user_id):
            if loan_id == MOCK_LOAN_ID_1:
                return loan_1
            return None

        with patch("app.api.routes.ai_insights.LoanRepository") as MockLoanRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(side_effect=mock_get_by_id)
            MockLoanRepo.return_value = mock_repo

            mock_ai = MagicMock()
            mock_ai.explain_loan = AsyncMock(return_value=("SBI explanation", mock_usage))
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/explain-loans-batch",
                headers={"Authorization": "Bearer token"},
                json={
                    "loan_ids": [str(MOCK_LOAN_ID_1), str(non_existent_id)],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["insights"]) == 2

        insights_by_id = {i["loan_id"]: i["text"] for i in data["insights"]}
        assert "SBI explanation" in insights_by_id[str(MOCK_LOAN_ID_1)]
        assert insights_by_id[str(non_existent_id)] == "Loan not found"

    @pytest.mark.asyncio
    async def test_batch_explain_single_loan(self, async_client: AsyncClient):
        """Batch explain with a single loan returns exactly 1 insight."""
        loan = _make_mock_loan(id=MOCK_LOAN_ID_1)
        mock_usage = {"prompt_tokens": 200, "completion_tokens": 60, "total_tokens": 260}

        with patch("app.api.routes.ai_insights.LoanRepository") as MockLoanRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=loan)
            MockLoanRepo.return_value = mock_repo

            mock_ai = MagicMock()
            mock_ai.explain_loan = AsyncMock(return_value=("Single loan insight", mock_usage))
            MockAI.return_value = mock_ai

            resp = await async_client.post(
                "/api/ai/explain-loans-batch",
                headers={"Authorization": "Bearer token"},
                json={"loan_ids": [str(MOCK_LOAN_ID_1)]},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["insights"]) == 1
        assert data["insights"][0]["loan_id"] == str(MOCK_LOAN_ID_1)
        assert data["insights"][0]["text"] == "Single loan insight"


# ---------------------------------------------------------------------------
# 7. Hindi Translation: Set User Language to HI -> Verify Translated
# ---------------------------------------------------------------------------


class TestHindiTranslation:
    """Tests for translation flow when user preferred_language is Hindi."""

    @pytest.mark.asyncio
    async def test_explain_loan_hindi_translation(self, async_client: AsyncClient, mock_user):
        """Explain loan with user language=hi triggers TranslatorService."""
        # Set user to prefer Hindi
        mock_user.preferred_language = "hi"

        mock_loan = _make_mock_loan(id=MOCK_LOAN_ID_1)
        english_explanation = "Your SBI home loan has Rs 45 lakh outstanding at 8.5%."
        hindi_translation = "Aapka SBI ghar ka loan Rs 45 lakh baki hai 8.5% par."
        mock_usage = {"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250}

        with patch("app.api.routes.ai_insights.LoanRepository") as MockLoanRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.TranslatorService") as MockTranslator, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_loan)
            MockLoanRepo.return_value = mock_repo

            mock_ai = MagicMock()
            mock_ai.explain_loan = AsyncMock(return_value=(english_explanation, mock_usage))
            MockAI.return_value = mock_ai

            mock_translator = MagicMock()
            mock_translator.translate = AsyncMock(return_value=hindi_translation)
            MockTranslator.return_value = mock_translator

            resp = await async_client.post(
                "/api/ai/explain-loan",
                headers={"Authorization": "Bearer token"},
                json={"loan_id": str(MOCK_LOAN_ID_1)},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == hindi_translation
        assert data["language"] == "hi"

        # Verify translator was called with the English text and target language
        mock_translator.translate.assert_called_once_with(english_explanation, "hi")

        # Reset user language for other tests
        mock_user.preferred_language = "en"

    @pytest.mark.asyncio
    async def test_explain_strategy_hindi_translation(self, async_client: AsyncClient, mock_user):
        """Explain strategy with user language=hi triggers translation."""
        mock_user.preferred_language = "hi"

        english_text = "Avalanche strategy: Pay highest interest loan first."
        hindi_text = "Avalanche strategy: Sabse zyada byaj wala loan pehle bharo."
        mock_usage = {"prompt_tokens": 150, "completion_tokens": 40, "total_tokens": 190}

        with patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.TranslatorService") as MockTranslator, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_ai = MagicMock()
            mock_ai.explain_strategy = AsyncMock(return_value=(english_text, mock_usage))
            MockAI.return_value = mock_ai

            mock_translator = MagicMock()
            mock_translator.translate = AsyncMock(return_value=hindi_text)
            MockTranslator.return_value = mock_translator

            resp = await async_client.post(
                "/api/ai/explain-strategy",
                headers={"Authorization": "Bearer token"},
                json={
                    "strategy_name": "avalanche",
                    "num_loans": 2,
                    "extra": 10000.0,
                    "interest_saved": 300000.0,
                    "months_saved": 12,
                    "payoff_order": ["HDFC Personal", "SBI Home"],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == hindi_text
        assert data["language"] == "hi"

        mock_translator.translate.assert_called_once_with(english_text, "hi")
        mock_user.preferred_language = "en"

    @pytest.mark.asyncio
    async def test_ask_hindi_translation(self, async_client: AsyncClient, mock_user):
        """Ask endpoint with user language=hi translates the answer."""
        mock_user.preferred_language = "hi"

        mock_embedding = [0.5] * 1536
        mock_context = [_make_mock_embedding_result("RBI rules context")]
        english_answer = "You can prepay without penalty on floating rate loans."
        hindi_answer = "Aap floating rate loans par bina penalty ke prepay kar sakte hain."
        mock_usage = {"prompt_tokens": 250, "completion_tokens": 40, "total_tokens": 290}

        with patch("app.api.routes.ai_insights.EmbeddingService") as MockEmbed, \
             patch("app.api.routes.ai_insights.EmbeddingRepository") as MockEmbedRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.TranslatorService") as MockTranslator, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_embed_svc = MagicMock()
            mock_embed_svc.generate_embedding = AsyncMock(return_value=mock_embedding)
            MockEmbed.return_value = mock_embed_svc

            mock_embed_repo = MagicMock()
            mock_embed_repo.similarity_search = AsyncMock(return_value=mock_context)
            MockEmbedRepo.return_value = mock_embed_repo

            mock_ai = MagicMock()
            mock_ai.ask_with_context = AsyncMock(return_value=(english_answer, mock_usage))
            MockAI.return_value = mock_ai

            mock_translator = MagicMock()
            mock_translator.translate = AsyncMock(return_value=hindi_answer)
            MockTranslator.return_value = mock_translator

            resp = await async_client.post(
                "/api/ai/ask",
                headers={"Authorization": "Bearer token"},
                json={"question": "Can I prepay my loan?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == hindi_answer
        assert data["language"] == "hi"

        mock_translator.translate.assert_called_once_with(english_answer, "hi")
        mock_user.preferred_language = "en"

    @pytest.mark.asyncio
    async def test_chat_hindi_translation(self, async_client: AsyncClient, mock_user):
        """Chat endpoint with user language=hi translates the response."""
        mock_user.preferred_language = "hi"

        mock_embedding = [0.6] * 1536
        mock_context = [_make_mock_embedding_result("Context chunk")]
        english_answer = "Your loan EMI can be reduced by making prepayments."
        hindi_answer = "Aapka loan EMI prepayments karke kam kiya ja sakta hai."
        mock_usage = {"prompt_tokens": 200, "completion_tokens": 40, "total_tokens": 240}

        with patch("app.api.routes.ai_insights.EmbeddingService") as MockEmbed, \
             patch("app.api.routes.ai_insights.EmbeddingRepository") as MockEmbedRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.TranslatorService") as MockTranslator, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_embed_svc = MagicMock()
            mock_embed_svc.generate_embedding = AsyncMock(return_value=mock_embedding)
            MockEmbed.return_value = mock_embed_svc

            mock_embed_repo = MagicMock()
            mock_embed_repo.similarity_search = AsyncMock(return_value=mock_context)
            MockEmbedRepo.return_value = mock_embed_repo

            mock_ai = MagicMock()
            mock_ai.chat_with_history = AsyncMock(return_value=(english_answer, mock_usage))
            MockAI.return_value = mock_ai

            mock_translator = MagicMock()
            mock_translator.translate = AsyncMock(return_value=hindi_answer)
            MockTranslator.return_value = mock_translator

            resp = await async_client.post(
                "/api/ai/chat",
                headers={"Authorization": "Bearer token"},
                json={
                    "message": "Mere loan ka EMI kaise kam karein?",
                    "history": [],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == hindi_answer
        assert data["language"] == "hi"

        mock_translator.translate.assert_called_once_with(english_answer, "hi")
        mock_user.preferred_language = "en"

    @pytest.mark.asyncio
    async def test_batch_explain_hindi_translation(self, async_client: AsyncClient, mock_user):
        """Batch explain with user language=hi translates all insights."""
        mock_user.preferred_language = "hi"

        loan_1 = _make_mock_loan(id=MOCK_LOAN_ID_1, bank_name="SBI")
        loan_2 = _make_mock_loan(id=MOCK_LOAN_ID_2, bank_name="HDFC")
        mock_usage = {"prompt_tokens": 200, "completion_tokens": 60, "total_tokens": 260}

        async def mock_get_by_id(loan_id, user_id):
            if loan_id == MOCK_LOAN_ID_1:
                return loan_1
            return loan_2

        call_count = 0

        async def mock_translate(text, lang):
            return f"[HI] {text}"

        with patch("app.api.routes.ai_insights.LoanRepository") as MockLoanRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.TranslatorService") as MockTranslator, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(side_effect=mock_get_by_id)
            MockLoanRepo.return_value = mock_repo

            mock_ai = MagicMock()
            mock_ai.explain_loan = AsyncMock(return_value=("English insight", mock_usage))
            MockAI.return_value = mock_ai

            mock_translator = MagicMock()
            mock_translator.translate = AsyncMock(side_effect=mock_translate)
            MockTranslator.return_value = mock_translator

            resp = await async_client.post(
                "/api/ai/explain-loans-batch",
                headers={"Authorization": "Bearer token"},
                json={
                    "loan_ids": [str(MOCK_LOAN_ID_1), str(MOCK_LOAN_ID_2)],
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["language"] == "hi"
        assert len(data["insights"]) == 2

        # All insights should have been translated (prefixed with [HI])
        for insight in data["insights"]:
            assert insight["text"].startswith("[HI]")

        # Translator should have been called once per insight
        assert mock_translator.translate.call_count == 2
        mock_user.preferred_language = "en"

    @pytest.mark.asyncio
    async def test_english_user_skips_translation(self, async_client: AsyncClient, mock_user):
        """User with preferred_language=en does NOT trigger translation."""
        mock_user.preferred_language = "en"

        mock_loan = _make_mock_loan(id=MOCK_LOAN_ID_1)
        english_text = "Your loan explanation in English."
        mock_usage = {"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250}

        with patch("app.api.routes.ai_insights.LoanRepository") as MockLoanRepo, \
             patch("app.api.routes.ai_insights.AIService") as MockAI, \
             patch("app.api.routes.ai_insights.TranslatorService") as MockTranslator, \
             patch("app.api.routes.ai_insights.track_usage", new_callable=AsyncMock):

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_loan)
            MockLoanRepo.return_value = mock_repo

            mock_ai = MagicMock()
            mock_ai.explain_loan = AsyncMock(return_value=(english_text, mock_usage))
            MockAI.return_value = mock_ai

            mock_translator = MagicMock()
            MockTranslator.return_value = mock_translator

            resp = await async_client.post(
                "/api/ai/explain-loan",
                headers={"Authorization": "Bearer token"},
                json={"loan_id": str(MOCK_LOAN_ID_1)},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == english_text
        assert data["language"] == "en"

        # TranslatorService constructor may be called, but translate should NOT be called
        # because user language is "en"
        MockTranslator.return_value.translate.assert_not_called()
