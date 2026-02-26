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


# ---------------------------------------------------------------------------
# Coverage gap tests — routes.py lines 91, 111, 114, 118-119, 128-136,
#                      187, 207-216, 241, 255, 268-271
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_client_returns_response_body(client, make_agent, auth_header):
    """Line 91: ClientCreateResponse is returned with all fields populated."""
    a, token = await make_agent(name='oa-body')
    payload = {
        'name': 'Full Body App',
        'redirect_uris': ['https://body.example.com/cb'],
        'scopes': 'read write',
        'owner_id': a.id,
    }
    resp = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data['name'] == 'Full Body App'
    assert data['scopes'] == 'read write'
    assert data['status'] == 'active'
    assert data['redirect_uris'] == ['https://body.example.com/cb']


@pytest.mark.asyncio
async def test_get_client_no_auth(client):
    """Line 111: GET /clients/{id} without auth header returns 401."""
    resp = await client.get(f'{BASE}/clients/some-client-id')
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_client_malformed_auth(client):
    """Line 114: malformed (non-Bearer) Authorization header returns 401."""
    resp = await client.get(
        f'{BASE}/clients/some-client-id',
        headers={'Authorization': 'Token something'},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_client_bad_token(client):
    """Lines 118-119: invalid JWT in GET /clients/{id} returns 401."""
    resp = await client.get(
        f'{BASE}/clients/some-client-id',
        headers={'Authorization': 'Bearer bad-jwt-token'},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_client_details_includes_grant_types(client, make_agent, auth_header):
    """Lines 128-136: successful GET /clients/{id} returns grant_types field."""
    a, token = await make_agent(name='oa-gc2')
    payload = {
        'name': 'Grant Types App',
        'redirect_uris': ['https://gt.example.com/cb'],
        'scopes': 'read',
        'owner_id': a.id,
    }
    r = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token))
    cid = r.json()['client_id']
    resp = await client.get(f'{BASE}/clients/{cid}', headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert 'grant_types' in data
    assert 'created_at' in data
    assert 'redirect_uris' in data


@pytest.mark.asyncio
async def test_authorize_user_id_in_production_rejected(client, make_agent, auth_header):
    """Line 187: user_id query param rejected when is_prod=True."""
    from unittest.mock import patch, MagicMock

    a, token = await make_agent(name='oa-prod')
    payload = {
        'name': 'Prod App',
        'redirect_uris': ['https://prod.example.com/cb'],
        'scopes': 'read',
        'owner_id': a.id,
    }
    r = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token))
    cid = r.json()['client_id']

    mock_s = MagicMock()
    mock_s.environment = 'production'

    with patch('marketplace.oauth2.routes.settings', mock_s):
        resp = await client.get(
            f'{BASE}/authorize',
            params={
                'client_id': cid,
                'redirect_uri': 'https://prod.example.com/cb',
                'user_id': a.id,
            },
        )
    assert resp.status_code == 401
    assert 'production' in resp.json()['detail'].lower()


@pytest.mark.asyncio
async def test_authorize_with_state_in_redirect(client, make_agent, auth_header):
    """Lines 213-214: state parameter is appended to redirect_uri in response."""
    a, token = await make_agent(name='oa-state')
    payload = {
        'name': 'State App',
        'redirect_uris': ['https://state.example.com/cb'],
        'scopes': 'read',
        'owner_id': a.id,
    }
    r = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token))
    cid = r.json()['client_id']

    resp = await client.get(
        f'{BASE}/authorize',
        params={
            'client_id': cid,
            'redirect_uri': 'https://state.example.com/cb',
            'user_id': a.id,
            'state': 'csrf-token-xyz',
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert 'csrf-token-xyz' in data['redirect_uri']
    assert 'code' in data


@pytest.mark.asyncio
async def test_authorize_invalid_client_returns_400(client, make_agent, auth_header):
    """Line 207-208: ValueError from server.authorize raises HTTP 400."""
    a, token = await make_agent(name='oa-inv')
    resp = await client.get(
        f'{BASE}/authorize',
        params={
            'client_id': 'nonexistent-client-id',
            'redirect_uri': 'https://invalid.example.com/cb',
            'user_id': a.id,
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_token_exchange_returns_token_response(client, make_agent, auth_header):
    """Line 241: successful token exchange returns TokenResponse with all fields."""
    a, token = await make_agent(name='oa-tok')
    payload = {
        'name': 'Token App',
        'redirect_uris': ['https://tok.example.com/cb'],
        'scopes': 'read',
        'owner_id': a.id,
    }
    r = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token))
    client_data = r.json()

    # Get an authorization code
    code_resp = await client.get(
        f'{BASE}/authorize',
        params={
            'client_id': client_data['client_id'],
            'redirect_uri': 'https://tok.example.com/cb',
            'user_id': a.id,
        },
    )
    assert code_resp.status_code == 200
    code = code_resp.json()['code']

    # Exchange for token
    tok_resp = await client.post(f'{BASE}/token', json={
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': client_data['client_id'],
        'client_secret': client_data['client_secret'],
        'redirect_uri': 'https://tok.example.com/cb',
    })
    assert tok_resp.status_code == 200
    tok_data = tok_resp.json()
    assert 'access_token' in tok_data
    assert tok_data['token_type'].lower() == 'bearer'


@pytest.mark.asyncio
async def test_revoke_returns_revoked_field(client, make_agent, auth_header):
    """Line 255: revoke returns {'revoked': bool}."""
    a, token = await make_agent(name='oa-rev')
    payload = {
        'name': 'Rev App',
        'redirect_uris': ['https://rev.example.com/cb'],
        'scopes': 'read',
        'owner_id': a.id,
    }
    r = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token))
    client_data = r.json()

    # Get code then token
    code_resp = await client.get(
        f'{BASE}/authorize',
        params={
            'client_id': client_data['client_id'],
            'redirect_uri': 'https://rev.example.com/cb',
            'user_id': a.id,
        },
    )
    code = code_resp.json()['code']
    tok_resp = await client.post(f'{BASE}/token', json={
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': client_data['client_id'],
        'client_secret': client_data['client_secret'],
        'redirect_uri': 'https://rev.example.com/cb',
    })
    access_token = tok_resp.json()['access_token']

    # Revoke the token
    rev_resp = await client.post(
        f'{BASE}/revoke',
        json={'token': access_token, 'client_id': client_data['client_id']},
    )
    assert rev_resp.status_code == 200
    assert 'revoked' in rev_resp.json()


@pytest.mark.asyncio
async def test_userinfo_with_bearer_prefix(client, make_agent, auth_header):
    """Lines 268-271: userinfo strips 'Bearer ' prefix and returns user info."""
    a, token_jwt = await make_agent(name='oa-ui')
    payload = {
        'name': 'UI App',
        'redirect_uris': ['https://ui.example.com/cb'],
        'scopes': 'read',
        'owner_id': a.id,
    }
    r = await client.post(f'{BASE}/clients', json=payload, headers=auth_header(token_jwt))
    client_data = r.json()

    # Get code then token
    code_resp = await client.get(
        f'{BASE}/authorize',
        params={
            'client_id': client_data['client_id'],
            'redirect_uri': 'https://ui.example.com/cb',
            'user_id': a.id,
        },
    )
    code = code_resp.json()['code']
    tok_resp = await client.post(f'{BASE}/token', json={
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': client_data['client_id'],
        'client_secret': client_data['client_secret'],
        'redirect_uri': 'https://ui.example.com/cb',
    })
    access_token = tok_resp.json()['access_token']

    # Call userinfo with Bearer prefix in access_token param
    ui_resp = await client.get(
        f'{BASE}/userinfo',
        params={'access_token': f'Bearer {access_token}'},
    )
    assert ui_resp.status_code == 200
    data = ui_resp.json()
    assert 'sub' in data
