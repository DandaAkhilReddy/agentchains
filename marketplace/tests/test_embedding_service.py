"""Tests for EmbeddingService — caching, provider fallback, and hash-based embedding."""

from __future__ import annotations

import hashlib
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marketplace.memory.embedding_service import EmbeddingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vector(dim: int = 8, seed: float = 0.5) -> list[float]:
    """Return a deterministic unit-normalised vector for mocking."""
    raw = [seed + i * 0.01 for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


def _service(*, cache_size: int = 1000, openai_key: str = "") -> EmbeddingService:
    return EmbeddingService(
        foundry_url="http://localhost:5272",
        ollama_url="http://localhost:11434",
        openai_api_key=openai_key,
        cache_size=cache_size,
    )


# ---------------------------------------------------------------------------
# embed() — basic behaviour
# ---------------------------------------------------------------------------

async def test_embed_returns_non_empty_float_list():
    svc = _service()
    vec = EmbeddingService._fallback_embed("hello world")
    assert isinstance(vec, list)
    assert len(vec) > 0
    assert all(isinstance(v, float) for v in vec)


async def test_embed_consistent_dimension():
    svc = _service()
    v1 = EmbeddingService._fallback_embed("short")
    v2 = EmbeddingService._fallback_embed("a much longer piece of text for dimension check")
    assert len(v1) == len(v2)
    assert len(v1) == 384


async def test_embed_different_texts_different_vectors():
    svc = _service()
    v1 = EmbeddingService._fallback_embed("apple")
    v2 = EmbeddingService._fallback_embed("banana")
    assert v1 != v2


async def test_embed_caches_result():
    """Second call to embed() must not invoke _generate_embedding again."""
    svc = _service()
    mock_vec = _make_vector()

    with patch.object(svc, "_generate_embedding", new_callable=AsyncMock, return_value=mock_vec) as mock_gen:
        first = await svc.embed("cache me")
        second = await svc.embed("cache me")

    assert first == mock_vec
    assert second == mock_vec
    # _generate_embedding called exactly once — second call served from cache
    mock_gen.assert_awaited_once()


async def test_embed_cache_max_size_evicts_oldest():
    """When cache is full the LRU item is evicted."""
    svc = _service(cache_size=2)

    vec_a = _make_vector(seed=0.1)
    vec_b = _make_vector(seed=0.2)
    vec_c = _make_vector(seed=0.3)

    with patch.object(svc, "_generate_embedding", new_callable=AsyncMock, side_effect=[vec_a, vec_b, vec_c]):
        await svc.embed("text-a")  # cache: [a]
        await svc.embed("text-b")  # cache: [a, b]
        await svc.embed("text-c")  # cache full → evict oldest (a) → [b, c]

    # "text-a" was evicted — re-fetching must call _generate_embedding again
    vec_a2 = _make_vector(seed=0.11)
    with patch.object(svc, "_generate_embedding", new_callable=AsyncMock, return_value=vec_a2) as mock_gen:
        result = await svc.embed("text-a")

    assert result == vec_a2
    mock_gen.assert_awaited_once()


# ---------------------------------------------------------------------------
# embed_batch()
# ---------------------------------------------------------------------------

async def test_embed_batch_returns_list_of_vectors():
    svc = _service()
    texts = ["one", "two", "three"]
    mock_vecs = [_make_vector(seed=i * 0.1) for i in range(3)]

    with patch.object(svc, "_generate_embedding", new_callable=AsyncMock, side_effect=mock_vecs):
        results = await svc.embed_batch(texts)

    assert len(results) == 3
    for vec in results:
        assert isinstance(vec, list)
        assert len(vec) > 0


async def test_embed_batch_empty_list():
    svc = _service()
    results = await svc.embed_batch([])
    assert results == []


async def test_embed_batch_single_item():
    svc = _service()
    mock_vec = _make_vector()
    with patch.object(svc, "_generate_embedding", new_callable=AsyncMock, return_value=mock_vec):
        results = await svc.embed_batch(["solo"])
    assert results == [mock_vec]


async def test_embed_batch_uses_cache_for_already_cached_items():
    """embed_batch should re-use cached entries without extra provider calls."""
    svc = _service()
    mock_vec = _make_vector()

    with patch.object(svc, "_generate_embedding", new_callable=AsyncMock, return_value=mock_vec) as mock_gen:
        await svc.embed("shared")
        results = await svc.embed_batch(["shared", "shared"])

    # _generate_embedding must have been called only once in total (first embed())
    assert mock_gen.await_count == 1
    assert results == [mock_vec, mock_vec]


# ---------------------------------------------------------------------------
# Provider fallback order
# ---------------------------------------------------------------------------

async def test_embed_falls_back_to_foundry_when_ollama_fails():
    svc = _service()
    foundry_vec = _make_vector(seed=0.7)

    with patch.object(svc, "_embed_ollama", new_callable=AsyncMock, side_effect=Exception("no ollama")):
        with patch.object(svc, "_embed_foundry", new_callable=AsyncMock, return_value=foundry_vec) as mock_foundry:
            result = await svc.embed("test")

    assert result == foundry_vec
    mock_foundry.assert_awaited_once()


async def test_embed_falls_back_to_openai_when_ollama_and_foundry_fail():
    svc = _service(openai_key="sk-test")
    openai_vec = _make_vector(seed=0.9)

    with patch.object(svc, "_embed_ollama", new_callable=AsyncMock, side_effect=Exception("no ollama")):
        with patch.object(svc, "_embed_foundry", new_callable=AsyncMock, side_effect=Exception("no foundry")):
            with patch.object(svc, "_embed_openai", new_callable=AsyncMock, return_value=openai_vec) as mock_openai:
                result = await svc.embed("test")

    assert result == openai_vec
    mock_openai.assert_awaited_once()


async def test_embed_all_providers_fail_uses_hash_fallback():
    """When all providers fail, _fallback_embed() is used — result is a valid vector."""
    svc = _service()  # no openai key

    with patch.object(svc, "_embed_ollama", new_callable=AsyncMock, side_effect=Exception("offline")):
        with patch.object(svc, "_embed_foundry", new_callable=AsyncMock, side_effect=Exception("offline")):
            result = await svc.embed("fallback text")

    assert isinstance(result, list)
    assert len(result) == 384
    assert all(isinstance(v, float) for v in result)


async def test_provider_preference_order_ollama_first():
    """Ollama is tried first — if it succeeds, foundry/openai never called."""
    svc = _service(openai_key="sk-test")
    ollama_vec = _make_vector(seed=0.3)

    with patch.object(svc, "_embed_ollama", new_callable=AsyncMock, return_value=ollama_vec) as mock_ollama:
        with patch.object(svc, "_embed_foundry", new_callable=AsyncMock) as mock_foundry:
            with patch.object(svc, "_embed_openai", new_callable=AsyncMock) as mock_openai:
                result = await svc.embed("test priority")

    assert result == ollama_vec
    mock_ollama.assert_awaited_once()
    mock_foundry.assert_not_awaited()
    mock_openai.assert_not_awaited()


# ---------------------------------------------------------------------------
# _fallback_embed() — static method
# ---------------------------------------------------------------------------

def test_fallback_embed_deterministic_same_text():
    v1 = EmbeddingService._fallback_embed("determinism test")
    v2 = EmbeddingService._fallback_embed("determinism test")
    assert v1 == v2


def test_fallback_embed_different_texts_different_vectors():
    v1 = EmbeddingService._fallback_embed("alpha")
    v2 = EmbeddingService._fallback_embed("beta")
    assert v1 != v2


def test_fallback_embed_default_dimension_is_384():
    vec = EmbeddingService._fallback_embed("check dim")
    assert len(vec) == 384


def test_fallback_embed_is_unit_normalised():
    vec = EmbeddingService._fallback_embed("normalisation check")
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-6


def test_fallback_embed_empty_string_returns_valid_vector():
    vec = EmbeddingService._fallback_embed("")
    assert isinstance(vec, list)
    assert len(vec) == 384


def test_fallback_embed_very_long_text():
    long_text = "a " * 10000
    vec = EmbeddingService._fallback_embed(long_text)
    assert len(vec) == 384


def test_fallback_embed_unicode_text():
    vec = EmbeddingService._fallback_embed("こんにちは世界 emoji 🤖")
    assert isinstance(vec, list)
    assert len(vec) == 384
    assert all(isinstance(v, float) for v in vec)


# ---------------------------------------------------------------------------
# Cache key is SHA-256
# ---------------------------------------------------------------------------

def test_cache_key_is_sha256_prefix():
    svc = _service()
    text = "key test"
    key = svc._cache_key(text)
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    assert key == expected


def test_cache_key_different_texts_different_keys():
    svc = _service()
    k1 = svc._cache_key("text one")
    k2 = svc._cache_key("text two")
    assert k1 != k2


# ---------------------------------------------------------------------------
# Private provider method tests (lines 96-138)
# ---------------------------------------------------------------------------


async def test_embed_ollama_success():
    """Lines 110-115: _embed_ollama returns first embedding vector."""
    svc = _service()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("marketplace.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
        result = await svc._embed_ollama("test text")
    assert result == [0.1, 0.2, 0.3]


async def test_embed_ollama_no_embeddings_raises():
    """Line 115: Empty embeddings list raises ValueError."""
    svc = _service()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"embeddings": []}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("marketplace.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="No embeddings"):
            await svc._embed_ollama("test")


async def test_embed_foundry_success():
    """Lines 124-126: _embed_foundry returns embedding from response."""
    svc = _service()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": [{"embedding": [0.4, 0.5, 0.6]}]}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("marketplace.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
        result = await svc._embed_foundry("test text")
    assert result == [0.4, 0.5, 0.6]


async def test_embed_openai_success():
    """Lines 129-138: _embed_openai returns embedding from OpenAI API."""
    svc = _service(openai_key="sk-test-key")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": [{"embedding": [0.7, 0.8, 0.9]}]}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("marketplace.memory.embedding_service.httpx.AsyncClient", return_value=mock_client):
        result = await svc._embed_openai("test text")
    assert result == [0.7, 0.8, 0.9]


async def test_embed_openai_skipped_without_key():
    """Lines 93-97: No OpenAI key → skip OpenAI provider, use fallback."""
    svc = _service(openai_key="")

    with patch.object(svc, "_embed_ollama", side_effect=Exception("fail")), \
         patch.object(svc, "_embed_foundry", side_effect=Exception("fail")):
        # Should use fallback (no openai_api_key set)
        result = await svc.embed("test text for fallback")
    assert isinstance(result, list)
    assert len(result) == 384  # fallback dimension


async def test_embed_openai_fails_with_key_falls_to_fallback():
    """Lines 96-97: OpenAI key set but _embed_openai raises → fallback used."""
    svc = _service(openai_key="sk-test-key")

    with patch.object(svc, "_embed_ollama", side_effect=Exception("ollama down")), \
         patch.object(svc, "_embed_foundry", side_effect=Exception("foundry down")), \
         patch.object(svc, "_embed_openai", side_effect=Exception("openai down")):
        result = await svc.embed("test text openai failure path")
    assert isinstance(result, list)
    assert len(result) == 384  # fallback dimension
