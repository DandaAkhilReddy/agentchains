"""Run the Agent 51 merge-gate protocol and emit final verdict report."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from marketplace.services.merge_gate_judge import evaluate_merge_gate, write_final_verdict

    parser = argparse.ArgumentParser(description="Evaluate merge readiness via Agent 51 protocol.")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("docs/reports"),
        help="Directory containing lead reports and governance artifacts.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reports/judge_51_final_verdict.md"),
        help="Output path for final verdict markdown.",
    )
    parser.add_argument(
        "--risk-coverage-target",
        type=float,
        default=90.0,
        help="Minimum risk coverage percent required per lead pod.",
    )
    parser.add_argument(
        "--run-conflicts",
        action="store_true",
        help="Execute 5+5 rerun protocol for disputed tests using provided commands.",
    )
    parser.add_argument(
        "--same-env-runs",
        type=int,
        default=5,
        help="Number of reruns in same environment for each disputed test.",
    )
    parser.add_argument(
        "--clean-env-runs",
        type=int,
        default=5,
        help="Number of reruns in clean/randomized environment for each disputed test.",
    )
    args = parser.parse_args()

    result = evaluate_merge_gate(
        args.report_dir,
        run_conflicts=args.run_conflicts,
        risk_coverage_target=args.risk_coverage_target,
        same_env_runs=args.same_env_runs,
        clean_env_runs=args.clean_env_runs,
    )
    output = write_final_verdict(result, args.output)

    print(f"Decision: {result.decision}")
    print(f"Verdict report: {output}")
    if result.issues:
        print("Blocking issues:")
        for issue in result.issues:
            print(f"- {issue}")
    return 0 if result.decision == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
