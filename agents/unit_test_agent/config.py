"""Configuration for the Unit Testing Agent pipeline.

Frozen dataclass with retry limits and pass thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitTestAgentConfig:
    """Immutable configuration for the test pipeline.

    Attributes:
        coverage_max_retries: Max retries for coverage judge (layer 1).
        quality_max_retries: Max retries for quality judge (layer 2).
        adversarial_max_retries: Max retries for adversarial judge (layer 3).
        total_max_iterations: Hard budget cap across all retries.
        coverage_threshold: Minimum score (0-100) to pass coverage judge.
        quality_threshold: Minimum score (0-100) to pass quality judge.
        adversarial_threshold: Minimum score (0-100) to pass adversarial judge.
        model: Model identifier for LLM calls.
        temperature: Sampling temperature for generation.
        max_tokens: Max tokens per LLM call.
    """

    coverage_max_retries: int = 3
    quality_max_retries: int = 3
    adversarial_max_retries: int = 2
    total_max_iterations: int = 8
    coverage_threshold: float = 80.0
    quality_threshold: float = 70.0
    adversarial_threshold: float = 70.0
    model: str = ""
    temperature: float = 0.4
    max_tokens: int = 4096
