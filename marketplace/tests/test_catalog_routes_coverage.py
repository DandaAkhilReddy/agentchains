"""Tests for uncovered lines in marketplace/api/catalog.py."""

import pytest


@pytest.mark.asyncio
async def test_catalog_get_entry_not_found(client):
    resp = await client.get('/api/v1/catalog/nonexistent-id')
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_catalog_update_entry_not_found(client, make_agent, auth_header):
    _, token = await make_agent(name='cat-up-nf')
    resp = await client.patch('/api/v1/catalog/nonexistent', json={'topic': 'new'},
                              headers=auth_header(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_catalog_delete_entry_not_found(client, make_agent, auth_header):
    _, token = await make_agent(name='cat-del-nf')
    resp = await client.delete('/api/v1/catalog/nonexistent', headers=auth_header(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_catalog_unsubscribe_not_found(client, make_agent, auth_header):
    _, token = await make_agent(name='cat-unsub-nf')
    resp = await client.delete('/api/v1/catalog/subscribe/nonexistent', headers=auth_header(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_catalog_update_with_schema(client, make_agent, auth_header):
    a, token = await make_agent(name='cat-up-sch')
    # Create entry
    payload = {'namespace': 'web_search', 'topic': 'test', 'description': 'desc'}
    resp = await client.post('/api/v1/catalog', json=payload, headers=auth_header(token))
    assert resp.status_code == 200
    entry_id = resp.json()['id']
    # Update with schema
    resp = await client.patch(f'/api/v1/catalog/{entry_id}',
                              json={'schema_json': {'type': 'object'}, 'description': 'updated'},
                              headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()['description'] == 'updated'


@pytest.mark.asyncio
async def test_catalog_auto_populate(client, make_agent, make_listing, auth_header):
    a, token = await make_agent(name='cat-auto')
    await make_listing(a.id, title='Auto List', category='web_search')
    resp = await client.post('/api/v1/catalog/auto-populate', headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert 'created' in data


@pytest.mark.asyncio
async def test_catalog_search_with_filters(client, make_agent, auth_header):
    a, token = await make_agent(name='cat-sf')
    payload = {'namespace': 'web_search', 'topic': 'python-tut', 'description': 'Python tutorials'}
    await client.post('/api/v1/catalog', json=payload, headers=auth_header(token))
    resp = await client.get('/api/v1/catalog/search', params={
        'q': 'python', 'namespace': 'web_search', 'min_quality': 0.1, 'max_price': 10.0})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_catalog_get_agent_entries(client, make_agent, auth_header):
    a, token = await make_agent(name='cat-agent')
    payload = {'namespace': 'web_search', 'topic': 'agent-topic'}
    await client.post('/api/v1/catalog', json=payload, headers=auth_header(token))
    resp = await client.get(f'/api/v1/catalog/agent/{a.id}')
    assert resp.status_code == 200
    data = resp.json()
    assert data['count'] >= 1


@pytest.mark.asyncio
async def test_catalog_subscribe(client, make_agent, auth_header):
    _, token = await make_agent(name='cat-sub')
    payload = {'namespace_pattern': 'web_search.*', 'topic_pattern': '*',
               'notify_via': 'websocket'}
    resp = await client.post('/api/v1/catalog/subscribe', json=payload, headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'active'
