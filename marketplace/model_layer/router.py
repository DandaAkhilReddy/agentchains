"""Model Router — routes completion requests with fallback chain.

Tries providers in configured order, falling through on failure.
Emits Prometheus metrics for token usage and latency.
"""

from __future__ import annotations

import structlog

from marketplace.core.metrics import MODEL_TOKENS_TOTAL
from marketplace.model_layer.config import ModelLayerConfig, ProviderConfig
from marketplace.model_layer.providers.base import ModelProviderBackend
from marketplace.model_layer.types import (
    CompletionRequest,
    CompletionResponse,
    ModelHealth,
    ModelProvider,
)

logger = structlog.get_logger(__name__)


class FallbackChain:
    """Ordered list of providers to try in sequence."""

    def __init__(self, providers: list[ModelProvider]) -> None:
        self.providers = providers


class ModelRouter:
    """Routes completion requests to the best available provider with fallback."""

    def __init__(self, config: ModelLayerConfig) -> None:
        self._config = config
        self._backends: dict[ModelProvider, ModelProviderBackend] = {}
        self._fallback_chain = FallbackChain(config.fallback_order)

    def register_provider(
        self,
        provider: ModelProvider,
        backend: ModelProviderBackend,
    ) -> None:
        """Register a provider backend."""
        self._backends[provider] = backend
        logger.info("model_provider_registered", provider=provider.value)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Route a completion request through the fallback chain.

        Tries each provider in order. Falls through on failure.
        Emits MODEL_TOKENS_TOTAL metrics on success.
        """
        errors: list[str] = []

        for provider in self._fallback_chain.providers:
            backend = self._backends.get(provider)
            if backend is None:
                continue

            provider_config = self._config.get_provider_config(provider)
            if not provider_config.enabled:
                continue

            try:
                # Use provider's default model if none specified in request
                if not request.model:
                    request.model = provider_config.default_model

                response = await backend.complete(request)

                # Emit token metrics
                MODEL_TOKENS_TOTAL.labels(
                    model=response.model,
                    provider=response.provider.value,
                    direction="prompt",
                ).inc(response.prompt_tokens)
                MODEL_TOKENS_TOTAL.labels(
                    model=response.model,
                    provider=response.provider.value,
                    direction="completion",
                ).inc(response.completion_tokens)

                logger.debug(
                    "model_completion_success",
                    provider=provider.value,
                    model=response.model,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    latency_ms=response.latency_ms,
                )
                return response

            except Exception as exc:
                error_msg = f"{provider.value}: {exc}"
                errors.append(error_msg)
                logger.warning(
                    "model_provider_failed",
                    provider=provider.value,
                    error=str(exc),
                )
                # Reset model for next provider attempt
                request.model = ""
                continue

        raise RuntimeError(
            f"All model providers failed. Errors: {'; '.join(errors)}"
        )

    async def health_check_all(self) -> dict[ModelProvider, ModelHealth]:
        """Check health of all registered providers."""
        results: dict[ModelProvider, ModelHealth] = {}
        for provider, backend in self._backends.items():
            results[provider] = await backend.health_check()
        return results

    async def close(self) -> None:
        """Close all provider backends."""
        for backend in self._backends.values():
            await backend.close()


def build_model_router_from_settings() -> ModelRouter:
    """Build a ModelRouter from application settings.

    Reads configuration from marketplace.config.settings and creates
    provider backends accordingly.
    """
    from marketplace.config import settings

    config = ModelLayerConfig(
        default_provider=ModelProvider(settings.model_default_provider),
        fallback_order=[
            ModelProvider(p.strip())
            for p in settings.model_fallback_order.split(",")
            if p.strip()
        ],
        foundry_local=ProviderConfig(
            base_url=settings.foundry_local_base_url,
            default_model=settings.foundry_local_default_model,
        ),
        ollama=ProviderConfig(
            base_url=settings.ollama_base_url,
            default_model=settings.ollama_default_model,
        ),
        azure_openai=ProviderConfig(
            default_model=settings.openai_model,
        ),
        openai=ProviderConfig(
            api_key=settings.openai_api_key,
            default_model=settings.openai_model,
        ),
    )

    router = ModelRouter(config)

    # Register Foundry Local
    from marketplace.model_layer.providers.foundry_local import FoundryLocalBackend

    router.register_provider(
        ModelProvider.FOUNDRY_LOCAL,
        FoundryLocalBackend(config.foundry_local),
    )

    # Register Ollama
    from marketplace.model_layer.providers.ollama import OllamaBackend

    router.register_provider(
        ModelProvider.OLLAMA,
        OllamaBackend(config.ollama),
    )

    # Register Azure OpenAI
    from marketplace.model_layer.providers.azure_openai import AzureOpenAIBackend

    router.register_provider(
        ModelProvider.AZURE_OPENAI,
        AzureOpenAIBackend(config.azure_openai),
    )

    # Register OpenAI
    from marketplace.model_layer.providers.openai_provider import OpenAIBackend

    router.register_provider(
        ModelProvider.OPENAI,
        OpenAIBackend(config.openai),
    )

    return router
