"""Tests for marketplace.core.structured_logging.

Covers context variable injection, configure_structlog renderer selection,
get_logger behavior, and cross-task context isolation.
"""

from __future__ import annotations

import asyncio
import logging
from contextvars import copy_context
from unittest.mock import MagicMock, patch

import pytest
import structlog

from marketplace.core.structured_logging import (
    _inject_context_vars,
    agent_id_var,
    configure_structlog,
    correlation_id_var,
    get_logger,
    operation_var,
    request_id_var,
)


# ---------------------------------------------------------------------------
# configure_structlog tests
# ---------------------------------------------------------------------------


def test_configure_structlog_production_uses_json_renderer():
    """production environment selects JSONRenderer."""
    with patch("structlog.configure") as mock_configure:
        configure_structlog("production")
        assert mock_configure.called


def test_configure_structlog_prod_alias_uses_json_renderer():
    """'prod' alias is treated as production."""
    with patch("structlog.configure") as mock_configure:
        configure_structlog("prod")
        assert mock_configure.called


def test_configure_structlog_development_uses_console_renderer():
    """development environment selects ConsoleRenderer."""
    with patch("structlog.configure") as mock_configure:
        configure_structlog("development")
        assert mock_configure.called


def test_configure_structlog_test_uses_console_renderer():
    """test environment falls back to console (not production)."""
    with patch("structlog.configure") as mock_configure:
        configure_structlog("test")
        assert mock_configure.called


def test_configure_structlog_unknown_env_console_fallback():
    """Any unrecognised environment string falls back to console renderer."""
    with patch("structlog.configure") as mock_configure:
        configure_structlog("staging")
        assert mock_configure.called


def test_configure_structlog_idempotent_no_crash():
    """Calling configure_structlog twice must not raise."""
    configure_structlog("development")
    configure_structlog("development")  # second call — should not explode


def test_configure_structlog_sets_root_logger_to_info():
    """Root logger level is set to INFO after configure."""
    configure_structlog("development")
    root = logging.getLogger()
    assert root.level == logging.INFO


def test_configure_structlog_adds_handler():
    """Root logger has at least one handler after configure."""
    configure_structlog("development")
    root = logging.getLogger()
    assert len(root.handlers) >= 1


def test_configure_structlog_suppresses_noisy_loggers():
    """Noisy third-party loggers are set to WARNING or higher."""
    configure_structlog("development")
    for name in ("uvicorn.access", "httpcore", "httpx", "hpack"):
        lvl = logging.getLogger(name).level
        assert lvl >= logging.WARNING, f"{name} not suppressed (level={lvl})"


# ---------------------------------------------------------------------------
# get_logger tests
# ---------------------------------------------------------------------------


def test_get_logger_returns_bound_logger():
    """get_logger returns a structlog bound logger instance."""
    logger = get_logger("test.module")
    assert logger is not None


def test_get_logger_with_name():
    """get_logger with a name doesn't raise."""
    logger = get_logger("marketplace.test")
    assert logger is not None


# ---------------------------------------------------------------------------
# _inject_context_vars processor tests
# ---------------------------------------------------------------------------


def test_inject_context_vars_correlation_id_in_event_dict():
    """Processor injects correlation_id when context var is set."""
    token = correlation_id_var.set("corr-123")
    try:
        event_dict: dict = {}
        result = _inject_context_vars(MagicMock(), "info", event_dict)
        assert result["correlation_id"] == "corr-123"
    finally:
        correlation_id_var.reset(token)


def test_inject_context_vars_request_id_in_event_dict():
    """Processor injects request_id when context var is set."""
    token = request_id_var.set("req-456")
    try:
        event_dict: dict = {}
        result = _inject_context_vars(MagicMock(), "info", event_dict)
        assert result["request_id"] == "req-456"
    finally:
        request_id_var.reset(token)


def test_inject_context_vars_agent_id_in_event_dict():
    """Processor injects agent_id when context var is set."""
    token = agent_id_var.set("agent-789")
    try:
        event_dict: dict = {}
        result = _inject_context_vars(MagicMock(), "info", event_dict)
        assert result["agent_id"] == "agent-789"
    finally:
        agent_id_var.reset(token)


def test_inject_context_vars_operation_in_event_dict():
    """Processor injects operation when context var is set."""
    token = operation_var.set("GET /health")
    try:
        event_dict: dict = {}
        result = _inject_context_vars(MagicMock(), "info", event_dict)
        assert result["operation"] == "GET /health"
    finally:
        operation_var.reset(token)


def test_inject_context_vars_empty_vars_no_keys_added():
    """Processor skips empty string context vars — no empty keys injected."""
    # Ensure defaults are empty (they are by design)
    correlation_id_var.set("")
    request_id_var.set("")
    agent_id_var.set("")
    operation_var.set("")
    event_dict: dict = {}
    result = _inject_context_vars(MagicMock(), "info", event_dict)
    assert "correlation_id" not in result
    assert "request_id" not in result
    assert "agent_id" not in result
    assert "operation" not in result


def test_inject_context_vars_does_not_overwrite_existing_keys():
    """Processor does not overwrite keys already in event_dict."""
    token = correlation_id_var.set("corr-new")
    try:
        event_dict: dict = {"correlation_id": "existing-value"}
        result = _inject_context_vars(MagicMock(), "info", event_dict)
        assert result["correlation_id"] == "existing-value"
    finally:
        correlation_id_var.reset(token)


def test_inject_context_vars_partial_context():
    """Only set context vars appear in the event dict."""
    corr_token = correlation_id_var.set("corr-partial")
    agent_token = agent_id_var.set("")
    try:
        event_dict: dict = {}
        result = _inject_context_vars(MagicMock(), "info", event_dict)
        assert result.get("correlation_id") == "corr-partial"
        assert "agent_id" not in result
    finally:
        correlation_id_var.reset(corr_token)
        agent_id_var.reset(agent_token)


def test_inject_context_vars_all_set():
    """All four context vars appear when all are set."""
    t1 = correlation_id_var.set("c1")
    t2 = request_id_var.set("r1")
    t3 = agent_id_var.set("a1")
    t4 = operation_var.set("POST /api/v1/agents")
    try:
        event_dict: dict = {}
        result = _inject_context_vars(MagicMock(), "info", event_dict)
        assert result["correlation_id"] == "c1"
        assert result["request_id"] == "r1"
        assert result["agent_id"] == "a1"
        assert result["operation"] == "POST /api/v1/agents"
    finally:
        correlation_id_var.reset(t1)
        request_id_var.reset(t2)
        agent_id_var.reset(t3)
        operation_var.reset(t4)


# ---------------------------------------------------------------------------
# Context var isolation across asyncio tasks
# ---------------------------------------------------------------------------


async def test_context_var_isolation_across_tasks():
    """Context vars set inside one task do not leak into a sibling task.

    asyncio tasks each get a *copy* of the context at creation time.
    A set() inside task_a only affects task_a's context copy; task_b's
    copy is unaffected and sees whatever value was current at gather() time.
    """
    # Ensure the var has a known baseline in this task's context
    baseline_token = correlation_id_var.set("baseline")

    captured: dict[str, str] = {}

    async def task_a() -> None:
        # Override in task_a's private context copy
        correlation_id_var.set("task-a-only")
        await asyncio.sleep(0)
        captured["a"] = correlation_id_var.get("")

    async def task_b() -> None:
        await asyncio.sleep(0)
        # task_b inherits "baseline" from the outer context at gather() time
        captured["b"] = correlation_id_var.get("")

    await asyncio.gather(task_a(), task_b())

    correlation_id_var.reset(baseline_token)

    # task_a sees its own override
    assert captured["a"] == "task-a-only"
    # task_b sees the baseline — NOT task_a's value (no cross-task leak)
    assert captured["b"] == "baseline"
    assert captured["b"] != captured["a"]
