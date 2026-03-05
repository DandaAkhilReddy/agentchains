"""Tests for marketplace.core.budgets.

Covers CostBudget, LatencyBudget, BudgetTracker, and BudgetExceededError.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from marketplace.core.budgets import (
    BudgetExceededError,
    BudgetTracker,
    CostBudget,
    LatencyBudget,
)
from marketplace.core.exceptions import DomainError


# ---------------------------------------------------------------------------
# BudgetExceededError
# ---------------------------------------------------------------------------


def test_budget_exceeded_error_is_domain_error():
    """BudgetExceededError inherits from DomainError."""
    err = BudgetExceededError("test")
    assert isinstance(err, DomainError)


def test_budget_exceeded_error_code():
    """BudgetExceededError has code='BUDGET_EXCEEDED'."""
    assert BudgetExceededError.code == "BUDGET_EXCEEDED"


def test_budget_exceeded_error_http_status():
    """BudgetExceededError maps to HTTP 429."""
    assert BudgetExceededError.http_status == 429


def test_budget_exceeded_error_detail_message():
    """BudgetExceededError stores detail message."""
    err = BudgetExceededError("cost exceeded")
    assert "cost exceeded" in str(err)


# ---------------------------------------------------------------------------
# CostBudget defaults
# ---------------------------------------------------------------------------


def test_cost_budget_defaults():
    """CostBudget default warn=1.00, hard=10.00."""
    budget = CostBudget()
    assert budget.warn_usd == 1.00
    assert budget.hard_limit_usd == 10.00


def test_cost_budget_custom_values():
    """CostBudget accepts custom thresholds."""
    budget = CostBudget(warn_usd=0.50, hard_limit_usd=5.00)
    assert budget.warn_usd == 0.50
    assert budget.hard_limit_usd == 5.00


# ---------------------------------------------------------------------------
# LatencyBudget defaults
# ---------------------------------------------------------------------------


def test_latency_budget_defaults():
    """LatencyBudget default warn=1000ms, hard=5000ms."""
    budget = LatencyBudget()
    assert budget.warn_ms == 1000
    assert budget.hard_limit_ms == 5000


def test_latency_budget_custom_values():
    """LatencyBudget accepts custom thresholds."""
    budget = LatencyBudget(warn_ms=500, hard_limit_ms=2000)
    assert budget.warn_ms == 500
    assert budget.hard_limit_ms == 2000


# ---------------------------------------------------------------------------
# BudgetTracker — cost checks
# ---------------------------------------------------------------------------


def test_cost_below_warn_no_warning_no_raise():
    """Cost well below warn threshold — no log, no raise."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=10.00))
    # $0.50 is below warn threshold
    tracker.record_cost(0.50, "op1")  # no exception


def test_cost_at_warn_threshold_logs_warning():
    """Cost exactly at warn threshold triggers a warning log, no raise."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=10.00))
    with patch("marketplace.core.budgets.logger") as mock_log:
        tracker.record_cost(1.00, "op-warn")
        mock_log.warning.assert_called_once()


def test_cost_above_warn_below_hard_logs_warning_no_raise():
    """Cost between warn and hard limit logs warning but does not raise."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=10.00))
    with patch("marketplace.core.budgets.logger") as mock_log:
        tracker.record_cost(5.00, "op-between")
        mock_log.warning.assert_called_once()
        mock_log.error.assert_not_called()


def test_cost_at_hard_limit_raises():
    """Cost exactly at hard limit raises BudgetExceededError."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=10.00))
    with pytest.raises(BudgetExceededError):
        tracker.record_cost(10.00, "op-hard")


def test_cost_exceeds_hard_limit_raises():
    """Cost beyond hard limit raises BudgetExceededError."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=10.00))
    with pytest.raises(BudgetExceededError):
        tracker.record_cost(15.00, "op-over")


def test_cost_cumulative_multiple_calls_raises():
    """Multiple small costs that sum to >= hard limit raise BudgetExceededError."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=5.00))
    tracker.record_cost(2.00, "step1")
    tracker.record_cost(2.00, "step2")
    with pytest.raises(BudgetExceededError):
        tracker.record_cost(1.00, "step3")  # total = 5.00 == hard limit


def test_cost_error_message_contains_operation():
    """BudgetExceededError message includes the operation name."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=0.01, hard_limit_usd=0.50))
    with pytest.raises(BudgetExceededError) as exc_info:
        tracker.record_cost(1.00, "my-op-name")
    assert "my-op-name" in str(exc_info.value)


def test_cost_negative_amount_no_raise():
    """Negative cost adjustment does not trigger any budget violation."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=10.00))
    tracker.record_cost(-0.50, "credit")  # no exception


def test_cost_zero_hard_limit_immediate_raise():
    """Hard limit of 0.0 raises immediately on any positive cost."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=0.0, hard_limit_usd=0.0))
    with pytest.raises(BudgetExceededError):
        tracker.record_cost(0.01, "any-op")


def test_float_precision_near_warn_threshold():
    """Float accumulation near threshold (0.1 + 0.2) is handled correctly."""
    # 0.1 + 0.2 in IEEE 754 = 0.30000000000000004, still below warn=1.0
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=10.00))
    tracker.record_cost(0.1, "step1")
    tracker.record_cost(0.2, "step2")
    # No raise expected; cumulative < warn_usd
    assert tracker.total_cost_usd < 1.0


# ---------------------------------------------------------------------------
# BudgetTracker — latency checks
# ---------------------------------------------------------------------------


def test_latency_below_warn_no_warning_no_raise():
    """Latency well below warn threshold — no log, no raise."""
    tracker = BudgetTracker(latency_budget=LatencyBudget(warn_ms=1000, hard_limit_ms=5000))
    tracker.record_latency(500.0, "fast-op")  # no exception


def test_latency_at_warn_threshold_logs_warning():
    """Latency at warn threshold triggers a warning log."""
    tracker = BudgetTracker(latency_budget=LatencyBudget(warn_ms=1000, hard_limit_ms=5000))
    with patch("marketplace.core.budgets.logger") as mock_log:
        tracker.record_latency(1000.0, "slow-op")
        mock_log.warning.assert_called_once()


def test_latency_exceeds_hard_limit_raises():
    """Latency at or beyond hard limit raises BudgetExceededError."""
    tracker = BudgetTracker(latency_budget=LatencyBudget(warn_ms=1000, hard_limit_ms=5000))
    with pytest.raises(BudgetExceededError):
        tracker.record_latency(5000.0, "timeout-op")


def test_latency_error_message_contains_operation():
    """BudgetExceededError from latency includes the operation name."""
    tracker = BudgetTracker(latency_budget=LatencyBudget(warn_ms=100, hard_limit_ms=200))
    with pytest.raises(BudgetExceededError) as exc_info:
        tracker.record_latency(300.0, "latency-op-name")
    assert "latency-op-name" in str(exc_info.value)


# ---------------------------------------------------------------------------
# BudgetTracker — combined / optional budgets
# ---------------------------------------------------------------------------


def test_budget_tracker_combined_cost_and_latency():
    """BudgetTracker with both budgets records each independently."""
    tracker = BudgetTracker(
        cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=10.00),
        latency_budget=LatencyBudget(warn_ms=1000, hard_limit_ms=5000),
    )
    tracker.record_cost(0.10, "call")
    tracker.record_latency(200.0, "call")
    assert tracker.total_cost_usd == pytest.approx(0.10)


def test_budget_tracker_cost_only():
    """BudgetTracker with only cost budget still works for cost calls."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=5.00))
    tracker.record_cost(0.50, "op")
    assert tracker.total_cost_usd == pytest.approx(0.50)


def test_budget_tracker_latency_only():
    """BudgetTracker with only latency budget works for latency calls."""
    tracker = BudgetTracker(latency_budget=LatencyBudget(warn_ms=500, hard_limit_ms=2000))
    tracker.record_latency(100.0, "op")  # no exception


def test_budget_tracker_reset_resets_cumulative_cost():
    """Directly resetting _total_cost_usd brings total back to 0.0."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=10.00, hard_limit_usd=100.00))
    tracker.record_cost(5.00, "before-reset")
    assert tracker.total_cost_usd == pytest.approx(5.00)
    tracker._total_cost_usd = 0.0
    assert tracker.total_cost_usd == pytest.approx(0.0)


def test_budget_tracker_reset_allows_further_recording():
    """After manual reset, further costs accumulate from zero."""
    tracker = BudgetTracker(cost_budget=CostBudget(warn_usd=1.00, hard_limit_usd=5.00))
    tracker.record_cost(3.00, "pre")
    tracker._total_cost_usd = 0.0
    tracker.record_cost(2.00, "post")
    assert tracker.total_cost_usd == pytest.approx(2.00)


def test_budget_tracker_default_construction():
    """BudgetTracker with no arguments uses default budgets."""
    tracker = BudgetTracker()
    assert tracker.cost_budget.warn_usd == 1.00
    assert tracker.cost_budget.hard_limit_usd == 10.00
    assert tracker.latency_budget.warn_ms == 1000
    assert tracker.latency_budget.hard_limit_ms == 5000
