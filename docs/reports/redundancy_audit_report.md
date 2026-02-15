# Redundancy Audit Report

Document duplicate/overlapping tests and CI budget impact.

| test_id | pods | overlap_reason | action | owner |
|---|---|---|---|---|
| `SCRIPT-E2E-COVERAGE-01` | C,D | `scripts/test_e2e.py` and `scripts/test_azure.py` both validate register/list/discover/express flows | keep both; local quick-check + deployment-target check have distinct risk signal | pod-E |
| `EXPRESS-HAPPY-PATH-01` | A,C | `test_express_integration.py` overlaps express purchase coverage already checked by script suites | keep route test in PR, retain scripts for end-to-end truthfulness | pod-E |
| `TRANSACTION-LIFECYCLE-01` | A,C | lifecycle validated in both route tests and script tests | no trim needed; one is unitized API, one is full integration | pod-E |

## Machine-Readable Evidence

```json
{
  "ci_budget": {
    "pr_max_minutes": 20,
    "current_pr_minutes": 12.4,
    "within_budget": true
  },
  "duplicates": [
    {
      "test_id": "SCRIPT-E2E-COVERAGE-01",
      "pods": ["C", "D"],
      "action": "keep",
      "justification": "deployment-target and local-target E2E scripts overlap by design but validate different operational risks"
    },
    {
      "test_id": "EXPRESS-HAPPY-PATH-01",
      "pods": ["A", "C"],
      "action": "keep",
      "justification": "route-level determinism plus script-level integration signal"
    },
    {
      "test_id": "TRANSACTION-LIFECYCLE-01",
      "pods": ["A", "C"],
      "action": "keep",
      "justification": "API lifecycle tests and end-to-end scripts provide non-identical assertions"
    }
  ]
}
```
