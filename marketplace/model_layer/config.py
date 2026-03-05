"""Model Layer configuration — per-provider settings."""

from __future__ import annotations

from dataclasses import dataclass, field

from marketplace.model_layer.types import ModelProvider


@dataclass
class ProviderConfig:
    """Configuration for a single model provider."""

    enabled: bool = True
    base_url: str = ""
    api_key: str = ""
    default_model: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 2


@dataclass
class ModelLayerConfig:
    """Aggregated configuration for all model providers."""

    default_provider: ModelProvider = ModelProvider.AZURE_OPENAI
    fallback_order: list[ModelProvider] = field(default_factory=lambda: [
        ModelProvider.FOUNDRY_LOCAL,
        ModelProvider.OLLAMA,
        ModelProvider.AZURE_OPENAI,
        ModelProvider.OPENAI,
    ])
    foundry_local: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        base_url="http://localhost:5272",
        default_model="phi-4-mini",
    ))
    ollama: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        base_url="http://localhost:11434",
        default_model="llama3.2",
    ))
    azure_openai: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        default_model="gpt-4o-mini",
    ))
    openai: ProviderConfig = field(default_factory=lambda: ProviderConfig(
        default_model="gpt-4o-mini",
    ))

    def get_provider_config(self, provider: ModelProvider) -> ProviderConfig:
        """Return the config for a given provider."""
        mapping = {
            ModelProvider.FOUNDRY_LOCAL: self.foundry_local,
            ModelProvider.OLLAMA: self.ollama,
            ModelProvider.AZURE_OPENAI: self.azure_openai,
            ModelProvider.OPENAI: self.openai,
        }
        return mapping[provider]
