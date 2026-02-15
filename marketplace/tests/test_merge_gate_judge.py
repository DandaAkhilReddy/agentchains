"""Tests for Agent 51 merge-gate evaluation."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile

import pytest
from marketplace.services.merge_gate_judge import evaluate_merge_gate, render_final_verdict


def _lead_payload(pod_id: str) -> dict:
    base = int((ord(pod_id) - ord("A")) * 10)
    return {
        "pod_id": pod_id,
        "workstreams": [f"agent-{base + i + 1:02d}" for i in range(10)],
        "integration_tests_all_workstreams_passed": True,
        "test_inventory": {
            "tests_added": 5,
            "tests_updated": 3,
            "integration_suites_run": ["python -m pytest marketplace/tests -q"],
        },
        "command_evidence": [
            {
                "command": "python -m pytest marketplace/tests -q",
                "pass_count": 120,
                "fail_count": 0,
                "rerun_count": 0,
            }
        ],
        "failure_triage": [],
        "coverage_evidence": {
            "critical_path": {
                "login_auth": True,
                "checkout": True,
                "data_persistence": True,
            },
            "risk_module_coverage_percent": 95.0,
        },
        "sweep_500": {
            "routes_scanned": 120,
            "reproducible_500_count": 0,
            "reproducible_routes": [],
        },
        "edge_case_audit": {
            "security": True,
            "data_integrity": True,
            "reliability": True,
        },
        "disputed_failures": [],
    }


def _lead_markdown(pod_id: str, payload: dict) -> str:
    return (
        f"# Lead Pod {pod_id} Report\n\n"
        "## Pod Scope Summary\n\n"
        "- scope\n\n"
        "## Test Inventory\n\n"
        "- inventory\n\n"
        "## Command Evidence\n\n"
        "- commands\n\n"
        "## Failure Triage\n\n"
        "- triage\n\n"
        "## Coverage Evidence\n\n"
        "- coverage\n\n"
        "## 500 Sweep Evidence\n\n"
        "- sweep\n\n"
        "## Edge-Case Audit\n\n"
        "- edge\n\n"
        "## Machine-Readable Evidence\n\n"
        "```json\n"
        f"{json.dumps(payload, indent=2)}\n"
        "```\n"
    )


def _write_reports(report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    for pod in ("A", "B", "C", "D", "E"):
        payload = _lead_payload(pod)
        (report_dir / f"lead_pod_{pod}.md").write_text(
            _lead_markdown(pod, payload), encoding="utf-8"
        )

    golden_payload = {
        "steps": [
            {
                "path": "login_auth",
                "step": "creator register/login/token use",
                "test_ids": ["login_01"],
                "covered": True,
                "passed": True,
            },
            {
                "path": "checkout",
                "step": "express checkout flow",
                "test_ids": ["checkout_01"],
                "covered": True,
                "passed": True,
            },
            {
                "path": "data_persistence",
                "step": "transaction + ledger persistence",
                "test_ids": ["persist_01"],
                "covered": True,
                "passed": True,
            },
        ]
    }
    (report_dir / "golden_path_coverage_matrix.md").write_text(
        (
            "# Golden Path Coverage Matrix\n\n"
            "## Machine-Readable Evidence\n\n"
            "```json\n"
            f"{json.dumps(golden_payload, indent=2)}\n"
            "```\n"
        ),
        encoding="utf-8",
    )

    ledger_payload = {
        "reproducible_500_count": 0,
        "entries": [],
    }
    (report_dir / "error_500_ledger.md").write_text(
        (
            "# 500 Error Ledger\n\n"
            "## Machine-Readable Evidence\n\n"
            "```json\n"
            f"{json.dumps(ledger_payload, indent=2)}\n"
            "```\n"
        ),
        encoding="utf-8",
    )

    redundancy_payload = {
        "ci_budget": {
            "pr_max_minutes": 20,
            "current_pr_minutes": 12,
            "within_budget": True,
        },
        "duplicates": [],
    }
    (report_dir / "redundancy_audit_report.md").write_text(
        (
            "# Redundancy Audit Report\n\n"
            "## Machine-Readable Evidence\n\n"
            "```json\n"
            f"{json.dumps(redundancy_payload, indent=2)}\n"
            "```\n"
        ),
        encoding="utf-8",
    )


@pytest.fixture()
def report_dir() -> Path:
    base = Path(".local") / "pytest-merge-gate"
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="judge-", dir=base))
    try:
        yield path / "reports"
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_merge_gate_returns_go_when_all_requirements_pass(report_dir: Path):
    _write_reports(report_dir)

    result = evaluate_merge_gate(report_dir)

    assert result.decision == "GO"
    assert not result.issues
    assert result.golden_path_summary == {
        "login_auth": True,
        "checkout": True,
        "data_persistence": True,
    }
    assert result.reproducible_500_count == 0
    assert result.redundancy_within_budget is True


def test_merge_gate_returns_no_go_when_golden_path_missing(report_dir: Path):
    _write_reports(report_dir)

    payload = {
        "steps": [
            {
                "path": "login_auth",
                "step": "creator register/login/token use",
                "test_ids": ["login_01"],
                "covered": True,
                "passed": True,
            },
            {
                "path": "data_persistence",
                "step": "transaction + ledger persistence",
                "test_ids": ["persist_01"],
                "covered": True,
                "passed": True,
            },
        ]
    }
    (report_dir / "golden_path_coverage_matrix.md").write_text(
        (
            "# Golden Path Coverage Matrix\n\n"
            "## Machine-Readable Evidence\n\n"
            "```json\n"
            f"{json.dumps(payload, indent=2)}\n"
            "```\n"
        ),
        encoding="utf-8",
    )

    result = evaluate_merge_gate(report_dir)

    assert result.decision == "NO-GO"
    assert any("Golden Path 'checkout'" in issue for issue in result.issues)


def test_merge_gate_returns_no_go_when_reproducible_500_exists(report_dir: Path):
    _write_reports(report_dir)

    payload = {
        "reproducible_500_count": 1,
        "entries": [{"route": "/api/v1/test", "method": "GET", "reproducible": True}],
    }
    (report_dir / "error_500_ledger.md").write_text(
        (
            "# 500 Error Ledger\n\n"
            "## Machine-Readable Evidence\n\n"
            "```json\n"
            f"{json.dumps(payload, indent=2)}\n"
            "```\n"
        ),
        encoding="utf-8",
    )

    result = evaluate_merge_gate(report_dir)

    assert result.decision == "NO-GO"
    assert any("reproducible_500_count=1" in issue for issue in result.issues)


def test_merge_gate_returns_no_go_when_blocker_unresolved(report_dir: Path):
    _write_reports(report_dir)

    pod_a_payload = _lead_payload("A")
    pod_a_payload["failure_triage"] = [
        {
            "test_id": "checkout_blocker_01",
            "classification": "blocker",
            "status": "open",
            "root_cause": "deterministic failure",
            "regression_test_ids": [],
        }
    ]
    (report_dir / "lead_pod_A.md").write_text(
        _lead_markdown("A", pod_a_payload), encoding="utf-8"
    )

    result = evaluate_merge_gate(report_dir)

    assert result.decision == "NO-GO"
    assert any("unresolved blocker triage item" in issue for issue in result.issues)


def test_merge_gate_returns_no_go_when_lead_report_missing_required_heading(report_dir: Path):
    _write_reports(report_dir)

    bad_text = (
        "# Lead Pod A Report\n\n"
        "## Pod Scope Summary\n\n"
        "- missing mandatory sections intentionally\n"
    )
    (report_dir / "lead_pod_A.md").write_text(bad_text, encoding="utf-8")

    result = evaluate_merge_gate(report_dir)

    assert result.decision == "NO-GO"
    assert any("lead_pod_A.md: missing heading" in issue for issue in result.issues)


def test_rendered_verdict_contains_required_sections(report_dir: Path):
    _write_reports(report_dir)

    result = evaluate_merge_gate(report_dir)
    rendered = render_final_verdict(result)

    assert "## Decision: `GO`" in rendered
    assert "## Conflict Decisions" in rendered
    assert "## Golden Path Matrix" in rendered
    assert "## 500 Ledger Result" in rendered
    assert "## Redundancy Findings" in rendered
    assert "## Edge-Case Audit Result" in rendered
    assert "## Mandatory Rework" in rendered
