"""Model Layer type definitions — provider-agnostic request/response types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModelProvider(str, Enum):
    """Supported model providers."""

    FOUNDRY_LOCAL = "foundry_local"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"


@dataclass(frozen=True)
class ModelSpec:
    """Specification for a model to use."""

    provider: ModelProvider
    model_id: str
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout_seconds: float = 30.0


@dataclass
class CompletionRequest:
    """Provider-agnostic completion request."""

    messages: list[dict[str, Any]]
    model: str = ""
    tools: list[dict[str, Any]] | None = None
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class ToolCall:
    """Represents a tool/function call from the model."""

    id: str
    name: str
    arguments: str  # JSON string


@dataclass
class CompletionResponse:
    """Provider-agnostic completion response with cost/latency metadata."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    provider: ModelProvider = ModelProvider.AZURE_OPENAI
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0


@dataclass
class ModelHealth:
    """Health check result for a model provider."""

    provider: ModelProvider
    available: bool
    latency_ms: float = 0.0
    error: str = ""
