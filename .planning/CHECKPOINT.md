# AgentChains — Project Checkpoint
*Last updated: 2026-03-04*

## Completed Features

### Stripe Checkout Integration (feat/stripe-checkout → merged to master)
- Real Stripe SDK calls replace stubs (sk_test_* keys use live SDK)
- `POST /wallet/deposit {payment_method: "stripe"}` → Stripe Checkout Session
- `checkout.session.completed` webhook confirms deposit
- Settlement fix: `verify_delivery` now credits seller wallet
- Frontend: redirect to Stripe hosted page, success/cancel URL handling
- 55 Stripe-specific tests + 1469 total suite passing

### Files changed
- marketplace/services/stripe_service.py
- marketplace/config.py (stripe_frontend_url)
- marketplace/services/deposit_service.py (update_deposit_payment_ref)
- marketplace/api/wallet.py (stripe payment_method)
- marketplace/api/webhooks.py (checkout.session.completed handler)
- marketplace/services/transaction_service.py (settlement fix)
- frontend/src/types/wallet.ts, lib/api.ts, pages/WalletPage.tsx
- marketplace/tests/test_stripe_checkout.py (new)
- marketplace/tests/test_stripe_service.py (updated)

## Pending — Not Yet Done

### Stripe Production Config (manual, not code)
Three env vars need to be set before Stripe works in production:
- `STRIPE_SECRET_KEY` — from Stripe Dashboard → API keys
- `STRIPE_WEBHOOK_SECRET` — from Stripe Dashboard → Webhooks → signing secret
- `STRIPE_FRONTEND_URL` — deployed frontend origin URL

Stripe Dashboard webhook endpoint:
- URL: https://<backend>/webhooks/stripe
- Events: checkout.session.completed

### Known Test Failures
- `test_cicd_pipeline_validation.py::TestDeployWorkflow::test_has_both_deploy_jobs`
  Pre-existing — checks CI YAML for deploy-infrastructure job. Not related to Stripe.

## Architecture Reference
Deposit flow: User → POST /wallet/deposit → Stripe Checkout Session → redirect
  → Stripe hosted page → payment → webhook → confirm_deposit → USD credited
