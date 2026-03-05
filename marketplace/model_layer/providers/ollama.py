"""Ollama provider — local LLM inference via Ollama API.

Supports Llama 3.2, Mistral, Qwen, and other Ollama-hosted models.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from marketplace.model_layer.config import ProviderConfig
from marketplace.model_layer.providers.base import ModelProviderBackend
from marketplace.model_layer.types import (
    CompletionRequest,
    CompletionResponse,
    ModelHealth,
    ModelProvider,
    ToolCall,
)

logger = structlog.get_logger(__name__)


class OllamaBackend(ModelProviderBackend):
    """Ollama local inference server."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._base_url = config.base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=config.timeout_seconds,
        )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        model = request.model or self._config.default_model

        # Ollama uses /api/chat with a slightly different format
        payload: dict[str, Any] = {
            "model": model,
            "messages": request.messages,
            "stream": False,
            "options": {
                "num_predict": request.max_tokens,
                "temperature": request.temperature,
            },
        }
        if request.tools:
            payload["tools"] = request.tools

        start = time.perf_counter()
        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        latency_ms = (time.perf_counter() - start) * 1000

        message = data.get("message", {})

        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=func.get("name", ""),
                arguments=func.get("arguments", "{}") if isinstance(func.get("arguments"), str)
                else __import__("json").dumps(func.get("arguments", {})),
            ))

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return CompletionResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            model=data.get("model", model),
            provider=ModelProvider.OLLAMA,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )

    async def health_check(self) -> ModelHealth:
        try:
            start = time.perf_counter()
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            latency_ms = (time.perf_counter() - start) * 1000
            return ModelHealth(
                provider=ModelProvider.OLLAMA,
                available=True,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            return ModelHealth(
                provider=ModelProvider.OLLAMA,
                available=False,
                error=str(exc),
            )

    async def close(self) -> None:
        await self._client.aclose()
