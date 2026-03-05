"""Abstract base class for model provider backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from marketplace.model_layer.types import CompletionRequest, CompletionResponse, ModelHealth


class ModelProviderBackend(ABC):
    """Abstract base for all model provider implementations."""

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a chat completion request."""

    @abstractmethod
    async def health_check(self) -> ModelHealth:
        """Check if this provider is available and responsive."""

    async def close(self) -> None:
        """Clean up resources. Override if the backend holds connections."""
