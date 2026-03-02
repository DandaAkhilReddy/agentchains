"""Language Detector A2A Agent — script and language detection via the A2A protocol.

Runs on port 9007 and exposes a ``detect-language`` skill. Accepts one or more
text strings and identifies the most likely natural language using trigram
frequency analysis combined with Unicode block detection for non-Latin scripts.
"""

from __future__ import annotations

from typing import Any

import uvicorn

from agents.common.base_agent import BaseA2AAgent

_SKILLS: list[dict[str, Any]] = [
    {
        "id": "detect-language",
        "name": "Detect Language",
        "description": (
            "Identify the natural language of one or more text strings using "
            "trigram frequency analysis and Unicode script detection. Returns "
            "language name, BCP-47 code, confidence score, and script."
        ),
        "tags": ["nlp", "language-detection", "text-analysis", "i18n"],
        "examples": [
            '{"text": "The quick brown fox jumps over the lazy dog"}',
            '{"texts": ["Bonjour le monde", "Hola mundo", "Guten Tag"]}',
        ],
    }
]

# ── Trigram profiles ──────────────────────────────────────────────────────────
# Each language has a frozenset of characteristic trigrams (lowercased, with
# spaces represented as underscores to distinguish word-boundary trigrams).

_TRIGRAM_PROFILES: dict[str, frozenset[str]] = {
    "en": frozenset({
        "the", "and", "ing", "ion", "tio", "ent", "hat", "his", "her",
        "tha", "he_", "_th", "is_", "in_", "_in", "ati", "on_", "_he",
        "ter", "for", "are", "not", "wit", "all", "was", "ere",
    }),
    "es": frozenset({
        "que", "los", "las", "del", "con", "una", "por", "cion", "ado",
        "nte", "_qu", "ue_", "es_", "_lo", "la_", "_la", "de_", "_de",
        "ien", "nes", "ado", "tos", "ara", "est", "pro",
    }),
    "fr": frozenset({
        "les", "des", "que", "ent", "une", "est", "les", "par", "sur",
        "_le", "le_", "_de", "de_", "_un", "_la", "la_", "ons", "tion",
        "ait", "our", "ous", "ais", "ans", "eur", "ment",
    }),
    "de": frozenset({
        "ein", "der", "die", "und", "den", "das", "ich", "von", "mit",
        "_de", "_di", "ie_", "er_", "_un", "und", "en_", "_ei", "che",
        "cht", "sch", "ver", "auf", "ist", "bei", "ung",
    }),
    "it": frozenset({
        "che", "per", "del", "una", "con", "non", "zione", "lle", "gli",
        "_ch", "he_", "_pe", "_de", "del", "la_", "_la", "ell", "ell",
        "ato", "are", "ent", "nte", "est", "sta", "ione",
    }),
    "pt": frozenset({
        "que", "dos", "das", "com", "uma", "para", "por", "cao", "oes",
        "_qu", "_pa", "para", "ao_", "_co", "_de", "de_", "ado", "oes",
        "nte", "est", "iss", "sso", "ndo", "ens", "ção",
    }),
    "nl": frozenset({
        "een", "van", "het", "den", "aan", "met", "ver", "ing", "aar",
        "_va", "_he", "het", "_ee", "ijk", "sch", "en_", "de_", "_de",
        "bij", "uit", "oor", "nde", "erd", "ges", "elijk",
    }),
    "ru": frozenset({
        "ого", "ого", "ние", "ния", "ости", "ые", "ого", "что", "как",
        "это", "ения", "ать", "ете", "ого", "его", "для", "при", "все",
        "ото", "по_", "_по", "не_", "_не", "про", "над", "под",
    }),
    "zh": frozenset({
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
        "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    }),
    "ja": frozenset({
        "する", "ている", "です", "ます", "ない", "から", "こと", "その",
        "について", "という", "ため", "ある", "これ", "それ", "より",
    }),
    "ar": frozenset({
        "في", "من", "على", "إلى", "أن", "هذا", "ما", "كان", "عن", "أو",
        "لا", "وقد", "قال", "التي", "كل", "هو", "ذلك", "مع", "وهو",
    }),
}

# Human-readable names and BCP-47 codes
_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ar": "Arabic",
}

# ── Script detection ranges ───────────────────────────────────────────────────

def _detect_script(text: str) -> str:
    """Identify the dominant Unicode script in a text sample.

    Checks character code points against known Unicode block ranges and
    returns the script name of the most-represented non-ASCII script.
    Falls back to ``"Latin"`` when no non-Latin characters are found.

    Args:
        text: The text sample to inspect.

    Returns:
        Script name string: ``"Latin"``, ``"Cyrillic"``, ``"CJK"``,
        ``"Arabic"``, ``"Devanagari"``, or ``"Hangul"``.
    """
    script_counts: dict[str, int] = {
        "Cyrillic": 0,
        "CJK": 0,
        "Arabic": 0,
        "Devanagari": 0,
        "Hangul": 0,
    }
    for ch in text:
        cp = ord(ch)
        if 0x0400 <= cp <= 0x04FF:          # Cyrillic
            script_counts["Cyrillic"] += 1
        elif 0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x30FF:  # CJK + kana
            script_counts["CJK"] += 1
        elif 0x0600 <= cp <= 0x06FF:         # Arabic
            script_counts["Arabic"] += 1
        elif 0x0900 <= cp <= 0x097F:         # Devanagari
            script_counts["Devanagari"] += 1
        elif 0xAC00 <= cp <= 0xD7AF:         # Hangul
            script_counts["Hangul"] += 1

    dominant = max(script_counts, key=lambda k: script_counts[k])
    if script_counts[dominant] > 0:
        return dominant
    return "Latin"


def _extract_trigrams(text: str) -> list[str]:
    """Extract overlapping trigrams from lowercased text with space markers.

    Spaces are replaced with underscores so word-boundary trigrams (e.g.
    ``"_th"``, ``"he_"``) are distinct from intra-word trigrams.

    Args:
        text: Raw input text.

    Returns:
        List of 3-character trigram strings.
    """
    normalised = text.lower()
    # Collapse runs of whitespace to single underscore
    cleaned: list[str] = []
    in_space = False
    for ch in normalised:
        if ch.isspace():
            if not in_space:
                cleaned.append("_")
                in_space = True
        else:
            cleaned.append(ch)
            in_space = False

    joined = "".join(cleaned)
    return [joined[i:i + 3] for i in range(len(joined) - 2)]


def _score_language(trigrams: list[str], profile: frozenset[str]) -> float:
    """Compute what fraction of a profile's trigrams appear in the input.

    Args:
        trigrams: List of trigrams extracted from the input text.
        profile: The reference trigram set for a language.

    Returns:
        Float in ``[0.0, 1.0]`` representing the match ratio.
    """
    if not trigrams or not profile:
        return 0.0
    input_set = set(trigrams)
    hits = len(profile & input_set)
    return hits / len(profile)


def _detect_single(text: str) -> dict[str, Any]:
    """Detect the language and script of a single text string.

    Combines Unicode-script heuristics with trigram profile matching to
    produce a language code, human-readable name, confidence estimate, and
    script label.

    Args:
        text: The text string to analyse.

    Returns:
        Dict with ``text_excerpt``, ``detected_language``, ``language_code``,
        ``confidence``, and ``script``.
    """
    excerpt = text[:120].replace("\n", " ")
    script = _detect_script(text)

    # For non-Latin scripts, short-circuit with script-based detection
    script_to_lang: dict[str, str] = {
        "Cyrillic": "ru",
        "CJK": "zh",
        "Arabic": "ar",
        "Devanagari": "hi",
        "Hangul": "ko",
    }
    if script != "Latin" and script in script_to_lang:
        lang_code = script_to_lang[script]
        return {
            "text_excerpt": excerpt,
            "detected_language": _LANGUAGE_NAMES.get(lang_code, lang_code.upper()),
            "language_code": lang_code,
            "confidence": 0.85,
            "script": script,
        }

    if not text.strip():
        return {
            "text_excerpt": excerpt,
            "detected_language": "Unknown",
            "language_code": "und",
            "confidence": 0.0,
            "script": "Latin",
        }

    trigrams = _extract_trigrams(text)
    scores: dict[str, float] = {
        lang: _score_language(trigrams, profile)
        for lang, profile in _TRIGRAM_PROFILES.items()
        if lang not in {"ru", "zh", "ja", "ar"}  # non-Latin handled above
    }

    best_lang = max(scores, key=lambda k: scores[k])
    best_score = scores[best_lang]

    # Confidence: scale the raw ratio to [0, 0.95] and penalise low scores
    confidence = min(0.95, best_score * 3.0) if best_score > 0.05 else 0.1

    return {
        "text_excerpt": excerpt,
        "detected_language": _LANGUAGE_NAMES.get(best_lang, best_lang.upper()),
        "language_code": best_lang,
        "confidence": round(confidence, 4),
        "script": "Latin",
    }


class LanguageDetectorA2AAgent(BaseA2AAgent):
    """A2A agent that detects natural language and Unicode script in text.

    Accepts a single text (``text`` key) or a batch of texts (``texts`` key)
    and returns a language detection result for each.
    """

    def __init__(self) -> None:
        super().__init__(
            name="Language Detector Agent",
            description=(
                "Detects the natural language and Unicode script of one or more "
                "text strings using trigram frequency analysis and Unicode block "
                "heuristics. Returns language name, BCP-47 code, confidence, and "
                "script. Suitable for pre-processing in multilingual pipelines."
            ),
            port=9007,
            skills=_SKILLS,
            version="0.1.0",
        )

    async def handle_skill(
        self, skill_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle an incoming language-detection request.

        Args:
            skill_id: Must be ``detect-language``.
            input_data: Dict with ``texts`` (list of str) or ``text`` (single str).

        Returns:
            Dict with ``results`` list, each item containing ``text_excerpt``,
            ``detected_language``, ``language_code``, ``confidence``, and
            ``script``.
        """
        texts: list[str]

        raw_texts = input_data.get("texts")
        if isinstance(raw_texts, list):
            texts = [str(t) for t in raw_texts]
        else:
            single = input_data.get("text", "")
            texts = [str(single)] if single else []

        if not texts:
            return {"results": []}

        results = [_detect_single(t) for t in texts]
        return {"results": results}


agent = LanguageDetectorA2AAgent()
app = agent.build_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9007)
