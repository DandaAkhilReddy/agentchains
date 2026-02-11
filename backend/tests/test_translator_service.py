"""Tests for app.services.translator_service — OpenAI-based translation."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Fixtures: configured / unconfigured TranslatorService
# ---------------------------------------------------------------------------


@pytest.fixture
def unconfigured_translator():
    """TranslatorService with empty key => not configured."""
    with patch("app.services.translator_service.settings") as mock_settings:
        mock_settings.openai_api_key = ""
        from app.services.translator_service import TranslatorService

        svc = TranslatorService()
        assert not svc.configured
        return svc


@pytest.fixture
def configured_translator():
    """TranslatorService with a fake key => configured."""
    with patch("app.services.translator_service.settings") as mock_settings:
        mock_settings.openai_api_key = "sk-fake-key"
        mock_settings.openai_model = "gpt-4o-mini"
        from app.services.translator_service import TranslatorService

        svc = TranslatorService()
        assert svc.configured
        return svc


# ---------------------------------------------------------------------------
# Helper: mock OpenAI chat completion response
# ---------------------------------------------------------------------------


def _mock_chat_response(text: str):
    """Create a mock OpenAI ChatCompletion response."""
    mock_message = MagicMock()
    mock_message.content = text

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


# ---------------------------------------------------------------------------
# Tests: __init__
# ---------------------------------------------------------------------------


class TestInit:
    """TranslatorService.__init__ sets .configured based on the key."""

    def test_configured_when_key_present(self, configured_translator):
        assert configured_translator.configured is True

    def test_not_configured_when_key_empty(self, unconfigured_translator):
        assert unconfigured_translator.configured is False


# ---------------------------------------------------------------------------
# Tests: translate()
# ---------------------------------------------------------------------------


class TestTranslate:
    """TranslatorService.translate — six scenarios."""

    @pytest.mark.asyncio
    async def test_en_to_hi_success(self, configured_translator):
        """EN->HI: mock API returns Hindi text."""
        configured_translator.client.chat.completions.create = AsyncMock(
            return_value=_mock_chat_response("\u0928\u092e\u0938\u094d\u0924\u0947")
        )
        result = await configured_translator.translate("Hello", target_language="hi")
        assert result == "\u0928\u092e\u0938\u094d\u0924\u0947"

    @pytest.mark.asyncio
    async def test_en_to_te_success(self, configured_translator):
        """EN->TE: mock API returns Telugu text."""
        configured_translator.client.chat.completions.create = AsyncMock(
            return_value=_mock_chat_response("\u0c38\u0c4d\u0c35\u0c3e\u0c17\u0c24\u0c02")
        )
        result = await configured_translator.translate(
            "Welcome", target_language="te"
        )
        assert result == "\u0c38\u0c4d\u0c35\u0c3e\u0c17\u0c24\u0c02"

    @pytest.mark.asyncio
    async def test_same_language_returns_original(self, configured_translator):
        """When target == source, return text immediately (no API call)."""
        configured_translator.client.chat.completions.create = AsyncMock()

        result = await configured_translator.translate(
            "Hello", target_language="en", source_language="en"
        )
        assert result == "Hello"
        configured_translator.client.chat.completions.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_not_configured_returns_original(self, unconfigured_translator):
        """When openai_api_key is empty, returns original text."""
        result = await unconfigured_translator.translate("Hello", target_language="hi")
        assert result == "Hello"

    @pytest.mark.asyncio
    async def test_unsupported_language_returns_original(self, configured_translator):
        """'fr' is not in SUPPORTED_LANGUAGES, so returns original text."""
        configured_translator.client.chat.completions.create = AsyncMock()

        result = await configured_translator.translate(
            "Hello", target_language="fr"
        )
        assert result == "Hello"
        configured_translator.client.chat.completions.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_api_error_returns_original(self, configured_translator):
        """When OpenAI raises an exception, returns original text."""
        configured_translator.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Connection timeout")
        )
        result = await configured_translator.translate(
            "Hello", target_language="hi"
        )
        assert result == "Hello"


# ---------------------------------------------------------------------------
# Tests: detect_language()
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    """TranslatorService.detect_language — four scenarios."""

    @pytest.mark.asyncio
    async def test_detect_hindi(self, configured_translator):
        """Detect Hindi text."""
        configured_translator.client.chat.completions.create = AsyncMock(
            return_value=_mock_chat_response("hi")
        )
        result = await configured_translator.detect_language(
            "\u0928\u092e\u0938\u094d\u0924\u0947"
        )
        assert result == "hi"

    @pytest.mark.asyncio
    async def test_detect_english(self, configured_translator):
        """Detect English text."""
        configured_translator.client.chat.completions.create = AsyncMock(
            return_value=_mock_chat_response("en")
        )
        result = await configured_translator.detect_language("Hello world")
        assert result == "en"

    @pytest.mark.asyncio
    async def test_not_configured_returns_en(self, unconfigured_translator):
        """When not configured, defaults to 'en'."""
        result = await unconfigured_translator.detect_language(
            "\u0928\u092e\u0938\u094d\u0924\u0947"
        )
        assert result == "en"

    @pytest.mark.asyncio
    async def test_api_error_returns_en(self, configured_translator):
        """When OpenAI raises, defaults to 'en'."""
        configured_translator.client.chat.completions.create = AsyncMock(
            side_effect=Exception("Service unavailable")
        )
        result = await configured_translator.detect_language("some text")
        assert result == "en"
