"""Prometheus metrics definitions for AgentChains golden signals.

Exposes counters, histograms, and gauges for HTTP requests, agent calls,
model tokens, workflow state, and circuit breaker status.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# HTTP request metrics (golden signals)
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ---------------------------------------------------------------------------
# Agent / skill call metrics
# ---------------------------------------------------------------------------

AGENT_CALL_LATENCY = Histogram(
    "agent_call_duration_seconds",
    "Agent call latency in seconds",
    ["agent_id", "skill_id"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

AGENT_CALL_COST = Counter(
    "agent_call_cost_usd_total",
    "Cumulative cost of agent calls in USD",
    ["agent_id"],
)

# ---------------------------------------------------------------------------
# Model / LLM metrics
# ---------------------------------------------------------------------------

MODEL_TOKENS_TOTAL = Counter(
    "model_tokens_total",
    "Total tokens processed by model provider",
    ["model", "provider", "direction"],  # direction: prompt | completion
)

# ---------------------------------------------------------------------------
# Workflow / orchestration metrics
# ---------------------------------------------------------------------------

ACTIVE_WORKFLOWS = Gauge(
    "active_workflows",
    "Number of currently running workflows",
)

CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["agent_id"],
)
