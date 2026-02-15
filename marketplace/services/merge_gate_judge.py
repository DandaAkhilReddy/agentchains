"""Agent 51 merge-gate evaluation logic."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import random
import re
import shlex
import subprocess
from typing import Any

LEAD_PODS = ("A", "B", "C", "D", "E")

LEAD_REQUIRED_HEADINGS = (
    "Pod Scope Summary",
    "Test Inventory",
    "Command Evidence",
    "Failure Triage",
    "Coverage Evidence",
    "500 Sweep Evidence",
    "Edge-Case Audit",
    "Machine-Readable Evidence",
)

GOLDEN_REQUIRED_HEADINGS = ("Golden Path Coverage Matrix", "Machine-Readable Evidence")
LEDGER_REQUIRED_HEADINGS = ("500 Error Ledger", "Machine-Readable Evidence")
REDUNDANCY_REQUIRED_HEADINGS = ("Redundancy Audit Report", "Machine-Readable Evidence")

RISK_TAGS_BLOCKING = {"security", "data_loss", "golden_path"}
SEVERE_CLASSIFICATIONS = {"blocker", "unknown"}
JSON_FENCE_PATTERN = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
HEADING_PATTERN = re.compile(r"^\s*#+\s*(.+?)\s*$", re.MULTILINE)


@dataclass
class ConflictDecision:
    test_id: str
    classification: str
    reason: str
    same_env_failures: int = 0
    clean_env_failures: int = 0


@dataclass
class JudgeResult:
    decision: str
    issues: list[str]
    warnings: list[str]
    reports_checked: list[str]
    conflict_decisions: list[ConflictDecision]
    golden_path_summary: dict[str, bool]
    reproducible_500_count: int
    redundancy_within_budget: bool
    edge_case_summary: dict[str, bool]


@dataclass
class LeadEvidence:
    pod_id: str
    workstreams: list[str]
    integration_tests_all_workstreams_passed: bool
    test_inventory: dict[str, Any]
    command_evidence: list[dict[str, Any]]
    failure_triage: list[dict[str, Any]]
    coverage_evidence: dict[str, Any]
    sweep_500: dict[str, Any]
    edge_case_audit: dict[str, Any]
    disputed_failures: list[dict[str, Any]] = field(default_factory=list)


def _normalize_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _find_missing_headings(text: str, required_headings: tuple[str, ...]) -> list[str]:
    present = {_normalize_heading(item) for item in HEADING_PATTERN.findall(text)}
    missing: list[str] = []
    for heading in required_headings:
        if _normalize_heading(heading) not in present:
            missing.append(heading)
    return missing


def _extract_json_fence(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    matches = JSON_FENCE_PATTERN.findall(text)
    if not matches:
        raise ValueError(f"{path} is missing a JSON code fence")
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} has invalid JSON in the machine-readable block: {exc}") from exc


def _load_report(path: Path, required_headings: tuple[str, ...]) -> tuple[dict[str, Any], list[str]]:
    text = path.read_text(encoding="utf-8")
    missing_headings = _find_missing_headings(text, required_headings)
    errors = [f"{path}: missing heading '{heading}'" for heading in missing_headings]
    if errors:
        return {}, errors
    try:
        payload = _extract_json_fence(path)
    except ValueError as exc:
        return {}, [str(exc)]
    return payload, []


def _validate_lead_payload(payload: dict[str, Any], pod: str) -> tuple[LeadEvidence | None, list[str]]:
    errors: list[str] = []
    required_keys: dict[str, type | tuple[type, ...]] = {
        "pod_id": str,
        "workstreams": list,
        "integration_tests_all_workstreams_passed": bool,
        "test_inventory": dict,
        "command_evidence": list,
        "failure_triage": list,
        "coverage_evidence": dict,
        "sweep_500": dict,
        "edge_case_audit": dict,
    }

    for key, expected_type in required_keys.items():
        if key not in payload:
            errors.append(f"Lead pod {pod}: missing key '{key}'")
            continue
        if not isinstance(payload[key], expected_type):
            errors.append(
                f"Lead pod {pod}: '{key}' must be {expected_type}, got {type(payload[key]).__name__}"
            )

    if errors:
        return None, errors

    if payload["pod_id"] != pod:
        errors.append(f"Lead pod {pod}: 'pod_id' value '{payload['pod_id']}' does not match filename")

    coverage = payload["coverage_evidence"]
    if "critical_path" not in coverage or not isinstance(coverage["critical_path"], dict):
        errors.append(f"Lead pod {pod}: coverage_evidence.critical_path must be present")
    if (
        "risk_module_coverage_percent" not in coverage
        or not isinstance(coverage["risk_module_coverage_percent"], (int, float))
    ):
        errors.append(f"Lead pod {pod}: coverage_evidence.risk_module_coverage_percent is required")

    sweep = payload["sweep_500"]
    if "reproducible_500_count" not in sweep or not isinstance(
        sweep["reproducible_500_count"], int
    ):
        errors.append(f"Lead pod {pod}: sweep_500.reproducible_500_count is required")

    edge = payload["edge_case_audit"]
    for key in ("security", "data_integrity", "reliability"):
        if key not in edge or not isinstance(edge[key], bool):
            errors.append(f"Lead pod {pod}: edge_case_audit.{key} must be boolean")

    disputed_failures = payload.get("disputed_failures", [])
    if not isinstance(disputed_failures, list):
        errors.append(f"Lead pod {pod}: disputed_failures must be a list when provided")

    if errors:
        return None, errors

    lead = LeadEvidence(
        pod_id=payload["pod_id"],
        workstreams=payload["workstreams"],
        integration_tests_all_workstreams_passed=payload[
            "integration_tests_all_workstreams_passed"
        ],
        test_inventory=payload["test_inventory"],
        command_evidence=payload["command_evidence"],
        failure_triage=payload["failure_triage"],
        coverage_evidence=payload["coverage_evidence"],
        sweep_500=payload["sweep_500"],
        edge_case_audit=payload["edge_case_audit"],
        disputed_failures=disputed_failures,
    )
    return lead, []


def _run_command(command: str, clean_env: bool = False, timeout_s: int = 900) -> bool:
    env = os.environ.copy()
    if clean_env:
        env["PYTHONHASHSEED"] = str(random.randint(1, 999_999))
        env["AGENTCHAINS_CLEAN_ENV"] = "1"
    proc = subprocess.run(
        shlex.split(command),
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=timeout_s,
    )
    return proc.returncode == 0


def _resolve_conflict(
    conflict: dict[str, Any],
    run_commands: bool,
    same_env_runs: int,
    clean_env_runs: int,
) -> ConflictDecision:
    test_id = str(conflict.get("test_id", "unknown-test"))
    risk_tag = str(conflict.get("risk_tag", "normal")).lower()
    same_env_command = conflict.get("same_env_command")
    clean_env_command = conflict.get("clean_env_command") or same_env_command

    if not run_commands:
        return ConflictDecision(
            test_id=test_id,
            classification="blocker",
            reason="Conflict unresolved because rerun protocol was not executed",
        )

    if not same_env_command:
        return ConflictDecision(
            test_id=test_id,
            classification="blocker",
            reason="Conflict missing same_env_command for rerun protocol",
        )

    same_results = [_run_command(same_env_command, clean_env=False) for _ in range(same_env_runs)]
    clean_results = [_run_command(clean_env_command, clean_env=True) for _ in range(clean_env_runs)]

    same_failures = sum(1 for ok in same_results if not ok)
    clean_failures = sum(1 for ok in clean_results if not ok)

    if risk_tag in RISK_TAGS_BLOCKING and (same_failures > 0 or clean_failures > 0):
        return ConflictDecision(
            test_id=test_id,
            classification="blocker",
            reason=f"High-stakes risk tag '{risk_tag}' with failing reruns",
            same_env_failures=same_failures,
            clean_env_failures=clean_failures,
        )

    if clean_failures > 0:
        return ConflictDecision(
            test_id=test_id,
            classification="blocker",
            reason="Failure reproducible in clean environment",
            same_env_failures=same_failures,
            clean_env_failures=clean_failures,
        )

    if 0 < same_failures < same_env_runs and clean_failures == 0:
        return ConflictDecision(
            test_id=test_id,
            classification="flake",
            reason="Non-deterministic same-env failures; clean-env reruns all passed",
            same_env_failures=same_failures,
            clean_env_failures=clean_failures,
        )

    if same_failures == 0 and clean_failures == 0:
        return ConflictDecision(
            test_id=test_id,
            classification="resolved",
            reason="All reruns passed",
            same_env_failures=same_failures,
            clean_env_failures=clean_failures,
        )

    return ConflictDecision(
        test_id=test_id,
        classification="blocker",
        reason="Unable to classify failure deterministically; treated as blocker",
        same_env_failures=same_failures,
        clean_env_failures=clean_failures,
    )


def _evaluate_golden_paths(payload: dict[str, Any]) -> tuple[dict[str, bool], list[str]]:
    issues: list[str] = []
    summary = {"login_auth": False, "checkout": False, "data_persistence": False}
    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        return summary, ["Golden Path matrix: 'steps' must be a list"]

    for step in steps:
        if not isinstance(step, dict):
            issues.append("Golden Path matrix: each step must be an object")
            continue
        path = step.get("path")
        covered = bool(step.get("covered"))
        passed = bool(step.get("passed"))
        if path in summary and covered and passed:
            summary[path] = True
        if path in summary and not covered:
            issues.append(f"Golden Path '{path}' has uncovered step '{step.get('step', 'unknown')}'")
        if path in summary and covered and not passed:
            issues.append(f"Golden Path '{path}' has failing step '{step.get('step', 'unknown')}'")

    for path, ok in summary.items():
        if not ok:
            issues.append(f"Golden Path '{path}' is not fully covered and passing")

    return summary, issues


def evaluate_merge_gate(
    report_dir: Path,
    *,
    run_conflicts: bool = False,
    risk_coverage_target: float = 90.0,
    same_env_runs: int = 5,
    clean_env_runs: int = 5,
) -> JudgeResult:
    issues: list[str] = []
    warnings: list[str] = []
    reports_checked: list[str] = []

    leads: list[LeadEvidence] = []
    for pod in LEAD_PODS:
        lead_path = report_dir / f"lead_pod_{pod}.md"
        reports_checked.append(str(lead_path))
        if not lead_path.exists():
            issues.append(f"Missing required lead report: {lead_path}")
            continue
        payload, load_errors = _load_report(lead_path, LEAD_REQUIRED_HEADINGS)
        if load_errors:
            issues.extend(load_errors)
            continue
        lead, validation_errors = _validate_lead_payload(payload, pod)
        if validation_errors:
            issues.extend(validation_errors)
            continue
        leads.append(lead)

    golden_path_file = report_dir / "golden_path_coverage_matrix.md"
    ledger_file = report_dir / "error_500_ledger.md"
    redundancy_file = report_dir / "redundancy_audit_report.md"

    reproducible_500_count = -1
    redundancy_within_budget = False
    golden_path_summary = {"login_auth": False, "checkout": False, "data_persistence": False}
    edge_case_summary = {"security": False, "data_integrity": False, "reliability": False}

    reports_checked.extend(
        [str(golden_path_file), str(ledger_file), str(redundancy_file)]
    )

    if golden_path_file.exists():
        payload, load_errors = _load_report(golden_path_file, GOLDEN_REQUIRED_HEADINGS)
        if load_errors:
            issues.extend(load_errors)
        else:
            golden_path_summary, golden_issues = _evaluate_golden_paths(payload)
            issues.extend(golden_issues)
    else:
        issues.append(f"Missing required report: {golden_path_file}")

    if ledger_file.exists():
        payload, load_errors = _load_report(ledger_file, LEDGER_REQUIRED_HEADINGS)
        if load_errors:
            issues.extend(load_errors)
        else:
            reproducible_500_count = int(payload.get("reproducible_500_count", -1))
            if reproducible_500_count != 0:
                issues.append(
                    f"500 Error Ledger has reproducible_500_count={reproducible_500_count}; must be 0"
                )
    else:
        issues.append(f"Missing required report: {ledger_file}")

    if redundancy_file.exists():
        payload, load_errors = _load_report(redundancy_file, REDUNDANCY_REQUIRED_HEADINGS)
        if load_errors:
            issues.extend(load_errors)
        else:
            ci_budget = payload.get("ci_budget", {})
            redundancy_within_budget = bool(ci_budget.get("within_budget", False))
            if not redundancy_within_budget:
                issues.append("Redundancy audit indicates CI budget is not within agreed guardrails")
    else:
        issues.append(f"Missing required report: {redundancy_file}")

    if len(leads) != len(LEAD_PODS):
        issues.append(
            f"Lead evidence incomplete: expected {len(LEAD_PODS)} complete reports, found {len(leads)}"
        )

    all_disputes: list[dict[str, Any]] = []
    for lead in leads:
        if not lead.integration_tests_all_workstreams_passed:
            issues.append(
                f"Lead pod {lead.pod_id}: integration tests across mapped workstreams are not passing"
            )

        critical = lead.coverage_evidence.get("critical_path", {})
        for key in ("login_auth", "checkout", "data_persistence"):
            if not bool(critical.get(key, False)):
                issues.append(f"Lead pod {lead.pod_id}: critical path '{key}' is not passing")

        risk_coverage = float(lead.coverage_evidence.get("risk_module_coverage_percent", 0.0))
        if risk_coverage < risk_coverage_target:
            issues.append(
                "Lead pod "
                f"{lead.pod_id}: risk coverage {risk_coverage:.1f}% is below target "
                f"{risk_coverage_target:.1f}%"
            )

        if int(lead.sweep_500.get("reproducible_500_count", 0)) > 0:
            issues.append(
                f"Lead pod {lead.pod_id}: endpoint 500 sweep contains reproducible failures"
            )

        for triage in lead.failure_triage:
            classification = str(triage.get("classification", "unknown")).lower()
            status = str(triage.get("status", "open")).lower()
            test_id = str(triage.get("test_id", "unknown-test"))
            if classification in SEVERE_CLASSIFICATIONS and status != "resolved":
                issues.append(
                    f"Lead pod {lead.pod_id}: unresolved {classification} triage item '{test_id}'"
                )

        edge = lead.edge_case_audit
        for key in edge_case_summary:
            edge_case_summary[key] = edge_case_summary[key] or bool(edge.get(key, False))

        all_disputes.extend(lead.disputed_failures)

    for key, is_covered in edge_case_summary.items():
        if not is_covered:
            issues.append(f"Edge-case audit missing required passing evidence for '{key}'")

    seen_disputes: set[str] = set()
    conflict_decisions: list[ConflictDecision] = []
    for dispute in all_disputes:
        test_id = str(dispute.get("test_id", "unknown-test"))
        if test_id in seen_disputes:
            continue
        seen_disputes.add(test_id)
        decision = _resolve_conflict(dispute, run_conflicts, same_env_runs, clean_env_runs)
        conflict_decisions.append(decision)
        if decision.classification in {"blocker", "unknown"}:
            issues.append(f"Conflict '{decision.test_id}' classified as {decision.classification}")
        elif decision.classification == "flake":
            risk_tag = str(dispute.get("risk_tag", "normal")).lower()
            if risk_tag in RISK_TAGS_BLOCKING:
                issues.append(
                    f"Conflict '{decision.test_id}' flake classification invalid for risk tag '{risk_tag}'"
                )
            warnings.append(f"Conflict '{decision.test_id}' classified as flake")

    if not conflict_decisions:
        warnings.append("No disputed failures submitted for conflict protocol")

    deduped_issues = list(dict.fromkeys(issues))
    deduped_warnings = list(dict.fromkeys(warnings))
    decision = "GO" if not deduped_issues else "NO-GO"

    return JudgeResult(
        decision=decision,
        issues=deduped_issues,
        warnings=deduped_warnings,
        reports_checked=reports_checked,
        conflict_decisions=conflict_decisions,
        golden_path_summary=golden_path_summary,
        reproducible_500_count=reproducible_500_count,
        redundancy_within_budget=redundancy_within_budget,
        edge_case_summary=edge_case_summary,
    )


def render_final_verdict(result: JudgeResult) -> str:
    lines: list[str] = []
    lines.append("# Judge 51 Final Verdict")
    lines.append("")
    lines.append(f"## Decision: `{result.decision}`")
    lines.append("")
    lines.append("## Summary of Evidence Reviewed")
    lines.append(
        f"- Reviewed reports: {', '.join(f'`{path}`' for path in result.reports_checked)}"
    )
    lines.append(f"- Issues found: {len(result.issues)}")
    lines.append(f"- Warnings noted: {len(result.warnings)}")
    lines.append("")
    lines.append("## Conflict Decisions")
    if result.conflict_decisions:
        lines.append("| test_id | classification | same_env_failures | clean_env_failures | reason |")
        lines.append("|---|---|---:|---:|---|")
        for decision in result.conflict_decisions:
            lines.append(
                "| "
                f"{decision.test_id} | {decision.classification} | {decision.same_env_failures} | "
                f"{decision.clean_env_failures} | {decision.reason} |"
            )
    else:
        lines.append("- No disputed failures were provided by lead pods.")
    lines.append("")
    lines.append("## Golden Path Matrix")
    lines.append("| Path | Passing |")
    lines.append("|---|---|")
    for path, passing in result.golden_path_summary.items():
        lines.append(f"| {path} | {'yes' if passing else 'no'} |")
    lines.append("")
    lines.append("## 500 Ledger Result")
    lines.append(f"- Reproducible HTTP 500 count: `{result.reproducible_500_count}`")
    lines.append("")
    lines.append("## Redundancy Findings")
    lines.append(
        f"- CI budget within guardrails: `{'yes' if result.redundancy_within_budget else 'no'}`"
    )
    lines.append("")
    lines.append("## Edge-Case Audit Result")
    lines.append("| Area | Passing Evidence |")
    lines.append("|---|---|")
    for area, passing in result.edge_case_summary.items():
        lines.append(f"| {area} | {'yes' if passing else 'no'} |")
    lines.append("")
    if result.decision == "NO-GO":
        lines.append("## Mandatory Rework")
        for issue in result.issues:
            lines.append(f"- {issue}")
    else:
        lines.append("## Mandatory Rework")
        lines.append("- None.")
    lines.append("")
    if result.warnings:
        lines.append("## Notes")
        for warning in result.warnings:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_final_verdict(result: JudgeResult, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_final_verdict(result), encoding="utf-8")
    return output_path

