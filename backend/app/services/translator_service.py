"""OpenAI-based translation service — EN to HI/TE/ES translation.

Uses the same OpenAI API key as the rest of the app.
"""

import logging
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "es": "Spanish",
}


class TranslatorService:
    """OpenAI-based translator for multi-language AI output."""

    def __init__(self):
        if settings.openai_api_key:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.configured = True
        else:
            self.client = None
            self.configured = False
            logger.warning("OpenAI not configured — translation unavailable")

    async def translate(self, text: str, target_language: str, source_language: str = "en") -> str:
        """Translate text to target language using OpenAI.

        Args:
            text: Source text
            target_language: Target language code ('hi', 'te', 'en')
            source_language: Source language code (default 'en')

        Returns:
            Translated text, or original text if translation fails
        """
        if not self.configured:
            return text

        if target_language == source_language:
            return text

        if target_language not in SUPPORTED_LANGUAGES:
            logger.warning(f"Unsupported language: {target_language}")
            return text

        target_name = SUPPORTED_LANGUAGES[target_language]
        source_name = SUPPORTED_LANGUAGES.get(source_language, source_language)

        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a translator. Translate the following text from {source_name} to {target_name}. "
                                   f"Return ONLY the translated text, nothing else.",
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text

    async def detect_language(self, text: str) -> str:
        """Detect the language of input text using OpenAI."""
        if not self.configured:
            return "en"

        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Detect the language of the following text. "
                                   "Return ONLY the ISO 639-1 language code (e.g., 'en', 'hi', 'te', 'es'). Nothing else.",
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.0,
                max_tokens=5,
            )
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return "en"
