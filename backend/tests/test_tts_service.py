"""Tests for app.services.tts_service — stub TTS.

The TTSService is now a simple stub that always returns None.
Frontend handles TTS via the browser's Web Speech API.
"""

import pytest
from app.services.tts_service import TTSService


# ---------------------------------------------------------------------------
# Tests: TTSService stub
# ---------------------------------------------------------------------------


class TestTTSInit:
    """TTSService.__init__ is always unconfigured."""

    def test_configured_is_false(self):
        svc = TTSService()
        assert svc.configured is False


class TestGenerateAudio:
    """TTSService.generate_audio always returns None."""

    @pytest.mark.asyncio
    async def test_returns_none_for_english(self):
        svc = TTSService()
        result = await svc.generate_audio("Hello world", language="en")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_hindi(self):
        svc = TTSService()
        result = await svc.generate_audio("Namaste", language="hi")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_telugu(self):
        svc = TTSService()
        result = await svc.generate_audio("Vandanalu", language="te")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_default_language(self):
        svc = TTSService()
        result = await svc.generate_audio("Some text")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_empty_text(self):
        svc = TTSService()
        result = await svc.generate_audio("")
        assert result is None
