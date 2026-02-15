# Golden Path Coverage Matrix

Golden paths must be 100% covered and passing for merge approval.

| Path | Step | Test IDs | Covered | Passed |
|---|---|---|---|---|
| login_auth | creator register/login/token use | `test_creator_integration.py::test_creator_register`, `test_creator_integration.py::test_creator_login` | yes | yes |
| login_auth | agent auth boundary and token-type rejection | `test_auth_permission_matrix.py::test_agent_endpoint_with_creator_token`, `test_auth_permission_matrix.py::test_creator_endpoint_with_agent_token` | yes | yes |
| checkout | discover/listing selection | `test_discovery_routes_deep.py::test_discover_search_by_title_keyword`, `scripts/test_adk_agents.py` | yes | yes |
| checkout | transaction init/confirm/deliver/verify | `test_transactions_routes.py::{initiate,confirm,deliver,verify}`, `scripts/test_e2e.py` | yes | yes |
| checkout | express checkout flow | `test_express_integration.py::{test_express_buy_token_success,test_express_buy_content_delivered}`, `scripts/test_azure.py` | yes | yes |
| data_persistence | listing persistence | `test_database_lifecycle.py::test_create_all_idempotent`, `test_data_serialization.py::test_listing_price_round_trips_through_db` | yes | yes |
| data_persistence | transaction + ledger persistence | `test_transaction_service.py::test_transaction_flow_end_to_end`, `test_concurrency_safety.py::test_ledger_entries_count_matches_operations` | yes | yes |
| data_persistence | restart/reload schema compatibility | `test_config_environment_matrix.py::TestMissingVarsAndDefaults::test_missing_db_url_falls_back_to_sqlite`, `test_database_lifecycle.py::test_drop_then_create_recreates` | yes | yes |

## Machine-Readable Evidence

```json
{
  "steps": [
    {
      "path": "login_auth",
      "step": "creator register/login/token use",
      "test_ids": [
        "marketplace/tests/test_creator_integration.py::test_creator_register",
        "marketplace/tests/test_creator_integration.py::test_creator_login"
      ],
      "covered": true,
      "passed": true
    },
    {
      "path": "login_auth",
      "step": "agent auth boundary and token-type rejection",
      "test_ids": [
        "marketplace/tests/test_auth_permission_matrix.py::test_agent_endpoint_with_creator_token",
        "marketplace/tests/test_auth_permission_matrix.py::test_creator_endpoint_with_agent_token"
      ],
      "covered": true,
      "passed": true
    },
    {
      "path": "checkout",
      "step": "discover/listing selection",
      "test_ids": [
        "marketplace/tests/test_discovery_routes_deep.py::test_discover_search_by_title_keyword",
        "scripts/test_adk_agents.py"
      ],
      "covered": true,
      "passed": true
    },
    {
      "path": "checkout",
      "step": "transaction init/confirm/deliver/verify",
      "test_ids": [
        "marketplace/tests/test_transactions_routes.py::test_initiate_transaction_success",
        "marketplace/tests/test_transactions_routes.py::test_confirm_payment_simulated",
        "marketplace/tests/test_transactions_routes.py::test_deliver_content_success",
        "marketplace/tests/test_transactions_routes.py::test_verify_delivery_success",
        "scripts/test_e2e.py"
      ],
      "covered": true,
      "passed": true
    },
    {
      "path": "checkout",
      "step": "express checkout flow",
      "test_ids": [
        "marketplace/tests/test_express_integration.py::test_express_buy_token_success",
        "marketplace/tests/test_express_integration.py::test_express_buy_content_delivered",
        "scripts/test_azure.py"
      ],
      "covered": true,
      "passed": true
    },
    {
      "path": "data_persistence",
      "step": "listing persistence",
      "test_ids": [
        "marketplace/tests/test_database_lifecycle.py::test_create_all_idempotent",
        "marketplace/tests/test_data_serialization.py::test_listing_price_round_trips_through_db"
      ],
      "covered": true,
      "passed": true
    },
    {
      "path": "data_persistence",
      "step": "transaction + ledger persistence",
      "test_ids": [
        "marketplace/tests/test_transaction_service.py::test_transaction_flow_end_to_end",
        "marketplace/tests/test_concurrency_safety.py::test_ledger_entries_count_matches_operations"
      ],
      "covered": true,
      "passed": true
    },
    {
      "path": "data_persistence",
      "step": "restart/reload schema compatibility",
      "test_ids": [
        "marketplace/tests/test_config_environment_matrix.py::TestMissingVarsAndDefaults::test_missing_db_url_falls_back_to_sqlite",
        "marketplace/tests/test_database_lifecycle.py::test_drop_then_create_recreates"
      ],
      "covered": true,
      "passed": true
    }
  ]
}
```
