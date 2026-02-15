# Agent 51 Merge-Gate Reports

This folder contains governance artifacts for the Final Quality Judge workflow.

Required files:

- `docs/reports/lead_pod_A.md`
- `docs/reports/lead_pod_B.md`
- `docs/reports/lead_pod_C.md`
- `docs/reports/lead_pod_D.md`
- `docs/reports/lead_pod_E.md`
- `docs/reports/golden_path_coverage_matrix.md`
- `docs/reports/error_500_ledger.md`
- `docs/reports/redundancy_audit_report.md`
- `docs/reports/judge_51_final_verdict.md`

Execution command:

```bash
python scripts/judge_merge_gate.py
```

The judge script exits `0` on `GO` and exits `1` on `NO-GO`.

