"""Structured logging via structlog with context variable injection.

Provides JSON output in production and colorized console output in development.
All loggers auto-inject correlation_id, request_id, agent_id, and operation
from contextvars set by the correlation middleware.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

import structlog

# ---------------------------------------------------------------------------
# Context variables — set per-request by CorrelationMiddleware
# ---------------------------------------------------------------------------

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
agent_id_var: ContextVar[str] = ContextVar("agent_id", default="")
operation_var: ContextVar[str] = ContextVar("operation", default="")


def _inject_context_vars(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Structlog processor that injects context vars into every log entry."""
    ctx_fields = {
        "correlation_id": correlation_id_var.get(""),
        "request_id": request_id_var.get(""),
        "agent_id": agent_id_var.get(""),
        "operation": operation_var.get(""),
    }
    for key, value in ctx_fields.items():
        if value and key not in event_dict:
            event_dict[key] = value
    return event_dict


def configure_structlog(environment: str = "development") -> None:
    """Configure structlog with JSON (production) or console (development) renderer.

    Args:
        environment: One of "development", "test", "production".
    """
    is_prod = environment.lower() in {"production", "prod"}

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _inject_context_vars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_prod:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root_logger = logging.getLogger()
    # Remove existing handlers to avoid duplicate output
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Suppress noisy third-party loggers
    for noisy in ("uvicorn.access", "httpcore", "httpx", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger with context var injection."""
    return structlog.get_logger(name)
