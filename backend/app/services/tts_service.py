"""Text-to-speech service — stub.

Frontend can use the browser's Web Speech API for TTS.
This stub ensures routes that reference TTSService still work gracefully.
"""

import logging

logger = logging.getLogger(__name__)


class TTSService:
    """Stub TTS service — always returns None (use browser Web Speech API)."""

    def __init__(self):
        self.configured = False

    async def generate_audio(self, text: str, language: str = "en") -> str | None:
        """Return None — TTS is handled client-side via Web Speech API."""
        return None
