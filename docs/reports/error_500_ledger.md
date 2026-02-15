# 500 Error Ledger

Track all route sweeps and reproducible HTTP 500 findings for merge-gate decisions.

| route | method | reproducible | status | owner | notes |
|---|---|---|---|---|---|
| `/api/v1/health` | GET | no | closed | pod-C | smoke probe returned 200 |
| `/api/v1/docs` | GET | no | closed | pod-C | docs probe returned 200 |
| adversarial route set (`discover`, `search`, `register`, `listings`) | mixed | no | closed | pod-D | `test_adversarial_inputs.py` asserts non-500 outcomes |
| SQL injection vectors on discover/search/register | mixed | no | closed | pod-D | `test_security_hardening.py::TestSQLInjectionSafety` passed |
| e2e script route matrix (`health`, `catalog`, `discovery`, `express`, `transactions`) | mixed | no | closed | pod-C | `scripts/test_adk_agents.py` and `scripts/test_azure.py` passed |

## Machine-Readable Evidence

```json
{
  "reproducible_500_count": 0,
  "entries": [
    {
      "route": "/api/v1/health",
      "method": "GET",
      "reproducible": false,
      "status": "closed",
      "owner": "pod-C",
      "notes": "smoke check returned HTTP 200"
    },
    {
      "route": "/docs",
      "method": "GET",
      "reproducible": false,
      "status": "closed",
      "owner": "pod-C",
      "notes": "docs check returned HTTP 200"
    },
    {
      "route": "adversarial_inputs_suite",
      "method": "mixed",
      "reproducible": false,
      "status": "closed",
      "owner": "pod-D",
      "notes": "marketplace/tests/test_adversarial_inputs.py passed"
    },
    {
      "route": "security_injection_suite",
      "method": "mixed",
      "reproducible": false,
      "status": "closed",
      "owner": "pod-D",
      "notes": "marketplace/tests/test_security_hardening.py::TestSQLInjectionSafety passed"
    },
    {
      "route": "script_e2e_matrix",
      "method": "mixed",
      "reproducible": false,
      "status": "closed",
      "owner": "pod-C",
      "notes": "scripts/test_adk_agents.py and scripts/test_azure.py passed"
    }
  ]
}
```
