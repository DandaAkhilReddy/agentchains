"""Azure OpenAI provider — async wrapper using openai.AsyncAzureOpenAI."""

from __future__ import annotations

import os
import time

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

# Cost per 1K tokens (approximate, GPT-4o-mini defaults)
_COST_PER_1K_PROMPT = 0.00015
_COST_PER_1K_COMPLETION = 0.0006


class AzureOpenAIBackend(ModelProviderBackend):
    """Azure OpenAI via the openai SDK (async)."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncAzureOpenAI

            self._client = AsyncAzureOpenAI(
                azure_endpoint=self._config.base_url or os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
                api_key=self._config.api_key or os.environ.get("AZURE_OPENAI_API_KEY", ""),
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
                timeout=self._config.timeout_seconds,
                max_retries=self._config.max_retries,
            )
        return self._client

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        client = self._get_client()
        model = request.model or self._config.default_model

        kwargs: dict = {
            "model": model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.tools:
            kwargs["tools"] = request.tools

        start = time.perf_counter()
        resp = await client.chat.completions.create(**kwargs)
        latency_ms = (time.perf_counter() - start) * 1000

        choice = resp.choices[0] if resp.choices else None
        message = choice.message if choice else None

        tool_calls: list[ToolCall] = []
        if message and message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id or "",
                    name=tc.function.name or "",
                    arguments=tc.function.arguments or "{}",
                ))

        prompt_tokens = resp.usage.prompt_tokens if resp.usage else 0
        completion_tokens = resp.usage.completion_tokens if resp.usage else 0
        cost = (prompt_tokens * _COST_PER_1K_PROMPT + completion_tokens * _COST_PER_1K_COMPLETION) / 1000

        return CompletionResponse(
            content=message.content or "" if message else "",
            tool_calls=tool_calls,
            model=resp.model or model,
            provider=ModelProvider.AZURE_OPENAI,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            cost_usd=cost,
        )

    async def health_check(self) -> ModelHealth:
        try:
            client = self._get_client()
            start = time.perf_counter()
            await client.models.list()
            latency_ms = (time.perf_counter() - start) * 1000
            return ModelHealth(
                provider=ModelProvider.AZURE_OPENAI,
                available=True,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            return ModelHealth(
                provider=ModelProvider.AZURE_OPENAI,
                available=False,
                error=str(exc),
            )

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
