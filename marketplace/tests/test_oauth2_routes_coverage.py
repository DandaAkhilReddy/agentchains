"""Tests for uncovered lines in marketplace/oauth2/routes.py."""

import pytest

BASE = '/oauth2'


@pytest.mark.asyncio
async def test_register_client_success(client, make_agent, auth_header):
    a, token = await make_agent(name='oa-reg')
    payload = {'name': 'My App', 'redirect_uris': ['https://example.com/cb'],
               'scopes': 'read write', 'owner_id': a.id}
    resp = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert 'client_id' in data and 'client_secret' in data


@pytest.mark.asyncio
async def test_register_client_no_auth(client):
    payload = {'name': 'App', 'redirect_uris': ['https://x.com/cb'], 'scopes': 'read', 'owner_id': 'x'}
    resp = await client.post(f'{BASE}/clients', json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_client_bad_token(client):
    payload = {'name': 'App', 'redirect_uris': ['https://x.com/cb'], 'scopes': 'read', 'owner_id': 'x'}
    resp = await client.post(f'{BASE}/clients', json=payload, headers={'Authorization': 'Bearer bad'})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_client_malformed_auth(client):
    payload = {'name': 'App', 'redirect_uris': ['https://x.com/cb'], 'scopes': 'read', 'owner_id': 'x'}
    resp = await client.post(f'{BASE}/clients', json=payload, headers={'Authorization': 'NotBearer tok'})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_client_success(client, make_agent, auth_header):
    a, token = await make_agent(name='oa-gc')
    payload = {'name': 'GC', 'redirect_uris': ['https://e.com/cb'], 'scopes': 'read', 'owner_id': a.id}
    r = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token))
    cid = r.json()['client_id']
    resp = await client.get(f'{BASE}/clients/{cid}', headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()['client_id'] == cid


@pytest.mark.asyncio
async def test_get_client_not_found(client, make_agent, auth_header):
    _, token = await make_agent(name='oa-nf')
    resp = await client.get(f'{BASE}/clients/nonexistent', headers=auth_header(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_client_not_owner(client, make_agent, auth_header):
    a, tok_a = await make_agent(name='oa-ow1')
    b, tok_b = await make_agent(name='oa-ow2')
    payload = {'name': 'OA', 'redirect_uris': ['https://x.com/cb'], 'scopes': 'read', 'owner_id': a.id}
    r = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(tok_a))
    cid = r.json()['client_id']
    resp = await client.get(f'{BASE}/clients/{cid}', headers=auth_header(tok_b))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_authorize_no_auth(client):
    resp = await client.get(f'{BASE}/authorize', params={'client_id': 'x', 'redirect_uri': 'https://x.com/cb'})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_authorize_with_user_id(client, make_agent, auth_header):
    a, token = await make_agent(name='oa-au1')
    payload = {'name': 'AU', 'redirect_uris': ['https://e.com/cb'], 'scopes': 'read', 'owner_id': a.id}
    r = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token))
    cid = r.json()['client_id']
    resp = await client.get(f'{BASE}/authorize', params={
        'client_id': cid, 'redirect_uri': 'https://e.com/cb', 'user_id': a.id, 'state': 'st'})
    assert resp.status_code == 200
    assert 'code' in resp.json()


@pytest.mark.asyncio
async def test_authorize_with_bearer(client, make_agent, auth_header):
    a, token = await make_agent(name='oa-au2')
    payload = {'name': 'AU2', 'redirect_uris': ['https://b.com/cb'], 'scopes': 'read', 'owner_id': a.id}
    r = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token))
    cid = r.json()['client_id']
    resp = await client.get(f'{BASE}/authorize', params={
        'client_id': cid, 'redirect_uri': 'https://b.com/cb'}, headers=auth_header(token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_authorize_invalid_bearer(client):
    resp = await client.get(f'{BASE}/authorize', params={'client_id': 'x', 'redirect_uri': 'https://x.com/cb'},
                            headers={'Authorization': 'Bearer bad'})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_exchange_invalid(client):
    payload = {'grant_type': 'bad_grant', 'code': 'fake', 'client_id': 'x', 'client_secret': 'y'}
    resp = await client.post(f'{BASE}/token', json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_revoke_nonexistent(client):
    resp = await client.post(f'{BASE}/revoke', json={'token': 'fake'})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_openid_configuration(client):
    resp = await client.get(f'{BASE}/.well-known/openid-configuration')
    assert resp.status_code == 200
    data = resp.json()
    assert data['issuer'] == 'https://agentchains.io'
    assert 'token_endpoint' in data


@pytest.mark.asyncio
async def test_userinfo_invalid(client):
    resp = await client.get(f'{BASE}/userinfo', params={'access_token': 'invalid'})
    assert resp.status_code == 401
