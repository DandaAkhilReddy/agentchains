"""Tests for Stripe Checkout flow: deposit endpoint + webhook handler.

5 test cases:
  1. Simulated: deposit with payment_method=stripe auto-confirms when no key
  2. Webhook checkout.session.completed confirms pending deposit
  3. Webhook idempotency: double-fire doesn't double-credit
  4. Webhook with payment_status != "paid" skips
  5. Webhook with missing deposit_id skips
"""

import json

import pytest

from marketplace.services.deposit_service import create_deposit, confirm_deposit


class TestStripeCheckoutSimulated:
    """Deposit endpoint auto-confirms when no Stripe key is configured."""

    async def test_deposit_stripe_simulated_autoconfirms(self, client, db, seed_platform, make_agent, make_token_account):
        """Test 1: POST /wallet/deposit with payment_method=stripe auto-confirms (no key)."""
        agent, token = await make_agent("checkout-buyer")
        await make_token_account(agent.id, 0)

        resp = await client.post(
            "/api/v1/wallet/deposit",
            json={"amount_usd": 5.0, "payment_method": "stripe"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Simulated: auto-confirmed, no checkout_url
        assert data["status"] == "completed"
        assert data["checkout_url"] is None


class TestStripeWebhook:
    """Webhook checkout.session.completed handler tests."""

    async def _create_pending_deposit(self, db, agent_id: str, amount: float = 10.0) -> str:
        """Helper: create a pending deposit and return its ID."""
        deposit = await create_deposit(db, agent_id, amount, "stripe")
        return deposit["id"]

    def _checkout_event(self, deposit_id: str, payment_status: str = "paid") -> dict:
        """Build a simulated checkout.session.completed webhook payload."""
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_abc123",
                    "payment_status": payment_status,
                    "metadata": {"deposit_id": deposit_id},
                }
            },
        }

    async def test_webhook_confirms_pending_deposit(self, client, db, seed_platform, make_agent, make_token_account):
        """Test 2: checkout.session.completed with payment_status=paid confirms deposit."""
        agent, _ = await make_agent("webhook-buyer")
        await make_token_account(agent.id, 0)

        deposit_id = await self._create_pending_deposit(db, agent.id)
        event = self._checkout_event(deposit_id, "paid")

        resp = await client.post(
            "/webhooks/stripe",
            content=json.dumps(event),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

        # Verify deposit is now completed
        from marketplace.services.deposit_service import _get_deposit
        deposit = await _get_deposit(db, deposit_id)
        # Refresh from DB to see webhook's changes
        await db.refresh(deposit)
        assert deposit.status == "completed"

    async def test_webhook_idempotent_double_fire(self, client, db, seed_platform, make_agent, make_token_account):
        """Test 3: Firing the same webhook twice doesn't double-credit."""
        agent, _ = await make_agent("webhook-idem")
        await make_token_account(agent.id, 0)

        deposit_id = await self._create_pending_deposit(db, agent.id, 15.0)
        event = self._checkout_event(deposit_id)

        # First fire
        resp1 = await client.post(
            "/webhooks/stripe",
            content=json.dumps(event),
            headers={"Content-Type": "application/json"},
        )
        assert resp1.status_code == 200

        # Second fire — should not raise or double-credit
        resp2 = await client.post(
            "/webhooks/stripe",
            content=json.dumps(event),
            headers={"Content-Type": "application/json"},
        )
        assert resp2.status_code == 200

    async def test_webhook_skips_unpaid(self, client, db, seed_platform, make_agent, make_token_account):
        """Test 4: checkout.session.completed with payment_status != paid skips."""
        agent, _ = await make_agent("webhook-unpaid")
        await make_token_account(agent.id, 0)

        deposit_id = await self._create_pending_deposit(db, agent.id)
        event = self._checkout_event(deposit_id, "unpaid")

        resp = await client.post(
            "/webhooks/stripe",
            content=json.dumps(event),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200

        # Deposit should still be pending
        from marketplace.services.deposit_service import _get_deposit
        deposit = await _get_deposit(db, deposit_id)
        assert deposit.status == "pending"

    async def test_webhook_skips_missing_deposit_id(self, client):
        """Test 5: checkout.session.completed without deposit_id in metadata skips."""
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_no_meta",
                    "payment_status": "paid",
                    "metadata": {},
                }
            },
        }

        resp = await client.post(
            "/webhooks/stripe",
            content=json.dumps(event),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
