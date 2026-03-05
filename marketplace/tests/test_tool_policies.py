"""Tests for marketplace.mcp.tools — TOOL_POLICIES dict and TOOL_DEFINITIONS."""

from __future__ import annotations

import pytest

from marketplace.mcp.tools import TOOL_DEFINITIONS, TOOL_POLICIES

_VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}


# ---------------------------------------------------------------------------
# Coverage and consistency
# ---------------------------------------------------------------------------


def test_all_tool_definitions_have_policies() -> None:
    """Every entry in TOOL_DEFINITIONS must have a matching TOOL_POLICIES entry."""
    definition_names = {defn["name"] for defn in TOOL_DEFINITIONS}
    policy_names = set(TOOL_POLICIES.keys())
    missing = definition_names - policy_names
    assert missing == set(), f"Tools without policies: {missing}"


def test_no_orphan_policies() -> None:
    """Every TOOL_POLICIES entry must correspond to a tool in TOOL_DEFINITIONS."""
    definition_names = {defn["name"] for defn in TOOL_DEFINITIONS}
    policy_names = set(TOOL_POLICIES.keys())
    orphans = policy_names - definition_names
    assert orphans == set(), f"Policies with no tool definition: {orphans}"


def test_tool_definitions_names_unique() -> None:
    names = [defn["name"] for defn in TOOL_DEFINITIONS]
    assert len(names) == len(set(names)), "Duplicate tool names in TOOL_DEFINITIONS"


# ---------------------------------------------------------------------------
# Risk level validation
# ---------------------------------------------------------------------------


def test_all_risk_levels_valid() -> None:
    for tool_name, policy in TOOL_POLICIES.items():
        rl = policy.get("risk_level")
        assert rl in _VALID_RISK_LEVELS, (
            f"Tool '{tool_name}' has invalid risk_level '{rl}'"
        )


# ---------------------------------------------------------------------------
# Timeout values
# ---------------------------------------------------------------------------


def test_all_policy_timeouts_positive() -> None:
    for tool_name, policy in TOOL_POLICIES.items():
        timeout = policy.get("timeout_seconds")
        assert isinstance(timeout, (int, float)), (
            f"Tool '{tool_name}' has non-numeric timeout: {timeout!r}"
        )
        assert timeout > 0, f"Tool '{tool_name}' has non-positive timeout: {timeout}"


# ---------------------------------------------------------------------------
# Specific tool policies
# ---------------------------------------------------------------------------


def test_marketplace_discover_is_low_risk() -> None:
    policy = TOOL_POLICIES["marketplace_discover"]
    assert policy["risk_level"] == "low"


def test_marketplace_discover_timeout_10s() -> None:
    policy = TOOL_POLICIES["marketplace_discover"]
    assert policy["timeout_seconds"] == 10


def test_marketplace_express_buy_is_high_risk() -> None:
    policy = TOOL_POLICIES["marketplace_express_buy"]
    assert policy["risk_level"] == "high"


def test_marketplace_express_buy_requires_consent() -> None:
    policy = TOOL_POLICIES["marketplace_express_buy"]
    assert policy.get("requires_consent") is True


def test_webmcp_execute_action_is_critical_risk() -> None:
    policy = TOOL_POLICIES["webmcp_execute_action"]
    assert policy["risk_level"] == "critical"


def test_webmcp_execute_action_requires_consent() -> None:
    policy = TOOL_POLICIES["webmcp_execute_action"]
    assert policy.get("requires_consent") is True


def test_webmcp_execute_action_longer_timeout() -> None:
    """webmcp_execute_action is allowed a longer timeout than the 30s default."""
    policy = TOOL_POLICIES["webmcp_execute_action"]
    assert policy["timeout_seconds"] > 30


def test_marketplace_discover_no_consent_required() -> None:
    policy = TOOL_POLICIES["marketplace_discover"]
    # Either not present or explicitly False
    assert not policy.get("requires_consent", False)


def test_most_tools_have_30s_or_less_timeout() -> None:
    """Most tools should have reasonable timeouts (at or under 30s), except long-running ones."""
    long_timeout_allowed = {"webmcp_execute_action"}
    for tool_name, policy in TOOL_POLICIES.items():
        if tool_name in long_timeout_allowed:
            continue
        assert policy["timeout_seconds"] <= 30, (
            f"Tool '{tool_name}' has unexpectedly long timeout: {policy['timeout_seconds']}s"
        )
