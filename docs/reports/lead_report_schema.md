# Lead Reviewer Report Schema

Each `lead_pod_*.md` file must include all required markdown sections and one JSON code block under `Machine-Readable Evidence` that follows this schema:

```json
{
  "pod_id": "A",
  "workstreams": ["agent-01", "agent-02"],
  "integration_tests_all_workstreams_passed": true,
  "test_inventory": {
    "tests_added": 0,
    "tests_updated": 0,
    "integration_suites_run": ["python -m pytest marketplace/tests -q"]
  },
  "command_evidence": [
    {
      "command": "python -m pytest marketplace/tests -q",
      "pass_count": 120,
      "fail_count": 0,
      "rerun_count": 0
    }
  ],
  "failure_triage": [
    {
      "test_id": "checkout_race_01",
      "classification": "flake",
      "status": "resolved",
      "root_cause": "timing race in fixture startup",
      "regression_test_ids": ["checkout_race_regression_01"]
    }
  ],
  "coverage_evidence": {
    "critical_path": {
      "login_auth": true,
      "checkout": true,
      "data_persistence": true
    },
    "risk_module_coverage_percent": 90.0
  },
  "sweep_500": {
    "routes_scanned": 120,
    "reproducible_500_count": 0,
    "reproducible_routes": []
  },
  "edge_case_audit": {
    "security": true,
    "data_integrity": true,
    "reliability": true
  },
  "disputed_failures": [
    {
      "test_id": "auth_boundary_dispute_01",
      "risk_tag": "security",
      "same_env_command": "python -m pytest marketplace/tests/test_auth_boundaries.py::test_agent_token_rejected -q",
      "clean_env_command": "python -m pytest marketplace/tests/test_auth_boundaries.py::test_agent_token_rejected -q"
    }
  ]
}
```

`classification` accepted values:

- `blocker`
- `flake`
- `unknown`

`status` accepted values:

- `open`
- `resolved`

