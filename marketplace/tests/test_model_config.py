"""Tests for marketplace.model_layer.config — ProviderConfig and ModelLayerConfig."""

from __future__ import annotations

import pytest

from marketplace.model_layer.config import ModelLayerConfig, ProviderConfig
from marketplace.model_layer.types import ModelProvider


# ---------------------------------------------------------------------------
# ProviderConfig
# ---------------------------------------------------------------------------


def test_provider_config_defaults() -> None:
    config = ProviderConfig()
    assert config.enabled is True
    assert config.base_url == ""
    assert config.api_key == ""
    assert config.default_model == ""
    assert config.timeout_seconds == 30.0
    assert config.max_retries == 2


def test_provider_config_disabled() -> None:
    config = ProviderConfig(enabled=False)
    assert config.enabled is False


def test_provider_config_custom_base_url() -> None:
    config = ProviderConfig(base_url="http://localhost:5272")
    assert config.base_url == "http://localhost:5272"


def test_provider_config_with_api_key() -> None:
    config = ProviderConfig(api_key="secret-key-123")
    assert config.api_key == "secret-key-123"


def test_provider_config_custom_timeout_and_retries() -> None:
    config = ProviderConfig(timeout_seconds=60.0, max_retries=5)
    assert config.timeout_seconds == 60.0
    assert config.max_retries == 5


def test_provider_config_with_default_model() -> None:
    config = ProviderConfig(default_model="gpt-4o-mini")
    assert config.default_model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# ModelLayerConfig
# ---------------------------------------------------------------------------


def test_model_layer_config_defaults() -> None:
    config = ModelLayerConfig()
    assert config.default_provider == ModelProvider.AZURE_OPENAI
    assert len(config.fallback_order) == 4


def test_model_layer_config_default_fallback_order() -> None:
    config = ModelLayerConfig()
    assert config.fallback_order[0] == ModelProvider.FOUNDRY_LOCAL
    assert config.fallback_order[1] == ModelProvider.OLLAMA
    assert config.fallback_order[2] == ModelProvider.AZURE_OPENAI
    assert config.fallback_order[3] == ModelProvider.OPENAI


def test_model_layer_config_get_provider_config_foundry() -> None:
    config = ModelLayerConfig()
    pconfig = config.get_provider_config(ModelProvider.FOUNDRY_LOCAL)
    assert pconfig is config.foundry_local
    assert pconfig.base_url == "http://localhost:5272"
    assert pconfig.default_model == "phi-4-mini"


def test_model_layer_config_get_provider_config_ollama() -> None:
    config = ModelLayerConfig()
    pconfig = config.get_provider_config(ModelProvider.OLLAMA)
    assert pconfig is config.ollama
    assert pconfig.base_url == "http://localhost:11434"
    assert pconfig.default_model == "llama3.2"


def test_model_layer_config_get_provider_config_azure() -> None:
    config = ModelLayerConfig()
    pconfig = config.get_provider_config(ModelProvider.AZURE_OPENAI)
    assert pconfig is config.azure_openai
    assert pconfig.default_model == "gpt-4o-mini"


def test_model_layer_config_get_provider_config_openai() -> None:
    config = ModelLayerConfig()
    pconfig = config.get_provider_config(ModelProvider.OPENAI)
    assert pconfig is config.openai
    assert pconfig.default_model == "gpt-4o-mini"


def test_model_layer_config_unknown_provider_raises_key_error() -> None:
    config = ModelLayerConfig()
    # Force an unmapped value using a raw string that doesn't match
    with pytest.raises(KeyError):
        config.get_provider_config("unknown_provider")  # type: ignore[arg-type]


def test_model_layer_config_custom_fallback_order() -> None:
    custom_order = [ModelProvider.OPENAI, ModelProvider.AZURE_OPENAI]
    config = ModelLayerConfig(fallback_order=custom_order)
    assert config.fallback_order == custom_order
    assert config.fallback_order[0] == ModelProvider.OPENAI


def test_model_layer_config_per_provider_defaults_are_independent_instances() -> None:
    """Each ModelLayerConfig must have its own ProviderConfig instances."""
    config_a = ModelLayerConfig()
    config_b = ModelLayerConfig()
    config_a.foundry_local.base_url  # access to ensure it's initialized
    # They should not share the same object
    assert config_a.foundry_local is not config_b.foundry_local
