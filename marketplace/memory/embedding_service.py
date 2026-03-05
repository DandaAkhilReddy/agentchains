"""Embedding service — generates text embeddings via ModelRouter.

Uses Foundry Local / Ollama embedding endpoints with Azure fallback.
Includes an in-memory LRU cache to avoid re-computation.
"""

from __future__ import annotations

import hashlib
import math
from collections import OrderedDict
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Generates text embeddings with caching.

    Tries local providers first (Foundry Local, Ollama) for embeddings,
    falls back to OpenAI-compatible cloud API.
    """

    def __init__(
        self,
        *,
        foundry_url: str = "http://localhost:5272",
        ollama_url: str = "http://localhost:11434",
        openai_api_key: str = "",
        model: str = "",
        cache_size: int = 1000,
        timeout: float = 30.0,
    ) -> None:
        self._foundry_url = foundry_url.rstrip("/")
        self._ollama_url = ollama_url.rstrip("/")
        self._openai_api_key = openai_api_key
        self._model = model
        self._timeout = timeout
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_size = cache_size

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _cache_get(self, text: str) -> list[float] | None:
        key = self._cache_key(text)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, text: str, embedding: list[float]) -> None:
        key = self._cache_key(text)
        self._cache[key] = embedding
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text. Uses cache."""
        cached = self._cache_get(text)
        if cached is not None:
            return cached

        embedding = await self._generate_embedding(text)
        self._cache_put(text, embedding)
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        results: list[list[float]] = []
        for text in texts:
            results.append(await self.embed(text))
        return results

    async def _generate_embedding(self, text: str) -> list[float]:
        """Try providers in order: Ollama -> Foundry Local -> OpenAI."""
        # Try Ollama first
        try:
            return await self._embed_ollama(text)
        except Exception:
            pass

        # Try Foundry Local
        try:
            return await self._embed_foundry(text)
        except Exception:
            pass

        # Try OpenAI
        if self._openai_api_key:
            try:
                return await self._embed_openai(text)
            except Exception:
                pass

        # Fallback: simple hash-based pseudo-embedding (deterministic, for dev)
        logger.warning("all_embedding_providers_failed_using_fallback")
        return self._fallback_embed(text)

    async def _embed_ollama(self, text: str) -> list[float]:
        model = self._model or "nomic-embed-text"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._ollama_url}/api/embed",
                json={"model": model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if embeddings:
                return embeddings[0]
            raise ValueError("No embeddings returned from Ollama")

    async def _embed_foundry(self, text: str) -> list[float]:
        model = self._model or "text-embedding-3-small"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._foundry_url}/v1/embeddings",
                json={"model": model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    async def _embed_openai(self, text: str) -> list[float]:
        model = self._model or "text-embedding-3-small"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self._openai_api_key}"},
                json={"model": model, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    @staticmethod
    def _fallback_embed(text: str, dim: int = 384) -> list[float]:
        """Deterministic pseudo-embedding for development/testing."""
        h = hashlib.sha512(text.encode("utf-8")).digest()
        raw = [b / 255.0 * 2 - 1 for b in h]
        # Pad or truncate to dim
        while len(raw) < dim:
            raw.extend(raw[:dim - len(raw)])
        raw = raw[:dim]
        # Normalize
        norm = math.sqrt(sum(x * x for x in raw))
        if norm > 0:
            raw = [x / norm for x in raw]
        return raw
