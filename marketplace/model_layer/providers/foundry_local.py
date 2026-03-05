"""Foundry Local provider — OpenAI-compatible API at localhost:5272.

Supports Phi-4-mini, Phi-4-multimodal and other Foundry-served models.
Uses the standard OpenAI chat completions format.
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


class FoundryLocalBackend(ModelProviderBackend):
    """Foundry Local — OpenAI-compatible local inference server."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._base_url = config.base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=config.timeout_seconds,
        )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        model = request.model or self._config.default_model
        payload: dict[str, Any] = {
            "model": model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.tools:
            payload["tools"] = request.tools

        start = time.perf_counter()
        resp = await self._client.post("/v1/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        latency_ms = (time.perf_counter() - start) * 1000

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls", []):
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=tc.get("function", {}).get("name", ""),
                arguments=tc.get("function", {}).get("arguments", "{}"),
            ))

        return CompletionResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            model=data.get("model", model),
            provider=ModelProvider.FOUNDRY_LOCAL,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
        )

    async def health_check(self) -> ModelHealth:
        try:
            start = time.perf_counter()
            resp = await self._client.get("/v1/models")
            resp.raise_for_status()
            latency_ms = (time.perf_counter() - start) * 1000
            return ModelHealth(
                provider=ModelProvider.FOUNDRY_LOCAL,
                available=True,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            return ModelHealth(
                provider=ModelProvider.FOUNDRY_LOCAL,
                available=False,
                error=str(exc),
            )

    async def close(self) -> None:
        await self._client.aclose()
