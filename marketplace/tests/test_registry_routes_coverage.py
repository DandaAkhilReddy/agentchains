"""Tests for uncovered lines in marketplace/api/registry.py."""

import uuid
import pytest


def _agent_payload(name=None, agent_type='seller'):
    return {
        'name': name or f'reg-{uuid.uuid4().hex[:8]}',
        'description': 'test agent',
        'agent_type': agent_type,
        'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7reg',
        'wallet_address': '0x' + 'ab' * 20,
        'capabilities': ['web_search'],
        'a2a_endpoint': 'https://reg.example.com/a2a',
    }


@pytest.mark.asyncio
async def test_register_agent(client):
    resp = await client.post('/api/v1/agents/register', json=_agent_payload('reg-new'))
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_list_agents(client, make_agent):
    await make_agent(name='reg-list1')
    await make_agent(name='reg-list2')
    resp = await client.get('/api/v1/agents')
    assert resp.status_code == 200
    assert resp.json()['total'] >= 2


@pytest.mark.asyncio
async def test_list_agents_filter_type(client, make_agent):
    await make_agent(name='reg-buyer', agent_type='buyer')
    await make_agent(name='reg-seller', agent_type='seller')
    resp = await client.get('/api/v1/agents', params={'agent_type': 'buyer'})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_agent(client, make_agent):
    a, _ = await make_agent(name='reg-get')
    resp = await client.get(f'/api/v1/agents/{a.id}')
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_agent(client, make_agent, auth_header):
    a, token = await make_agent(name='reg-upd')
    resp = await client.put(f'/api/v1/agents/{a.id}', json={'description': 'updated'},
                            headers=auth_header(token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_agent_wrong_owner(client, make_agent, auth_header):
    a, _ = await make_agent(name='reg-upd-a')
    _, tok_b = await make_agent(name='reg-upd-b')
    resp = await client.put(f'/api/v1/agents/{a.id}', json={'description': 'hack'},
                            headers=auth_header(tok_b))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_heartbeat(client, make_agent, auth_header):
    a, token = await make_agent(name='reg-hb')
    resp = await client.post(f'/api/v1/agents/{a.id}/heartbeat', headers=auth_header(token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_heartbeat_wrong_owner(client, make_agent, auth_header):
    a, _ = await make_agent(name='reg-hb-a')
    _, tok_b = await make_agent(name='reg-hb-b')
    resp = await client.post(f'/api/v1/agents/{a.id}/heartbeat', headers=auth_header(tok_b))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_deactivate_agent(client, make_agent, auth_header):
    a, token = await make_agent(name='reg-deact')
    resp = await client.delete(f'/api/v1/agents/{a.id}', headers=auth_header(token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_deactivate_wrong_owner(client, make_agent, auth_header):
    a, _ = await make_agent(name='reg-deact-a')
    _, tok_b = await make_agent(name='reg-deact-b')
    resp = await client.delete(f'/api/v1/agents/{a.id}', headers=auth_header(tok_b))
    assert resp.status_code == 403
