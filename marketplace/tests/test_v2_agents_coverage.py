"""Tests for uncovered lines in marketplace/api/v2_agents.py."""

import pytest
from marketplace.core.creator_auth import create_creator_token


@pytest.mark.asyncio
async def test_onboard_agent_success(client, make_creator):
    creator, token = await make_creator(display_name='v2-onboard')
    payload = {
        'name': 'onboard-agent-1',
        'description': 'Test onboard agent',
        'agent_type': 'seller',
        'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-onboard',
        'capabilities': ['web_search'],
        'a2a_endpoint': 'https://test.example.com/a2a',
    }
    resp = await client.post('/api/v2/agents/onboard', json=payload,
                             headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 201
    data = resp.json()
    assert 'agent_id' in data
    assert 'agent_jwt_token' in data
    assert 'stream_token' in data


@pytest.mark.asyncio
async def test_onboard_agent_no_auth(client):
    payload = {'name': 'no-auth', 'agent_type': 'seller', 'public_key': 'ssh-rsa AAAA_long_key_here'}
    resp = await client.post('/api/v2/agents/onboard', json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_onboard_agent_duplicate_name(client, make_creator):
    creator, token = await make_creator(display_name='v2-dup')
    payload = {
        'name': 'dup-agent',
        'agent_type': 'buyer',
        'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-dup',
    }
    headers = {'Authorization': f'Bearer {token}'}
    await client.post('/api/v2/agents/onboard', json=payload, headers=headers)
    resp = await client.post('/api/v2/agents/onboard', json=payload, headers=headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_trust_public(client, make_creator):
    creator, token = await make_creator(display_name='v2-trust-pub')
    payload = {
        'name': 'trust-pub-agent',
        'agent_type': 'both',
        'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-trust',
    }
    resp = await client.post('/api/v2/agents/onboard', json=payload,
                             headers={'Authorization': f'Bearer {token}'})
    agent_id = resp.json()['agent_id']
    resp = await client.get(f'/api/v2/agents/{agent_id}/trust/public')
    assert resp.status_code == 200
    data = resp.json()
    assert data['agent_id'] == agent_id
    assert 'agent_trust_status' in data


@pytest.mark.asyncio
async def test_get_trust_public_not_found(client):
    resp = await client.get('/api/v2/agents/nonexistent/trust/public')
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_attest_runtime(client, make_creator):
    creator, token = await make_creator(display_name='v2-attest')
    payload = {
        'name': 'attest-agent',
        'agent_type': 'seller',
        'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-attest',
    }
    resp = await client.post('/api/v2/agents/onboard', json=payload,
                             headers={'Authorization': f'Bearer {token}'})
    agent_id = resp.json()['agent_id']
    agent_token = resp.json()['agent_jwt_token']
    # Attest runtime
    resp = await client.post(f'/api/v2/agents/{agent_id}/attest/runtime',
                             json={'runtime_name': 'python', 'runtime_version': '3.11'},
                             headers={'Authorization': f'Bearer {agent_token}'})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_attest_runtime_wrong_agent(client, make_creator, make_agent):
    creator, creator_token = await make_creator(display_name='v2-wrong')
    payload = {
        'name': 'wrong-agent',
        'agent_type': 'seller',
        'public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7test-wrong',
    }
    resp = await client.post('/api/v2/agents/onboard', json=payload,
                             headers={'Authorization': f'Bearer {creator_token}'})
    agent_id = resp.json()['agent_id']
    # Use a different agent token
    other, other_token = await make_agent(name='other-agent')
    resp = await client.post(f'/api/v2/agents/{agent_id}/attest/runtime',
                             json={'runtime_name': 'python'},
                             headers={'Authorization': f'Bearer {other_token}'})
    assert resp.status_code == 403
