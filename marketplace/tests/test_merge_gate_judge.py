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


# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Additional tests for uncovered lines
# ---------------------------------------------------------------------------

from unittest.mock import patch

from marketplace.services.merge_gate_judge import (
    _extract_json_fence,
    _load_report,
    _resolve_conflict,
    _run_command,
    _validate_lead_payload,
    _evaluate_golden_paths,
    write_final_verdict,
)


def test_extract_json_fence_no_fence(tmp_path):
    p = tmp_path / 'no_fence.md'
    p.write_text(chr(10).join(["# Report", "", "No JSON here."]), encoding="utf-8")
    with pytest.raises(ValueError, match='missing a JSON code fence'):
        _extract_json_fence(p)


def test_extract_json_fence_invalid_json(tmp_path):
    p = tmp_path / 'bad_json.md'
    fence = chr(96) * 3
    content_str = f"# Report" + chr(10) + f"{fence}json" + chr(10) + "{{bad json}}" + chr(10) + f"{fence}" + chr(10)
    p.write_text(content_str, encoding="utf-8")
    with pytest.raises(ValueError, match='invalid JSON'):
        _extract_json_fence(p)


def test_load_report_invalid_json_in_fence(tmp_path):
    p = tmp_path / 'bad_fence.md'
    fence = chr(96) * 3
    content_str = f"# Machine-Readable Evidence" + chr(10) + f"{fence}json" + chr(10) + "{{not valid}}" + chr(10) + f"{fence}" + chr(10)
    p.write_text(content_str, encoding="utf-8")
    payload, errors = _load_report(p, ('Machine-Readable Evidence',))
    assert len(errors) == 1
    assert 'invalid JSON' in errors[0]


def test_validate_lead_payload_missing_keys():
    payload = {'pod_id': 'A'}
    lead, errors = _validate_lead_payload(payload, 'A')
    assert lead is None
    assert any('missing key' in e for e in errors)


def test_validate_lead_payload_wrong_types():
    payload = {
        'pod_id': 'A', 'workstreams': 'not a list',
        'integration_tests_all_workstreams_passed': True,
        'test_inventory': {}, 'command_evidence': [],
        'failure_triage': [], 'coverage_evidence': {},
        'sweep_500': {}, 'edge_case_audit': {},
    }
    lead, errors = _validate_lead_payload(payload, 'A')
    assert lead is None
    assert any('must be' in e for e in errors)


def test_validate_lead_payload_pod_id_mismatch():
    payload = _lead_payload('A')
    payload['pod_id'] = 'X'
    lead, errors = _validate_lead_payload(payload, 'A')
    assert any('does not match filename' in e for e in errors)


def test_validate_lead_payload_missing_critical_path():
    payload = _lead_payload('A')
    payload['coverage_evidence'] = {'risk_module_coverage_percent': 95.0}
    lead, errors = _validate_lead_payload(payload, 'A')
    assert any('critical_path must be present' in e for e in errors)


def test_validate_lead_payload_missing_risk_coverage():
    payload = _lead_payload('A')
    payload['coverage_evidence'] = {'critical_path': {'login_auth': True}}
    lead, errors = _validate_lead_payload(payload, 'A')
    assert any('risk_module_coverage_percent' in e for e in errors)


def test_validate_lead_payload_missing_500_count():
    payload = _lead_payload('A')
    payload['sweep_500'] = {'routes_scanned': 100}
    lead, errors = _validate_lead_payload(payload, 'A')
    assert any('reproducible_500_count' in e for e in errors)


def test_validate_lead_payload_missing_edge_booleans():
    payload = _lead_payload('A')
    payload['edge_case_audit'] = {'security': 'not a bool'}
    lead, errors = _validate_lead_payload(payload, 'A')
    assert any('must be boolean' in e for e in errors)


def test_validate_lead_payload_disputed_not_list():
    payload = _lead_payload('A')
    payload['disputed_failures'] = 'not-a-list'
    lead, errors = _validate_lead_payload(payload, 'A')
    assert any('disputed_failures must be a list' in e for e in errors)


def test_run_command_success():
    assert _run_command('python -c "print(1)"') is True


def test_run_command_failure():
    assert _run_command('python -c "raise SystemExit(1)"') is False


def test_run_command_clean_env():
    cmd = 'python -c "import os; assert os.environ.get(chr(65)+chr(71)+chr(69)+chr(78)+chr(84)+chr(67)+chr(72)+chr(65)+chr(73)+chr(78)+chr(83)+chr(95)+chr(67)+chr(76)+chr(69)+chr(65)+chr(78)+chr(95)+chr(69)+chr(78)+chr(86))==chr(49)"' 
    assert _run_command(cmd, clean_env=True) is True


def test_resolve_conflict_no_run():
    d = _resolve_conflict({'test_id': 't-1'}, run_commands=False, same_env_runs=5, clean_env_runs=5)
    assert d.classification == 'blocker'
    assert 'rerun protocol' in d.reason


def test_resolve_conflict_no_command():
    d = _resolve_conflict({'test_id': 't-2'}, run_commands=True, same_env_runs=5, clean_env_runs=5)
    assert d.classification == 'blocker'
    assert 'missing same_env_command' in d.reason


@patch('marketplace.services.merge_gate_judge._run_command')
def test_resolve_conflict_all_pass(mock_run):
    mock_run.return_value = True
    d = _resolve_conflict({'test_id': 't-3', 'same_env_command': 'echo ok'}, True, 2, 2)
    assert d.classification == 'resolved'


@patch('marketplace.services.merge_gate_judge._run_command')
def test_resolve_conflict_clean_fail(mock_run):
    mock_run.side_effect = lambda cmd, clean_env=False, timeout_s=900: not clean_env
    d = _resolve_conflict({'test_id': 't-4', 'same_env_command': 'echo ok'}, True, 2, 2)
    assert d.classification == 'blocker'
    assert 'clean environment' in d.reason


@patch('marketplace.services.merge_gate_judge._run_command')
def test_resolve_conflict_flake(mock_run):
    state = {'c': 0}
    def _se(cmd, clean_env=False, timeout_s=900):
        state['c'] += 1
        return True if clean_env else state['c'] % 2 == 0
    mock_run.side_effect = _se
    d = _resolve_conflict({'test_id': 't-5', 'same_env_command': 'echo ok'}, True, 3, 2)
    assert d.classification == 'flake'


@patch('marketplace.services.merge_gate_judge._run_command')
def test_resolve_conflict_blocking_risk(mock_run):
    state = {'c': 0}
    def _se(cmd, clean_env=False, timeout_s=900):
        state['c'] += 1
        return False if (not clean_env and state['c'] == 1) else True
    mock_run.side_effect = _se
    d = _resolve_conflict({'test_id': 't-6', 'risk_tag': 'security', 'same_env_command': 'echo ok'}, True, 2, 2)
    assert d.classification == 'blocker'
    assert 'High-stakes' in d.reason


def test_golden_paths_steps_not_list():
    _, issues = _evaluate_golden_paths({'steps': 'not-a-list'})
    assert any('must be a list' in i for i in issues)


def test_golden_paths_step_not_dict():
    _, issues = _evaluate_golden_paths({'steps': ['not-a-dict']})
    assert any('must be an object' in i for i in issues)


def test_golden_paths_uncovered():
    _, issues = _evaluate_golden_paths({'steps': [{'path': 'login_auth', 'step': 'x', 'covered': False}]})
    assert any('uncovered step' in i for i in issues)


def test_golden_paths_failing():
    _, issues = _evaluate_golden_paths({'steps': [{'path': 'checkout', 'step': 'x', 'covered': True, 'passed': False}]})
    assert any('failing step' in i for i in issues)

def test_merge_gate_missing_lead(report_dir):
    _write_reports(report_dir)
    (report_dir / 'lead_pod_A.md').unlink()
    r = evaluate_merge_gate(report_dir)
    assert r.decision == 'NO-GO'
    assert any('Missing required lead report' in i for i in r.issues)


def test_merge_gate_low_risk_coverage(report_dir):
    _write_reports(report_dir)
    p = _lead_payload('B')
    p['coverage_evidence']['risk_module_coverage_percent'] = 50.0
    (report_dir / 'lead_pod_B.md').write_text(_lead_markdown('B', p), encoding='utf-8')
    r = evaluate_merge_gate(report_dir)
    assert any('risk coverage' in i for i in r.issues)


def test_merge_gate_integration_failing(report_dir):
    _write_reports(report_dir)
    p = _lead_payload('C')
    p['integration_tests_all_workstreams_passed'] = False
    (report_dir / 'lead_pod_C.md').write_text(_lead_markdown('C', p), encoding='utf-8')
    r = evaluate_merge_gate(report_dir)
    assert any('integration tests' in i for i in r.issues)


def test_merge_gate_sweep_500_pod(report_dir):
    _write_reports(report_dir)
    p = _lead_payload('D')
    p['sweep_500']['reproducible_500_count'] = 3
    (report_dir / 'lead_pod_D.md').write_text(_lead_markdown('D', p), encoding='utf-8')
    r = evaluate_merge_gate(report_dir)
    assert any('500 sweep' in i for i in r.issues)


def test_merge_gate_critical_path_fail(report_dir):
    _write_reports(report_dir)
    p = _lead_payload('E')
    p['coverage_evidence']['critical_path']['checkout'] = False
    (report_dir / 'lead_pod_E.md').write_text(_lead_markdown('E', p), encoding='utf-8')
    r = evaluate_merge_gate(report_dir)
    assert any('critical path' in i for i in r.issues)


def test_merge_gate_edge_case_missing(report_dir):
    _write_reports(report_dir)
    for pod in ('A', 'B', 'C', 'D', 'E'):
        p = _lead_payload(pod)
        p['edge_case_audit']['security'] = False
        (report_dir / f'lead_pod_{pod}.md').write_text(_lead_markdown(pod, p), encoding='utf-8')
    r = evaluate_merge_gate(report_dir)
    assert any('Edge-case audit' in i for i in r.issues)


def test_merge_gate_redundancy_budget(report_dir):
    _write_reports(report_dir)
    import json as _json
    rp = {'ci_budget': {'within_budget': False}}
    fence = chr(96) * 3
    txt = f"# Redundancy Audit Report" + chr(10)*2 + "## Machine-Readable Evidence" + chr(10)*2 + f"{fence}json" + chr(10) + _json.dumps(rp) + chr(10) + f"{fence}" + chr(10)
    (report_dir / 'redundancy_audit_report.md').write_text(txt, encoding='utf-8')
    r = evaluate_merge_gate(report_dir)
    assert any('CI budget' in i for i in r.issues)


def test_merge_gate_missing_files(report_dir):
    _write_reports(report_dir)
    (report_dir / 'golden_path_coverage_matrix.md').unlink()
    (report_dir / 'error_500_ledger.md').unlink()
    (report_dir / 'redundancy_audit_report.md').unlink()
    r = evaluate_merge_gate(report_dir)
    assert r.decision == 'NO-GO'


def test_merge_gate_disputes_processed(report_dir):
    _write_reports(report_dir)
    p = _lead_payload('A')
    p['disputed_failures'] = [{'test_id': 'cf-01', 'same_env_command': 'echo ok'}]
    (report_dir / 'lead_pod_A.md').write_text(_lead_markdown('A', p), encoding='utf-8')
    r = evaluate_merge_gate(report_dir, run_conflicts=False)
    assert any(d.test_id == 'cf-01' for d in r.conflict_decisions)


def test_merge_gate_dup_dispute(report_dir):
    _write_reports(report_dir)
    dispute = {'test_id': 'dup-01', 'same_env_command': 'echo ok'}
    for pod in ('A', 'B'):
        p = _lead_payload(pod)
        p['disputed_failures'] = [dispute]
        (report_dir / f'lead_pod_{pod}.md').write_text(_lead_markdown(pod, p), encoding='utf-8')
    r = evaluate_merge_gate(report_dir, run_conflicts=False)
    assert len([d for d in r.conflict_decisions if d.test_id == 'dup-01']) == 1


def test_render_no_go_rework(report_dir):
    _write_reports(report_dir)
    p = _lead_payload('A')
    p['integration_tests_all_workstreams_passed'] = False
    (report_dir / 'lead_pod_A.md').write_text(_lead_markdown('A', p), encoding='utf-8')
    r = evaluate_merge_gate(report_dir)
    rendered = render_final_verdict(r)
    assert '## Mandatory Rework' in rendered


def test_render_conflict_table(report_dir):
    _write_reports(report_dir)
    p = _lead_payload('A')
    p['disputed_failures'] = [{'test_id': 'tbl-01', 'same_env_command': 'echo ok'}]
    (report_dir / 'lead_pod_A.md').write_text(_lead_markdown('A', p), encoding='utf-8')
    r = evaluate_merge_gate(report_dir, run_conflicts=False)
    rendered = render_final_verdict(r)
    assert '| test_id |' in rendered
    assert 'tbl-01' in rendered


def test_write_verdict_file(report_dir, tmp_path):
    _write_reports(report_dir)
    r = evaluate_merge_gate(report_dir)
    out = tmp_path / 'sub' / 'verdict.md'
    ret = write_final_verdict(r, out)
    assert ret == out and out.exists()


def test_render_go_none_rework(report_dir):
    _write_reports(report_dir)
    r = evaluate_merge_gate(report_dir)
    assert r.decision == 'GO'
    assert '- None.' in render_final_verdict(r)
