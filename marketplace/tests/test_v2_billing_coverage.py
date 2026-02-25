"""Tests for uncovered lines in marketplace/api/v2_billing.py."""

import pytest


@pytest.mark.asyncio
async def test_billing_account_me_no_account(client, make_agent, auth_header):
    _, token = await make_agent(name='bill-no-acc')
    resp = await client.get('/api/v2/billing/accounts/me', headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data['balance_usd'] == 0.0


@pytest.mark.asyncio
async def test_billing_account_me_with_balance(client, make_agent, auth_header, db):
    a, token = await make_agent(name='bill-bal')
    from marketplace.services.token_service import create_account, ensure_platform_account
    from marketplace.services.deposit_service import create_deposit, confirm_deposit
    await ensure_platform_account(db)
    await create_account(db, a.id)
    dep = await create_deposit(db, a.id, 100.0, 'admin_credit')
    await confirm_deposit(db, dep['id'], a.id)
    resp = await client.get('/api/v2/billing/accounts/me', headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()['balance_usd'] > 0


@pytest.mark.asyncio
async def test_billing_ledger_empty(client, make_agent, auth_header, db):
    a, token = await make_agent(name='bill-led')
    from marketplace.services.token_service import create_account, ensure_platform_account
    await ensure_platform_account(db)
    await create_account(db, a.id)
    resp = await client.get('/api/v2/billing/ledger/me', headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()['entries'] == []


@pytest.mark.asyncio
async def test_billing_create_deposit(client, make_agent, auth_header, db):
    a, token = await make_agent(name='bill-dep')
    from marketplace.services.token_service import create_account, ensure_platform_account
    await ensure_platform_account(db)
    await create_account(db, a.id)
    resp = await client.post('/api/v2/billing/deposits',
                             json={'amount_usd': 50.0, 'payment_method': 'admin_credit'},
                             headers=auth_header(token))
    assert resp.status_code == 200
    assert 'id' in resp.json()


@pytest.mark.asyncio
async def test_billing_confirm_deposit(client, make_agent, auth_header, db):
    a, token = await make_agent(name='bill-conf')
    from marketplace.services.token_service import create_account, ensure_platform_account
    from marketplace.services.deposit_service import create_deposit
    await ensure_platform_account(db)
    await create_account(db, a.id)
    dep = await create_deposit(db, a.id, 25.0, 'admin_credit')
    resp = await client.post(f'/api/v2/billing/deposits/{dep["id"]}/confirm',
                             headers=auth_header(token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_billing_transfer_to_self(client, make_agent, auth_header):
    a, token = await make_agent(name='bill-self')
    resp = await client.post('/api/v2/billing/transfers',
                             json={'to_agent_id': a.id, 'amount_usd': 10.0},
                             headers=auth_header(token))
    assert resp.status_code == 400
    assert 'yourself' in resp.json()['detail'].lower()


@pytest.mark.asyncio
async def test_billing_requires_auth(client):
    resp = await client.get('/api/v2/billing/accounts/me')
    assert resp.status_code == 401
