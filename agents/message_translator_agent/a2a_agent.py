"""Message Translator A2A Agent — dictionary-based translation via the A2A protocol.

Runs on port 9009 and exposes a ``translate`` skill. Translates English text
to a target language (default Spanish) using a built-in word-for-word
dictionary. Unsupported language pairs fall through unchanged with a note.
"""

from __future__ import annotations

from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "translate",
        "name": "Translate",
        "description": (
            "Translate English text to Spanish (default) or French using a "
            "built-in word dictionary. Returns the translated text, word counts, "
            "and the translation method used. Unsupported language pairs return "
            "the original text with a passthrough note."
        ),
        "tags": ["translation", "nlp", "i18n", "language"],
        "examples": [
            '{"text": "Hello world, how are you today?"}',
            '{"text": "I love programming", "target_language": "fr"}',
            '{"text": "Good morning", "target_language": "es", "source_language": "en"}',
        ],
    }
]

# ── Word maps ─────────────────────────────────────────────────────────────────
# English → Spanish (50+ common words)
_EN_ES: dict[str, str] = {
    "hello": "hola",
    "goodbye": "adiós",
    "yes": "sí",
    "no": "no",
    "please": "por favor",
    "thank": "gracias",
    "thanks": "gracias",
    "you": "tú",
    "i": "yo",
    "we": "nosotros",
    "they": "ellos",
    "he": "él",
    "she": "ella",
    "it": "eso",
    "is": "es",
    "are": "son",
    "was": "era",
    "have": "tener",
    "has": "tiene",
    "do": "hacer",
    "does": "hace",
    "can": "puede",
    "will": "hará",
    "the": "el",
    "a": "un",
    "an": "un",
    "and": "y",
    "or": "o",
    "but": "pero",
    "not": "no",
    "of": "de",
    "in": "en",
    "on": "en",
    "at": "en",
    "to": "a",
    "for": "para",
    "with": "con",
    "from": "de",
    "by": "por",
    "good": "bueno",
    "bad": "malo",
    "great": "genial",
    "small": "pequeño",
    "big": "grande",
    "new": "nuevo",
    "old": "viejo",
    "world": "mundo",
    "day": "día",
    "time": "tiempo",
    "love": "amor",
    "work": "trabajo",
    "home": "hogar",
    "water": "agua",
    "food": "comida",
    "book": "libro",
    "name": "nombre",
    "man": "hombre",
    "woman": "mujer",
    "child": "niño",
    "how": "cómo",
    "what": "qué",
    "where": "dónde",
    "when": "cuándo",
    "why": "por qué",
    "who": "quién",
    "morning": "mañana",
    "night": "noche",
    "today": "hoy",
    "tomorrow": "mañana",
    "yesterday": "ayer",
    "program": "programa",
    "programming": "programación",
    "computer": "computadora",
    "language": "idioma",
    "friend": "amigo",
    "life": "vida",
    "city": "ciudad",
    "country": "país",
    "happy": "feliz",
    "sad": "triste",
    "fast": "rápido",
    "slow": "lento",
    "hot": "caliente",
    "cold": "frío",
    "open": "abrir",
    "close": "cerrar",
    "start": "empezar",
    "stop": "detener",
    "help": "ayuda",
    "one": "uno",
    "two": "dos",
    "three": "tres",
    "four": "cuatro",
    "five": "cinco",
    "six": "seis",
    "seven": "siete",
    "eight": "ocho",
    "nine": "nueve",
    "ten": "diez",
}

# English → French (50+ common words)
_EN_FR: dict[str, str] = {
    "hello": "bonjour",
    "goodbye": "au revoir",
    "yes": "oui",
    "no": "non",
    "please": "s'il vous plaît",
    "thank": "merci",
    "thanks": "merci",
    "you": "vous",
    "i": "je",
    "we": "nous",
    "they": "ils",
    "he": "il",
    "she": "elle",
    "it": "il",
    "is": "est",
    "are": "sont",
    "was": "était",
    "have": "avoir",
    "has": "a",
    "do": "faire",
    "does": "fait",
    "can": "peut",
    "will": "fera",
    "the": "le",
    "a": "un",
    "an": "un",
    "and": "et",
    "or": "ou",
    "but": "mais",
    "not": "pas",
    "of": "de",
    "in": "dans",
    "on": "sur",
    "at": "à",
    "to": "à",
    "for": "pour",
    "with": "avec",
    "from": "de",
    "by": "par",
    "good": "bon",
    "bad": "mauvais",
    "great": "formidable",
    "small": "petit",
    "big": "grand",
    "new": "nouveau",
    "old": "vieux",
    "world": "monde",
    "day": "jour",
    "time": "temps",
    "love": "amour",
    "work": "travail",
    "home": "maison",
    "water": "eau",
    "food": "nourriture",
    "book": "livre",
    "name": "nom",
    "man": "homme",
    "woman": "femme",
    "child": "enfant",
    "how": "comment",
    "what": "quoi",
    "where": "où",
    "when": "quand",
    "why": "pourquoi",
    "who": "qui",
    "morning": "matin",
    "night": "nuit",
    "today": "aujourd'hui",
    "tomorrow": "demain",
    "yesterday": "hier",
    "program": "programme",
    "programming": "programmation",
    "computer": "ordinateur",
    "language": "langue",
    "friend": "ami",
    "life": "vie",
    "city": "ville",
    "country": "pays",
    "happy": "heureux",
    "sad": "triste",
    "fast": "rapide",
    "slow": "lent",
    "hot": "chaud",
    "cold": "froid",
    "open": "ouvrir",
    "close": "fermer",
    "start": "commencer",
    "stop": "arrêter",
    "help": "aide",
    "one": "un",
    "two": "deux",
    "three": "trois",
    "four": "quatre",
    "five": "cinq",
    "six": "six",
    "seven": "sept",
    "eight": "huit",
    "nine": "neuf",
    "ten": "dix",
}

# Registry: source_lang → target_lang → word map
_DICTIONARIES: dict[str, dict[str, dict[str, str]]] = {
    "en": {
        "es": _EN_ES,
        "fr": _EN_FR,
    }
}

_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
}


def _tokenize_preserving_case(text: str) -> list[str]:
    """Split text into tokens, preserving original whitespace as separate tokens.

    Punctuation attached to words is kept so that the output can be re-joined
    faithfully. Each "word" token (alphanumeric run) is returned separately from
    surrounding punctuation/space.

    Args:
        text: Input text string.

    Returns:
        List of token strings alternating between word-like tokens and
        separator/punctuation tokens.
    """
    tokens: list[str] = []
    current: list[str] = []
    for ch in text:
        if ch.isalpha():
            current.append(ch)
        else:
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def _translate_word(word: str, word_map: dict[str, str]) -> tuple[str, bool]:
    """Look up a word in the translation map, preserving capitalisation.

    Checks lowercase, then title-case forms. Returns the translated word
    with the original capitalisation pattern applied, or the original word
    if no match is found.

    Args:
        word: A single word token (no punctuation).
        word_map: Source-to-target word dictionary.

    Returns:
        Tuple of ``(translated_word, was_translated)`` where ``was_translated``
        is ``True`` if a dictionary match was found.
    """
    lower = word.lower()
    translation = word_map.get(lower)
    if translation is None:
        return word, False

    # Mirror capitalisation: ALL-CAPS, Title, or lowercase
    if word.isupper():
        return translation.upper(), True
    if word[0].isupper():
        return translation.capitalize(), True
    return translation, True


def _translate_text(
    text: str,
    source_language: str,
    target_language: str,
) -> dict[str, Any]:
    """Translate *text* from *source_language* to *target_language*.

    Uses the built-in word dictionaries for supported language pairs. Falls
    through with the original text and a note when the pair is unsupported.

    Args:
        text: The source text to translate.
        source_language: BCP-47 source language code (e.g. ``"en"``).
        target_language: BCP-47 target language code (e.g. ``"es"``).

    Returns:
        Dict with ``original``, ``translated``, ``source_language``,
        ``target_language``, ``method``, ``word_count``, ``translated_count``,
        and optionally ``note``.
    """
    src_maps = _DICTIONARIES.get(source_language, {})
    word_map = src_maps.get(target_language)

    if word_map is None:
        return {
            "original": text,
            "translated": text,
            "source_language": _LANGUAGE_NAMES.get(source_language, source_language),
            "target_language": _LANGUAGE_NAMES.get(target_language, target_language),
            "method": "passthrough",
            "word_count": len(text.split()),
            "translated_count": 0,
            "note": (
                f"Translation from '{source_language}' to '{target_language}' "
                "is not supported. Original text returned unchanged."
            ),
        }

    tokens = _tokenize_preserving_case(text)
    output_tokens: list[str] = []
    word_count = 0
    translated_count = 0

    for token in tokens:
        if token.isalpha():
            word_count += 1
            translated, did_translate = _translate_word(token, word_map)
            if did_translate:
                translated_count += 1
            output_tokens.append(translated)
        else:
            output_tokens.append(token)

    translated_text = "".join(output_tokens)

    return {
        "original": text,
        "translated": translated_text,
        "source_language": _LANGUAGE_NAMES.get(source_language, source_language),
        "target_language": _LANGUAGE_NAMES.get(target_language, target_language),
        "method": "dictionary",
        "word_count": word_count,
        "translated_count": translated_count,
    }


class MessageTranslatorA2AAgent(BaseA2AAgent):
    """A2A agent that performs dictionary-based word-for-word translation.

    Supports English → Spanish and English → French. Unrecognised language
    pairs return the original text via passthrough with an explanatory note.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Message Translator Agent",
            description=(
                "Translates English text to Spanish (default) or French using a "
                "built-in word dictionary. Returns the translated text, translation "
                "method, and word-level statistics. Unsupported language pairs "
                "return the original text with a passthrough note."
            ),
            port=9009,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming translation request.

        Args:
            skill_id: Must be ``translate``.
            input_data: Dict with:
                - ``text`` (str): The text to translate. Required.
                - ``target_language`` (str, default ``"es"``): BCP-47 target code.
                - ``source_language`` (str, default ``"en"``): BCP-47 source code.

        Returns:
            Dict with ``original``, ``translated``, ``source_language``,
            ``target_language``, ``method`` (``"dictionary"`` or
            ``"passthrough"``), ``word_count``, ``translated_count``,
            and optionally ``note``.
        """
        text: str = input_data.get("text", "")
        target_language: str = str(input_data.get("target_language", "es")).lower()
        source_language: str = str(input_data.get("source_language", "en")).lower()

        if not text:
            return {
                "original": "",
                "translated": "",
                "source_language": _LANGUAGE_NAMES.get(source_language, source_language),
                "target_language": _LANGUAGE_NAMES.get(target_language, target_language),
                "method": "dictionary",
                "word_count": 0,
                "translated_count": 0,
            }

        return _translate_text(text, source_language, target_language)


agent = MessageTranslatorA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9009)
