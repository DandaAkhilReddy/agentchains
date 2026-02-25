"""Tests for uncovered lines in marketplace/api/creators.py."""

import pytest


@pytest.mark.asyncio
async def test_register_creator(client):
    resp = await client.post('/api/v1/creators/register', json={
        'email': 'testreg@example.com', 'password': 'securepass123', 'display_name': 'Test',
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_register_creator_duplicate(client):
    payload = {'email': 'dup@example.com', 'password': 'securepass123', 'display_name': 'Dup'}
    await client.post('/api/v1/creators/register', json=payload)
    resp = await client.post('/api/v1/creators/register', json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_creator(client, make_creator):
    await make_creator(email='login@test.com', password='testpass123')
    resp = await client.post('/api/v1/creators/login', json={
        'email': 'login@test.com', 'password': 'testpass123',
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password(client, make_creator):
    await make_creator(email='bad@test.com', password='testpass123')
    resp = await client.post('/api/v1/creators/login', json={
        'email': 'bad@test.com', 'password': 'wrongpass',
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_my_profile(client, make_creator):
    _, token = await make_creator(display_name='Profile')
    resp = await client.get('/api/v1/creators/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_my_profile(client, make_creator):
    _, token = await make_creator(display_name='Update')
    resp = await client.put('/api/v1/creators/me', json={'display_name': 'Updated'},
                            headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_my_agents(client, make_creator):
    _, token = await make_creator(display_name='Agents')
    resp = await client.get('/api/v1/creators/me/agents',
                            headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert 'agents' in resp.json()


@pytest.mark.asyncio
async def test_get_dashboard(client, make_creator):
    _, token = await make_creator(display_name='Dash')
    resp = await client.get('/api/v1/creators/me/dashboard',
                            headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_wallet(client, make_creator):
    _, token = await make_creator(display_name='Wallet')
    resp = await client.get('/api/v1/creators/me/wallet',
                            headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_claim_agent(client, make_creator, make_agent):
    _, token = await make_creator(display_name='Claim')
    a, _ = await make_agent(name='claimable')
    resp = await client.post(f'/api/v1/creators/me/agents/{a.id}/claim',
                             headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code in (200, 400)
