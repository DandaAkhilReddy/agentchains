"""Cost and latency budget tracking for workflow execution.

Provides per-operation latency budgets and per-workflow cost budgets
with warning thresholds and hard limits.
"""

from __future__ import annotations

import structlog

from marketplace.core.exceptions import DomainError

logger = structlog.get_logger(__name__)


class BudgetExceededError(DomainError):
    """Raised when a cost or latency hard limit is exceeded."""

    code = "BUDGET_EXCEEDED"
    http_status = 429


class LatencyBudget:
    """Per-operation latency thresholds in milliseconds."""

    def __init__(self, warn_ms: int = 1000, hard_limit_ms: int = 5000) -> None:
        self.warn_ms = warn_ms
        self.hard_limit_ms = hard_limit_ms


class CostBudget:
    """Per-workflow cost thresholds in USD."""

    def __init__(self, warn_usd: float = 1.00, hard_limit_usd: float = 10.00) -> None:
        self.warn_usd = warn_usd
        self.hard_limit_usd = hard_limit_usd


class BudgetTracker:
    """Tracks cumulative cost and per-operation latency against budgets."""

    def __init__(
        self,
        cost_budget: CostBudget | None = None,
        latency_budget: LatencyBudget | None = None,
    ) -> None:
        self.cost_budget = cost_budget or CostBudget()
        self.latency_budget = latency_budget or LatencyBudget()
        self._total_cost_usd: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost_usd

    def record_cost(self, amount_usd: float, operation: str) -> None:
        """Record a cost increment. Warns or raises on budget violations."""
        self._total_cost_usd += amount_usd

        if self._total_cost_usd >= self.cost_budget.hard_limit_usd:
            logger.error(
                "cost_budget_exceeded",
                total_cost_usd=self._total_cost_usd,
                hard_limit_usd=self.cost_budget.hard_limit_usd,
                operation=operation,
            )
            raise BudgetExceededError(
                f"Cost budget exceeded: ${self._total_cost_usd:.4f} >= "
                f"${self.cost_budget.hard_limit_usd:.2f} (operation: {operation})"
            )

        if self._total_cost_usd >= self.cost_budget.warn_usd:
            logger.warning(
                "cost_budget_warning",
                total_cost_usd=self._total_cost_usd,
                warn_usd=self.cost_budget.warn_usd,
                operation=operation,
            )

    def record_latency(self, duration_ms: float, operation: str) -> None:
        """Record an operation's latency. Warns or raises on budget violations."""
        if duration_ms >= self.latency_budget.hard_limit_ms:
            logger.error(
                "latency_budget_exceeded",
                duration_ms=duration_ms,
                hard_limit_ms=self.latency_budget.hard_limit_ms,
                operation=operation,
            )
            raise BudgetExceededError(
                f"Latency budget exceeded: {duration_ms:.0f}ms >= "
                f"{self.latency_budget.hard_limit_ms}ms (operation: {operation})"
            )

        if duration_ms >= self.latency_budget.warn_ms:
            logger.warning(
                "latency_budget_warning",
                duration_ms=duration_ms,
                warn_ms=self.latency_budget.warn_ms,
                operation=operation,
            )
