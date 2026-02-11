"""Tests for app.services.ai_service — OpenAI GPT integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixture: build an AIService with client=None (not configured)
# ---------------------------------------------------------------------------


@pytest.fixture
def unconfigured_ai_service():
    """AIService with no OpenAI credentials (client=None)."""
    with patch("app.services.ai_service.settings") as mock_settings:
        mock_settings.openai_api_key = ""
        mock_settings.openai_model = "gpt-4o-mini"
        from app.services.ai_service import AIService

        svc = AIService()
        assert svc.client is None
        return svc


@pytest.fixture
def configured_ai_service():
    """AIService with a mocked AsyncOpenAI client."""
    with patch("app.services.ai_service.settings") as mock_settings:
        mock_settings.openai_api_key = "sk-fake-key"
        mock_settings.openai_model = "gpt-4o-mini"

        with patch("app.services.ai_service.AsyncOpenAI") as MockClient:
            mock_client_instance = AsyncMock()
            MockClient.return_value = mock_client_instance

            from app.services.ai_service import AIService

            svc = AIService()
            svc.client = mock_client_instance
            svc.model = "gpt-4o-mini"
            return svc


# ---------------------------------------------------------------------------
# Tests: unconfigured service returns fallback messages
# ---------------------------------------------------------------------------


class TestAIServiceNotConfigured:
    """When OpenAI is not configured, all methods return a fallback."""

    @pytest.mark.asyncio
    async def test_explain_loan_not_configured(self, unconfigured_ai_service):
        text, usage = await unconfigured_ai_service.explain_loan(
            bank_name="SBI",
            loan_type="home",
            principal=5000000,
            outstanding=4500000,
            rate=8.5,
            rate_type="floating",
            emi=43391,
            remaining_months=220,
        )
        assert "not configured" in text.lower()
        assert usage == {}

    @pytest.mark.asyncio
    async def test_explain_strategy_not_configured(self, unconfigured_ai_service):
        text, usage = await unconfigured_ai_service.explain_strategy(
            strategy_name="Avalanche",
            num_loans=3,
            extra=10000,
            interest_saved=250000,
            months_saved=18,
            payoff_order=["HDFC Personal", "ICICI Car", "SBI Home"],
        )
        assert "not configured" in text.lower()
        assert usage == {}

    @pytest.mark.asyncio
    async def test_ask_with_context_not_configured(self, unconfigured_ai_service):
        text, usage = await unconfigured_ai_service.ask_with_context(
            question="What is the RBI rule on prepayment?",
            context_chunks=["Some context"],
        )
        assert "not configured" in text.lower()
        assert usage == {}


# ---------------------------------------------------------------------------
# Tests: configured service — error handling
# ---------------------------------------------------------------------------


class TestAIServiceErrorHandling:
    """When the OpenAI client raises, the service returns an error message."""

    @pytest.mark.asyncio
    async def test_chat_error_handling(self, configured_ai_service):
        """Mock client.chat.completions.create to raise an exception."""
        configured_ai_service.client.chat.completions.create = AsyncMock(
            side_effect=Exception("API rate limit exceeded")
        )

        text, usage = await configured_ai_service.explain_loan(
            bank_name="SBI",
            loan_type="home",
            principal=5000000,
            outstanding=4500000,
            rate=8.5,
            rate_type="floating",
            emi=43391,
            remaining_months=220,
        )
        assert "couldn't generate" in text.lower() or "error" in text.lower()
        assert usage == {}

    @pytest.mark.asyncio
    async def test_chat_success(self, configured_ai_service):
        """A successful chat completion returns the model content and usage."""
        mock_choice = MagicMock()
        mock_choice.message.content = "Your SBI home loan explanation..."
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_usage.total_tokens = 150
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        text, usage = await configured_ai_service.explain_loan(
            bank_name="SBI",
            loan_type="home",
            principal=5000000,
            outstanding=4500000,
            rate=8.5,
            rate_type="floating",
            emi=43391,
            remaining_months=220,
        )
        assert text == "Your SBI home loan explanation..."
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50

    @pytest.mark.asyncio
    async def test_chat_empty_content(self, configured_ai_service):
        """If the model returns None content, result should be empty string."""
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 0
        mock_usage.total_tokens = 10
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        text, usage = await configured_ai_service.explain_loan(
            bank_name="SBI",
            loan_type="home",
            principal=5000000,
            outstanding=4500000,
            rate=8.5,
            rate_type="floating",
            emi=43391,
            remaining_months=220,
        )
        assert text == ""
        assert usage["total_tokens"] == 10


# ---------------------------------------------------------------------------
# Helper: build a mock OpenAI response
# ---------------------------------------------------------------------------


def _make_mock_response(content: str, prompt_tokens: int = 80, completion_tokens: int = 40):
    """Create a mock chat completion response with the given content and usage."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = prompt_tokens
    mock_usage.completion_tokens = completion_tokens
    mock_usage.total_tokens = prompt_tokens + completion_tokens
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    return mock_response


# ---------------------------------------------------------------------------
# Tests: chat_with_history
# ---------------------------------------------------------------------------


class TestChatWithHistory:
    """Tests for the chat_with_history method."""

    @pytest.mark.asyncio
    async def test_basic_conversation(self, configured_ai_service):
        """A basic conversation with history returns the model's reply and usage."""
        mock_response = _make_mock_response("Here's how EMI works...")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        history = [
            ("user", "Hi, I have a home loan"),
            ("assistant", "Hello! I can help with that."),
        ]
        text, usage = await configured_ai_service.chat_with_history(
            message="How does EMI work?",
            history=history,
            context_chunks=[],
        )

        assert text == "Here's how EMI works..."
        assert usage["prompt_tokens"] == 80
        assert usage["completion_tokens"] == 40
        assert usage["total_tokens"] == 120

        # Verify messages sent to the API
        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        # system + 2 history + 1 user = 4 messages
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1] == {"role": "user", "content": "Hi, I have a home loan"}
        assert messages[2] == {"role": "assistant", "content": "Hello! I can help with that."}
        assert messages[3] == {"role": "user", "content": "How does EMI work?"}

    @pytest.mark.asyncio
    async def test_with_context_chunks_injected(self, configured_ai_service):
        """When context chunks are provided, they are injected into the system prompt."""
        mock_response = _make_mock_response("RBI says prepayment is free for floating rate.")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        context = [
            "RBI mandates zero prepayment penalty on floating rate loans.",
            "Fixed rate loans may have up to 2% prepayment charge.",
        ]
        text, usage = await configured_ai_service.chat_with_history(
            message="Can I prepay without penalty?",
            history=[],
            context_chunks=context,
        )

        assert text == "RBI says prepayment is free for floating rate."

        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        system_content = messages[0]["content"]
        assert "RBI mandates zero prepayment penalty" in system_content
        assert "Fixed rate loans may have up to 2%" in system_content
        assert "---" in system_content
        assert "knowledge base context" in system_content

    @pytest.mark.asyncio
    async def test_empty_history(self, configured_ai_service):
        """When history is empty, only system + user message are sent."""
        mock_response = _make_mock_response("Sure, ask me anything about loans!")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        text, usage = await configured_ai_service.chat_with_history(
            message="Hello",
            history=[],
            context_chunks=[],
        )

        assert text == "Sure, ask me anything about loans!"

        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1] == {"role": "user", "content": "Hello"}

    @pytest.mark.asyncio
    async def test_all_history_entries_forwarded(self, configured_ai_service):
        """The service forwards ALL history entries to the API."""
        mock_response = _make_mock_response("Here's your answer.")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        history = [
            ("user", f"Question {i}")
            if i % 2 == 0
            else ("assistant", f"Answer {i}")
            for i in range(8)
        ]

        text, _ = await configured_ai_service.chat_with_history(
            message="Final question",
            history=history,
            context_chunks=[],
        )

        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        assert len(messages) == 10
        assert messages[0]["role"] == "system"
        assert messages[-1] == {"role": "user", "content": "Final question"}
        for i in range(8):
            expected_content = f"Question {i}" if i % 2 == 0 else f"Answer {i}"
            assert messages[i + 1]["content"] == expected_content

    @pytest.mark.asyncio
    async def test_not_configured(self, unconfigured_ai_service):
        """chat_with_history returns fallback when client is None."""
        text, usage = await unconfigured_ai_service.chat_with_history(
            message="Hello",
            history=[],
            context_chunks=[],
        )
        assert "not configured" in text.lower()
        assert usage == {}

    @pytest.mark.asyncio
    async def test_api_error_handling(self, configured_ai_service):
        """chat_with_history returns an error message when the API call fails."""
        configured_ai_service.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Connection timeout")
        )

        text, usage = await configured_ai_service.chat_with_history(
            message="Hello",
            history=[("user", "Hi")],
            context_chunks=[],
        )
        assert "couldn't process" in text.lower() or "error" in text.lower()
        assert usage == {}


# ---------------------------------------------------------------------------
# Tests: explain_loan — country-aware system prompts
# ---------------------------------------------------------------------------


class TestExplainLoanCountryContext:
    """Verify that explain_loan picks the correct system prompt for each country."""

    @pytest.mark.asyncio
    async def test_us_country_uses_us_system_prompt(self, configured_ai_service):
        mock_response = _make_mock_response("Your mortgage explanation...")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        await configured_ai_service.explain_loan(
            bank_name="Chase",
            loan_type="mortgage",
            principal=300000,
            outstanding=280000,
            rate=6.5,
            rate_type="fixed",
            emi=1896,
            remaining_months=348,
            country="US",
        )

        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        system_content = messages[0]["content"]
        assert "American" in system_content
        assert "$" in system_content or "US numbering" in system_content

        user_content = messages[1]["content"]
        assert "$" in user_content
        assert "tax deductions" in user_content

    @pytest.mark.asyncio
    async def test_in_country_uses_india_system_prompt(self, configured_ai_service):
        mock_response = _make_mock_response("Your SBI home loan explanation...")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        await configured_ai_service.explain_loan(
            bank_name="SBI",
            loan_type="home",
            principal=5000000,
            outstanding=4500000,
            rate=8.5,
            rate_type="floating",
            emi=43391,
            remaining_months=220,
            country="IN",
        )

        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        system_content = messages[0]["content"]
        assert "Indian" in system_content
        assert "\u20b9" in system_content or "Indian numbering" in system_content

        user_content = messages[1]["content"]
        assert "\u20b9" in user_content


# ---------------------------------------------------------------------------
# Tests: explain_strategy — relay-race metaphor
# ---------------------------------------------------------------------------


class TestExplainStrategy:

    @pytest.mark.asyncio
    async def test_includes_relay_race_metaphor(self, configured_ai_service):
        mock_response = _make_mock_response("Great strategy! Think of it like a relay race...")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        await configured_ai_service.explain_strategy(
            strategy_name="Avalanche",
            num_loans=3,
            extra=10000,
            interest_saved=250000,
            months_saved=18,
            payoff_order=["HDFC Personal", "ICICI Car", "SBI Home"],
            country="IN",
        )

        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[1]["content"]
        assert "relay race" in user_content.lower()
        assert "baton" in user_content.lower()
        assert "HDFC Personal" in user_content
        assert "\u2192" in user_content

    @pytest.mark.asyncio
    async def test_us_strategy_also_has_relay_metaphor(self, configured_ai_service):
        mock_response = _make_mock_response("Think of a relay race!")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        await configured_ai_service.explain_strategy(
            strategy_name="Snowball",
            num_loans=2,
            extra=500,
            interest_saved=8000,
            months_saved=12,
            payoff_order=["Credit Card", "Student Loan"],
            country="US",
        )

        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[1]["content"]
        assert "relay race" in user_content.lower()
        assert "$" in user_content


# ---------------------------------------------------------------------------
# Tests: ask_with_context — RAG Q&A
# ---------------------------------------------------------------------------


class TestAskWithContext:

    @pytest.mark.asyncio
    async def test_uses_context_in_prompt(self, configured_ai_service):
        mock_response = _make_mock_response("Based on the knowledge base...")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        chunks = [
            "Section 80C allows deduction up to 1.5L on principal.",
            "Section 24(b) allows deduction up to 2L on interest.",
        ]
        text, usage = await configured_ai_service.ask_with_context(
            question="What tax benefits can I get?",
            context_chunks=chunks,
            country="IN",
        )

        assert text == "Based on the knowledge base..."

        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        assert "Indian" in messages[0]["content"]
        user_content = messages[1]["content"]
        assert "Section 80C" in user_content
        assert "Section 24(b)" in user_content
        assert "What tax benefits can I get?" in user_content

    @pytest.mark.asyncio
    async def test_empty_context_uses_fallback(self, configured_ai_service):
        mock_response = _make_mock_response("I don't have specific information...")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        await configured_ai_service.ask_with_context(
            question="Tell me about PMAY",
            context_chunks=[],
            country="IN",
        )

        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[1]["content"]
        assert "No relevant context found" in user_content

    @pytest.mark.asyncio
    async def test_us_context_uses_us_prompts(self, configured_ai_service):
        mock_response = _make_mock_response("In the US, you can deduct...")
        configured_ai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        await configured_ai_service.ask_with_context(
            question="Can I deduct mortgage interest?",
            context_chunks=["Mortgage interest deduction is available for itemizers."],
            country="US",
        )

        call_kwargs = configured_ai_service.client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        assert "American" in messages[0]["content"]
        assert "Mortgage interest deduction" in messages[1]["content"]


# ---------------------------------------------------------------------------
# Tests: graceful handling when OpenAI is not configured
# ---------------------------------------------------------------------------


class TestServiceGracefullyHandlesNotConfigured:

    @pytest.mark.asyncio
    async def test_all_methods_return_fallback(self, unconfigured_ai_service):
        svc = unconfigured_ai_service

        text, usage = await svc.explain_loan(
            bank_name="SBI", loan_type="home", principal=5000000,
            outstanding=4500000, rate=8.5, rate_type="floating",
            emi=43391, remaining_months=220,
        )
        assert "not configured" in text.lower()
        assert usage == {}

        text, usage = await svc.explain_strategy(
            strategy_name="Avalanche", num_loans=3, extra=10000,
            interest_saved=250000, months_saved=18,
            payoff_order=["A", "B", "C"],
        )
        assert "not configured" in text.lower()
        assert usage == {}

        text, usage = await svc.ask_with_context(
            question="What is EMI?", context_chunks=["Some context"],
        )
        assert "not configured" in text.lower()
        assert usage == {}

        text, usage = await svc.chat_with_history(
            message="Hello", history=[], context_chunks=[],
        )
        assert "not configured" in text.lower()
        assert usage == {}

    def test_client_is_none_when_not_configured(self, unconfigured_ai_service):
        assert unconfigured_ai_service.client is None

    def test_configured_service_has_client(self, configured_ai_service):
        assert configured_ai_service.client is not None
