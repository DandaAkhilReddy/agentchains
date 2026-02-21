# Billing V2 Guide

Plan management, usage metering, invoice generation, and payment integration for the AgentChains marketplace.

---

## 1. Overview

Billing V2 provides a complete subscription billing system for the AgentChains platform. It supports tiered plans with usage limits, automatic metering, invoice generation, and dual payment gateway integration (Stripe for global markets and Razorpay for India).

### Architecture

```
Agent / Creator
      |
      v
Subscription (plan_id, status, period)
      |
      +---> Usage Meters (api_calls, storage, bandwidth, compute)
      |
      +---> Invoices (amount, status, line items)
      |
      +---> Payment Gateways
              |
              +---> Stripe (global, USD)
              +---> Razorpay (India, INR)
```

### Components

| Component | Location | Responsibility |
|-----------|----------|---------------|
| Billing V2 Service | `marketplace/services/billing_v2_service.py` | Plans, subscriptions, metering, invoices |
| Stripe Service | `marketplace/services/stripe_service.py` | Stripe payment operations |
| Razorpay Service | `marketplace/services/razorpay_service.py` | Razorpay payment operations |
| Billing Models | `marketplace/models/billing.py` | BillingPlan, Subscription, UsageMeter, Invoice |
| Reconciliation Service | `marketplace/services/payment_reconciliation_service.py` | Payment verification and consistency |

---

## 2. Plans

### 2.1 Plan Tiers

| Plan | Tier | Monthly Price | Yearly Price | API Calls/mo | Storage | Agents |
|------|------|--------------|-------------|-------------|---------|--------|
| Free | `free` | $0 | $0 | 1,000 | 1 GB | 1 |
| Pro | `pro` | $29 | $290 | 50,000 | 25 GB | 10 |
| Enterprise | `enterprise` | $99 | $990 | 500,000 | 100 GB | Unlimited |

### 2.2 Plan Data Model

The `BillingPlan` table (`billing_plans`):

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `name` | string(100) | Unique plan name (e.g., "Pro") |
| `description` | text | Plan description |
| `tier` | string(20) | `free`, `starter`, `pro`, `enterprise` |
| `price_usd_monthly` | decimal(10,2) | Monthly price in USD |
| `price_usd_yearly` | decimal(10,2) | Annual price in USD (discounted) |
| `api_calls_limit` | integer | Monthly API call limit |
| `storage_gb_limit` | integer | Storage limit in GB |
| `agents_limit` | integer | Maximum agents (0 = unlimited) |
| `features_json` | text | JSON array of feature flags |
| `status` | string(20) | `active` or `archived` |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

Indexed on: `status`.

### 2.3 Create a Plan

```python
from marketplace.services.billing_v2_service import create_plan

plan = await create_plan(
    db=db,
    name="Pro",
    price_monthly=29.00,
    price_yearly=290.00,
    api_calls_limit=50000,
    storage_limit_gb=25,
    tier="pro",
    features=["priority_support", "advanced_analytics", "custom_webhooks"],
    description="For professional teams building AI agent pipelines",
)
```

### 2.4 List Plans

```python
from marketplace.services.billing_v2_service import list_plans, get_plans

# All active plans
plans = await list_plans(db)

# Filter by tier
pro_plans = await get_plans(db, tier="pro")
```

---

## 3. Subscriptions

### 3.1 Subscription Data Model

The `Subscription` table (`subscriptions`):

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `agent_id` | string(36) | Subscribing agent ID |
| `plan_id` | UUID (FK) | Reference to billing plan |
| `status` | string(20) | `active`, `cancelled`, `past_due`, `trialing` |
| `current_period_start` | datetime | Current billing period start |
| `current_period_end` | datetime | Current billing period end (30 days from start) |
| `cancel_at_period_end` | boolean | Cancel when current period ends |
| `stripe_subscription_id` | string(200) | Stripe subscription ID (if applicable) |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

Indexed on: `agent_id`, `plan_id`, `status`.

### 3.2 Subscribe an Agent

```python
from marketplace.services.billing_v2_service import subscribe

subscription = await subscribe(
    db=db,
    agent_id="agent-123",
    plan_id=plan.id,
)
# subscription.status = "active"
# subscription.current_period_end = now + 30 days
```

### 3.3 Cancel a Subscription

```python
from marketplace.services.billing_v2_service import cancel_subscription

# Cancel at end of current period (graceful)
sub = await cancel_subscription(db, subscription_id=sub.id, immediate=False)
# sub.cancel_at_period_end = True, status remains "active"

# Cancel immediately
sub = await cancel_subscription(db, subscription_id=sub.id, immediate=True)
# sub.status = "cancelled"
# sub.current_period_end = now
```

### 3.4 Get Active Subscription

```python
from marketplace.services.billing_v2_service import get_subscription

sub = await get_subscription(db, agent_id="agent-123")
if sub:
    print(f"Plan: {sub.plan.name}, Expires: {sub.current_period_end}")
else:
    print("No active subscription")
```

---

## 4. Usage Metering

### 4.1 Meter Types

| Meter | Unit | Tracked Against |
|-------|------|----------------|
| `api_calls` | count | `plan.api_calls_limit` |
| `storage` | GB | `plan.storage_gb_limit` |
| `compute` | count | `plan.api_calls_limit` (shared) |
| `bandwidth` | GB | `plan.storage_gb_limit` (shared) |

### 4.2 Usage Meter Data Model

The `UsageMeter` table (`usage_meters`):

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `agent_id` | string(36) | Agent being metered |
| `metric_name` | string(50) | Meter type (api_calls, storage, etc.) |
| `value` | decimal(14,4) | Usage value for this record |
| `period_start` | datetime | Billing period start (1st of month, 00:00 UTC) |
| `period_end` | datetime | Billing period end (1st of next month, 00:00 UTC) |
| `created_at` | datetime | When this usage record was created |

Indexed on: `(agent_id, metric_name, period_start)`.

### 4.3 Record Usage

```python
from marketplace.services.billing_v2_service import record_usage

# Record 1 API call
meter = await record_usage(db, agent_id="agent-123", meter_type="api_calls", value=1.0)

# Record 0.5 GB of storage usage
meter = await record_usage(db, agent_id="agent-123", meter_type="storage", value=0.5)
```

Usage is automatically bucketed into monthly periods based on the current UTC date.

### 4.4 Check Usage Limits

```python
from marketplace.services.billing_v2_service import check_limits, check_usage_limit

# Detailed limit check
result = await check_limits(db, agent_id="agent-123", meter_type="api_calls")
# {"allowed": True, "current": 4500.0, "limit": 50000}

# Simple boolean check (True = within limit, False = exceeded or no plan)
within_limit = await check_usage_limit(db, agent_id="agent-123", metric_name="api_calls")
```

The limit check:
1. Finds the agent's active subscription.
2. Loads the associated billing plan.
3. Maps the meter type to the appropriate plan limit.
4. Sums all usage records for the current period.
5. Returns whether the current usage is below the limit.

### 4.5 Query Usage History

```python
from marketplace.services.billing_v2_service import get_usage
from datetime import datetime, timezone

# All usage for an agent
records = await get_usage(db, agent_id="agent-123")

# Filter by meter type
api_usage = await get_usage(db, agent_id="agent-123", meter_type="api_calls")

# Filter by period
period_start = datetime(2026, 2, 1, tzinfo=timezone.utc)
feb_usage = await get_usage(db, agent_id="agent-123", period_start=period_start)
```

---

## 5. Invoice Generation

### 5.1 Invoice Data Model

The `Invoice` table (`invoices`):

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `agent_id` | string(36) | Billed agent |
| `subscription_id` | UUID (FK) | Related subscription (optional) |
| `amount_usd` | decimal(12,4) | Subtotal amount |
| `tax_usd` | decimal(12,4) | Tax amount |
| `total_usd` | decimal(12,4) | Total amount (amount + tax) |
| `status` | string(20) | `draft`, `open`, `paid`, `void`, `uncollectible` |
| `stripe_invoice_id` | string(200) | Stripe invoice ID |
| `pdf_url` | string(500) | Generated PDF URL |
| `line_items_json` | text | JSON array of line items |
| `issued_at` | datetime | When the invoice was issued |
| `due_at` | datetime | Payment due date (30 days after issued) |
| `paid_at` | datetime | When payment was received |

Indexed on: `agent_id`, `subscription_id`, `status`.

### 5.2 Generate an Invoice

```python
from marketplace.services.billing_v2_service import generate_invoice

invoice = await generate_invoice(
    db=db,
    agent_id="agent-123",
    amount_usd=29.00,
    description="Pro Plan - February 2026",
    subscription_id=subscription.id,
)
# invoice.status = "open"
# invoice.due_at = now + 30 days
```

### 5.3 List Invoices

```python
from marketplace.services.billing_v2_service import list_invoices, get_invoices

# All invoices for an agent (most recent first)
invoices = await list_invoices(db, agent_id="agent-123")

# Filter by status
open_invoices = await get_invoices(db, agent_id="agent-123", status="open")
paid_invoices = await get_invoices(db, agent_id="agent-123", status="paid")
```

---

## 6. Stripe Integration

### 6.1 Configuration

| Environment Variable | Description |
|---------------------|-------------|
| `STRIPE_SECRET_KEY` | Stripe secret key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (`whsec_...`) |

If `STRIPE_SECRET_KEY` is not set, the service operates in **simulated mode**.

### 6.2 Service Initialization

```python
from marketplace.services.stripe_service import StripePaymentService

stripe = StripePaymentService(
    secret_key="sk_test_...",
    webhook_secret="whsec_...",
)
# Detects test vs live mode from key prefix
```

### 6.3 Payment Intents

```python
from decimal import Decimal

# Create a payment intent
intent = await stripe.create_payment_intent(
    amount_usd=Decimal("29.00"),
    currency="usd",
    metadata={"agent_id": "agent-123", "plan": "pro"},
)
# intent["id"] = "pi_..." (real) or "pi_sim_..." (simulated)
# intent["status"] = "requires_confirmation"

# Confirm payment
result = await stripe.confirm_payment(intent["id"])
# result["status"] = "succeeded"

# Retrieve payment intent
details = await stripe.retrieve_payment_intent(intent["id"])
```

### 6.4 Refunds

```python
# Full refund
refund = await stripe.create_refund(payment_intent_id=intent["id"])

# Partial refund
refund = await stripe.create_refund(
    payment_intent_id=intent["id"],
    amount_usd=Decimal("10.00"),
)
```

### 6.5 Connected Accounts (Creator Payouts)

```python
# Create a Stripe Connect Express account for a creator
account = await stripe.create_connected_account(
    email="creator@example.com",
    country="US",
)
# account["id"] = "acct_..." or "acct_sim_..."

# Create a payout (transfer) to the connected account
payout = await stripe.create_payout(
    account_id=account["id"],
    amount_usd=Decimal("100.00"),
    currency="usd",
)
```

### 6.6 Webhook Verification

```python
event = stripe.verify_webhook_signature(
    payload=request.body,
    sig_header=request.headers["Stripe-Signature"],
)
if event:
    match event["type"]:
        case "payment_intent.succeeded":
            # Mark invoice as paid
            pass
        case "invoice.paid":
            # Update subscription status
            pass
        case "customer.subscription.deleted":
            # Cancel subscription
            pass
```

---

## 7. Razorpay Integration

### 7.1 Configuration

| Environment Variable | Description |
|---------------------|-------------|
| `RAZORPAY_KEY_ID` | Razorpay key ID (`rzp_test_...` or `rzp_live_...`) |
| `RAZORPAY_KEY_SECRET` | Razorpay key secret |

If `RAZORPAY_KEY_ID` is not set, the service operates in simulated mode.

### 7.2 Service Initialization

```python
from marketplace.services.razorpay_service import RazorpayPaymentService

razorpay = RazorpayPaymentService(
    key_id="rzp_test_...",
    key_secret="...",
)
```

### 7.3 Orders

```python
from decimal import Decimal

order = await razorpay.create_order(
    amount_inr=Decimal("2400.00"),
    currency="INR",
    receipt="rcpt_agent123_feb2026",
)
# order["id"] = "order_..." or "order_sim_..."
# order["status"] = "created"
```

### 7.4 Payment Verification

Razorpay payments are verified using HMAC-SHA256 signature validation:

```python
result = await razorpay.verify_payment(
    order_id="order_...",
    payment_id="pay_...",
    signature="received_signature",
)
# result["verified"] = True/False
```

### 7.5 Fetch Payment Details

```python
payment = await razorpay.fetch_payment(payment_id="pay_...")
# payment["status"] = "captured"
# payment["method"] = "upi" | "card" | "netbanking"
```

### 7.6 Bank Transfer Payouts (RazorpayX)

```python
payout = await razorpay.create_payout(
    account_number="1234567890",
    ifsc="SBIN0001234",
    amount_inr=Decimal("5000.00"),
    mode="NEFT",       # NEFT, RTGS, IMPS
    purpose="payout",
)
```

### 7.7 UPI Payouts

```python
payout = await razorpay.create_upi_payout(
    vpa="creator@upi",
    amount_inr=Decimal("2500.00"),
)
```

---

## 8. Webhook Handling

### 8.1 Stripe Webhooks

Configure your webhook endpoint URL in the Stripe Dashboard:

```
https://api.agentchains.com/api/v4/billing/webhooks/stripe
```

| Event | Action |
|-------|--------|
| `payment_intent.succeeded` | Mark invoice as `paid`, update `paid_at` |
| `payment_intent.payment_failed` | Mark invoice as `past_due` |
| `invoice.paid` | Update subscription status to `active` |
| `invoice.payment_failed` | Flag subscription as `past_due` |
| `customer.subscription.deleted` | Cancel subscription |
| `charge.refunded` | Record refund in ledger |

### 8.2 Razorpay Webhooks

Configure your webhook URL in the Razorpay Dashboard:

```
https://api.agentchains.com/api/v4/billing/webhooks/razorpay
```

| Event | Action |
|-------|--------|
| `payment.captured` | Mark invoice as `paid` |
| `payment.failed` | Mark invoice as `past_due` |
| `order.paid` | Update subscription status |
| `payout.processed` | Confirm creator payout |
| `subscription.charged` | Record subscription payment |
| `subscription.halted` | Flag subscription as `past_due` |

---

## 9. Usage Enforcement Flow

```
Agent makes API call
  |
  v
Middleware: Check active subscription
  |-- No subscription --> HTTP 402 Payment Required
  |
  v
Middleware: Check usage limit (check_usage_limit)
  |-- Exceeded --> HTTP 429 Limit Exceeded
  |
  v
Process request normally
  |
  v
Record usage (record_usage)
  |
  v
Return response
```

---

## 10. API Endpoints

All endpoints under `/api/v3/billing/`.

### Plans

| Method | Path | Description |
|--------|------|-------------|
| GET | `/plans` | List available plans |
| GET | `/plans/{id}` | Get plan details |

### Subscriptions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/subscriptions` | Create subscription |
| GET | `/subscriptions/{id}` | Get subscription details |
| POST | `/subscriptions/{id}/cancel` | Cancel subscription |
| POST | `/subscriptions/{id}/resume` | Resume cancelled subscription |
| PUT | `/subscriptions/{id}/plan` | Change plan (upgrade/downgrade) |

### Usage

| Method | Path | Description |
|--------|------|-------------|
| GET | `/subscriptions/{id}/usage` | Get current period usage |
| GET | `/subscriptions/{id}/usage/history` | Usage history by period |

### Invoices

| Method | Path | Description |
|--------|------|-------------|
| GET | `/invoices` | List invoices |
| GET | `/invoices/{id}` | Get invoice details |
| GET | `/invoices/{id}/pdf` | Download invoice PDF |

---

## 11. Simulated Mode

When no payment gateway credentials are configured, both Stripe and Razorpay services operate in **simulated mode**:

- All operations succeed immediately.
- IDs are prefixed with `sim_` (e.g., `pi_sim_abc123`, `order_sim_def456`).
- Responses include `"simulated": true`.
- No real charges are made.
- Webhook signature verification is skipped.

This enables full end-to-end development and testing without payment gateway accounts.

To switch to live mode, set the appropriate environment variables and install the SDK packages:

```bash
pip install stripe>=8.0          # For Stripe
pip install razorpay>=1.4        # For Razorpay
```
