"""Provider-agnostic ModelAgent — async agent with function calling.

Uses ModelRouter for multi-provider support with automatic fallback.
Optionally injects semantic memory context via ContextBuilder.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from marketplace.model_layer.router import ModelRouter
from marketplace.model_layer.types import CompletionRequest, CompletionResponse

logger = structlog.get_logger(__name__)


class ModelAgent:
    """Async, provider-agnostic agent with function calling support.

    Uses ModelRouter internally for multi-provider fallback.
    Optionally uses ContextBuilder to inject relevant memories.
    """

    def __init__(
        self,
        model_router: ModelRouter,
        *,
        agent_id: str = "",
        system_prompt: str = "",
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[dict[str, Any]] | None = None,
        context_builder: Any | None = None,  # ContextBuilder from memory layer
    ) -> None:
        self._router = model_router
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.tools = tools
        self._context_builder = context_builder

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> CompletionResponse:
        """Send a completion request through the model router.

        If a context_builder is configured, retrieves relevant memories
        and prepends them to the system prompt.
        """
        effective_messages = list(messages)

        # Build system message with optional memory context
        system_content = self.system_prompt
        if self._context_builder and self.agent_id:
            try:
                # Extract user query from last user message
                user_query = ""
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        user_query = msg.get("content", "")
                        break

                if user_query:
                    memory_context = await self._context_builder.build_context(
                        self.agent_id, user_query,
                    )
                    if memory_context:
                        system_content = (
                            f"{self.system_prompt}\n\n"
                            f"## Relevant Context\n{memory_context}"
                        )
            except Exception:
                logger.warning("memory_context_build_failed", agent_id=self.agent_id)

        # Prepend system message if configured
        if system_content:
            effective_messages = [
                {"role": "system", "content": system_content},
                *effective_messages,
            ]

        request = CompletionRequest(
            messages=effective_messages,
            model=model or self.model,
            tools=tools or self.tools,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature or self.temperature,
        )

        response = await self._router.complete(request)

        logger.info(
            "model_agent_completion",
            agent_id=self.agent_id,
            model=response.model,
            provider=response.provider.value,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=round(response.latency_ms, 1),
        )

        return response

    async def chat(self, user_message: str, **kwargs: Any) -> str:
        """Simple single-turn chat — returns content string."""
        response = await self.complete(
            [{"role": "user", "content": user_message}],
            **kwargs,
        )
        return response.content

    async def function_call(
        self,
        user_message: str,
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> CompletionResponse:
        """Send a message with tools and return the full response including tool calls."""
        return await self.complete(
            [{"role": "user", "content": user_message}],
            tools=tools,
            **kwargs,
        )
