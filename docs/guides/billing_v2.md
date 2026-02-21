# Billing V2 Guide

## Overview

Billing V2 provides subscription management, usage metering, and invoicing for the AgentChains marketplace. It integrates with Stripe and Razorpay for payment processing.

## Components

### Billing Plans

Plans define pricing tiers with feature limits:

```json
{
  "name": "Professional",
  "code": "pro",
  "price_monthly": 49.99,
  "price_yearly": 499.99,
  "currency": "usd",
  "features": {
    "max_agents": 50,
    "max_api_calls": 100000,
    "max_workflows": 20,
    "support_level": "priority"
  },
  "stripe_price_id": "price_xxx",
  "razorpay_plan_id": "plan_xxx"
}
```

### Subscriptions

Subscriptions link a user to a billing plan:

| Field | Description |
|-------|-------------|
| `user_id` | The subscriber |
| `plan_id` | The billing plan |
| `status` | `active`, `past_due`, `canceled`, `trialing` |
| `current_period_start` | Billing period start |
| `current_period_end` | Billing period end |
| `cancel_at_period_end` | Whether to cancel at renewal |
| `stripe_subscription_id` | External Stripe ID |
| `razorpay_subscription_id` | External Razorpay ID |

### Usage Meters

Track metered usage for pay-as-you-go billing:

```python
# Record API call usage
await billing_service.record_usage(
    subscription_id="sub_123",
    meter_name="api_calls",
    quantity=1
)

# Record token usage
await billing_service.record_usage(
    subscription_id="sub_123",
    meter_name="tokens",
    quantity=1500
)
```

### Invoices

Invoices are generated at the end of each billing period:

| Field | Description |
|-------|-------------|
| `subscription_id` | The subscription |
| `amount` | Total amount |
| `currency` | Payment currency |
| `status` | `draft`, `open`, `paid`, `void`, `uncollectible` |
| `line_items` | Itemized charges (JSON) |
| `pdf_url` | Invoice PDF in Azure Blob Storage |
| `due_date` | Payment due date |

## API Endpoints

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
| GET | `/subscriptions/{id}` | Get subscription |
| POST | `/subscriptions/{id}/cancel` | Cancel subscription |
| POST | `/subscriptions/{id}/resume` | Resume canceled subscription |
| PUT | `/subscriptions/{id}/plan` | Change plan (upgrade/downgrade) |

### Usage

| Method | Path | Description |
|--------|------|-------------|
| GET | `/subscriptions/{id}/usage` | Get current usage |
| GET | `/subscriptions/{id}/usage/history` | Usage history |

### Invoices

| Method | Path | Description |
|--------|------|-------------|
| GET | `/invoices` | List invoices |
| GET | `/invoices/{id}` | Get invoice |
| GET | `/invoices/{id}/pdf` | Download invoice PDF |

## Stripe Integration

Subscriptions sync bidirectionally with Stripe:

1. **Create**: Calls `stripe.Subscription.create()` with the Stripe price ID
2. **Webhooks**: Stripe sends `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated` events
3. **Reconciliation**: The payment reconciliation service verifies consistency

## Razorpay Integration

For Indian payments, Razorpay subscriptions are supported:

1. **Create**: Calls `razorpay_client.subscription.create()` with the plan ID
2. **Webhooks**: Razorpay sends `subscription.charged`, `subscription.halted` events
3. **Signature Verification**: HMAC-SHA256 verification on all webhooks

## Usage Metering Flow

```
API Request → Rate Limiter → Handler → Usage Recorder
                                            ↓
                                    UsageMeter (Redis)
                                            ↓
                                    Periodic Flush to DB
                                            ↓
                                    Invoice Generation
```

Usage is tracked in Redis for performance and periodically flushed to the database. At billing period end, usage meters are aggregated into invoice line items.

## Tier Enforcement

The billing service checks subscription limits before allowing operations:

```python
can_proceed = await billing_service.check_limit(
    subscription_id="sub_123",
    resource="api_calls"
)
if not can_proceed:
    raise HTTPException(429, "Usage limit exceeded for current plan")
```
